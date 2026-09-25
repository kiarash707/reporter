"""Role checks: owner, staff and group administrator."""

from __future__ import annotations

import logging

from telethon import TelegramClient, errors

from bot.errors import AccessDenied
from bot.storage.repository import Repository

logger = logging.getLogger("bot.services.roles")

OWNER = "owner"
STAFF = "staff"
MEMBER = "member"


class Roles:
    """Resolves what an actor is allowed to do."""

    def __init__(self, repo: Repository, owner_ids: list[int] | set[int]) -> None:
        self.repo = repo
        self.owner_ids = {int(value) for value in owner_ids}

    # --- static roles --------------------------------------------------------
    def is_owner(self, user_id: int | None) -> bool:
        return user_id is not None and int(user_id) in self.owner_ids

    def is_staff(self, user_id: int | None) -> bool:
        if self.is_owner(user_id):
            return True
        return user_id is not None and int(user_id) in self.repo.staff_ids()

    def roles_of(self, user_id: int | None) -> set[str]:
        result: set[str] = {MEMBER}
        if self.is_staff(user_id):
            result.add(STAFF)
        if self.is_owner(user_id):
            result.add(OWNER)
        return result

    def require_owner(self, user_id: int | None) -> None:
        if not self.is_owner(user_id):
            raise AccessDenied("Owner rights required", required_role=OWNER)

    def require_staff(self, user_id: int | None) -> None:
        if not self.is_staff(user_id):
            raise AccessDenied("Staff rights required", required_role=STAFF)

    # --- chat-level roles ----------------------------------------------------
    async def is_chat_admin(self, client: TelegramClient, chat_id: int, user_id: int | None) -> bool:
        """Whether ``user_id`` is an administrator in ``chat_id``."""
        if user_id is None:
            return False
        if self.is_owner(user_id):
            return True
        try:
            permissions = await client.get_permissions(chat_id, int(user_id))
            return bool(getattr(permissions, "is_admin", False) or getattr(permissions, "is_creator", False))
        except errors.RPCError as exc:
            logger.debug("Cannot resolve admin rights for %s in %s: %s", user_id, chat_id, exc)
            return False
        except Exception as exc:  # pragma: no cover - unexpected telethon failure
            logger.warning("Admin check failed: %s", exc)
            return False

    async def require_chat_admin(self, client: TelegramClient, chat_id: int, user_id: int | None) -> None:
        if not await self.is_chat_admin(client, chat_id, user_id):
            raise AccessDenied("Group administrator rights required", required_role="chat_admin")
