from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_user_from_api_key
from app.database import get_db
from app.schemas.proxy import ModelListResponse
from app.services.proxy_service import get_enabled_models

from app.api.deps import get_current_user

router = APIRouter()


@router.get("/public-models")
async def public_models(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List models for logged-in users (cookie auth)."""
    models = await get_enabled_models(db)
    # Also include pricing from model_configs
    from app.models.model_config import ModelConfig
    from sqlalchemy import select as sa_select
    result = await db.execute(sa_select(ModelConfig).where(ModelConfig.is_enabled == True))
    configs = {m.model_id: m for m in result.scalars().all()}
    enriched = []
    for m in models:
        cfg = configs.get(m["id"])
        enriched.append({
            "id": m["id"],
            "provider": m.get("owned_by", ""),
            "display_name": cfg.display_name if cfg else m["id"],
            "input_price": cfg.input_price if cfg else None,
            "output_price": cfg.output_price if cfg else None,
            "supports_streaming": cfg.supports_streaming if cfg else True,
            "supports_vision": cfg.supports_vision if cfg else False,
        })
    return enriched


@router.get("/models", response_model=ModelListResponse)
async def list_models(
    _=Depends(get_user_from_api_key),
    db: AsyncSession = Depends(get_db),
):
    models = await get_enabled_models(db)
    return ModelListResponse(data=models)
