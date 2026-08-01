"""Runner de escenarios del canal de VIAJE (guías + notas) — sin Meta.

Segundo script junto a `bot_scenario_runner.py` (finanzas). Acá el foco es
`trip_question`: grounding en guías reales de `andiamo/content` + notas dummy
alineadas al Itinerary.

- DB SQLite in-memory, LLM real (OpenAI desde spitwise/.env).
- Hoy ficticio fijo: **2026-09-25** (en Viena, mid-trip del itinerario real).
- Carga markdown real desde `../andiamo/content/guides` (no inventa docs).
- Cada corrida **borra y reescribe** `scripts/bot_trip_scenarios.md`.

Uso (desde backend/):

    .venv/bin/python scripts/bot_trip_scenario_runner.py
    .venv/bin/python scripts/bot_trip_scenario_runner.py --only 1,3
    .venv/bin/python scripts/bot_trip_scenario_runner.py --pause-turn 2
"""
from __future__ import annotations

import argparse
import asyncio
import json
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
OUT_MD = SCRIPTS / "bot_trip_scenarios.md"
ANDIAMO_CONTENT = ROOT.parent / "andiamo" / "content" / "guides"
MANIFEST_PATH = ANDIAMO_CONTENT / "manifest.json"

load_dotenv(ROOT / ".env", override=False)

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"


def _provider_from_argv() -> str:
    """--provider se lee antes que argparse: `get_settings()` congela el
    proveedor apenas se importa la app."""
    for i, a in enumerate(sys.argv):
        if a == "--provider" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if a.startswith("--provider="):
            return a.split("=", 1)[1]
    return ""


# Default: lo que diga .env (= producción), no openai a la fuerza.
PROVIDER = (_provider_from_argv() or os.getenv("LLM_PROVIDER") or "openai").lower()
os.environ["LLM_PROVIDER"] = PROVIDER
os.environ.setdefault("ENVIRONMENT", "dev")
os.environ.setdefault("SECRET_KEY", "trip-scenario-runner-local-only")
os.environ["AUTH_USERS"] = "bruno:demo:549111,katia:demo:549222"
# Deep-links del agente: forzar local aunque .env apunte a Railway.
os.environ["ANDIAMO_URL"] = "http://localhost:3000"

from app.andiamo import ensure_stops_fresh  # noqa: E402
from app.api.auth import hash_password  # noqa: E402
from app.bot.dispatcher import dispatch  # noqa: E402
from app.bot.render import BotReply  # noqa: E402
from app.categories.seed import seed_categories  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db.models import (  # noqa: E402
    Base, BotPendingAction, Category, FxRate, GuideDoc, Movement, Stop, StopGuide,
    TripDocument, TripNote, User,
)
from app.due import ensure_due_settled  # noqa: E402
from app import trace  # noqa: E402
from scripts.scenario_lib import Check, CheckCtx, Errors, TurnTrace  # noqa: E402

get_settings.cache_clear()

# Mid-trip real: Viena 23–28 sep 2026 → hoy = día 3 en Viena.
TODAY = date(2026, 9, 25)
PAUSE_BETWEEN_TURNS_S = 4.0
PAUSE_BETWEEN_CONVOS_S = 6.0

BRUNO_WA = "549111"
KATIA_WA = "549222"

# Mismo mapa que andiamo/src/lib/guides.ts STOP_TO_GUIDES (subset del viaje).
STOP_TO_GUIDES: dict[str, list[str]] = {
    "viena": ["viena"],
    "praga": ["praga"],
    "cracovia": ["cracovia"],
    "budapest": ["budapest"],
    "interlaken": ["interlaken"],
    "lisboa": ["lisboa"],
    "porto": ["porto"],
    "friburgo": ["friburgo"],
    "roma": ["roma"],
}

# Guías country-level (pseudo) que queremos en el cache además de las de ciudad.
EXTRA_GUIDE_SLUGS = {"polonia", "chequia", "hungria", "austria", "suiza"}


@dataclass
class Turn:
    wa_id: str
    text: str
    note: str = ""


@dataclass
class Conversation:
    name: str
    goal: str
    turns: list[Turn]
    # Id estable: `--only guias-viena` sobrevive a reordenar el catálogo.
    id: str = ""
    expect_hints: list[str] = field(default_factory=list)
    fix_in: str = ""
    # Asserts deterministas (canal, tools, hits). Sin wording del LLM.
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
    trace: TurnTrace = field(default_factory=TurnTrace)


@dataclass
class ConvoRecord:
    index: int
    name: str
    goal: str
    expect_hints: list[str]
    fix_in: str
    turns: list[TurnRecord]
    id: str = ""
    errors: list[str] = field(default_factory=list)
    checked: bool = False


# --- Checks deterministas -----------------------------------------------------
# Solo canal ruteado y tools llamadas: el contenido de la respuesta se lee a ojo
# en el markdown. Un check que falla => exit 1.

FINANCE_TOOLS = {"aggregate_expenses", "list_movements", "get_balance", "get_itinerary",
                 "edit_movement", "delete_movements"}
GUIDE_TOOLS = {"search_guides", "list_guides", "read_guide_doc"}
TRIP_TOOLS = GUIDE_TOOLS | {"list_notes", "search_documents"}


def _trip_only(channels: list[str | None], e: Errors) -> None:
    e.want(all(c == "trip" for c in channels),
           f"todos los turnos son del canal viaje, fueron {channels}")


def _no_finance(ctx: CheckCtx, e: Errors) -> None:
    used = ctx.tools_used() & FINANCE_TOOLS
    e.want(not used, f"el canal viaje no puede tocar tools financieras: {sorted(used)}")


def trip_check(*, channels: list[str] | None = None, needs: set[str] | None = None,
               needs_per_turn: dict[int, set[str]] | None = None) -> Check:
    """Check declarativo: canales esperados + tools que TIENEN que haberse usado.

    `needs` es una intersección: alcanza con que se haya llamado alguna de esas
    tools (el modelo puede llegar por search o por read)."""
    async def _check(ctx: CheckCtx) -> list[str]:
        e = Errors()
        if channels is not None:
            e.want(ctx.channels() == channels,
                   f"canales esperados {channels}, fueron {ctx.channels()}")
        else:
            _trip_only(ctx.channels(), e)
            _no_finance(ctx, e)
        if needs:
            e.want(bool(ctx.tools_used() & needs),
                   f"esperaba alguna de {sorted(needs)}, se usaron {sorted(ctx.tools_used())}")
        for i, want in (needs_per_turn or {}).items():
            if e.want(i < len(ctx.traces), f"falta el turno {i + 1} para chequear tools"):
                got = set(ctx.traces[i].tools)
                e.want(bool(got & want),
                       f"turno {i + 1}: esperaba alguna de {sorted(want)}, usó {sorted(got)}")
        return e
    return _check


async def _chk_cambio_canal(ctx: CheckCtx) -> list[str]:
    """El corte entre canales: notas primero, plata después, sin mezclar tools."""
    e = Errors()
    e.want(ctx.channels() == ["trip", "qa"],
           f"guía → plata debe cambiar de canal, fue {ctx.channels()}")
    if len(ctx.traces) == 2:
        e.want(not (set(ctx.traces[0].tools) & FINANCE_TOOLS),
               "el turno de notas no puede llamar tools financieras")
        e.want(not (set(ctx.traces[1].tools) & TRIP_TOOLS),
               "el turno de plata no puede llamar tools de guías")
    return e


async def _chk_grounding_negativo(ctx: CheckCtx) -> list[str]:
    """Negar exige haber buscado: 'las guías no dicen nada' sin tools es inventar."""
    e = Errors()
    _trip_only(ctx.channels(), e)
    _no_finance(ctx, e)
    if e.want(bool(ctx.traces), "sin turnos que chequear"):
        e.want(bool(set(ctx.traces[0].tools) & TRIP_TOOLS),
               "una negativa grounded exige search/list en ESE turno")
    return e


async def _chk_bar_mleczny(ctx: CheckCtx) -> list[str]:
    e = Errors()
    e.want(ctx.channels() == ["trip", "trip", "qa"],
           f"esperaba viaje→viaje→finanzas, fue {ctx.channels()}")
    if len(ctx.traces) == 3:
        e.want(not (set(ctx.traces[2].tools) & TRIP_TOOLS),
               "la pregunta de saldo no puede usar tools de guías")
    return e


async def _chk_documento_encontrado(ctx: CheckCtx) -> list[str]:
    """Buscar un archivo guardado es search_documents, no search_guides: son
    fuentes distintas y confundirlas hacía que el bot leyera la guía del hostel
    en vez de devolver el voucher."""
    e = Errors()
    _trip_only(ctx.channels(), e)
    _no_finance(ctx, e)
    e.want("search_documents" in ctx.tools_used(),
           f"esperaba search_documents, se usaron {sorted(ctx.tools_used())}")
    return e


async def _chk_documento_inexistente(ctx: CheckCtx) -> list[str]:
    """Negar que existe un documento exige haberlo buscado."""
    e = Errors()
    _trip_only(ctx.channels(), e)
    if e.want(bool(ctx.traces), "sin turnos que chequear"):
        e.want("search_documents" in set(ctx.traces[0].tools),
               "negar que hay un documento exige search_documents en ESE turno")
    return e


def note_check(*, marker: str, stop_slug: str | None = ...) -> Check:
    """Nota dictada: intent trip_note, su pending abierto, CERO movimientos.

    Los escenarios comparten una sola DB (solo se resetean los historiales), así
    que todo se filtra por `marker` — una palabra propia de ESTA nota. Un check
    con conteos absolutos contaba lo sembrado y lo de las conversaciones previas.

    Lo caro es el movimiento: una nota que menciona plata no puede terminar en
    el ledger. `stop_slug=...` (default) no chequea la parada.
    """
    async def _check(ctx: CheckCtx) -> list[str]:
        import json
        from sqlalchemy import select
        from scripts.scenario_lib import load_movements
        e = Errors()
        wanted = marker.casefold()

        e.want(ctx.intents() == ["trip_note"] * len(ctx.traces),
               f"esperaba trip_note en todos los turnos, fueron {ctx.intents()}")
        e.want(not (ctx.tools_used() & FINANCE_TOOLS),
               "dictar una nota no llama tools financieras")

        movs = [m for m in await load_movements(ctx.session)
                if wanted in (m.description or "").casefold()]
        e.want(not movs,
               f"una nota no puede crear movimientos, se creó {[m.description for m in movs]}")

        # Sobre el JSON parseado, no sobre el string: json.dumps escapa los
        # acentos ('depósito' → 'dep\\u00f3sito') y el match crudo no encontraba nada.
        rows = [r for r in (await ctx.session.execute(
            select(BotPendingAction).where(BotPendingAction.action_type == "note_create")
        )).scalars().all()
            if wanted in json.dumps(json.loads(r.payload_json), ensure_ascii=False).casefold()]
        if e.want(len(rows) == 1, f"esperaba 1 pending note_create con {marker!r}, hay {len(rows)}"):
            e.want(rows[0].cancelled_at is None, "el pending de la nota quedó cancelado")
            if stop_slug is not ...:
                got = json.loads(rows[0].payload_json).get("stop_slug")
                e.want(got == stop_slug, f"parada de la nota: esperaba {stop_slug}, fue {got}")
        return e
    return _check


CONVERSATIONS: list[Conversation] = [
    Conversation(
        name="Viena deíctica + follow-up day-trip",
        id="viena-deictico",
        check=trip_check(needs=GUIDE_TOOLS),
        goal="Resolver 'acá/mañana' con parada de hoy=Viena; segunda vuelta pide desvío sin repetir el doc entero.",
        turns=[
            Turn(BRUNO_WA, "che, ¿qué hacemos mañana acá que valga la pena?",
                 note="deíctico → viena/actividades"),
            Turn(BRUNO_WA, "¿y qué dice el doc de desvíos cercanos de Viena? algún day trip decente?",
                 note="follow-up → viena/desvios-cercanos"),
        ],
        expect_hints=[
            "Turno 1: intent trip_question; cita cosas reales de Viena (Schönbrunn, Belvedere, "
            "Naschmarkt, café vienés…). Link a /guias/viena/…. FAIL si inventa o habla de Lisboa.",
            "Turno 2: sigue en canal viaje; usa desvíos/day-trips de Viena o dice si el doc no "
            "cubre mucho. FAIL si cambia a finanzas o inventa Bratislava sin estar en la guía.",
        ],
        fix_in="bot/trip_qa.py · qa/trip_tools.py · llm/client.py (trip_question)",
    ),
    Conversation(
        name="Polonia: domingo + dziękuję (guía país + notas)",
        id="polonia-domingo",
        check=trip_check(needs=TRIP_TOOLS),
        goal="Pregunta de costumbres que exige search/read de polonia/costumbres y/o notas globales.",
        turns=[
            Turn(KATIA_WA,
                 "cuando estemos en Cracovia, ¿qué onda con el domingo? ¿podemos ir al súper?",
                 note="zakaz handlu"),
            Turn(KATIA_WA,
                 "y lo del tip en Polonia: si digo dziękuję al pagar, ¿qué pasa con el vuelto?",
                 note="dziękuję = quedate el cambio"),
        ],
        expect_hints=[
            "Turno 1: menciona domingo sin comercio / zakaz handlu / comprar sábado / Żabka. "
            "Fuente: costumbres Polonia o nota 'Domingo en Polonia'. FAIL si dice que abre todo.",
            "Turno 2: explica dziękuję = no querés vuelto. FAIL si confunde con propina checa "
            "o inventa otro protocolo.",
        ],
        fix_in="qa/trip_tools.py (search_guides country) · seed notas Monedas/Domingo",
    ),
    Conversation(
        name="Auschwitz: nota propia + precio de la guía",
        id="auschwitz-nota",
        check=trip_check(needs_per_turn={0: {"list_notes"}, 1: GUIDE_TOOLS}),
        goal="Mezclar list_notes (reserva dummy) con read_guide de actividades/day-trip Cracovia.",
        turns=[
            Turn(BRUNO_WA, "¿qué anotamos de Auschwitz?",
                 note="list_notes cracovia"),
            Turn(BRUNO_WA, "ok y según la guía cuánto sale el tour con educator?",
                 note="read guía → ~150 PLN"),
        ],
        expect_hints=[
            "Turno 1: cita la nota (slot / visit.auschwitz.org / respeto). FAIL si dice que no "
            "hay notas o inventa un horario distinto al seeded.",
            "Turno 2: ~150 PLN del educator (guía Cracovia). FAIL si inventa euros sin citar PLN "
            "o responde sin tool.",
        ],
        fix_in="trip_tools list_notes + read_guide_doc · notas seed Auschwitz",
    ),
    Conversation(
        name="Praga comida → propina (cross-doc + nota)",
        id="praga-propina",
        check=trip_check(needs=TRIP_TOOLS),
        goal="Follow-up elíptico: gastronomía Praga y después propina checa vs polaca.",
        turns=[
            Turn(KATIA_WA, "en Praga qué tenemos que comer sí o sí?",
                 note="praga/gastronomia"),
            Turn(KATIA_WA, "y según nuestras notas, la propina en Praga es igual que en Polonia?",
                 note="nota Propina Chequia vs dziękuję PL"),
        ],
        expect_hints=[
            "Turno 1: platos reales (svíčková, guláš, pivo/tanque…). FAIL si lista comida polaca.",
            "Turno 2: Chequia ≠ dziękuję polaco; redondeo/~10%. Puede usar nota 'Propina Chequia'. "
            "FAIL si dice que es igual que Polonia.",
        ],
        fix_in="trip_qa follow-ups · search_guides + list_notes",
    ),
    Conversation(
        name="Cambio de canal: guía → plata",
        id="cambio-canal",
        check=_chk_cambio_canal,
        goal="Aislamiento: viaje grounded y después intent question con montos de DB.",
        turns=[
            Turn(BRUNO_WA, "algo urgente que tengamos anotado para Cracovia?",
                 note="notas pinned Auschwitz/hostel"),
            Turn(BRUNO_WA, "bárbaro. ¿cuánto llevamos gastado en Viena?",
                 note="cambio a finanzas"),
        ],
        expect_hints=[
            "Turno 1: trip_question → notas Cracovia (Auschwitz / hostel). FAIL si va a aggregate.",
            "Turno 2: intent question → agente financiero; total Viena del seed (Cena/Museum). "
            "FAIL si el agente de guías inventa un monto.",
        ],
        fix_in="dispatcher latest_fresh_channel · llm/client borde plata/contenido",
    ),
    Conversation(
        name="Grounding negativo + Suiza caro",
        id="grounding-negativo",
        check=_chk_grounding_negativo,
        goal="Pregunta fuera de guías → 'no está'; después pregunta cubierta por nota Interlaken.",
        turns=[
            Turn(KATIA_WA,
                 "el IKEA de Viena abre los domingos? a qué hora?",
                 note="NO está en las guías"),
            Turn(KATIA_WA,
                 "ok olvidate. para Interlaken, ¿qué anotamos de lo caro / pases?",
                 note="nota Suiza caro / Swiss Travel"),
        ],
        expect_hints=[
            "Turno 1: admite que las guías/notas no cubren IKEA. FAIL si inventa horarios.",
            "Turno 2: cita nota Interlaken (CHF, picnic, Jungfraujoch caro) o guía Suiza. "
            "FAIL si vuelve a inventar sobre IKEA.",
        ],
        fix_in="trip_qa grounding · list_notes interlaken",
    ),
    Conversation(
        name="Frases útiles Polonia (guía país)",
        id="frases-polonia",
        check=trip_check(needs=GUIDE_TOOLS),
        goal="Pedidos de idioma: read/search polonia/frases-utiles, no inventar vocabulario.",
        turns=[
            Turn(BRUNO_WA,
                 "según nuestras frases útiles de Polonia, cómo pedimos la cuenta y cómo se dice gracias?",
                 note="frases-utiles → rachunek / dziękuję"),
            Turn(BRUNO_WA,
                 "y hay algo ahí sobre saludar al entrar a un negocio?",
                 note="follow-up frases · dzień dobry"),
        ],
        expect_hints=[
            "Turno 1: cita formas de la guía (p.ej. rachunek/proszę, dziękuję). FAIL si inventa "
            "frases que no están o responde en checo/húngaro.",
            "Turno 2: sigue en frases PL (dzień dobry u equivalente de la guía). FAIL si cambia "
            "de país o alucina.",
        ],
        fix_in="search/read polonia/frases-utiles · trip_qa follow-up",
    ),
    Conversation(
        name="Budapest: nota baños + guía termales",
        id="budapest-banos",
        check=trip_check(needs_per_turn={0: {"list_notes"}, 1: GUIDE_TOOLS}),
        goal="Nota propia de Budapest y después detalle de la guía (Széchenyi/Gellért).",
        turns=[
            Turn(KATIA_WA, "qué anotamos de los baños en Budapest?",
                 note="list_notes budapest"),
            Turn(KATIA_WA,
                 "ok y según la guía de actividades, Széchenyi o Gellért — qué conviene?",
                 note="budapest/actividades termales"),
        ],
        expect_hints=[
            "Turno 1: nota Baños (Széchenyi/Gellért online, OTP, no reventa calle). FAIL si dice "
            "que no hay notas.",
            "Turno 2: contenido real de la guía Budapest (precios/tips termales si están). "
            "FAIL si inventa un spa que no figura o responde de cultura general.",
        ],
        fix_in="list_notes budapest · read_guide_doc budapest/actividades",
    ),
    Conversation(
        name="Próxima parada → transporte Praga",
        id="proxima-praga",
        check=trip_check(needs=GUIDE_TOOLS),
        goal="Deíctico de itinerario (próxima=Praga) y después movilidad en esa ciudad.",
        turns=[
            Turn(BRUNO_WA, "después de acá, ¿a dónde vamos y cuándo llegamos?",
                 note="snapshot próximas → Praga 28/9"),
            Turn(BRUNO_WA,
                 "joya. en Praga, según la guía de transporte, ¿cómo nos movemos en la ciudad?",
                 note="praga/transporte"),
        ],
        expect_hints=[
            "Turno 1: Praga + fecha de llegada del seed (2026-09-28). FAIL si dice Budapest/Cracovia "
            "como próxima o inventa fechas.",
            "Turno 2: tips reales de praga/transporte (metro/tranvía/Lítačka o lo que diga el doc). "
            "FAIL si habla de Viena o inventa líneas.",
        ],
        fix_in="trip_qa snapshot próximas · read praga/transporte",
    ),
    Conversation(
        name="Bar mleczny + efectivo PLN (3 turnos)",
        id="bar-mleczny",
        check=_chk_bar_mleczny,
        goal="Cadena: costumbre milk bar → follow-up efectivo → pregunta plata (cambio de canal).",
        turns=[
            Turn(KATIA_WA,
                 "en Cracovia qué es un bar mleczny y cómo se pide según las costumbres?",
                 note="polonia/costumbres milk bar"),
            Turn(KATIA_WA,
                 "ahí hace falta efectivo o va tarjeta? y a qué hora conviene ir?",
                 note="follow-up cash + antes 14h"),
            Turn(KATIA_WA,
                 "ok gracias. al margen: ¿quién debe plata ahora?",
                 note="cambio a finanzas → balance"),
        ],
        expect_hints=[
            "Turno 1: milk bar / cantina / pedir en caja (costumbres PL). FAIL si lo confunde con "
            "café vienés o hospoda checa.",
            "Turno 2: cash only frecuente + ir antes de ~14h. Puede citar nota PLN/propina. "
            "FAIL si dice que todo es contactless sin matices.",
            "Turno 3: intent question → get_balance / agente financiero. FAIL si el agente de "
            "guías inventa un saldo.",
        ],
        fix_in="costumbres PL · list_notes · dispatcher canal plata",
    ),
    Conversation(
        name="Harry Potter en Lisboa o Porto (multi-ciudad + sinónimos)",
        id="harry-potter",
        check=trip_check(needs=GUIDE_TOOLS),
        goal=("Consulta que ninguna guía nombra literalmente: hay que expandirla "
              "(Hogwarts / Livraria Lello) y cubrir DOS ciudades sin quedarse a "
              "mitad de camino."),
        turns=[
            Turn(KATIA_WA,
                 "¿hay algo de Harry Potter para ver en Lisboa o en Porto?",
                 note="multi-ciudad + sinónimo (ninguna guía dice 'Harry Potter')"),
            Turn(KATIA_WA, "¿y cuánto sale entrar?", note="follow-up sobre el mismo lugar"),
        ],
        expect_hints=[
            "Turno 1: tiene que encontrar la Livraria Lello de Porto (la guía la liga a "
            "Hogwarts) y decir en una línea, grounded, qué hay o no hay en Lisboa. "
            "FAIL histórico: search_guides exige TODAS las palabras ('harry' + 'potter' + "
            "'lisboa' + 'porto') y devuelve 0 hits → 'las guías no dicen nada'",
            "FAIL grave: contestar de cultura general (tour de HP, estudios) sin tools",
            "Turno 2: precio TAL CUAL la guía (€10 Silver / €15.95 Gold). FAIL si inventa "
            "un precio o cambia de ciudad",
        ],
        fix_in="qa/trip_tools.py (search escalonado, multi guide_slugs) · bot/trip_qa.py",
    ),
    Conversation(
        name="Dónde está el voucher del hostel",
        id="voucher-buscar",
        check=_chk_documento_encontrado,
        goal=("Buscar un ARCHIVO guardado, no lo que dice una guía: tiene que ir a "
              "search_documents y devolver el link del voucher."),
        turns=[
            Turn(BRUNO_WA, "¿dónde está el voucher del hostel de Viena?",
                 note="documento, no guía"),
            Turn(BRUNO_WA, "¿y la entrada de Auschwitz la tenemos?",
                 note="follow-up sobre otro documento, otra parada"),
        ],
        expect_hints=[
            "Turno 1: usa search_documents y pasa el link http://localhost:3000/api/documents/"
            "d-viena-hostel. FAIL si lee la guía del hostel o inventa un link.",
            "Turno 2: encuentra la entrada de Auschwitz (parada Cracovia) con su link. "
            "FAIL si dice que no hay nada o mezcla con la nota de Auschwitz sin el archivo.",
        ],
        fix_in="qa/trip_tools.py (search_documents) · bot/trip_qa.py (prompt: archivo ≠ guía)",
    ),
    Conversation(
        name="Documento que no existe",
        id="doc-inexistente",
        check=_chk_documento_inexistente,
        goal="Negar un documento exige haberlo buscado, igual que negar una guía.",
        turns=[
            Turn(KATIA_WA, "¿tenemos guardado el pasaje de avión de vuelta?",
                 note="no hay ningún documento de vuelo en el seed"),
        ],
        expect_hints=[
            "Turno único: llama search_documents y dice que no está guardado. "
            "FAIL si lo afirma sin buscar, o si inventa un vuelo. Puede ofrecer el dato de "
            "qué SÍ hay guardado, pero sin inventar.",
        ],
        fix_in="qa/trip_tools.py (search_documents) · bot/trip_qa.py (grounding)",
    ),
    Conversation(
        name="Dictar una nota con parada explícita",
        id="nota-crear",
        check=note_check(marker="depósito", stop_slug="praga"),
        goal="Anotar algo por chat: preview + pending, sin tocar el ledger.",
        turns=[
            Turn(BRUNO_WA, "anotá que el hostel de Praga pide efectivo para el depósito",
                 note="trip_note con ciudad explícita"),
        ],
        expect_hints=[
            "Turno único: intent trip_note, card 📝 con el contenido y parada Praga, "
            "botones Guardar/Cancelar. FAIL si lo toma como gasto o como pregunta.",
        ],
        fix_in="llm/client.py (intent trip_note) · bot/trip_notes.py · bot/dispatcher.py",
    ),
    Conversation(
        name="Nota sin ciudad → parada de hoy",
        id="nota-general",
        check=note_check(marker="free tour", stop_slug="viena"),
        goal="Sin ciudad, la nota cae en la parada de hoy (Viena), como un gasto.",
        turns=[
            Turn(KATIA_WA, "tomá nota: el free tour sale 11am de la plaza",
                 note="sin ciudad → resolve_place con hoy"),
        ],
        expect_hints=[
            "Turno único: trip_note imputado a Viena (parada de hoy). FAIL si lo manda a "
            "General teniendo parada, o si pregunta en qué ciudad.",
        ],
        fix_in="bot/trip_notes.py (resolve_place) · llm/client.py (city en trip_note)",
    ),
    Conversation(
        name="Nota que menciona plata",
        id="nota-con-plata",
        check=note_check(marker="zloty"),
        goal=("El borde caro del prompt: un número adentro de una nota NO la "
              "convierte en gasto."),
        turns=[
            Turn(BRUNO_WA, "anotá que el hostel de Cracovia cobra 20 zloty de depósito en efectivo",
                 note="trip_note con monto y moneda — NO es expense"),
        ],
        expect_hints=[
            "Turno único: trip_note, CERO movimientos en la DB. FAIL grave: cargar un gasto "
            "de 20 PLN. FAIL menor: pedir aclaración en vez de anotar.",
        ],
        fix_in="llm/client.py (regla trip_note vs expense) · bot/dispatcher.py",
    ),
]


def _read_md(rel: str) -> str | None:
    path = ANDIAMO_CONTENT / rel
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def _iter_manifest_docs() -> list[dict]:
    """Aplana manifest.json a filas {guide_slug, guide_title, country, kind, doc…}."""
    if not MANIFEST_PATH.is_file():
        raise SystemExit(f"No encuentro manifest: {MANIFEST_PATH}")
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    rows: list[dict] = []

    for country in data.get("countries", []):
        flag = country.get("flag", "")
        cname = country.get("name", "")
        for guide in country.get("guides", []):
            for doc in guide.get("docs", []):
                rows.append({
                    "guide_slug": guide["slug"],
                    "guide_title": guide.get("title", guide["slug"]),
                    "country": guide.get("country") or cname,
                    "country_flag": guide.get("countryFlag") or flag,
                    "kind": "city",
                    "doc": doc,
                })
            for doc in guide.get("dayTrips", []):
                rows.append({
                    "guide_slug": guide["slug"],
                    "guide_title": guide.get("title", guide["slug"]),
                    "country": guide.get("country") or cname,
                    "country_flag": guide.get("countryFlag") or flag,
                    "kind": "daytrip",
                    "doc": doc,
                })
        for doc in country.get("countryDocs", []):
            rows.append({
                "guide_slug": country["slug"],
                "guide_title": cname,
                "country": cname,
                "country_flag": flag,
                "kind": "country",
                "doc": doc,
            })
    for doc in data.get("general", []):
        rows.append({
            "guide_slug": "general", "guide_title": "El viaje",
            "country": "General", "country_flag": "🌍", "kind": "general", "doc": doc,
        })
    for doc in data.get("resources", []):
        rows.append({
            "guide_slug": "recursos", "guide_title": "Recursos",
            "country": "General", "country_flag": "🎒", "kind": "resource", "doc": doc,
        })
    return rows


def load_guide_rows_for_seed() -> list[dict]:
    """Docs de guías que mapean a nuestros stops + country extras (polonia, etc.)."""
    wanted = set(EXTRA_GUIDE_SLUGS)
    for slugs in STOP_TO_GUIDES.values():
        wanted.update(slugs)

    out: list[dict] = []
    for row in _iter_manifest_docs():
        if row["guide_slug"] not in wanted:
            continue
        content = _read_md(row["doc"]["file"])
        if not content:
            continue
        out.append({
            "guide_slug": row["guide_slug"],
            "doc_slug": row["doc"]["slug"],
            "guide_title": row["guide_title"],
            "title": row["doc"].get("title", row["doc"]["slug"]),
            "country": row["country"],
            "kind": row["kind"],
            "file": row["doc"]["file"],
            "content_md": content,
        })
    return out


async def seed(session: AsyncSession) -> dict:
    """Itinerario real (fechas Andiamo) + guías del filesystem + notas dummy."""
    bruno = User(username="bruno", password_hash=hash_password("demo"), whatsapp_wa_id=BRUNO_WA)
    katia = User(username="katia", password_hash=hash_password("demo"), whatsapp_wa_id=KATIA_WA)
    session.add_all([bruno, katia])
    await seed_categories(session)
    await session.flush()

    stops = [
        Stop(slug="friburgo", order=1, name="Friburgo", country="Alemania", country_flag="🇩🇪",
             arrival_date=date(2026, 9, 16), departure_date=date(2026, 9, 19),
             currency_code="EUR", timezone="Europe/Berlin"),
        Stop(slug="interlaken", order=2, name="Interlaken", country="Suiza", country_flag="🇨🇭",
             arrival_date=date(2026, 9, 19), departure_date=date(2026, 9, 23),
             currency_code="CHF", timezone="Europe/Zurich"),
        Stop(slug="viena", order=3, name="Viena", country="Austria", country_flag="🇦🇹",
             arrival_date=date(2026, 9, 23), departure_date=date(2026, 9, 28),
             currency_code="EUR", timezone="Europe/Vienna"),
        Stop(slug="praga", order=4, name="Praga", country="Chequia", country_flag="🇨🇿",
             arrival_date=date(2026, 9, 28), departure_date=date(2026, 10, 3),
             currency_code="CZK", timezone="Europe/Prague"),
        Stop(slug="cracovia", order=5, name="Cracovia", country="Polonia", country_flag="🇵🇱",
             arrival_date=date(2026, 10, 3), departure_date=date(2026, 10, 7),
             currency_code="PLN", timezone="Europe/Warsaw"),
        Stop(slug="budapest", order=6, name="Budapest", country="Hungría", country_flag="🇭🇺",
             arrival_date=date(2026, 10, 7), departure_date=date(2026, 10, 11),
             currency_code="HUF", timezone="Europe/Budapest"),
        Stop(slug="lisboa", order=7, name="Lisboa", country="Portugal", country_flag="🇵🇹",
             arrival_date=date(2026, 9, 4), departure_date=date(2026, 9, 9),
             currency_code="EUR", timezone="Europe/Lisbon", is_archived=True),
    ]
    session.add_all(stops)

    guide_rows = load_guide_rows_for_seed()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for g in guide_rows:
        session.add(GuideDoc(
            guide_slug=g["guide_slug"], doc_slug=g["doc_slug"],
            guide_title=g["guide_title"], title=g["title"],
            country=g["country"], kind=g["kind"], file=g["file"],
            content_md=g["content_md"], synced_at=now,
        ))
    for stop_slug, guide_slugs in STOP_TO_GUIDES.items():
        for pos, gs in enumerate(guide_slugs):
            session.add(StopGuide(stop_slug=stop_slug, guide_slug=gs, position=pos))

    # Notas alineadas a andiamo/prisma/seed-dev.ts (lo que /api/notes exportaría).
    session.add_all([
        TripNote(id="n-monedas", stop_slug=None, title="Monedas no-Euro", pinned=True,
                 body=("CHF · CZK · PLN · HUF (OTP Bank, nunca Euronet). "
                       "En Polonia: dziękuję al pagar = quedate el cambio.")),
        TripNote(id="n-domingo-pl", stop_slug=None, title="Domingo en Polonia", pinned=False,
                 body=("Zakaz handlu: súper cerrados la mayoría de los domingos. "
                       "Tramo Cracovia: comprar el sábado. Abren Żabka y gastronomía.")),
        TripNote(id="n-viena-hostel", stop_slug="viena", title="Hostel Viena", pinned=True,
                 body=("Wombats City · check-in 15:00 · código 8812. "
                       "Prioridad Schönbrunn jardines + Belvedere con slot.")),
        TripNote(id="n-praga-comida", stop_slug="praga", title="Comida Praga", pinned=True,
                 body=("Salir del tourist highway. Svíčková 180-250 CZK. "
                       "Cerveza tanque 50-70 CZK.")),
        TripNote(id="n-praga-tip", stop_slug="praga", title="Propina Chequia", pinned=False,
                 body=("Redondear / ~10%. NO es como Polonia (dziękuję ≠ vuelto). "
                       "Účet, prosím.")),
        TripNote(id="n-auschwitz", stop_slug="cracovia", title="Auschwitz — crítico", pinned=True,
                 body=("Reserva visit.auschwitz.org. Slot preferido lun/mar 5-6 oct 09:00. "
                       "Educator ~150 PLN. Día completo; respeto; bus MDA ~1h30.")),
        TripNote(id="n-cracovia-hostel", stop_slug="cracovia", title="Hostel Cracovia", pinned=True,
                 body="Check-in 15hs · código 4421. Bar mleczny antes de las 14h."),
        TripNote(id="n-interlaken", stop_slug="interlaken", title="Suiza caro", pinned=True,
                 body=("CHF. Picnic/súper. Jungfraujoch carísimo — mirar "
                       "Lauterbrunnen/Grindelwald en la guía.")),
        TripNote(id="n-budapest-banos", stop_slug="budapest", title="Baños Budapest", pinned=True,
                 body=("Széchenyi/Gellért: comprar entrada ONLINE (no reventa en la calle). "
                       "Efectivo HUF en OTP Bank.")),
    ])

    # Documentos: metadata como la exportaría /api/integration/documents.
    session.add_all([
        TripDocument(id="d-viena-hostel", stop_slug="viena", label="Voucher Wombats Viena",
                     note="Check-in 15:00, código 8812", kind="voucher", source="upload",
                     doc_date=date(2026, 9, 23), file_name="wombats.pdf",
                     mime_type="application/pdf", created_at=datetime(2026, 8, 10, 12, 0)),
        TripDocument(id="d-auschwitz", stop_slug="cracovia", label="Entrada Auschwitz",
                     note="Slot 6-oct 09:00, educator", kind="ticket", source="upload",
                     doc_date=date(2026, 10, 6), file_name="auschwitz.pdf",
                     mime_type="application/pdf", created_at=datetime(2026, 8, 12, 12, 0)),
        TripDocument(id="d-tren-praga", stop_slug="praga", label="Tren Viena-Praga",
                     note="Regiojet, 09:39", kind="train", source="upload",
                     doc_date=date(2026, 9, 29), file_name="regiojet.pdf",
                     mime_type="application/pdf", created_at=datetime(2026, 8, 14, 12, 0)),
        TripDocument(id="d-seguro", stop_slug=None, label="Seguro de viaje",
                     note="Póliza 998877, cobertura Schengen", kind="insurance",
                     source="link", doc_date=None, file_name=None, mime_type=None,
                     created_at=datetime(2026, 7, 1, 12, 0)),
    ])

    for cur, rate in (("EUR", "1.10"), ("CHF", "1.15"), ("CZK", "0.043"),
                      ("PLN", "0.25"), ("HUF", "0.0028")):
        for d in (TODAY, TODAY - timedelta(days=1), date(2026, 9, 20), date(2026, 10, 1)):
            session.add(FxRate(currency=cur, rate_date=d, rate_to_usd=Decimal(rate)))

    await session.flush()
    cats = {c.name: c.id for c in (await session.execute(select(Category))).scalars()}

    # Gastos Viena para el escenario de cambio de canal.
    session.add(Movement(
        type="expense", amount=Decimal("45"), currency="EUR",
        amount_usd=Decimal("49.50"), fx_rate=Decimal("1.10"), fx_source="cache",
        description="Cena Naschmarkt", category_id=cats.get("Comida"),
        city_name="Viena", stop_slug="viena", paid_by=bruno.id, split="shared",
        created_by=bruno.id, payment_date=date(2026, 9, 24), status="confirmed",
        created_at=datetime(2026, 9, 24, 20, 0, tzinfo=timezone.utc),
    ))
    session.add(Movement(
        type="expense", amount=Decimal("39"), currency="EUR",
        amount_usd=Decimal("42.90"), fx_rate=Decimal("1.10"), fx_source="cache",
        description="Belvedere El Beso", category_id=cats.get("Actividades"),
        city_name="Viena", stop_slug="viena", paid_by=katia.id, split="shared",
        created_by=katia.id, payment_date=date(2026, 9, 25), status="confirmed",
        created_at=datetime(2026, 9, 25, 11, 0, tzinfo=timezone.utc),
    ))
    await session.commit()
    notes_count = (await session.execute(
        select(TripNote)
    )).scalars().all()
    return {"guides": len(guide_rows), "notes": len(notes_count), "stops": len(stops)}


def _fmt_reply(reply: BotReply) -> str:
    lines = []
    if reply.text:
        lines.append(reply.text)
    if reply.buttons:
        lines.append("[botones]")
        for bid, label in reply.buttons:
            lines.append(f"  · {label}  (`{bid}`)")
    return "\n".join(lines) if lines else "(reply vacío)"


def _indent(s: str, n: int) -> str:
    pad = " " * n
    return "\n".join(pad + line if line else line for line in s.splitlines())


async def run_turn(session: AsyncSession, turn: Turn) -> TurnRecord:
    who = "bruno" if turn.wa_id == BRUNO_WA else "katia"
    print(f"\n  → {who}: {turn.text}")
    if turn.note:
        print(f"     ({turn.note})")

    t0 = time.perf_counter()
    await ensure_stops_fresh(session)
    stops_s = time.perf_counter() - t0

    t1 = time.perf_counter()
    await ensure_due_settled(session, TODAY)
    due_s = time.perf_counter() - t1

    t2 = time.perf_counter()
    # Traza del turno (canal, intent, tools): base de los checks deterministas.
    trace.start()
    try:
        reply = await dispatch(session, turn.wa_id, "text", turn.text, None, TODAY)
        tr = TurnTrace.capture()
    finally:
        trace.clear()
    dispatch_s = time.perf_counter() - t2
    total_s = stops_s + due_s + dispatch_s

    reply_s = _fmt_reply(reply)
    print(f"  ⏱  dispatch {dispatch_s:.1f}s · total {total_s:.1f}s")
    print(f"  🔍 {tr.summary()}")
    print(f"  ← bot:\n{_indent(reply_s, 4)}")

    return TurnRecord(
        who=who, inbound=turn.text, note=turn.note, reply_text=reply_s,
        stops_s=stops_s, due_s=due_s, dispatch_s=dispatch_s, total_s=total_s,
        trace=tr,
    )


async def run_convo(session: AsyncSession, idx: int, conv: Conversation) -> ConvoRecord:
    # Cada conversación es standalone: sin esto, el historial Q&A fresco de un
    # escenario anterior (p.ej. Cracovia) contamina los follow-ups del siguiente.
    from app.bot.active_stop import update_state_payload
    for wa_id in (BRUNO_WA, KATIA_WA):
        await update_state_payload(session, wa_id, qa_history=[], trip_qa_history=[])

    turns: list[TurnRecord] = []
    for i, turn in enumerate(conv.turns):
        turns.append(await run_turn(session, turn))
        if i < len(conv.turns) - 1:
            await asyncio.sleep(PAUSE_BETWEEN_TURNS_S)
    rec = ConvoRecord(
        index=idx, id=conv.id, name=conv.name, goal=conv.goal,
        expect_hints=conv.expect_hints, fix_in=conv.fix_in, turns=turns,
    )
    if conv.check is not None:
        rec.checked = True
        ctx = CheckCtx(session=session, traces=[t.trace for t in turns],
                       replies=[t.reply_text for t in turns])
        try:
            rec.errors = list(await conv.check(ctx))
        except Exception as exc:  # un check roto no es un pase
            rec.errors = [f"el check explotó: {type(exc).__name__}: {exc}"]
        if rec.errors:
            print(f"\n  ❌ CHECKS [{rec.id}]:")
            for err in rec.errors:
                print(f"     - {err}")
        else:
            print(f"\n  ✅ CHECKS [{rec.id}] ok")
    return rec


def render_md(records: list[ConvoRecord], *, seed_info: dict, suite_label: str) -> str:
    lines = [
        "# Escenarios bot — canal VIAJE (guías + notas)",
        "",
        f"Corrida: **{datetime.now().strftime('%Y-%m-%d %H:%M')}** · hoy ficticio "
        f"`{TODAY.isoformat()}` (Viena) · suite: {suite_label}",
        "",
        f"Seed: **{seed_info['guides']}** guide docs desde "
        f"`andiamo/content/guides` · **{seed_info['notes']}** notas · "
        f"**{seed_info['stops']}** stops.",
        "",
        "> Cada corrida reescribe este archivo. Checklist **Mirar** = qué validar a ojo.",
        "",
    ]
    for rec in records:
        badge = "❌" if rec.errors else ("✅" if rec.checked else "·")
        lines.append(f"## {rec.index}. {rec.name} {badge}")
        lines.append("")
        lines.append(f"**Id:** `{rec.id}` — reproducir con `--only {rec.id or rec.index}`")
        lines.append("")
        lines.append(f"**Goal:** {rec.goal}")
        lines.append("")
        if rec.checked:
            if rec.errors:
                lines.append("**Checks deterministas: ❌ FALLAN**")
                for err in rec.errors:
                    lines.append(f"- {err}")
            else:
                lines.append("**Checks deterministas: ✅ pasan**")
            lines.append("")
        if rec.expect_hints:
            lines.append("**Mirar:**")
            for h in rec.expect_hints:
                lines.append(f"- {h}")
            lines.append("")
        if rec.fix_in:
            lines.append(f"**Dónde tocar:** `{rec.fix_in}`")
            lines.append("")
        for t in rec.turns:
            lines.append(f"### {t.who}")
            lines.append("")
            lines.append(f"**→** {t.inbound}")
            if t.note:
                lines.append(f"*{t.note}*")
            lines.append("")
            lines.append(
                f"⏱ dispatch `{t.dispatch_s:.1f}s` · total `{t.total_s:.1f}s`"
            )
            lines.append("")
            lines.append(f"🔍 {t.trace.summary()}")
            lines.append("")
            lines.append("```")
            lines.append(t.reply_text)
            lines.append("```")
            lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## Resumen latencia")
    lines.append("")
    lines.append("| # | Escenario | Turno | Quién | dispatch_s | total_s |")
    lines.append("|---:|---|---:|---|---:|---:|")
    for rec in records:
        for i, t in enumerate(rec.turns, 1):
            lines.append(
                f"| {rec.index} | {rec.name} | {i} | {t.who} | "
                f"{t.dispatch_s:.1f} | {t.total_s:.1f} |"
            )
    lines.append("")
    lines.append("```bash")
    lines.append("cd backend")
    lines.append(".venv/bin/python scripts/bot_trip_scenario_runner.py")
    lines.append(".venv/bin/python scripts/bot_trip_scenario_runner.py --only 2,3,6")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Escenarios LLM del canal viaje (guías/notas).")
    p.add_argument("--only", type=str, default=None,
                   help="índices 1-based o ids estables, ej. 1,3,5 o auschwitz-nota")
    p.add_argument("--provider", type=str, default=None, choices=["openai", "anthropic"],
                   help="proveedor del LLM (default: LLM_PROVIDER del .env)")
    p.add_argument("--pause-turn", type=float, default=PAUSE_BETWEEN_TURNS_S)
    p.add_argument("--pause-convo", type=float, default=PAUSE_BETWEEN_CONVOS_S)
    return p.parse_args(argv)


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
    if not ANDIAMO_CONTENT.is_dir():
        print(f"ERROR: no está el content de Andiamo en {ANDIAMO_CONTENT}")
        return 1

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
                raise SystemExit(f"id de escenario desconocido: {raw!r}; válidos: {sorted(by_id)}")
        label = f"custom ({len(idxs)})"
    else:
        idxs = list(range(1, len(CONVERSATIONS) + 1))
        label = f"suite viaje ({len(CONVERSATIONS)})"
    for i in idxs:
        if i < 1 or i > len(CONVERSATIONS):
            raise SystemExit(f"índice fuera de rango: {i} (hay {len(CONVERSATIONS)})")

    engine = create_async_engine(os.environ["DATABASE_URL"])
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    records: list[ConvoRecord] = []
    seed_info: dict = {}
    async with Session() as session:
        seed_info = await seed(session)
        print(
            f"Seed OK · {seed_info['guides']} docs · {seed_info['notes']} notas · "
            f"hoy={TODAY} (Viena) · provider={s.llm_provider or 'auto'}"
        )

        for n, idx in enumerate(idxs):
            conv = CONVERSATIONS[idx - 1]
            print(f"\n{'=' * 60}")
            print(f"CONVERSACIÓN {idx}/{len(CONVERSATIONS)}: {conv.name}")
            print(f"{'=' * 60}")
            records.append(await run_convo(session, idx, conv))
            if n < len(idxs) - 1:
                await asyncio.sleep(PAUSE_BETWEEN_CONVOS_S)

    md = render_md(records, seed_info=seed_info, suite_label=label)
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"\n📝 Escrito {OUT_MD.relative_to(ROOT)}")
    await engine.dispose()

    failed = [r for r in records if r.errors]
    checked = sum(1 for r in records if r.checked)
    if failed:
        print(f"❌ CHECKS: {len(failed)} de {checked} escenarios con fallas deterministas")
        for r in failed:
            print(f"   · {r.index} [{r.id}] {r.name}")
            for err in r.errors:
                print(f"       - {err}")
        return 1
    print(f"✅ CHECKS: {checked}/{len(records)} escenarios verificados sin fallas")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
