"""Text and time helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from bot.utils import text as text_utils
from bot.utils import time as time_utils


def test_escape_html_neutralises_markup() -> None:
    assert text_utils.escape_html("<b>hi</b>") == "&lt;b&gt;hi&lt;/b&gt;"
    assert text_utils.escape_html("a & b") == "a &amp; b"


def test_strip_tags_removes_markup() -> None:
    assert text_utils.strip_tags("<b>bold</b> text") == "bold text"


def test_truncate_keeps_limit_and_marks_cut() -> None:
    assert text_utils.truncate("abcdef", 4) == "abc…"
    assert text_utils.truncate("short", 10) == "short"
    assert text_utils.truncate("abcdef", 0) == ""


def test_split_message_prefers_natural_breaks() -> None:
    chunks = text_utils.split_message("first line\nsecond line\nthird line", limit=15)
    assert all(len(chunk) <= 15 for chunk in chunks)
    assert "".join(chunks).replace("\n", "") == "first linesecond linethird line".replace("\n", "")


def test_split_message_handles_oversized_words() -> None:
    chunks = text_utils.split_message("x" * 25, limit=10)
    assert [len(chunk) for chunk in chunks] == [10, 10, 5]


def test_split_message_rejects_bad_limit() -> None:
    with pytest.raises(ValueError):
        text_utils.split_message("text", limit=0)


def test_mention_and_mask() -> None:
    assert text_utils.mention(42, "Ali") == '<a href="tg://user?id=42">Ali</a>'
    assert text_utils.mask("123456789:AAsecret", visible=4) == "1234" + "*" * 14
    assert text_utils.mask("ab", visible=4) == "**"


def test_parse_csv_handles_comments_and_multiple_lines() -> None:
    value = "github.com, docs.python.org # allowed\nyandex.ru\n# whole line\n\n"
    assert text_utils.parse_csv(value) == ["github.com", "docs.python.org", "yandex.ru"]
    assert text_utils.parse_csv(None) == []
    assert text_utils.parse_csv("") == []


def test_bullet_list_and_title_case_safe() -> None:
    assert text_utils.bullet_list(["a", "b"]).splitlines() == ["• a", "• b"]
    assert text_utils.title_case_safe("  hello   world  ") == "hello world"


def test_humanize_delta_english_and_persian() -> None:
    delta = timedelta(days=1, hours=2, minutes=3)
    assert time_utils.humanize_delta(delta) == "1d 2h 3m"
    assert "روز" in time_utils.humanize_delta(delta, language="fa")


def test_humanize_delta_zero() -> None:
    assert time_utils.humanize_delta(timedelta(seconds=0)) == "0s"


def test_parse_datetime_variants() -> None:
    assert time_utils.parse_datetime(None) is None
    assert time_utils.parse_datetime("") is None
    assert time_utils.parse_datetime("not-a-date") is None
    parsed = time_utils.parse_datetime("2025-01-02T03:04:05+00:00")
    assert parsed is not None and parsed.tzinfo is not None


def test_now_is_timezone_aware_and_zoned() -> None:
    assert time_utils.now("UTC").tzinfo is not None
    tehran = time_utils.now("Asia/Tehran")
    assert "Tehran" in str(tehran.tzinfo) or "Iran" in str(tehran.tzinfo) or "+03:30" in str(tehran)


def test_unknown_timezone_raises_config_error() -> None:
    from bot.errors import ConfigError

    with pytest.raises(ConfigError):
        time_utils.get_zone("Mars/Olympus")


def test_utcnow_is_aware() -> None:
    moment = time_utils.utcnow()
    assert moment.tzinfo is timezone.utc
    assert (datetime.now(timezone.utc) - moment).total_seconds() < 5


def test_format_datetime_none_and_value() -> None:
    assert time_utils.format_datetime(None) == "-"
    assert time_utils.format_datetime(datetime(2025, 5, 6, 7, 8)) == "2025-05-06 07:08"
