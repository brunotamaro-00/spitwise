from datetime import date

import httpx
from sqlalchemy import select

from app.andiamo_content import sync_documents, sync_guides, sync_notes
from app.db.models import GuideDoc, StopGuide, SyncMeta, TripDocument, TripNote

_EXPORT = {
    "version": "v1-hash",
    "stopToGuides": {"roma": ["roma"], "napoles": ["napoles", "costa-amalfitana"]},
    "docs": [
        {"guideSlug": "roma", "guideTitle": "Roma", "docSlug": "actividades",
         "title": "Actividades", "country": "Italia", "countryFlag": "🇮🇹",
         "kind": "city", "file": "italia/roma/actividades.md",
         "content": "# Actividades en Roma\n\n- Coliseo €18"},
        {"guideSlug": "roma", "guideTitle": "Roma", "docSlug": "tivoli",
         "title": "Day Trip: Tivoli", "country": "Italia", "countryFlag": "🇮🇹",
         "kind": "daytrip", "file": "italia/roma/day-trips/tivoli.md",
         "content": "# Tivoli\n\nVilla d'Este"},
    ],
}

_NOTES = [
    {"id": "n1", "stopSlug": "roma", "title": "Hostel", "body": "Check-in 15hs",
     "pinned": True, "updatedAt": "2026-07-20T10:00:00.000Z"},
    {"id": "n2", "stopSlug": None, "title": "Seguro", "body": "Póliza 123",
     "pinned": False, "updatedAt": "2026-07-19T10:00:00.000Z"},
]


_DOCS = [
    {"id": "d1", "stopSlug": "roma", "label": "Voucher hostel", "note": "Check-in 15hs",
     "kind": "voucher", "source": "upload", "docDate": "2026-09-03",
     "fileName": "voucher.pdf", "mimeType": "application/pdf",
     "createdAt": "2026-08-01T10:00:00.000Z"},
    {"id": "d2", "stopSlug": None, "label": "Seguro", "note": None,
     "kind": "insurance", "source": "link", "docDate": None,
     "fileName": None, "mimeType": None, "createdAt": "2026-07-01T10:00:00.000Z"},
]


def _client(payload, status=200):
    def handler(request):
        return httpx.Response(status, json=payload)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://andiamo")


def _env(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("ANDIAMO_URL", "http://andiamo")
    get_settings.cache_clear()


async def test_sync_guides_upserts_and_maps_stops(db_session, monkeypatch):
    _env(monkeypatch)
    async with _client(_EXPORT) as c:
        r = await sync_guides(db_session, client=c)
    assert r == {"synced": 2, "deleted": 0, "status": "ok"}
    rows = (await db_session.execute(select(GuideDoc).order_by(GuideDoc.doc_slug))).scalars().all()
    assert [d.doc_slug for d in rows] == ["actividades", "tivoli"]
    assert rows[0].kind == "city"
    assert "Coliseo" in rows[0].content_md
    guides = (await db_session.execute(select(StopGuide).order_by(StopGuide.stop_slug, StopGuide.position))).scalars().all()
    assert [(g.stop_slug, g.guide_slug, g.position) for g in guides] == [
        ("napoles", "napoles", 0), ("napoles", "costa-amalfitana", 1), ("roma", "roma", 0),
    ]
    meta = await db_session.get(SyncMeta, "guides_version")
    assert meta.value == "v1-hash"


async def test_sync_guides_noop_on_same_version(db_session, monkeypatch):
    _env(monkeypatch)
    async with _client(_EXPORT) as c:
        await sync_guides(db_session, client=c)
        r = await sync_guides(db_session, client=c)
    assert r["status"] == "unchanged"


async def test_sync_guides_reconciles_deleted_docs(db_session, monkeypatch):
    _env(monkeypatch)
    async with _client(_EXPORT) as c:
        await sync_guides(db_session, client=c)
    smaller = {**_EXPORT, "version": "v2-hash", "docs": _EXPORT["docs"][:1]}
    async with _client(smaller) as c:
        r = await sync_guides(db_session, client=c)
    assert r == {"synced": 1, "deleted": 1, "status": "ok"}
    rows = (await db_session.execute(select(GuideDoc))).scalars().all()
    assert [d.doc_slug for d in rows] == ["actividades"]


async def test_sync_guides_never_wipes_on_failure(db_session, monkeypatch):
    _env(monkeypatch)
    async with _client(_EXPORT) as c:
        await sync_guides(db_session, client=c)
    async with _client({}, status=500) as c:
        r = await sync_guides(db_session, client=c)
    assert r["status"] == "fetch_failed"
    async with _client({"version": "x", "stopToGuides": {}, "docs": []}) as c:
        r = await sync_guides(db_session, client=c)
    assert r["status"] == "fetch_failed"
    assert len((await db_session.execute(select(GuideDoc))).scalars().all()) == 2


async def test_sync_notes_upserts_and_reconciles(db_session, monkeypatch):
    _env(monkeypatch)
    async with _client(_NOTES) as c:
        r = await sync_notes(db_session, client=c)
    assert r == {"synced": 2, "deleted": 0, "status": "ok"}
    n1 = await db_session.get(TripNote, "n1")
    assert n1.stop_slug == "roma" and n1.pinned
    n2 = await db_session.get(TripNote, "n2")
    assert n2.stop_slug is None
    async with _client(_NOTES[:1]) as c:
        r = await sync_notes(db_session, client=c)
    assert r["deleted"] == 1
    assert await db_session.get(TripNote, "n2") is None


async def test_sync_notes_failure_keeps_snapshot(db_session, monkeypatch):
    _env(monkeypatch)
    async with _client(_NOTES) as c:
        await sync_notes(db_session, client=c)
    async with _client([], status=500) as c:
        r = await sync_notes(db_session, client=c)
    assert r["status"] == "fetch_failed"
    assert len((await db_session.execute(select(TripNote))).scalars().all()) == 2


async def test_sync_documents_upserts_and_reconciles(db_session, monkeypatch):
    _env(monkeypatch)
    async with _client(_DOCS) as c:
        r = await sync_documents(db_session, client=c)
    assert r == {"synced": 2, "deleted": 0, "status": "ok"}
    d1 = await db_session.get(TripDocument, "d1")
    assert d1.stop_slug == "roma" and d1.kind == "voucher"
    assert d1.doc_date == date(2026, 9, 3)
    d2 = await db_session.get(TripDocument, "d2")
    assert d2.stop_slug is None and d2.doc_date is None and d2.source == "link"

    async with _client(_DOCS[:1]) as c:
        r = await sync_documents(db_session, client=c)
    assert r["deleted"] == 1
    assert await db_session.get(TripDocument, "d2") is None


async def test_sync_documents_failure_keeps_snapshot(db_session, monkeypatch):
    _env(monkeypatch)
    async with _client(_DOCS) as c:
        await sync_documents(db_session, client=c)
    async with _client([], status=500) as c:
        r = await sync_documents(db_session, client=c)
    assert r["status"] == "fetch_failed"
    assert len((await db_session.execute(select(TripDocument))).scalars().all()) == 2


async def test_sync_documents_empty_list_empties_table(db_session, monkeypatch):
    """Asimetría deliberada con las guías: borrar el último documento es
    legítimo, así que una lista vacía SÍ vacía la tabla."""
    _env(monkeypatch)
    async with _client(_DOCS) as c:
        await sync_documents(db_session, client=c)
    async with _client([]) as c:
        r = await sync_documents(db_session, client=c)
    assert r == {"synced": 0, "deleted": 2, "status": "ok"}
    assert (await db_session.execute(select(TripDocument))).scalars().all() == []


async def test_sync_documents_kind_degrades(db_session, monkeypatch):
    """Un kind que Andiamo agregó y Spitwise todavía no conoce entra igual;
    quien degrada a 'other' es el catálogo, no el sync."""
    _env(monkeypatch)
    async with _client([{**_DOCS[0], "kind": None, "source": None}]) as c:
        await sync_documents(db_session, client=c)
    d1 = await db_session.get(TripDocument, "d1")
    assert d1.kind == "other" and d1.source == "upload"
