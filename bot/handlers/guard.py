"""Cross-cutting concerns for handlers: access checks, rate limits, error mapping.

Handlers stay readable because every guard lives in one place::

    @client.on(events.NewMessage(pattern=r"^/ban"))
    @guard(ctx, staff_only=True, group_only=True)
    async def ban(event): ...
"""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from telethon import events

from bot.context import AppContext
from bot.errors import AccessDenied, ConfigError, NotConfigured, RateLimited, StorageError, TelegramFlood

logger = logging.getLogger("bot.handlers")

Handler = Callable[[Any], Awaitable[Any]]


def guard(
    ctx: AppContext,
    *,
    staff_only: bool = False,
    owner_only: bool = False,
    group_only: bool = False,
    private_only: bool = False,
    rate_limit: bool = True,
    ignore_when_disabled: bool = True,
) -> Callable[[Handler], Handler]:
    """Wrap a handler with permission, availability and error handling."""

    def decorator(func: Handler) -> Handler:
        @functools.wraps(func)
        async def wrapper(event: Any) -> Any:
            user_id = _user_id(event)
            chat_id = getattr(event, "chat_id", None)
            language = ctx.language_of(user_id) if user_id else ctx.settings.default_language
            started = time.perf_counter()

            try:
                _check_environment(
                    ctx,
                    event,
                    user_id=user_id,
                    staff_only=staff_only,
                    owner_only=owner_only,
                    group_only=group_only,
                    private_only=private_only,
                    ignore_when_disabled=ignore_when_disabled,
                )
                if rate_limit and user_id and not ctx.is_owner(user_id):
                    ctx.ratelimit.check(user_id, "command")
                result = await func(event)
                ctx.repo.increment_counter("commands")
                logger.info(
                    "handled %s | user=%s chat=%s | %.1f ms",
                    func.__name__,
                    user_id,
                    chat_id,
                    (time.perf_counter() - started) * 1000,
                    extra={"user_id": user_id, "chat_id": chat_id, "command": func.__name__},
                )
                return result
            except events.StopPropagation:
                raise
            except AccessDenied:
                await _safe_answer(event, ctx.tr("common.not_allowed", language))
            except RateLimited as exc:
                await _safe_answer(event, ctx.tr("common.rate_limited", language, seconds=int(exc.retry_after)))
            except TelegramFlood as exc:
                logger.warning("Telegram flood wait: %ss (%s)", exc.seconds, func.__name__)
                await _safe_answer(event, ctx.tr("error.flood_wait", language, seconds=exc.seconds))
            except NotConfigured:
                await _safe_answer(event, ctx.tr("common.feature_disabled", language))
            except StorageError as exc:
                logger.error("Storage error in %s: %s", func.__name__, exc, exc_info=True)
                await _safe_answer(event, ctx.tr("error.db", language))
            except ConfigError as exc:
                logger.error("Configuration error in %s: %s", func.__name__, exc)
                await _safe_answer(event, ctx.tr("common.error", language))
            except Exception as exc:
                logger.exception("Unhandled error in %s: %s", func.__name__, exc)
                await _safe_answer(event, ctx.tr("error.internal", language))
                await ctx.notify_owner(f"{func.__name__}: {type(exc).__name__}: {exc}", category="error")
                return None

        wrapper.__wrapped_handler__ = func  # type: ignore[attr-defined]
        return wrapper

    return decorator


def _check_environment(
    ctx: AppContext,
    event: Any,
    *,
    user_id: int | None,
    staff_only: bool,
    owner_only: bool,
    group_only: bool,
    private_only: bool,
    ignore_when_disabled: bool,
) -> None:
    """Raise AccessDenied/NotConfigured before the handler body runs."""
    if user_id is None:
        raise AccessDenied("Anonymous actor")

    if ctx.repo.is_blocked(user_id) and not ctx.is_owner(user_id):
        raise AccessDenied("Blocked user", required_role="member")

    if owner_only:
        ctx.roles.require_owner(user_id)
    elif staff_only and not ctx.roles.is_staff(user_id):
        ctx.roles.require_staff(user_id)

    if group_only and not getattr(event, "is_group", False):
        raise NotConfigured("group-only handler")
    if private_only and not getattr(event, "is_private", False):
        raise NotConfigured("private-only handler")

    if ignore_when_disabled and not ctx.is_owner(user_id):
        if not ctx.repo.get_flag("bot_enabled", True):
            raise AccessDenied("Bot disabled", required_role="owner")
        if ctx.repo.get_flag("maintenance", False):
            raise NotConfigured("maintenance mode")


def _user_id(event: Any) -> int | None:
    value = getattr(event, "sender_id", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


async def _safe_answer(event: Any, text: str) -> None:
    """Reply (or toast, for callbacks) without ever raising."""
    try:
        is_callback = getattr(event, "is_callback", False) or type(event).__name__.endswith("CallbackQuery")
        if is_callback and hasattr(event, "answer") and getattr(event, "message", None) is not None:
            await event.answer(_toast(text), alert=False)
            return
        await event.reply(text, parse_mode=None, link_preview=False)
    except Exception as exc:  # pragma: no cover - depends on Telegram state
        logger.debug("Cannot deliver guard message: %s", exc)


def _toast(text: str) -> str:
    """Callbacks only show a small toast, so collapse to a single line."""
    line = " ".join(str(text).split())
    return line[:190]


async def reply(event: Any, text: str, **kwargs: Any) -> Any:
    """Uniform reply helper used by handlers (never previews links)."""
    kwargs.setdefault("parse_mode", "html")
    kwargs.setdefault("link_preview", False)
    return await event.reply(text, **kwargs)


async def edit(event: Any, text: str, **kwargs: Any) -> Any:
    """Uniform edit helper for callback messages."""
    kwargs.setdefault("parse_mode", "html")
    kwargs.setdefault("link_preview", False)
    return await event.edit(text, **kwargs)
