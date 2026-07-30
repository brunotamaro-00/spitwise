"""Runner de escenarios de charla contra el bot (sin Meta).

Llama a `dispatch()` con LLM real (OpenAI desde spitwise/.env), DB SQLite
efímera, seed de usuarios/paradas/FX/movimientos previos. Por turno mide las
mismas fases que `webhook.process_message` (stops → due → dispatch); Graph
API no se llama.

Cada corrida **borra y reescribe** `scripts/bot_scenarios.md` con el transcript
de esa corrida (no acumula historial).

No es solo un transcript: cada escenario declara CHECKS deterministas (estado
de la DB, intent ruteado, tools llamadas) que no dependen del wording del LLM.
Si alguno falla, el runner termina con **exit code 1**. Cada conversación corre
con DB e historial PROPIOS: antes compartían sesión y un escenario contaminaba
el contexto reciente del siguiente.

Uso (desde backend/):

    # Default: suite crítica (10) — óptima para una sesión Claude/Fable
    .venv/bin/python scripts/bot_scenario_runner.py

    # Crítica + 7 extras de valor (17)
    .venv/bin/python scripts/bot_scenario_runner.py --all

    # Subconjunto del catálogo unificado (por índice o por id estable)
    .venv/bin/python scripts/bot_scenario_runner.py --only 1,4,6
    .venv/bin/python scripts/bot_scenario_runner.py --only cuotas-total,pititas-owner
    .venv/bin/python scripts/bot_scenario_runner.py --from 11 --to 14

    # Proveedor: por default el de .env (LLM_PROVIDER); forzable
    .venv/bin/python scripts/bot_scenario_runner.py --provider anthropic

Secuencial: un turno a la vez, pausa entre turnos y entre conversaciones
para no quemar la API. Requiere la API key del proveedor elegido en
spitwise/.env.
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


def _provider_from_argv() -> str:
    """--provider se lee antes que argparse: `get_settings()` congela el
    proveedor y las claves apenas se importa la app."""
    for i, a in enumerate(sys.argv):
        if a == "--provider" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if a.startswith("--provider="):
            return a.split("=", 1)[1]
    return ""


# Default: lo que diga .env (= producción). Antes se forzaba openai siempre, así
# que la suite nunca ejercitaba el proveedor real del deploy.
PROVIDER = (_provider_from_argv() or os.getenv("LLM_PROVIDER") or "openai").lower()
os.environ["LLM_PROVIDER"] = PROVIDER
os.environ.setdefault("ENVIRONMENT", "dev")
os.environ.setdefault("SECRET_KEY", "scenario-runner-local-only")
os.environ["AUTH_USERS"] = "bruno:demo:549111,katia:demo:549222"
# Deep-links del agente de guías; el seed deja el cache fresco así que nunca
# se fetchea de verdad contra esta URL.
os.environ.setdefault("ANDIAMO_URL", "https://andiamo.local")

from app import trace  # noqa: E402
from app.andiamo import ensure_stops_fresh  # noqa: E402
from app.api.auth import hash_password  # noqa: E402
from app.bot.dispatcher import dispatch  # noqa: E402
from app.bot.render import BotReply  # noqa: E402
from app.categories.seed import seed_categories  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db.models import (  # noqa: E402
    Base, Category, FxRate, GuideDoc, Movement, Stop, StopGuide, TripNote, User,
)
from app.due import ensure_due_settled  # noqa: E402
from scripts.scenario_lib import (  # noqa: E402
    Check, CheckCtx, Errors, TurnTrace, by_desc, load_movements, one_by_desc,
)

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
    # Id estable: sobrevive a reordenar el catálogo (los índices no).
    id: str = ""
    # Checklist accionable para corregir (se renderiza como **Mirar:**).
    expect_hints: list[str] = field(default_factory=list)
    # Archivos / capas sospechosas cuando falla (para la sesión de fix).
    fix_in: str = ""
    # Asserts deterministas (DB / routing / tools). Sin wording del LLM.
    check: Check | None = None


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
    trace: TurnTrace = field(default_factory=TurnTrace)


@dataclass
class ConvoRecord:
    index: int
    name: str
    goal: str
    expect_hints: list[str]
    id: str = ""
    fix_in: str = ""
    turns: list[TurnRecord] = field(default_factory=list)
    # Errores de los checks deterministas (vacío = pasó).
    errors: list[str] = field(default_factory=list)
    checked: bool = False


# --- Checks deterministas -----------------------------------------------------
# Reglas de estos asserts: solo miran DB, intent ruteado y tools llamadas. Nada
# de wording (eso se evalúa a ojo en el .md). Un check que falla => exit 1.


async def _chk_installments_total(ctx: CheckCtx) -> list[str]:
    e = Errors()
    movs = await load_movements(ctx.session)
    hostel = by_desc(movs, "interlaken")
    if not e.want(len(hostel) == 2, f"esperaba 2 cuotas de Interlaken, hay {len(hostel)}"):
        return e
    e.want(len({m.batch_key for m in hostel}) == 1 and hostel[0].batch_key,
           "las dos cuotas deben compartir batch_key")
    total = sum(Decimal(m.amount) for m in hostel)
    e.want(total == Decimal("480"), f"el total del batch debe ser 480 CHF, es {total}")
    e.want(all(m.currency == "CHF" for m in hostel), "las cuotas deben quedar en CHF")
    futura = [m for m in hostel if m.payment_date == date(2026, 9, 3)]
    e.want(len(futura) == 1 and futura[0].status == "pending",
           "la cuota del 3-sep debe existir y quedar pending")
    e.want(ctx.intents()[:2] == ["expense", "edit"],
           f"intents esperados expense→edit, fueron {ctx.intents()}")
    return e


async def _chk_batch_split_fix(ctx: CheckCtx) -> list[str]:
    e = Errors()
    movs = await load_movements(ctx.session)
    nuevos = [m for m in movs if m.batch_key]
    e.want(len(nuevos) == 3 and len({m.batch_key for m in nuevos}) == 1,
           f"esperaba 3 gastos de un mismo batch, hay {len(nuevos)}")
    taxi = one_by_desc(movs, "taxi")
    if e.want(taxi is not None, "no encontré un único Taxi"):
        e.want(taxi.split == "shared",
               f"el taxi debía quedar compartido tras el edit, quedó {taxi.split}")
    cena = [m for m in nuevos if "cena" in (m.description or "").casefold()]
    if e.want(len(cena) == 1, "esperaba una Cena en el batch"):
        e.want(cena[0].split == "shared",
               "'pagó katia' no hace individual el gasto: la cena debe quedar shared")
    e.want(all(m.city_name == "Roma" for m in nuevos), "los 3 ítems van a Roma")
    return e


async def _chk_daytrip(ctx: CheckCtx) -> list[str]:
    e = Errors()
    movs = await load_movements(ctx.session)
    paseo = one_by_desc(movs, "sintra") or one_by_desc(movs, "paseo")
    if not e.want(paseo is not None, "no encontré el paseo a Sintra"):
        return e
    e.want(paseo.stop_slug == "lisboa" and paseo.city_name == "Lisboa",
           f"un day-trip se imputa a la parada base (Lisboa), quedó {paseo.city_name}")
    e.want(paseo.split == "payer_only", f"pagó Katia y es de ella: payer_only, no {paseo.split}")
    e.want(ctx.channels()[-1] == "qa", "la pregunta de deuda va al canal financiero")
    return e


async def _chk_pending_confirm(ctx: CheckCtx) -> list[str]:
    e = Errors()
    movs = await load_movements(ctx.session)
    louvre = one_by_desc(movs, "louvre")
    if not e.want(louvre is not None, "no encontré el gasto del Louvre"):
        return e
    e.want(louvre.city_name == "Paris", f"city debía seguir en Paris, quedó {louvre.city_name}")
    e.want(louvre.payment_date == TODAY and louvre.status == "confirmed",
           f"tras 'se paga hoy' debía quedar confirmed hoy: {louvre.status}/{louvre.payment_date}")
    e.want(ctx.channels()[1] == "qa", "la pregunta de saldo va al canal financiero")
    return e


async def _chk_correccion_corta(ctx: CheckCtx) -> list[str]:
    e = Errors()
    movs = await load_movements(ctx.session)
    trenes = by_desc(movs, "tren")
    e.want(len(trenes) == 1, f"la corrección no debe crear un 2.º tren (hay {len(trenes)})")
    e.want(ctx.intents()[1] == "edit",
           f"'no, contalo solo para katia' es edit, fue {ctx.intents()[1]}")
    if trenes:
        e.want(trenes[0].split == "payer_only",
               f"gasto de Katia pagado por Katia: payer_only, no {trenes[0].split}")
    return e


async def _chk_delete_texto(ctx: CheckCtx) -> list[str]:
    e = Errors()
    movs = await load_movements(ctx.session)
    e.want(not by_desc(movs, "museo"), "el museo debía quedar borrado tras confirmar")
    e.want(ctx.intents()[1] == "delete", f"'borrá el museo' es delete, fue {ctx.intents()[1]}")
    return e


async def _chk_settlement_cruzado(ctx: CheckCtx) -> list[str]:
    e = Errors()
    movs = await load_movements(ctx.session)
    setts = [m for m in movs if m.type == "settlement"]
    if not e.want(len(setts) == 1, f"esperaba 1 settlement, hay {len(setts)}"):
        return e
    s = setts[0]
    e.want(Decimal(s.amount) == Decimal("80") and s.currency == "USD",
           f"el settlement es de 80 USD, es {s.amount} {s.currency}")
    e.want(s.city_name is None, "un settlement nunca lleva ciudad")
    e.want(not by_desc(movs, "hotel de paris"), "no debe crearse un gasto de hotel")
    e.want(ctx.channels()[-1] == "qa", "'quién debe plata' va al canal financiero")
    return e


async def _chk_batch_borrar(ctx: CheckCtx) -> list[str]:
    e = Errors()
    movs = await load_movements(ctx.session)
    for desc in ("metro", "croissant", "agua"):
        e.want(not by_desc(movs, desc), f"'{desc}' debía borrarse con el batch entero")
    return e


async def _chk_pititas_owner(ctx: CheckCtx) -> list[str]:
    e = Errors()
    movs = await load_movements(ctx.session)
    supers = by_desc(movs, "super")
    if not e.want(len(supers) == 1, f"esperaba 1 super, hay {len(supers)}"):
        return e
    e.want(supers[0].stop_slug == "pititas", "el gasto va a la parada Pititas")
    e.want(supers[0].split == "shared", f"tras 'era compartido' debe ser shared, es {supers[0].split}")
    return e


async def _chk_moneda_explicita(ctx: CheckCtx) -> list[str]:
    e = Errors()
    movs = await load_movements(ctx.session)
    cenas = [m for m in movs if Decimal(m.amount) == Decimal("40")]
    if not e.want(len(cenas) == 1, f"esperaba 1 cena de 40 (hay {len(cenas)}); no duplicar"):
        return e
    e.want(cenas[0].currency == "EUR", f"tras el edit la moneda es EUR, es {cenas[0].currency}")
    e.want(cenas[0].city_name == "Lisboa", "la ciudad sigue siendo Lisboa")
    return e


async def _chk_cat_pick(ctx: CheckCtx) -> list[str]:
    e = Errors()
    movs = await load_movements(ctx.session)
    nuevos = [m for m in movs if Decimal(m.amount) == Decimal("35")]
    if not e.want(len(nuevos) == 1, f"esperaba 1 gasto de 35 tras el tap, hay {len(nuevos)}"):
        return e
    e.want(nuevos[0].category_id is not None, "el tap de categoría debe dejar category_id")
    return e


async def _chk_qa_followup(ctx: CheckCtx) -> list[str]:
    e = Errors()
    movs = await load_movements(ctx.session)
    e.want(len(movs) == SEED_MOVEMENTS, "una consulta no crea movimientos")
    e.want(all(c == "qa" for c in ctx.channels()),
           f"los 3 turnos son financieros, fueron {ctx.channels()}")
    e.want("aggregate_expenses" in ctx.tools_used(),
           "un total con filtros exige aggregate_expenses, no el snapshot")
    return e


async def _chk_general_sin_ciudad(ctx: CheckCtx) -> list[str]:
    e = Errors()
    movs = await load_movements(ctx.session)
    seguro = one_by_desc(movs, "seguro")
    if not e.want(seguro is not None, "no encontré el seguro de viaje"):
        return e
    e.want(seguro.city_name is None and seguro.stop_slug is None,
           f"fuera del itinerario => General, quedó {seguro.city_name}")
    e.want(seguro.split == "payer_only", "'solo mío' desde Bruno es payer_only")
    e.want(seguro.currency == "USD", "moneda explícita USD")
    return e


async def _chk_settlement_me_paso(ctx: CheckCtx) -> list[str]:
    e = Errors()
    movs = await load_movements(ctx.session)
    setts = [m for m in movs if m.type == "settlement"]
    if not e.want(len(setts) == 1, f"esperaba 1 settlement, hay {len(setts)}"):
        return e
    users = {u.id: u.username for u in (await ctx.session.execute(select(User))).scalars()}
    e.want(users.get(setts[0].paid_by) == "bruno",
           "'bruno me pasó 50' => paid_by=bruno (no invertir la dirección)")
    return e


async def _chk_multi_hostel(ctx: CheckCtx) -> list[str]:
    e = Errors()
    movs = await load_movements(ctx.session)
    nuevos = [m for m in movs if m.batch_key]
    e.want(len(nuevos) == 5, f"esperaba 5 movimientos (2+2+1), hay {len(nuevos)}")
    e.want(len({m.batch_key for m in nuevos}) == 1, "todos comparten un batch_key")
    gbp = [m for m in nuevos if m.currency == "GBP"]
    e.want(len(gbp) == 2, f"las etapas del resto van en GBP, hay {len(gbp)}")
    e.want(all(m.status == "pending" for m in gbp), "las etapas futuras nacen pending")
    return e


async def _chk_guias(ctx: CheckCtx) -> list[str]:
    e = Errors()
    movs = await load_movements(ctx.session)
    e.want(len(movs) == SEED_MOVEMENTS, "una pregunta de guías no crea movimientos")
    e.want(all(c == "trip" for c in ctx.channels()),
           f"los dos turnos son del canal viaje, fueron {ctx.channels()}")
    e.want(not (ctx.tools_used() & FINANCE_TOOLS),
           f"el canal viaje no puede tocar tools financieras: {ctx.tools_used()}")
    return e


async def _chk_mixta(ctx: CheckCtx) -> list[str]:
    e = Errors()
    e.want(ctx.channels() == ["trip", "qa"],
           f"guía → plata debe cambiar de canal, fue {ctx.channels()}")
    if len(ctx.traces) == 2:
        e.want(not (set(ctx.traces[0].tools) & FINANCE_TOOLS),
               "el turno de notas no puede llamar tools financieras")
        e.want(not (set(ctx.traces[1].tools) & TRIP_TOOLS),
               "el turno de plata no puede llamar tools de guías")
    return e



async def _chk_qa_multitool(ctx: CheckCtx) -> list[str]:
    """Consulta pesada: varias tools en el turno y respuesta igual (con síntesis
    si hizo falta). Lo que no puede pasar es perder la evidencia y degradar."""
    from app.bot import copy

    e = Errors()
    movs = await load_movements(ctx.session)
    e.want(len(movs) == SEED_MOVEMENTS, "una consulta no crea movimientos")
    e.want(all(c == "qa" for c in ctx.channels()), f"canal financiero, fue {ctx.channels()}")
    tools = [t for tr in ctx.traces for t in tr.tools]
    e.want(len(tools) >= 2, f"esperaba varias tool calls, hubo {tools}")
    for tr, reply in zip(ctx.traces, ctx.replies):
        e.want(tr.outcome not in ("provider_error", "tool_error"),
               f"outcome degradado sin evidencia: {tr.outcome}")
        degraded = {copy.chat_degraded("qa", o)
                    for o in ("provider_error", "tool_error", "budget_exceeded")}
        e.want(reply.strip() not in degraded,
               "la evidencia ya juntada tiene que llegar al usuario, no la copy de degradación")
    return e

FINANCE_TOOLS = {"aggregate_expenses", "list_movements", "get_balance", "get_itinerary",
                 "edit_movement", "delete_movements"}
TRIP_TOOLS = {"search_guides", "list_guides", "read_guide_doc", "list_notes"}
SEED_MOVEMENTS = 4  # movimientos que deja `seed()` antes de cada conversación


# --- Suite crítica (default): 10 flujos de más valor para una sesión Claude ---
SUITE_CRITICAL: list[Conversation] = [
    Conversation(
        name="Cuotas + corrección de total",
        id="cuotas-total",
        check=_chk_installments_total,
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
        id="batch-split-fix",
        check=_chk_batch_split_fix,
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
        id="daytrip-payer",
        check=_chk_daytrip,
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
        id="pending-a-hoy",
        check=_chk_pending_confirm,
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
        id="correccion-corta",
        check=_chk_correccion_corta,
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
        id="delete-por-texto",
        check=_chk_delete_texto,
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
        id="settlement-cruzado",
        check=_chk_settlement_cruzado,
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
        id="batch-borrar",
        check=_chk_batch_borrar,
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
        id="pititas-owner",
        check=_chk_pititas_owner,
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
        id="moneda-explicita",
        check=_chk_moneda_explicita,
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
        id="cat-pick",
        check=_chk_cat_pick,
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
        id="qa-followup",
        check=_chk_qa_followup,
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
        id="general-sin-ciudad",
        check=_chk_general_sin_ciudad,
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
        id="settlement-me-paso",
        check=_chk_settlement_me_paso,
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
        id="multi-hostel",
        check=_chk_multi_hostel,
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

CONVERSATIONS_EXTRA += [
    Conversation(
        name="Guías: qué hacer + cómo llegar",
        id="guias-que-hacer",
        check=_chk_guias,
        goal="trip_question grounded: lee las guías cacheadas y linkea a Andiamo.",
        turns=[
            Turn(BRUNO_WA, "¿qué podemos hacer mañana acá?", note="trip_question deíctico"),
            Turn(BRUNO_WA, "¿y cómo llegamos a Sintra?", note="follow-up transporte"),
        ],
        expect_hints=[
            "Turno 1: intent trip_question (no question ni unknown); parada de hoy = Lisboa; "
            "responde con contenido del doc 'actividades' seeded (Belém / Alfama), corto, "
            "con link a /guias/lisboa/actividades. FAIL si inventa contenido no seeded",
            "Turno 2: sigue en el canal de viaje; cita el tren desde Rossio (€2,30) del doc "
            "transporte. FAIL si responde de cultura general sin tools",
        ],
        fix_in="llm/client.py (intent trip_question) · bot/trip_qa.py · qa/trip_tools.py",
    ),
    Conversation(
        name="Mixta: guía → nota → plata (cambio de canal)",
        id="mixta-guia-plata",
        check=_chk_mixta,
        goal="Aislamiento de canales: viaje y finanzas alternan sin pisarse.",
        turns=[
            Turn(KATIA_WA, "¿qué anotamos del hostel de lisboa?", note="list_notes"),
            Turn(KATIA_WA, "¿cuánto llevamos gastado acá en lisboa?", note="vuelve a finanzas"),
        ],
        expect_hints=[
            "Turno 1: trip_question → list_notes; responde el check-in 15hs / código 4421 de la "
            "nota seeded. FAIL si dice que no hay notas o va al agente financiero",
            "Turno 2: intent question (plata) → agente financiero: total Lisboa desde tools "
            "(seed: Cena Lisboa USD 66). FAIL si el agente de guías intenta responder montos",
        ],
        fix_in="llm/client.py (borde plata/contenido) · bot/dispatcher.py (ruteo por canal)",
    ),
    Conversation(
        name="Q&A multi-tool pesado",
        id="qa-multitool",
        check=_chk_qa_multitool,
        goal="Consulta que obliga a varias tools: comparación entre ciudades + promedio por día.",
        turns=[
            Turn(BRUNO_WA,
                 "comparame cuánto gastamos en Roma, Paris y Lisboa, y decime el "
                 "promedio por día del viaje",
                 note="multi-tool: aggregate x ciudad + itinerario"),
            Turn(BRUNO_WA, "y de eso, ¿cuánto puse yo de bolsillo?",
                 note="follow-up attribution=paid"),
        ],
        expect_hints=[
            "Turno 1: varias tool calls en el turno (aggregate por ciudad / group_by=city + "
            "get_itinerary). Debe responder con los tres totales, no pedir que acote",
            "Si se corta por presupuesto, la síntesis final tiene que entregar lo que ya juntó "
            "(respuesta parcial grounded). FAIL: copy de degradación con tools exitosas",
            "Turno 2: attribution=paid para Bruno; sigue en el canal financiero",
        ],
        fix_in="llm/chat.py (presupuestos + síntesis) · qa/tools.py (aggregate) · bot/qa.py",
    ),
]

# Catálogo unificado: índices 1..10 = crítica, 11..18 = extra.
CONVERSATIONS: list[Conversation] = SUITE_CRITICAL + CONVERSATIONS_EXTRA
assert len(SUITE_CRITICAL) == N_CRITICAL
assert len(CONVERSATIONS_EXTRA) == 8
assert len(CONVERSATIONS) == N_CRITICAL + len(CONVERSATIONS_EXTRA)
# Ids únicos: `--only <id>` tiene que ser inequívoco.
assert len({c.id for c in CONVERSATIONS}) == len(CONVERSATIONS)


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
             is_local=True, owner_username="katia", country_flag="👭"),
        Stop(slug="fort-william", order=6, name="Fort William", arrival_date=date(2026, 9, 12),
             departure_date=date(2026, 9, 15), currency_code="GBP", timezone="Europe/London"),
        Stop(slug="portree", order=7, name="Portree", arrival_date=date(2026, 9, 15),
             departure_date=date(2026, 9, 18), currency_code="GBP", timezone="Europe/London"),
    ])

    # Cache de guías/notas para los escenarios de trip_question. synced_at
    # queda "ahora" → ensure_content_fresh nunca fetchea durante la corrida.
    session.add_all([
        GuideDoc(guide_slug="lisboa", doc_slug="actividades", guide_title="Lisboa",
                 title="Actividades", country="Portugal", kind="city",
                 file="portugal/lisboa/actividades.md",
                 content_md=("# Actividades en Lisboa\n\n"
                             "- **Torre de Belém** €8, ir antes de las 10\n"
                             "- **Alfama**: perderse por las callecitas + mirador Santa Luzia\n"
                             "- Pastéis de Belém: la cola avanza rápido\n")),
        GuideDoc(guide_slug="lisboa", doc_slug="transporte", guide_title="Lisboa",
                 title="Transporte", country="Portugal", kind="city",
                 file="portugal/lisboa/transporte.md",
                 content_md=("# Transporte\n\n"
                             "Tren a **Sintra** desde Rossio cada 20 min, €2,30 con "
                             "tarjeta Viva Viagem. Tranvía 28 temprano para evitar la cola.\n")),
        StopGuide(stop_slug="lisboa", guide_slug="lisboa", position=0),
        TripNote(id="note-hostel-lisboa", stop_slug="lisboa", title="Hostel Lisboa",
                 body="Check-in 15hs, código puerta 4421", pinned=True),
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
    # Traza del turno (contextvar): intent ruteado, canal y tools llamadas.
    # Es lo que miran los checks deterministas, en vez del texto del bot.
    trace.start()
    try:
        reply = await dispatch(
            session, turn.wa_id, msg_type, text, interactive_id, TODAY,
        )
        tr = TurnTrace.capture()
    finally:
        trace.clear()
    dispatch_s = time.perf_counter() - t2
    total_s = stops_s + due_s + dispatch_s

    reply_s = _fmt_reply(reply)
    lat = _fmt_latency(stops_s, due_s, dispatch_s, total_s)
    print(f"  ⏱  {lat}")
    print(f"  🔍 {tr.summary()}")
    print(f"  ← bot:\n{_indent(reply_s, 4)}")
    snap = await _snapshot(session)
    print(f"\n  DB (últimos):\n{_indent(snap, 4)}")
    rec = TurnRecord(
        who=who, inbound=inbound, note=turn.note, reply_text=reply_s,
        stops_s=stops_s, due_s=due_s, dispatch_s=dispatch_s, total_s=total_s,
        db_snapshot=snap, trace=tr,
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
        "> Catálogo: `SUITE_CRITICAL` (1–10) + `CONVERSATIONS_EXTRA` (11–17) en el script.",
        "> Los **checks** son deterministas (DB / intent / tools): si fallan, el runner "
        "sale con exit 1. El texto se evalúa a ojo.",
        "",
        f"- Corrida: `{started_at.isoformat(timespec='seconds')}`",
        f"- Suite: **{suite_label}**",
        f"- {settings_line}",
        f"- Hoy ficticio: `{TODAY}` (parada activa: Lisboa)",
        f"- Escenarios corridos: {', '.join(str(i) for i in selected)} "
        f"({len(records)} conversaciones)",
        f"- Checks: **{sum(1 for r in records if r.checked and not r.errors)} ok** · "
        f"**{sum(1 for r in records if r.errors)} con fallas** · "
        f"{sum(1 for r in records if not r.checked)} sin checks",
        "- Latencia: fases espejo de `process_message` "
        "(stops → due → dispatch); Meta send/typing **no** medidos",
        "",
        "---",
        "",
    ]
    for rec in records:
        badge = "❌" if rec.errors else ("✅" if rec.checked else "·")
        lines.append(f"## {rec.index} · {rec.name} {badge}")
        lines.append("")
        lines.append(f"**Id:** `{rec.id}` — reproducir con "
                     f"`--only {rec.id or rec.index}`")
        lines.append("")
        lines.append(f"**Meta:** {rec.goal}")
        if rec.checked:
            lines.append("")
            if rec.errors:
                lines.append("**Checks deterministas: ❌ FALLAN**")
                for err in rec.errors:
                    lines.append(f"- {err}")
            else:
                lines.append("**Checks deterministas: ✅ pasan**")
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
            lines.append(f"**Traza:** {t.trace.summary()}")
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
    lines.append(".venv/bin/python scripts/bot_scenario_runner.py --all    # 17 (10+7)")
    lines.append(".venv/bin/python scripts/bot_scenario_runner.py --only cuotas-total,pititas-owner")
    lines.append(".venv/bin/python scripts/bot_scenario_runner.py --provider anthropic")
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
        help="correr el catálogo completo (crítica + extras)",
    )
    p.add_argument("--from", dest="from_n", type=int, default=None,
                   help="primer escenario (1-based) del catálogo unificado")
    p.add_argument("--to", dest="to_n", type=int, default=None,
                   help="último escenario (1-based, inclusive)")
    p.add_argument("--only", type=str, default=None,
                   help="lista de índices o ids estables, ej. 1,4,6 o cuotas-total,pititas-owner")
    p.add_argument("--provider", type=str, default=None,
                   choices=["openai", "anthropic"],
                   help="proveedor del LLM (default: LLM_PROVIDER del .env)")
    p.add_argument("--pause-turn", type=float, default=PAUSE_BETWEEN_TURNS_S)
    p.add_argument("--pause-convo", type=float, default=PAUSE_BETWEEN_CONVOS_S)
    return p.parse_args(argv)


def select_indices(args: argparse.Namespace, n: int) -> tuple[list[int], str]:
    """Devuelve (índices 1-based, etiqueta de suite para el .md).

    `--only` acepta índices o ids estables: reordenar el catálogo no invalida
    un comando guardado en un PR."""
    if args.only:
        by_id = {c.id: i for i, c in enumerate(CONVERSATIONS, start=1)}
        idxs = []
        for raw in (x.strip() for x in args.only.split(",")):
            if not raw:
                continue
            if raw in by_id:
                idxs.append(by_id[raw])
            elif raw.isdigit():
                idxs.append(int(raw))
            else:
                raise SystemExit(f"id de escenario desconocido: {raw!r}; "
                                 f"válidos: {sorted(by_id)}")
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
    if PROVIDER == "anthropic" and not s.anthropic_api_key:
        print("ERROR: falta ANTHROPIC_API_KEY en spitwise/.env (--provider anthropic)")
        return 1
    if PROVIDER == "openai" and not s.openai_api_key:
        print("ERROR: falta OPENAI_API_KEY en spitwise/.env")
        return 1

    selected, suite_label = select_indices(args, len(CONVERSATIONS))
    if PROVIDER == "anthropic":
        settings_line = (
            f"provider=`anthropic` parser=`{s.anthropic_model}` "
            f"chat=`{s.anthropic_chat_model}`"
        )
    else:
        settings_line = (
            f"provider=`openai` parser=`{s.openai_model}` "
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

    records: list[ConvoRecord] = []
    try:
        for pos, idx in enumerate(selected):
            conv = CONVERSATIONS[idx - 1]
            print("\n" + "=" * 72)
            print(f"CONVERSACIÓN {idx}/{len(CONVERSATIONS)} [{conv.id}]: {conv.name}")
            print(f"Meta: {conv.goal}")
            if conv.expect_hints:
                print("Mirar:")
                for h in conv.expect_hints:
                    print(f"  - {h}")
            if conv.fix_in:
                print(f"Fix in: {conv.fix_in}")
            print("=" * 72)

            crec = ConvoRecord(
                index=idx, id=conv.id, name=conv.name, goal=conv.goal,
                expect_hints=list(conv.expect_hints), fix_in=conv.fix_in,
            )
            # DB propia por conversación: compartir sesión dejaba que el gasto
            # (y el historial Q&A) de un escenario contaminara al siguiente.
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            maker = async_sessionmaker(engine, expire_on_commit=False)
            try:
                async with maker() as session:
                    await seed(session)
                    last: BotReply | None = None
                    for i, turn in enumerate(conv.turns):
                        last, trec = await run_turn(session, turn, last_reply=last)
                        crec.turns.append(trec)
                        if i < len(conv.turns) - 1:
                            print(f"\n  … pausa {PAUSE_BETWEEN_TURNS_S:.0f}s …")
                            await asyncio.sleep(PAUSE_BETWEEN_TURNS_S)
                    if conv.check is not None:
                        crec.checked = True
                        ctx = CheckCtx(
                            session=session,
                            traces=[t.trace for t in crec.turns],
                            replies=[t.reply_text for t in crec.turns],
                        )
                        try:
                            crec.errors = list(await conv.check(ctx))
                        except Exception as exc:  # un check roto no es un pase
                            crec.errors = [f"el check explotó: {type(exc).__name__}: {exc}"]
                        _print_checks(crec)
            finally:
                await engine.dispose()
            records.append(crec)

            if pos < len(selected) - 1:
                print(f"\n…… pausa entre conversaciones "
                      f"{PAUSE_BETWEEN_CONVOS_S:.0f}s ……")
                await asyncio.sleep(PAUSE_BETWEEN_CONVOS_S)
    finally:
        write_md(render_md(
            records=records, settings_line=settings_line,
            started_at=started, selected=selected, suite_label=suite_label,
        ))

    failed = [r for r in records if r.errors]
    print("\n" + "=" * 72)
    print(f"Listo. Transcript en {OUT_MD.relative_to(ROOT)}")
    checked = sum(1 for r in records if r.checked)
    if failed:
        print(f"❌ CHECKS: {len(failed)} de {checked} escenarios con fallas deterministas")
        for r in failed:
            print(f"   · {r.index} [{r.id}] {r.name}")
            for err in r.errors:
                print(f"       - {err}")
    else:
        print(f"✅ CHECKS: {checked}/{len(records)} escenarios verificados sin fallas")
    print("=" * 72)
    return 1 if failed else 0


def _print_checks(crec: ConvoRecord) -> None:
    if crec.errors:
        print(f"\n  ❌ CHECKS [{crec.id}]:")
        for err in crec.errors:
            print(f"     - {err}")
    else:
        print(f"\n  ✅ CHECKS [{crec.id}] ok")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
