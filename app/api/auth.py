from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.logging_config import logger
from app.schemas.auth import LoginRequest, RefreshRequest, RefreshResponse, RegisterRequest, TokenResponse
from app.schemas.user import UserOut
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_service.register(db, req.email, req.password)
    return user


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    tokens = await auth_service.login(db, req.email, req.password)
    resp = JSONResponse(content=tokens)
    resp.set_cookie(
        key="token",
        value=tokens["access_token"],
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        samesite="lax",
        secure=not settings.DEBUG,
    )
    return resp


@router.post("/login-form")
async def login_form(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        tokens = await auth_service.login(db, email, password)
    except Exception as e:
        logger.warning("login_form_failed", extra={"email": email, "error": str(e)})
        return RedirectResponse(url="/login?error=invalid", status_code=302)

    resp = RedirectResponse(url="/dashboard", status_code=302)
    resp.set_cookie(
        key="token",
        value=tokens["access_token"],
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        samesite="lax",
        secure=not settings.DEBUG,
    )
    return resp


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(req: RefreshRequest):
    return await auth_service.refresh_token(req.refresh_token)
