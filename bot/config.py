"""Typed, validated application configuration.

Every setting can be provided through environment variables or a ``.env`` file;
no secret is ever hard-coded in the source tree. See ``.env.example``.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from bot.errors import ConfigError
from bot.utils.text import mask, parse_csv
from bot.utils.time import get_zone

ENV_HOME_VAR = "BOT_HOME"
PLACEHOLDER_VALUES = {
    "1234567",
    "0123456789abcdef0123456789abcdef",
    "123456789:aaexampletokenreplacemewitharealone",
    "changeme",
    "your_api_hash",
    "your_bot_token",
}
PLACEHOLDER_MARKERS = ("example", "replaceme", "your_", "changeme", "xxxx", "<", ">")

LogLevel = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
Environment = Literal["development", "production"]
AntispamAction = Literal["delete", "warn", "mute"]


def _is_placeholder(value: str) -> bool:
    """Detect values copied from .env.example or obviously fake secrets."""
    candidate = value.strip().lower()
    if candidate in PLACEHOLDER_VALUES:
        return True
    return any(marker in candidate for marker in PLACEHOLDER_MARKERS)


def detect_base_dir() -> Path:
    """Locate the project home directory.

    Order of precedence:
    1. ``BOT_HOME`` environment variable (used by systemd/docker),
    2. the current working directory when it contains a ``.env`` file,
    3. the directory that contains the ``bot`` package (i.e. the repo root),
    4. the current working directory.
    """
    explicit = os.getenv(ENV_HOME_VAR)
    if explicit:
        return Path(explicit).expanduser().resolve()

    cwd = Path.cwd()
    if (cwd / ".env").is_file():
        return cwd

    package_root = Path(__file__).resolve().parent.parent
    if (package_root / ".env").is_file() or (package_root / "pyproject.toml").is_file():
        return package_root
    return cwd


class Settings(BaseSettings):
    """Application settings with fail-fast validation."""

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        enable_decoding=False,
    )

    # --- Telegram credentials ------------------------------------------------
    api_id: int = Field(..., gt=0)
    api_hash: SecretStr
    bot_token: SecretStr
    owner_ids: list[int] = Field(default_factory=list)
    log_chat_id: int | None = None

    # --- Runtime -------------------------------------------------------------
    base_dir: Path = Field(default_factory=detect_base_dir)
    environment: Environment = "production"
    timezone: str = "Asia/Tehran"
    default_language: str = "fa"
    data_dir: Path = Path("data")
    session_dir: Path = Path("sessions")
    log_dir: Path = Path("logs")
    log_level: LogLevel = "INFO"
    log_json: bool = False
    log_rotate_mb: int = Field(5, ge=1, le=1024)
    log_backup_count: int = Field(5, ge=1, le=100)

    # --- Feature switches ----------------------------------------------------
    feature_tickets: bool = True
    feature_moderation: bool = True
    feature_antispam: bool = True
    feature_broadcast: bool = True

    # --- Anti-spam -----------------------------------------------------------
    antispam_flood_messages: int = Field(8, ge=1, le=1000)
    antispam_flood_window: int = Field(10, ge=1, le=3600)
    antispam_action: AntispamAction = "warn"
    antispam_mute_minutes: int = Field(60, ge=1, le=10080)
    antispam_warn_limit: int = Field(3, ge=1, le=100)
    antispam_ban_limit: int = Field(5, ge=1, le=100)
    antispam_block_links: bool = False
    antispam_allowed_domains: list[str] = Field(default_factory=list)
    antispam_banned_words: list[str] = Field(default_factory=list)
    antispam_new_user_seconds: int = Field(0, ge=0, le=86400)

    # --- Limits --------------------------------------------------------------
    ratelimit_commands: int = Field(20, ge=1, le=1000)
    ratelimit_window: int = Field(60, ge=1, le=86400)
    ticket_cooldown_seconds: int = Field(300, ge=0, le=86400)
    ticket_max_open: int = Field(3, ge=1, le=100)
    broadcast_delay: float = Field(0.06, ge=0.0, le=5.0)
    broadcast_concurrency: int = Field(4, ge=1, le=32)

    # --- Validators ----------------------------------------------------------
    @field_validator("api_hash", mode="before")
    @classmethod
    def _clean_hash(cls, value: Any) -> Any:
        if isinstance(value, SecretStr):
            value = value.get_secret_value()
        return str(value).strip()

    @field_validator("api_hash")
    @classmethod
    def _validate_hash(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if _is_placeholder(raw):
            raise ValueError("API_HASH still contains the example value from .env.example")
        if len(raw) != 32 or not all(char in "0123456789abcdefABCDEF" for char in raw):
            raise ValueError("API_HASH must be the 32-character hexadecimal hash from my.telegram.org")
        return value

    @field_validator("bot_token", mode="before")
    @classmethod
    def _clean_token(cls, value: Any) -> Any:
        if isinstance(value, SecretStr):
            value = value.get_secret_value()
        return str(value).strip()

    @field_validator("bot_token")
    @classmethod
    def _validate_token(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if _is_placeholder(raw):
            raise ValueError("BOT_TOKEN still contains the example value from .env.example")
        head, _, tail = raw.partition(":")
        if not head.isdigit() or len(tail) < 30:
            raise ValueError("BOT_TOKEN must look like '123456789:AA...' (get one from @BotFather)")
        return value

    @field_validator("api_id", mode="before")
    @classmethod
    def _validate_api_id(cls, value: Any) -> Any:
        if str(value) in PLACEHOLDER_VALUES:
            raise ValueError("API_ID still contains the example value from .env.example")
        return value

    @field_validator("log_chat_id", mode="before")
    @classmethod
    def _empty_to_none(cls, value: Any) -> Any:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return value

    @field_validator("owner_ids", "antispam_allowed_domains", "antispam_banned_words", mode="before")
    @classmethod
    def _split_lists(cls, value: Any) -> Any:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return parse_csv(value)
        return value

    @field_validator(
        "owner_ids",
        "antispam_allowed_domains",
        "antispam_banned_words",
        mode="after",
    )
    @classmethod
    def _dedupe(cls, value: list[Any]) -> list[Any]:
        seen: list[Any] = []
        for item in value:
            if item not in seen:
                seen.append(item)
        return seen

    @field_validator("default_language")
    @classmethod
    def _validate_language(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"fa", "en"}:
            raise ValueError("DEFAULT_LANGUAGE must be 'fa' or 'en'")
        return value

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str) -> str:
        candidate = value.strip()
        try:
            get_zone(candidate)
        except ConfigError as exc:
            # Re-raised as ValueError so the report points at the TIMEZONE field.
            raise ValueError(str(exc)) from exc
        return candidate

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_level(cls, value: Any) -> Any:
        return str(value).strip().upper()

    @model_validator(mode="after")
    def _check_limits(self) -> Settings:
        if self.antispam_ban_limit <= self.antispam_warn_limit:
            raise ValueError("ANTISPAM_BAN_LIMIT must be greater than ANTISPAM_WARN_LIMIT")
        if self.antispam_action == "mute" and self.antispam_mute_minutes <= 0:
            raise ValueError("ANTISPAM_MUTE_MINUTES must be positive when ANTISPAM_ACTION=mute")
        return self

    # --- Derived helpers -----------------------------------------------------
    @property
    def api_hash_value(self) -> str:
        return self.api_hash.get_secret_value()

    @property
    def bot_token_value(self) -> str:
        return self.bot_token.get_secret_value()

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def tz(self) -> Any:
        return get_zone(self.timezone)

    @property
    def data_path(self) -> Path:
        return self.resolve(self.data_dir)

    @property
    def session_path(self) -> Path:
        return self.resolve(self.session_dir)

    @property
    def log_path(self) -> Path:
        return self.resolve(self.log_dir)

    @property
    def db_file(self) -> Path:
        return self.data_path / "state.db"

    @property
    def legacy_json_file(self) -> Path:
        return self.data_path / "state.json"

    @property
    def env_file(self) -> Path:
        return self.base_dir / ".env"

    def resolve(self, path: Path | str) -> Path:
        """Resolve ``path`` relative to the project home directory."""
        candidate = Path(path).expanduser()
        return candidate if candidate.is_absolute() else (self.base_dir / candidate)

    def prepare_directories(self) -> None:
        """Create the runtime directories (idempotent)."""
        for path in (self.data_path, self.session_path, self.log_path):
            path.mkdir(parents=True, exist_ok=True)

    def safe_dump(self) -> dict[str, Any]:
        """Configuration snapshot with every secret masked."""
        data = self.model_dump(mode="json")
        data["api_hash"] = mask(self.api_hash_value)
        data["bot_token"] = mask(self.bot_token_value)
        return data

    def describe(self) -> str:
        """Short human-readable summary used by ``bot check`` and startup logs."""
        owners = ", ".join(str(owner) for owner in self.owner_ids) or "not set"
        features = [
            name.removeprefix("feature_")
            for name, enabled in (
                ("feature_tickets", self.feature_tickets),
                ("feature_moderation", self.feature_moderation),
                ("feature_antispam", self.feature_antispam),
                ("feature_broadcast", self.feature_broadcast),
            )
            if enabled
        ]
        return (
            f"home={self.base_dir} env={self.environment} tz={self.timezone} lang={self.default_language}\n"
            f"owners={owners} log_chat={self.log_chat_id or 'not set'}\n"
            f"features={', '.join(features) if features else 'none'}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return load_settings()


def load_settings(**overrides: Any) -> Settings:
    """Build Settings, converting validation problems into a friendly ConfigError."""
    base_dir = Path(overrides.pop("base_dir", detect_base_dir()))
    env_file = base_dir / ".env"
    try:
        settings = Settings(_env_file=env_file if env_file.is_file() else None, base_dir=base_dir, **overrides)
    except Exception as exc:  # pydantic ValidationError subclasses ValueError
        raise ConfigError(_format_validation_error(exc, env_file)) from exc
    return settings


def reload_settings() -> Settings:
    """Clear the cache and reload - used by tests."""
    get_settings.cache_clear()
    return get_settings()


def _format_validation_error(exc: Exception, env_file: Path) -> str:
    lines = [f"Invalid configuration (file: {env_file if env_file.is_file() else 'not found'})."]
    errors = getattr(exc, "errors", None)
    if callable(errors):
        for error in errors():
            field = ".".join(str(part) for part in error.get("loc", ())) or "settings"
            message = str(error.get("msg", "")).removeprefix("Value error, ")
            lines.append(f"  - {field.upper()}: {message}")
    else:  # pragma: no cover - unexpected error type
        lines.append(f"  - {exc}")
    lines.append("")
    lines.append("Fix the values in your .env file and try again. See .env.example for the full list.")
    return "\n".join(lines)
