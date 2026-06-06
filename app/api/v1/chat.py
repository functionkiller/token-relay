import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_user_from_api_key
from app.database import get_db
from app.models.user import User
from app.security.rate_limiter import check_rate_limit
from app.services.proxy_service import chat_completion_proxy

router = APIRouter()


def _error_response(message: str, code: str, status_code: int = 400):
    return JSONResponse(
        content={"error": {"message": message, "type": "api_error", "code": code}},
        status_code=status_code,
    )


@router.post("/chat/completions")
async def chat_completions(
    request: Request,
    user: User = Depends(get_user_from_api_key),
    db: AsyncSession = Depends(get_db),
):
    if not await check_rate_limit(user.id):
        return _error_response("Rate limit exceeded", "rate_limit_exceeded", 429)

    try:
        body = await request.json()
    except Exception:
        return _error_response("Invalid JSON body", "invalid_request_error", 400)

    model_id = body.get("model", "")
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
            if "not found" in detail.lower() or "not found" in detail.lower():
                return _error_response(detail, "model_not_found", 404)
            if "Insufficient credits" in detail:
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
                error_body = json.dumps({
                    "error": {"message": str(e), "type": "api_error", "code": "internal_error"}
                })
                yield f"data: {error_body}\n\n".encode()

        return StreamingResponse(generate(), media_type="text/event-stream")
