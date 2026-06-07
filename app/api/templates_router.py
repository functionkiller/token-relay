from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session
from app.models.user import User, UserRole
from app.security.jwt import decode_token
from app.services import admin_service, analytics_service

router = APIRouter(tags=["admin_ui"])
templates = Jinja2Templates(directory="app/templates")


async def get_admin_from_cookie(request: Request):
    token = request.cookies.get("token")
    if not token:
        return None
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        role = payload.get("role")
        if role != UserRole.ADMIN.value:
            return None
        async with async_session() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            return user if (user and user.is_active) else None
    except (JWTError, Exception):
        return None


@router.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return templates.TemplateResponse(request, "admin/login.html", {"request": request})


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_admin_from_cookie(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=302)
    stats = await analytics_service.get_dashboard_stats(db)
    return templates.TemplateResponse(request, "admin/dashboard.html", {"request": request, "stats": stats})


@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_admin_from_cookie(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=302)
    users, total = await admin_service.list_users(db)
    return templates.TemplateResponse(request, "admin/users.html", {"request": request, "users": users, "total": total})


@router.get("/admin/models", response_class=HTMLResponse)
async def admin_models_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_admin_from_cookie(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=302)
    models = await admin_service.list_model_configs(db)
    return templates.TemplateResponse(request, "admin/models.html", {"request": request, "models": models})


@router.get("/admin/keys", response_class=HTMLResponse)
async def admin_keys_page(request: Request, db: AsyncSession = Depends(get_db)):
    user = await get_admin_from_cookie(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=302)
    keys = await admin_service.list_provider_keys(db)
    return templates.TemplateResponse(request, "admin/keys.html", {"request": request, "keys": keys})


@router.get("/admin/logs", response_class=HTMLResponse)
async def admin_logs_page(request: Request):
    user = await get_admin_from_cookie(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=302)
    return templates.TemplateResponse(request, "admin/logs.html", {"request": request})


@router.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings_page(request: Request):
    user = await get_admin_from_cookie(request)
    if not user:
        return RedirectResponse(url="/admin/login", status_code=302)
    return templates.TemplateResponse(request, "admin/settings.html", {"request": request})
