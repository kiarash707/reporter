"""Tiny JSON-based translation layer (no runtime dependency).

Usage::

    translator = Translator(default_language="fa")
    translator.t("start.welcome", language="en", name="Ali")
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("bot.i18n")

LOCALES_DIR = Path(__file__).resolve().parent / "locales"
FALLBACK_LANGUAGE = "en"


class Translator:
    """Loads ``locales/<lang>.json`` catalogues and formats messages."""

    def __init__(self, locales_dir: Path | None = None, default_language: str = "fa") -> None:
        self.locales_dir = Path(locales_dir) if locales_dir else LOCALES_DIR
        self.default_language = default_language
        self._catalogs: dict[str, dict[str, str]] = {}
        self._missing: set[str] = set()
        self.load()

    # --- loading -------------------------------------------------------------
    def load(self) -> dict[str, int]:
        """(Re)load every catalogue; returns the key count per language."""
        self._catalogs.clear()
        for path in sorted(self.locales_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.error("Cannot load locale %s: %s", path.name, exc)
                continue
            if not isinstance(payload, dict):
                logger.error("Locale %s must contain a JSON object", path.name)
                continue
            self._catalogs[path.stem] = {str(key): str(value) for key, value in payload.items()}
        if self.default_language not in self._catalogs and self._catalogs:
            self.default_language = next(iter(self._catalogs))
        logger.debug("Locales loaded: %s", ", ".join(self.languages) or "none")
        return {lang: len(catalog) for lang, catalog in self._catalogs.items()}

    @property
    def languages(self) -> list[str]:
        return sorted(self._catalogs)

    # --- lookups -------------------------------------------------------------
    def t(self, key: str, language: str | None = None, **params: object) -> str:
        """Return a translated, formatted string for ``key``."""
        text = self.raw(key, language)
        if not params:
            return text
        try:
            return text.format(**params)
        except (KeyError, IndexError, ValueError) as exc:
            logger.warning("Bad placeholders for '%s' (%s): %s", key, language, exc)
            return text

    gettext = t

    def raw(self, key: str, language: str | None = None) -> str:
        """Look up a key without formatting, falling back to English/keys."""
        lang = language or self.default_language
        catalog = self._catalogs.get(lang, {})
        if key in catalog:
            return catalog[key]
        fallback = self._catalogs.get(FALLBACK_LANGUAGE, {})
        if key in fallback:
            return fallback[key]
        if lang != self.default_language:
            default_catalog = self._catalogs.get(self.default_language, {})
            if key in default_catalog:
                return default_catalog[key]
        if key not in self._missing:
            self._missing.add(key)
            logger.warning("Missing translation key: %s", key)
        return key

    def has(self, key: str, language: str | None = None) -> bool:
        return key in self._catalogs.get(language or self.default_language, {})

    def normalize_language(self, value: str | None) -> str:
        """Map arbitrary input to a supported language code."""
        if not value:
            return self.default_language
        candidate = str(value).strip().lower()[:2]
        return candidate if candidate in self._catalogs else self.default_language

    def coverage(self) -> float:
        """Share of keys that carry a non-empty translation in every language."""
        if not self._catalogs:
            return 0.0
        every_key: set[str] = set()
        for catalog in self._catalogs.values():
            every_key.update(catalog)
        if not every_key:
            return 0.0
        complete = sum(1 for key in every_key if all(catalog.get(key) for catalog in self._catalogs.values()))
        return round(complete / len(every_key), 4)
