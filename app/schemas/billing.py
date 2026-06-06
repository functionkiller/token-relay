from datetime import datetime

from pydantic import BaseModel


class TransactionOut(BaseModel):
    id: str
    amount: int
    balance_after: int
    type: str
    reference_id: str | None
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BalanceOut(BaseModel):
    credit_balance: int
    formatted: str


class UsageLogOut(BaseModel):
    id: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    credits_consumed: int
    streaming: bool
    latency_ms: int | None
    status: str
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
