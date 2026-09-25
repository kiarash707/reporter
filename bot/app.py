"""Application wiring: build the client/context, run, and shut down cleanly."""

from __future__ import annotations

import asyncio
import contextlib
import signal
import sys
from pathlib import Path
from typing import Any

from telethon import TelegramClient, errors

from bot import APP_NAME, __version__
from bot.config import Settings
from bot.context import AppContext
from bot.errors import ConfigError, StorageError
from bot.handlers import register_all
from bot.i18n import Translator
from bot.logging_setup import get_logger, setup_logging
from bot.services.antispam import AntispamService
from bot.services.backup import backup_age, create_backup
from bot.services.ratelimit import RateLimiter
from bot.services.roles import Roles
from bot.storage.database import Database
from bot.storage.repository import Repository
from bot.utils.time import now

MAINTENANCE_INTERVAL = 1800  # seconds between housekeeping passes
BACKUP_INTERVAL = 24 * 3600  # automatic daily backup
SESSION_NAME = "bot"

logger = get_logger("app")


# --------------------------------------------------------------------------- #
# Construction
# --------------------------------------------------------------------------- #
def build_context(settings: Settings) -> AppContext:
    """Create the database, repository, services and every collaborator."""
    settings.prepare_directories()
    db = Database(settings.db_file)
    version = db.migrate()
    repo = Repository(db, timezone=settings.timezone)
    i18n = Translator(default_language=settings.default_language)
    context = AppContext(
        settings=settings,
        db=db,
        repo=repo,
        i18n=i18n,
        roles=Roles(repo, settings.owner_ids),
        ratelimit=RateLimiter(repo, limit=settings.ratelimit_commands, window=settings.ratelimit_window),
    )
    context.antispam = AntispamService(settings, repo)
    logger.debug("Context ready (schema v%s, %s locales)", version, len(i18n.languages))
    return context


def build_client(settings: Settings) -> TelegramClient:
    """Create the Telethon client configured for long-running bot use."""
    session_path = settings.session_path / SESSION_NAME
    client = TelegramClient(
        str(session_path),
        settings.api_id,
        settings.api_hash_value,
        connection_retries=None,  # never give up reconnecting
        retry_delay=5,
        auto_reconnect=True,
        request_retries=5,
        flood_sleep_threshold=60,
        device_model="CommunityBot",
        system_version=f"{APP_NAME} {__version__}",
        app_version=__version__,
    )
    return client


# --------------------------------------------------------------------------- #
# Startup / shutdown
# --------------------------------------------------------------------------- #
async def start_bot(context: AppContext) -> TelegramClient:
    """Start the client, log in as the bot and register handlers."""
    settings = context.settings
    client = build_client(settings)
    try:
        await client.start(bot_token=settings.bot_token_value)
    except errors.AccessTokenInvalidError as exc:
        await _safe_disconnect(client)
        raise ConfigError("BOT_TOKEN is invalid or was revoked (create a new one with @BotFather)") from exc
    except errors.AccessTokenExpiredError as exc:
        await _safe_disconnect(client)
        raise ConfigError("BOT_TOKEN expired - generate a fresh token with @BotFather") from exc
    except errors.ApiIdInvalidError as exc:
        await _safe_disconnect(client)
        raise ConfigError("API_ID/API_HASH are invalid - copy them from https://my.telegram.org") from exc
    except Exception as exc:
        await _safe_disconnect(client)
        raise ConfigError(f"Could not start the Telegram client: {exc}") from exc

    context.client = client
    me = await client.get_me()
    register_all(client, context)

    logger.info(
        "Started as @%s (id=%s) | version=%s env=%s | sqlite=%s | locales=%s",
        getattr(me, "username", "?"),
        getattr(me, "id", "?"),
        __version__,
        settings.environment,
        context.db.path.name,
        ", ".join(context.i18n.languages),
    )
    await _startup_notice(context)
    return client


async def _startup_notice(context: AppContext) -> None:
    """Tell the owners (and the log chat) that the bot came back online."""
    text = (
        f"✅ <b>{APP_NAME}</b> v{__version__} started\n"
        f"🏠 home: <code>{context.settings.base_dir}</code>\n"
        f"🌐 env: {context.settings.environment} · tz: {context.settings.timezone}\n"
        f"💾 db: schema v{context.db.health().get('schema_version')}"
    )
    await context.notify_owner(text, category="startup")
    await context.log_to_chat("✅ Bot started", f"v{__version__} · env {context.settings.environment}")


async def shutdown(context: AppContext) -> None:
    """Close the client and the database, in that order."""
    if context.client is not None:
        with contextlib.suppress(Exception):
            await context.client.disconnect()
    with contextlib.suppress(Exception):
        context.db.close()
    logger.info("Shutdown complete")


async def run(settings: Settings) -> int:
    """Run the bot until it is stopped by a signal or KeyboardInterrupt."""
    setup_logging(settings)
    logger.info("Booting %s v%s (%s)", APP_NAME, __version__, settings.environment)
    logger.debug("Configuration:\n%s", settings.describe())

    context = build_context(settings)
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)

    log_startup_hint(settings)
    await start_bot(context)
    maintenance = asyncio.create_task(_maintenance_loop(context))

    try:
        await stop_event.wait()
    except asyncio.CancelledError:  # pragma: no cover - cancellation during shutdown
        pass
    finally:
        maintenance.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await maintenance
        await shutdown(context)
    return 0


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    """SIGINT/SIGTERM trigger a graceful shutdown (POSIX only)."""
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except (NotImplementedError, RuntimeError, ValueError):  # pragma: no cover - Windows
            with contextlib.suppress(Exception):
                signal.signal(sig, lambda *_: stop_event.set())


async def _maintenance_loop(context: AppContext) -> None:
    """Periodic housekeeping: prune caches, back up, log a heartbeat."""
    settings = context.settings
    while True:
        try:
            await asyncio.sleep(MAINTENANCE_INTERVAL)
            if context.antispam is not None:
                context.antispam.prune_history()
            context.states.prune()
            context.repo.prune_rate_limits()
            context.admin_cache.clear()

            age = backup_age(settings)
            if age is None or age.total_seconds() > BACKUP_INTERVAL:
                result = await asyncio.to_thread(create_backup, settings, context.repo)
                logger.info("Automatic backup: %s", result.as_text())

            logger.info(
                "Heartbeat | uptime=%s users=%s tickets_open=%s",
                context.uptime,
                context.repo.user_stats()["total"],
                context.repo.count_open_tickets(),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Maintenance pass failed: %s", exc, exc_info=True)


async def _safe_disconnect(client: TelegramClient) -> None:
    with contextlib.suppress(Exception):
        await client.disconnect()


# --------------------------------------------------------------------------- #
# Diagnostics (used by `bot check`)
# --------------------------------------------------------------------------- #
def check_environment(settings: Settings) -> tuple[bool, list[str]]:
    """Validate configuration, directories, database and locales."""
    problems: list[str] = []
    notes: list[str] = []

    if not settings.owner_ids:
        notes.append("OWNER_IDS is empty - nobody can use the owner panel (send /id to the bot to learn your id).")
    if not settings.log_chat_id:
        notes.append("LOG_CHAT_ID is not set - moderation events are only written to the local log files.")

    for path in (settings.data_path, settings.session_path, settings.log_path):
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            problems.append(f"Directory not writable: {path} ({exc})")

    try:
        context = build_context(settings)
    except (ConfigError, StorageError) as exc:
        problems.append(f"Database error: {exc}")
        return False, problems + notes

    health = context.db.health()
    if not health.get("ok"):
        problems.append(f"Database unhealthy: {health.get('error')}")
    else:
        notes.append(f"Database OK: {health['path']} (schema v{health['schema_version']}, {health['tables']} tables)")

    coverage = context.i18n.coverage()
    notes.append(f"Locales: {', '.join(context.i18n.languages)} (coverage {coverage:.0%})")
    if coverage < 1.0:
        notes.append("Some translation keys are missing in at least one locale - run `make test` for details.")

    token = settings.bot_token_value
    notes.append(
        f"Credentials: api_id={settings.api_id} hash=...{settings.api_hash_value[-4:]} token={token.split(':')[0]}:***"
    )
    notes.append(
        f"Features: tickets={settings.feature_tickets} moderation={settings.feature_moderation} "
        f"antispam={settings.feature_antispam} broadcast={settings.feature_broadcast}"
    )
    context.db.close()
    return not problems, problems + notes


def print_report(settings: Settings, ok: bool, lines: list[str], *, stream: Any = None) -> None:
    """Pretty-print the ``bot check`` report."""
    stream = stream or sys.stdout
    print(f"\n{APP_NAME} v{__version__} - environment check", file=stream)
    print("=" * 58, file=stream)
    for line in lines:
        print(f"  • {line}", file=stream)
    print("-" * 58, file=stream)
    print("  ✅ configuration looks good" if ok else "  ❌ problems found - fix them before running", file=stream)
    print(file=stream)


def session_file(settings: Settings) -> Path:
    return settings.session_path / f"{SESSION_NAME}.session"


def log_startup_hint(settings: Settings) -> None:
    """Explain the very first run to the operator (once, at startup)."""
    if not session_file(settings).exists():
        logger.info("First run detected: the Telegram session will be created at %s", session_file(settings))
    logger.debug("Local time: %s", now(settings.timezone).isoformat(timespec="seconds"))
