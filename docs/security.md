# Security

## Secrets

| Secret | Where it lives | Never |
| --- | --- | --- |
| `API_ID`, `API_HASH` | `.env` (mode `600`) | committed, pasted in issues, shared in screenshots |
| `BOT_TOKEN` | `.env` (mode `600`) | logged, sent to users, stored in the database |
| `sessions/*.session` | `sessions/` (mode `700`) | committed, copied to a public host, mailed around |

`.gitignore` excludes `.env`, `*.session*`, `data/`, `logs/` and the virtual
environment. The logger installs a `SecretFilter` that masks the bot token and
the API hash inside every log record, and suppresses debug-level records that
mention credential keywords such as `token`, `api_hash` or `password`.

If a secret leaked:

1. Bot token → [@BotFather](https://t.me/BotFather) → `/revoke` → put the new
   token in `.env` → `sudo systemctl restart reporter`.
2. `API_HASH` → <https://my.telegram.org> → *API development tools* → delete the
   application and create a new one. The old hash cannot be "regenerated".
3. Session files → delete them; the bot re-creates one on the next start.
4. Check `git log -p -- .env` and your forks — history is public forever, so
   rotate first, clean history second.

## Permissions inside Telegram

* Owners (`OWNER_IDS`) and staff (`/addstaff`) are the only accounts that reach
  destructive handlers; every handler is wrapped in `@guard(...)` and the guard
  is default-deny.
* `/adminpanel` and `/broadcast` are private-chat only.
* Staff commands in groups are ignored while the bot is switched off or in
  maintenance mode; `/ping`, `/start` and `/help` keep working.
* Give the bot only the group rights it needs: *Delete messages*, *Ban users*,
  *Restrict members*, *Pin messages*. It never needs to be an administrator in
  channels, and it never needs to know your password (bots do not log in as a
  user account).

## Host hardening

* Run as a dedicated unprivileged user (`useradd --system reporter`); the
  shipped systemd unit adds `NoNewPrivileges`, `ProtectSystem=full`,
  `ProtectHome=read-only`, `PrivateTmp` and `RestrictSUIDSGID`.
* Keep the install directory readable only by that user: `chmod 700 /opt/reporter`.
* Keep the OS updated; the bot only performs outbound TLS connections, so no
  inbound firewall rule is required.
* In Docker, do not add `--privileged` or mount the Docker socket; the provided
  image already drops to uid 10001.

## Data the bot stores

Only what it needs to work: user ids, usernames, language, message counters,
warnings, tickets, audit entries and group settings. Message bodies are **not**
archived; the ticket text you send is stored because that is the point of a
ticket. `/importdb` accepts only local file paths and validates the structure
before writing.

## Abuse prevention

* Anti-spam is per group and configurable (`ANTISPAM_*`), acting only where the
  bot is an administrator.
* Command rate limiting (`RATELIMIT_*`) protects staff endpoints; owners are
  exempt.
* Broadcasts are paced (`BROADCAST_DELAY`, `BROADCAST_CONCURRENCY`) and retry a
  `FloodWait` once before marking a user as unreachable.
* Blocked users (`/block`) are refused by the ticket flow and skipped by
  broadcasts.

## Reporting a vulnerability

Please open a private security advisory on GitHub rather than a public issue
(see [SECURITY.md](../SECURITY.md)).
