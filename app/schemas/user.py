from datetime import datetime
from typing import Any

from pydantic import BaseModel


class UserOut(BaseModel):
    id: str
    email: str
    role: str
    credit_balance: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    email: str | None = None
    password: str | None = None


class ApiKeyOut(BaseModel):
    id: str
    key_prefix: str
    name: str
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreate(BaseModel):
    name: str = "default"


class ApiKeyCreated(BaseModel):
    id: str
    key_prefix: str
    full_key: str
    name: str
    created_at: datetime
