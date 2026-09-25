"""Handler wiring and the guard decorator (no network involved)."""

from __future__ import annotations

import pytest
from telethon import events

from bot.errors import AccessDenied, RateLimited
from bot.handlers import register_all
from bot.handlers.guard import guard
from tests.conftest import FakeClient, FakeEvent


def test_register_all_attaches_handlers(context) -> None:
    client = FakeClient()
    register_all(client, context)
    assert len(client.handlers) > 25, "every handler group should register at least a few handlers"
    # the catch-all handlers must come last so commands win
    names = [func.__name__ for _builder, func in client.handlers]
    assert names[-1] == "catch_all", "the catch-all must be registered last"
    assert "start" in names and "warn" in names and "ticket_flow_text" in names


def test_handlers_are_registered_before_catch_all(context) -> None:
    client = FakeClient()
    register_all(client, context)
    names = [func.__name__ for _builder, func in client.handlers]
    assert names.index("start") < names.index("catch_all")
    assert names.index("ticket_flow_text") < names.index("catch_all")


async def test_guard_blocks_when_bot_is_disabled(context) -> None:
    context.repo.set_flag("bot_enabled", False)
    event = FakeEvent(sender_id=500)

    @guard(context)
    async def handler(inner_event):
        inner_event.ran = True  # pragma: no cover - must not be reached

    await handler(event)
    assert not hasattr(event, "ran")
    assert event.replies, "the user should be told why nothing happened"


async def test_guard_allows_owner_while_disabled(context) -> None:
    context.repo.set_flag("bot_enabled", False)
    owner_id = context.settings.owner_ids[0]
    event = FakeEvent(sender_id=owner_id)

    @guard(context)
    async def handler(inner_event):
        inner_event.ran = True

    await handler(event)
    assert getattr(event, "ran", False) is True


async def test_guard_blocks_blocked_users(context) -> None:
    context.repo.set_blocked(600, True)
    event = FakeEvent(sender_id=600)

    @guard(context)
    async def handler(inner_event):  # pragma: no cover - must not be reached
        inner_event.ran = True

    await handler(event)
    assert not hasattr(event, "ran")


async def test_guard_enforces_owner_only(context) -> None:
    event = FakeEvent(sender_id=601)

    @guard(context, owner_only=True)
    async def handler(inner_event):  # pragma: no cover - must not be reached
        inner_event.ran = True

    await handler(event)
    assert not hasattr(event, "ran")
    assert event.replies


async def test_guard_enforces_group_only(context) -> None:
    event = FakeEvent(sender_id=602, is_private=True, is_group=False)

    @guard(context, group_only=True)
    async def handler(inner_event):  # pragma: no cover - must not be reached
        inner_event.ran = True

    await handler(event)
    assert not hasattr(event, "ran")


async def test_guard_applies_rate_limit(context) -> None:
    context.settings.ratelimit_commands = 1
    context.ratelimit.limit = 1
    event = FakeEvent(sender_id=603)
    calls = 0

    @guard(context)
    async def handler(inner_event):
        nonlocal calls
        calls += 1

    await handler(event)
    await handler(event)
    assert calls == 1
    assert event.replies, "the second call should report the rate limit"


async def test_guard_answers_callbacks_instead_of_replying(context) -> None:
    event = FakeEvent(sender_id=604, data="menu:home")

    @guard(context, owner_only=True)
    async def handler(inner_event):  # pragma: no cover - must not be reached
        inner_event.ran = True

    await handler(event)
    assert event.answers or event.replies


async def test_guard_logs_and_reports_internal_errors(context) -> None:
    event = FakeEvent(sender_id=605)

    @guard(context)
    async def handler(inner_event):
        raise RuntimeError("boom")

    await handler(event)  # must not raise
    assert event.replies


async def test_guard_propagates_stop_propagation(context) -> None:
    event = FakeEvent(sender_id=606)

    @guard(context)
    async def handler(inner_event):
        raise events.StopPropagation

    with pytest.raises(events.StopPropagation):
        await handler(event)


async def test_guard_counts_commands(context) -> None:
    event = FakeEvent(sender_id=607)

    @guard(context)
    async def handler(inner_event):
        return "ok"

    await handler(event)
    assert context.repo.get_counter("commands") == 1


def test_access_denied_defaults() -> None:
    error = AccessDenied()
    assert error.required_role == ""
    limited = RateLimited(retry_after=12)
    assert limited.retry_after == 12
