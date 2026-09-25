"""Group moderation actions built on Telethon, with typed results."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, NamedTuple

from telethon import TelegramClient, errors
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.functions.messages import EditChatDefaultBannedRightsRequest
from telethon.tl.types import ChatBannedRights

from bot.storage.repository import Repository

logger = logging.getLogger("bot.services.moderation")

MUTE_RIGHTS = ChatBannedRights(
    until_date=None,
    send_messages=True,
    send_media=True,
    send_stickers=True,
    send_gifs=True,
    send_games=True,
    send_inline=True,
    embed_links=True,
)

# Note: ``ChatBannedRights`` flags are expressed as "restrictions to apply",
# so the mute set used below restricts every message type.
SILENCE = ChatBannedRights(
    until_date=None,
    send_messages=True,
    send_media=True,
    send_stickers=True,
    send_gifs=True,
    send_games=True,
    send_inline=True,
    embed_links=True,
    send_polls=True,
    change_info=False,
    invite_users=False,
    pin_messages=False,
)
UNRESTRICT = ChatBannedRights(until_date=None)


class ModerationResult(NamedTuple):
    ok: bool
    reason: str = ""


class ModerationService:
    """Wraps the moderation RPC calls used by the group handlers."""

    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    async def mute(self, client: TelegramClient, chat_id: int, user_id: int, minutes: int = 60) -> ModerationResult:
        until = None
        if minutes and minutes > 0:
            from bot.utils.time import now

            until = now("UTC") + timedelta(minutes=int(minutes))
        try:
            await client(EditBannedRequest(chat_id, user_id, _mute_rights(until)))
            return ModerationResult(True)
        except errors.ChatAdminRequiredError:
            return ModerationResult(False, "bot_not_admin")
        except errors.RPCError as exc:
            logger.warning("Mute failed (%s): %s", user_id, exc)
            return ModerationResult(False, type(exc).__name__)

    async def unmute(self, client: TelegramClient, chat_id: int, user_id: int) -> ModerationResult:
        try:
            await client(EditBannedRequest(chat_id, user_id, UNRESTRICT))
            return ModerationResult(True)
        except errors.ChatAdminRequiredError:
            return ModerationResult(False, "bot_not_admin")
        except errors.RPCError as exc:
            logger.warning("Unmute failed (%s): %s", user_id, exc)
            return ModerationResult(False, type(exc).__name__)

    async def ban(self, client: TelegramClient, chat_id: int, user_id: int, *, minutes: int = 0) -> ModerationResult:
        until = None
        if minutes and minutes > 0:
            from bot.utils.time import now

            until = now("UTC") + timedelta(minutes=int(minutes))
        try:
            await client(EditBannedRequest(chat_id, user_id, _ban_rights(until)))
            return ModerationResult(True)
        except errors.ChatAdminRequiredError:
            return ModerationResult(False, "bot_not_admin")
        except errors.RPCError as exc:
            logger.warning("Ban failed (%s): %s", user_id, exc)
            return ModerationResult(False, type(exc).__name__)

    unban = unmute  # unbanning is exactly "clear all restrictions"

    async def kick(self, client: TelegramClient, chat_id: int, user_id: int) -> ModerationResult:
        """Remove a member without a lasting ban."""
        banned = await self.ban(client, chat_id, user_id)
        if not banned.ok:
            return banned
        return await self.unban(client, chat_id, user_id)

    async def delete_messages(self, client: TelegramClient, chat_id: int, message_ids: list[int]) -> ModerationResult:
        if not message_ids:
            return ModerationResult(True)
        try:
            await client.delete_messages(chat_id, message_ids, revoke=True)
            return ModerationResult(True)
        except errors.MessageDeleteForbiddenError:
            return ModerationResult(False, "delete_forbidden")
        except errors.RPCError as exc:
            logger.warning("Delete failed in %s: %s", chat_id, exc)
            return ModerationResult(False, type(exc).__name__)

    async def lock_chat_defaults(
        self, client: TelegramClient, chat_id: int, *, restrict_media: bool = True
    ) -> ModerationResult:
        """Apply (or lift) default restrictions - used by the anti-spam service."""
        try:
            await client(EditChatDefaultBannedRightsRequest(chat_id, SILENCE if restrict_media else UNRESTRICT))
            return ModerationResult(True)
        except errors.RPCError as exc:
            return ModerationResult(False, type(exc).__name__)

    async def can_moderate(self, client: TelegramClient, chat_id: int, target_id: int, actor_id: int) -> bool:
        """Refuse to act on administrators (except when an owner does it)."""
        try:
            target = await client.get_permissions(chat_id, int(target_id))
        except Exception:
            return True
        return not (getattr(target, "is_admin", False) or getattr(target, "is_creator", False))

    async def log_action(
        self, actor_id: int, action: str, target: Any, *, chat_id: int, details: dict[str, Any] | None = None
    ) -> None:
        self.repo.audit(
            actor_id,
            action,
            target=str(target),
            details={"chat_id": chat_id, **(details or {})},
        )


def _mute_rights(until: Any) -> ChatBannedRights:
    if until is None:
        return SILENCE
    return ChatBannedRights(
        until_date=until,
        send_messages=True,
        send_media=True,
        send_stickers=True,
        send_gifs=True,
        send_games=True,
        send_inline=True,
        embed_links=True,
        send_polls=True,
    )


def _ban_rights(until: Any) -> ChatBannedRights:
    return ChatBannedRights(until_date=until, view_messages=True)
