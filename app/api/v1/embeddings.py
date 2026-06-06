import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.registry import AdapterRegistry
from app.api.deps import get_user_from_api_key
from app.database import get_db
from app.models.model_config import ModelConfig
from app.models.provider_key import ProviderKey
from app.security.encryption import decrypt

router = APIRouter()


@router.post("/embeddings")
async def embeddings(
    request: Request,
    _=Depends(get_user_from_api_key),
    db: AsyncSession = Depends(get_db),
):
    try:
        body = await request.json()
    except Exception:
        return StreamingResponse(
            iter([json.dumps({"error": {"message": "Invalid JSON", "type": "invalid_request_error", "code": "invalid_request"}}).encode()]),
            media_type="application/json", status_code=400,
        )

    model_id = body.get("model", "")
    result = await db.execute(
        select(ModelConfig).where(ModelConfig.model_id == model_id, ModelConfig.is_enabled == True)
    )
    mc = result.scalar_one_or_none()
    if mc is None:
        return StreamingResponse(
            iter([json.dumps({"error": {"message": f"Model '{model_id}' not found", "type": "invalid_request_error", "code": "model_not_found"}}).encode()]),
            media_type="application/json", status_code=404,
        )

    result = await db.execute(
        select(ProviderKey)
        .where(ProviderKey.provider == mc.provider, ProviderKey.is_active == True)
        .order_by(ProviderKey.priority)
    )
    pk = result.scalars().first()
    if pk is None:
        return StreamingResponse(
            iter([json.dumps({"error": {"message": "No provider key available", "type": "api_error", "code": "upstream_error"}}).encode()]),
            media_type="application/json", status_code=502,
        )

    AdapterRegistry.register_provider_key(pk.provider, pk.base_url, pk.proxy_url)
    adapter = AdapterRegistry.get(mc.provider)
    api_key = decrypt(pk.encrypted_key)

    try:
        resp = await adapter.embeddings(body, api_key)
        return resp
    except Exception as e:
        return StreamingResponse(
            iter([json.dumps({"error": {"message": str(e), "type": "api_error", "code": "upstream_error"}}).encode()]),
            media_type="application/json", status_code=502,
        )
