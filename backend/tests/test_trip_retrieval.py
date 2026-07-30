"""Retrieval escalonado del canal viaje (app/qa/trip_tools.py).

El AND literal sobre todas las palabras dejaba en cero cualquier pregunta
natural: los conectores ('hay', 'en', 'algo') no están en ningún doc, y una
consulta multi-ciudad ('Lisboa o Porto') exigía que UN doc nombrara las dos.
Acá se fija el comportamiento nuevo: stopwords fuera, lugares como filtro,
cobertura parcial declarada y truncación visible.
"""
from app.db.models import GuideDoc, StopGuide, TripNote
from app.qa.trip_tools import (
    list_guides, list_notes, read_guide_doc, search_guides,
)


async def _seed(db_session):
    db_session.add_all([
        GuideDoc(guide_slug="porto", doc_slug="actividades", guide_title="Porto",
                 title="Actividades", country="Portugal", kind="city",
                 file="portugal/porto/actividades.md",
                 content_md=("# Actividades en Porto\n\n"
                             "- **Livraria Lello** — la librería más linda del mundo, "
                             "inspiración parcial de Hogwarts según algunos autores "
                             "(€10 Silver o €15.95 Gold)\n"
                             "- Ribeira al atardecer\n")),
        GuideDoc(guide_slug="lisboa", doc_slug="actividades", guide_title="Lisboa",
                 title="Actividades", country="Portugal", kind="city",
                 file="portugal/lisboa/actividades.md",
                 content_md="# Actividades en Lisboa\n\n- Torre de Belém €8\n- Alfama\n"),
        GuideDoc(guide_slug="lisboa", doc_slug="transporte", guide_title="Lisboa",
                 title="Transporte", country="Portugal", kind="city",
                 file="portugal/lisboa/transporte.md",
                 content_md="# Transporte\n\nTren a Sintra desde Rossio, €2,30\n"),
        GuideDoc(guide_slug="viena", doc_slug="actividades", guide_title="Viena",
                 title="Actividades", country="Austria", kind="city",
                 file="austria/viena/actividades.md",
                 content_md="# Actividades en Viena\n\n- Schönbrunn €26\n"),
    ])
    db_session.add_all([
        StopGuide(stop_slug="porto", guide_slug="porto", position=0),
        StopGuide(stop_slug="lisboa", guide_slug="lisboa", position=0),
        StopGuide(stop_slug="viena", guide_slug="viena", position=0),
    ])
    await db_session.commit()


async def test_stopwords_do_not_kill_the_query(db_session):
    """'¿hay algo del tren a Sintra?' — los conectores no están en ningún doc."""
    await _seed(db_session)
    out = await search_guides(db_session, {}, query="hay algo del tren a Sintra?")
    assert out["terms_used"] == ["tren", "sintra"]
    assert out["hits"] and out["hits"][0]["doc_slug"] == "transporte"


async def test_places_filter_instead_of_being_required_words(db_session):
    """'actividades en Viena': 'viena' elige la guía, no tiene que estar en el cuerpo."""
    await _seed(db_session)
    out = await search_guides(db_session, {}, query="actividades en Viena")
    assert out["searched_guides"] == ["viena"]
    assert [h["guide_slug"] for h in out["hits"]] == ["viena"]


async def test_multi_city_query_searches_both_guides(db_session):
    """'Lisboa o Porto' — antes exigía que UN doc nombrara las dos ciudades."""
    await _seed(db_session)
    out = await search_guides(db_session, {}, query="librería en Lisboa o Porto")
    assert out["searched_guides"] == ["lisboa", "porto"]
    assert [h["guide_slug"] for h in out["hits"]] == ["porto"]


async def test_multi_guide_slugs_param(db_session):
    await _seed(db_session)
    out = await search_guides(db_session, {}, query="actividades",
                              guide_slugs=["lisboa", "porto"])
    assert {h["guide_slug"] for h in out["hits"]} == {"lisboa", "porto"}


async def test_unknown_guide_slug_tells_the_model_the_valid_ones(db_session):
    await _seed(db_session)
    try:
        await search_guides(db_session, {}, query="tren", guide_slugs=["lisbon"])
    except ValueError as exc:
        assert "lisboa" in str(exc)
    else:
        raise AssertionError("un slug inexistente tiene que ser ValueError")


async def test_zero_hits_returns_the_index_to_retry_with(db_session):
    """Caso Harry Potter: ninguna guía usa esas palabras. En vez de 'no hay
    nada', se devuelve dónde se buscó para que el modelo reformule."""
    await _seed(db_session)
    out = await search_guides(db_session, {}, query="harry potter en Lisboa o Porto")
    assert out["match_mode"] == "none"
    assert out["searched_guides"] == ["lisboa", "porto"]
    assert {d["doc_slug"] for d in out["docs_available"]}  # hay docs para leer
    # Y el término que sí usa la guía encuentra el pasaje.
    out2 = await search_guides(db_session, {}, query="hogwarts",
                               guide_slugs=["lisboa", "porto"])
    assert out2["hits"][0]["guide_slug"] == "porto"
    assert "Lello" in out2["hits"][0]["snippet"]


async def test_partial_coverage_declares_missing_terms(db_session):
    await _seed(db_session)
    out = await search_guides(db_session, {}, query="hogwarts belem")
    assert out["match_mode"] == "partial"
    assert all(h["missing_terms"] for h in out["hits"])
    assert all(h["matched_terms"] for h in out["hits"])


async def test_phrase_boost_beats_scattered_mentions(db_session):
    db_session.add_all([
        GuideDoc(guide_slug="a", doc_slug="uno", guide_title="A", title="Uno", kind="city",
                 file="a/uno.md",
                 content_md="tren por acá. sintra por allá. tren. sintra. tren. sintra."),
        GuideDoc(guide_slug="b", doc_slug="dos", guide_title="B", title="Dos", kind="city",
                 file="b/dos.md", content_md="el tren sintra sale de Rossio"),
    ])
    await db_session.commit()
    out = await search_guides(db_session, {}, query="tren sintra")
    assert out["hits"][0]["doc_slug"] == "dos"


async def test_long_doc_focus_keeps_the_relevant_passage(db_session):
    filler = "relleno " * 6000  # > 25k chars
    db_session.add(GuideDoc(
        guide_slug="porto", doc_slug="largo", guide_title="Porto", title="Largo",
        kind="city", file="portugal/porto/largo.md",
        content_md=f"# Largo\n\n{filler}\n\nEntradas Livraria Lello: 10 euros Silver.\n",
    ))
    await db_session.commit()
    plain = await read_guide_doc(db_session, {}, guide_slug="porto", doc_slug="largo")
    focused = await read_guide_doc(db_session, {}, guide_slug="porto", doc_slug="largo",
                                   focus="entradas lello precio")
    assert plain["truncated"] and "Livraria Lello: 10 euros" not in plain["content"]
    assert "Livraria Lello: 10 euros" in focused["content"]
    assert focused["content"].startswith("# Largo")  # el encabezado sigue estando


async def test_list_guides_filters_and_reports_totals(db_session):
    await _seed(db_session)
    out = await list_guides(db_session, {}, country="Portugal")
    assert {g["guide_slug"] for g in out["guides"]} == {"lisboa", "porto"}
    assert out["truncated"] is False and out["total_guides"] == 2
    by_stop = await list_guides(db_session, {}, stop_slug="viena")
    assert {g["guide_slug"] for g in by_stop["guides"]} == {"viena"}


async def test_list_notes_truncation_is_visible(db_session):
    for i in range(30):
        db_session.add(TripNote(id=f"n{i}", stop_slug=None, title=f"Nota {i}",
                                body="cuerpo", pinned=False))
    await db_session.commit()
    out = await list_notes(db_session)
    assert out["truncated"] is True and out["total_notes"] == 30
    assert len(out["notes"]) == 25 and "recortada" in out["note"]


async def test_list_notes_query_filter(db_session):
    db_session.add_all([
        TripNote(id="a", stop_slug=None, title="Auschwitz", body="slot 10:30", pinned=True),
        TripNote(id="b", stop_slug=None, title="Hostel", body="check-in 15hs", pinned=False),
    ])
    await db_session.commit()
    out = await list_notes(db_session, query="auschwitz")
    assert [n["title"] for n in out["notes"]] == ["Auschwitz"]


async def test_empty_cache_is_declared_not_a_negative_answer(db_session):
    out = await search_guides(db_session, {}, query="coliseo")
    assert out["match_mode"] == "empty_cache" and out["hits"] == []


# --- guarda estructural de grounding ------------------------------------------
# El prompt ya prohíbe responder de cultura general; esto lo hace verificable.

from datetime import date  # noqa: E402

from app.api.auth import hash_password  # noqa: E402
from app.bot.active_stop import get_state_payload  # noqa: E402
from app.bot.trip_qa import handle_trip_question  # noqa: E402
from app.db.models import User  # noqa: E402
from app.llm.chat import ChatResult  # noqa: E402

TODAY = date(2026, 8, 6)


class _Chat:
    """Responde sin llamar herramientas (como el modelo tirando de memoria)."""

    def __init__(self, text, tool_calls=()):
        self.result = ChatResult(text=text, outcome="ok", tool_calls=list(tool_calls))

    async def run(self, **kw):
        return self.result


async def _user(db_session):
    u = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549111")
    db_session.add(u)
    db_session.add(User(username="katia", password_hash=hash_password("pw"),
                        whatsapp_wa_id="549222"))
    await db_session.commit()
    return u


async def test_concrete_answer_without_tools_is_blocked(db_session):
    await _seed(db_session)
    u = await _user(db_session)
    reply = await handle_trip_question(
        db_session, u, "549111", "cuánto sale la Livraria Lello?", TODAY,
        chat_client=_Chat("Sale *€8* y abre 9:30."),
    )
    assert "no te lo invento" in reply.text.casefold()
    # Tampoco se guarda: el hilo no puede quedar anclado a algo sin respaldo.
    payload = await get_state_payload(db_session, "549111")
    assert not payload.get("trip_qa_history")


async def test_concrete_answer_with_tool_evidence_passes(db_session):
    await _seed(db_session)
    u = await _user(db_session)
    reply = await handle_trip_question(
        db_session, u, "549111", "cuánto sale?", TODAY,
        chat_client=_Chat("Sale *€10* el Silver.", tool_calls=["search_guides"]),
    )
    assert "€10" in reply.text


async def test_qualitative_answer_without_tools_is_allowed(db_session):
    """Una respuesta sin datos concretos (saludo, redirección) no necesita tools."""
    await _seed(db_session)
    u = await _user(db_session)
    reply = await handle_trip_question(
        db_session, u, "549111", "hola", TODAY,
        chat_client=_Chat("¡Hola! Preguntame por las guías del viaje."),
    )
    assert reply.text.startswith("¡Hola!")


async def test_stale_guides_are_surfaced_in_the_snapshot(db_session):
    from datetime import datetime, timedelta

    from sqlalchemy import update

    from app.db.models import GuideDoc as GD
    from app.bot.trip_qa import _trip_context_snapshot

    await _seed(db_session)
    await db_session.execute(update(GD).values(synced_at=datetime.utcnow() - timedelta(days=3)))
    await db_session.commit()
    snap = await _trip_context_snapshot(db_session, TODAY)
    assert "desactualizadas" in snap
