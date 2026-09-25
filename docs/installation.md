# Installation

Every supported way to install the bot, from the one-liner to a container
image. Pick **one** method — they all end up running `python -m bot run`.

* [A. Requirements](#a-requirements)
* [B. Method 1 — automated installer (recommended)](#method-1--automated-installer-recommended)
* [C. Method 2 — manual virtual environment](#method-2--manual-virtual-environment)
* [D. Method 3 — systemd service](#method-3--systemd-service)
* [E. Method 4 — Docker](#method-4--docker)
* [F. Method 5 — Docker Compose](#method-5--docker-compose)
* [G. Method 6 — install as a Python package](#method-6--install-as-a-python-package)
* [H. Method 7 — no-root / shared hosting](#method-7--no-root--shared-hosting)
* [I. Updating](#updating)
* [J. Uninstalling](#uninstalling)

---

## A. Requirements

| Component | Minimum | Notes |
| --- | --- | --- |
| Python | 3.10 | 3.11/3.12 recommended (CI tests all three) |
| OS | any Linux, macOS, WSL, Docker | Debian/Ubuntu/RHEL/Alpine/Pacman supported by the installer |
| Disk | ~120 MB | venv + dependencies; logs and backups grow over time |
| RAM | ~120 MB idle | Telethon keeps one connection per bot token |
| Network | outbound HTTPS to `api.telegram.org` | no inbound ports are needed |

Optional but recommended: `cryptg` (faster media transfers),
`uvloop` (faster event loop on Linux) — both are installed by the `fast` extra:

```bash
.venv/bin/pip install -e ".[fast]"
```

### Getting the credentials

1. `API_ID` / `API_HASH` — log in at <https://my.telegram.org>, open
   *API development tools*, create an application if you have none.
2. `BOT_TOKEN` — message [@BotFather](https://t.me/BotFather), `/newbot`,
   answer the two questions, copy the token.
3. `OWNER_IDS` — send `/start` to [@userinfobot](https://t.me/userinfobot).
   Multiple owners are allowed: `OWNER_IDS=111111,222222`.

---

## Method 1 — automated installer (recommended)

```bash
git clone <repository-url> reporter && cd reporter
bash scripts/install.sh
```

What it does, in order:

1. verifies Python ≥ 3.10;
2. installs the OS packages it needs (`python3-venv`, `git`, `ca-certificates`)
   using `apt-get`, `dnf`, `yum`, `apk`, `pacman` or `zypper` — skip with
   `--skip-system-deps`;
3. creates `.venv` and installs `requirements.txt`;
4. copies `.env.example` to `.env` (mode `600`) if `.env` does not exist;
5. runs `python -m bot check` and tells you exactly what is missing;
6. optionally installs and starts the systemd service.

Options:

```text
--dir PATH           install/run from PATH               (default: repository root)
--user NAME          system user that runs the service   (default: current user)
--service            install and start the systemd service
--no-service         never touch systemd
--venv NAME          virtual environment directory       (default: .venv)
--dev                also install development dependencies
--yes, -y            answer "yes" to every question (non-interactive)
--skip-system-deps   do not install OS packages
--no-start           install the service but do not start it
--dry-run            show what would happen and exit
-h, --help           show the help
```

Examples:

```bash
bash scripts/install.sh --dry-run                  # preview, change nothing
bash scripts/install.sh --dev                      # include pytest/ruff/mypy
sudo bash scripts/install.sh --service             # production, systemd
bash scripts/install.sh --dir /srv/bot --venv env   # custom location and venv name
curl -fsSL <installer-url> | bash                  # remote bootstrap (review it first!)
```

The installer is idempotent: running it again upgrades an existing
installation instead of breaking it.

---

## Method 2 — manual virtual environment

For people who want to see every step.

```bash
# 1. system packages (Debian/Ubuntu example)
sudo apt-get update
sudo apt-get install -y python3 python3-venv git

# 2. code
git clone <repository-url> reporter
cd reporter

# 3. isolated environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 4. dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install cryptg                 # optional: faster transfers

# 5. configuration
cp .env.example .env
chmod 600 .env
nano .env                          # fill in API_ID, API_HASH, BOT_TOKEN, OWNER_IDS

# 6. verify and run
python -m bot check
python -m bot run
```

To run it detached without systemd:

```bash
nohup .venv/bin/python -m bot run >> logs/stdout.log 2>&1 &
```

---

## Method 3 — systemd service

```bash
cd /path/to/reporter
sudo bash scripts/install.sh --service --user "$USER"
sudo nano .env                     # credentials
sudo systemctl restart reporter
systemctl status reporter
```

The unit is rendered from [`deploy/systemd/reporter.service.in`](../deploy/systemd/reporter.service.in),
which hardens the process (`NoNewPrivileges`, `ProtectSystem=full`,
`ProtectHome=read-only`, `PrivateTmp`) and restarts it automatically.
Day-to-day commands:

```bash
bash scripts/service.sh status     # or start|stop|restart|logs|errors|enable|disable
journalctl -u reporter -f
```

Details and a dedicated-user walkthrough: [deploy/systemd/README.md](../deploy/systemd/README.md).

---

## Method 4 — Docker

```bash
docker build -f deploy/docker/Dockerfile -t telegram-community-bot .
docker run -d --name telegram-bot \
  --restart unless-stopped \
  --env-file .env \
  -v "$PWD/data:/app/data" \
  -v "$PWD/sessions:/app/sessions" \
  -v "$PWD/logs:/app/logs" \
  telegram-community-bot
docker logs -f telegram-bot
```

The image runs as the unprivileged user `botuser` (uid 10001) and includes a
`HEALTHCHECK` that opens the database. `data/`, `sessions/` and `logs/` are the
only stateful paths — mount them or the state is lost when the container is
recreated.

---

## Method 5 — Docker Compose

```bash
cp .env.example .env && nano .env
docker compose -f deploy/docker/docker-compose.yml up -d
docker compose -f deploy/docker/docker-compose.yml logs -f
docker compose -f deploy/docker/docker-compose.yml down
```

Named volumes (`bot-data`, `bot-sessions`, `bot-logs`) keep the state between
upgrades. Upgrade with:

```bash
git pull && docker compose -f deploy/docker/docker-compose.yml up -d --build
```

---

## Method 6 — install as a Python package

Useful when you want the `bot` command on your `PATH`.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install .            # or: pip install ".[fast]" / pip install ".[dev]"
bot --help
bot check
bot run
```

From a source checkout, `pip install -e .` gives you an editable install that
picks up your changes immediately.

---

## Method 7 — no-root / shared hosting

No root, no systemd, no Docker — a user-space install is fully supported.

```bash
git clone <repository-url> ~/reporter && cd ~/reporter
bash scripts/install.sh --skip-system-deps --no-service
nano .env
.venv/bin/python -m bot check
```

Keep it alive without systemd:

* `cron` watchdog every five minutes:

  ```cron
  */5 * * * * pgrep -f "bot run" >/dev/null || (cd ~/reporter && nohup .venv/bin/python -m bot run >> logs/stdout.log 2>&1 &)
  ```

* `tmux` / `screen` for an interactive session: `tmux new -s bot '.venv/bin/python -m bot run'`
* a user-level systemd unit: `systemctl --user enable --now reporter` with the
  `WantedBy=default.target` variant of the unit file.

---

## Updating

```bash
bash scripts/update.sh                # backup → pull → deps → migrate → restart
bash scripts/update.sh --no-restart   # stage the update, restart later
```

Manual equivalent:

```bash
bash scripts/backup.sh
git pull
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m bot migrate
sudo systemctl restart reporter
```

Database migrations are forward-only and run automatically at startup; taking a
backup first is still the right habit.

---

## Uninstalling

```bash
sudo bash scripts/uninstall.sh            # removes the service, keeps your data
sudo bash scripts/uninstall.sh --purge    # also deletes data/, logs/, sessions/, .env, .venv
```

`--purge` asks for confirmation; the source tree itself is never deleted.
