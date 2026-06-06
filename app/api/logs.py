from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.billing import UsageLogOut
from app.schemas.common import PaginatedResponse
from app.services import analytics_service

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/usage", response_model=PaginatedResponse)
async def get_usage(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    from_date: str | None = None,
    to_date: str | None = None,
    model: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items, total = await analytics_service.get_user_usage(
        db, user.id, page, size, from_date, to_date, model
    )
    return PaginatedResponse(
        items=[UsageLogOut.model_validate(i) for i in items],
        total=total, page=page, size=size,
        pages=(total + size - 1) // size if total > 0 else 1,
    )


@router.get("/stats")
async def get_stats(
    from_date: str | None = None,
    to_date: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await analytics_service.get_user_stats(db, user.id, from_date, to_date)
