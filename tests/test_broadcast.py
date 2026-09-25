"""Broadcast service: pacing, progress, blocked targets and flood handling."""

from __future__ import annotations

import pytest
from telethon import errors

from bot.services.broadcast import BroadcastService


class FakeSendClient:
    """Records deliveries and can simulate per-recipient failures."""

    def __init__(self, *, blocked: set[int] | None = None, flood_once: int | None = None) -> None:
        self.sent: list[tuple[int, str]] = []
        self.blocked = blocked or set()
        self.flood_once = flood_once
        self.attempts: dict[int, int] = {}

    async def send_message(self, user_id: int, text: str, parse_mode: str | None = None) -> None:
        self.attempts[user_id] = self.attempts.get(user_id, 0) + 1
        if user_id in self.blocked:
            raise errors.UserIsBlockedError(request=None)
        if self.flood_once == user_id and self.attempts[user_id] == 1:
            raise errors.FloodWaitError(request=None, capture=0)
        self.sent.append((user_id, text))


async def test_broadcast_delivers_to_every_target(context) -> None:
    for user_id in (11, 12, 13):
        context.repo.upsert_user(user_id)
    client = FakeSendClient()
    service = BroadcastService(context.repo, delay=0.0, concurrency=2)

    progress_calls: list[tuple[int, int]] = []

    async def progress(sent: int, total: int) -> None:
        progress_calls.append((sent, total))

    report = await service.send(client, "hello everyone", progress=progress, progress_every=1)
    assert report.total == 3
    assert report.sent == 3
    assert report.failed == 0
    assert {user_id for user_id, _ in client.sent} == {11, 12, 13}
    assert progress_calls[-1] == (3, 3)
    assert context.repo.get_counter("broadcasts") == 1


async def test_broadcast_marks_unreachable_users_as_blocked(context) -> None:
    context.repo.upsert_user(21)
    context.repo.upsert_user(22)
    client = FakeSendClient(blocked={22})
    report = await BroadcastService(context.repo, delay=0.0, concurrency=1).send(client, "hi")

    assert report.sent == 1
    assert report.blocked == 1
    assert context.repo.is_blocked(22) is True
    assert "UserIsBlockedError" in report.errors


async def test_broadcast_retries_after_flood_wait(context) -> None:
    context.repo.upsert_user(31)
    client = FakeSendClient(flood_once=31)
    report = await BroadcastService(context.repo, delay=0.0, concurrency=1).send(client, "hi")

    assert report.flood_waits == 1
    assert report.sent == 1
    assert client.attempts[31] == 2


async def test_broadcast_without_targets(context) -> None:
    client = FakeSendClient()
    report = await BroadcastService(context.repo, delay=0.0).send(client, "hi")
    assert report.total == 0 and report.sent == 0
    assert client.sent == []


async def test_broadcast_reports_dict(context) -> None:
    context.repo.upsert_user(41)
    report = await BroadcastService(context.repo, delay=0.0).send(FakeSendClient(), "hi")
    payload = report.as_dict()
    assert payload["total"] == 1 and payload["sent"] == 1
    assert set(payload) == {"total", "sent", "failed", "blocked", "flood_waits"}


@pytest.mark.parametrize("delay", [0.0, 0.01])
async def test_broadcast_delay_is_honoured(context, delay: float) -> None:
    context.repo.upsert_user(51)
    report = await BroadcastService(context.repo, delay=delay, concurrency=1).send(FakeSendClient(), "hi")
    assert report.sent == 1
