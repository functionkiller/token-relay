from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError
from sqlalchemy import select

from app.database import async_session
from app.models.user import User
from app.security.jwt import decode_token

router = APIRouter(tags=["user_ui"])
templates = Jinja2Templates(directory="app/templates")


async def _get_user_from_cookie(request: Request):
    token = request.cookies.get("token")
    if not token:
        return None
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        async with async_session() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            return user if (user and user.is_active) else None
    except (JWTError, Exception):
        return None


def _require_auth(request: Request):
    return templates.TemplateResponse(request, "user/login.html", {"request": request})


@router.get("/login", response_class=HTMLResponse)
async def user_login(request: Request):
    user = await _get_user_from_cookie(request)
    if user:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse(request, "user/login.html", {"request": request})


@router.get("/register", response_class=HTMLResponse)
async def user_register(request: Request):
    return templates.TemplateResponse(request, "user/register.html", {"request": request})


@router.get("/dashboard", response_class=HTMLResponse)
async def user_dashboard(request: Request):
    user = await _get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request, "user/dashboard.html", {"request": request, "user": user})


@router.get("/dashboard/models", response_class=HTMLResponse)
async def user_models(request: Request):
    user = await _get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request, "user/models.html", {"request": request, "user": user})


@router.get("/dashboard/keys", response_class=HTMLResponse)
async def user_keys(request: Request):
    user = await _get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request, "user/keys.html", {"request": request, "user": user})


@router.get("/dashboard/usage", response_class=HTMLResponse)
async def user_usage(request: Request):
    user = await _get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request, "user/usage.html", {"request": request, "user": user})


@router.get("/dashboard/billing", response_class=HTMLResponse)
async def user_billing(request: Request):
    user = await _get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request, "user/billing.html", {"request": request, "user": user})


@router.get("/dashboard/settings", response_class=HTMLResponse)
async def user_settings(request: Request):
    user = await _get_user_from_cookie(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request, "user/settings.html", {"request": request, "user": user})
