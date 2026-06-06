from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage_log import UsageLog
from app.models.user import User


async def get_user_usage(
    db: AsyncSession, user_id: str, page: int = 1, size: int = 20,
    from_date: str | None = None, to_date: str | None = None,
    model: str | None = None,
) -> tuple[list[UsageLog], int]:
    query = select(UsageLog).where(UsageLog.user_id == user_id)
    count_q = select(func.count(UsageLog.id)).where(UsageLog.user_id == user_id)

    if from_date:
        query = query.where(UsageLog.created_at >= from_date)
        count_q = count_q.where(UsageLog.created_at >= from_date)
    if to_date:
        query = query.where(UsageLog.created_at <= to_date)
        count_q = count_q.where(UsageLog.created_at <= to_date)
    if model:
        query = query.where(UsageLog.model == model)
        count_q = count_q.where(UsageLog.model == model)

    total = (await db.execute(count_q)).scalar()
    items = (await db.execute(
        query.order_by(desc(UsageLog.created_at)).offset((page - 1) * size).limit(size)
    )).scalars().all()
    return list(items), total


async def get_user_stats(
    db: AsyncSession, user_id: str,
    from_date: str | None = None, to_date: str | None = None,
) -> dict:
    query = select(
        func.count(UsageLog.id).label("total_requests"),
        func.sum(UsageLog.total_tokens).label("total_tokens"),
        func.sum(UsageLog.credits_consumed).label("total_credits"),
    ).where(UsageLog.user_id == user_id)
    if from_date:
        query = query.where(UsageLog.created_at >= from_date)
    if to_date:
        query = query.where(UsageLog.created_at <= to_date)
    result = (await db.execute(query)).one()
    return {
        "total_requests": result.total_requests or 0,
        "total_tokens": result.total_tokens or 0,
        "total_credits": result.total_credits or 0,
    }


async def get_dashboard_stats(db: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_users = (await db.execute(select(func.count(User.id)))).scalar()
    active_today = (await db.execute(
        select(func.count(func.distinct(UsageLog.user_id)))
        .where(UsageLog.created_at >= today_start)
    )).scalar()

    requests_today = (await db.execute(
        select(func.count(UsageLog.id))
        .where(UsageLog.created_at >= today_start)
    )).scalar()

    revenue_today = (await db.execute(
        select(func.sum(UsageLog.credits_consumed))
        .where(UsageLog.created_at >= today_start)
    )).scalar() or 0

    revenue_month = (await db.execute(
        select(func.sum(UsageLog.credits_consumed))
        .where(UsageLog.created_at >= month_start)
    )).scalar() or 0

    top_models_result = (await db.execute(
        select(UsageLog.model, func.count(UsageLog.id).label("requests"), func.sum(UsageLog.credits_consumed).label("revenue"))
        .where(UsageLog.created_at >= today_start)
        .group_by(UsageLog.model)
        .order_by(desc("requests"))
        .limit(5)
    )).all()

    top_models = [
        {"model": r.model, "requests": r.requests, "revenue": r.revenue}
        for r in top_models_result
    ]

    return {
        "total_users": total_users,
        "active_users_today": active_today,
        "total_requests_today": requests_today,
        "revenue_today_cents": revenue_today,
        "revenue_this_month_cents": revenue_month,
        "top_models": top_models,
    }
