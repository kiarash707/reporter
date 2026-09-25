"""Central logging configuration: console + rotating files (+ optional JSON)."""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from datetime import datetime, timezone

from bot.config import Settings
from bot.utils.text import mask

CONSOLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s"
FILE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_SECRET_MARKERS = ("token", "hash", "password", "secret", "api_key", "session_string")


class SecretFilter(logging.Filter):
    """Best-effort guard that keeps session strings and tokens out of log files."""

    def __init__(self, secrets: list[str]) -> None:
        super().__init__()
        self._secrets = [secret for secret in secrets if secret and len(secret) > 6]

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - malformed record
            return True
        redacted = message
        for secret in self._secrets:
            if secret in redacted:
                redacted = redacted.replace(secret, mask(secret))
        lowered = redacted.lower()
        if (
            any(marker in lowered for marker in _SECRET_MARKERS) and record.levelno < logging.INFO
        ) or redacted != message:
            record.msg = redacted
            record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line - friendly for journald/Loki/ELK pipelines."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key in ("chat_id", "user_id", "command", "duration_ms"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(settings: Settings, *, force: bool = False) -> logging.Logger:
    """Configure the root logger once and return the application logger."""
    root = logging.getLogger()
    if getattr(root, "_bot_configured", False) and not force:
        return logging.getLogger("bot")

    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    settings.prepare_directories()
    level = getattr(logging, settings.log_level, logging.INFO)
    root.setLevel(level)

    secret_filter = SecretFilter([settings.bot_token_value, settings.api_hash_value])

    console = logging.StreamHandler(stream=sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(CONSOLE_FORMAT, DATE_FORMAT))
    console.addFilter(secret_filter)
    root.addHandler(console)

    bot_handler = logging.handlers.RotatingFileHandler(
        settings.log_path / "bot.log",
        maxBytes=settings.log_rotate_mb * 1024 * 1024,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    bot_handler.setLevel(level)
    bot_handler.setFormatter(JsonFormatter() if settings.log_json else logging.Formatter(FILE_FORMAT, DATE_FORMAT))
    bot_handler.addFilter(secret_filter)
    root.addHandler(bot_handler)

    error_handler = logging.handlers.RotatingFileHandler(
        settings.log_path / "errors.log",
        maxBytes=settings.log_rotate_mb * 1024 * 1024,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(logging.Formatter(FILE_FORMAT, DATE_FORMAT))
    error_handler.addFilter(secret_filter)
    root.addHandler(error_handler)

    # Telethon is chatty at INFO level; keep its noise down.
    logging.getLogger("telethon").setLevel(max(level, logging.WARNING))
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    root._bot_configured = True  # type: ignore[attr-defined]
    logger = logging.getLogger("bot")
    logger.debug(
        "Logging configured: level=%s json=%s dir=%s", settings.log_level, settings.log_json, settings.log_path
    )
    return logger


def get_logger(name: str) -> logging.Logger:
    """Convenience accessor that keeps logger naming consistent."""
    return logging.getLogger(name if name.startswith("bot") else f"bot.{name}")
