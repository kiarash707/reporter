"""Entity helpers used across handlers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from telethon import errors
from telethon.tl.types import Channel, User

from bot.errors import TelegramFlood
from bot.utils import telegram as tg


def test_display_name_prefers_title_then_name_then_username() -> None:
    assert tg.display_name(SimpleNamespace(title="Group")) == "Group"
    assert tg.display_name(SimpleNamespace(first_name="Ali", last_name="Ahmadi")) == "Ali Ahmadi"
    assert tg.display_name(SimpleNamespace(username="ali")) == "@ali"
    assert tg.display_name(SimpleNamespace(id=5)) == "5"
    assert tg.display_name(None) == "unknown"


def _channel(**attributes) -> Channel:
    """Telethon entities are plain attribute bags; skip the TL constructor."""
    entity = Channel.__new__(Channel)
    for key, value in attributes.items():
        setattr(entity, key, value)
    return entity


def test_entity_helpers() -> None:
    group = _channel(id=2, title="Chat", megagroup=True, broadcast=False)
    channel = _channel(id=1, title="News", megagroup=False, broadcast=True)
    assert tg.is_group(group) is True
    assert tg.is_group(channel) is False
    assert tg.is_channel(channel) is True
    assert tg.is_channel(group) is False
    assert tg.entity_id(channel) == 1
    assert tg.entity_id(object()) is None
    assert tg.is_user(SimpleNamespace(username="u", first_name="U")) is False
    assert tg.is_bot(SimpleNamespace(bot=True)) is True


def test_full_mention_and_chat_identifier() -> None:
    entity = SimpleNamespace(id=42, first_name="Ali")
    assert tg.full_mention(entity) == '<a href="tg://user?id=42">Ali</a>'
    assert tg.chat_identifier(SimpleNamespace(chat_id=-100, sender_id=5)) == -100
    assert tg.chat_identifier(SimpleNamespace(chat_id=None, sender_id=5)) == 5


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (errors.FloodWaitError(request=None, capture=3), "flood_wait"),
        (errors.ChatAdminRequiredError(request=None), "missing_permissions"),
        (errors.ChannelPrivateError(request=None), "entity_unavailable"),
        (errors.UserIsBlockedError(request=None), "user_unreachable"),
        (errors.AuthKeyUnregisteredError(request=None), "session_revoked"),
        (errors.BotMethodInvalidError(request=None), "bot_restricted"),
        (ValueError("x"), "ValueError"),
    ],
)
def test_classify_error(error: Exception, expected: str) -> None:
    assert tg.classify_error(error) == expected


async def test_guard_flood_raises_typed_error() -> None:
    with pytest.raises(TelegramFlood) as excinfo:
        await tg.guard_flood(errors.FloodWaitError(request=None, capture=12))
    assert excinfo.value.seconds == 12


def test_admin_rights_summary() -> None:
    assert tg.admin_rights_summary(None) == "none"
    permissions = SimpleNamespace(
        delete_messages=True, ban_users=True, mute_users=False, invite_users=False, pin_messages=True
    )
    assert tg.admin_rights_summary(permissions) == "delete, ban, pin"
    assert tg.admin_rights_summary(SimpleNamespace()) == "none"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("check https://example.com", True),
        ("visit www.example.com", True),
        ("join t.me/channel", True),
        ("buy at shop.com now", True),
        ("plain text without links", False),
        ("", False),
    ],
)
def test_looks_like_link(text: str, expected: bool) -> None:
    assert tg.looks_like_link(text) is expected


def test_user_type_helpers_with_real_tl_objects() -> None:
    user = User(
        id=1,
        is_self=None,
        contact=None,
        mutual_contact=None,
        deleted=None,
        bot=True,
        bot_chat_history=None,
        bot_nochats=None,
        verified=None,
        restricted=None,
        min=None,
        bot_inline_geo=None,
        support=None,
        scam=None,
        apply_min_photo=None,
        fake=None,
        bot_attach_menu=None,
        premium=None,
        attach_menu_enabled=None,
        bot_can_edit=None,
        close_friend=None,
        stories_hidden=None,
        stories_unavailable=None,
        contact_require_premium=None,
        access_hash=None,
        first_name="Bot",
        last_name=None,
        username="mybot",
        phone=None,
        photo=None,
        status=None,
        bot_info_version=None,
        restriction_reason=None,
        bot_inline_placeholder=None,
        lang_code=None,
        emoji_status=None,
        usernames=None,
        stories_max_id=None,
        color=None,
        profile_color=None,
        bot_active_users=None,
        send_paid_messages_stars=None,
    )
    assert tg.is_user(user) is True
    assert tg.is_bot(user) is True
