"""Canal documentos: verify de media, pipeline de preview, correcciones y confirm."""
import json
from datetime import date

from sqlalchemy import select

from app.api.auth import hash_password
from app.bot.documents import pipeline
from app.bot.documents.pipeline import (
    cancel_doc_upload,
    confirm_doc_upload,
    handle_document_media,
    maybe_apply_correction,
)
from app.config import get_settings
from app.db.models import BotPendingAction, Stop, User
from app.whatsapp.verify import MediaInfo, iter_incoming_messages

TODAY = date(2026, 8, 20)
PDF_BYTES = b"%PDF-1.4 fake"


class FakeMeta:
    def __init__(self, data=PDF_BYTES, mime="application/pdf", fail=False):
        self.data, self.mime, self.fail = data, mime, fail
        self.downloads = 0

    async def download_media(self, media_id):
        self.downloads += 1
        if self.fail:
            raise RuntimeError("meta down")
        return self.data, self.mime

    async def aclose(self):
        pass


class FakeVision:
    def __init__(self, extraction=None, correction=None):
        self.extraction = extraction or {}
        self.correction = correction or {"is_correction": False}
        self.extract_calls = 0
        self.correction_calls = 0

    async def extract(self, file_bytes, mime_type, **kwargs):
        self.extract_calls += 1
        self.last_extract_kwargs = kwargs
        return self.extraction

    async def classify_correction(self, text, extraction_summary, **kwargs):
        self.correction_calls += 1
        return self.correction


def _extraction(**over):
    base = {
        "is_travel_doc": True, "kind": "train", "doc_date": "2026-08-29",
        "stop_slug": "paris", "label": "Tren Ámsterdam–París",
        "note": "Eurostar 9434. PNR VD4XNX.", "confidence": 0.9,
    }
    base.update(over)
    return base


async def _seed(db_session):
    u = User(username="bruno", password_hash=hash_password("pw"), whatsapp_wa_id="549110")
    db_session.add(u)
    db_session.add(Stop(slug="paris", order=1, name="París", country="Francia",
                        arrival_date=date(2026, 8, 29), departure_date=date(2026, 9, 2)))
    db_session.add(Stop(slug="york", order=2, name="York", country="UK",
                        arrival_date=date(2026, 8, 13), departure_date=date(2026, 8, 15)))
    db_session.add(Stop(slug="viejo", order=3, name="Viejo", is_archived=True))
    await db_session.commit()
    return u


def _media(**over):
    base = dict(media_id="MEDIA1", mime_type="application/pdf",
                caption=None, filename="ticket.pdf")
    base.update(over)
    return MediaInfo(**base)


async def _pending_rows(db_session):
    return (await db_session.execute(
        select(BotPendingAction).where(BotPendingAction.action_type == "doc_upload")
    )).scalars().all()


# --- verify.py ---

def test_iter_image_and_document_media():
    payload = {"entry": [{"changes": [{"value": {"messages": [
        {"from": "549110", "id": "wamid.I", "type": "image",
         "image": {"id": "MID1", "mime_type": "image/jpeg", "caption": "entrada museo"}},
        {"from": "549110", "id": "wamid.D", "type": "document",
         "document": {"id": "MID2", "mime_type": "application/pdf", "filename": "res.pdf"}},
        {"from": "549110", "id": "wamid.A", "type": "audio", "audio": {"id": "MID3"}},
    ]}}]}]}
    msgs = iter_incoming_messages(payload)
    assert [m.type for m in msgs] == ["image", "document", "audio"]
    img, doc, audio = msgs
    assert img.media.media_id == "MID1"
    assert img.media.caption == "entrada museo"
    assert img.media.filename is None
    assert doc.media.filename == "res.pdf"
    assert audio.media is None


# --- pipeline: preview ---

async def test_media_preview_creates_pending(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "andiamo_url", "http://andiamo.test")
    u = await _seed(db_session)
    vision = FakeVision(_extraction())
    reply = await handle_document_media(db_session, u, "549110", _media(), TODAY,
                                        vision_client=vision, meta_client=FakeMeta())
    assert "Tren Ámsterdam–París" in reply.text
    assert "París" in reply.text
    assert "29/08" in reply.text
    assert [bid.split(":")[0] for bid, _ in reply.buttons] == ["doc_save", "doc_cancel"]
    rows = await _pending_rows(db_session)
    assert len(rows) == 1
    data = json.loads(rows[0].payload_json)
    assert data["media_id"] == "MEDIA1" and data["stop_slug"] == "paris"
    # El catálogo del prompt sale de la DB y excluye archivadas.
    slugs = [s["slug"] for s in vision.last_extract_kwargs["stops"]]
    assert slugs == ["paris", "york"]


async def test_media_unknown_slug_falls_to_general(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "andiamo_url", "http://andiamo.test")
    u = await _seed(db_session)
    vision = FakeVision(_extraction(stop_slug="narnia", kind="inventado", doc_date="no-fecha"))
    reply = await handle_document_media(db_session, u, "549110", _media(), TODAY,
                                        vision_client=vision, meta_client=FakeMeta())
    assert "General" in reply.text
    assert "Sin fecha" in reply.text
    data = json.loads((await _pending_rows(db_session))[0].payload_json)
    assert data["stop_slug"] is None and data["kind"] == "other" and data["doc_date"] is None


async def test_media_rejects_unsupported_and_big(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "andiamo_url", "http://andiamo.test")
    u = await _seed(db_session)
    vision = FakeVision(_extraction())
    r = await handle_document_media(db_session, u, "549110", _media(mime_type="video/mp4"),
                                    TODAY, vision_client=vision, meta_client=FakeMeta())
    assert "tipo de archivo" in r.text
    big = FakeMeta(data=b"x" * (pipeline.MAX_BYTES + 1))
    r = await handle_document_media(db_session, u, "549110", _media(), TODAY,
                                    vision_client=vision, meta_client=big)
    assert "pesado" in r.text
    assert vision.extract_calls == 0  # rechazo temprano: nunca llegó al LLM
    assert await _pending_rows(db_session) == []


async def test_media_without_andiamo_degrades(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "andiamo_url", "")
    u = await _seed(db_session)
    r = await handle_document_media(db_session, u, "549110", _media(), TODAY,
                                    vision_client=FakeVision(), meta_client=FakeMeta())
    assert "Andiamo" in r.text


# --- correcciones por texto ---

async def test_correction_without_pending_skips_llm(db_session):
    u = await _seed(db_session)
    vision = FakeVision()
    assert await maybe_apply_correction(db_session, u, "549110", "cena 20 euros", TODAY,
                                        vision_client=vision) is None
    assert vision.correction_calls == 0


async def test_correction_rewrites_preview(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "andiamo_url", "http://andiamo.test")
    u = await _seed(db_session)
    await handle_document_media(db_session, u, "549110", _media(), TODAY,
                                vision_client=FakeVision(_extraction()), meta_client=FakeMeta())
    vision = FakeVision(correction={"is_correction": True, "stop_slug": "york",
                                    "doc_date": "2026-08-13", "kind": None,
                                    "label": None, "note": None})
    reply = await maybe_apply_correction(db_session, u, "549110", "es en york el 13", TODAY,
                                         vision_client=vision)
    assert reply is not None and "York" in reply.text and "13/08" in reply.text
    rows = await _pending_rows(db_session)
    open_rows = [r for r in rows if r.cancelled_at is None]
    assert len(rows) == 2 and len(open_rows) == 1  # el viejo quedó cancelado
    assert json.loads(open_rows[0].payload_json)["stop_slug"] == "york"


async def test_non_correction_falls_through(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "andiamo_url", "http://andiamo.test")
    u = await _seed(db_session)
    await handle_document_media(db_session, u, "549110", _media(), TODAY,
                                vision_client=FakeVision(_extraction()), meta_client=FakeMeta())
    vision = FakeVision(correction={"is_correction": False, "stop_slug": None,
                                    "doc_date": None, "kind": None, "label": None, "note": None})
    assert await maybe_apply_correction(db_session, u, "549110", "gasté 20 en comida", TODAY,
                                        vision_client=vision) is None
    assert vision.correction_calls == 1


async def test_vision_failure_does_not_break_the_finance_path(db_session, monkeypatch):
    """Con un preview fresco a la vista, TODO texto pasa por classify_correction.
    Si Vision se cae, el gasto tiene que guardarse igual por el parser."""
    from sqlalchemy import select

    from app.bot.dispatcher import dispatch
    from app.db.models import Movement

    class FakeLLM:
        def __init__(self, payload):
            self.payload = payload

        async def parse(self, text, **kwargs):
            return self.payload

    monkeypatch.setattr(get_settings(), "andiamo_url", "http://andiamo.test")
    u = await _seed(db_session)
    # El camino financiero exige los dos usuarios (invariante 1) y categorías.
    db_session.add(User(username="katia", password_hash=hash_password("pw"),
                        whatsapp_wa_id="549222"))
    from app.categories.seed import seed_categories
    await seed_categories(db_session)
    await db_session.commit()
    await handle_document_media(db_session, u, "549110", _media(), TODAY,
                                vision_client=FakeVision(_extraction()), meta_client=FakeMeta())

    class BoomVision(FakeVision):
        async def classify_correction(self, text, extraction_summary, **kwargs):
            self.correction_calls += 1
            raise RuntimeError("openai down")

    vision = BoomVision()
    assert await maybe_apply_correction(db_session, u, "549110", "cena 20 euros", TODAY,
                                        vision_client=vision) is None
    assert vision.correction_calls == 1

    llm = FakeLLM({"intent": "expense", "amount": "20", "currency": "EUR",
                   "description": "Cena", "category": "Comida", "split": "shared",
                   "paid_by": None, "date": None, "city": None,
                   "confidence": 0.9, "candidates": []})
    reply = await dispatch(db_session, "549110", "text", "cena 20 euros", None, TODAY,
                           llm_client=llm, vision_client=BoomVision())
    assert "Cena" in reply.text
    movs = (await db_session.execute(select(Movement))).scalars().all()
    assert len(movs) == 1 and movs[0].description == "Cena"


# --- dispatcher: ruteo lateral ---

async def test_dispatch_routes_media_and_unsupported(db_session, monkeypatch):
    from app.bot.dispatcher import dispatch
    monkeypatch.setattr(get_settings(), "andiamo_url", "")
    await _seed(db_session)
    r = await dispatch(db_session, "549110", "image", None, None, TODAY, media=_media())
    assert "Andiamo" in r.text  # entró al canal documentos (degradado sin URL)
    r = await dispatch(db_session, "549110", "audio", None, None, TODAY)
    assert "Audio" in r.text


# --- confirm / cancel ---

async def _preview_token(db_session):
    return (await _pending_rows(db_session))[0].token


async def test_confirm_uploads_and_closes(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "andiamo_url", "http://andiamo.test")
    u = await _seed(db_session)
    await handle_document_media(db_session, u, "549110", _media(), TODAY,
                                vision_client=FakeVision(_extraction()), meta_client=FakeMeta())
    calls = []

    async def fake_upload(**kwargs):
        calls.append(kwargs)
        return {"id": "doc1"}

    monkeypatch.setattr(pipeline, "upload_document", fake_upload)
    reply = await confirm_doc_upload(db_session, u, await _preview_token(db_session),
                                     meta_client=FakeMeta())
    assert "guardado en Andiamo" in reply.text
    assert "http://andiamo.test/stops/paris" in reply.text
    assert calls[0]["stop_slug"] == "paris" and calls[0]["kind"] == "train"
    assert calls[0]["doc_date"] == "2026-08-29"
    assert calls[0]["file_bytes"] == PDF_BYTES
    row = (await _pending_rows(db_session))[0]
    assert row.confirmed_at is not None


async def test_confirm_retries_once_then_fails_open(db_session, monkeypatch):
    from app.andiamo_documents import AndiamoUploadError
    monkeypatch.setattr(get_settings(), "andiamo_url", "http://andiamo.test")
    u = await _seed(db_session)
    await handle_document_media(db_session, u, "549110", _media(), TODAY,
                                vision_client=FakeVision(_extraction()), meta_client=FakeMeta())
    attempts = []

    async def flaky_upload(**kwargs):
        attempts.append(1)
        raise AndiamoUploadError("boom")

    monkeypatch.setattr(pipeline, "upload_document", flaky_upload)
    token = await _preview_token(db_session)
    reply = await confirm_doc_upload(db_session, u, token, meta_client=FakeMeta())
    assert len(attempts) == 2  # 1 intento + 1 reintento
    assert "Guardar" in reply.text  # invita a reintentar
    row = (await _pending_rows(db_session))[0]
    assert row.confirmed_at is None and row.cancelled_at is None  # sigue abierto

    async def ok_upload(**kwargs):
        return {"id": "doc1"}

    monkeypatch.setattr(pipeline, "upload_document", ok_upload)
    reply = await confirm_doc_upload(db_session, u, token, meta_client=FakeMeta())
    assert "guardado en Andiamo" in reply.text


async def test_cancel_closes_pending(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "andiamo_url", "http://andiamo.test")
    u = await _seed(db_session)
    await handle_document_media(db_session, u, "549110", _media(), TODAY,
                                vision_client=FakeVision(_extraction()), meta_client=FakeMeta())
    token = await _preview_token(db_session)
    reply = await cancel_doc_upload(db_session, u, token)
    assert "Cancelado" in reply.text
    assert (await _pending_rows(db_session))[0].cancelled_at is not None
    # Cancelado ⇒ ya no hay ventana de corrección.
    vision = FakeVision()
    assert await maybe_apply_correction(db_session, u, "549110", "es en york", TODAY,
                                        vision_client=vision) is None
    assert vision.correction_calls == 0
