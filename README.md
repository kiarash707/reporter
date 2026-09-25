<div align="center">

# 🤖 Telegram Community Bot

**A production-ready, modular Telegram community & moderation bot built on Telethon.**

Tickets · moderation · anti-spam · i18n (fa/en) · SQLite · systemd & Docker ready

[![CI](https://github.com/kiarash707/reporter/actions/workflows/ci.yml/badge.svg)](../../actions/workflows/ci.yml)
[![Release](https://github.com/kiarash707/reporter/actions/workflows/release.yml/badge.svg)](../../actions/workflows/release.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Code style](https://img.shields.io/badge/code%20style-ruff-000000)](https://github.com/astral-sh/ruff)

[Quick start](docs/quickstart.md) · [Installation](docs/installation.md) · [Configuration](docs/configuration.md) · [Commands](docs/commands.md) · [نصب فارسی](docs/installation.fa.md)

</div>

---

## What is this?

A clean, well-tested Telegram bot template for running a community: it answers
users, opens support tickets, moderates groups, keeps a full audit trail and
deploys the same way on a laptop, a VPS or in Docker.

It is deliberately conservative: **no user-bot automation, no scraping, no
automated messaging to people who did not contact you.** Everything runs through
one bot token, which is what Telegram's terms expect.

## Features

| | |
| --- | --- |
| 🎫 **Support tickets** | Multi-step conversation flow (subject → body → staff reply), statuses, cooldowns, per-user limits, inline actions |
| 🛡️ **Moderation** | `/warn`, `/mute`, `/ban`, `/kick`, `/purge`, `/pin`, rules per group, warning history, automatic warn→mute→ban escalation |
| 🚫 **Anti-spam** | Flood protection, banned words (plain or regex), link filtering with a domain whitelist, new-member restrictions, configurable action (`delete`/`warn`/`mute`) |
| 🧑‍💼 **Roles** | Owners from `.env`, staff list in the database, per-handler permission decorators, rate limits, maintenance and on/off switches |
| 👑 **Owner panel** | Buttons for toggles, broadcast with pacing + FloodWait retry, backups, audit log, stats, legacy import, locale reload |
| 🌍 **Bilingual** | Persian and English UI, per-user language, hot-reloadable JSON locale files |
| 💾 **Storage** | SQLite (WAL) with versioned migrations, automatic backups with retention, atomic snapshots |
| 🧰 **Operations** | `python -m bot run\|check\|backup\|migrate\|import-legacy`, one-shot installer, systemd unit, Dockerfile, Compose, `scripts/doctor.sh`, `scripts/update.sh` |
| ✅ **Quality** | 150+ unit tests, ruff lint/format, mypy config, GitHub Actions CI on Python 3.10–3.12, Docker build check |

## Quick install (60 seconds)

```bash
git clone https://github.com/kiarash707/reporter.git && cd reporter
bash scripts/install.sh          # venv + dependencies + .env + config check
nano .env                        # API_ID, API_HASH, BOT_TOKEN, OWNER_IDS
.venv/bin/python -m bot check    # validates .env, dirs and database
.venv/bin/python -m bot run      # 🚀 talk to your bot
```

Run it as a background service:

```bash
sudo bash scripts/install.sh --service     # systemd unit, auto-restart, hardened
systemctl status reporter
journalctl -u reporter -f
```

Prefer containers?

```bash
cp .env.example .env && nano .env
docker compose -f deploy/docker/docker-compose.yml up -d --build
```

Full walkthroughs for every method: **[docs/installation.md](docs/installation.md)** ·
**[راهنمای فارسی](docs/installation.fa.md)**

## Installation methods

| # | Method | Command | Best for |
| - | ------ | ------- | -------- |
| 1 | Automated installer | `bash scripts/install.sh` | everyone |
| 2 | Manual venv | `python3 -m venv .venv && pip install -r requirements.txt` | full control |
| 3 | systemd service | `sudo bash scripts/install.sh --service` | VPS / bare metal |
| 4 | Docker | `docker build -f deploy/docker/Dockerfile -t tg-bot .` | isolated hosts |
| 5 | Docker Compose | `docker compose -f deploy/docker/docker-compose.yml up -d` | homelabs |
| 6 | Python package | `pip install .` → `bot run` | using it as a library/CLI |
| 7 | No-root install | `bash scripts/install.sh --skip-system-deps --no-service` | shared hosting |

## Configuration

Everything lives in `.env` — never in the code. The minimum:

```dotenv
API_ID=1234567                                            # https://my.telegram.org
API_HASH=0123456789abcdef0123456789abcdef
BOT_TOKEN=123456789:AA...                                 # @BotFather
OWNER_IDS=123456789                                       # @userinfobot
```

Sensible defaults are provided for the rest: timezone and language, feature
switches, anti-spam thresholds, rate limits, ticket limits and broadcast pacing.
See **[docs/configuration.md](docs/configuration.md)** for the complete table and
[`.env.example`](.env.example) for the annotated template.

## Commands

`/start` `/help` `/id` `/lang` `/rules` `/ticket` `/mytickets` `/ping` for
everyone; `/tickets` `/reply` `/open` `/close` `/admin` `/warn` `/mute` `/ban`
`/kick` `/purge` `/pin` `/setrules` `/warns` `/unwarn` `/unmute` `/unban` for
staff; `/adminpanel` `/staff` `/broadcast` `/backup` `/audit` `/stats`
`/maintenance` `/togglebot` `/block` `/importdb` `/reloadlocales` for owners.

Full matrix with permissions: **[docs/commands.md](docs/commands.md)**.

## Project structure

```text
bot/            application package (handlers, services, storage, i18n, utils)
deploy/         systemd unit template + Docker/Compose deployment
docs/           quickstart, installation, configuration, commands, security, …
scripts/        install.sh · update.sh · uninstall.sh · backup.sh · doctor.sh · service.sh
tests/          150+ unit tests running without network or credentials
```

Architecture details and extension points: **[docs/architecture.md](docs/architecture.md)**.

## Operations

```bash
bash scripts/doctor.sh        # paste-ready diagnostic report
bash scripts/backup.sh        # timestamped archive in data/backups/
bash scripts/update.sh        # backup → pull → deps → migrate → restart
bash scripts/service.sh logs  # tail the systemd service
sudo bash scripts/uninstall.sh [--purge]
```

## Development

```bash
pip install -r requirements-dev.txt
pytest --cov            # 150+ tests, no network required
ruff check . && ruff format --check .
mypy bot
```

Contributions are welcome — read [CONTRIBUTING.md](CONTRIBUTING.md) and
[docs/development.md](docs/development.md) first.

## Security

Secrets belong in `.env` (mode `600`) and `sessions/` (mode `700`); both are
git-ignored and the logger masks them. Never commit them, and revoke a token
immediately if it ever leaked. Details and hardening notes:
[docs/security.md](docs/security.md) · [SECURITY.md](SECURITY.md).

## License

MIT — see [LICENSE](LICENSE).

<div align="center"><sub>Built with <a href="https://docs.telethon.dev">Telethon</a> · <a href="https://docs.pydantic.dev">pydantic</a></sub></div>
