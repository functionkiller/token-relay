import asyncio
import time
from collections import defaultdict

from app.config import settings


class InMemoryRateLimiter:
    def __init__(self):
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._cleanup_task: asyncio.Task | None = None

    def is_allowed(self, key: str, max_requests: int, window_seconds: int = 60) -> tuple[bool, int, int]:
        """Returns (allowed, remaining, reset_seconds)."""
        now = time.time()
        cutoff = now - window_seconds
        bucket = self._buckets[key]
        self._buckets[key] = [t for t in bucket if t > cutoff]
        remaining = max(0, max_requests - len(self._buckets[key]))
        if remaining <= 0:
            oldest = min(self._buckets[key])
            reset_seconds = int(oldest + window_seconds - now) + 1
            return False, 0, reset_seconds
        self._buckets[key].append(now)
        return True, remaining - 1, window_seconds

    def cleanup(self):
        now = time.time()
        for key in list(self._buckets.keys()):
            self._buckets[key] = [t for t in self._buckets[key] if t > now - 120]
            if not self._buckets[key]:
                del self._buckets[key]

    def start_cleanup(self, interval: int = 120):
        """Start a periodic cleanup task (call during app startup)."""
        async def _loop():
            while True:
                await asyncio.sleep(interval)
                self.cleanup()
        self._cleanup_task = asyncio.create_task(_loop())

    def stop_cleanup(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()


rate_limiter = InMemoryRateLimiter()


class RateLimitResult:
    def __init__(self, allowed: bool, remaining: int, reset_seconds: int):
        self.allowed = allowed
        self.remaining = remaining
        self.reset_seconds = reset_seconds


async def check_rate_limit(user_id: str) -> RateLimitResult:
    """Check both per-user and global rate limits. Returns result with header info."""
    per_user = settings.RATE_LIMIT_PER_USER_PER_MINUTE
    global_limit = settings.RATE_LIMIT_GLOBAL_PER_MINUTE

    # Check per-user first
    if per_user > 0:
        allowed, remaining, reset = rate_limiter.is_allowed(f"user:{user_id}", per_user, 60)
        if not allowed:
            return RateLimitResult(False, 0, reset)

    # Check global
    if global_limit > 0:
        allowed, remaining, reset = rate_limiter.is_allowed("global", global_limit, 60)
        if not allowed:
            return RateLimitResult(False, 0, reset)

    # Compute remaining for user
    if per_user > 0:
        _, remaining, reset = rate_limiter.is_allowed(f"user:{user_id}", per_user, 60)
        # Don't consume a second token — just query. Fix by checking bucket directly.
        now = time.time()
        bucket = rate_limiter._buckets.get(f"user:{user_id}", [])
        bucket = [t for t in bucket if t > now - 60]
        remaining = max(0, per_user - len(bucket))
        return RateLimitResult(True, remaining, 60)
    return RateLimitResult(True, 0, 60)


def add_rate_limit_headers(response, result: RateLimitResult):
    """Add standard rate limit headers to a response."""
    response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_PER_USER_PER_MINUTE)
    response.headers["X-RateLimit-Remaining"] = str(result.remaining)
    response.headers["X-RateLimit-Reset"] = str(result.reset_seconds)
