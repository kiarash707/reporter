# FAQ

**Do I need a phone number or a user account to run the bot?**
No. It runs on a bot token, which is exactly why it is safe to host on a server.

**Where do I get `API_ID` and `API_HASH`?**
<https://my.telegram.org> → log in → *API development tools* → create an app.
The id is a number, the hash is 32 hexadecimal characters.

**Which Python versions are supported?**
3.10 and newer; CI runs the suite on 3.10, 3.11 and 3.12.

**Does it need a database server?**
No. SQLite lives in `DATA_DIR` (WAL mode) and needs no daemon.

**Can I run several bots from one checkout?**
Yes — copy the directory (or use `--dir`), give each a distinct `.env`, `DATA_DIR`,
`SESSION_DIR` and service name. Never share a session file between processes.

**Does it work in channels?**
It is designed for groups and private chats. Channel support is limited to
reading/post logging; moderation commands need a group.

**How do I add a second language?**
Copy `bot/i18n/locales/en.json`, translate the values, save it as `xx.json`, then
`/reloadlocales`. The parity test in `tests/test_i18n.py` keeps the key sets equal.

**How do I give a moderator rights without making them an owner?**
`/addstaff <numeric-id>`. Staff can moderate and answer tickets; owners manage the
bot itself.

**Is there a web dashboard?**
No, and it is deliberate: the owner panel is a Telegram inline keyboard, which
keeps the deployment surface minimal.

**Can I use this as the base for my own project?**
Yes, MIT licence — keep `LICENSE`. Renaming the package is a matter of editing
`pyproject.toml`, `bot/__init__.py` and `docs/`.

**How do I migrate from an older JSON-based version?**
`python -m bot import-legacy path/to/export.json` (owner command `/importdb`) —
it validates the payload and merges users, warns and staff.

**Where are the logs?**
`logs/bot.log` (everything) and `logs/errors.log` (warnings/errors), plus
`journalctl -u reporter` under systemd. Rotation is automatic.

**Why did my broadcast stop halfway?**
Telegram flood control. The bot retries the failing target once and continues;
users that repeatedly fail are marked as unreachable (`set_blocked`). Increase
`BROADCAST_DELAY` for large audiences.

**How do I completely reset the bot?**
Stop it, delete `data/` (or run `/importdb` afterwards with a fresh state) and
`sessions/`; the next start recreates everything.

**Is the anti-spam bot-wide or per group?**
Per group, through each group's panel (`/admin`) and the `ANTISPAM_*` defaults.
Channel-wide or cross-group bans are not implemented.

**Something is broken. What do I send in the issue?**
`bash scripts/doctor.sh` output (secrets removed), the exact commands, and the
relevant lines from `logs/errors.log`.
