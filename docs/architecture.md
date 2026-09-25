# Architecture

## Design goals

1. **One responsibility per module** — a handler only translates Telegram events
   into service calls; a service only implements behaviour; the repository only
   talks to the database.
2. **Explicit dependencies** — everything a handler needs hangs off a single
   `AppContext` object, which makes handlers trivially testable without a live
   Telegram connection.
3. **Fail loudly at startup, softly at runtime** — a broken `.env` aborts before
   the bot connects; a failing command answers the user with a friendly error and
   is written to `logs/errors.log`.
4. **No secrets in code** — configuration comes from `.env`, logs are sanitised.

## Layout

```text
bot/
├── __init__.py          version / project constants
├── __main__.py          entry point for `python -m bot`
├── cli.py               argparse CLI: run | check | backup | migrate | import-legacy
├── app.py               builds the client, supervises background tasks, graceful shutdown
├── context.py           AppContext: settings + storage + services, shared by handlers
├── config.py            pydantic-settings model, .env parsing, validation
├── errors.py            domain exceptions (AccessDenied, RateLimited, StorageError, …)
├── logging_setup.py     console + rotating files, SecretFilter, optional JSON lines
├── handlers/            Telegram-facing layer
│   ├── guard.py         decorator: permissions, rate limit, maintenance, error mapping
│   ├── common.py        /start /help /id /lang /cancel, shared keyboards and menus
│   ├── tickets.py       support ticket flows (state machine)
│   ├── owner.py         owner panel, staff, broadcast, backup, audit, import
│   ├── moderation.py    /warn /mute /ban /purge /pin /rules and escalation
│   ├── health.py        /ping and the catch-all fallback (registered last)
│   └── commands.py      the command registry (patterns → names)
├── keyboards/           inline keyboard builders + callback constants
├── services/            reusable behaviour, no Telegram imports
│   ├── roles.py         owner/staff resolution with a warm cache
│   ├── ratelimit.py     fixed-window limiter
│   ├── moderation.py    warn/mute/ban logic incl. duration parsing
│   ├── antispam.py      flood, banned-word, link and new-user checks
│   ├── broadcast.py     throttled fan-out with FloodWait retry
│   ├── stats.py         aggregate counters for /stats
│   ├── backup.py        tar.gz archives + retention
│   └── states.py        TTL state store used by multi-step flows
├── storage/
│   ├── database.py      SQLite connection, WAL, schema migrations
│   └── repository.py    queries grouped by concern (users, tickets, warns, audit…)
├── i18n/                Translator + locales/{fa,en}.json
└── utils/               text, time and Telegram helpers
```

## Request lifecycle

```text
Telegram update ─► Telethon dispatch
                 ─► handler (matched by message regex / callback data)
                     ├─ @guard: bot enabled? maintenance? permissions? rate limit?
                     ├─ service call (moderation, tickets, broadcast, …)
                     │     └─ repository → SQLite
                     └─ reply / edit / answer callback
                 ─► errors mapped to translated user messages + logs
```

`AppContext` is created once in `bot/app.py` and passed to every handler at
registration time, so there is no global mutable state beyond the SQLite
connection and the two small caches (roles, admin TTL).

## Handler ordering

Handlers are registered in a fixed order — `common → tickets → owner →
moderation → health` — because Telethon runs **all** matching handlers in
registration order and only `StopPropagation` stops the chain. The catch-all in
`health.py` is therefore registered last, and it skips any text that matches a
known command from the registry. If you add a handler, register it before
`health.register(...)` in `bot/handlers/__init__.py`.

## State

* **Persistent** — SQLite in `data/state.db` (WAL mode), schema version tracked in
  `schema_version` and migrated forward at startup.
* **Session** — Telethon's `.session` file in `sessions/`; deleting it forces a new
  bot login (harmless for bots, they authenticate with the token).
* **Short-lived** — `StateStore` (multi-step flows, 15 min TTL) and the two caches
  (`roles`, `admin_cache`), all in memory and rebuilt on restart.
* **Backups** — `data/backups/state-<timestamp>.tar.gz`, seven kept by default.

## Extension points

| I want to… | Touch this |
| --- | --- |
| add a command | new `*_PATTERN` + handler in `bot/handlers/`, register it, add locale keys |
| add a language | drop `bot/i18n/locales/xx.json` with the same keys, run the parity test |
| add a table/column | bump `SCHEMA_VERSION` and add a migration step in `storage/database.py` |
| add a background task | `bot/app.py` — create the task in the startup hook and cancel it on shutdown |
| change permissions | `bot/handlers/guard.py` and `bot/services/roles.py` |
| change button layout | `bot/keyboards/inline.py` (constants are re-exported from `bot/keyboards`) |

## Testing strategy

Handlers are unit-tested with lightweight fakes (`tests/conftest.py` provides
`FakeEvent`, `FakeMessage`, `FakeClient`, in-memory settings and a temporary
database), so the suite runs without network access and finishes in seconds.
`pytest --cov` currently covers the storage layer, services, config, i18n,
keyboards and the main flows.
