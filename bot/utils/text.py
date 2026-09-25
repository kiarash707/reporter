"""Text helpers: escaping, truncation and message splitting."""

from __future__ import annotations

import html
import re

TELEGRAM_MESSAGE_LIMIT = 4096
TELEGRAM_CAPTION_LIMIT = 1024
_ELLIPSIS = "…"
_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")


def escape_html(value: object) -> str:
    """Escape a user-supplied value so it is safe inside parse_mode=HTML."""
    return html.escape(str(value), quote=False)


def strip_tags(value: str) -> str:
    """Remove HTML tags - useful when a plain-text preview is needed."""
    return _TAG_RE.sub("", value)


def truncate(value: str, limit: int = TELEGRAM_MESSAGE_LIMIT, suffix: str = _ELLIPSIS) -> str:
    """Cut ``value`` so it fits into ``limit`` characters, keeping the suffix."""
    if limit <= 0:
        return ""
    if len(value) <= limit:
        return value
    if len(suffix) >= limit:
        return value[:limit]
    return value[: limit - len(suffix)].rstrip() + suffix


def split_message(value: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Split long text into chunks, preferring paragraph/line/word boundaries."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    text = value.strip("\n")
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        window = remaining[:limit]
        cut = -1
        for separator in ("\n\n", "\n", ". ", " "):
            index = window.rfind(separator)
            if index > 0 and index > cut:
                cut = index + (len(separator) if separator == ". " else 0)
        if cut <= 0:
            cut = limit
        chunk = remaining[:cut].rstrip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[cut:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks


def mention(user_id: int, name: str | None = None, *, html: bool = True) -> str:
    """Build a mention - an HTML link when ``html`` is true, ``@id`` otherwise."""
    safe_name = escape_html(name) if name else str(user_id)
    if html:
        return f'<a href="tg://user?id={int(user_id)}">{safe_name}</a>'
    return f"@{user_id}"


def mask(value: str, *, visible: int = 4) -> str:
    """Mask a secret for logs: ``123456789:AAH...`` -> ``1234********``."""
    value = str(value)
    if len(value) <= visible:
        return "*" * len(value)
    return value[:visible] + "*" * (len(value) - visible)


def bullet_list(items: list[str], *, marker: str = "•") -> str:
    """Render a simple bullet list."""
    return "\n".join(f"{marker} {item}" for item in items)


def title_case_safe(value: str) -> str:
    """Trim and collapse whitespace without changing the case/language."""
    return " ".join(str(value).split())


def parse_csv(value: str | None) -> list[str]:
    """Parse a comma/newline separated env value into a clean list.

    Inline ``# comments`` are ignored, so both of these are valid::

        ANTISPAM_ALLOWED_DOMAINS=github.com,docs.python.org   # whitelist
        ANTISPAM_BANNED_WORDS=first
                              second
    """
    if not value:
        return []
    items: list[str] = []
    for raw_line in str(value).splitlines():
        line = re.sub(r"\s+#.*$", "", raw_line).strip()
        if not line or line.startswith("#"):
            continue
        items.extend(part.strip() for part in line.split(",") if part.strip())
    return items
