"""Tiny in-memory conversation store with TTL pruning.

Telethon's ``conversation`` API is great for linear dialogs, but this project
needs a *stateless* flow where every message can carry the flow forward, so a
small keyed store is easier to reason about (and to unit test).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("bot.services.states")

DEFAULT_TTL = 15 * 60  # a half-finished dialog should not live forever


@dataclass(slots=True)
class State:
    name: str
    data: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.monotonic)

    def age(self) -> float:
        return time.monotonic() - self.created_at


class StateStore:
    """Keyed by user id: at most one pending flow per user."""

    def __init__(self, ttl: int = DEFAULT_TTL) -> None:
        self.ttl = ttl
        self._states: dict[int, State] = {}

    def set(self, user_id: int, name: str, **data: Any) -> State:
        state = State(name=name, data=dict(data))
        self._states[int(user_id)] = state
        logger.debug("State set for %s: %s", user_id, name)
        return state

    def get(self, user_id: int) -> State | None:
        state = self._states.get(int(user_id))
        if state is None:
            return None
        if state.age() > self.ttl:
            self.clear(user_id)
            return None
        return state

    def is_(self, user_id: int, name: str) -> bool:
        state = self.get(user_id)
        return state is not None and state.name == name

    def update(self, user_id: int, **data: Any) -> State | None:
        state = self.get(user_id)
        if state is None:
            return None
        state.data.update(data)
        return state

    def clear(self, user_id: int) -> bool:
        return self._states.pop(int(user_id), None) is not None

    def prune(self) -> int:
        expired = [user_id for user_id, state in self._states.items() if state.age() > self.ttl]
        for user_id in expired:
            self._states.pop(user_id, None)
        return len(expired)

    def __len__(self) -> int:
        return len(self._states)

    def __contains__(self, user_id: object) -> bool:
        try:
            return self.get(int(user_id)) is not None  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False
