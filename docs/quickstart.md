# Quickstart

Five minutes from a fresh server to a bot that answers `/start`.

## 0. Prerequisites

* A Linux/macOS machine (Windows works through WSL or Docker)
* Python **3.10+** — check with `python3 --version`
* `git`
* Telegram credentials:
  * `API_ID` and `API_HASH` from <https://my.telegram.org> → *API development tools*
  * `BOT_TOKEN` from [@BotFather](https://t.me/BotFather) → `/newbot`
  * your numeric user id for `OWNER_IDS` (ask [@userinfobot](https://t.me/userinfobot))

> Treat these three values like passwords. They belong in `.env`, never in code,
> never in a screenshot and never in a git commit.

## 1. Get the code

```bash
git clone https://github.com/<you>/<your-fork>.git reporter
cd reporter
```

## 2. Install

```bash
bash scripts/install.sh
```

The installer creates `.venv`, installs the dependencies, copies
`.env.example` to `.env` with `600` permissions and runs a configuration check.
It never asks for root unless you request the systemd service.

## 3. Configure

```bash
nano .env
```

Minimum you must fill in:

```dotenv
API_ID=1234567
API_HASH=0123456789abcdef0123456789abcdef
BOT_TOKEN=123456789:AA...your-token...
OWNER_IDS=123456789
```

Everything else has a sane default — see [configuration.md](configuration.md).

## 4. Validate

```bash
.venv/bin/python -m bot check
```

A green line means the credentials are present, the timezone parses and the
directories are writable. Any problem is reported with the field name.

## 5. Run

```bash
.venv/bin/python -m bot run
```

Open your bot in Telegram and send `/start`. In a group where the bot is an
admin, `/admin` opens the moderation panel.

Stop with `Ctrl+C` — the bot logs out and closes the database cleanly.

## 6. Run it as a service (recommended)

```bash
sudo bash scripts/install.sh --service
sudo systemctl status reporter
journalctl -u reporter -f
```

The rest of your life with the bot: `bash scripts/update.sh` to upgrade,
`bash scripts/backup.sh` before risky changes, `bash scripts/doctor.sh` when
something looks wrong.

## Where to go next

* [configuration.md](configuration.md) — feature flags, anti-spam thresholds, limits
* [commands.md](commands.md) — the full command list
* [deployment.md](deployment.md) — Docker, reverse-proxy hosts, updates, backups
* [troubleshooting.md](troubleshooting.md) — when it refuses to start
