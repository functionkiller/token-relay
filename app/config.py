from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Token Relay"
    DEBUG: bool = False
    SECRET_KEY: str
    ENCRYPTION_KEY: str

    # Admin auto-creation
    ADMIN_EMAIL: str = "admin@tokenrelay.com"
    ADMIN_PASSWORD: str = "admin123456"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./app.db"

    # Redis (empty = in-memory fallback)
    REDIS_URL: str = ""

    # Rate Limiting
    RATE_LIMIT_PER_USER_PER_MINUTE: int = 60
    RATE_LIMIT_GLOBAL_PER_MINUTE: int = 10000

    # JWT
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Proxy
    PROXY_REQUEST_TIMEOUT: int = 120
    PROXY_MAX_RETRIES: int = 2

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # Registration
    REGISTRATION_OPEN: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
