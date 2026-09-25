"""Single source of truth for the command names the bot actually implements.

The catch-all handler must stay silent for commands that a real handler owns,
otherwise ``/start`` would be answered twice (catch-all + start handler).
``collect_known_commands()`` derives the list from the registered patterns so it
can never drift away from the handlers.
"""

from __future__ import annotations

import logging
import re
from types import ModuleType

logger = logging.getLogger("bot.handlers.commands")

_COMMAND_IN_PATTERN = re.compile(r"\^/\(?([a-z_|]+)\)?")

# Commands handled through callbacks or helper patterns that are not obvious
# from a "/name" prefix inside a pattern string.
EXTRA_COMMANDS = frozenset({"start", "ticket", "mytickets"})


def command_names_of(pattern: str) -> set[str]:
    """Extract command names from a handler pattern.

    ``^/warn...`` -> ``{"warn"}`` and ``^/(block|unblock)...`` -> both names.
    """
    match = _COMMAND_IN_PATTERN.match(pattern)
    if not match:
        return set()
    return {name for name in match.group(1).split("|") if name}


def command_name_of(pattern_or_text: str) -> str | None:
    """Single-command convenience wrapper (first name wins)."""
    names = command_names_of(pattern_or_text)
    return sorted(names)[0] if names else None


def collect_known_commands(*modules: ModuleType) -> frozenset[str]:
    """Union of every ``*_PATTERN`` command across the handler modules."""
    if not modules:
        from bot.handlers import common, moderation, owner, tickets

        modules = (common, moderation, owner, tickets)

    names: set[str] = set(EXTRA_COMMANDS)
    for module in modules:
        for attribute in dir(module):
            if not attribute.endswith("_PATTERN"):
                continue
            value = getattr(module, attribute)
            if not isinstance(value, str):
                continue
            names.update(command_names_of(value))
    logger.debug("Known commands: %s", ", ".join(sorted(names)))
    return frozenset(names)
