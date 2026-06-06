import json
from collections.abc import AsyncIterator

import httpx

from app.adapters.base import AdapterRequest, BaseAdapter, ModelInfo


class OpenAICompatibleAdapter(BaseAdapter):
    def __init__(self, base_url: str, proxy_url: str | None = None):
        self._base_url = base_url.rstrip("/")
        self._proxy_url = proxy_url

    async def _client(self) -> httpx.AsyncClient:
        kwargs = {"timeout": httpx.Timeout(120.0)}
        if self._proxy_url:
            kwargs["proxy"] = self._proxy_url
        return httpx.AsyncClient(**kwargs)

    async def chat_completion(self, request: AdapterRequest, api_key: str) -> AsyncIterator[bytes]:
        url = f"{self._base_url}/chat/completions"
        body = request.body or {}
        body.setdefault("model", request.model)
        body.setdefault("stream", request.stream)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        client = await self._client()
        try:
            async with client.stream("POST", url, json=body, headers=headers) as response:
                if response.status_code >= 400:
                    error_body = await response.aread()
                    yield error_body
                    return
                if request.stream:
                    async for chunk in response.aiter_bytes():
                        yield chunk
                else:
                    yield await response.aread()
        finally:
            await client.aclose()

    async def list_models(self, api_key: str) -> list[ModelInfo]:
        url = f"{self._base_url}/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        client = await self._client()
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            models = []
            for m in data.get("data", []):
                models.append(ModelInfo(
                    id=m["id"],
                    created=m.get("created", 0),
                    owned_by=m.get("owned_by", ""),
                ))
            return models
        finally:
            await client.aclose()

    async def embeddings(self, body: dict, api_key: str) -> dict:
        url = f"{self._base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        client = await self._client()
        try:
            response = await client.post(url, json=body, headers=headers)
            response.raise_for_status()
            return response.json()
        finally:
            await client.aclose()
