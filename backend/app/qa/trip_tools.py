"""Herramientas del agente de Q&A de viaje: solo lectura sobre el cache local
de guías y notas de Andiamo (guide_docs / trip_notes / stop_guides).

Deliberadamente separadas de qa/tools.py (finanzas): los dos agentes no
comparten tools ni prompt. Los handlers levantan ValueError ante parámetros
inválidos; el loop de chat se lo devuelve al modelo para que se corrija.

Retrieval ESCALONADO (no un AND literal): la búsqueda saca conectores, separa
los lugares como filtro, y si no hay un doc que tenga todas las palabras baja a
cobertura parcial informando `match_mode` y qué términos faltaron. El AND duro
devolvía cero hits ante cualquier pregunta natural ("¿algo de Harry Potter en
Lisboa o Porto?") y el agente terminaba diciendo que las guías no dicen nada.
"""
import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.copy import link_andiamo_stop
from app.bot.documents.kinds import DOC_KINDS
from app.config import get_settings
from app.db.models import GuideDoc, Stop, StopGuide, TripDocument, TripNote
from app.llm.chat import ToolSpec

_MAX_DOC_CHARS = 25_000
_MAX_NOTE_CHARS = 4_000
_MAX_NOTES = 25
_MAX_GUIDES = 40
_MAX_SEARCH_HITS = 8
_SNIPPET_RADIUS = 200
_FOCUS_HEAD_CHARS = 2_000  # arranque del doc que se conserva al recortar por foco

# Conectores y muletillas del español rioplatense: si entran como términos, el
# AND no matchea nunca ("que", "hay", "en") y además ensucian el ranking.
_STOPWORDS = frozenset("""
a al algo alguna algunas alguno algunos ante antes aca aqui asi cada como con contra cual
cuales cuando cuanto cuanta cuantos de del desde donde dos el ella ellas ellos en entre era
eran eres es esa ese eso esta estan este esto estos fue fui ha hace hacer hacia hasta hay
ir la las le les lo los mas me mi mis mucho muy nada ni no nos nosotros nuestra nuestras
nuestro nuestros o os otra otro para pero podemos poder por porque pue que quiero se sea ser
si sin sobre solo son su sus tan te tenemos tener tiene todo todos tu tus un una uno unos
vamos ver y ya
""".split())


def _fold(s: str | None) -> str:
    """lowercase + sin tildes: la búsqueda no distingue 'Múnich' de 'munich'."""
    nfkd = unicodedata.normalize("NFD", (s or "").casefold())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^0-9a-z]+", _fold(text)) if t]


def _query_terms(query: str) -> list[str]:
    """Términos con contenido: sin conectores y sin repetidos, en orden.

    Si sacar stopwords deja la query vacía ('¿y ahí?'), se conservan los tokens
    largos: mejor buscar algo flojo que levantar un error."""
    toks = _tokens(query)
    terms = [t for t in toks if len(t) >= 3 and t not in _STOPWORDS]
    if not terms:
        terms = [t for t in toks if len(t) >= 2]
    seen, out = set(), []
    for t in terms:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def doc_link(guide_slug: str, doc_slug: str) -> str | None:
    base = (get_settings().andiamo_url or "").rstrip("/")
    return f"{base}/guias/{guide_slug}/{doc_slug}" if base else None


def document_link(doc_id: str) -> str | None:
    """Link al archivo guardado. Es la única ruta de Andiamo que resuelve las
    dos fuentes (upload en R2 y link externo); pide sesión abierta, que es el
    caso normal en el celu."""
    base = (get_settings().andiamo_url or "").rstrip("/")
    return f"{base}/api/documents/{doc_id}" if base else None


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


async def list_guides(session: AsyncSession, cache: dict, *,
                      country: str | None = None, stop_slug: str | None = None) -> dict:
    docs = await _load_docs(session, cache)
    mappings = await _load_stop_guides(session, cache)
    stops_by_guide: dict[str, list[str]] = {}
    for m in mappings:
        stops_by_guide.setdefault(m.guide_slug, []).append(m.stop_slug)

    if stop_slug:
        wanted = _fold(stop_slug)
        allowed = {m.guide_slug for m in mappings if _fold(m.stop_slug) == wanted}
        if not allowed:
            known = sorted({m.stop_slug for m in mappings})
            raise ValueError(f"stop_slug sin guías: {stop_slug!r}; con guías: {known}")
        docs = [d for d in docs if d.guide_slug in allowed]
    if country:
        wanted_c = _fold(country)
        docs = [d for d in docs if _fold(d.country) == wanted_c]

    guides: dict[str, dict] = {}
    for d in docs:
        g = guides.setdefault(d.guide_slug, {
            "guide_slug": d.guide_slug, "guide_title": d.guide_title,
            "country": d.country, "stops": stops_by_guide.get(d.guide_slug, []),
            "docs": [],
        })
        g["docs"].append({"doc_slug": d.doc_slug, "title": d.title, "kind": d.kind})
    rows = list(guides.values())
    # Truncar en silencio hacía que el agente afirmara "no hay guía de X" mirando
    # una lista recortada: si se corta, se dice.
    truncated = len(rows) > _MAX_GUIDES
    return {
        "guides": rows[:_MAX_GUIDES],
        "total_guides": len(rows),
        "truncated": truncated,
        "note": ("kind: city=guía de la ciudad, daytrip=excursión, country=doc de país, "
                 "general=doc del viaje entero, resource=recurso práctico. "
                 "'stops' = paradas del itinerario que usan esa guía."
                 + (" ATENCIÓN: la lista está recortada, filtrá por country o "
                    "stop_slug antes de afirmar que algo no existe." if truncated else "")),
    }


def _focus_window(content: str, terms: list[str]) -> str:
    """Recorte de un doc largo centrado en el primer término que aparece.

    Cortar siempre los primeros 25k escondía el pasaje pedido cuando estaba al
    final (los docs de actividades ponen precios abajo del todo)."""
    folded = _fold(content)
    pos = min((p for p in (folded.find(t) for t in terms) if p >= 0), default=-1)
    if pos < 0:
        return content[:_MAX_DOC_CHARS] + "\n\n[TRUNCADO — el doc sigue en el link]"
    head = content[:_FOCUS_HEAD_CHARS]
    body_budget = _MAX_DOC_CHARS - _FOCUS_HEAD_CHARS
    start = max(_FOCUS_HEAD_CHARS, pos - body_budget // 3)
    end = min(len(content), start + body_budget)
    return (
        head
        + "\n\n[… tramo omitido …]\n\n"
        + content[start:end]
        + ("\n\n[TRUNCADO — el doc sigue en el link]" if end < len(content) else "")
    )


async def read_guide_doc(session: AsyncSession, cache: dict, *,
                         guide_slug: str, doc_slug: str,
                         focus: str | None = None) -> dict:
    docs = await _load_docs(session, cache)
    doc = next((d for d in docs if d.guide_slug == guide_slug and d.doc_slug == doc_slug), None)
    if doc is None:
        known = sorted({d.guide_slug for d in docs})
        raise ValueError(
            f"no existe el doc {guide_slug}/{doc_slug}; guías válidas: {known} "
            "(los doc_slug salen de list_guides o search_guides)"
        )
    content = doc.content_md
    truncated = len(content) > _MAX_DOC_CHARS
    if truncated:
        terms = _query_terms(focus) if focus else []
        content = _focus_window(content, terms) if terms else (
            content[:_MAX_DOC_CHARS] + "\n\n[TRUNCADO — el doc sigue en el link]"
        )
    return {"title": doc.title, "guide_title": doc.guide_title,
            "link": doc_link(doc.guide_slug, doc.doc_slug),
            "truncated": truncated,
            "content": content}


def _place_index(docs: list[GuideDoc], mappings: list[StopGuide]) -> dict[str, set[str]]:
    """token de lugar → guide_slugs. Permite tratar 'lisboa' o 'porto' como
    FILTRO (dónde buscar) y no como palabra que el doc tiene que contener."""
    index: dict[str, set[str]] = {}

    def add(token: str, slug: str) -> None:
        if len(token) >= 3 and token not in _STOPWORDS:
            index.setdefault(token, set()).add(slug)

    for d in docs:
        for tok in _tokens(d.guide_slug):
            add(tok, d.guide_slug)
        for tok in _tokens(d.guide_title):
            add(tok, d.guide_slug)
        for tok in _tokens(d.country or ""):
            add(tok, d.guide_slug)
    by_guide = {d.guide_slug for d in docs}
    for m in mappings:
        if m.guide_slug in by_guide:
            for tok in _tokens(m.stop_slug):
                add(tok, m.guide_slug)
    return index


def _score_doc(d: GuideDoc, terms: list[str]) -> tuple[int, float, list[str]]:
    """(términos cubiertos, score, faltantes). El título y el nombre de la guía
    pesan mucho más que menciones sueltas del cuerpo."""
    heading = _fold(d.title) + "\n" + _fold(d.guide_title)
    body = _fold(d.content_md)
    covered, missing, score = 0, [], 0.0
    for t in terms:
        h, b = heading.count(t), body.count(t)
        if h or b:
            covered += 1
            score += h * 20 + min(b, 25)  # capar el cuerpo: un doc largo no gana por largo
        else:
            missing.append(t)
    if covered >= 2:
        # Bigramas: 'livraria lello' pegado vale mucho más que las dos sueltas.
        for a, b in zip(terms, terms[1:]):
            if f"{a} {b}" in body or f"{a} {b}" in heading:
                score += 30
    phrase = " ".join(terms)
    if len(terms) > 1 and (phrase in body or phrase in heading):
        score += 100
    return covered, score, missing


async def search_guides(session: AsyncSession, cache: dict, *, query: str,
                        guide_slug: str | None = None,
                        guide_slugs: list[str] | None = None) -> dict:
    terms = _query_terms(query)
    if not terms:
        raise ValueError("query vacía o demasiado corta")
    docs = await _load_docs(session, cache)
    mappings = await _load_stop_guides(session, cache)
    if not docs:
        return {"hits": [], "match_mode": "empty_cache", "searched_guides": [],
                "note": "el cache de guías está vacío: no hay nada que buscar todavía"}

    known_slugs = {d.guide_slug for d in docs}
    wanted: set[str] = set()
    for raw in ([guide_slug] if guide_slug else []) + list(guide_slugs or []):
        folded = _fold(raw)
        match = next((s for s in known_slugs if _fold(s) == folded), None)
        if match is None:
            raise ValueError(f"guide_slug desconocido: {raw!r}; válidas: {sorted(known_slugs)}")
        wanted.add(match)

    # Lugares mencionados en la query: filtran DÓNDE buscar, no qué contener.
    places = _place_index(docs, mappings)
    place_terms = [t for t in terms if t in places]
    if place_terms and not wanted:
        for t in place_terms:
            wanted |= places[t]
    content_terms = [t for t in terms if t not in places] or terms

    candidates = [d for d in docs if d.guide_slug in wanted] if wanted else docs

    scored = [(cov, sc, miss, d) for d in candidates
              for cov, sc, miss in [_score_doc(d, content_terms)] if cov]
    if not scored:
        # Cero cobertura: en vez de "no hay nada", devolver el índice de las
        # guías donde se buscó para que el modelo reformule con otro término.
        index = [{"guide_slug": d.guide_slug, "doc_slug": d.doc_slug, "title": d.title,
                  "kind": d.kind} for d in candidates[:_MAX_SEARCH_HITS * 2]]
        return {
            "hits": [], "match_mode": "none",
            "searched_guides": sorted(wanted) if wanted else "todas",
            "terms_used": content_terms,
            "docs_available": index,
            "note": ("ninguna guía menciona esos términos. Si la pregunta usa un nombre "
                     "que las guías no usarían (marcas, sagas, apodos), reintentá con el "
                     "concepto concreto que sí estaría escrito. Si no, decí que las guías "
                     "no lo cubren — pero recién después de intentarlo."),
        }

    full = [row for row in scored if row[0] == len(content_terms)]
    match_mode = "all" if full else "partial"
    rows = full or scored
    rows.sort(key=lambda r: (-r[0], -r[1]))

    hits = []
    for cov, sc, miss, d in rows[:_MAX_SEARCH_HITS]:
        hits.append({
            "guide_slug": d.guide_slug, "doc_slug": d.doc_slug, "title": d.title,
            "guide_title": d.guide_title, "kind": d.kind,
            "link": doc_link(d.guide_slug, d.doc_slug),
            "score": round(sc, 1), "matched_terms": [t for t in content_terms if t not in miss],
            "missing_terms": miss,
            "snippet": _snippet(d, content_terms),
        })
    return {
        "hits": hits,
        "match_mode": match_mode,
        "searched_guides": sorted(wanted) if wanted else "todas",
        "terms_used": content_terms,
        "truncated": len(rows) > _MAX_SEARCH_HITS,
        "note": ("ordenado por cobertura de términos y relevancia. match_mode 'partial' = "
                 "ningún doc tiene TODAS las palabras: mirá 'missing_terms' antes de "
                 "afirmar que algo está cubierto. Para el detalle completo usá "
                 "read_guide_doc (pasale 'focus' con las palabras clave si el doc es largo)."),
    }


def _snippet(d: GuideDoc, terms: list[str]) -> str:
    """Ventana alrededor del término MÁS específico (el que menos veces aparece):
    centrarla siempre en el primero traía la mención más genérica del doc."""
    folded = _fold(d.content_md)
    found = [(folded.count(t), folded.find(t)) for t in terms if folded.find(t) >= 0]
    if not found:
        return d.content_md[:_SNIPPET_RADIUS]
    pos = min(found)[1]
    start = max(0, pos - _SNIPPET_RADIUS)
    end = min(len(d.content_md), pos + _SNIPPET_RADIUS)
    return (("…" if start > 0 else "") + d.content_md[start:end].strip()
            + ("…" if end < len(d.content_md) else ""))


async def list_notes(session: AsyncSession, *, stop_slug: str | None = None,
                     query: str | None = None) -> dict:
    q = select(TripNote)
    if stop_slug:
        q = q.where((TripNote.stop_slug == stop_slug) | (TripNote.stop_slug.is_(None)))
    notes = (await session.execute(q)).scalars().all()
    if query:
        terms = _query_terms(query)
        notes = [n for n in notes
                 if any(t in _fold(f"{n.title} {n.body}") for t in terms)] or notes
    # Pinned primero, después globales, después por fecha de edición desc.
    notes.sort(key=lambda n: (not n.pinned, n.stop_slug is not None,
                              -(n.updated_at.timestamp() if n.updated_at else 0)))
    rows = [{
        "title": n.title,
        "body": n.body[:_MAX_NOTE_CHARS],
        "stop_slug": n.stop_slug,
        "pinned": n.pinned,
    } for n in notes[:_MAX_NOTES]]
    truncated = len(notes) > _MAX_NOTES
    return {
        "notes": rows,
        "total_notes": len(notes),
        "truncated": truncated,
        "note": ("anotaciones cargadas por ustedes en Andiamo; stop_slug null = nota "
                 "global del viaje. Si está vacío, no anotaron nada de eso."
                 + (" La lista viene recortada: filtrá por stop_slug o query."
                    if truncated else "")),
    }


def _score_document(d: TripDocument, terms: list[str]) -> tuple[int, list[str]]:
    """Score de un documento contra los términos. El label es el nombre que le
    puso quien lo guardó, así que pesa mucho más que la nota o el archivo."""
    label = _fold(d.label)
    rest = _fold(f"{d.note or ''} {d.file_name or ''} {DOC_KINDS.get(d.kind, '')}")
    score, matched = 0, []
    for t in terms:
        if t in label:
            score += 30
            matched.append(t)
        elif t in rest:
            score += 10
            matched.append(t)
    return score, matched


async def search_documents(session: AsyncSession, *, query: str | None = None,
                           stop_slug: str | None = None, kind: str | None = None) -> dict:
    """Busca en los documentos guardados en Andiamo (solo metadata local).

    Sin argumentos devuelve los más recientes. Un stop_slug que no es una parada
    del itinerario es un error del agente (ValueError); una parada real sin
    documentos devuelve lista vacía, que es una respuesta legítima.
    """
    if kind is not None and kind not in DOC_KINDS:
        raise ValueError(f"kind inválido: {kind!r}; válidos: {sorted(DOC_KINDS)}")

    if stop_slug:
        known = set((await session.execute(select(Stop.slug))).scalars().all())
        if stop_slug not in known:
            raise ValueError(f"stop_slug desconocido: {stop_slug!r}; paradas: {sorted(known)}")

    q = select(TripDocument)
    if stop_slug:
        # Los generales (stop_slug null) valen para cualquier parada: el seguro
        # de viaje es la respuesta correcta a "¿tengo algo del seguro en Roma?".
        q = q.where((TripDocument.stop_slug == stop_slug) | (TripDocument.stop_slug.is_(None)))
    if kind:
        q = q.where(TripDocument.kind == kind)
    docs = list((await session.execute(q)).scalars().all())

    terms = _query_terms(query) if query else []
    if terms:
        scored = [(s, m, d) for d in docs for s, m in [_score_document(d, terms)] if s > 0]
        scored.sort(key=lambda x: (-x[0], x[2].label))
        hits = [(d, m) for _, m, d in scored]
        match_mode = "all" if any(len(m) == len(terms) for _, m in hits) else (
            "partial" if hits else "none")
    else:
        docs.sort(key=lambda d: (d.created_at is None, -(d.created_at.timestamp()
                                                         if d.created_at else 0)))
        hits = [(d, []) for d in docs]
        match_mode = "listing"

    rows = [{
        "id": d.id,
        "label": d.label,
        "note": d.note,
        "kind": d.kind,
        "kind_label": DOC_KINDS.get(d.kind, "Otro"),
        "stop_slug": d.stop_slug,
        "doc_date": d.doc_date.isoformat() if d.doc_date else None,
        "matched_terms": m,
        "file_link": document_link(d.id),
        "stop_link": link_andiamo_stop(d.stop_slug),
    } for d, m in hits[:_MAX_SEARCH_HITS]]
    truncated = len(hits) > _MAX_SEARCH_HITS
    return {
        "documents": rows,
        "total_documents": len(hits),
        "match_mode": match_mode,
        "terms_used": terms,
        "truncated": truncated,
        "note": ("documentos que ustedes guardaron en Andiamo (vouchers, entradas, "
                 "seguros). 'file_link' abre el archivo; 'stop_link' es la parada donde "
                 "vive. stop_slug null = documento general del viaje. Si viene vacío, "
                 "no hay nada guardado de eso — decilo, no lo inventes."
                 + (" La lista viene recortada: afiná query o stop_slug."
                    if truncated else "")),
    }


def build_trip_tools(session: AsyncSession) -> list[ToolSpec]:
    cache: dict = {}  # docs compartidos entre tool calls del mismo turno

    async def _list_guides(**kw):
        return await list_guides(session, cache, **kw)

    async def _read(**kw):
        return await read_guide_doc(session, cache, **kw)

    async def _search(**kw):
        return await search_guides(session, cache, **kw)

    async def _notes(**kw):
        return await list_notes(session, **kw)

    async def _documents(**kw):
        return await search_documents(session, **kw)

    return [
        ToolSpec(
            name="search_guides",
            description=("Busca en el texto completo de las guías del viaje. Es la primera "
                         "herramienta para casi toda pregunta ('tren a Sintra', 'entradas "
                         "Coliseo'). Saca conectores y trata las ciudades/países de la "
                         "consulta como filtro, no como palabra a encontrar. Devuelve hasta "
                         "8 docs con snippet, score, 'matched_terms'/'missing_terms' y "
                         "'match_mode' ('all' | 'partial' | 'none'). Con 'none' devuelve el "
                         "índice de docs donde buscó: reintentá con el término concreto que "
                         "la guía SÍ usaría antes de decir que no está."),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string",
                              "description": "Palabras clave (sin conectores)."},
                    "guide_slugs": {
                        "type": "array", "items": {"type": "string"},
                        "description": ("Opcional: limita la búsqueda a esas guías. Para "
                                        "comparar ciudades ('Lisboa o Porto') pasá las dos."),
                    },
                    "guide_slug": {"type": "string",
                                   "description": "Opcional: una sola guía (equivale a guide_slugs de 1)."},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            handler=_search,
        ),
        ToolSpec(
            name="list_guides",
            description=("Índice de las guías: por guía, sus docs (actividades, gastronomía, "
                         "transporte, day-trips...) y las paradas del itinerario que la usan. "
                         "Usalo para orientarte cuando la búsqueda no alcanza o preguntan "
                         "'qué guías hay'. Se puede filtrar por country o stop_slug; si "
                         "'truncated' es true, la lista viene recortada."),
            input_schema={
                "type": "object",
                "properties": {
                    "country": {"type": "string", "description": "Filtra por país de la guía."},
                    "stop_slug": {"type": "string",
                                  "description": "Filtra a las guías de esa parada."},
                },
                "additionalProperties": False,
            },
            handler=_list_guides,
        ),
        ToolSpec(
            name="read_guide_doc",
            description=("Lee el markdown completo de un doc de guía (slugs de list_guides o "
                         "search_guides). Devuelve también el 'link' a la guía en Andiamo para "
                         "cerrar tu respuesta. En docs largos pasá 'focus' con las palabras "
                         "clave: el recorte se centra ahí en vez de cortar el final."),
            input_schema={
                "type": "object",
                "properties": {
                    "guide_slug": {"type": "string"},
                    "doc_slug": {"type": "string"},
                    "focus": {"type": "string",
                              "description": ("Palabras clave de lo que buscás dentro del doc "
                                              "(ej 'entradas precio'). Solo afecta docs largos.")},
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
                         "parada + las globales; con query filtra por texto. Sin argumentos "
                         "devuelve todas (hasta 25, con 'truncated')."),
            input_schema={
                "type": "object",
                "properties": {
                    "stop_slug": {"type": "string",
                                  "description": "Slug de la parada (del snapshot o list_guides)."},
                    "query": {"type": "string",
                              "description": "Palabras clave para filtrar las notas."},
                },
                "additionalProperties": False,
            },
            handler=_notes,
        ),
        ToolSpec(
            name="search_documents",
            description=("Documentos guardados en Andiamo: vouchers, entradas, check-ins, "
                         "seguros, pasajes. Usalo para '¿dónde está el voucher del hostel "
                         "de Roma?' o '¿tenemos la entrada del Coliseo?'. Filtrá por query "
                         "(texto del nombre o la nota), stop_slug (esa parada + los "
                         "generales) y/o kind. Sin argumentos lista los más recientes. "
                         "Devuelve 'file_link' (abre el archivo) y 'stop_link' (la parada): "
                         "pasale al usuario el file_link. Lista vacía = no está guardado."),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string",
                              "description": "Palabras clave del documento ('voucher hostel')."},
                    "stop_slug": {"type": "string",
                                  "description": "Slug de la parada (del snapshot o list_guides)."},
                    "kind": {"type": "string", "enum": sorted(DOC_KINDS),
                             "description": "Tipo de documento."},
                },
                "additionalProperties": False,
            },
            handler=_documents,
        ),
    ]
