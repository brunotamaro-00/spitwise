from app.db.models import GuideDoc, StopGuide, TripNote
from app.qa.trip_tools import build_trip_tools, list_guides, list_notes, read_guide_doc, search_guides


async def _seed(db_session):
    db_session.add_all([
        GuideDoc(guide_slug="roma", doc_slug="actividades", guide_title="Roma",
                 title="Actividades", country="Italia", kind="city",
                 file="italia/roma/actividades.md",
                 content_md="# Actividades en Roma\n\n- **Coliseo** €18, reservar en parcocolosseo.it\n- Trastevere de noche"),
        GuideDoc(guide_slug="roma", doc_slug="tivoli", guide_title="Roma",
                 title="Day Trip: Tívoli", country="Italia", kind="daytrip",
                 file="italia/roma/day-trips/tivoli.md",
                 content_md="# Tívoli\n\nVilla d'Este y Villa Adriana, tren desde Termini"),
        GuideDoc(guide_slug="lisboa", doc_slug="transporte", guide_title="Lisboa",
                 title="Transporte", country="Portugal", kind="city",
                 file="portugal/lisboa/transporte.md",
                 content_md="# Transporte\n\nTren a Sintra desde Rossio cada 20 min, €2,30 con Viva Viagem"),
    ])
    db_session.add_all([
        StopGuide(stop_slug="roma", guide_slug="roma", position=0),
        StopGuide(stop_slug="lisboa", guide_slug="lisboa", position=0),
    ])
    db_session.add_all([
        TripNote(id="n1", stop_slug="roma", title="Hostel Roma", body="Check-in 15hs, cod 4421", pinned=True),
        TripNote(id="n2", stop_slug=None, title="Seguro", body="Póliza 123", pinned=False),
        TripNote(id="n3", stop_slug="lisboa", title="Tranvía 28", body="Ir temprano", pinned=False),
    ])
    await db_session.commit()


async def test_list_guides_index(db_session):
    await _seed(db_session)
    out = await list_guides(db_session, {})
    by_slug = {g["guide_slug"]: g for g in out["guides"]}
    assert by_slug["roma"]["stops"] == ["roma"]
    assert {d["doc_slug"] for d in by_slug["roma"]["docs"]} == {"actividades", "tivoli"}
    assert by_slug["roma"]["docs"][0]["kind"] in ("city", "daytrip")


async def test_search_guides_multiterm_accent_insensitive(db_session):
    await _seed(db_session)
    out = await search_guides(db_session, {}, query="tren sintra")
    assert [h["doc_slug"] for h in out["hits"]] == ["transporte"]
    assert "Sintra" in out["hits"][0]["snippet"]
    # Sin tildes también matchea ('tivoli' vs 'Tívoli').
    out = await search_guides(db_session, {}, query="tivoli")
    assert any(h["doc_slug"] == "tivoli" for h in out["hits"])
    # Todas las palabras tienen que estar.
    out = await search_guides(db_session, {}, query="coliseo sintra")
    assert out["hits"] == []


async def test_read_guide_doc_link_and_truncation(db_session, monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("ANDIAMO_URL", "http://andiamo.test/")
    get_settings.cache_clear()
    await _seed(db_session)
    out = await read_guide_doc(db_session, {}, guide_slug="roma", doc_slug="actividades")
    assert out["link"] == "http://andiamo.test/guias/roma/actividades"
    assert "Coliseo" in out["content"]

    db_session.add(GuideDoc(guide_slug="g", doc_slug="largo", guide_title="G",
                            title="Largo", kind="city", file="g/largo.md",
                            content_md="x" * 30_000))
    await db_session.commit()
    out = await read_guide_doc(db_session, {}, guide_slug="g", doc_slug="largo")
    assert out["content"].endswith("[TRUNCADO — el doc sigue en el link]")
    assert len(out["content"]) < 26_000
    get_settings.cache_clear()


async def test_read_guide_doc_unknown_raises(db_session):
    await _seed(db_session)
    try:
        await read_guide_doc(db_session, {}, guide_slug="paris", doc_slug="nada")
        raise AssertionError("debió levantar ValueError")
    except ValueError as e:
        assert "lisboa" in str(e)


async def test_list_notes_filtering_and_order(db_session):
    await _seed(db_session)
    out = await list_notes(db_session)
    assert len(out["notes"]) == 3
    assert out["notes"][0]["title"] == "Hostel Roma"  # pinned primero
    out = await list_notes(db_session, stop_slug="roma")
    titles = {n["title"] for n in out["notes"]}
    assert titles == {"Hostel Roma", "Seguro"}  # de la parada + globales


async def test_build_trip_tools_names(db_session):
    tools = build_trip_tools(db_session)
    assert [t.name for t in tools] == [
        "search_guides", "list_guides", "read_guide_doc", "list_notes",
    ]
