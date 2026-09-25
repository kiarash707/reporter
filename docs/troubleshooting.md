# Troubleshooting

Start here — it answers most "it does not work" questions:

```bash
bash scripts/doctor.sh
```

The report contains versions, configuration names, file permissions, the result
of `python -m bot check` and the last log lines. Remove secrets before sharing it.

---

## The bot does not start

**`Configuration error: BOT_TOKEN is missing or still a placeholder`**
Edit `.env`: the value is empty or still looks like `your-token-here`. Get a real
token from [@BotFather](https://t.me/BotFather) and run
`.venv/bin/python -m bot check`.

**`API_HASH must be the 32 character application hash`**
`API_HASH` is the *hash*, not the *id*. Both come from
<https://my.telegram.org> → *API development tools*.

**`Invalid timezone`**
Use an IANA name: `Europe/Berlin`, `Asia/Tehran`, `UTC`. Abbreviations such as
`CET` or `IRST` are rejected.

**`sqlite3.OperationalError: unable to open database file`**
`DATA_DIR` exists but is not writable by the service user:

```bash
sudo chown -R "$USER":"$USER" data logs sessions
chmod 700 sessions
```

**`ModuleNotFoundError: No module named 'bot'`**
You are running the system Python instead of the virtual environment. Use
`.venv/bin/python -m bot run` or activate it first (`source .venv/bin/activate`).

**Service restarts in a loop** — read the reason:

```bash
journalctl -u reporter -n 50 --no-pager
```

Nine times out of ten it is a missing credential or a wrong `WorkingDirectory`.

---

## The bot is online but silent

| Symptom | Cause | Fix |
| --- | --- | --- |
| Nothing happens in a group | no privacy mode / not an admin | BotFather → `/setprivacy` → *Disable*, then re-add the bot to the group; promote it to admin for moderation |
| Only `/start` works | command sent with a different bot username | commands accept `/cmd@YourBot`, so check the mention |
| "feature disabled" replies | feature flag is off | `FEATURE_*` in `.env` or `/adminpanel` |
| "maintenance" notice | maintenance mode is on | `/maintenance off` as owner |
| No commands after redeploy | `/togglebot` left the bot paused | `/togglebot` again, or restart the service |

---

## Permissions

**`Not enough rights to restrict/unban/etc.`**
The bot must be an administrator with the matching right (*Ban users*,
*Restrict members*, *Delete messages*, *Pin messages*). Re-check the group's
administrator list — Telegram sometimes drops rights after a bot re-add.

**A staff member cannot use `/mute`**
Staff ids are stored in the database; verify with `/staff` and add with
`/addstaff <id>`. Owners bypass the staff list but group checks still apply.

**Owner commands do nothing**
`OWNER_IDS` must contain the **numeric** id of the account (not `@username`).
Send `/id` to the bot to read yours, then restart the service after editing
`.env`.

---

## Flood waits and rate limits

`FloodWaitError` is normal when sending a lot of messages. The bot retries once
and then skips the target.

* Raise `BROADCAST_DELAY` (e.g. `0.2`) and lower `BROADCAST_CONCURRENCY` (e.g. `2`).
* `Rate limited, retry in Ns` comes from `RATELIMIT_*`; owners are exempt, and
  staff can wait or raise the limits.
* Never send broadcasts from several processes with the same token — Telegram
  will throttle the whole account.

---

## Tickets

**`You already have too many open tickets`** — `TICKET_MAX_OPEN` (default 3);
close one with `/close <id>`.

**`Please wait before creating another ticket`** — `TICKET_COOLDOWN_SECONDS`
(default 300).

**A ticket is stuck in a state** — the flow expires after 15 minutes; `/cancel`
clears it immediately, then `/ticket` again.

---

## Anti-spam behaves unexpectedly

* It only acts where the bot is an administrator with *Delete messages*.
* Staff and owners are exempt from every check.
* `ANTISPAM_BANNED_WORDS` entries are treated as regular expressions, so `.*`
  matches everything — escape dots (`example\.com`).
* To diagnose, set `LOG_LEVEL=DEBUG`, reproduce, and read `logs/bot.log`; the
  reasons (`flood`, `banned_word`, `link`) are logged per action.

---

## Docker

**`Permission denied` on mounted directories** — the container uses uid 10001:

```bash
sudo chown -R 10001:10001 data logs sessions
```

**Container exits immediately** — `docker logs telegram-community-bot` shows the
configuration error; remember that `.env` must also be passed with
`--env-file .env` (Compose does it for you).

**Health status `unhealthy`** — the database path inside the container is not
writable; check the volume mounts.

---

## Logs and diagnostics

```bash
tail -f logs/bot.log        # everything
tail -f logs/errors.log     # warnings and errors only
journalctl -u reporter -f   # systemd
docker logs -f telegram-community-bot
```

Set `LOG_LEVEL=DEBUG` temporarily for detailed traces, and `LOG_JSON=true` when
shipping logs into a collector. Remember to revert `DEBUG` afterwards.

If none of this helps, open an issue with the `bug_report.yml` template and
attach the `scripts/doctor.sh` output plus the exact commands you ran.
