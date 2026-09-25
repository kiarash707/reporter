# Configuration

All configuration lives in a single `.env` file next to the project.

```bash
cp .env.example .env
chmod 600 .env
nano .env
.venv/bin/python -m bot check     # verifies every value
```

Nothing is read from the environment of the shell unless it is defined in
`.env` — the file is the single source of truth and is git-ignored.

## Required values

| Variable | Type | Description |
| --- | --- | --- |
| `API_ID` | int | Telegram application id from <https://my.telegram.org> |
| `API_HASH` | 32 hex chars | Telegram application hash |
| `BOT_TOKEN` | string | Bot token from [@BotFather](https://t.me/BotFather), format `123456:ABC...` |
| `OWNER_IDS` | list of ints | Users with full access. Comma separated: `111111,222222` |

The bot refuses to start with placeholder values such as `your-token-here`,
`changeme` or `<token>` — this catches the "forgot to edit `.env`" mistake.

## Optional values

| Variable | Default | Description |
| --- | --- | --- |
| `LOG_CHAT_ID` | *(empty)* | Channel/group id (e.g. `-1001234567890`) that receives moderation and error reports. The bot must be able to post there. |
| `ENVIRONMENT` | `production` | `development` lowers log noise expectations and enables debug tooling. |
| `TIMEZONE` | `Asia/Tehran` | Any IANA zone; used for timestamps, ticket ids and log files. Invalid zones abort startup. |
| `DEFAULT_LANGUAGE` | `fa` | `fa` or `en`; the language shown to users who have not chosen one. |
| `DATA_DIR` | `data` | SQLite database and backups. Relative paths resolve against the project root. |
| `SESSION_DIR` | `sessions` | Telethon session files (a login credential — keep private). |
| `LOG_DIR` | `logs` | Rotating log files. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `LOG_JSON` | `false` | `true` writes one JSON object per line for log collectors. |
| `LOG_ROTATE_MB` | `5` | Rotate a log file after this many megabytes. |
| `LOG_BACKUP_COUNT` | `5` | Rotated files kept per log. |

## Feature switches

| Variable | Default | Effect when `false` |
| --- | --- | --- |
| `FEATURE_TICKETS` | `true` | `/ticket`, `/mytickets` reply "feature disabled" |
| `FEATURE_MODERATION` | `true` | `/warn`, `/mute`, `/ban`, … reply "feature disabled" |
| `FEATURE_ANTISPAM` | `true` | no automatic flood/word/link filtering |
| `FEATURE_BROADCAST` | `true` | `/broadcast` is refused |

Owners can flip most of these at runtime from `/adminpanel`; the `.env` value is
the value used at startup.

## Anti-spam

| Variable | Default | Description |
| --- | --- | --- |
| `ANTISPAM_FLOOD_MESSAGES` | `8` | Messages allowed inside the window before action. |
| `ANTISPAM_FLOOD_WINDOW` | `10` | Window length in seconds. |
| `ANTISPAM_ACTION` | `warn` | What happens on flood: `delete`, `warn` or `mute`. |
| `ANTISPAM_MUTE_MINUTES` | `60` | Mute duration for flood/treshold escalations (`0` = permanent). |
| `ANTISPAM_WARN_LIMIT` | `3` | Warnings before an automatic mute. |
| `ANTISPAM_BAN_LIMIT` | `5` | Warnings before an automatic ban. |
| `ANTISPAM_BLOCK_LINKS` | `false` | Delete messages containing links. |
| `ANTISPAM_ALLOWED_DOMAINS` | *(empty)* | Comma separated whitelist, e.g. `github.com,docs.python.org`. |
| `ANTISPAM_BANNED_WORDS` | *(empty)* | Comma separated plain words or regular expressions. |
| `ANTISPAM_NEW_USER_SECONDS` | `0` | Treat members younger than this as "new" and apply link filtering to them. |

Anti-spam only acts in groups where the bot is an administrator with the
*Delete messages* permission. Its own administrators and staff are exempt.

## Limits and cooldowns

| Variable | Default | Description |
| --- | --- | --- |
| `RATELIMIT_COMMANDS` | `20` | Commands per user per window. |
| `RATELIMIT_WINDOW` | `60` | Window length in seconds. |
| `TICKET_COOLDOWN_SECONDS` | `300` | Minimum delay between two tickets of the same user. |
| `TICKET_MAX_OPEN` | `3` | Maximum simultaneously open tickets per user. |
| `BROADCAST_DELAY` | `0.06` | Seconds between broadcast messages; raise it if you see flood waits. |
| `BROADCAST_CONCURRENCY` | `4` | Parallel deliveries; 1–8 is a sane range. |

Owners bypass the command rate limit.

## Validation rules

* Lists accept commas and/or whitespace: `OWNER_IDS=1, 2 3` → `(1, 2, 3)`.
* Inline comments after values are stripped: `TIMEZONE=Europe/Berlin  # my zone` works.
* Empty values mean "not configured" (never an empty string where an id is
  expected).
* Unknown keys are ignored — typos in names are *not* reported, so after editing
  run `python -m bot check` and look for the warning summary.
* `python -m bot check` exits `0` when valid and `2` when something is missing or
  malformed, printing the offending field.

## Example: production group admin

```dotenv
ENVIRONMENT=production
TIMEZONE=Europe/Berlin
DEFAULT_LANGUAGE=en
LOG_CHAT_ID=-1001234567890
LOG_JSON=true
ANTISPAM_FLOOD_MESSAGES=6
ANTISPAM_FLOOD_WINDOW=10
ANTISPAM_ACTION=mute
ANTISPAM_MUTE_MINUTES=120
ANTISPAM_BLOCK_LINKS=true
ANTISPAM_ALLOWED_DOMAINS=github.com
BROADCAST_DELAY=0.1
BROADCAST_CONCURRENCY=2
```
