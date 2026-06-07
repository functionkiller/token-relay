import json
import math
import time
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.registry import AdapterRegistry
from app.api.deps import get_user_from_api_key
from app.database import get_db
from app.logging_config import logger
from app.models.model_config import ModelConfig
from app.schemas.proxy import EmbeddingRequest
from app.models.provider_key import ProviderKey
from app.models.system_setting import SystemSetting
from app.models.transaction import CreditTransaction, TransactionType
from app.models.usage_log import UsageLog, UsageStatus
from app.models.user import User
from app.security.encryption import decrypt
from app.security.rate_limiter import add_rate_limit_headers, check_rate_limit

router = APIRouter()

DEFAULT_EMBEDDING_COST_PRICES: dict[str, int] = {
    "text-embedding-v1": 0.5,
    "text-embedding-v2": 1,
    "text-embedding-v3": 2,
}


def _estimate_tokens(texts: list[str]) -> int:
    """Rough token count: ~4 chars per token for Chinese, ~4 chars for English."""
    total_chars = sum(len(t) for t in texts)
    return max(1, math.ceil(total_chars / 4))


def _calculate_embedding_cost(tokens: int, price_per_1k: int) -> int:
    return math.ceil(tokens / 1000 * price_per_1k)


def _parse_embedding_usage(body: dict) -> int:
    usage = body.get("usage", {})
    return usage.get("total_tokens", 0)


async def _resolve_embedding_price(db: AsyncSession, model_id: str) -> tuple[int, ModelConfig]:
    result = await db.execute(
        select(ModelConfig).where(ModelConfig.model_id == model_id, ModelConfig.is_enabled == True)
    )
    mc = result.scalar_one_or_none()
    if mc is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")

    # Use input_price as embedding price if set, otherwise use defaults + markup
    if mc.input_price is not None:
        return mc.input_price, mc

    result = await db.execute(select(SystemSetting).where(SystemSetting.key == "markup_percent"))
    setting = result.scalar_one_or_none()
    markup = float(setting.value) if setting else 15.0

    cp = DEFAULT_EMBEDDING_COST_PRICES.get(model_id, 1)
    price = math.ceil(cp * (1 + markup / 100))
    return price, mc


@router.post("/embeddings")
async def embeddings(
    request: Request,
    user=Depends(get_user_from_api_key),
    db: AsyncSession = Depends(get_db),
):
    # Rate limit
    rate_result = await check_rate_limit(user.id)
    if not rate_result.allowed:
        resp = JSONResponse(
            {"error": {"message": f"Rate limit exceeded. Retry after {rate_result.reset_seconds}s", "type": "rate_limit_exceeded", "code": "rate_limit_exceeded"}},
            status_code=429,
        )
        add_rate_limit_headers(resp, rate_result)
        return resp

    # Parse body
    try:
        raw_body = await request.json()
        body = EmbeddingRequest.model_validate(raw_body).model_dump()
    except Exception as e:
        logger.warning("embedding_validation_failed", extra={"error": str(e)[:200]})
        return JSONResponse(
            {"error": {"message": f"Invalid request: {e}", "type": "invalid_request_error", "code": "invalid_request"}},
            status_code=400,
        )

    model_id = body["model"]

    try:
        price_per_1k, mc = await _resolve_embedding_price(db, model_id)
    except Exception as e:
        return JSONResponse(
            {"error": {"message": str(e.detail) if hasattr(e, 'detail') else str(e), "type": "invalid_request_error", "code": "model_not_found"}},
            status_code=404,
        )

    # Resolve provider key
    result = await db.execute(
        select(ProviderKey)
        .where(ProviderKey.provider == mc.provider, ProviderKey.is_active == True)
        .order_by(ProviderKey.priority)
    )
    pk = result.scalars().first()
    if pk is None:
        return JSONResponse(
            {"error": {"message": "No provider key available", "type": "api_error", "code": "upstream_error"}},
            status_code=502,
        )

    # Estimate cost from input
    input_texts = body.get("input", [])
    if isinstance(input_texts, str):
        input_texts = [input_texts]
    estimated_tokens = _estimate_tokens(input_texts)
    estimated_cost = _calculate_embedding_cost(estimated_tokens, price_per_1k)

    # Atomic credit hold
    result = await db.execute(
        update(User)
        .where(User.id == user.id, User.credit_balance >= estimated_cost)
        .values(credit_balance=User.credit_balance - estimated_cost)
        .returning(User.credit_balance)
    )
    new_balance = result.scalar_one_or_none()
    if new_balance is None:
        return JSONResponse(
            {"error": {"message": "Insufficient credits", "type": "insufficient_funds", "code": "insufficient_funds"}},
            status_code=402,
        )

    db.add(CreditTransaction(
        user_id=user.id,
        amount=-estimated_cost,
        balance_after=new_balance,
        type=TransactionType.CONSUMPTION,
        note=f"Pre-auth: embeddings {model_id}",
    ))
    await db.flush()

    # Call upstream
    request_id = str(uuid.uuid4())
    start_time = time.time()

    AdapterRegistry.register_provider_key(pk.provider, pk.base_url, pk.proxy_url)
    adapter = AdapterRegistry.get(mc.provider)
    api_key = decrypt(pk.encrypted_key)

    try:
        resp = await adapter.embeddings(body, api_key)
        response_status = UsageStatus.SUCCESS
        error_message = None
    except Exception as e:
        # Refund pre-auth on failure
        result = await db.execute(
            update(User)
            .where(User.id == user.id)
            .values(credit_balance=User.credit_balance + estimated_cost)
            .returning(User.credit_balance)
        )
        refunded_balance = result.scalar_one()
        db.add(CreditTransaction(
            user_id=user.id,
            amount=estimated_cost,
            balance_after=refunded_balance,
            type=TransactionType.REFUND,
            note=f"Refund: embeddings failed - {str(e)[:100]}",
        ))

        db.add(UsageLog(
            user_id=user.id,
            api_key_id="",  # will be populated from context
            provider=mc.provider,
            model=model_id,
            request_id=request_id,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            credits_consumed=0,
            streaming=False,
            latency_ms=int((time.time() - start_time) * 1000),
            status=UsageStatus.ERROR,
            error_message=str(e)[:500],
        ))
        await db.flush()

        return JSONResponse(
            {"error": {"message": str(e), "type": "api_error", "code": "upstream_error"}},
            status_code=502,
        )

    # Parse actual usage
    latency_ms = int((time.time() - start_time) * 1000)
    actual_tokens = _parse_embedding_usage(resp)
    actual_cost = _calculate_embedding_cost(actual_tokens, price_per_1k) if actual_tokens > 0 else estimated_cost

    # Settle delta
    delta = estimated_cost - actual_cost
    if delta > 0:
        result = await db.execute(
            update(User)
            .where(User.id == user.id)
            .values(credit_balance=User.credit_balance + delta)
            .returning(User.credit_balance)
        )
        refunded_balance = result.scalar_one()
        db.add(CreditTransaction(
            user_id=user.id,
            amount=delta,
            balance_after=refunded_balance,
            type=TransactionType.REFUND,
            reference_id=request_id,
            note=f"Refund: embeddings est={estimated_cost} actual={actual_cost}",
        ))

    # Log
    db.add(UsageLog(
        user_id=user.id,
        api_key_id="",
        provider=mc.provider,
        model=model_id,
        request_id=request_id,
        prompt_tokens=actual_tokens,
        completion_tokens=0,
        total_tokens=actual_tokens,
        credits_consumed=actual_cost,
        streaming=False,
        latency_ms=latency_ms,
        status=response_status,
        error_message=error_message,
    ))
    await db.flush()

    return resp
