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


async def test_pending_rejects_wrong_kind(db_session):
    """El kind es el tipo que el HANDLER espera: un token de otra clase no puede
    llegar con un payload que el handler va a leer como si fuera suyo."""
    token = await create_pending(db_session, owner="bruno", payload={"x": 1}, kind="doc_upload")
    assert await load_pending(db_session, token, kind="del_confirm") is None
    assert await load_pending(db_session, token, kind="doc_upload") == {"x": 1}
    # Sin `kind` sigue cargando (los callers que no lo declaran no cambian).
    assert await load_pending(db_session, token) == {"x": 1}


async def test_create_pending_accepts_a_pregenerated_token(db_session):
    """Pendings hermanos: cada payload necesita el token del otro antes de que
    existan las filas."""
    from app.bot.pending import new_token

    t_a, t_b = new_token(), new_token()
    await create_pending(db_session, owner="bruno", payload={"siblings": [t_b]},
                         kind="del_confirm", token=t_a)
    await create_pending(db_session, owner="bruno", payload={"siblings": [t_a]},
                         kind="del_confirm", token=t_b)
    assert (await load_pending(db_session, t_a))["siblings"] == [t_b]
    assert (await load_pending(db_session, t_b))["siblings"] == [t_a]


async def test_purge_closed_only_takes_the_old_ones(db_session):
    from sqlalchemy import func, select

    from app.bot.pending import purge_closed
    from app.db.models import BotPendingAction

    fresh = await create_pending(db_session, owner="bruno", payload={"x": 1}, kind="cat_pick")
    old = await create_pending(db_session, owner="bruno", payload={"x": 2}, kind="cat_pick")
    row = (await db_session.execute(
        select(BotPendingAction).where(BotPendingAction.token == old)
    )).scalar_one()
    row.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=49)
    await db_session.commit()

    assert await purge_closed(db_session) == 1
    left = (await db_session.execute(select(BotPendingAction.token))).scalars().all()
    assert left == [fresh]
