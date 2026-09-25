"""Owner-only broadcast with flood-aware pacing and per-user result tracking."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from telethon import TelegramClient, errors

from bot.storage.repository import Repository

logger = logging.getLogger("bot.services.broadcast")

StatusCallback = Callable[[int, int], Awaitable[None]]


@dataclass(slots=True)
class BroadcastReport:
    total: int = 0
    sent: int = 0
    failed: int = 0
    blocked: int = 0
    flood_waits: int = 0
    errors: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, int]:
        return {
            "total": self.total,
            "sent": self.sent,
            "failed": self.failed,
            "blocked": self.blocked,
            "flood_waits": self.flood_waits,
        }


class BroadcastService:
    """Sends a message to every reachable user, respecting Telegram limits."""

    def __init__(self, repo: Repository, *, delay: float = 0.06, concurrency: int = 4) -> None:
        self.repo = repo
        self.delay = max(0.0, float(delay))
        self.concurrency = max(1, int(concurrency))

    async def send(
        self,
        client: TelegramClient,
        text: str,
        *,
        progress: StatusCallback | None = None,
        progress_every: int = 25,
        parse_mode: str | None = "html",
    ) -> BroadcastReport:
        targets = self.repo.broadcast_targets()
        report = BroadcastReport(total=len(targets))
        if not targets:
            return report

        semaphore = asyncio.Semaphore(self.concurrency)
        lock = asyncio.Lock()

        async def deliver(user_id: int) -> None:
            async with semaphore:
                try:
                    await client.send_message(user_id, text, parse_mode=parse_mode)
                except errors.FloodWaitError as exc:
                    wait = min(int(exc.seconds), 300)
                    async with lock:
                        report.flood_waits += 1
                    logger.warning("Broadcast flood wait %ss", wait)
                    await asyncio.sleep(wait)
                    try:
                        await client.send_message(user_id, text, parse_mode=parse_mode)
                    except Exception as exc2:
                        async with lock:
                            report.failed += 1
                            report.errors[type(exc2).__name__] = report.errors.get(type(exc2).__name__, 0) + 1
                        return
                except (errors.UserIsBlockedError, errors.InputUserDeactivatedError, errors.PeerIdInvalidError) as exc:
                    async with lock:
                        report.blocked += 1
                        report.errors[type(exc).__name__] = report.errors.get(type(exc).__name__, 0) + 1
                    self.repo.set_blocked(user_id, True, reason=f"broadcast: {type(exc).__name__}")
                    return
                except Exception as exc:
                    async with lock:
                        report.failed += 1
                        report.errors[type(exc).__name__] = report.errors.get(type(exc).__name__, 0) + 1
                    logger.debug("Broadcast to %s failed: %s", user_id, exc)
                    return

                async with lock:
                    report.sent += 1
                    done = report.sent + report.failed + report.blocked
                    if progress and done % progress_every == 0:
                        await progress(done, report.total)
                if self.delay:
                    await asyncio.sleep(self.delay)

        tasks = [asyncio.create_task(deliver(int(target["user_id"]))) for target in targets]
        await asyncio.gather(*tasks, return_exceptions=True)

        if progress:
            await progress(report.total, report.total)
        self.repo.increment_counter("broadcasts")
        self.repo.increment_counter("broadcast_delivered", report.sent)
        logger.info("Broadcast finished: %s", report.as_dict())
        return report
