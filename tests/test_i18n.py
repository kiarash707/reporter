"""Translation catalogues must stay consistent across languages."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bot.i18n import FALLBACK_LANGUAGE, LOCALES_DIR, Translator


@pytest.fixture(scope="module")
def catalogs() -> dict[str, dict[str, str]]:
    result = {}
    for path in LOCALES_DIR.glob("*.json"):
        result[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return result


def test_both_languages_exist(catalogs: dict[str, dict[str, str]]) -> None:
    assert {"fa", "en"} <= set(catalogs)


def test_catalogues_have_identical_keys(catalogs: dict[str, dict[str, str]]) -> None:
    fa, en = set(catalogs["fa"]), set(catalogs["en"])
    assert fa == en, f"missing in fa: {en - fa} / missing in en: {fa - en}"


def test_no_empty_translations(catalogs: dict[str, dict[str, str]]) -> None:
    for language, catalog in catalogs.items():
        empties = [key for key, value in catalog.items() if not str(value).strip()]
        assert not empties, f"{language} has empty values: {empties}"


def test_translation_and_formatting(translator: Translator) -> None:
    text = translator.t("ticket.created", language="en", ticket_id=7)
    assert "#7" in text
    assert "7" in translator.t("ticket.created", language="fa", ticket_id=7)


def test_missing_key_falls_back_to_key_name(translator: Translator) -> None:
    assert translator.raw("does.not.exist") == "does.not.exist"
    assert translator.has("start.welcome", "en")


def test_fallback_language_is_used_for_unknown_locale(translator: Translator) -> None:
    text = translator.t("start.blocked", language="de")
    assert text == translator.raw("start.blocked", FALLBACK_LANGUAGE)


def test_normalize_language(translator: Translator) -> None:
    assert translator.normalize_language("EN") == "en"
    assert translator.normalize_language("fa-IR") == "fa"
    assert translator.normalize_language("klingon") == translator.default_language
    assert translator.normalize_language(None) == translator.default_language


def test_coverage_is_complete(translator: Translator) -> None:
    assert translator.coverage() == 1.0


def test_broken_placeholder_is_tolerated(translator: Translator) -> None:
    # a missing format argument must not raise inside a handler
    assert "{" in translator.t("stats.users", language="en") or translator.t("common.error", language="en") != ""


def test_custom_locale_directory(tmp_path: Path) -> None:
    (tmp_path / "fa.json").write_text(json.dumps({"hello": "سلام"}), encoding="utf-8")
    translator = Translator(locales_dir=tmp_path, default_language="fa")
    assert translator.t("hello") == "سلام"
    assert translator.languages == ["fa"]
