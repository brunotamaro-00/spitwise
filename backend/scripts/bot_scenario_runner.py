"""Runner de escenarios de charla contra el bot (sin Meta).

Llama a `dispatch()` con LLM real (OpenAI desde spitwise/.env), DB SQLite
efímera, seed de usuarios/paradas/FX/movimientos previos. Por turno mide las
mismas fases que `webhook.process_message` (stops → due → dispatch); Graph
API no se llama.

Cada corrida **borra y reescribe** `scripts/bot_scenarios.md` con el transcript
de esa corrida (no acumula historial).

Uso (desde backend/):

    # Default: suite crítica (10) — óptima para una sesión Claude/Fable
    .venv/bin/python scripts/bot_scenario_runner.py

    # Crítica + 5 extras de valor (15)
    .venv/bin/python scripts/bot_scenario_runner.py --all

    # Subconjunto del catálogo unificado
    .venv/bin/python scripts/bot_scenario_runner.py --only 1,4,6
    .venv/bin/python scripts/bot_scenario_runner.py --from 11 --to 14

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

from app.andiamo import ensure_stops_fresh  # noqa: E402
from app.api.auth import hash_password  # noqa: E402
from app.bot.dispatcher import dispatch  # noqa: E402
from app.bot.render import BotReply  # noqa: E402
from app.categories.seed import seed_categories  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db.models import Base, Category, FxRate, Movement, Stop, User  # noqa: E402
from app.due import ensure_due_settled  # noqa: E402

get_settings.cache_clear()

TODAY = date(2026, 8, 20)
PAUSE_BETWEEN_TURNS_S = 4.0
PAUSE_BETWEEN_CONVOS_S = 6.0
N_CRITICAL = 10  # suite default para una sesión Claude/Fable

BRUNO_WA = "549111"
KATIA_WA = "549222"


@dataclass
class Turn:
    wa_id: str
    text: str | None = None
    interactive_id: str | None = None
    note: str = ""
    tap_first_button: bool = False
    tap_button_contains: str | None = None


@dataclass
class Conversation:
    name: str
    goal: str
    turns: list[Turn]
    # Checklist accionable para corregir (se renderiza como **Mirar:**).
    expect_hints: list[str] = field(default_factory=list)
    # Archivos / capas sospechosas cuando falla (para la sesión de fix).
    fix_in: str = ""


@dataclass
class TurnRecord:
    who: str
    inbound: str
    note: str
    reply_text: str
    stops_s: float
    due_s: float
    dispatch_s: float
    total_s: float
    db_snapshot: str


@dataclass
class ConvoRecord:
    index: int
    name: str
    goal: str
    expect_hints: list[str]
    fix_in: str = ""
    turns: list[TurnRecord] = field(default_factory=list)


# --- Suite crítica (default): 10 flujos de más valor para una sesión Claude ---
SUITE_CRITICAL: list[Conversation] = [
    Conversation(
        name="Cuotas + corrección de total",
        goal="Gasto en etapas (30% hoy / resto check-in) y corregir el total del batch.",
        turns=[
            Turn(BRUNO_WA,
                 "hostel interlaken 430 chf, 30% hoy y el resto al check-in el 3 de septiembre",
                 note="cuotas"),
            Turn(BRUNO_WA, "no, el total era 480 no 430", note="edit monto del batch"),
        ],
        expect_hints=[
            "Turno 1: 2 filas mismo batch_key; montos 129+301 (=430); 2ª con pay=2026-09-03 y status=pending",
            "Turno 2 FAIL típico: solo edita la cuota 2/2 a 480 (total 609). Debe redistribuir el batch a total 480 (≈144+336) o editar el gasto lógico, no un renglón suelto",
            "Card no debe mostrar deuda por la cuota pending",
        ],
        fix_in="llm/client.py (installments) · bot/editor.py (edit amount + batch) · bot/capture.py (expand_installments)",
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
        expect_hints=[
            "Turno 1: 3 movimientos Roma, pay=ayer; cena paid_by=katia con split=shared ('pagó' ≠ 'solo de'); taxi payer_only Bruno; helado shared",
            "FAIL típico: cena nace payer_only / Solo Katia sin que lo digan",
            "Turno 2: debe editar el Taxi (ref_text), no el último (helado). DB: taxi.split → shared. FAIL: 'Nada que cambiar'",
        ],
        fix_in="llm/client.py (split vs paid_by; expenses[]) · bot/editor.py (resolve ref_text en batch)",
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
        expect_hints=[
            "Turno 1: city_name=Lisboa (no 'Sintra' libre); shared; pagó Bruno",
            "Turno 2: paid_by=katia + split=payer_only (Solo Katia). FAIL: other_only / Solo Bruno",
            "Turno 3: responder con el paseo recién editado (USD 30,8 a favor de Katia), no pedir ciudad si hay uno solo reciente",
        ],
        fix_in="bot/capture.py (resolve_place) · llm/client.py (new_split relativo al NUEVO paid_by) · bot/qa.py + qa/tools.py",
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
        expect_hints=[
            "Turno 1: city=Paris; status=pending; pay=2026-09-15; split=shared (NO inventar Solo Katia)",
            "Turno 2: respuesta debe decir que NO entra al balance todavía (pending excluido de compute_balance). FAIL: 'sí, ya está incluido'",
            "Turno 3: pay→hoy, status→confirmed; city debe seguir Paris. FAIL: arrastra ciudad a Lisboa",
        ],
        fix_in="llm/client.py (no inventar split) · bot/qa.py / qa/tools get_balance · bot/editor.py (edit date sin re-resolve city)",
    ),
    Conversation(
        name="Corrección corta post-carga",
        goal="last_expense → edit por mensaje sin monto propio.",
        turns=[
            Turn(KATIA_WA, "tren 39 usd en pititas", note="carga"),
            Turn(KATIA_WA, "no, contalo solo para katia", note="edit split corto"),
        ],
        expect_hints=[
            "Turno 1: city=Pititas; owner default puede ya ser Solo Katia — anotar estado real en DB",
            "Turno 2: intent=edit (ref_last), NO expense nuevo; un solo movement_id. Si ya era payer_only, 'Nada que cambiar' es OK; si era shared → payer_only",
            "No debe aparecer un 2.º tren",
        ],
        fix_in="llm/client.py (regla Último gasto) · bot/editor.py · stops_local / capture.owner_split",
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
        expect_hints=[
            "Turno 1: Museo en Roma; paid_by=katia; split=payer_only (Solo Katia). FAIL: Solo Bruno / other_only",
            "Turno 2: botones de confirm; el resumen debe ser el museo, NO otro gasto (FAIL visto: ofreció 'Cena Lisboa')",
            "Turno 3: tras tap, el museo desaparece de la DB; no hard-delete en el turno 2",
        ],
        fix_in="bot/editor.py (resolve ref_text delete) · bot/interactive.py · llm/client.py (solo de ella → payer_only si paga ella)",
    ),
    Conversation(
        name="Settlement cruzado + ¿quién debe?",
        goal="Bruno salda con 'le pasé…'; Katia pregunta el neto.",
        turns=[
            Turn(BRUNO_WA, "le pasé 80 usd a katia por lo del hotel de paris",
                 note="settlement"),
            Turn(KATIA_WA, "che y ahora quién debe plata?", note="Q&A balance"),
        ],
        expect_hints=[
            "Turno 1: type=settlement; Bruno→Katia; amount=80 USD; no crear expense de hotel",
            "Turno 2: desde wa_id de Katia, get_balance coherente post-settlement; no invertir deudor",
        ],
        fix_in="bot/capture.py (settlement) · balance.py · bot/qa.py",
    ),
    Conversation(
        name="Batch + borrar (fast path) + confirmar los N",
        goal="Multi-gasto + comando borrar sin LLM + del_confirm del batch.",
        turns=[
            Turn(BRUNO_WA, "en paris: metro 4 eur, croissant 3, agua 2", note="batch 3"),
            Turn(BRUNO_WA, "borrar", note="fast path"),
            Turn(BRUNO_WA, tap_button_contains="Borrar los", note="confirmar batch"),
        ],
        expect_hints=[
            "Turno 1: 3 gastos mismo batch_key, city=Paris",
            "Turno 2: fast path (dispatch ~0s LLM); botones 'Borrar los 3' + 'Solo el último' + Cancelar",
            "Turno 3: desaparecen los 3 del batch, no solo el último",
        ],
        fix_in="bot/dispatcher.py (_handle_delete_command) · bot/interactive.py",
    ),
    Conversation(
        name="Stop local / owner split (Pititas)",
        goal="Default split por owner_username; después forzar shared.",
        turns=[
            Turn(BRUNO_WA, "super 22 eur en pititas", note="owner default"),
            Turn(BRUNO_WA, "en realidad era compartido", note="edit → shared"),
        ],
        expect_hints=[
            "Turno 1: city=Pititas; Bruno puede cargar ahí; split default Solo Katia (owner). Relativo a paid_by=bruno → other_only en DB / label Solo Katia",
            "Turno 2: edit → shared; un solo movimiento",
        ],
        fix_in="bot/capture.py (owner_split) · stops_local.py · bot/editor.py",
    ),
    Conversation(
        name="Moneda explícita ≠ moneda ciudad + edit",
        goal="USD dicho en Lisboa (EUR); después corregir a euros.",
        turns=[
            Turn(BRUNO_WA, "cena 40 usd en lisboa", note="USD explícito"),
            Turn(BRUNO_WA, "era en euros, no dólares", note="edit currency"),
        ],
        expect_hints=[
            "Turno 1: currency=USD (no forzar EUR de Lisboa); amount=40; city=Lisboa",
            "Turno 2: edit currency→EUR + recalc amount_usd; no crear 2.ª cena",
        ],
        fix_in="llm/client.py (currency explícita) · bot/editor.py (new_currency + FX)",
    ),
]

# --- Extra (4 de valor; con --all / --only) ---
CONVERSATIONS_EXTRA: list[Conversation] = [
    Conversation(
        name="Categoría ambigua + cat_pick",
        goal="Descripción vaga → botones de categoría; confirmar con tap.",
        turns=[
            Turn(BRUNO_WA, "me cobraron 35 eur en lisboa por aquello", note="categoría ambigua"),
            Turn(BRUNO_WA, tap_first_button=True, note="tap 1.er candidato"),
        ],
        expect_hints=[
            "Turno 1: confidence baja → botones cat_pick (2–3). FAIL si guarda directo (p.ej. Compras) sin preguntar",
            "Turno 2: tras tap, gasto confirmado con esa category_id. Si el runner omite el tap, el turno 1 falló el umbral",
        ],
        fix_in="bot/capture.py (candidates / pending) · bot/interactive.py (cat_pick)",
    ),
    Conversation(
        name="Q&A follow-up elíptico",
        goal="Historial fresco: reusar intención cambiando ciudad/attribution.",
        turns=[
            Turn(BRUNO_WA, "¿cuánto gastamos en comida en paris?", note="Q&A"),
            Turn(BRUNO_WA, "¿y en roma?", note="follow-up ciudad"),
            Turn(BRUNO_WA, "¿y cuánto puse yo de bolsillo ahí?", note="attribution paid"),
        ],
        expect_hints=[
            "Turno 1: total comida Paris desde tools (seed: Cena Paris USD 88 half-share context)",
            "Turno 2: reusa categoría Comida + ciudad Roma; no preguntar '¿comida o total?'",
            "Turno 3: attribution=paid para Bruno en Roma (no share)",
        ],
        fix_in="bot/qa.py (historial) · qa/tools.py (attribution)",
    ),
    Conversation(
        name="General / pre-viaje sin ciudad",
        goal="Fecha fuera de itinerario → city null; Q&A lo admite.",
        turns=[
            Turn(BRUNO_WA, "seguro de viaje 320 usd el 1 de julio, solo mío",
                 note="fuera de rango"),
            Turn(BRUNO_WA, "¿en qué ciudad quedó el seguro?", note="Q&A"),
        ],
        expect_hints=[
            "Turno 1: city_name=null / sin stop; split=payer_only; currency=USD; pay≈2026-07-01",
            "Turno 2: admitir General / sin ciudad; NO inventar Roma/Londres",
        ],
        fix_in="bot/capture.py (resolve_place fuera de rango) · bot/qa.py",
    ),
    Conversation(
        name="Settlement 'me pasó' desde Katia",
        goal="Dirección del pago desde el otro lado + saldo.",
        turns=[
            Turn(KATIA_WA, "bruno me pasó 50 usd", note="settlement"),
            Turn(BRUNO_WA, "saldo", note="fast path"),
        ],
        expect_hints=[
            "Turno 1: settlement Bruno→Katia (paid_by=bruno); no expense; no invertir",
            "Turno 2: saldo fast path (~0s dispatch LLM) refleja el neto post-pago",
        ],
        fix_in="llm/client.py (settlement dirección) · bot/capture.py · bot/quick.py",
    ),
    Conversation(
        name="Multi-hostel con seña USD + resto en moneda local",
        goal="Mensaje real: varios hostels, cada uno con seña en USD hoy y resto en GBP a la fecha de ingreso, más uno simple con fecha.",
        turns=[
            Turn(BRUNO_WA,
                 "34 usd Hostel Fort William hoy. El resto (134 GBP) a pagar al ingresar "
                 "(12 de septiembre)\n\n"
                 "94 USD Hostel Portree hoy. El resto (70 GBP) a pagar al ingresar "
                 "(15 de septiembre)\n\n"
                 "Hostel ClinkMama 403 euros el 25 de agosto en Lisboa",
                 note="multi-hostel etapas mixtas"),
        ],
        expect_hints=[
            "5 movimientos, un solo batch_key: FW 34 USD confirmed hoy + FW 134 GBP pending 12/09; "
            "Portree 94 USD confirmed + 70 GBP pending 15/09; ClinkMama 403 EUR pending 25/08",
            "FAIL histórico: se pierden las etapas GBP (solo quedan las señas USD) o cada etapa nace como gasto suelto sin (i/n)",
            "Ciudades: Fort William / Portree / Lisboa (paradas reales); montos GBP con TC proxy de hoy",
        ],
        fix_in="llm/client.py (installments por ítem + currency) · bot/capture.py (expand_installments modo directo)",
    ),
]

# Catálogo unificado: índices 1..10 = crítica, 11..15 = extra.
CONVERSATIONS: list[Conversation] = SUITE_CRITICAL + CONVERSATIONS_EXTRA
assert len(SUITE_CRITICAL) == N_CRITICAL
assert len(CONVERSATIONS_EXTRA) == 5
assert len(CONVERSATIONS) == N_CRITICAL + len(CONVERSATIONS_EXTRA)


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
        Stop(slug="pititas", order=5, name="Pititas", arrival_date=date(2026, 9, 4),
             departure_date=date(2026, 9, 12), currency_code="EUR", timezone="Europe/Paris",
             is_local=True, owner_username="katia", country_flag="😊"),
        Stop(slug="fort-william", order=6, name="Fort William", arrival_date=date(2026, 9, 12),
             departure_date=date(2026, 9, 15), currency_code="GBP", timezone="Europe/London"),
        Stop(slug="portree", order=7, name="Portree", arrival_date=date(2026, 9, 15),
             departure_date=date(2026, 9, 18), currency_code="GBP", timezone="Europe/London"),
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


def _fmt_latency(stops_s: float, due_s: float, dispatch_s: float, total_s: float) -> str:
    return (
        f"dispatch {dispatch_s:.1f}s · stops {stops_s:.1f}s · due {due_s:.1f}s · "
        f"**total {total_s:.1f}s** (sin Meta send)"
    )


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


def _pick_button(reply: BotReply, turn: Turn) -> str | None:
    """Devuelve interactive_id o None si no hay botón usable (queda documentado)."""
    if not reply.buttons:
        return None
    if turn.tap_button_contains:
        needle = turn.tap_button_contains.casefold()
        for bid, label in reply.buttons:
            if needle in label.casefold():
                return bid
        return None
    return reply.buttons[0][0]


async def run_turn(
    session: AsyncSession,
    turn: Turn,
    *,
    last_reply: BotReply | None,
) -> tuple[BotReply, TurnRecord]:
    """Espejo de webhook.process_message: stops → due → dispatch (sin Meta)."""
    interactive_id = turn.interactive_id
    text = turn.text
    msg_type = "text"
    skipped_tap = False

    if turn.tap_first_button or turn.tap_button_contains:
        if last_reply is None:
            raise RuntimeError("tap sin reply anterior")
        interactive_id = _pick_button(last_reply, turn)
        if interactive_id is None:
            # El bot no ofreció el botón esperado: documentar y no crashear la suite.
            skipped_tap = True
            want = turn.tap_button_contains or "primer botón"
            labels = (
                ", ".join(l for _, l in last_reply.buttons)
                if last_reply.buttons else "(sin botones)"
            )
            fake = BotReply(
                text=(
                    f"⚠️ RUNNER: tap omitido — se esperaba «{want}» pero el reply "
                    f"anterior no lo tenía. Botones: {labels}"
                )
            )
            who = "bruno" if turn.wa_id == BRUNO_WA else "katia"
            print(f"\n  → {who}: [tap omitido] {want}")
            print(f"  ⚠  {fake.text}")
            snap = await _snapshot(session)
            rec = TurnRecord(
                who=who,
                inbound=f"[tap omitido] {want}",
                note=turn.note or "tap fallido",
                reply_text=_fmt_reply(fake),
                stops_s=0.0, due_s=0.0, dispatch_s=0.0, total_s=0.0,
                db_snapshot=snap,
            )
            return last_reply, rec
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
    await ensure_stops_fresh(session)
    stops_s = time.perf_counter() - t0

    t1 = time.perf_counter()
    await ensure_due_settled(session, TODAY)
    due_s = time.perf_counter() - t1

    t2 = time.perf_counter()
    reply = await dispatch(
        session, turn.wa_id, msg_type, text, interactive_id, TODAY,
    )
    dispatch_s = time.perf_counter() - t2
    total_s = stops_s + due_s + dispatch_s

    reply_s = _fmt_reply(reply)
    lat = _fmt_latency(stops_s, due_s, dispatch_s, total_s)
    print(f"  ⏱  {lat}")
    print(f"  ← bot:\n{_indent(reply_s, 4)}")
    snap = await _snapshot(session)
    print(f"\n  DB (últimos):\n{_indent(snap, 4)}")
    rec = TurnRecord(
        who=who, inbound=inbound, note=turn.note, reply_text=reply_s,
        stops_s=stops_s, due_s=due_s, dispatch_s=dispatch_s, total_s=total_s,
        db_snapshot=snap,
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
    suite_label: str,
) -> str:
    """Transcript de ESTA corrida. Se reescribe entero en cada run."""
    lines = [
        "# Escenarios de charla — última corrida",
        "",
        "> **Auto-generado** por `scripts/bot_scenario_runner.py`.",
        "> Cada corrida **borra y reemplaza** este archivo (no acumula historial).",
        "> Catálogo: `SUITE_CRITICAL` (1–10) + `CONVERSATIONS_EXTRA` (11–15) en el script.",
        "",
        f"- Corrida: `{started_at.isoformat(timespec='seconds')}`",
        f"- Suite: **{suite_label}**",
        f"- {settings_line}",
        f"- Hoy ficticio: `{TODAY}` (parada activa: Lisboa)",
        f"- Escenarios corridos: {', '.join(str(i) for i in selected)} "
        f"({len(records)} conversaciones)",
        "- Latencia: fases espejo de `process_message` "
        "(stops → due → dispatch); Meta send/typing **no** medidos",
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
            lines.append("**Mirar (qué corregir si falla):**")
            for hint in rec.expect_hints:
                lines.append(f"- {hint}")
        if rec.fix_in:
            lines.append("")
            lines.append(f"**Dónde tocar:** `{rec.fix_in}`")
        lines.append("")
        for turn_i, t in enumerate(rec.turns, 1):
            note = f" _{t.note}_" if t.note else ""
            lines.append(f"**{t.who.capitalize()}:** {t.inbound}{note}")
            lines.append("")
            lines.append(
                f"**Latencia:** {_fmt_latency(t.stops_s, t.due_s, t.dispatch_s, t.total_s)}"
            )
            lines.append("")
            lines.append("**Bot:**")
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

    # Resumen de latencia
    lines.append("## Resumen de latencia")
    lines.append("")
    lines.append(
        "| Escenario | Turno | Quién | Nota | dispatch_s | stops_s | due_s | total_s |"
    )
    lines.append("|---|---:|---|---|---:|---:|---:|---:|")
    for rec in records:
        for turn_i, t in enumerate(rec.turns, 1):
            note = t.note.replace("|", "/") if t.note else "—"
            lines.append(
                f"| {rec.index} · {rec.name} | {turn_i} | {t.who} | {note} | "
                f"{t.dispatch_s:.1f} | {t.stops_s:.1f} | {t.due_s:.1f} | "
                f"{t.total_s:.1f} |"
            )
    lines.append("")
    if records:
        all_turns = [t for r in records for t in r.turns]
        avg_d = sum(t.dispatch_s for t in all_turns) / len(all_turns)
        avg_t = sum(t.total_s for t in all_turns) / len(all_turns)
        max_t = max(all_turns, key=lambda t: t.total_s)
        lines.append(
            f"Promedio dispatch **{avg_d:.1f}s** · promedio total **{avg_t:.1f}s** · "
            f"más lento: {max_t.who} «{max_t.inbound[:40]}…» ({max_t.total_s:.1f}s)"
            if len(max_t.inbound) > 40
            else (
                f"Promedio dispatch **{avg_d:.1f}s** · promedio total **{avg_t:.1f}s** · "
                f"más lento: {max_t.who} «{max_t.inbound}» ({max_t.total_s:.1f}s)"
            )
        )
        lines.append("")
    lines.append(
        "> En prod, al `total_s` se suman typing/react/send Graph "
        "(~0.3–1.5s típico, no medido acá)."
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Cómo volver a correr")
    lines.append("")
    lines.append("```bash")
    lines.append("cd backend")
    lines.append(".venv/bin/python scripts/bot_scenario_runner.py          # suite crítica (10)")
    lines.append(".venv/bin/python scripts/bot_scenario_runner.py --all    # 14 (10+4)")
    lines.append(".venv/bin/python scripts/bot_scenario_runner.py --only 1,4,6")
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
    p.add_argument(
        "--all", action="store_true",
        help="correr crítica + 5 extras (15)",
    )
    p.add_argument("--from", dest="from_n", type=int, default=None,
                   help="primer escenario (1-based) del catálogo unificado")
    p.add_argument("--to", dest="to_n", type=int, default=None,
                   help="último escenario (1-based, inclusive)")
    p.add_argument("--only", type=str, default=None,
                   help="lista de índices, ej. 1,4,6 o 7,12,15")
    p.add_argument("--pause-turn", type=float, default=PAUSE_BETWEEN_TURNS_S)
    p.add_argument("--pause-convo", type=float, default=PAUSE_BETWEEN_CONVOS_S)
    return p.parse_args(argv)


def select_indices(args: argparse.Namespace, n: int) -> tuple[list[int], str]:
    """Devuelve (índices 1-based, etiqueta de suite para el .md)."""
    if args.only:
        idxs = [int(x.strip()) for x in args.only.split(",") if x.strip()]
        label = f"custom ({len(idxs)})"
    elif args.from_n is not None or args.to_n is not None:
        start = args.from_n if args.from_n is not None else 1
        end = args.to_n if args.to_n is not None else n
        idxs = list(range(start, end + 1))
        label = f"rango {start}–{end}"
    elif args.all:
        idxs = list(range(1, n + 1))
        label = f"catálogo completo ({n})"
    else:
        idxs = list(range(1, N_CRITICAL + 1))
        label = f"suite crítica ({N_CRITICAL})"
    for i in idxs:
        if i < 1 or i > n:
            raise SystemExit(f"índice fuera de rango: {i} (hay {n} escenarios)")
    return idxs, label


async def main(argv: list[str] | None = None) -> int:
    global PAUSE_BETWEEN_TURNS_S, PAUSE_BETWEEN_CONVOS_S
    args = parse_args(argv)
    PAUSE_BETWEEN_TURNS_S = args.pause_turn
    PAUSE_BETWEEN_CONVOS_S = args.pause_convo

    s = get_settings()
    if not s.openai_api_key:
        print("ERROR: falta OPENAI_API_KEY en spitwise/.env")
        return 1

    selected, suite_label = select_indices(args, len(CONVERSATIONS))
    settings_line = (
        f"provider=`{s.llm_provider or 'auto'}` parser=`{s.openai_model}` "
        f"chat=`{s.openai_chat_model}`"
    )
    started = datetime.now().astimezone()
    print(settings_line)
    print(f"suite={suite_label}  today={TODAY}")
    print(f"pause_turn={PAUSE_BETWEEN_TURNS_S}s  pause_convo={PAUSE_BETWEEN_CONVOS_S}s")
    print(f"Escenarios: {selected} (secuencial, LLM real, sin Meta)")
    print(f"Output: {OUT_MD}  ← se limpia y reescribe al final")

    write_md(
        "# Escenarios de charla — corrida en curso\n\n"
        f"> Empezó `{started.isoformat(timespec='seconds')}`. "
        f"Suite: {suite_label}. Se reemplaza al terminar.\n"
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
                    print("Mirar:")
                    for h in conv.expect_hints:
                        print(f"  - {h}")
                if conv.fix_in:
                    print(f"Fix in: {conv.fix_in}")
                print("=" * 72)

                crec = ConvoRecord(
                    index=idx, name=conv.name, goal=conv.goal,
                    expect_hints=list(conv.expect_hints),
                    fix_in=conv.fix_in,
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
            started_at=started, selected=selected, suite_label=suite_label,
        ))

    print("\n" + "=" * 72)
    print(f"Listo. Transcript en {OUT_MD.relative_to(ROOT)}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
