import time
from collections import defaultdict

from app.config import settings


class InMemoryRateLimiter:
    def __init__(self):
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str, max_requests: int, window_seconds: int = 60) -> bool:
        now = time.time()
        cutoff = now - window_seconds
        bucket = self._buckets[key]
        self._buckets[key] = [t for t in bucket if t > cutoff]
        if len(self._buckets[key]) >= max_requests:
            return False
        self._buckets[key].append(now)
        return True

    def cleanup(self):
        now = time.time()
        for key in list(self._buckets.keys()):
            self._buckets[key] = [t for t in self._buckets[key] if t > now - 120]
            if not self._buckets[key]:
                del self._buckets[key]


rate_limiter = InMemoryRateLimiter()


async def check_rate_limit(user_id: str) -> bool:
    per_user = settings.RATE_LIMIT_PER_USER_PER_MINUTE
    if per_user <= 0:
        return True
    return rate_limiter.is_allowed(f"user:{user_id}", per_user, 60)
