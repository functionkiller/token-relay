from datetime import datetime
from typing import Any

from pydantic import BaseModel


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    size: int
    pages: int


class ErrorResponse(BaseModel):
    detail: str


class OpenAIErrorResponse(BaseModel):
    error: dict[str, str]


class SystemSettingOut(BaseModel):
    key: str
    value: str
    updated_at: datetime

    model_config = {"from_attributes": True}
