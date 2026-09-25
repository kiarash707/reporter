"""Command line interface: ``python -m bot <command>``."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from bot import APP_NAME, __version__
from bot.app import check_environment, print_report, run
from bot.config import load_settings
from bot.errors import BotError, ConfigError

EXIT_OK = 0
EXIT_CONFIG_ERROR = 2
EXIT_RUNTIME_ERROR = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bot",
        description=f"{APP_NAME} - Telegram community & moderation bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python -m bot run                 start the bot (default)\n"
            "  python -m bot check               validate .env, directories and database\n"
            "  python -m bot backup              write a backup archive to data/backups\n"
            "  python -m bot import-legacy FILE  import users/tickets from the old JSON file\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("run", help="start the bot (default when no command is given)")
    sub.add_parser("check", help="validate configuration and environment")
    sub.add_parser("backup", help="create a backup archive of the runtime data")
    sub.add_parser("migrate", help="apply pending database migrations and exit")

    importer = sub.add_parser("import-legacy", help="import data from the previous version's JSON file")
    importer.add_argument("path", type=Path, help="path to the legacy JSON file (e.g. data/state.json)")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    command = args.command or "run"

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"\n❌ Configuration error\n\n{exc}\n", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    if command == "check":
        ok, lines = check_environment(settings)
        print_report(settings, ok, lines)
        return EXIT_OK if ok else EXIT_CONFIG_ERROR

    if command == "backup":
        return _backup(settings)

    if command == "migrate":
        return _migrate(settings)

    if command == "import-legacy":
        return _import_legacy(settings, args.path)

    try:
        return asyncio.run(run(settings))
    except KeyboardInterrupt:  # pragma: no cover - interactive stop
        print("\n👋 Stopped by user.")
        return EXIT_OK
    except BotError as exc:
        print(f"\n❌ {exc}\n", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    except Exception as exc:
        print(f"\n💥 Unhandled error: {type(exc).__name__}: {exc}\n", file=sys.stderr)
        return EXIT_RUNTIME_ERROR


def _backup(settings) -> int:
    from bot.services.backup import create_backup
    from bot.storage.database import Database
    from bot.storage.repository import Repository

    settings.prepare_directories()
    db = Database(settings.db_file)
    try:
        db.migrate()
        result = create_backup(settings, Repository(db, timezone=settings.timezone), include_sessions=True)
    finally:
        db.close()
    print(f"✅ Backup created: {result.as_text()}")
    return EXIT_OK


def _migrate(settings) -> int:
    from bot.storage.database import Database

    settings.prepare_directories()
    db = Database(settings.db_file)
    try:
        version = db.migrate()
        health = db.health()
    finally:
        db.close()
    print(f"✅ Database ready: {health['path']} (schema v{version}, {health['tables']} tables)")
    return EXIT_OK


def _import_legacy(settings, path: Path) -> int:
    from bot.storage.database import Database
    from bot.storage.repository import Repository

    resolved = settings.resolve(path)
    if not resolved.is_file():
        print(f"❌ File not found: {resolved}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    settings.prepare_directories()
    db = Database(settings.db_file)
    try:
        db.migrate()
        summary = Repository(db, timezone=settings.timezone).import_legacy_json(resolved)
    finally:
        db.close()
    print("✅ Legacy import finished:")
    for key, value in summary.items():
        print(f"   • {key}: {value}")
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())
