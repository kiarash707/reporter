"""Thin, defensive helpers around Telethon objects.

Nothing in here performs bulk automated actions: the helpers only translate
Telethon errors into the project's typed exceptions and normalise small pieces
of metadata used by handlers.
"""

from __future__ import annotations

from typing import Any

from telethon import errors
from telethon.tl.types import Channel, Chat, User

from bot.errors import TelegramFlood
from bot.utils.text import escape_html


def display_name(entity: Any) -> str:
    """Best-effort human readable name for a user/chat/channel."""
    if entity is None:
        return "unknown"
    title = getattr(entity, "title", None)
    if title:
        return str(title)
    parts = [getattr(entity, "first_name", None), getattr(entity, "last_name", None)]
    joined = " ".join(part for part in parts if part)
    if joined:
        return joined
    username = getattr(entity, "username", None)
    if username:
        return f"@{username}"
    return str(getattr(entity, "id", "unknown"))


def entity_id(entity: Any) -> int | None:
    value = getattr(entity, "id", None)
    return int(value) if value is not None else None


def is_group(entity: Any) -> bool:
    return isinstance(entity, (Chat, Channel)) and bool(getattr(entity, "megagroup", False) or isinstance(entity, Chat))


def is_channel(entity: Any) -> bool:
    return isinstance(entity, Channel) and not getattr(entity, "megagroup", False)


def is_user(entity: Any) -> bool:
    return isinstance(entity, User)


def is_bot(entity: Any) -> bool:
    return bool(getattr(entity, "bot", False))


def full_mention(entity: Any) -> str:
    """HTML mention for a user entity, falling back to the display name."""
    identifier = entity_id(entity)
    name = escape_html(display_name(entity))
    if identifier is None:
        return name
    return f'<a href="tg://user?id={identifier}">{name}</a>'


def chat_identifier(event: Any) -> int:
    """Return the id used to key per-chat settings (chat_id for groups)."""
    chat_id = getattr(event, "chat_id", None)
    if chat_id is not None:
        return int(chat_id)
    return int(event.sender_id)


def classify_error(exc: BaseException) -> str:
    """Map an exception to a stable, log-friendly reason code."""
    if isinstance(exc, errors.FloodWaitError):
        return "flood_wait"
    if isinstance(exc, (errors.ChatAdminRequiredError, errors.ChatWriteForbiddenError)):
        return "missing_permissions"
    if isinstance(exc, (errors.ChannelPrivateError, errors.PeerIdInvalidError)):
        return "entity_unavailable"
    if isinstance(exc, (errors.UserIsBlockedError, errors.UserPrivacyRestrictedError)):
        return "user_unreachable"
    if isinstance(exc, errors.AuthKeyUnregisteredError):
        return "session_revoked"
    for name in ("BotMethodInvalidError", "BotBlockedError"):
        error_type = getattr(errors, name, None)
        if error_type is not None and isinstance(exc, error_type):
            return "bot_restricted"
    return type(exc).__name__


async def guard_flood(exc: errors.FloodWaitError) -> None:
    """Convert a Telethon FloodWaitError into a typed TelegramFlood exception."""
    raise TelegramFlood(int(getattr(exc, "seconds", 0) or 0))


def admin_rights_summary(permissions: Any) -> str:
    """Short text listing of the rights granted to the bot in a chat."""
    if permissions is None:
        return "none"
    fields = (
        ("delete_messages", "delete"),
        ("ban_users", "ban"),
        ("mute_users", "mute"),
        ("invite_users", "invite"),
        ("pin_messages", "pin"),
    )
    granted = [label for attr, label in fields if getattr(permissions, attr, False)]
    return ", ".join(granted) or "none"


def looks_like_link(text: str) -> bool:
    """Very small link detector (http/https, tg links, bare domains)."""
    import re

    pattern = re.compile(
        r"(https?://|www\.|t\.me/|telegram\.me/|\b[\w-]+\.(?:com|net|org|io|ir|co|ru|xyz|info|me)\b)", re.I
    )
    return bool(pattern.search(text or ""))
