from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.capture import apply_category_pick
from app.bot.render import BotReply, deleted_card, movement_summary, text_reply
from app.db.models import Category, Movement, User


async def _summary_lines(session: AsyncSession, movements: list[Movement]) -> str:
    """Desglose de los movimientos (para confirmar qué se borró), antes de borrarlos."""
    users = {u.id: u.username for u in (await session.execute(select(User))).scalars().all()}
    cats = {c.id: c.name for c in (await session.execute(select(Category))).scalars().all()}
    return "\n".join(
        movement_summary(m, cats.get(m.category_id), users.get(m.paid_by, "?"))
        for m in movements
    )


# Legacy: botones de split de la versión anterior (pueden quedar en el historial del chat).
_SPLIT_MAP = {"split_shared": "shared", "split_mine": "payer_only", "split_theirs": "other_only"}
_SPLIT_LABEL = {"shared": "compartido", "payer_only": "solo tuyo", "other_only": "solo del otro"}


def _token_and_id(interactive_id: str, prefix: str) -> tuple[str, int]:
    rest = interactive_id[len(prefix):]
    token, mid = rest.split("|", 1)
    return token, int(mid)


async def _delete_by_ids(session: AsyncSession, user: User, ids: list[int], expected: int | None = None) -> BotReply:
    movements = (await session.execute(
        select(Movement).where(Movement.id.in_(ids))
    )).scalars().all()
    summary = await _summary_lines(session, movements)
    for mv in movements:
        await session.delete(mv)
    await session.commit()
    n = len(movements)
    if n == 0:
        return text_reply("⚠️ Ya no estaban esos movimientos.")
    reply = deleted_card(summary, plural=n)
    if expected is not None and n < expected:
        missing = expected - n
        reply = f"{reply}\n⚠️ {missing} ya no existían."
    return text_reply(reply)


async def handle_interactive(session: AsyncSession, user: User, wa_id: str, interactive_id: str, today: date) -> BotReply:
    try:
        return await _handle_interactive(session, user, wa_id, interactive_id, today)
    except (ValueError, IndexError):
        return text_reply("⚠️ Botón inválido o viejo.")


async def _handle_interactive(session: AsyncSession, user: User, wa_id: str, interactive_id: str, today: date) -> BotReply:
    if interactive_id.startswith("cat_pick:"):
        token, cid = _token_and_id(interactive_id, "cat_pick:")
        return await apply_category_pick(session, user, token, cid, today)

    if interactive_id.startswith("edit_pick:"):
        from app.bot.editor import apply_edit_pick
        token, mid = _token_and_id(interactive_id, "edit_pick:")
        return await apply_edit_pick(session, user, token, mid, today)

    if interactive_id.startswith("del_pick:"):
        from app.bot.editor import apply_delete_pick
        token, mid = _token_and_id(interactive_id, "del_pick:")
        return await apply_delete_pick(session, user, token, mid)

    for prefix, split_val in _SPLIT_MAP.items():
        if interactive_id.startswith(prefix + ":"):
            mid = int(interactive_id.split(":", 1)[1])
            mv = (await session.execute(select(Movement).where(Movement.id == mid))).scalar_one_or_none()
            if mv is None:
                return text_reply("⚠️ No encontrado: ese movimiento ya no existe.")
            mv.split = split_val
            await session.commit()
            return text_reply(f"✅ División actualizada: {_SPLIT_LABEL[split_val]}.")

    if interactive_id.startswith("qa_del:"):
        from app.bot.pending import close_pending, load_pending
        token = interactive_id[len("qa_del:"):]
        data = await load_pending(session, token, owner=user.username)
        if data is None:
            return text_reply("⚠️ Expiró: esa confirmación ya no está disponible.")
        ids = [int(i) for i in data.get("ids") or []]
        expected = len(ids)
        reply = await _delete_by_ids(session, user, ids, expected=expected)
        await close_pending(session, token)
        return reply

    if interactive_id.startswith("del_confirm:"):
        from app.bot.pending import close_pending, load_pending
        rest = interactive_id.split(":", 1)[1]
        # Nuevo: token de pending. Legacy: id numérico sin TTL.
        if rest.isdigit():
            mid = int(rest)
            return await _delete_by_ids(session, user, [mid])
        data = await load_pending(session, rest, owner=user.username)
        if data is None:
            return text_reply("⚠️ Expiró: esa confirmación ya no está disponible.")
        ids = [int(i) for i in data.get("ids") or []]
        reply = await _delete_by_ids(session, user, ids, expected=len(ids))
        await close_pending(session, rest)
        return reply

    if interactive_id.startswith("del_cancel:"):
        return text_reply("Cancelado.")

    if interactive_id.startswith("doc_save:"):
        from app.bot.documents.pipeline import confirm_doc_upload
        return await confirm_doc_upload(session, user, interactive_id[len("doc_save:"):])

    if interactive_id.startswith("doc_cancel:"):
        from app.bot.documents.pipeline import cancel_doc_upload
        return await cancel_doc_upload(session, user, interactive_id[len("doc_cancel:"):])

    if interactive_id.startswith("note_save:"):
        from app.bot.trip_notes import confirm_note
        return await confirm_note(session, user, interactive_id[len("note_save:"):])

    if interactive_id.startswith("note_cancel:"):
        from app.bot.trip_notes import cancel_note
        return await cancel_note(session, user, interactive_id[len("note_cancel:"):])

    return text_reply("⚠️ Botón desconocido.")
