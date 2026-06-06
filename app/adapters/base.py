from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from pydantic import BaseModel


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str


@dataclass
class AdapterRequest:
    model: str
    messages: list[dict]
    stream: bool = False
    max_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    body: dict | None = None  # raw parsed JSON, for pass-through


class BaseAdapter(ABC):
    @abstractmethod
    async def chat_completion(self, request: AdapterRequest, api_key: str) -> AsyncIterator[bytes]:
        """Yield raw bytes (one chunk for non-streaming, SSE chunks for streaming)."""
        ...

    @abstractmethod
    async def list_models(self, api_key: str) -> list[ModelInfo]:
        ...

    @abstractmethod
    async def embeddings(self, body: dict, api_key: str) -> dict:
        ...
