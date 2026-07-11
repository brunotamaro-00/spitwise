from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.capture import apply_category_pick
from app.bot.render import BotReply, text_reply
from app.db.models import Movement, User

_SPLIT_MAP = {"split_shared": "shared", "split_mine": "payer_only", "split_theirs": "other_only"}
_SPLIT_LABEL = {"shared": "compartido", "payer_only": "solo tuyo", "other_only": "solo del otro"}


async def handle_interactive(session: AsyncSession, user: User, wa_id: str, interactive_id: str, today: date) -> BotReply:
    if interactive_id.startswith("cat_pick:"):
        rest = interactive_id[len("cat_pick:"):]
        token, cid = rest.split("|", 1)
        return await apply_category_pick(session, user, token, int(cid))

    for prefix, split_val in _SPLIT_MAP.items():
        if interactive_id.startswith(prefix + ":"):
            mid = int(interactive_id.split(":", 1)[1])
            mv = (await session.execute(select(Movement).where(Movement.id == mid))).scalar_one_or_none()
            if mv is None:
                return text_reply("⚠️ No encontrado: ese movimiento ya no existe.")
            mv.split = split_val
            await session.commit()
            return text_reply(f"✅ División actualizada: {_SPLIT_LABEL[split_val]}.")

    if interactive_id.startswith("del_confirm:"):
        mid = int(interactive_id.split(":", 1)[1])
        mv = (await session.execute(select(Movement).where(Movement.id == mid))).scalar_one_or_none()
        if mv is not None:
            await session.delete(mv)
            await session.commit()
        return text_reply("🗑️ Borrado.")

    if interactive_id.startswith("del_cancel:"):
        return text_reply("Cancelado.")

    return text_reply("⚠️ Botón desconocido.")
