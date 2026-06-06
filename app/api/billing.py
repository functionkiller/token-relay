from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.billing import BalanceOut, TransactionOut
from app.schemas.common import PaginatedResponse
from app.services import billing_service

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/balance", response_model=BalanceOut)
async def get_balance(user: User = Depends(get_current_user)):
    return await billing_service.get_balance(user)


@router.get("/transactions", response_model=PaginatedResponse)
async def list_transactions(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    type: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items, total = await billing_service.get_transactions(db, user.id, page, size, type)
    return PaginatedResponse(
        items=[TransactionOut.model_validate(i) for i in items],
        total=total, page=page, size=size,
        pages=(total + size - 1) // size if total > 0 else 1,
    )
