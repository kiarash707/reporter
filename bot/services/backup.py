"""Backups: consistent SQLite copy plus a compressed archive of runtime data."""

from __future__ import annotations

import logging
import tarfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bot.config import Settings
from bot.errors import StorageError
from bot.storage.repository import Repository
from bot.utils.time import now

logger = logging.getLogger("bot.services.backup")


@dataclass(slots=True)
class BackupResult:
    path: Path
    size_kb: float
    files: int

    def as_text(self) -> str:
        return f"{self.path} ({self.size_kb} KB, {self.files} files)"


def create_backup(
    settings: Settings, repo: Repository, *, keep: int = 7, include_sessions: bool = False
) -> BackupResult:
    """Create ``data/backups/state-<timestamp>.tar.gz`` and prune old archives."""
    backups_dir = settings.data_path / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    timestamp = now(settings.timezone).strftime("%Y%m%d-%H%M%S")
    archive_path = _unique_path(backups_dir, timestamp)

    snapshot = backups_dir / f"state-{timestamp}.db"
    try:
        repo.backup(snapshot)
    except Exception as exc:
        raise StorageError(f"Database backup failed: {exc}") from exc

    sources = [snapshot]
    if include_sessions and settings.session_path.exists():
        sources.extend(settings.session_path.glob("*.session"))

    try:
        with tarfile.open(archive_path, "w:gz") as archive:
            for source in sources:
                archive.add(source, arcname=source.name)
    finally:
        snapshot.unlink(missing_ok=True)

    prune_backups(settings, keep=keep)
    size_kb = round(archive_path.stat().st_size / 1024, 1)
    logger.info("Backup written: %s (%s KB)", archive_path, size_kb)
    return BackupResult(archive_path, size_kb, len(sources))


def _unique_path(backups_dir: Path, timestamp: str) -> Path:
    """Avoid collisions when several backups happen inside the same second."""
    candidate = backups_dir / f"state-{timestamp}.tar.gz"
    counter = 1
    while candidate.exists():
        candidate = backups_dir / f"state-{timestamp}-{counter}.tar.gz"
        counter += 1
    return candidate


def prune_backups(settings: Settings, *, keep: int = 7) -> int:
    """Keep only the newest ``keep`` archives; returns the number removed."""
    backups_dir = settings.data_path / "backups"
    if not backups_dir.exists():
        return 0
    archives = sorted(backups_dir.glob("state-*.tar.gz"), key=lambda path: path.stat().st_mtime, reverse=True)
    removed = 0
    for old in archives[max(1, keep) :]:
        try:
            old.unlink()
            removed += 1
        except OSError as exc:  # pragma: no cover - permissions
            logger.warning("Cannot remove old backup %s: %s", old, exc)
    return removed


def latest_backup(settings: Settings) -> Path | None:
    backups_dir = settings.data_path / "backups"
    if not backups_dir.exists():
        return None
    archives = sorted(backups_dir.glob("state-*.tar.gz"), key=lambda path: path.stat().st_mtime, reverse=True)
    return archives[0] if archives else None


def backup_age(settings: Settings) -> timedelta | None:
    latest = latest_backup(settings)
    if latest is None:
        return None
    return datetime.now(timezone.utc) - datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc)
