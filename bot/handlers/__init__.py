"""Handler registration.

Order matters: Telethon walks matching handlers in registration order and stops
when a handler raises :class:`telethon.events.StopPropagation`. Command and
conversational handlers therefore register *before* the catch-all handlers.
"""

from __future__ import annotations

import logging

from telethon import TelegramClient

from bot.context import AppContext
from bot.handlers import common, health, moderation, owner, tickets

logger = logging.getLogger("bot.handlers")


def register_all(client: TelegramClient, ctx: AppContext) -> None:
    """Attach every handler group to the client."""
    registered: list[str] = []
    for module in (common, tickets, owner, moderation, health):
        module.register(client, ctx)
        registered.append(module.__name__.rsplit(".", 1)[-1])
    logger.info("Handlers registered: %s", ", ".join(registered))
