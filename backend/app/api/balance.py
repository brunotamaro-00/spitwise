from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.api.schemas import BalanceOut
from app.balance import compute_balance
from app.db.engine import get_session
from app.db.models import Movement, User
from app.due import ensure_due_settled
from app.users import get_trip_users

router = APIRouter(tags=["balance"])


@router.get("/balance", response_model=BalanceOut)
async def get_balance(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> BalanceOut:
    await ensure_due_settled(session)
    a, b = await get_trip_users(session)
    rows = (await session.execute(select(Movement))).scalars().all()
    bal = compute_balance(rows, a.id, b.id)
    return BalanceOut(
        debtor_id=bal.debtor_id,
        creditor_id=bal.creditor_id,
        amount_usd=str(bal.amount_usd),
    )
