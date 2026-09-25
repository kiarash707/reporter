"""Per-user command rate limiting (SQLite backed, survives restarts)."""

from __future__ import annotations

import logging

from bot.errors import RateLimited
from bot.storage.repository import Repository

logger = logging.getLogger("bot.services.ratelimit")


class RateLimiter:
    """Fixed-window limiter shared by every command handler."""

    def __init__(self, repo: Repository, *, limit: int = 20, window: int = 60) -> None:
        self.repo = repo
        self.limit = max(1, int(limit))
        self.window = max(1, int(window))

    def check(self, user_id: int, scope: str = "command") -> None:
        """Raise RateLimited when the caller exceeded the allowance."""
        allowed, retry_after = self.repo.check_rate_limit(scope, int(user_id), self.limit, self.window)
        if not allowed:
            raise RateLimited(f"Rate limit exceeded for {scope}", retry_after=retry_after)

    def is_allowed(self, user_id: int, scope: str = "command") -> tuple[bool, float]:
        return self.repo.check_rate_limit(scope, int(user_id), self.limit, self.window)

    def cooldown_left(self, scope: str, key: object, seconds: float) -> float:
        return self.repo.cooldown_remaining(scope, key, seconds)

    def start_cooldown(self, scope: str, key: object) -> None:
        self.repo.start_cooldown(scope, key)
