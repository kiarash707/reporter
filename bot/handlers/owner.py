"""Owner-only commands: broadcast, maintenance, audit, backup, staff, import."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from telethon import Button, TelegramClient, events

from bot.context import AppContext
from bot.handlers.guard import edit, guard, reply
from bot.keyboards import (
    CB_CLOSE,
    CB_HOME,
    CB_OWN_AUDIT,
    CB_OWN_BACKUP,
    CB_OWN_BROADCAST,
    CB_OWN_BROADCAST_GO,
    CB_OWN_IMPORT,
    CB_OWN_STAFF,
    CB_OWN_TOGGLE,
    owner_panel,
)
from bot.services.backup import create_backup, latest_backup
from bot.services.broadcast import BroadcastService
from bot.utils.text import bullet_list, escape_html, truncate

logger = logging.getLogger("bot.handlers.owner")

STATE_BROADCAST = "owner_broadcast"

PANEL_PATTERN = r"^/adminpanel(?:@[\w_]+)?$"
BROADCAST_PATTERN = r"^/broadcast(?:@[\w_]+)?(?:\s|$)"
TOGGLE_PATTERN = r"^/togglebot(?:@[\w_]+)?$"
MAINTENANCE_PATTERN = r"^/maintenance(?:@[\w_]+)?$"
AUDIT_PATTERN = r"^/audit(?:@[\w_]+)?$"
BACKUP_PATTERN = r"^/backup(?:@[\w_]+)?$"
IMPORT_PATTERN = r"^/importdb(?:@[\w_]+)?\s+(.+)$"
IMPORT_HELP_PATTERN = r"^/importdb(?:@[\w_]+)?$"
RELOAD_PATTERN = r"^/reloadlocales(?:@[\w_]+)?$"
STAFF_PATTERN = r"^/staff(?:@[\w_]+)?$"
ADD_STAFF_PATTERN = r"^/addstaff(?:@[\w_]+)?\s+(-?\d+)$"
DEL_STAFF_PATTERN = r"^/delstaff(?:@[\w_]+)?\s+(-?\d+)$"
BLOCK_PATTERN = r"^/(block|unblock)(?:@[\w_]+)?\s+(-?\d+)(?:\s+(.+))?$"


def register(client: TelegramClient, ctx: AppContext) -> None:
    """Attach owner handlers."""

    @client.on(events.NewMessage(pattern=PANEL_PATTERN))
    @guard(ctx, owner_only=True, private_only=True)
    async def panel(event: events.NewMessage.Event) -> None:
        await show_panel(ctx, event, mode="message")

    @client.on(events.NewMessage(pattern=BROADCAST_PATTERN))
    @guard(ctx, owner_only=True, private_only=True)
    async def broadcast_command(event: events.NewMessage.Event) -> None:
        await _begin_broadcast(ctx, event)

    @client.on(events.NewMessage(pattern=TOGGLE_PATTERN))
    @guard(ctx, owner_only=True)
    async def toggle_bot(event: events.NewMessage.Event) -> None:
        language = ctx.language_of(event.sender_id)
        enabled = ctx.repo.get_flag("bot_enabled", True)
        ctx.repo.set_flag("bot_enabled", not enabled)
        ctx.repo.audit(int(event.sender_id), "toggle_bot", target=str(not enabled))
        await reply(event, ctx.tr("owner.bot_on" if not enabled else "owner.bot_off", language))

    @client.on(events.NewMessage(pattern=MAINTENANCE_PATTERN))
    @guard(ctx, owner_only=True)
    async def maintenance(event: events.NewMessage.Event) -> None:
        language = ctx.language_of(event.sender_id)
        active = ctx.repo.get_flag("maintenance", False)
        ctx.repo.set_flag("maintenance", not active)
        ctx.repo.audit(int(event.sender_id), "maintenance", target=str(not active))
        await reply(event, "🛠 " + ("off" if active else "on") + "\n" + ctx.tr("common.done", language))

    @client.on(events.NewMessage(pattern=AUDIT_PATTERN))
    @guard(ctx, owner_only=True)
    async def audit(event: events.NewMessage.Event) -> None:
        await _send_audit(ctx, event, mode="message")

    @client.on(events.NewMessage(pattern=BACKUP_PATTERN))
    @guard(ctx, owner_only=True)
    async def backup(event: events.NewMessage.Event) -> None:
        await _do_backup(ctx, event, mode="message")

    @client.on(events.NewMessage(pattern=IMPORT_PATTERN))
    @guard(ctx, owner_only=True)
    async def import_legacy(event: events.NewMessage.Event) -> None:
        await _do_import(ctx, event, event.pattern_match.group(1).strip(), mode="message")

    @client.on(events.NewMessage(pattern=RELOAD_PATTERN))
    @guard(ctx, owner_only=True)
    async def reload_locales(event: events.NewMessage.Event) -> None:
        counts = ctx.i18n.load()
        ctx.repo.audit(int(event.sender_id), "reload_locales", details=counts)
        await reply(event, f"♻️ locales reloaded: {counts}")

    @client.on(events.NewMessage(pattern=STAFF_PATTERN))
    @guard(ctx, owner_only=True)
    async def staff_list(event: events.NewMessage.Event) -> None:
        language = ctx.language_of(event.sender_id)
        staff = sorted(ctx.repo.staff_ids())
        await reply(event, ctx.tr("owner.staff_list", language, staff=", ".join(str(value) for value in staff) or "-"))

    @client.on(events.NewMessage(pattern=ADD_STAFF_PATTERN))
    @guard(ctx, owner_only=True)
    async def add_staff(event: events.NewMessage.Event) -> None:
        language = ctx.language_of(event.sender_id)
        target = int(event.pattern_match.group(1))
        added = ctx.repo.add_staff(target, actor_id=int(event.sender_id))
        if added:
            await reply(event, ctx.tr("owner.staff_added", language, user_id=target))
        else:
            await reply(event, ctx.tr("common.done", language) + " (already staff)")

    @client.on(events.NewMessage(pattern=DEL_STAFF_PATTERN))
    @guard(ctx, owner_only=True)
    async def del_staff(event: events.NewMessage.Event) -> None:
        language = ctx.language_of(event.sender_id)
        target = int(event.pattern_match.group(1))
        removed = ctx.repo.remove_staff(target, actor_id=int(event.sender_id))
        await reply(
            event,
            ctx.tr("owner.staff_removed", language, user_id=target)
            if removed
            else ctx.tr("common.invalid_input", language),
        )

    @client.on(events.NewMessage(pattern=BLOCK_PATTERN))
    @guard(ctx, owner_only=True)
    async def block_user(event: events.NewMessage.Event) -> None:
        action, raw_target, reason = (
            event.pattern_match.group(1),
            int(event.pattern_match.group(2)),
            event.pattern_match.group(3),
        )
        blocked = action == "block"
        if ctx.is_owner(raw_target):
            await reply(event, ctx.tr("common.not_allowed", ctx.language_of(event.sender_id)))
            return
        ctx.repo.set_blocked(raw_target, blocked, reason=reason)
        ctx.repo.audit(int(event.sender_id), action, target=str(raw_target), details={"reason": reason})
        await reply(event, f"✅ {action} → <code>{raw_target}</code>")

    @client.on(events.NewMessage(pattern=IMPORT_HELP_PATTERN))
    @guard(ctx, owner_only=True)
    async def import_help(event: events.NewMessage.Event) -> None:
        await reply(event, ctx.tr("owner.import_help", ctx.language_of(event.sender_id)))

    # ------------------------------------------------------------ broadcast
    @client.on(events.NewMessage(incoming=True, func=lambda event: event.is_private))
    @guard(ctx, owner_only=True, private_only=True, ignore_when_disabled=False)
    async def broadcast_text(event: events.NewMessage.Event) -> None:
        if not ctx.states.is_(int(event.sender_id), STATE_BROADCAST):
            return
        text = (event.raw_text or "").strip()
        if len(text) < 2:
            raise events.StopPropagation
        targets = ctx.repo.broadcast_targets()
        ctx.states.update(int(event.sender_id), text=text)
        await event.respond(
            ctx.tr("owner.broadcast_confirm", ctx.language_of(event.sender_id), total=len(targets)),
            buttons=[
                [Button.inline("🚀 " + ctx.tr("common.done", ctx.language_of(event.sender_id)), CB_OWN_BROADCAST_GO)],
                [Button.inline(ctx.tr("common.cancel", ctx.language_of(event.sender_id)), CB_CLOSE)],
            ],
            parse_mode="html",
        )
        raise events.StopPropagation

    # ------------------------------------------------------------ callbacks
    @client.on(events.CallbackQuery(data=CB_OWN_TOGGLE))
    @guard(ctx, owner_only=True)
    async def toggle_callback(event: events.CallbackQuery.Event) -> None:
        await event.answer("🔌")
        enabled = ctx.repo.get_flag("bot_enabled", True)
        ctx.repo.set_flag("bot_enabled", not enabled)
        ctx.repo.audit(int(event.sender_id), "toggle_bot", target=str(not enabled))
        await show_panel(ctx, event, mode="callback")

    @client.on(events.CallbackQuery(data=CB_OWN_BROADCAST))
    @guard(ctx, owner_only=True)
    async def broadcast_callback(event: events.CallbackQuery.Event) -> None:
        await _begin_broadcast(ctx, event, mode="callback")

    @client.on(events.CallbackQuery(data=CB_OWN_BROADCAST_GO))
    @guard(ctx, owner_only=True, ignore_when_disabled=False)
    async def broadcast_go(event: events.CallbackQuery.Event) -> None:
        user_id = int(event.sender_id)
        state = ctx.states.get(user_id)
        text = (state.data.get("text") if state else None) or ""
        if not text:
            await event.answer("❌")
            return
        ctx.states.clear(user_id)
        language = ctx.language_of(user_id)
        service = BroadcastService(
            ctx.repo, delay=ctx.settings.broadcast_delay, concurrency=ctx.settings.broadcast_concurrency
        )
        await event.answer("🚀")
        status_message = await edit(event, ctx.tr("owner.broadcast_progress", language, sent=0, total=0), buttons=None)

        async def progress(sent: int, total: int) -> None:
            try:
                await status_message.edit(
                    ctx.tr("owner.broadcast_progress", language, sent=sent, total=total), parse_mode="html"
                )
            except Exception as exc:  # pragma: no cover - editing may fail on flood
                logger.debug("Broadcast progress edit failed: %s", exc)

        report = await service.send(ctx.client, text, progress=progress)
        ctx.repo.audit(user_id, "broadcast", details=report.as_dict())
        await status_message.edit(
            ctx.tr("owner.broadcast_done", language, sent=report.sent, failed=report.failed + report.blocked),
            buttons=[[Button.inline(ctx.tr("menu.back_to_menu", language), CB_HOME)]],
            parse_mode="html",
        )

    @client.on(events.CallbackQuery(data=CB_OWN_AUDIT))
    @guard(ctx, owner_only=True)
    async def audit_callback(event: events.CallbackQuery.Event) -> None:
        await _send_audit(ctx, event, mode="callback")

    @client.on(events.CallbackQuery(data=CB_OWN_BACKUP))
    @guard(ctx, owner_only=True)
    async def backup_callback(event: events.CallbackQuery.Event) -> None:
        await _do_backup(ctx, event, mode="callback")

    @client.on(events.CallbackQuery(data=CB_OWN_IMPORT))
    @guard(ctx, owner_only=True)
    async def import_callback(event: events.CallbackQuery.Event) -> None:
        await event.answer()
        await edit(event, ctx.tr("owner.import_help", ctx.language_of(event.sender_id)))

    @client.on(events.CallbackQuery(data=CB_OWN_STAFF))
    @guard(ctx, owner_only=True)
    async def staff_callback(event: events.CallbackQuery.Event) -> None:
        user_id = int(event.sender_id)
        language = ctx.language_of(user_id)
        staff = sorted(ctx.repo.staff_ids())
        await event.answer()
        await edit(
            event,
            ctx.tr("owner.staff_list", language, staff=", ".join(str(value) for value in staff) or "-"),
            buttons=[
                [Button.inline(ctx.tr("menu.back_to_menu", language), CB_HOME)],
            ],
        )


# --------------------------------------------------------------------------- #
# Shared helpers (also used by common.py)
# --------------------------------------------------------------------------- #
async def show_panel(ctx: AppContext, event: Any, *, mode: str = "callback") -> None:
    """Render the owner panel."""
    user_id = int(event.sender_id)
    language = ctx.language_of(user_id)
    enabled = ctx.repo.get_flag("bot_enabled", True)
    text = ctx.tr(
        "owner.title",
        language,
        bot_status="🟢 on" if enabled else "🔴 off",
    )
    buttons = owner_panel(ctx, language, bot_enabled=enabled)
    if mode == "callback":
        await event.answer()
        await edit(event, text, buttons=buttons)
    else:
        await event.respond(text, buttons=buttons, parse_mode="html")


async def _begin_broadcast(ctx: AppContext, event: Any, *, mode: str = "message") -> None:
    user_id = int(event.sender_id)
    language = ctx.language_of(user_id)
    if not ctx.settings.feature_broadcast:
        text = ctx.tr("common.feature_disabled", language)
    else:
        ctx.states.set(user_id, STATE_BROADCAST)
        text = ctx.tr("owner.broadcast_prompt", language)
    if mode == "callback":
        await event.answer()
        await edit(event, text)
    else:
        await reply(event, text)


async def _send_audit(ctx: AppContext, event: Any, *, mode: str = "message") -> None:
    user_id = int(event.sender_id)
    language = ctx.language_of(user_id)
    entries = ctx.repo.recent_audit(15)
    if not entries:
        text = ctx.tr("owner.audit_empty", language)
    else:
        rows = [
            ctx.tr(
                "owner.audit_item",
                language,
                time=str(entry["created_at"])[11:16] if entry["created_at"] else "-",
                actor=entry["actor_id"] if entry["actor_id"] is not None else "-",
                action=escape_html(str(entry["action"])),
                target=escape_html(truncate(str(entry["target"] or "-"), 24)),
            )
            for entry in entries
        ]
        text = ctx.tr("owner.audit_header", language) + "\n" + bullet_list(rows)
    buttons = [[Button.inline(ctx.tr("menu.back_to_menu", language), CB_HOME)]]
    if mode == "callback":
        await event.answer()
        await edit(event, text, buttons=buttons)
    else:
        await event.respond(text, buttons=buttons, parse_mode="html", link_preview=False)


async def _do_backup(ctx: AppContext, event: Any, *, mode: str = "message") -> None:
    user_id = int(event.sender_id)
    language = ctx.language_of(user_id)
    try:
        result = create_backup(ctx.settings, ctx.repo)
        text = ctx.tr("owner.backup_done", language, path=str(result.path), size=result.size_kb)
        ctx.repo.audit(user_id, "backup", target=str(result.path))
    except Exception as exc:
        logger.error("Backup failed: %s", exc, exc_info=True)
        latest = latest_backup(ctx.settings)
        text = f"❌ {exc}" + (f"\n(latest: {latest.name})" if latest else "")
    if mode == "callback":
        await event.answer()
        await edit(event, text)
    else:
        await reply(event, text)


async def _do_import(ctx: AppContext, event: Any, raw_path: str, *, mode: str = "message") -> None:
    user_id = int(event.sender_id)
    language = ctx.language_of(user_id)
    path = ctx.settings.resolve(Path(raw_path.strip()))
    if not path.is_file():
        text = ctx.tr("owner.import_missing", language, path=str(path))
    else:
        try:
            summary = ctx.repo.import_legacy_json(path)
            ctx.repo.audit(user_id, "legacy_import", target=str(path), details=summary)
            text = ctx.tr(
                "owner.import_done",
                language,
                users=summary["users"],
                languages=summary["languages"],
                blocked=summary["blocked"],
                tickets=summary["tickets"],
            )
        except Exception as exc:
            logger.error("Legacy import failed: %s", exc, exc_info=True)
            text = f"❌ {exc}"
    if mode == "callback":
        await event.answer()
        await edit(event, text)
    else:
        await reply(event, text)
