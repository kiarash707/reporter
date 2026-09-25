# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

* CI pipeline (lint, format check, tests on Python 3.10–3.12, mypy, shell syntax,
  Docker build) and release pipeline (wheel/sdist + `ghcr.io` container image).
* `scripts/ci.sh` (and `make ci`) — runs the complete pipeline locally, including
  YAML validation, an optional Docker build and the smoke test.
* `scripts/smoke.sh` (and `make smoke`) — end-to-end release check in a throwaway
  copy: version, configuration validation (valid *and* broken), migration, legacy
  import, backup archive and package/context/locale wiring.
* `AppContext.require_client()` — explicit Telegram client accessor that raises a
  domain error instead of an `AttributeError` when used before startup.
* `bot.app.install_event_loop_policy()` — automatically uses `uvloop` when the
  optional extra is installed, and reports which loop backend is in use.

### Fixed

* `tests/test_config.py::test_is_cached_and_reloadable` no longer depends on the
  developer's local `.env`, so the suite is hermetic on a fresh clone and in CI.
* Telethon 1.45 compatibility in `classify_error` (the removed
  `errors.BotBlockedError` is now looked up defensively).
* Type errors across `bot/` resolved; `mypy bot` is clean and blocking in CI.

## [2.0.0] — 2026-09-25

Complete rewrite as a modular, tested community & moderation bot.

### Added

* Package layout `bot/{handlers,services,storage,i18n,keyboards,utils}` with an
  application context shared by every handler.
* CLI: `python -m bot run|check|backup|migrate|import-legacy` and the `bot`
  console script; exit codes suited to automation.
* Support ticket flow with statuses, cooldowns, limits, staff queue and inline
  actions.
* Moderation suite (`/warn`, `/unwarn`, `/warns`, `/mute`, `/unmute`, `/ban`,
  `/unban`, `/kick`, `/purge`, `/pin`, `/setrules`, `/rules`, `/admin`) with
  audit logging and warn→mute→ban escalation.
* Anti-spam: flood windows, banned words (plain/regex), link filtering with a
  whitelist, new-member restrictions, configurable actions.
* Owner panel with runtime toggles, throttled broadcast, backups, stats, legacy
  import and locale hot-reload.
* Bilingual UI (Persian/English) with 140+ keys per locale and per-user language.
* SQLite storage in WAL mode with versioned migrations, atomic backups and
  retention.
* Structured logging with rotation, credential masking and optional JSON lines.
* One-shot installer plus `update`, `uninstall`, `backup`, `doctor` and
  `service` scripts; systemd unit template; Dockerfile and Compose file.
* Documentation set: quickstart, installation (seven methods), configuration,
  commands, architecture, deployment, security, troubleshooting, FAQ,
  development, and a Persian quick-install guide.
* 150+ unit tests covering configuration, storage, services, handlers, flows,
  keyboards and logging.

### Changed

* Configuration moved to a validated `pydantic-settings` model with placeholder
  detection; invalid values abort startup with the offending field name.
* Timezone handling centralized; every timestamp is rendered in the configured
  zone.

### Removed

* The previous single-file implementation, its embedded credentials and its
  unsolicited mass-messaging behaviour. Configuration now lives exclusively in
  `.env`, and the bot only replies to users who contact it.

### Security

* No secrets in the repository; `.env` and `sessions/` are git-ignored and logs
  are sanitised.
* Handler permissions are default-deny; owner panel and broadcast require a
  private chat.
