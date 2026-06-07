from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext
from sqlalchemy import select

from app.config import settings
from app.database import init_db, async_session
from app.logging_config import RequestLoggingMiddleware, setup_logging
from app.models.user import User, UserRole
from app.security.rate_limiter import rate_limiter

setup_logging(level="DEBUG" if settings.DEBUG else "INFO")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await _ensure_admin()
    rate_limiter.start_cleanup(interval=300)
    yield
    rate_limiter.stop_cleanup()


async def _ensure_admin():
    async with async_session() as db:
        result = await db.execute(select(User).where(User.role == UserRole.ADMIN).limit(1))
        if result.scalar_one_or_none() is None:
            admin = User(
                email=settings.ADMIN_EMAIL,
                hashed_password=pwd_context.hash(settings.ADMIN_PASSWORD),
                role=UserRole.ADMIN,
                credit_balance=0,
            )
            db.add(admin)
            await db.commit()
            print(f"[startup] Admin user created: {settings.ADMIN_EMAIL}")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLoggingMiddleware)

# Security headers
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.billing import router as billing_router
from app.api.dashboard_router import router as dashboard_router
from app.api.logs import router as logs_router
from app.api.templates_router import router as templates_router
from app.api.users import router as users_router
from app.api.v1.router import router as v1_router

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(v1_router)
app.include_router(billing_router)
app.include_router(logs_router)
app.include_router(admin_router)
app.include_router(templates_router)
app.include_router(dashboard_router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def root():
    return RedirectResponse(url="/login")


@app.get("/health")
async def health():
    return {"status": "ok"}
