"""Typed exceptions used across the application."""

from __future__ import annotations


class BotError(Exception):
    """Base class for every error raised intentionally by this project."""


class ConfigError(BotError):
    """Configuration is missing, malformed or still contains placeholders."""


class StorageError(BotError):
    """Persistent state could not be read or written."""


class AccessDenied(BotError):
    """The actor is not allowed to perform the requested action."""

    def __init__(self, message: str = "Access denied", *, required_role: str = "") -> None:
        super().__init__(message)
        self.required_role = required_role


class RateLimited(BotError):
    """Too many requests from the same actor."""

    def __init__(self, message: str = "Rate limited", *, retry_after: float = 0.0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class TelegramFlood(BotError):
    """Telegram asked us to slow down (FloodWaitError)."""

    def __init__(self, seconds: int) -> None:
        super().__init__(f"Flood wait requested by Telegram: {seconds}s")
        self.seconds = seconds


class NotConfigured(BotError):
    """A feature was used although it is disabled or lacks configuration."""
