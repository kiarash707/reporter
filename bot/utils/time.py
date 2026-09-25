"""Timezone-aware date helpers built on the standard library (no pytz needed)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bot.errors import ConfigError


def get_zone(name: str) -> ZoneInfo:
    """Return a ZoneInfo for ``name`` or raise a clear ConfigError."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:  # pragma: no cover - depends on tzdata
        raise ConfigError(
            f"Unknown timezone {name!r}. Use an IANA name such as 'Asia/Tehran' or 'Europe/Berlin'."
        ) from exc


def now(tz: ZoneInfo | str = "UTC") -> datetime:
    """Current, timezone-aware time."""
    zone = tz if isinstance(tz, ZoneInfo) else get_zone(tz)
    return datetime.now(zone)


def ensure_aware(value: datetime, tz: ZoneInfo | str = "UTC") -> datetime:
    """Attach ``tz`` to naive datetimes coming from older data files."""
    if value.tzinfo is None:
        zone = tz if isinstance(tz, ZoneInfo) else get_zone(tz)
        return value.replace(tzinfo=zone)
    return value


def parse_datetime(value: str | datetime | None, tz: ZoneInfo | str = "UTC") -> datetime | None:
    """Parse an ISO-8601 string (as stored in JSON) into an aware datetime."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return ensure_aware(value, tz)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return ensure_aware(parsed, tz)


def humanize_delta(delta: timedelta, *, language: str = "en") -> str:
    """Render a duration such as ``2d 4h 10m`` in English or Persian."""
    total = int(delta.total_seconds())
    sign = "-" if total < 0 else ""
    total = abs(total)
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, seconds = divmod(rest, 60)

    if language == "fa":
        units = [(days, "روز"), (hours, "ساعت"), (minutes, "دقیقه"), (seconds, "ثانیه")]
    else:
        units = [(days, "d"), (hours, "h"), (minutes, "m"), (seconds, "s")]

    parts = [f"{value}{' ' if language == 'fa' else ''}{label}" for value, label in units if value]
    if not parts:
        return "0" + (" ثانیه" if language == "fa" else "s")
    return sign + (" و ".join(parts[:2]) if language == "fa" else " ".join(parts[:3]))


def format_datetime(value: datetime | None, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """Format a datetime, returning a dash for empty values."""
    if value is None:
        return "-"
    return value.strftime(fmt)


def utcnow() -> datetime:
    """Timezone-aware UTC now (explicit, to avoid naive datetime bugs)."""
    return datetime.now(timezone.utc)
