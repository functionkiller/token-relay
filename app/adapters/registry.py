from app.adapters.base import BaseAdapter
from app.adapters.openai_adapter import OpenAICompatibleAdapter


class AdapterRegistry:
    _adapters: dict[str, BaseAdapter] = {}
    _provider_base_urls: dict[str, str] = {}
    _provider_proxy_urls: dict[str, str | None] = {}

    @classmethod
    def register(cls, provider: str, base_url: str, proxy_url: str | None = None):
        cls._provider_base_urls[provider] = base_url
        cls._provider_proxy_urls[provider] = proxy_url
        cls._adapters[provider] = OpenAICompatibleAdapter(base_url, proxy_url)

    @classmethod
    def get(cls, provider: str) -> BaseAdapter | None:
        if provider not in cls._adapters:
            if provider in cls._provider_base_urls:
                cls.register(provider, cls._provider_base_urls[provider], cls._provider_proxy_urls.get(provider))
            else:
                return None
        return cls._adapters[provider]

    @classmethod
    def register_provider_key(cls, provider: str, base_url: str, proxy_url: str | None = None):
        if provider not in cls._adapters:
            cls.register(provider, base_url, proxy_url)
