"""Shared fixtures: isolated settings, a real SQLite repository and fake Telegram objects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from bot.config import Settings, load_settings
from bot.context import AppContext
from bot.i18n import Translator
from bot.services.antispam import AntispamService
from bot.services.ratelimit import RateLimiter
from bot.services.roles import Roles
from bot.services.states import StateStore
from bot.storage.database import Database
from bot.storage.repository import Repository

VALID_ENV = """\
API_ID=123456
API_HASH=fedcba9876543210fedcba9876543210
BOT_TOKEN=123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw
OWNER_IDS=111111,222222
LOG_CHAT_ID=-1001234567890
ENVIRONMENT=development
TIMEZONE=Asia/Tehran
DEFAULT_LANGUAGE=fa
DATA_DIR=data
SESSION_DIR=sessions
LOG_DIR=logs
LOG_LEVEL=DEBUG
ANTISPAM_BLOCK_LINKS=true
ANTISPAM_ALLOWED_DOMAINS=github.com, docs.python.org
ANTISPAM_BANNED_WORDS=badword, https?://spam\\..*
ANTISPAM_FLOOD_MESSAGES=3
ANTISPAM_FLOOD_WINDOW=10
"""


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """A throwaway project home with a valid .env file."""
    (tmp_path / ".env").write_text(VALID_ENV, encoding="utf-8")
    return tmp_path


@pytest.fixture
def settings(project_dir: Path) -> Settings:
    return load_settings(base_dir=project_dir)


@pytest.fixture
def db(settings: Settings) -> Database:
    database = Database(settings.db_file)
    database.migrate()
    yield database
    database.close()


@pytest.fixture
def repo(db: Database, settings: Settings) -> Repository:
    return Repository(db, timezone=settings.timezone)


@pytest.fixture
def translator(settings: Settings) -> Translator:
    return Translator(default_language=settings.default_language)


@pytest.fixture
def context(settings: Settings, db: Database, repo: Repository, translator: Translator) -> AppContext:
    """A fully wired AppContext without a Telegram connection."""
    settings.prepare_directories()
    ctx = AppContext(
        settings=settings,
        db=db,
        repo=repo,
        i18n=translator,
        roles=Roles(repo, settings.owner_ids),
        ratelimit=RateLimiter(repo, limit=settings.ratelimit_commands, window=settings.ratelimit_window),
        states=StateStore(),
    )
    ctx.antispam = AntispamService(settings, repo)
    return ctx


# --------------------------------------------------------------------------- #
# Lightweight Telegram doubles
# --------------------------------------------------------------------------- #
class FakeMessage:
    """Records what a handler replied/edited so assertions stay simple."""

    def __init__(self, text: str = "") -> None:
        self.text = text
        self.parse_mode: str | None = None
        self.buttons: Any = None

    async def edit(self, text: str, **kwargs: Any) -> FakeMessage:
        self.text = text
        self.parse_mode = kwargs.get("parse_mode")
        self.buttons = kwargs.get("buttons")
        return self

    async def delete(self) -> None:
        return None


class FakeEvent:
    """Minimal stand-in for a Telethon NewMessage/CallbackQuery event."""

    def __init__(
        self,
        *,
        sender_id: int = 999,
        chat_id: int = 999,
        text: str = "",
        is_private: bool = True,
        is_group: bool = False,
        data: str | None = None,
    ) -> None:
        self.sender_id = sender_id
        self.chat_id = chat_id
        self.raw_text = text
        self.text = text
        self.is_private = is_private
        self.is_group = is_group
        self.is_callback = data is not None
        self.data = data.encode() if data else b""
        self.replies: list[FakeMessage] = []
        self.answers: list[str] = []
        self.deleted = False
        self.message = FakeMessage()
        self.id = 42
        self.reply_to_msg_id = None

    async def reply(self, text: str, **kwargs: Any) -> FakeMessage:
        message = FakeMessage(text)
        message.parse_mode = kwargs.get("parse_mode")
        message.buttons = kwargs.get("buttons")
        self.replies.append(message)
        return message

    respond = reply

    async def edit(self, text: str, **kwargs: Any) -> FakeMessage:
        self.message.text = text
        self.message.parse_mode = kwargs.get("parse_mode")
        self.message.buttons = kwargs.get("buttons")
        return self.message

    async def answer(self, text: str = "", **kwargs: Any) -> None:
        self.answers.append(text)

    async def delete(self) -> None:
        self.deleted = True

    async def get_sender(self) -> Any:  # pragma: no cover - only used by a few handlers
        return None

    async def get_chat(self) -> Any:
        return None

    async def get_user(self) -> Any:
        return None

    @property
    def last_reply(self) -> str:
        return self.replies[-1].text if self.replies else ""


class FakeClient:
    """Collects handler registrations instead of talking to Telegram."""

    def __init__(self) -> None:
        self.handlers: list[tuple[Any, Any]] = []

    def on(self, builder: Any) -> Any:
        def decorator(func: Any) -> Any:
            self.handlers.append((builder, func))
            return func

        return decorator


@pytest.fixture
def fake_event() -> FakeEvent:
    return FakeEvent()


@pytest.fixture
def legacy_payload() -> dict[str, Any]:
    return {
        "users": [1, 2, 3],
        "blocked": [3],
        "user_lang": {"1": "fa", "2": "en"},
        "support_tickets": {
            "1": {"subject": "Old ticket", "message": "Please help", "status": "open"},
            "2": "not-a-dict",
        },
        "total_reports": 120,
    }


@pytest.fixture
def legacy_file(tmp_path: Path, legacy_payload: dict[str, Any]) -> Path:
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(legacy_payload), encoding="utf-8")
    return path
