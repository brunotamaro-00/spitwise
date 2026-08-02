from datetime import datetime, timedelta

from sqlalchemy import select

from app.db.models import WhatsAppDedupe
from app.whatsapp.dedupe import _IN_FLIGHT_GRACE, claim_wamid, mark_processed


async def _row(db_session, wamid: str) -> WhatsAppDedupe:
    return (await db_session.execute(
        select(WhatsAppDedupe).where(WhatsAppDedupe.wamid == wamid)
    )).scalar_one()


async def test_claim_is_idempotent(db_session):
    assert await claim_wamid(db_session, "wamid.1") is True
    assert await claim_wamid(db_session, "wamid.1") is False
    assert await claim_wamid(db_session, "wamid.2") is True


async def test_in_flight_claim_is_not_stolen(db_session):
    """Reintento de Meta mientras el primero todavía procesa: se descarta."""
    assert await claim_wamid(db_session, "wamid.1") is True
    assert await claim_wamid(db_session, "wamid.1") is False


async def test_processed_never_reprocesses(db_session):
    assert await claim_wamid(db_session, "wamid.1") is True
    await mark_processed(db_session, "wamid.1")
    assert (await _row(db_session, "wamid.1")).processed_at is not None

    # Ni recién terminado ni mucho después: procesado es para siempre.
    assert await claim_wamid(db_session, "wamid.1") is False
    row = await _row(db_session, "wamid.1")
    row.created_at = datetime.utcnow() - timedelta(days=1)
    await db_session.commit()
    assert await claim_wamid(db_session, "wamid.1") is False


async def test_stale_unprocessed_claim_is_recovered(db_session):
    """El proceso murió a mitad: la fila quedó sin `processed_at`. Pasada la
    ventana de gracia, el reintento de Meta vuelve a agarrar el mensaje en vez
    de descartarlo (que era perderlo en silencio)."""
    assert await claim_wamid(db_session, "wamid.1") is True
    row = await _row(db_session, "wamid.1")
    row.created_at = datetime.utcnow() - _IN_FLIGHT_GRACE - timedelta(minutes=1)
    await db_session.commit()

    assert await claim_wamid(db_session, "wamid.1") is True
    # El re-claim reinicia la ventana: un tercer intento inmediato no duplica.
    assert await claim_wamid(db_session, "wamid.1") is False
