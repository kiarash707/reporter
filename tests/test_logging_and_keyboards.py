"""Logging setup and keyboard builders."""

from __future__ import annotations

import json
import logging

import pytest

from bot.keyboards import (
    CB_ACCEPT_RULES,
    CB_GROUP_ANTISPAM,
    CB_LANG_EN,
    CB_OWN_TOGGLE,
    CB_TICKET_REPLY,
    group_panel,
    language_menu,
    main_menu,
    owner_panel,
    staff_ticket_actions,
    ticket_detail_actions,
    tickets_menu,
)
from bot.logging_setup import JsonFormatter, SecretFilter, setup_logging


def payload(button) -> bytes:
    """Telethon 1.45 stores the callback payload on ``button.type.data``."""
    return button.type.data


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
def test_setup_logging_creates_rotating_files(settings) -> None:
    logger = setup_logging(settings, force=True)
    logger.info("hello from the test suite")
    logging.getLogger("bot.test").warning("a warning goes to errors.log too")
    for handler in logging.getLogger().handlers:
        handler.flush()

    assert (settings.log_path / "bot.log").is_file()
    assert (settings.log_path / "errors.log").is_file()
    assert "hello from the test suite" in (settings.log_path / "bot.log").read_text(encoding="utf-8")
    assert "a warning goes to errors.log too" in (settings.log_path / "errors.log").read_text(encoding="utf-8")


def test_secret_filter_masks_tokens() -> None:
    secret = "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"
    record = logging.LogRecord("bot", logging.INFO, "f.py", 1, "token=%s", (secret,), None)
    SecretFilter([secret]).filter(record)
    assert secret not in record.getMessage()
    assert "*" in record.getMessage()


def test_json_formatter_emits_one_object_per_line() -> None:
    record = logging.LogRecord("bot.test", logging.INFO, "file.py", 42, "message %s", ("x",), None)
    record.chat_id = -100
    payload = json.loads(JsonFormatter().format(record))
    assert payload["level"] == "INFO"
    assert payload["message"] == "message x"
    assert payload["chat_id"] == -100
    assert payload["line"] == 42


def test_setup_logging_is_idempotent(settings) -> None:
    setup_logging(settings, force=True)
    before = len(logging.getLogger().handlers)
    setup_logging(settings)
    assert len(logging.getLogger().handlers) == before


def test_json_mode_is_configured(settings) -> None:
    settings.log_json = True
    setup_logging(settings, force=True)
    logger = logging.getLogger("bot.json")
    logger.error("json line")
    for handler in logging.getLogger().handlers:
        handler.flush()
    content = (settings.log_path / "bot.log").read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(content[-1])["message"] == "json line"


# --------------------------------------------------------------------------- #
# Keyboards
# --------------------------------------------------------------------------- #
def test_main_menu_hides_admin_rows_from_members(context) -> None:
    member_rows = main_menu(context, "en", is_staff=False, is_owner=False)
    staff_rows = main_menu(context, "en", is_staff=True, is_owner=True, in_group=True)
    assert len(member_rows) == 2
    assert len(staff_rows) == 4
    assert all(payload(button) != CB_OWN_TOGGLE.encode() for row in member_rows for button in row)


def test_owner_panel_reflects_state(context) -> None:
    enabled_rows = owner_panel(context, "en", bot_enabled=True)
    disabled_rows = owner_panel(context, "en", bot_enabled=False)
    assert enabled_rows[0][0].text.startswith("🟢")
    assert disabled_rows[0][0].text.startswith("🔴")
    assert payload(enabled_rows[0][0]) == CB_OWN_TOGGLE.encode()


def test_group_panel_toggle_icons(context) -> None:
    rows = group_panel(context, "en", antispam=True, welcome=False)
    assert payload(rows[0][0]) == CB_GROUP_ANTISPAM.encode()
    assert rows[0][0].text.startswith("🟢")
    assert rows[1][0].text.startswith("🔴")


def test_language_menu_offers_both_buttons(context) -> None:
    rows = language_menu(context, "fa")
    assert payload(rows[0][1]) == CB_LANG_EN.encode()
    assert payload(rows[0][0]) == b"menu:lang:fa"


def test_ticket_keyboards_carry_ids(context) -> None:
    rows = staff_ticket_actions(context, "en", 7)
    assert payload(rows[0][0]) == f"{CB_TICKET_REPLY}:7".encode()
    detail = ticket_detail_actions(context, "fa", 9)
    assert any(payload(button) == b"ticket:close:9" for row in detail for button in row)
    assert all(payload(button) != CB_ACCEPT_RULES.encode() for row in tickets_menu(context, "en") for button in row)


def test_keyboard_labels_follow_the_language(context) -> None:
    english = tickets_menu(context, "en")[0][0].text
    persian = tickets_menu(context, "fa")[0][0].text
    assert english != persian


# --------------------------------------------------------------------------- #
# Context helpers
# --------------------------------------------------------------------------- #
def test_require_client_reports_a_missing_client(context) -> None:
    from bot.errors import NotConfigured

    context.client = None
    with pytest.raises(NotConfigured):
        context.require_client()

    sentinel = object()
    context.client = sentinel
    assert context.require_client() is sentinel


def test_event_loop_policy_reports_the_backend() -> None:
    from bot.app import install_event_loop_policy

    assert install_event_loop_policy() in {"asyncio", "uvloop"}
