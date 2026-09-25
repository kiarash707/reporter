"""The moderation RPC wrapper: rights objects and result reporting."""

from __future__ import annotations

from telethon import errors
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.functions.messages import EditChatDefaultBannedRightsRequest

from bot.services.moderation import UNRESTRICT, ModerationService


class RecordingClient:
    """Async-callable fake that records every request it receives."""

    def __init__(self, error: Exception | None = None) -> None:
        self.requests: list[object] = []
        self.error = error

    async def __call__(self, request: object) -> None:
        self.requests.append(request)
        if self.error is not None:
            raise self.error

    async def delete_messages(self, chat_id: int, message_ids: list[int], revoke: bool = True) -> None:
        if self.error is not None:
            raise self.error
        self.requests.append(("delete", chat_id, tuple(message_ids)))


async def test_mute_requests_the_silence_rights(repo) -> None:
    client = RecordingClient()
    result = await ModerationService(repo).mute(client, -100, 5, minutes=30)
    assert result.ok is True
    request = client.requests[0]
    assert isinstance(request, EditBannedRequest)
    assert request.participant == 5
    assert request.banned_rights.send_messages is True
    assert request.banned_rights.until_date is not None


async def test_permanent_mute_has_no_until_date(repo) -> None:
    client = RecordingClient()
    result = await ModerationService(repo).mute(client, -100, 5, minutes=0)
    assert result.ok
    assert client.requests[0].banned_rights.until_date is None


async def test_ban_restricts_viewing(repo) -> None:
    client = RecordingClient()
    await ModerationService(repo).ban(client, -100, 6)
    rights = client.requests[0].banned_rights
    assert rights.view_messages is True


async def test_unban_clears_every_restriction(repo) -> None:
    client = RecordingClient()
    await ModerationService(repo).unban(client, -100, 6)
    rights = client.requests[0].banned_rights
    assert rights == UNRESTRICT
    assert rights.view_messages is None and rights.send_messages is None


async def test_kick_bans_then_unbans(repo) -> None:
    client = RecordingClient()
    result = await ModerationService(repo).kick(client, -100, 7)
    assert result.ok is True
    assert len(client.requests) == 2
    assert client.requests[0].banned_rights.view_messages is True
    assert client.requests[1].banned_rights == UNRESTRICT


async def test_missing_permissions_are_reported(repo) -> None:
    client = RecordingClient(error=errors.ChatAdminRequiredError(request=None))
    result = await ModerationService(repo).ban(client, -100, 8)
    assert result.ok is False
    assert result.reason == "bot_not_admin"


async def test_delete_messages(repo) -> None:
    client = RecordingClient()
    assert (await ModerationService(repo).delete_messages(client, -100, [1, 2, 3])).ok
    assert ("delete", -100, (1, 2, 3)) in client.requests
    empty = RecordingClient()
    assert (await ModerationService(repo).delete_messages(empty, -100, [])).ok
    assert empty.requests == []


async def test_delete_forbidden_is_reported(repo) -> None:
    client = RecordingClient(error=errors.MessageDeleteForbiddenError(request=None))
    result = await ModerationService(repo).delete_messages(client, -100, [1])
    assert result.ok is False and result.reason == "delete_forbidden"


async def test_lock_chat_defaults(repo) -> None:
    client = RecordingClient()
    assert (await ModerationService(repo).lock_chat_defaults(client, -100)).ok
    assert isinstance(client.requests[0], EditChatDefaultBannedRightsRequest)


async def test_log_action_writes_audit_rows(repo) -> None:
    service = ModerationService(repo)
    await service.log_action(1, "mute", 2, chat_id=-100, details={"minutes": 5})
    entry = repo.recent_audit(1)[0]
    assert entry["action"] == "mute" and entry["target"] == "2"
    assert "-100" in str(entry["details"])
