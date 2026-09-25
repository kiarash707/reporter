"""Support tickets: user flow, staff replies and lifecycle management."""

from __future__ import annotations

import contextlib
import logging
import re
from typing import Any

from telethon import TelegramClient, events

from bot.context import AppContext
from bot.handlers.guard import edit, guard, reply
from bot.keyboards import (
    CB_TICKET_CLOSE,
    CB_TICKET_REPLY,
    CB_TICKET_VIEW,
    staff_ticket_actions,
    ticket_detail_actions,
    tickets_menu,
)
from bot.storage.repository import TICKET_ANSWERED, TICKET_CLOSED, TICKET_OPEN
from bot.utils.text import bullet_list, escape_html, split_message, title_case_safe, truncate

logger = logging.getLogger("bot.handlers.tickets")

STATE_SUBJECT = "ticket_subject"
STATE_BODY = "ticket_body"
STATE_STAFF_REPLY = "ticket_staff_reply"

SUBJECT_MAX = 120
BODY_MAX = 3500
FLOW_STATES = (STATE_SUBJECT, STATE_BODY, STATE_STAFF_REPLY)

TICKET_PATTERN = r"^/ticket(?:@[\w_]+)?(?:\s|$)"
MY_TICKETS_PATTERN = r"^/mytickets(?:@[\w_]+)?(?:\s|$)"
STAFF_LIST_PATTERN = r"^/tickets(?:@[\w_]+)?(?:\s|$)"
REPLY_PATTERN = r"^/reply(?:@[\w_]+)?(?:\s+(\d+))?\s*$"
CLOSE_PATTERN = r"^/close(?:@[\w_]+)?\s*(\d+)?\s*$"
OPEN_CMD_PATTERN = r"^/open(?:@[\w_]+)?\s*(\d+)?\s*$"


def register(client: TelegramClient, ctx: AppContext) -> None:
    """Attach ticket handlers."""

    # ------------------------------------------------------------ user flow
    @client.on(events.NewMessage(pattern=TICKET_PATTERN, func=lambda event: event.is_private))
    @guard(ctx, private_only=True)
    async def open_ticket(event: events.NewMessage.Event) -> None:
        await start_ticket_flow(ctx, event, int(event.sender_id), mode="message")

    @client.on(events.NewMessage(pattern=MY_TICKETS_PATTERN))
    @guard(ctx)
    async def my_tickets(event: events.NewMessage.Event) -> None:
        await show_my_tickets(ctx, event, int(event.sender_id), mode="message")

    @client.on(events.NewMessage(incoming=True, func=lambda event: event.is_private))
    @guard(ctx, private_only=True, ignore_when_disabled=False)
    async def ticket_flow_text(event: events.NewMessage.Event) -> None:
        """Advance the active ticket conversation; ignore anything else."""
        consumed = await advance_ticket_flow(ctx, event, int(event.sender_id), event.raw_text or "")
        if consumed:
            raise events.StopPropagation

    # ---------------------------------------------------------------- staff
    @client.on(events.NewMessage(pattern=STAFF_LIST_PATTERN))
    @guard(ctx, staff_only=True)
    async def list_open_tickets(event: events.NewMessage.Event) -> None:
        language = ctx.language_of(event.sender_id)
        tickets = ctx.repo.list_tickets(status=TICKET_OPEN, limit=15)
        if not tickets:
            await reply(event, ctx.tr("ticket.open_list_empty", language))
            return
        rows = []
        for ticket in tickets:
            rows.append(
                ctx.tr(
                    "ticket.item",
                    language,
                    ticket_id=ticket["id"],
                    status=ctx.tr(f"ticket.status_{ticket['status']}", language),
                    subject=escape_html(truncate(str(ticket["subject"]), 40)),
                )
            )
        buttons = [[staff_ticket_actions(ctx, language, int(ticket["id"]))[0]] for ticket in tickets[:10]]
        await event.respond(
            ctx.tr("ticket.open_list_header", language) + "\n" + bullet_list(rows),
            buttons=buttons,
            parse_mode="html",
            link_preview=False,
        )

    @client.on(events.NewMessage(pattern=REPLY_PATTERN))
    @guard(ctx, staff_only=True)
    async def reply_command(event: events.NewMessage.Event) -> None:
        ticket_id = int(event.pattern_match.group(1) or 0)
        await _begin_staff_reply(ctx, event, int(event.sender_id), ticket_id, mode="message")

    @client.on(events.NewMessage(pattern=CLOSE_PATTERN))
    @guard(ctx)
    async def close_command(event: events.NewMessage.Event) -> None:
        ticket_id = int(event.pattern_match.group(1) or 0)
        if not ticket_id:
            await reply(event, ctx.tr("common.invalid_input", ctx.language_of(event.sender_id)))
            return
        await _close_ticket(ctx, event, int(event.sender_id), ticket_id, mode="message")

    @client.on(events.NewMessage(pattern=OPEN_CMD_PATTERN))
    @guard(ctx, staff_only=True)
    async def open_command(event: events.NewMessage.Event) -> None:
        ticket_id = int(event.pattern_match.group(1) or 0)
        await _reopen_ticket(ctx, event, int(event.sender_id), ticket_id)

    # ------------------------------------------------------------ callbacks
    # Telethon matches callback data either exactly (bytes) or via a bytes
    # regex; the "<action>:<id>" buttons therefore use patterns.
    @client.on(events.CallbackQuery(pattern=re.compile(rb"^" + CB_TICKET_REPLY.encode() + rb":(\d+)$")))
    @guard(ctx, staff_only=True)
    async def reply_callback(event: events.CallbackQuery.Event) -> None:
        await _begin_staff_reply(ctx, event, int(event.sender_id), _callback_id(event), mode="callback")

    @client.on(events.CallbackQuery(pattern=re.compile(rb"^" + CB_TICKET_CLOSE.encode() + rb":(\d+)$")))
    @guard(ctx)
    async def close_callback(event: events.CallbackQuery.Event) -> None:
        await _close_ticket(ctx, event, int(event.sender_id), _callback_id(event), mode="callback")

    @client.on(events.CallbackQuery(pattern=re.compile(rb"^" + CB_TICKET_VIEW.encode() + rb":(\d+)$")))
    @guard(ctx)
    async def view_callback(event: events.CallbackQuery.Event) -> None:
        await _show_ticket_detail(ctx, event, int(event.sender_id), _callback_id(event), mode="callback")


# --------------------------------------------------------------------------- #
# Flows
# --------------------------------------------------------------------------- #


async def advance_ticket_flow(ctx: AppContext, event: Any, user_id: int, raw_text: str) -> bool:
    """Move a pending ticket conversation one step forward.

    Returns ``True`` when the message belonged to the flow (and must therefore
    not be handled by the catch-all), ``False`` otherwise.
    """
    state = ctx.states.get(user_id)
    if state is None or state.name not in FLOW_STATES:
        return False
    if ctx.repo.is_blocked(user_id) and not ctx.is_owner(user_id):
        ctx.states.clear(user_id)
        return True

    text = title_case_safe(raw_text)
    language = ctx.language_of(user_id)

    if state.name == STATE_SUBJECT:
        subject = truncate(text, SUBJECT_MAX)
        if len(subject) < 3:
            await reply(event, ctx.tr("common.invalid_input", language))
            return True
        ctx.states.set(user_id, STATE_BODY, subject=subject)
        await reply(event, ctx.tr("ticket.prompt_body", language))
        return True

    if state.name == STATE_BODY:
        await _create_ticket(ctx, event, user_id, str(state.data.get("subject", "-")), text)
        return True

    if state.name == STATE_STAFF_REPLY:
        await _store_staff_reply(ctx, event, user_id, int(state.data.get("ticket_id", 0)), text)
        return True

    return False


async def start_ticket_flow(ctx: AppContext, event: Any, user_id: int, *, mode: str = "message") -> None:
    """Entry point shared by /ticket and the inline button."""
    language = ctx.language_of(user_id)
    if not ctx.settings.feature_tickets:
        await _send(ctx, event, ctx.tr("common.feature_disabled", language), mode=mode)
        return

    open_count = ctx.repo.count_open_tickets(user_id)
    if open_count >= ctx.settings.ticket_max_open:
        await _send(ctx, event, ctx.tr("ticket.limit_reached", language, limit=ctx.settings.ticket_max_open), mode=mode)
        return

    remaining = ctx.repo.cooldown_remaining("ticket", user_id, ctx.settings.ticket_cooldown_seconds)
    if remaining > 0:
        minutes = max(1, int(remaining // 60))
        await _send(ctx, event, ctx.tr("ticket.cooldown", language, minutes=minutes), mode=mode)
        return

    ctx.states.set(user_id, STATE_SUBJECT)
    await _send(ctx, event, ctx.tr("ticket.prompt_subject", language), mode=mode)


async def show_my_tickets(ctx: AppContext, event: Any, user_id: int, *, mode: str = "message") -> None:
    language = ctx.language_of(user_id)
    tickets = ctx.repo.list_tickets(user_id=user_id, limit=10)
    if not tickets:
        await _send(ctx, event, ctx.tr("ticket.none", language), mode=mode, buttons=tickets_menu(ctx, language))
        return

    rows = [
        ctx.tr(
            "ticket.item",
            language,
            ticket_id=ticket["id"],
            status=ctx.tr(f"ticket.status_{ticket['status']}", language),
            subject=escape_html(truncate(str(ticket["subject"]), 40)),
        )
        for ticket in tickets
    ]
    from telethon import Button

    buttons = [[Button.inline(f"#{ticket['id']}", f"{CB_TICKET_VIEW}:{ticket['id']}")] for ticket in tickets]
    buttons.append([Button.inline(ctx.tr("menu.back_to_menu", language), "menu:home")])
    await _send(
        ctx,
        event,
        ctx.tr("ticket.list_header", language) + "\n" + bullet_list(rows),
        mode=mode,
        buttons=buttons,
    )


async def _create_ticket(ctx: AppContext, event: Any, user_id: int, subject: str, body: str) -> None:
    language = ctx.language_of(user_id)
    ctx.states.clear(user_id)
    body = truncate(body, BODY_MAX) or "-"
    ticket_id = ctx.repo.create_ticket(user_id, truncate(title_case_safe(subject), SUBJECT_MAX), body)
    ctx.repo.start_cooldown("ticket", user_id)
    ctx.repo.increment_counter("tickets_created")
    ctx.repo.audit(user_id, "ticket_create", target=str(ticket_id), details={"subject": subject[:80]})

    await event.reply(ctx.tr("ticket.created", language, ticket_id=ticket_id), parse_mode="html", link_preview=False)
    await _notify_staff(ctx, ticket_id, user_id, subject, body, language)
    await ctx.log_to_chat("🎫 New ticket", f"#{ticket_id} · user <code>{user_id}</code> · {escape_html(subject)}")


async def _begin_staff_reply(ctx: AppContext, event: Any, staff_id: int, ticket_id: int, *, mode: str) -> None:
    language = ctx.language_of(staff_id)
    ticket = ctx.repo.get_ticket(ticket_id)
    if ticket is None:
        await _send(ctx, event, ctx.tr("ticket.not_found", language), mode=mode)
        return
    if ticket["status"] == TICKET_CLOSED:
        await _send(ctx, event, ctx.tr("ticket.already_closed", language), mode=mode)
        return
    ctx.states.set(staff_id, STATE_STAFF_REPLY, ticket_id=ticket_id)
    prompt = ctx.tr("ticket.reply_prompt", language, ticket_id=ticket_id)
    await _send(ctx, event, prompt, mode=mode)


async def _store_staff_reply(ctx: AppContext, event: Any, staff_id: int, ticket_id: int, body: str) -> None:
    language = ctx.language_of(staff_id)
    ctx.states.clear(staff_id)
    ticket = ctx.repo.get_ticket(ticket_id)
    if ticket is None:
        await reply(event, ctx.tr("ticket.not_found", language))
        return

    body = truncate(body, BODY_MAX) or "-"
    ctx.repo.add_ticket_message(ticket_id, staff_id, body, from_staff=True)
    ctx.repo.set_ticket_status(ticket_id, TICKET_ANSWERED, admin_id=staff_id, reply=body)
    ctx.repo.increment_counter("ticket_replies")
    ctx.repo.audit(staff_id, "ticket_reply", target=str(ticket_id))

    user_id = int(ticket["user_id"])
    user_language = ctx.language_of(user_id)
    sent = True
    if ctx.client is not None:
        try:
            await ctx.client.send_message(
                user_id,
                ctx.tr("ticket.replied_user", user_language, ticket_id=ticket_id, reply=escape_html(body)),
                parse_mode="html",
            )
        except Exception as exc:
            sent = False
            logger.warning("Cannot deliver ticket reply to %s: %s", user_id, exc)
    confirmation = ctx.tr("ticket.reply_sent", language)
    if not sent:
        confirmation += "\n⚠️ " + ctx.tr("error.unreachable", language)
    await reply(event, confirmation)


async def _close_ticket(ctx: AppContext, event: Any, actor_id: int, ticket_id: int, *, mode: str) -> None:
    language = ctx.language_of(actor_id)
    ticket = ctx.repo.get_ticket(ticket_id)
    if ticket is None:
        await _send(ctx, event, ctx.tr("ticket.not_found", language), mode=mode)
        return

    is_staff = ctx.roles.is_staff(actor_id)
    is_owner_of_ticket = int(ticket["user_id"]) == actor_id
    if not (is_staff or is_owner_of_ticket):
        await _send(ctx, event, ctx.tr("common.not_allowed", language), mode=mode)
        return
    if ticket["status"] == TICKET_CLOSED:
        await _send(ctx, event, ctx.tr("ticket.already_closed", language), mode=mode)
        return

    ctx.repo.set_ticket_status(ticket_id, TICKET_CLOSED, admin_id=actor_id if is_staff else None)
    ctx.repo.increment_counter("tickets_closed")
    ctx.repo.audit(actor_id, "ticket_close", target=str(ticket_id))
    await _send(ctx, event, ctx.tr("ticket.closed_ok", language, ticket_id=ticket_id), mode=mode)


async def _reopen_ticket(ctx: AppContext, event: Any, staff_id: int, ticket_id: int) -> None:
    language = ctx.language_of(staff_id)
    ticket = ctx.repo.get_ticket(ticket_id)
    if ticket is None:
        await reply(event, ctx.tr("ticket.not_found", language))
        return
    ctx.repo.set_ticket_status(ticket_id, TICKET_OPEN, admin_id=staff_id)
    ctx.repo.audit(staff_id, "ticket_reopen", target=str(ticket_id))
    await reply(event, f"♻️ #{ticket_id} → {ctx.tr('ticket.status_open', language)}")


async def _show_ticket_detail(ctx: AppContext, event: Any, user_id: int, ticket_id: int, *, mode: str) -> None:
    language = ctx.language_of(user_id)
    ticket = ctx.repo.get_ticket(ticket_id)
    if ticket is None:
        await _send(ctx, event, ctx.tr("ticket.not_found", language), mode=mode)
        return
    if int(ticket["user_id"]) != user_id and not ctx.roles.is_staff(user_id):
        await _send(ctx, event, ctx.tr("common.not_allowed", language), mode=mode)
        return

    messages = ctx.repo.ticket_messages(ticket_id)[-6:]
    lines = []
    for message in messages:
        author = "🛡 staff" if message["from_staff"] else "👤 user"
        lines.append(
            f"{author} · {truncate(str(message['created_at']).replace('T', ' ')[:16], 16)}\n{escape_html(truncate(str(message['body']), 400))}"
        )
    body = "\n\n".join(lines) or "-"
    text = ctx.tr(
        "ticket.detail_header",
        language,
        ticket_id=ticket_id,
        status=ctx.tr(f"ticket.status_{ticket['status']}", language),
        subject=escape_html(str(ticket["subject"])),
        messages=body,
    )
    buttons = ticket_detail_actions(ctx, language, ticket_id)
    if ctx.roles.is_staff(user_id) and ticket["status"] != TICKET_CLOSED:
        buttons = staff_ticket_actions(ctx, language, ticket_id) + buttons
    await _send(ctx, event, text, mode=mode, buttons=buttons)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
async def _notify_staff(ctx: AppContext, ticket_id: int, user_id: int, subject: str, body: str, language: str) -> None:
    """Tell every staff member about the new ticket."""
    if ctx.client is None:
        return
    recipients = sorted({*ctx.settings.owner_ids, *ctx.repo.staff_ids()})
    text = (
        f"🎫 <b>Ticket #{ticket_id}</b>\n"
        f"👤 <code>{user_id}</code>\n"
        f"📌 {escape_html(subject)}\n\n{escape_html(truncate(body, 1200))}"
    )
    for recipient in recipients:
        recipient_language = ctx.language_of(recipient) or language
        try:
            for chunk in split_message(text):
                await ctx.client.send_message(
                    recipient,
                    chunk,
                    buttons=staff_ticket_actions(ctx, recipient_language, ticket_id),
                    parse_mode="html",
                )
        except Exception as exc:
            logger.debug("Cannot notify staff %s: %s", recipient, exc)


def _callback_id(event: events.CallbackQuery.Event) -> int:
    """Extract the numeric id from a ``<action>:<id>`` callback payload."""
    match = getattr(event, "pattern_match", None)
    try:
        return int(match.group(1)) if match else 0
    except (AttributeError, IndexError, TypeError, ValueError):
        return 0


async def _send(ctx: AppContext, event: Any, text: str, *, mode: str, buttons: Any = None) -> None:
    """Send on either a message or a callback (answer + edit) context."""
    if mode == "callback" and hasattr(event, "edit"):
        with contextlib.suppress(Exception):  # callback may already be answered
            await event.answer()
        try:
            await edit(event, text, buttons=buttons)
            return
        except Exception as exc:  # old menu message could have been deleted
            logger.debug("Cannot edit callback message: %s", exc)
    if hasattr(event, "respond"):
        await event.respond(text, buttons=buttons, parse_mode="html", link_preview=False)
    else:  # pragma: no cover - defensive
        await reply(event, text, buttons=buttons)
