"""Group moderation: member commands, anti-spam enforcement and welcome messages."""

from __future__ import annotations

import contextlib
import logging
import re
import time
from datetime import timedelta
from typing import Any

from telethon import Button, TelegramClient, events

from bot.context import AppContext
from bot.handlers.guard import edit, guard, reply
from bot.keyboards import CB_GROUP_ANTISPAM, CB_GROUP_RULES, CB_GROUP_STATS, CB_GROUP_WELCOME, CB_HOME, group_panel
from bot.services import stats
from bot.services.moderation import ModerationService
from bot.utils.telegram import display_name, full_mention
from bot.utils.text import escape_html, truncate
from bot.utils.time import humanize_delta

logger = logging.getLogger("bot.handlers.moderation")

STATE_GROUP_RULES = "group_rules"

PANEL_PATTERN = r"^/admin(?:@[\w_]+)?$"
RULES_PATTERN = r"^/rules(?:@[\w_]+)?$"
SET_RULES_PATTERN = r"^/setrules(?:@[\w_]+)?(?:\s|$)"
WARN_PATTERN = r"^/warn(?:@[\w_]+)?(?:\s+([\s\S]+))?$"
UNWARN_PATTERN = r"^/unwarn(?:@[\w_]+)?(?:\s+([\s\S]+))?$"
WARNS_PATTERN = r"^/warns(?:@[\w_]+)?(?:\s+([\s\S]+))?$"
MUTE_PATTERN = r"^/mute(?:@[\w_]+)?(?:\s+([\s\S]+))?$"
UNMUTE_PATTERN = r"^/unmute(?:@[\w_]+)?(?:\s+([\s\S]+))?$"
BAN_PATTERN = r"^/ban(?:@[\w_]+)?(?:\s+([\s\S]+))?$"
UNBAN_PATTERN = r"^/unban(?:@[\w_]+)?(?:\s+([\s\S]+))?$"
KICK_PATTERN = r"^/kick(?:@[\w_]+)?(?:\s+([\s\S]+))?$"
PURGE_PATTERN = r"^/purge(?:@[\w_]+)?(?:\s+(\d+))?$"
PIN_PATTERN = r"^/pin(?:@[\w_]+)?$"
WELCOME_PATTERN = None  # welcome messages are handled via ChatAction


def register(client: TelegramClient, ctx: AppContext) -> None:
    """Attach group handlers."""

    # ------------------------------------------------------------- panel
    @client.on(events.NewMessage(pattern=PANEL_PATTERN))
    @guard(ctx, group_only=True)
    async def panel_command(event: events.NewMessage.Event) -> None:
        await show_panel(ctx, event, mode="message")

    @client.on(events.NewMessage(pattern=RULES_PATTERN))
    @guard(ctx)
    async def rules(event: events.NewMessage.Event) -> None:
        language = ctx.language_of(event.sender_id)
        text = ctx.repo.get_group_rules(int(event.chat_id)) if event.is_group else None
        if not text:
            await reply(event, ctx.tr("group.rules_empty", language))
            return
        await reply(event, ctx.tr("group.rules_header", language, rules=escape_html(text)))

    @client.on(events.NewMessage(pattern=SET_RULES_PATTERN))
    @guard(ctx, group_only=True)
    async def set_rules(event: events.NewMessage.Event) -> None:
        await _require_chat_admin(ctx, event)
        user_id = int(event.sender_id)
        ctx.states.set(user_id, STATE_GROUP_RULES, chat_id=int(event.chat_id))
        await reply(event, ctx.tr("group.rules_prompt", ctx.language_of(user_id)))

    @client.on(events.NewMessage(incoming=True, func=lambda event: event.is_group))
    @guard(ctx, group_only=True, ignore_when_disabled=False)
    async def rules_text(event: events.NewMessage.Event) -> None:
        user_id = int(event.sender_id)
        state = ctx.states.get(user_id)
        if state is None or state.name != STATE_GROUP_RULES:
            return
        await _require_chat_admin(ctx, event)
        chat_id = int(state.data.get("chat_id") or event.chat_id)
        ctx.repo.set_group_rules(chat_id, truncate(event.raw_text or "", 3000))
        ctx.states.clear(user_id)
        ctx.repo.audit(user_id, "set_group_rules", target=str(chat_id))
        await reply(event, ctx.tr("group.rules_saved", ctx.language_of(user_id)))
        raise events.StopPropagation

    # ------------------------------------------------------- member tools
    @client.on(events.NewMessage(pattern=WARN_PATTERN))
    @guard(ctx, group_only=True)
    async def warn(event: events.NewMessage.Event) -> None:
        await _warn_command(ctx, event)

    @client.on(events.NewMessage(pattern=UNWARN_PATTERN))
    @guard(ctx, group_only=True)
    async def unwarn(event: events.NewMessage.Event) -> None:
        await _require_chat_admin(ctx, event)
        language = ctx.language_of(event.sender_id)
        target = await _resolve_target(ctx, event, event.pattern_match.group(1))
        if target is None:
            await reply(event, ctx.tr("mod.target_not_found", language))
            return
        removed = ctx.repo.clear_warnings(int(event.chat_id), target)
        name = await _name(ctx, target)
        ctx.repo.audit(
            int(event.sender_id), "unwarn", target=str(target), details={"chat_id": event.chat_id, "removed": removed}
        )
        await reply(event, ctx.tr("mod.warn_cleared", language, target=escape_html(name), count=removed))

    @client.on(events.NewMessage(pattern=WARNS_PATTERN))
    @guard(ctx, group_only=True)
    async def warns(event: events.NewMessage.Event) -> None:
        language = ctx.language_of(event.sender_id)
        target = await _resolve_target(ctx, event, event.pattern_match.group(1)) or int(event.sender_id)
        count = ctx.repo.warning_count(int(event.chat_id), target)
        name = await _name(ctx, target)
        await reply(event, ctx.tr("mod.warning_list", language, target=escape_html(name), count=count))

    @client.on(events.NewMessage(pattern=MUTE_PATTERN))
    @guard(ctx, group_only=True)
    async def mute(event: events.NewMessage.Event) -> None:
        await _apply_sanction(ctx, event, "mute")

    @client.on(events.NewMessage(pattern=UNMUTE_PATTERN))
    @guard(ctx, group_only=True)
    async def unmute(event: events.NewMessage.Event) -> None:
        await _apply_sanction(ctx, event, "unmute")

    @client.on(events.NewMessage(pattern=BAN_PATTERN))
    @guard(ctx, group_only=True)
    async def ban(event: events.NewMessage.Event) -> None:
        await _apply_sanction(ctx, event, "ban")

    @client.on(events.NewMessage(pattern=UNBAN_PATTERN))
    @guard(ctx, group_only=True)
    async def unban(event: events.NewMessage.Event) -> None:
        await _apply_sanction(ctx, event, "unban")

    @client.on(events.NewMessage(pattern=KICK_PATTERN))
    @guard(ctx, group_only=True)
    async def kick(event: events.NewMessage.Event) -> None:
        await _apply_sanction(ctx, event, "kick")

    @client.on(events.NewMessage(pattern=PURGE_PATTERN))
    @guard(ctx, group_only=True)
    async def purge(event: events.NewMessage.Event) -> None:
        await _purge(ctx, event)

    @client.on(events.NewMessage(pattern=PIN_PATTERN))
    @guard(ctx, group_only=True)
    async def pin(event: events.NewMessage.Event) -> None:
        await _require_chat_admin(ctx, event, need_delete=False)
        language = ctx.language_of(event.sender_id)
        if not event.reply_to_msg_id:
            await reply(event, ctx.tr("mod.need_reply", language))
            return
        try:
            await ctx.require_client().pin_message(event.chat_id, event.reply_to_msg_id, notify=False)
            ctx.repo.audit(
                int(event.sender_id), "pin", target=str(event.reply_to_msg_id), details={"chat_id": event.chat_id}
            )
            await reply(event, ctx.tr("mod.pinned", language))
        except Exception as exc:
            logger.info("Pin failed: %s", exc)
            await reply(event, ctx.tr("mod.bot_no_rights", language))

    # ------------------------------------------------------------ callbacks
    @client.on(events.CallbackQuery(data=CB_GROUP_ANTISPAM))
    @guard(ctx, staff_only=True, group_only=True)
    async def toggle_antispam(event: events.CallbackQuery.Event) -> None:
        chat_id = int(event.chat_id)
        current = ctx.repo.group_feature_enabled(chat_id, "anti_spam", True)
        ctx.repo.set_group_feature(chat_id, "anti_spam", not current)
        ctx.repo.audit(int(event.sender_id), "toggle_antispam", target=str(chat_id), details={"enabled": not current})
        await event.answer("🛡")
        await show_panel(ctx, event, mode="callback")

    @client.on(events.CallbackQuery(data=CB_GROUP_WELCOME))
    @guard(ctx, staff_only=True, group_only=True)
    async def toggle_welcome(event: events.CallbackQuery.Event) -> None:
        chat_id = int(event.chat_id)
        current = ctx.repo.group_feature_enabled(chat_id, "welcome", True)
        ctx.repo.set_group_feature(chat_id, "welcome", not current)
        ctx.repo.audit(int(event.sender_id), "toggle_welcome", target=str(chat_id), details={"enabled": not current})
        await event.answer("👋")
        await show_panel(ctx, event, mode="callback")

    @client.on(events.CallbackQuery(data=CB_GROUP_RULES))
    @guard(ctx, staff_only=True, group_only=True)
    async def rules_callback(event: events.CallbackQuery.Event) -> None:
        user_id = int(event.sender_id)
        language = ctx.language_of(user_id)
        ctx.states.set(user_id, STATE_GROUP_RULES, chat_id=int(event.chat_id))
        await event.answer()
        await edit(event, ctx.tr("group.rules_prompt", language))

    @client.on(events.CallbackQuery(data=CB_GROUP_STATS))
    @guard(ctx, staff_only=True)
    async def stats_callback(event: events.CallbackQuery.Event) -> None:
        user_id = int(event.sender_id)
        language = ctx.language_of(user_id)
        await event.answer()
        await edit(
            event,
            stats.render(ctx, language),
            buttons=[[Button.inline(ctx.tr("common.back", language), CB_HOME)]],
        )

    # ------------------------------------------------------------- welcome
    @client.on(events.ChatAction())
    @guard(ctx, group_only=True, ignore_when_disabled=False)
    async def welcome(event: events.ChatAction.Event) -> None:
        if not (event.user_joined or event.user_added):
            return
        chat_id = int(event.chat_id)
        ctx.repo.upsert_group(chat_id)
        if not ctx.repo.group_feature_enabled(chat_id, "welcome", True):
            return
        new_user = await event.get_user()
        if new_user is None:
            return
        ctx.repo.upsert_user(
            int(new_user.id),
            username=getattr(new_user, "username", None),
            first_name=getattr(new_user, "first_name", None),
        )
        language = ctx.language_of(int(new_user.id))
        try:
            await event.reply(
                ctx.tr("group.welcome_message", language, name=full_mention(new_user)),
                parse_mode="html",
                link_preview=False,
            )
        except Exception as exc:
            logger.debug("Welcome message failed in %s: %s", chat_id, exc)

    # ------------------------------------------------------------ anti-spam
    @client.on(events.NewMessage(incoming=True, func=lambda event: event.is_group))
    @guard(ctx, group_only=True, ignore_when_disabled=False)
    async def antispam(event: events.NewMessage.Event) -> None:
        if ctx.antispam is None or not ctx.settings.feature_antispam:
            return
        chat_id = int(event.chat_id)
        user_id = int(event.sender_id)
        if not ctx.repo.group_feature_enabled(chat_id, "anti_spam", True):
            return
        if ctx.roles.is_staff(user_id) or await _is_chat_admin_cached(ctx, event, chat_id, user_id):
            return

        text = event.raw_text or ""
        verdict = ctx.antispam.check(
            chat_id=chat_id,
            user_id=user_id,
            text=text,
            is_new_member=ctx.antispam.is_new_member(user_id),
        )
        if not verdict.blocked:
            return
        logger.info(
            "Anti-spam hit in %s by %s (%s)",
            chat_id,
            user_id,
            verdict.reason_key,
            extra={"chat_id": chat_id, "user_id": user_id},
        )
        await ctx.antispam.enforce(ctx, event, verdict)
        raise events.StopPropagation


# --------------------------------------------------------------------------- #
# Implementation details
# --------------------------------------------------------------------------- #
async def show_panel(ctx: AppContext, event: Any, *, mode: str = "callback") -> None:
    """Render the group panel."""
    chat_id = int(event.chat_id)
    ctx.repo.upsert_group(chat_id)
    language = ctx.language_of(event.sender_id)
    title = ""
    try:
        chat = await event.get_chat()
        title = escape_html(display_name(chat))
    except Exception:  # pragma: no cover - chat may be inaccessible
        title = str(chat_id)
    antispam = ctx.repo.group_feature_enabled(chat_id, "anti_spam", True)
    welcome_enabled = ctx.repo.group_feature_enabled(chat_id, "welcome", True)
    text = ctx.tr(
        "group.panel_title",
        language,
        title=title,
        antispam=ctx.tr("group.on" if antispam else "group.off", language),
        welcome=ctx.tr("group.on" if welcome_enabled else "group.off", language),
    )
    buttons = group_panel(ctx, language, antispam=antispam, welcome=welcome_enabled)
    if mode == "callback":
        await event.answer()
        await edit(event, text, buttons=buttons)
    else:
        await event.respond(text, buttons=buttons, parse_mode="html", link_preview=False)


async def _require_chat_admin(ctx: AppContext, event: Any, *, need_delete: bool = True) -> None:
    """Ensure the actor is a chat admin *and* the bot has the needed rights."""
    from bot.errors import AccessDenied

    user_id = int(event.sender_id)
    if not await ctx.roles.is_chat_admin(ctx.require_client(), int(event.chat_id), user_id):
        raise AccessDenied("Group administrator rights required", required_role="chat_admin")

    if not need_delete or ctx.is_owner(user_id):
        return
    try:
        me = await ctx.require_client().get_permissions(int(event.chat_id), "me")
        if not getattr(me, "delete_messages", False):
            language = ctx.language_of(user_id)
            await reply(event, ctx.tr("mod.bot_no_rights", language))
            raise events.StopPropagation
    except events.StopPropagation:
        raise
    except Exception as exc:  # pragma: no cover - permission lookup failures
        logger.debug("Bot permission lookup failed: %s", exc)


async def _is_chat_admin_cached(ctx: AppContext, event: Any, chat_id: int, user_id: int, *, ttl: float = 300.0) -> bool:
    """Admin check with a short TTL cache so anti-spam stays cheap."""
    key = (int(chat_id), int(user_id))
    moment = time.monotonic()
    cached = ctx.admin_cache.get(key)
    if cached is not None and abs(moment - cached) < ttl:
        return cached > 0
    try:
        permissions = await ctx.require_client().get_permissions(int(chat_id), int(user_id))
        is_admin = bool(getattr(permissions, "is_admin", False) or getattr(permissions, "is_creator", False))
    except Exception:
        is_admin = False
    ctx.admin_cache[key] = moment if is_admin else -moment
    return is_admin


async def _resolve_target(ctx: AppContext, event: Any, raw: str | None) -> int | None:
    """Resolve a moderation target from a reply, id or @username."""
    if event.reply_to_msg_id:
        target_message = await event.get_reply_message()
        if target_message is not None and target_message.sender_id is not None:
            return int(target_message.sender_id)
    if not raw:
        return None
    candidate = raw.strip().split()[0]
    try:
        if candidate.lstrip("-").isdigit():
            return int(candidate)
        if candidate.startswith("@"):
            entity = await ctx.require_client().get_entity(candidate)
            return int(entity.id)
    except Exception as exc:
        logger.debug("Target resolution failed for %r: %s", raw, exc)
    return None


def _reason_of(raw: str | None, target: int | None) -> str:
    """Extract the free-text reason, dropping the target token if present."""
    if not raw:
        return ""
    parts = raw.strip().split(maxsplit=1)
    if target is not None and parts and (parts[0].lstrip("-").isdigit() or parts[0].startswith("@")):
        return parts[1].strip() if len(parts) > 1 else ""
    return raw.strip()


async def _name(ctx: AppContext, user_id: int) -> str:
    try:
        entity = await ctx.require_client().get_entity(user_id)
        return display_name(entity)
    except Exception:
        return str(user_id)


async def _warn_command(ctx: AppContext, event: Any) -> None:
    await _require_chat_admin(ctx, event, need_delete=False)
    language = ctx.language_of(event.sender_id)
    raw = event.pattern_match.group(1)
    target = await _resolve_target(ctx, event, raw)
    if target is None:
        await reply(event, ctx.tr("mod.target_not_found", language))
        return
    chat_id = int(event.chat_id)
    if target == int(event.sender_id):
        await reply(event, ctx.tr("mod.self_target", language))
        return
    if ctx.is_owner(target) or ctx.roles.is_staff(target):
        await reply(event, ctx.tr("mod.admin_immune", language))
        return

    reason = _reason_of(raw, target) or ctx.tr("mod.reason_default", language)
    count = ctx.repo.add_warning(chat_id, target, int(event.sender_id), reason)
    ctx.repo.increment_counter("warnings")
    name = await _name(ctx, target)
    ctx.repo.audit(
        int(event.sender_id), "warn", target=str(target), details={"chat_id": chat_id, "reason": reason, "count": count}
    )

    moderation = ModerationService(ctx.repo)
    limit = ctx.settings.antispam_warn_limit
    ban_limit = ctx.settings.antispam_ban_limit
    await reply(
        event, ctx.tr("mod.warned", language, target=escape_html(name), count=count, reason=escape_html(reason))
    )

    if count >= ban_limit:
        await moderation.ban(ctx.client, chat_id, target)
        await reply(event, ctx.tr("mod.ban_limit_reached", language, target=escape_html(name)))
    elif count >= limit:
        await moderation.mute(ctx.client, chat_id, target, ctx.settings.antispam_mute_minutes)
        await reply(event, ctx.tr("mod.warn_limit_reached", language, target=escape_html(name)))


async def _apply_sanction(ctx: AppContext, event: Any, action: str) -> None:
    await _require_chat_admin(ctx, event)
    language = ctx.language_of(event.sender_id)
    raw = event.pattern_match.group(1)
    target = await _resolve_target(ctx, event, raw)
    if target is None:
        await reply(event, ctx.tr("mod.target_not_found", language))
        return
    if target == int(event.sender_id):
        await reply(event, ctx.tr("mod.self_target", language))
        return
    if action in {"ban", "mute", "kick"} and (ctx.is_owner(target) or ctx.roles.is_staff(target)):
        await reply(event, ctx.tr("mod.admin_immune", language))
        return

    chat_id = int(event.chat_id)
    reason = _reason_of(raw, target) or ctx.tr("mod.reason_default", language)
    moderation = ModerationService(ctx.repo)
    name = await _name(ctx, target)
    safe_name = escape_html(name)

    if action == "mute":
        minutes = _extract_minutes(raw) or ctx.settings.antispam_mute_minutes
        result = await moderation.mute(ctx.client, chat_id, target, minutes)
        text = ctx.tr(
            "mod.muted",
            language,
            target=safe_name,
            duration=humanize_delta(timedelta(minutes=minutes), language=language),
            reason=escape_html(reason),
        )
    elif action == "unmute":
        result = await moderation.unmute(ctx.client, chat_id, target)
        text = ctx.tr("mod.unmuted", language, target=safe_name)
    elif action == "ban":
        result = await moderation.ban(ctx.client, chat_id, target)
        text = ctx.tr("mod.banned", language, target=safe_name, reason=escape_html(reason))
    elif action == "unban":
        result = await moderation.unban(ctx.client, chat_id, target)
        text = ctx.tr("mod.unbanned", language, target=safe_name)
    elif action == "kick":
        result = await moderation.kick(ctx.client, chat_id, target)
        text = ctx.tr("mod.kicked", language, target=safe_name)
    else:  # pragma: no cover - programming error
        raise ValueError(f"Unknown sanction: {action}")

    if not result.ok:
        logger.warning("%s failed for %s in %s: %s", action, target, chat_id, result.reason)
        await reply(event, ctx.tr("mod.bot_no_rights", language))
        return

    ctx.repo.audit(int(event.sender_id), action, target=str(target), details={"chat_id": chat_id, "reason": reason})
    ctx.repo.increment_counter(f"mod_{action}")
    await reply(event, text)
    await ctx.log_to_chat(
        f"🛡 {action}", f"chat <code>{chat_id}</code> · user <code>{target}</code> · by <code>{event.sender_id}</code>"
    )


_DURATION_RE = re.compile(r"(\d+)\s*(minutes?|mins?|m|hours?|hrs?|h|days?|d|دقیقه|ساعت|روز)?\b", re.IGNORECASE)
_MINUTE_UNITS = {"m", "min", "mins", "minute", "minutes", "دقیقه"}
_HOUR_UNITS = {"h", "hr", "hrs", "hour", "hours", "ساعت"}
_DAY_UNITS = {"d", "day", "days", "روز"}


def _extract_minutes(raw: str | None) -> int | None:
    """Support ``/mute 30``, ``/mute 30m``, ``/mute 2h`` and ``/mute 1d``."""
    if not raw:
        return None
    match = _DURATION_RE.search(raw)
    if not match:
        return None
    value = int(match.group(1))
    if value <= 0:
        return None
    unit = (match.group(2) or "").lower()
    if unit in _HOUR_UNITS:
        return value * 60
    if unit in _DAY_UNITS:
        return value * 60 * 24
    if unit in _MINUTE_UNITS or unit == "":
        return value
    return value


async def _purge(ctx: AppContext, event: Any) -> None:
    await _require_chat_admin(ctx, event)
    language = ctx.language_of(event.sender_id)
    chat_id = int(event.chat_id)
    raw_count = event.pattern_match.group(1)
    message_ids: list[int] = []

    if event.reply_to_msg_id:
        first = int(event.reply_to_msg_id)
        message_ids = list(range(first, int(event.id) + 1))
    else:
        limit = min(int(raw_count or 10), 100)
        history = await ctx.require_client().get_messages(chat_id, limit=limit + 1)
        message_ids = [message.id for message in history if message.id != event.id]

    deleted = 0
    for chunk_start in range(0, len(message_ids), 100):
        chunk = message_ids[chunk_start : chunk_start + 100]
        result = await ModerationService(ctx.repo).delete_messages(ctx.require_client(), chat_id, chunk)
        if result.ok:
            deleted += len(chunk)
        else:
            break

    with contextlib.suppress(Exception):  # best effort: the bot may lack the right
        await event.delete()
    await event.respond(ctx.tr("mod.purged", language, count=deleted), parse_mode="html")
    ctx.repo.audit(int(event.sender_id), "purge", target=str(chat_id), details={"count": deleted})
    logger.info("Purged %s messages in %s", deleted, chat_id)
