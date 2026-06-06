from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import CreditTransaction
from app.models.user import User


async def get_balance(user: User) -> dict:
    return {
        "credit_balance": user.credit_balance,
        "formatted": f"{user.credit_balance / 100:.2f} credits",
    }


async def get_transactions(
    db: AsyncSession, user_id: str, page: int = 1, size: int = 20, txn_type: str | None = None
) -> tuple[list[CreditTransaction], int]:
    query = select(CreditTransaction).where(CreditTransaction.user_id == user_id)
    count_query = select(func.count(CreditTransaction.id)).where(CreditTransaction.user_id == user_id)
    if txn_type:
        query = query.where(CreditTransaction.type == txn_type)
        count_query = count_query.where(CreditTransaction.type == txn_type)

    total = (await db.execute(count_query)).scalar()
    items = (await db.execute(
        query.order_by(desc(CreditTransaction.created_at)).offset((page - 1) * size).limit(size)
    )).scalars().all()
    return list(items), total
