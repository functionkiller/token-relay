from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.user import UserOut


class SettingUpdate(BaseModel):
    value: str = Field(min_length=1)


class ProviderKeyCreate(BaseModel):
    provider: str = Field(min_length=1, max_length=50)
    label: str = Field(min_length=1, max_length=100)
    api_key: str = Field(min_length=1, max_length=512)
    base_url: str = Field(min_length=1, max_length=255)
    proxy_url: str | None = Field(default=None, max_length=255)
    priority: int = Field(default=10, ge=1, le=100)


class ProviderKeyOut(BaseModel):
    id: str
    provider: str
    label: str
    key_preview: str  # first 4 + last 4 chars redacted
    base_url: str
    proxy_url: str | None
    is_active: bool
    priority: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ModelConfigCreate(BaseModel):
    provider: str = Field(min_length=1, max_length=50)
    model_id: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=100)
    is_enabled: bool = True
    input_price: int | None = Field(default=None, ge=0)
    output_price: int | None = Field(default=None, ge=0)
    supports_streaming: bool = True
    supports_vision: bool = False


class ModelConfigUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    is_enabled: bool | None = None
    input_price: int | None = Field(default=None, ge=0)
    output_price: int | None = Field(default=None, ge=0)
    supports_streaming: bool | None = None
    supports_vision: bool | None = None


class ModelConfigOut(BaseModel):
    id: str
    provider: str
    model_id: str
    display_name: str
    is_enabled: bool
    input_price: int | None
    output_price: int | None
    supports_streaming: bool
    supports_vision: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CreditAdjust(BaseModel):
    amount: int = Field(gt=0, description="Positive amount in cents to add")
    note: str = Field(default="", max_length=500)


class AdminUserUpdate(BaseModel):
    is_active: bool | None = None
    role: str | None = Field(default=None, pattern="^(user|admin)$")


class DashboardStats(BaseModel):
    total_users: int
    active_users_today: int
    total_requests_today: int
    revenue_today_cents: int
    revenue_this_month_cents: int
    top_models: list[dict]
