# Security policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| 2.x     | ✅ |
| < 2.0   | ❌ |

## Reporting a vulnerability

Please **do not** open a public issue. Use GitHub's private reporting:

* Security → Advisories → *Report a vulnerability*, or
* e-mail the maintainer listed in `pyproject.toml`.

Include the version (`python -m bot --version`), the affected component, a
minimal reproduction and, if possible, a suggested fix. We aim to acknowledge
reports within a few days and to release a fix as soon as it is verified.

## In scope

* Authentication/authorisation mistakes that let a non-owner reach owner
  commands or read another user's tickets.
* Injection through user input (regex, SQL, path handling in `/importdb`).
* Secret exposure through logs, error messages or backups.
* Denial of service reachable through ordinary Telegram messages.

## Out of scope

* Misconfiguration of a self-hosted instance (weak file permissions, public
  `.env`, an owner that hands out staff rights too generously).
* Telegram-side limitations such as `FloodWaitError` or privacy mode.
* Anything requiring an attacker to already control the host.

## Basic hygiene for operators

* Keep `.env` at mode `600`, `sessions/` at `700`, and run as an unprivileged user.
* Revoke a leaked bot token via [@BotFather](https://t.me/BotFather) `/revoke`;
  recreate a leaked `API_HASH` at <https://my.telegram.org>.
* Keep the OS and dependencies updated (`bash scripts/update.sh`).
* Take regular backups (`bash scripts/backup.sh`) and store them off the host.
