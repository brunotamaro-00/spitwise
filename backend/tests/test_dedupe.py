from app.whatsapp.dedupe import claim_wamid


async def test_claim_is_idempotent(db_session):
    assert await claim_wamid(db_session, "wamid.1") is True
    assert await claim_wamid(db_session, "wamid.1") is False
    assert await claim_wamid(db_session, "wamid.2") is True
