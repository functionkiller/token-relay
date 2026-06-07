from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserOut(BaseModel):
    id: str
    email: str
    role: str
    credit_balance: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class ApiKeyOut(BaseModel):
    id: str
    key_prefix: str
    name: str
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreate(BaseModel):
    name: str = Field(default="default", min_length=1, max_length=40)


class ApiKeyCreated(BaseModel):
    id: str
    key_prefix: str
    full_key: str
    name: str
    created_at: datetime
