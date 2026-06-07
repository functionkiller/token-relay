import json
import math
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import AdapterRequest
from app.adapters.registry import AdapterRegistry
from app.logging_config import logger
from app.models.model_config import ModelConfig
from app.models.provider_key import ProviderKey
from app.models.system_setting import SystemSetting
from app.models.transaction import CreditTransaction, TransactionType
from app.models.usage_log import UsageLog, UsageStatus
from app.models.user import User
from app.security.encryption import decrypt

# Default cost prices in cents per 1K tokens (input, output)
DEFAULT_COST_PRICES: dict[str, tuple[int, int]] = {
    "qwen-turbo": (1, 2),
    "qwen-plus": (2, 6),
    "qwen-max": (10, 30),
    "deepseek-chat": (0.5, 2),
    "deepseek-reasoner": (1, 4),
    "glm-4-flash": (0.5, 1),
    "glm-4": (5, 5),
    "glm-4v": (10, 10),
}


def _calculate_cost(prompt_tokens: int, completion_tokens: int, input_price: int, output_price: int) -> int:
    return math.ceil(prompt_tokens / 1000 * input_price + completion_tokens / 1000 * output_price)


def _parse_usage(body_bytes: bytes) -> tuple[int, int]:
    try:
        data = json.loads(body_bytes)
        usage = data.get("usage", {})
        return usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
    except Exception:
        return 0, 0


def _parse_stream_usage(chunks: list[bytes]) -> tuple[int, int]:
    last = None
    for chunk in chunks:
        text = chunk.decode("utf-8", errors="replace")
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("data: ") and line[6:] != "[DONE]":
                try:
                    d = json.loads(line[6:])
                    if d.get("usage"):
                        last = d["usage"]
                except json.JSONDecodeError:
                    pass
    if last:
        return last.get("prompt_tokens", 0), last.get("completion_tokens", 0)
    return 0, 0


async def get_enabled_models(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(ModelConfig).where(ModelConfig.is_enabled == True))
    return [
        {"id": m.model_id, "object": "model", "created": int(m.created_at.timestamp()), "owned_by": m.provider}
        for m in result.scalars().all()
    ]


async def _resolve_prices(db: AsyncSession, model_id: str) -> tuple[int, int, ModelConfig]:
    result = await db.execute(
        select(ModelConfig).where(ModelConfig.model_id == model_id, ModelConfig.is_enabled == True)
    )
    mc = result.scalar_one_or_none()
    if mc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Model '{model_id}' not found or disabled")

    if mc.input_price is not None and mc.output_price is not None:
        return mc.input_price, mc.output_price, mc

    result = await db.execute(select(SystemSetting).where(SystemSetting.key == "markup_percent"))
    setting = result.scalar_one_or_none()
    markup = float(setting.value) if setting else 15.0

    cp_input, cp_output = DEFAULT_COST_PRICES.get(model_id, (2, 6))
    in_price = math.ceil(cp_input * (1 + markup / 100))
    out_price = math.ceil(cp_output * (1 + markup / 100))
    return in_price, out_price, mc


async def _get_active_provider_keys(db: AsyncSession, provider: str) -> list[ProviderKey]:
    result = await db.execute(
        select(ProviderKey)
        .where(ProviderKey.provider == provider, ProviderKey.is_active == True)
        .order_by(ProviderKey.priority)
    )
    return list(result.scalars().all())


async def chat_completion_proxy(
    db: AsyncSession,
    user_id: str,
    api_key_id: str,
    model_id: str,
    body: dict,
    stream: bool,
) -> AsyncIterator[bytes]:
    request_id = str(uuid.uuid4())
    start_time = time.time()

    # 1. Resolve pricing and model
    input_price, output_price, mc = await _resolve_prices(db, model_id)
    provider = mc.provider

    # 2. Get active provider keys
    provider_keys = await _get_active_provider_keys(db, provider)
    for pk in provider_keys:
        AdapterRegistry.register_provider_key(pk.provider, pk.base_url, pk.proxy_url)

    # 3. Pre-authorize: estimate cost
    # Estimate input tokens from message content (rough: ~4 chars/token)
    messages = body.get("messages", [])
    input_chars = sum(len(str(m.get("content", ""))) for m in messages if isinstance(m, dict))
    estimated_input_tokens = max(1, math.ceil(input_chars / 4))
    max_tokens = body.get("max_tokens", 1024)
    estimated_cost = _calculate_cost(estimated_input_tokens, max_tokens, input_price, output_price)

    # Atomic check and deduct
    result = await db.execute(
        update(User)
        .where(User.id == user_id, User.credit_balance >= estimated_cost)
        .values(credit_balance=User.credit_balance - estimated_cost)
        .returning(User.credit_balance)
    )
    new_balance = result.scalar_one_or_none()
    if new_balance is None:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient credits")

    txn = CreditTransaction(
        user_id=user_id,
        amount=-estimated_cost,
        balance_after=new_balance,
        type=TransactionType.CONSUMPTION,
        note=f"Pre-auth: {model_id}",
    )
    db.add(txn)
    await db.flush()

    # 4. Call upstream with key rotation
    collected_chunks: list[bytes] = []
    response_status = UsageStatus.SUCCESS
    error_message = None

    for pk in provider_keys:
        api_key = decrypt(pk.encrypted_key)
        AdapterRegistry.register_provider_key(pk.provider, pk.base_url, pk.proxy_url)
        adapter = AdapterRegistry.get(provider)

        adapter_request = AdapterRequest(
            model=model_id,
            messages=body.get("messages", []),
            stream=stream,
            max_tokens=max_tokens,
            temperature=body.get("temperature"),
            top_p=body.get("top_p"),
            body=body,
        )

        try:
            async for chunk in adapter.chat_completion(adapter_request, api_key):
                collected_chunks.append(chunk)
                yield chunk
            break
        except Exception as e:
            logger.warning("upstream_key_failed", extra={"provider": provider, "model": model_id, "error": str(e)[:200]})
            error_message = str(e)
            collected_chunks.clear()
            continue
    else:
        logger.error("all_upstream_keys_failed", extra={"provider": provider, "model": model_id, "keys_tried": len(provider_keys)})
        response_status = UsageStatus.ERROR
        collected_chunks.clear()
        error_body = json.dumps({
            "error": {
                "message": f"Upstream error: {error_message}",
                "type": "api_error",
                "code": "upstream_error",
            }
        }).encode()
        collected_chunks.append(error_body)
        yield error_body

    # 5. Parse usage
    latency_ms = int((time.time() - start_time) * 1000)
    if stream:
        prompt_tokens, completion_tokens = _parse_stream_usage(collected_chunks)
    else:
        body_data = b"".join(collected_chunks)
        prompt_tokens, completion_tokens = _parse_usage(body_data)

    # 6. Settle cost delta
    actual_cost = _calculate_cost(prompt_tokens, completion_tokens, input_price, output_price)
    delta = estimated_cost - actual_cost
    if delta > 0:
        result = await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(credit_balance=User.credit_balance + delta)
            .returning(User.credit_balance)
        )
        refunded_balance = result.scalar_one()
        db.add(CreditTransaction(
            user_id=user_id,
            amount=delta,
            balance_after=refunded_balance,
            type=TransactionType.REFUND,
            reference_id=request_id,
            note=f"Refund: estimated={estimated_cost} actual={actual_cost}",
        ))

    # 7. Log
    db.add(UsageLog(
        user_id=user_id,
        api_key_id=api_key_id,
        provider=provider,
        model=model_id,
        request_id=request_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        credits_consumed=actual_cost,
        streaming=stream,
        latency_ms=latency_ms,
        status=response_status,
        error_message=error_message,
    ))
    await db.flush()
