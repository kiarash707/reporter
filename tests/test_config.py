"""Configuration validation is the first line of defence - test it thoroughly."""

from __future__ import annotations

from pathlib import Path

import pytest

from bot.config import detect_base_dir, load_settings
from bot.errors import ConfigError
from tests.conftest import VALID_ENV


def _write(tmp_path: Path, **overrides: str) -> Path:
    env_lines = []
    for line in VALID_ENV.strip().splitlines():
        key = line.split("=", 1)[0]
        if key in overrides:
            continue
        env_lines.append(line)
    env_lines.extend(f"{key}={value}" for key, value in overrides.items())
    (tmp_path / ".env").write_text("\n".join(env_lines) + "\n", encoding="utf-8")
    return tmp_path


def test_loads_valid_configuration(tmp_path: Path) -> None:
    settings = load_settings(base_dir=_write(tmp_path))
    assert settings.api_id == 123456
    assert settings.owner_ids == [111111, 222222]
    assert settings.log_chat_id == -1001234567890
    assert settings.antispam_allowed_domains == ["github.com", "docs.python.org"]
    assert settings.data_path == tmp_path / "data"
    assert settings.db_file.name == "state.db"


def test_is_cached_and_reloadable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The singleton caches, and ``reload_settings`` picks up edited values.

    The test must not depend on the developer's own ``.env``: it points the
    configuration loader at a temporary directory instead.
    """
    from bot.config import get_settings, reload_settings

    _write(tmp_path, TIMEZONE="UTC", DEFAULT_LANGUAGE="en")
    monkeypatch.delenv("BOT_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()

    first = get_settings()
    assert first is get_settings()  # cached while unchanged
    assert first.timezone == "UTC"

    # editing .env only takes effect after an explicit reload
    _write(tmp_path, TIMEZONE="Europe/Berlin", DEFAULT_LANGUAGE="en")
    assert get_settings().timezone == "UTC"
    assert reload_settings().timezone == "Europe/Berlin"
    get_settings.cache_clear()


def test_placeholder_credentials_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as excinfo:
        load_settings(base_dir=_write(tmp_path, BOT_TOKEN="123456789:AAExampleTokenReplaceMeWithARealOne"))
    assert "BOT_TOKEN" in str(excinfo.value)


def test_invalid_token_shape_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as excinfo:
        load_settings(base_dir=_write(tmp_path, BOT_TOKEN="not-a-token"))
    assert "BOT_TOKEN" in str(excinfo.value)


def test_invalid_api_hash_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as excinfo:
        load_settings(base_dir=_write(tmp_path, API_HASH="zzzz"))
    assert "API_HASH" in str(excinfo.value)


def test_bad_timezone_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as excinfo:
        load_settings(base_dir=_write(tmp_path, TIMEZONE="Mars/Olympus"))
    assert "TIMEZONE" in str(excinfo.value)


def test_ban_limit_must_exceed_warn_limit(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as excinfo:
        load_settings(base_dir=_write(tmp_path, ANTISPAM_WARN_LIMIT="5", ANTISPAM_BAN_LIMIT="3"))
    assert "ANTISPAM_BAN_LIMIT" in str(excinfo.value)


def test_unsupported_language_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_settings(base_dir=_write(tmp_path, DEFAULT_LANGUAGE="de"))


def test_empty_optional_values_are_allowed(tmp_path: Path) -> None:
    settings = load_settings(base_dir=_write(tmp_path, LOG_CHAT_ID="", OWNER_IDS="", ANTISPAM_BANNED_WORDS=""))
    assert settings.log_chat_id is None
    assert settings.owner_ids == []
    assert settings.antispam_banned_words == []


def test_secrets_are_masked_in_dumps(tmp_path: Path) -> None:
    settings = load_settings(base_dir=_write(tmp_path))
    dump = settings.safe_dump()
    assert "0123456789abcdef0123456789abcdef" not in str(dump)
    assert dump["bot_token"].startswith("1234")
    assert "*" in dump["api_hash"]


def test_describe_summarises_the_environment(tmp_path: Path) -> None:
    settings = load_settings(base_dir=_write(tmp_path))
    text = settings.describe()
    assert "Asia/Tehran" in text
    assert "111111" in text


def test_detect_base_dir_prefers_bot_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_HOME", str(tmp_path))
    assert detect_base_dir() == tmp_path.resolve()


def test_relative_paths_resolve_against_base_dir(tmp_path: Path) -> None:
    settings = load_settings(base_dir=_write(tmp_path))
    assert settings.resolve("logs") == tmp_path / "logs"
    assert settings.resolve("/var/log/bot") == Path("/var/log/bot")
