"""Herramientas del agente de Q&A de viaje: solo lectura sobre el cache local
de guías y notas de Andiamo (guide_docs / trip_notes / stop_guides).

Deliberadamente separadas de qa/tools.py (finanzas): los dos agentes no
comparten tools ni prompt. Los handlers levantan ValueError ante parámetros
inválidos; el loop de chat se lo devuelve al modelo para que se corrija.
"""
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import GuideDoc, StopGuide, TripNote
from app.llm.chat import ToolSpec

_MAX_DOC_CHARS = 25_000
_MAX_NOTE_CHARS = 4_000
_MAX_SEARCH_HITS = 8
_SNIPPET_RADIUS = 200


def _fold(s: str | None) -> str:
    """lowercase + sin tildes: la búsqueda no distingue 'Múnich' de 'munich'."""
    nfkd = unicodedata.normalize("NFD", (s or "").casefold())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def doc_link(guide_slug: str, doc_slug: str) -> str | None:
    base = (get_settings().andiamo_url or "").rstrip("/")
    return f"{base}/guias/{guide_slug}/{doc_slug}" if base else None


async def _load_docs(session: AsyncSession, cache: dict) -> list[GuideDoc]:
    if "docs" not in cache:
        cache["docs"] = (await session.execute(
            select(GuideDoc).order_by(GuideDoc.guide_slug, GuideDoc.doc_slug)
        )).scalars().all()
    return cache["docs"]


async def _load_stop_guides(session: AsyncSession, cache: dict) -> list[StopGuide]:
    if "stop_guides" not in cache:
        cache["stop_guides"] = (await session.execute(
            select(StopGuide).order_by(StopGuide.stop_slug, StopGuide.position)
        )).scalars().all()
    return cache["stop_guides"]


async def list_guides(session: AsyncSession, cache: dict) -> dict:
    docs = await _load_docs(session, cache)
    mappings = await _load_stop_guides(session, cache)
    stops_by_guide: dict[str, list[str]] = {}
    for m in mappings:
        stops_by_guide.setdefault(m.guide_slug, []).append(m.stop_slug)

    guides: dict[str, dict] = {}
    for d in docs:
        g = guides.setdefault(d.guide_slug, {
            "guide_slug": d.guide_slug, "guide_title": d.guide_title,
            "country": d.country, "stops": stops_by_guide.get(d.guide_slug, []),
            "docs": [],
        })
        g["docs"].append({"doc_slug": d.doc_slug, "title": d.title, "kind": d.kind})
    return {
        "guides": list(guides.values()),
        "note": ("kind: city=guía de la ciudad, daytrip=excursión, country=doc de país, "
                 "general=doc del viaje entero, resource=recurso práctico. "
                 "'stops' = paradas del itinerario que usan esa guía."),
    }


async def read_guide_doc(session: AsyncSession, cache: dict, *,
                         guide_slug: str, doc_slug: str) -> dict:
    docs = await _load_docs(session, cache)
    doc = next((d for d in docs if d.guide_slug == guide_slug and d.doc_slug == doc_slug), None)
    if doc is None:
        known = sorted({d.guide_slug for d in docs})
        raise ValueError(
            f"no existe el doc {guide_slug}/{doc_slug}; guías válidas: {known} "
            "(los doc_slug salen de list_guides o search_guides)"
        )
    content = doc.content_md
    if len(content) > _MAX_DOC_CHARS:
        content = content[:_MAX_DOC_CHARS] + "\n\n[TRUNCADO — el doc sigue en el link]"
    return {"title": doc.title, "guide_title": doc.guide_title,
            "link": doc_link(doc.guide_slug, doc.doc_slug), "content": content}


async def search_guides(session: AsyncSession, cache: dict, *, query: str,
                        guide_slug: str | None = None) -> dict:
    terms = [t for t in _fold(query).split() if len(t) >= 2]
    if not terms:
        raise ValueError("query vacía o demasiado corta")
    docs = await _load_docs(session, cache)
    if guide_slug:
        wanted = _fold(guide_slug)
        filtered = [d for d in docs if _fold(d.guide_slug) == wanted]
        if not filtered:
            known = sorted({d.guide_slug for d in docs})
            raise ValueError(f"guide_slug desconocido: {guide_slug!r}; válidas: {known}")
        docs = filtered

    scored: list[tuple[float, GuideDoc]] = []
    for d in docs:
        heading = _fold(d.title) + "\n" + _fold(d.guide_title)
        body = _fold(d.content_md)
        if not all(t in heading or t in body for t in terms):
            continue
        # Relevancia: título/guía pesan mucho más que menciones sueltas del
        # cuerpo — sin esto gana el primer doc en orden alfabético de guía.
        score = sum(heading.count(t) * 20 + body.count(t) for t in terms)
        scored.append((score, d))
    scored.sort(key=lambda pair: -pair[0])

    hits = []
    for _, d in scored[:_MAX_SEARCH_HITS]:
        # Snippet alrededor del primer término que aparece en el cuerpo.
        folded_body = _fold(d.content_md)
        pos = min((p for p in (folded_body.find(t) for t in terms) if p >= 0), default=-1)
        if pos >= 0:
            start = max(0, pos - _SNIPPET_RADIUS)
            end = min(len(d.content_md), pos + _SNIPPET_RADIUS)
            snippet = ("…" if start > 0 else "") + d.content_md[start:end].strip() \
                      + ("…" if end < len(d.content_md) else "")
        else:
            snippet = d.content_md[:_SNIPPET_RADIUS]
        hits.append({
            "guide_slug": d.guide_slug, "doc_slug": d.doc_slug, "title": d.title,
            "guide_title": d.guide_title, "kind": d.kind,
            "link": doc_link(d.guide_slug, d.doc_slug), "snippet": snippet,
        })
    return {
        "hits": hits,
        "note": ("busca todas las palabras (sin tildes) en título y contenido, "
                 "ordenado por relevancia; para el detalle completo usá "
                 "read_guide_doc"),
    }


async def list_notes(session: AsyncSession, *, stop_slug: str | None = None) -> dict:
    q = select(TripNote)
    if stop_slug:
        q = q.where((TripNote.stop_slug == stop_slug) | (TripNote.stop_slug.is_(None)))
    notes = (await session.execute(q)).scalars().all()
    # Pinned primero, después globales, después por fecha de edición desc.
    notes.sort(key=lambda n: (not n.pinned, n.stop_slug is not None,
                              -(n.updated_at.timestamp() if n.updated_at else 0)))
    rows = [{
        "title": n.title,
        "body": n.body[:_MAX_NOTE_CHARS],
        "stop_slug": n.stop_slug,
        "pinned": n.pinned,
    } for n in notes]
    return {
        "notes": rows,
        "note": ("anotaciones cargadas por ustedes en Andiamo; stop_slug null = nota "
                 "global del viaje. Si está vacío, no anotaron nada de eso."),
    }


def build_trip_tools(session: AsyncSession) -> list[ToolSpec]:
    cache: dict = {}  # docs compartidos entre tool calls del mismo turno

    async def _list_guides(**kw):
        return await list_guides(session, cache)

    async def _read(**kw):
        return await read_guide_doc(session, cache, **kw)

    async def _search(**kw):
        return await search_guides(session, cache, **kw)

    async def _notes(**kw):
        return await list_notes(session, **kw)

    return [
        ToolSpec(
            name="search_guides",
            description=("Busca en el texto completo de las guías del viaje. Es la primera "
                         "herramienta para casi toda pregunta ('tren a Sintra', 'entradas "
                         "Coliseo'). Devuelve hasta 8 docs por relevancia con un snippet; para "
                         "responder con detalle leé el mejor con read_guide_doc. En follow-ups "
                         "sobre la misma ciudad/país pasá guide_slug para no saltar de guía."),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string",
                              "description": "Palabras clave (sin conectores)."},
                    "guide_slug": {"type": "string",
                                   "description": ("Opcional: limita la búsqueda a esa guía "
                                                   "(slug de list_guides o de un hit previo).")},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            handler=_search,
        ),
        ToolSpec(
            name="list_guides",
            description=("Índice completo de las guías: por guía, sus docs (actividades, "
                         "gastronomía, transporte, day-trips...) y las paradas del itinerario "
                         "que la usan. Usalo para orientarte cuando la búsqueda no alcanza o "
                         "preguntan 'qué guías hay'."),
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            handler=_list_guides,
        ),
        ToolSpec(
            name="read_guide_doc",
            description=("Lee el markdown completo de un doc de guía (slugs de list_guides o "
                         "search_guides). Devuelve también el 'link' a la guía en Andiamo para "
                         "cerrar tu respuesta."),
            input_schema={
                "type": "object",
                "properties": {
                    "guide_slug": {"type": "string"},
                    "doc_slug": {"type": "string"},
                },
                "required": ["guide_slug", "doc_slug"],
                "additionalProperties": False,
            },
            handler=_read,
        ),
        ToolSpec(
            name="list_notes",
            description=("Anotaciones propias del viaje cargadas en Andiamo (reservas, "
                         "recordatorios, datos de alojamientos). Con stop_slug filtra a esa "
                         "parada + las globales; sin argumento devuelve todas."),
            input_schema={
                "type": "object",
                "properties": {"stop_slug": {"type": "string",
                                             "description": "Slug de la parada (del snapshot o list_guides)."}},
                "additionalProperties": False,
            },
            handler=_notes,
        ),
    ]
