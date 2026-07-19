"""Runner de escenarios de charla contra el bot (sin Meta).

Llama a `dispatch()` con LLM real (OpenAI desde spitwise/.env), DB SQLite
efímera, seed de usuarios/paradas/FX/movimientos previos.

Cada corrida **borra y reescribe** `scripts/bot_scenarios.md` con el transcript
de esa corrida (no acumula historial).

Uso (desde backend/):

    .venv/bin/python scripts/bot_scenario_runner.py
    .venv/bin/python scripts/bot_scenario_runner.py --from 6 --to 10
    .venv/bin/python scripts/bot_scenario_runner.py --only 7,12,15

Secuencial: un turno a la vez, pausa entre turnos y entre conversaciones
para no quemar la API. Requiere OPENAI_API_KEY en spitwise/.env.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[2]  # spitwise/
SCRIPTS = Path(__file__).resolve().parent
OUT_MD = SCRIPTS / "bot_scenarios.md"

load_dotenv(ROOT / ".env", override=False)

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ.setdefault("LLM_PROVIDER", "openai")
os.environ.setdefault("ENVIRONMENT", "dev")
os.environ.setdefault("SECRET_KEY", "scenario-runner-local-only")
os.environ["AUTH_USERS"] = "bruno:demo:549111,katia:demo:549222"

from app.api.auth import hash_password  # noqa: E402
from app.bot.dispatcher import dispatch  # noqa: E402
from app.bot.render import BotReply  # noqa: E402
from app.categories.seed import seed_categories  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db.models import Base, Category, FxRate, Movement, Stop, User  # noqa: E402

get_settings.cache_clear()

TODAY = date(2026, 8, 20)
PAUSE_BETWEEN_TURNS_S = 4.0
PAUSE_BETWEEN_CONVOS_S = 6.0

BRUNO_WA = "549111"
KATIA_WA = "549222"


@dataclass
class Turn:
    wa_id: str
    text: str | None = None
    interactive_id: str | None = None
    note: str = ""
    # Si True y el reply anterior trae botones, usa el 1.er botón.
    tap_first_button: bool = False
    # Si set, elige el botón cuyo label contenga este substring (casefold).
    tap_button_contains: str | None = None


@dataclass
class Conversation:
    name: str
    goal: str
    turns: list[Turn]
    expect_hints: list[str] = field(default_factory=list)


@dataclass
class TurnRecord:
    who: str
    inbound: str
    note: str
    reply_text: str
    elapsed_s: float
    db_snapshot: str


@dataclass
class ConvoRecord:
    index: int
    name: str
    goal: str
    expect_hints: list[str]
    turns: list[TurnRecord] = field(default_factory=list)


# Catálogo de escenarios. Editar acá; el .md se regenera solo al correr.
CONVERSATIONS: list[Conversation] = [
    Conversation(
        name="Cuotas + corrección de total",
        goal="Gasto en etapas (30% hoy / resto check-in) y corregir el total del batch.",
        turns=[
            Turn(BRUNO_WA,
                 "hostel interlaken 430 chf, 30% hoy y el resto al check-in el 3 de septiembre",
                 note="cuotas"),
            Turn(BRUNO_WA, "no, el total era 480 no 430", note="edit monto del batch"),
        ],
        expect_hints=["cuotas/batch", "edit redistribuye a total 480"],
    ),
    Conversation(
        name="Multi-gasto mezclado + fix de split",
        goal="3 ítems (payer/split distintos) y corregir el split del taxi por ref.",
        turns=[
            Turn(BRUNO_WA,
                 "en Roma ayer: cena 45 euros pagó katia, taxi 12 solo mío, helado 5",
                 note="batch 3 ítems"),
            Turn(BRUNO_WA, "el taxi en realidad era compartido", note="edit split taxi"),
        ],
        expect_hints=["3 movimientos", "cena shared (solo pagó≠solo de)", "taxi → shared"],
    ),
    Conversation(
        name="Day-trip + payer/split + saldo",
        goal="Sintra (no parada) → Lisboa; pagó Katia + solo ella; pregunta de deuda.",
        turns=[
            Turn(BRUNO_WA, "paseo a sintra 28 euros", note="daytrip → Lisboa"),
            Turn(BRUNO_WA, "en realidad lo pagó katia y es solo de ella",
                 note="edit paid_by + split"),
            Turn(BRUNO_WA, "¿cuánto le debo a katia por ese paseo?", note="Q&A"),
        ],
        expect_hints=["ciudad Lisboa", "Solo Katia (payer_only)", "Q&A sin inventar"],
    ),
    Conversation(
        name="Settlement cruzado + ¿quién debe?",
        goal="Bruno salda con 'le pasé…'; Katia pregunta el neto.",
        turns=[
            Turn(BRUNO_WA, "le pasé 80 usd a katia por lo del hotel de paris",
                 note="settlement"),
            Turn(KATIA_WA, "che y ahora quién debe plata?", note="Q&A balance"),
        ],
        expect_hints=["settlement Bruno→Katia", "balance post-pago"],
    ),
    Conversation(
        name="Pago futuro + ¿entra al saldo? + traer a hoy",
        goal="payment_date futura → pending; preguntar si cuenta; mover a hoy.",
        turns=[
            Turn(BRUNO_WA,
                 "entrada al louvre 44 eur, se paga el 15 de septiembre en paris",
                 note="pending futuro"),
            Turn(BRUNO_WA, "eso del louvre, ¿ya entra en el saldo o todavía no?",
                 note="Q&A pending vs balance"),
            Turn(BRUNO_WA, "ok, poné que se paga hoy", note="edit payment_date"),
        ],
        expect_hints=["pending", "Q&A: NO entra al saldo", "edit fecha sin mover ciudad"],
    ),
    Conversation(
        name="Categoría ambigua + cat_pick",
        goal="Descripción vaga → botones de categoría; confirmar con tap.",
        turns=[
            Turn(BRUNO_WA, "eso de la tienda 35 eur en lisboa", note="categoría ambigua"),
            Turn(BRUNO_WA, tap_first_button=True, note="tap 1.er candidato"),
        ],
        expect_hints=["botones cat_pick", "gasto confirmado tras tap"],
    ),
    Conversation(
        name="Batch + borrar (fast path) + confirmar los N",
        goal="Multi-gasto + comando borrar sin LLM + del_confirm del batch.",
        turns=[
            Turn(BRUNO_WA, "en paris: metro 4 eur, croissant 3, agua 2", note="batch 3"),
            Turn(BRUNO_WA, "borrar", note="fast path"),
            Turn(BRUNO_WA, tap_button_contains="Borrar los", note="confirmar batch"),
        ],
        expect_hints=["mismo batch_key", "borrar ofrece batch vs último", "borrados los 3"],
    ),
    Conversation(
        name="Corrección corta post-carga",
        goal="last_expense → edit por mensaje sin monto propio.",
        turns=[
            Turn(KATIA_WA, "tren 39 usd en pititas", note="carga"),
            Turn(KATIA_WA, "no, contalo solo para katia", note="edit split corto"),
        ],
        expect_hints=["no crea 2.º gasto", "split Solo Katia"],
    ),
    Conversation(
        name="Fast path saldo/total vs pregunta NL",
        goal="quick.py sin LLM vs mismo dato vía Q&A.",
        turns=[
            Turn(BRUNO_WA, "saldo", note="fast path"),
            Turn(BRUNO_WA, "¿quién debe plata ahora?", note="Q&A"),
            Turn(BRUNO_WA, "total", note="fast path"),
        ],
        expect_hints=["saldo/total instantáneos", "Q&A alineado al neto"],
    ),
    Conversation(
        name="Stop local / owner split (Pititas)",
        goal="Default split por owner_username; después forzar shared.",
        turns=[
            Turn(BRUNO_WA, "super 22 eur en pititas", note="owner default"),
            Turn(BRUNO_WA, "en realidad era compartido", note="edit → shared"),
        ],
        expect_hints=["default Solo Katia", "2º turno shared"],
    ),
    Conversation(
        name="General / pre-viaje sin ciudad",
        goal="Fecha fuera de itinerario → city null; Q&A lo admite.",
        turns=[
            Turn(BRUNO_WA, "seguro de viaje 320 usd el 1 de julio, solo mío",
                 note="fuera de rango"),
            Turn(BRUNO_WA, "¿en qué ciudad quedó el seguro?", note="Q&A"),
        ],
        expect_hints=["city null / General", "no inventar 1.ª parada"],
    ),
    Conversation(
        name="Delete por texto + confirmación",
        goal="intent delete del parser → botones; nunca hard-delete.",
        turns=[
            Turn(BRUNO_WA,
                 "museo vaticano 25 eur en roma, solo de katia, pagó katia",
                 note="carga"),
            Turn(BRUNO_WA, "borrá el museo", note="delete NL"),
            Turn(BRUNO_WA, tap_button_contains="Borrar", note="confirmar"),
        ],
        expect_hints=["turno 2 pide confirm", "tras tap desaparece"],
    ),
    Conversation(
        name="Q&A follow-up elíptico",
        goal="Historial fresco: reusar intención cambiando ciudad/attribution.",
        turns=[
            Turn(BRUNO_WA, "¿cuánto gastamos en comida en paris?", note="Q&A"),
            Turn(BRUNO_WA, "¿y en roma?", note="follow-up ciudad"),
            Turn(BRUNO_WA, "¿y cuánto puse yo de bolsillo ahí?", note="attribution paid"),
        ],
        expect_hints=["reusa comida", "attribution paid en Roma"],
    ),
    Conversation(
        name="Moneda explícita ≠ moneda ciudad + edit",
        goal="USD dicho en Lisboa (EUR); después corregir a euros.",
        turns=[
            Turn(BRUNO_WA, "cena 40 usd en lisboa", note="USD explícito"),
            Turn(BRUNO_WA, "era en euros, no dólares", note="edit currency"),
        ],
        expect_hints=["1º queda USD", "2º → EUR + FX"],
    ),
    Conversation(
        name="Settlement 'me pasó' desde Katia",
        goal="Dirección del pago desde el otro lado + saldo.",
        turns=[
            Turn(KATIA_WA, "bruno me pasó 50 usd", note="settlement"),
            Turn(BRUNO_WA, "saldo", note="fast path"),
        ],
        expect_hints=["Bruno→Katia (no invertido)", "no es expense"],
    ),
]


async def seed(session: AsyncSession) -> None:
    bruno = User(username="bruno", password_hash=hash_password("demo"), whatsapp_wa_id=BRUNO_WA)
    katia = User(username="katia", password_hash=hash_password("demo"), whatsapp_wa_id=KATIA_WA)
    session.add_all([bruno, katia])
    await seed_categories(session)
    await session.flush()

    session.add_all([
        Stop(slug="roma", order=1, name="Roma", arrival_date=date(2026, 8, 1),
             departure_date=date(2026, 8, 6), currency_code="EUR", timezone="Europe/Rome"),
        Stop(slug="paris", order=2, name="Paris", arrival_date=date(2026, 8, 6),
             departure_date=date(2026, 8, 12), currency_code="EUR", timezone="Europe/Paris"),
        Stop(slug="lisboa", order=3, name="Lisboa", arrival_date=date(2026, 8, 12),
             departure_date=date(2026, 8, 22), currency_code="EUR", timezone="Europe/Lisbon"),
        Stop(slug="interlaken", order=4, name="Interlaken", arrival_date=date(2026, 9, 1),
             departure_date=date(2026, 9, 6), currency_code="CHF", timezone="Europe/Zurich"),
        # Stop local (solo Spitwise): default split por owner.
        Stop(slug="pititas", order=5, name="Pititas", arrival_date=date(2026, 9, 4),
             departure_date=date(2026, 9, 12), currency_code="EUR", timezone="Europe/Paris",
             is_local=True, owner_username="katia", country_flag="😊"),
    ])

    fx_dates = {
        TODAY, TODAY - timedelta(days=1), date(2026, 7, 1), date(2026, 8, 10),
        date(2026, 9, 3), date(2026, 9, 15),
    }
    for cur, rate in (("EUR", "1.10"), ("CHF", "1.20"), ("GBP", "1.30"), ("USD", "1.0")):
        for d in fx_dates:
            if cur == "USD":
                continue
            session.add(FxRate(currency=cur, rate_date=d, rate_to_usd=Decimal(rate)))

    await session.flush()
    cats = {c.name: c.id for c in (await session.execute(select(Category))).scalars()}

    session.add(Movement(
        type="expense", amount=Decimal("200"), currency="EUR",
        amount_usd=Decimal("220"), fx_rate=Decimal("1.10"), fx_source="cache",
        description="Hotel Paris", category_id=cats.get("Alojamiento"),
        city_name="Paris", stop_slug="paris", paid_by=katia.id, split="shared",
        created_by=katia.id, payment_date=date(2026, 8, 10), status="confirmed",
        created_at=datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc),
    ))
    session.add(Movement(
        type="expense", amount=Decimal("60"), currency="EUR",
        amount_usd=Decimal("66"), fx_rate=Decimal("1.10"), fx_source="cache",
        description="Cena Lisboa", category_id=cats.get("Comida"),
        city_name="Lisboa", stop_slug="lisboa", paid_by=bruno.id, split="shared",
        created_by=bruno.id, payment_date=TODAY - timedelta(days=1), status="confirmed",
        created_at=datetime(2026, 8, 19, 20, 0, tzinfo=timezone.utc),
    ))
    # Comida en Paris/Roma para Q&A follow-ups (escenario 13).
    session.add(Movement(
        type="expense", amount=Decimal("80"), currency="EUR",
        amount_usd=Decimal("88"), fx_rate=Decimal("1.10"), fx_source="cache",
        description="Cena Paris", category_id=cats.get("Comida"),
        city_name="Paris", stop_slug="paris", paid_by=bruno.id, split="shared",
        created_by=bruno.id, payment_date=date(2026, 8, 8), status="confirmed",
        created_at=datetime(2026, 8, 8, 21, 0, tzinfo=timezone.utc),
    ))
    session.add(Movement(
        type="expense", amount=Decimal("50"), currency="EUR",
        amount_usd=Decimal("55"), fx_rate=Decimal("1.10"), fx_source="cache",
        description="Pasta Roma", category_id=cats.get("Comida"),
        city_name="Roma", stop_slug="roma", paid_by=katia.id, split="shared",
        created_by=katia.id, payment_date=date(2026, 8, 3), status="confirmed",
        created_at=datetime(2026, 8, 3, 20, 0, tzinfo=timezone.utc),
    ))
    await session.commit()


def _fmt_reply(reply: BotReply) -> str:
    lines = []
    if reply.text:
        lines.append(reply.text)
    if reply.buttons:
        lines.append("[botones]")
        for bid, label in reply.buttons:
            lines.append(f"  · {label}  (`{bid}`)")
    if reply.movement_id is not None:
        lines.append(f"(movement_id={reply.movement_id})")
    return "\n".join(lines) if lines else "(reply vacío)"


async def _snapshot(session: AsyncSession) -> str:
    rows = (await session.execute(
        select(Movement).order_by(Movement.id.desc()).limit(8)
    )).scalars().all()
    if not rows:
        return "(sin movimientos)"
    users = {u.id: u.username for u in (await session.execute(select(User))).scalars()}
    cats = {c.id: c.name for c in (await session.execute(select(Category))).scalars()}
    out = []
    for m in reversed(rows):
        out.append(
            f"#{m.id} {m.type} {m.amount} {m.currency} usd={m.amount_usd} "
            f"desc={m.description!r} city={m.city_name} split={m.split} "
            f"paid_by={users.get(m.paid_by)} cat={cats.get(m.category_id)} "
            f"pay={m.payment_date} status={m.status} batch={m.batch_key}"
        )
    return "\n".join(out)


def _pick_button(reply: BotReply, turn: Turn) -> str:
    if not reply.buttons:
        raise RuntimeError("tap pedido pero el bot no ofreció botones")
    if turn.tap_button_contains:
        needle = turn.tap_button_contains.casefold()
        for bid, label in reply.buttons:
            if needle in label.casefold():
                return bid
        labels = ", ".join(l for _, l in reply.buttons)
        raise RuntimeError(
            f"ningún botón contiene {turn.tap_button_contains!r}; había: {labels}"
        )
    return reply.buttons[0][0]


async def run_turn(
    session: AsyncSession,
    turn: Turn,
    *,
    last_reply: BotReply | None,
) -> tuple[BotReply, TurnRecord]:
    interactive_id = turn.interactive_id
    text = turn.text
    msg_type = "text"

    if turn.tap_first_button or turn.tap_button_contains:
        if last_reply is None:
            raise RuntimeError("tap sin reply anterior")
        interactive_id = _pick_button(last_reply, turn)
        text = None
        msg_type = "interactive"
    elif interactive_id:
        msg_type = "interactive"

    who = "bruno" if turn.wa_id == BRUNO_WA else "katia"
    inbound = text if text else f"[tap] `{interactive_id}`"
    print(f"\n  → {who}: {inbound}")
    if turn.note:
        print(f"     ({turn.note})")

    t0 = time.perf_counter()
    reply = await dispatch(
        session, turn.wa_id, msg_type, text, interactive_id, TODAY,
    )
    dt = time.perf_counter() - t0
    reply_s = _fmt_reply(reply)
    print(f"  ← bot ({dt:.1f}s):\n{_indent(reply_s, 4)}")
    snap = await _snapshot(session)
    print(f"\n  DB (últimos):\n{_indent(snap, 4)}")
    rec = TurnRecord(
        who=who, inbound=inbound, note=turn.note,
        reply_text=reply_s, elapsed_s=dt, db_snapshot=snap,
    )
    return reply, rec


def _indent(s: str, n: int) -> str:
    pad = " " * n
    return "\n".join(pad + line if line else line for line in s.splitlines())


def render_md(
    *,
    records: list[ConvoRecord],
    settings_line: str,
    started_at: datetime,
    selected: list[int],
) -> str:
    """Transcript de ESTA corrida. Se reescribe entero en cada run."""
    lines = [
        "# Escenarios de charla — última corrida",
        "",
        "> **Auto-generado** por `scripts/bot_scenario_runner.py`.",
        "> Cada corrida **borra y reemplaza** este archivo (no acumula historial).",
        "> El catálogo de escenarios vive en el script (`CONVERSATIONS`), no acá.",
        "",
        f"- Corrida: `{started_at.isoformat(timespec='seconds')}`",
        f"- {settings_line}",
        f"- Hoy ficticio: `{TODAY}` (parada activa: Lisboa)",
        f"- Escenarios corridos: {', '.join(str(i) for i in selected)} "
        f"({len(records)} conversaciones)",
        f"- Sin Meta: solo `dispatch()` + OpenAI + SQLite in-memory",
        "",
        "---",
        "",
    ]
    for rec in records:
        lines.append(f"## {rec.index} · {rec.name}")
        lines.append("")
        lines.append(f"**Meta:** {rec.goal}")
        if rec.expect_hints:
            lines.append("")
            lines.append(f"**Mirar:** {', '.join(rec.expect_hints)}")
        lines.append("")
        for t in rec.turns:
            note = f" _{t.note}_" if t.note else ""
            lines.append(f"**{t.who.capitalize()}:** {t.inbound}{note}")
            lines.append("")
            lines.append(f"**Bot** ({t.elapsed_s:.1f}s):")
            lines.append("")
            lines.append("```")
            lines.append(t.reply_text)
            lines.append("```")
            lines.append("")
            lines.append("<details><summary>DB (últimos)</summary>")
            lines.append("")
            lines.append("```")
            lines.append(t.db_snapshot)
            lines.append("```")
            lines.append("")
            lines.append("</details>")
            lines.append("")
        lines.append("---")
        lines.append("")
    lines.append("## Cómo volver a correr")
    lines.append("")
    lines.append("```bash")
    lines.append("cd backend")
    lines.append(".venv/bin/python scripts/bot_scenario_runner.py")
    lines.append(".venv/bin/python scripts/bot_scenario_runner.py --from 6 --to 10")
    lines.append(".venv/bin/python scripts/bot_scenario_runner.py --only 7,12,15")
    lines.append("```")
    lines.append("")
    lines.append("Requiere `OPENAI_API_KEY` en `spitwise/.env`. Secuencial; pausas entre turnos.")
    lines.append("")
    return "\n".join(lines)


def write_md(content: str) -> None:
    OUT_MD.write_text(content, encoding="utf-8")
    print(f"\n📝 Escrito {OUT_MD.relative_to(ROOT)}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Correr escenarios del bot WPP (sin Meta).")
    p.add_argument("--from", dest="from_n", type=int, default=1,
                   help="primer escenario (1-based)")
    p.add_argument("--to", dest="to_n", type=int, default=None,
                   help="último escenario (1-based, inclusive)")
    p.add_argument("--only", type=str, default=None,
                   help="lista de índices, ej. 7,12,15")
    p.add_argument("--pause-turn", type=float, default=PAUSE_BETWEEN_TURNS_S)
    p.add_argument("--pause-convo", type=float, default=PAUSE_BETWEEN_CONVOS_S)
    return p.parse_args(argv)


def select_indices(args: argparse.Namespace, n: int) -> list[int]:
    if args.only:
        idxs = [int(x.strip()) for x in args.only.split(",") if x.strip()]
    else:
        end = args.to_n if args.to_n is not None else n
        idxs = list(range(args.from_n, end + 1))
    for i in idxs:
        if i < 1 or i > n:
            raise SystemExit(f"índice fuera de rango: {i} (hay {n} escenarios)")
    return idxs


async def main(argv: list[str] | None = None) -> int:
    global PAUSE_BETWEEN_TURNS_S, PAUSE_BETWEEN_CONVOS_S
    args = parse_args(argv)
    PAUSE_BETWEEN_TURNS_S = args.pause_turn
    PAUSE_BETWEEN_CONVOS_S = args.pause_convo

    s = get_settings()
    if not s.openai_api_key:
        print("ERROR: falta OPENAI_API_KEY en spitwise/.env")
        return 1

    selected = select_indices(args, len(CONVERSATIONS))
    settings_line = (
        f"provider=`{s.llm_provider or 'auto'}` parser=`{s.openai_model}` "
        f"chat=`{s.openai_chat_model}`"
    )
    started = datetime.now().astimezone()
    print(settings_line)
    print(f"today={TODAY}  pause_turn={PAUSE_BETWEEN_TURNS_S}s  "
          f"pause_convo={PAUSE_BETWEEN_CONVOS_S}s")
    print(f"Escenarios: {selected} (secuencial, LLM real, sin Meta)")
    print(f"Output: {OUT_MD}  ← se limpia y reescribe al final")

    # Limpiar el md al empezar para que una corrida a medias no deje transcript viejo.
    write_md(
        "# Escenarios de charla — corrida en curso\n\n"
        f"> Empezó `{started.isoformat(timespec='seconds')}`. "
        "Se reemplaza al terminar.\n"
    )

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    records: list[ConvoRecord] = []
    try:
        async with maker() as session:
            await seed(session)
            print("\nSeed OK. Movimientos previos:")
            print(_indent(await _snapshot(session), 2))

            for pos, idx in enumerate(selected):
                conv = CONVERSATIONS[idx - 1]
                print("\n" + "=" * 72)
                print(f"CONVERSACIÓN {idx}/{len(CONVERSATIONS)}: {conv.name}")
                print(f"Meta: {conv.goal}")
                if conv.expect_hints:
                    print(f"Mirar: {', '.join(conv.expect_hints)}")
                print("=" * 72)

                crec = ConvoRecord(
                    index=idx, name=conv.name, goal=conv.goal,
                    expect_hints=list(conv.expect_hints),
                )
                last: BotReply | None = None
                for i, turn in enumerate(conv.turns):
                    last, trec = await run_turn(session, turn, last_reply=last)
                    crec.turns.append(trec)
                    if i < len(conv.turns) - 1:
                        print(f"\n  … pausa {PAUSE_BETWEEN_TURNS_S:.0f}s …")
                        await asyncio.sleep(PAUSE_BETWEEN_TURNS_S)
                records.append(crec)

                if pos < len(selected) - 1:
                    print(f"\n…… pausa entre conversaciones "
                          f"{PAUSE_BETWEEN_CONVOS_S:.0f}s ……")
                    await asyncio.sleep(PAUSE_BETWEEN_CONVOS_S)
    finally:
        await engine.dispose()
        write_md(render_md(
            records=records, settings_line=settings_line,
            started_at=started, selected=selected,
        ))

    print("\n" + "=" * 72)
    print(f"Listo. Transcript en {OUT_MD.relative_to(ROOT)}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
