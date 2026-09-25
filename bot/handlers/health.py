"""Health/diagnostics handlers and the catch-all fallback.

This module registers *last*: its handlers only answer what nobody else claimed.
"""

from __future__ import annotations

import logging

from telethon import TelegramClient, events

from bot.context import AppContext
from bot.handlers.commands import collect_known_commands
from bot.handlers.guard import guard, reply
from bot.services import stats
from bot.utils.text import escape_html

logger = logging.getLogger("bot.handlers.health")

PING_PATTERN = r"^/ping(?:@[\w_]+)?$"

#: how often a user may be reminded about the menu (seconds)
FALLBACK_COOLDOWN = 600


def register(client: TelegramClient, ctx: AppContext) -> None:
    """Register the diagnostics and fallback handlers (call this last)."""
    known_commands = collect_known_commands()

    @client.on(events.NewMessage(pattern=PING_PATTERN))
    @guard(ctx, rate_limit=False)
    async def ping(event: events.NewMessage.Event) -> None:
        """Uptime probe for monitoring; deliberately cheap."""
        language = ctx.language_of(event.sender_id)
        data = stats.collect(ctx)
        await reply(
            event,
            f"🏓 pong\n{ctx.tr('stats.uptime', language, uptime=data['uptime'])}\n"
            f"{ctx.tr('stats.db', language, size=data['db_size_kb'], schema=data['schema_version'])}",
        )

    @client.on(events.NewMessage(incoming=True))
    @guard(ctx, rate_limit=False)
    async def catch_all(event: events.NewMessage.Event) -> None:
        """Answer unknown commands; stay quiet about everything else."""
        text = (event.raw_text or "").strip()
        language = ctx.language_of(event.sender_id)

        if text.startswith("/"):
            name = text.split()[0].split("@", 1)[0].lstrip("/").lower()
            if name in known_commands:
                return  # owned by a real handler
            if event.is_private:
                await reply(event, ctx.tr("common.unknown_command", language))
                raise events.StopPropagation
            logger.debug("Unknown command %r in chat %s", text.split()[0], event.chat_id)
            return

        if not event.is_private:
            return

        # Plain private text: nudge towards the menu, but never spam the user.
        allowed, _retry = ctx.repo.check_rate_limit("fallback", int(event.sender_id), 1, FALLBACK_COOLDOWN)
        if not allowed:
            return
        await reply(
            event,
            ctx.tr("start.welcome", language, name=escape_html(getattr(event.sender, "first_name", "") or "👋")),
        )
        raise events.StopPropagation
