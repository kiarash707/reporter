"""Aggregated statistics used by /stats and the owner panel."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from bot.utils.time import humanize_delta, now

if TYPE_CHECKING:  # pragma: no cover - typing only
    from bot.context import AppContext

logger = logging.getLogger("bot.services.stats")


def collect(ctx: AppContext) -> dict[str, Any]:
    """Gather a flat statistics payload (safe to call from any handler)."""
    users = ctx.repo.user_stats()
    counters = ctx.repo.all_counters()
    health = ctx.db.health()
    warnings_total = int(ctx.db.scalar("SELECT COUNT(*) FROM warnings", default=0))
    groups_total = int(ctx.db.scalar("SELECT COUNT(*) FROM groups", default=0))

    return {
        "users_total": users["total"],
        "users_active": users["active"],
        "users_blocked": users["blocked"],
        "groups_total": groups_total,
        "tickets_open": ctx.repo.count_open_tickets(),
        "tickets_total": int(ctx.db.scalar("SELECT COUNT(*) FROM tickets", default=0)),
        "warnings_total": warnings_total,
        "commands": counters.get("commands", 0),
        "broadcasts": counters.get("broadcasts", 0),
        "antispam_deleted": counters.get("antispam_deleted", 0),
        "antispam_warned": counters.get("antispam_warned", 0),
        "uptime": humanize_delta(now("UTC") - ctx.started_at),
        "db_size_kb": round(int(health.get("size_bytes", 0)) / 1024, 1),
        "schema_version": health.get("schema_version", 0),
        "db_ok": bool(health.get("ok")),
    }


def render(ctx: AppContext, language: str) -> str:
    """Human-readable statistics message."""
    data = collect(ctx)
    lines = [
        ctx.tr("stats.title", language),
        ctx.tr(
            "stats.users",
            language,
            total=data["users_total"],
            active=data["users_active"],
            blocked=data["users_blocked"],
        ),
        ctx.tr("stats.groups", language, groups=data["groups_total"]),
        ctx.tr("stats.tickets", language, open_tickets=data["tickets_open"]),
        ctx.tr("stats.warnings", language, warnings=data["warnings_total"]),
        ctx.tr("stats.commands", language, commands=data["commands"]),
        ctx.tr("stats.uptime", language, uptime=data["uptime"]),
        ctx.tr("stats.db", language, size=data["db_size_kb"], schema=data["schema_version"]),
    ]
    return "\n".join(lines)
