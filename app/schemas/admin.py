from datetime import datetime

from pydantic import BaseModel

from app.schemas.user import UserOut


class SettingUpdate(BaseModel):
    value: str


class ProviderKeyCreate(BaseModel):
    provider: str
    label: str
    api_key: str
    base_url: str
    proxy_url: str | None = None
    priority: int = 10


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
    provider: str
    model_id: str
    display_name: str
    is_enabled: bool = True
    input_price: int | None = None
    output_price: int | None = None
    supports_streaming: bool = True
    supports_vision: bool = False


class ModelConfigUpdate(BaseModel):
    display_name: str | None = None
    is_enabled: bool | None = None
    input_price: int | None = None
    output_price: int | None = None
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
    amount: int
    note: str = ""


class AdminUserUpdate(BaseModel):
    is_active: bool | None = None
    role: str | None = None


class DashboardStats(BaseModel):
    total_users: int
    active_users_today: int
    total_requests_today: int
    revenue_today_cents: int
    revenue_this_month_cents: int
    top_models: list[dict]
