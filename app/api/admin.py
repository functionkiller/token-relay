from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.database import get_db
from app.schemas.admin import (
    AdminUserUpdate, CreditAdjust, DashboardStats, ModelConfigCreate, ModelConfigOut,
    ModelConfigUpdate, ProviderKeyCreate, ProviderKeyOut, SettingUpdate,
)
from app.schemas.common import PaginatedResponse, SystemSettingOut
from app.schemas.user import UserOut
from app.services import admin_service, analytics_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


# Settings
@router.get("/settings/{key}", response_model=SystemSettingOut)
async def get_setting(key: str, _=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    setting = await admin_service.get_setting(db, key)
    return setting if setting else {"key": key, "value": "", "updated_at": None}


@router.patch("/settings/{key}", response_model=SystemSettingOut)
async def update_setting(key: str, req: SettingUpdate, _=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return await admin_service.set_setting(db, key, req.value)


# Users
@router.get("/users", response_model=PaginatedResponse)
async def list_users(
    search: str | None = None,
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    _=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    items, total = await admin_service.list_users(db, search, is_active, page, size)
    return PaginatedResponse(
        items=[UserOut.model_validate(u) for u in items],
        total=total, page=page, size=size,
        pages=(total + size - 1) // size if total > 0 else 1,
    )


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: str, req: AdminUserUpdate, _=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return await admin_service.update_user_admin(db, user_id, req.model_dump(exclude_none=True))


@router.post("/users/{user_id}/credits", response_model=UserOut)
async def add_credits(user_id: str, req: CreditAdjust, _=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return await admin_service.add_credits(db, user_id, req.amount, req.note)


# Provider Keys
@router.get("/provider-keys", response_model=list[ProviderKeyOut])
async def list_provider_keys(_=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    keys = await admin_service.list_provider_keys(db)
    return [
        ProviderKeyOut(
            id=k.id, provider=k.provider, label=k.label,
            key_preview=f"{k.encrypted_key[:4]}...{k.encrypted_key[-4:]}",
            base_url=k.base_url, proxy_url=k.proxy_url,
            is_active=k.is_active, priority=k.priority, created_at=k.created_at,
        )
        for k in keys
    ]


@router.post("/provider-keys", response_model=ProviderKeyOut, status_code=201)
async def create_provider_key(req: ProviderKeyCreate, _=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    k = await admin_service.create_provider_key(db, req.model_dump())
    return ProviderKeyOut(
        id=k.id, provider=k.provider, label=k.label,
        key_preview=f"{k.encrypted_key[:4]}...{k.encrypted_key[-4:]}",
        base_url=k.base_url, proxy_url=k.proxy_url,
        is_active=k.is_active, priority=k.priority, created_at=k.created_at,
    )


@router.delete("/provider-keys/{key_id}", status_code=204)
async def delete_provider_key(key_id: str, _=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    await admin_service.delete_provider_key(db, key_id)


# Models
@router.get("/models", response_model=list[ModelConfigOut])
async def list_models(_=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return [ModelConfigOut.model_validate(m) for m in await admin_service.list_model_configs(db)]


@router.post("/models", response_model=ModelConfigOut, status_code=201)
async def create_model(req: ModelConfigCreate, _=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return ModelConfigOut.model_validate(await admin_service.create_model_config(db, req.model_dump()))


@router.patch("/models/{model_id}", response_model=ModelConfigOut)
async def update_model(model_id: str, req: ModelConfigUpdate, _=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return ModelConfigOut.model_validate(
        await admin_service.update_model_config(db, model_id, req.model_dump(exclude_none=True))
    )


# Stats
@router.get("/stats/dashboard", response_model=DashboardStats)
async def dashboard(_=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    return await analytics_service.get_dashboard_stats(db)


# Usage logs (admin)
@router.get("/logs")
async def admin_logs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    model: str | None = None,
    status: str | None = None,
    _=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    items, total = await analytics_service.get_admin_usage(db, page, size, search, model, status)
    return {"items": items, "total": total, "page": page, "size": size,
            "pages": (total + size - 1) // size if total > 0 else 1}
