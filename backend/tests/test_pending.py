from datetime import datetime, timedelta, timezone

from app.bot.pending import close_pending, create_pending, load_pending


async def test_pending_expires(db_session):
    token = await create_pending(db_session, owner="bruno", payload={"x": 1}, kind="cat_pick")
    from sqlalchemy import select
    from app.db.models import BotPendingAction
    row = (await db_session.execute(
        select(BotPendingAction).where(BotPendingAction.token == token)
    )).scalar_one()
    row.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    await db_session.commit()
    assert await load_pending(db_session, token, owner="bruno") is None


async def test_pending_rejects_wrong_owner(db_session):
    token = await create_pending(db_session, owner="bruno", payload={"x": 1}, kind="qa_del")
    assert await load_pending(db_session, token, owner="katia") is None
    assert await load_pending(db_session, token, owner="bruno") is not None
    await close_pending(db_session, token)
    assert await load_pending(db_session, token, owner="bruno") is None
