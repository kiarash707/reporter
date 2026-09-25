"""End-to-end flows with fake Telegram objects (no network, no sleeping)."""

from __future__ import annotations

import pytest

from bot.handlers import commands as command_utils
from bot.handlers import moderation, tickets
from bot.storage.repository import TICKET_ANSWERED, TICKET_CLOSED, TICKET_OPEN
from tests.conftest import FakeClient, FakeEvent


# --------------------------------------------------------------------------- #
# Command bookkeeping
# --------------------------------------------------------------------------- #
def test_known_commands_cover_every_handler_pattern() -> None:
    known = command_utils.collect_known_commands()
    expected = {
        "start",
        "help",
        "id",
        "lang",
        "cancel",
        "stats",
        "ticket",
        "mytickets",
        "tickets",
        "reply",
        "close",
        "open",
        "admin",
        "rules",
        "setrules",
        "warn",
        "unwarn",
        "warns",
        "mute",
        "unmute",
        "ban",
        "unban",
        "kick",
        "purge",
        "pin",
        "adminpanel",
        "broadcast",
        "togglebot",
        "maintenance",
        "audit",
        "backup",
        "importdb",
        "reloadlocales",
        "staff",
        "addstaff",
        "delstaff",
        "block",
        "unblock",
    }
    assert expected <= known, f"missing from the command registry: {sorted(expected - known)}"


def test_command_name_extraction() -> None:
    assert command_utils.command_name_of(r"^/warn(?:@[\w_]+)?(?:\s+([\s\S]+))?$") == "warn"
    assert command_utils.command_names_of(r"^/(block|unblock)\s+(-?\d+)$") == {"block", "unblock"}
    assert command_utils.command_names_of(r"^text") == set()


# --------------------------------------------------------------------------- #
# Ticket flow
# --------------------------------------------------------------------------- #
async def test_ticket_flow_happy_path(context) -> None:
    user_id = 1001
    event = FakeEvent(sender_id=user_id)

    await tickets.start_ticket_flow(context, event, user_id, mode="message")
    assert context.states.is_(user_id, tickets.STATE_SUBJECT)
    assert event.replies and event.last_reply == context.tr("ticket.prompt_subject", "fa")

    # second step: subject -> body
    consumed = await tickets.advance_ticket_flow(context, event, user_id, "  Payment   problem ")
    assert consumed is True
    state = context.states.get(user_id)
    assert state.name == tickets.STATE_BODY
    assert state.data["subject"] == "Payment problem"

    # third step: body -> ticket created
    consumed = await tickets.advance_ticket_flow(context, event, user_id, "I paid twice, please check.")
    assert consumed is True
    assert context.states.get(user_id) is None

    created = context.repo.list_tickets(user_id=user_id)
    assert len(created) == 1
    assert created[0]["status"] == TICKET_OPEN
    assert context.repo.ticket_messages(created[0]["id"])[0]["body"] == "I paid twice, please check."


async def test_ticket_flow_rejects_tiny_subject(context) -> None:
    user_id = 1002
    event = FakeEvent(sender_id=user_id)
    await tickets.start_ticket_flow(context, event, user_id, mode="message")
    assert await tickets.advance_ticket_flow(context, event, user_id, "a") is True
    assert context.states.is_(user_id, tickets.STATE_SUBJECT)
    assert context.repo.list_tickets(user_id=user_id) == []


async def test_ticket_flow_ignores_unrelated_messages(context) -> None:
    event = FakeEvent(sender_id=1003)
    assert await tickets.advance_ticket_flow(context, event, 1003, "hello there") is False


async def test_ticket_flow_blocked_user_is_dropped(context) -> None:
    user_id = 1004
    context.repo.upsert_user(user_id)
    context.states.set(user_id, tickets.STATE_SUBJECT)
    context.repo.set_blocked(user_id, True)
    assert await tickets.advance_ticket_flow(context, FakeEvent(sender_id=user_id), user_id, "anything") is True
    assert context.states.get(user_id) is None


async def test_ticket_open_limit_and_cooldown(context) -> None:
    user_id = 1005
    context.settings.ticket_max_open = 1
    await tickets.start_ticket_flow(context, FakeEvent(sender_id=user_id), user_id, mode="message")
    await tickets.advance_ticket_flow(context, FakeEvent(sender_id=user_id), user_id, "Subject line")
    await tickets.advance_ticket_flow(context, FakeEvent(sender_id=user_id), user_id, "Body text")

    event = FakeEvent(sender_id=user_id)
    await tickets.start_ticket_flow(context, event, user_id, mode="message")
    assert context.states.get(user_id) is None
    assert event.replies and "1" in event.last_reply

    # closing the ticket still leaves the cooldown in place
    ticket_id = context.repo.list_tickets(user_id=user_id)[0]["id"]
    await tickets._close_ticket(context, FakeEvent(sender_id=user_id), user_id, ticket_id, mode="message")
    assert context.repo.get_ticket(ticket_id)["status"] == TICKET_CLOSED

    context.settings.ticket_cooldown_seconds = 600
    cooldown_event = FakeEvent(sender_id=user_id)
    await tickets.start_ticket_flow(context, cooldown_event, user_id, mode="message")
    assert context.states.get(user_id) is None
    assert cooldown_event.replies


async def test_ticket_feature_flag_disables_the_flow(context) -> None:
    context.settings.feature_tickets = False
    event = FakeEvent(sender_id=1006)
    await tickets.start_ticket_flow(context, event, 1006, mode="message")
    assert context.states.get(1006) is None
    assert event.replies


async def test_staff_reply_reaches_the_user(context) -> None:
    user_id, staff_id = 1007, context.settings.owner_ids[0]
    ticket_id = context.repo.create_ticket(user_id, "Help", "please help")
    event = FakeEvent(sender_id=staff_id)

    await tickets._begin_staff_reply(context, event, staff_id, ticket_id, mode="message")
    assert context.states.is_(staff_id, tickets.STATE_STAFF_REPLY)

    await tickets.advance_ticket_flow(context, event, staff_id, "We fixed it for you.")
    assert context.states.get(staff_id) is None

    ticket = context.repo.get_ticket(ticket_id)
    assert ticket["status"] == TICKET_ANSWERED
    assert ticket["admin_id"] == staff_id
    messages = context.repo.ticket_messages(ticket_id)
    assert messages[-1]["from_staff"] is True


async def test_staff_reply_to_missing_ticket(context) -> None:
    event = FakeEvent(sender_id=context.settings.owner_ids[0])
    await tickets._begin_staff_reply(context, event, event.sender_id, 999999, mode="message")
    assert context.states.get(event.sender_id) is None
    assert event.replies


async def test_close_permissions(context) -> None:
    owner_id, stranger_id = context.settings.owner_ids[0], 1008
    ticket_id = context.repo.create_ticket(store := 1009, "subj", "body")

    stranger_event = FakeEvent(sender_id=stranger_id)
    await tickets._close_ticket(context, stranger_event, stranger_id, ticket_id, mode="message")
    assert context.repo.get_ticket(ticket_id)["status"] == TICKET_OPEN
    assert stranger_event.replies

    staff_event = FakeEvent(sender_id=owner_id)
    await tickets._close_ticket(context, staff_event, owner_id, ticket_id, mode="message")
    assert context.repo.get_ticket(ticket_id)["status"] == TICKET_CLOSED

    again = FakeEvent(sender_id=owner_id)
    await tickets._close_ticket(context, again, owner_id, ticket_id, mode="message")
    assert again.replies
    assert store == 1009


async def test_my_tickets_and_detail(context) -> None:
    user_id = 1010
    ticket_id = context.repo.create_ticket(user_id, "Subject", "body")

    listing = FakeEvent(sender_id=user_id)
    await tickets.show_my_tickets(context, listing, user_id, mode="message")
    assert listing.replies and f"#{ticket_id}" in listing.last_reply

    detail = FakeEvent(sender_id=user_id)
    await tickets._show_ticket_detail(context, detail, user_id, ticket_id, mode="message")
    assert detail.replies and "Subject" in detail.last_reply

    # callback id extraction works off the regex match object
    class _PatternMatch:
        def group(self, index: int) -> str:
            return str(ticket_id) if index == 1 else ""

    callback_fake = FakeEvent(sender_id=user_id, data=f"ticket:view:{ticket_id}")
    callback_fake.pattern_match = _PatternMatch()
    assert tickets._callback_id(callback_fake) == ticket_id
    assert tickets._callback_id(FakeEvent(data="garbage")) == 0


async def test_empty_ticket_list(context) -> None:
    event = FakeEvent(sender_id=1011)
    await tickets.show_my_tickets(context, event, 1011, mode="message")
    assert event.replies


# --------------------------------------------------------------------------- #
# Moderation helpers
# --------------------------------------------------------------------------- #
def test_extract_minutes_units() -> None:
    assert moderation._extract_minutes("10m") == 10
    assert moderation._extract_minutes("2h") == 120
    assert moderation._extract_minutes("1d") == 1440
    assert moderation._extract_minutes("45") == 45
    assert moderation._extract_minutes("no digits here") is None
    assert moderation._extract_minutes(None) is None


def test_reason_extraction() -> None:
    assert moderation._reason_of("12345 spam links", 12345) == "spam links"
    assert moderation._reason_of("@someone advertising", 5) == "advertising"
    assert moderation._reason_of("just a reason", 5) == "just a reason"
    assert moderation._reason_of(None, 5) == ""


async def test_resolve_target_prefers_reply(context) -> None:
    event = FakeEvent(sender_id=1)
    event.reply_to_msg_id = 77

    class Message:
        sender_id = 4242

    async def get_reply_message():
        return Message()

    event.get_reply_message = get_reply_message
    assert await moderation._resolve_target(context, event, None) == 4242


async def test_resolve_target_from_numeric_argument(context) -> None:
    event = FakeEvent(sender_id=1)
    assert await moderation._resolve_target(context, event, "55542") == 55542
    assert await moderation._resolve_target(context, event, "not-a-user") is None
    assert await moderation._resolve_target(context, event, None) is None


async def test_require_chat_admin_rejects_non_admin(context) -> None:
    from bot.errors import AccessDenied

    event = FakeEvent(sender_id=2002, chat_id=-100, is_group=True)
    context.client = FakeClient()
    context.roles.is_chat_admin = _always(False)  # type: ignore[assignment]
    with pytest.raises(AccessDenied):
        await moderation._require_chat_admin(context, event)


async def test_warn_flow_applies_mute_at_limit(context) -> None:
    context.settings.antispam_warn_limit = 1
    context.settings.antispam_ban_limit = 3
    context.client = FakeClient(is_admin=True)
    context.roles.is_chat_admin = _always(True)  # type: ignore[assignment]

    muted: list[tuple] = []

    class FakeModeration:
        def __init__(self, repo):
            self.repo = repo

        async def mute(self, client, chat_id, user_id, minutes):
            muted.append((chat_id, user_id, minutes))
            from bot.services.moderation import ModerationResult

            return ModerationResult(True)

        async def ban(self, client, chat_id, user_id, *, minutes=0):
            from bot.services.moderation import ModerationResult

            return ModerationResult(True)

    import bot.handlers.moderation as moderation_module

    original = moderation_module.ModerationService
    moderation_module.ModerationService = FakeModeration
    try:
        event = FakeEvent(sender_id=3003, chat_id=-100, is_group=True)
        event.pattern_match = _Match("4004 flooding")
        await moderation._warn_command(context, event)
    finally:
        moderation_module.ModerationService = original

    assert context.repo.warning_count(-100, 4004) == 1
    assert muted and muted[0][1] == 4004
    assert event.replies


def _always(value):
    async def _call(*args, **kwargs):
        return value

    return _call


class _Match:
    """Mimics ``event.pattern_match`` for the moderation command patterns."""

    def __init__(self, raw: str) -> None:
        self._raw = raw

    def group(self, index: int):
        return self._raw if index == 1 else None
