import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_user_from_api_key
from app.database import get_db
from app.logging_config import logger
from app.models.user import User
from app.schemas.proxy import ChatCompletionRequest
from app.security.rate_limiter import add_rate_limit_headers, check_rate_limit
from app.services.proxy_service import chat_completion_proxy

router = APIRouter()


def _error_response(message: str, code: str, status_code: int = 400):
    resp = JSONResponse(
        content={"error": {"message": message, "type": "api_error", "code": code}},
        status_code=status_code,
    )
    return resp


@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    user: User = Depends(get_user_from_api_key),
    db: AsyncSession = Depends(get_db),
):
    rate_result = await check_rate_limit(user.id)
    if not rate_result.allowed:
        return _error_response(
            f"Rate limit exceeded. Retry after {rate_result.reset_seconds}s",
            "rate_limit_exceeded", 429,
        )

    try:
        raw_body = await request.json()
        body = ChatCompletionRequest.model_validate(raw_body).model_dump()
    except Exception as e:
        logger.warning("chat_validation_failed", extra={"error": str(e)[:200]})
        return _error_response(f"Invalid request: {e}", "invalid_request_error", 400)

    model_id = body["model"]
    stream = body.get("stream", False)

    if not stream:
        # Non-streaming: collect the full response, return proper HTTP status
        try:
            chunks = []
            async for chunk in chat_completion_proxy(
                db=db, user_id=user.id, api_key_id=user.id,
                model_id=model_id, body=body, stream=False,
            ):
                chunks.append(chunk)
            full_body = b"".join(chunks)
            # Check if it's an error from our proxy
            try:
                data = json.loads(full_body)
                if "error" in data:
                    err = data["error"]
                    err_code = err.get("code", "internal_error")
                    if err_code == "model_not_found":
                        return JSONResponse(content=data, status_code=404)
                    elif err_code == "insufficient_credits":
                        return JSONResponse(content=data, status_code=402)
                    return JSONResponse(content=data, status_code=502)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
            return JSONResponse(content=json.loads(full_body))
        except Exception as e:
            detail = str(e)
            logger.error("chat_completion_error", extra={"detail": detail[:200]})
            if "not found" in detail.lower():
                return _error_response(detail, "model_not_found", 404)
            if "Insufficient credits" in detail.lower() or "insufficient" in detail.lower():
                return _error_response(detail, "insufficient_credits", 402)
            return _error_response(detail, "internal_error", 500)
    else:
        # Streaming: errors go in the SSE stream
        async def generate():
            try:
                async for chunk in chat_completion_proxy(
                    db=db, user_id=user.id, api_key_id=user.id,
                    model_id=model_id, body=body, stream=True,
                ):
                    yield chunk
            except Exception as e:
                logger.error("stream_error", extra={"detail": str(e)[:200]})
                error_body = json.dumps({
                    "error": {"message": str(e), "type": "api_error", "code": "internal_error"}
                })
                yield f"data: {error_body}\n\n".encode()

        return StreamingResponse(generate(), media_type="text/event-stream")
