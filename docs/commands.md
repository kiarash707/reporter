# Commands and buttons

Regenerate this list from the code with:

```bash
.venv/bin/python -c "from bot.handlers.commands import collect_known_commands as c; print('\n'.join(sorted(c())))"
```

Permissions: 🌍 anyone · 👤 private chat · 🧑‍💼 staff (owners + added staff) ·
👑 owner · 🏘️ group only.

## General

| Command | Who | Where | Description |
| --- | --- | --- | --- |
| `/start` | 🌍 | 👤 | Welcome message, main menu, language choice |
| `/help` | 🌍 | any | Command overview for the caller's role |
| `/id` | 🌍 | any | Your id, the chat id and, when used as a reply, the target's id |
| `/lang` | 🌍 | any | Switch between `fa` and `en` |
| `/rules` | 🌍 | 🏘️ | Show the group rules (`/setrules` to edit them) |
| `/ping` | 🌍 | any | Uptime and latency probe |
| `/cancel` | 🌍 | any | Abort the current input flow (e.g. a half-written ticket) |

## Support tickets

| Command | Who | Where | Description |
| --- | --- | --- | --- |
| `/ticket` | 🌍 | 👤 | Start a ticket: subject → message. Subject and body are validated, then staff is notified |
| `/mytickets` | 🌍 | 👤 | List your tickets with their status |
| `/tickets` | 🧑‍💼 | any | Staff queue: newest open tickets with quick actions |
| `/reply <id>` | 🧑‍💼 | any | Reply to a ticket (or `/reply` after using a reply button) |
| `/open <id>` | 🧑‍💼 | any | Reopen a closed ticket |
| `/close <id>` | 🧑‍💼 / 🌍 | any | Close a ticket; users may close their own |

Ticket statuses: `OPEN` → `ANSWERED` → `CLOSED`. Limits come from
`TICKET_COOLDOWN_SECONDS` and `TICKET_MAX_OPEN`. Ticket ids are stable and
referenced by the inline buttons (`ticket:reply:<id>`, `ticket:close:<id>`,
`ticket:open:<id>`).

## Group moderation

| Command | Who | Description |
| --- | --- | --- |
| `/admin` | 🧑‍💼 | Moderation panel with the group's toggles |
| `/warn [user] [reason]` | 🧑‍💼 | Warn a user (reply, @username or numeric id) |
| `/unwarn [user]` | 🧑‍💼 | Remove one warning |
| `/warns [user]` | 🧑‍💼 | Show the warning history |
| `/mute [user] [duration]` | 🧑‍💼 | Mute for `10m`, `2h`, `1d`, … (bare number = minutes, `0` = forever) |
| `/unmute [user]` | 🧑‍💼 | Remove a mute |
| `/ban [user] [reason]` | 🧑‍💼 | Ban and record the reason |
| `/unban [user]` | 🧑‍💼 | Lift a ban |
| `/kick [user]` | 🧑‍💼 | Remove from the group (they may rejoin) |
| `/purge [count]` | 🧑‍💼 | Delete recent messages (up to 100, defaults to the replied message onward) |
| `/pin` | 🧑‍💼 | Pin the replied message |
| `/setrules <text>` | 🧑‍💼 | Replace the group rules |

Automatic escalation: warning count ≥ `ANTISPAM_WARN_LIMIT` → mute,
≥ `ANTISPAM_BAN_LIMIT` → ban. Every moderation action is written to the audit
log (`/audit`) and, when `LOG_CHAT_ID` is set, mirrored to that chat.

## Owner panel

| Command | Description |
| --- | --- |
| `/adminpanel` | Runtime toggles (bot on/off, maintenance mode, features) |
| `/staff`, `/addstaff <id>`, `/delstaff <id>` | Manage staff |
| `/togglebot` | Stop/start answering commands without stopping the process |
| `/maintenance [on\|off] [message]` | Maintenance mode with a custom notice |
| `/broadcast` | Send a message to every user who started the bot; supports pinning and a preview/confirm step |
| `/backup` | Create and send a backup archive |
| `/importdb <path>` | Import a legacy JSON export |
| `/audit [count]` | Recent audit entries |
| `/stats` | Users, groups, tickets, warns, uptime |
| `/block <id> [reason]`, `/unblock <id>` | Block/unblock a user globally |
| `/reloadlocales` | Re-read `bot/i18n/locales/*.json` without restarting |

Owner-only commands are rate-limit exempt but otherwise obey the same guard as
everything else: they run wherever the owner uses them, while `/adminpanel` and
`/broadcast` require a **private chat** so that a compromised group cannot be
used to open the owner panel or start a broadcast.

## Buttons

Callbacks follow `scope:action[:id]`, e.g. `menu:home`, `menu:lang:fa`,
`grp:antispam`, `own:toggle`, `ticket:reply:42`, `rules:accept`. Unknown
callbacks are answered with a short "unknown action" toast instead of an error.
All button labels are translated (fa/en) through `bot/i18n/locales/*.json`.

## Adding a command

1. Add the pattern as a module-level `*_PATTERN` string in the handler module
   (the registry scans for those names, so the command is documented and the
   catch-all keeps ignoring it).
2. Decorate the handler with `@guard(ctx, ...)` for permissions.
3. Add the translated reply strings to both locale files.
4. Register the function in the module's `register(...)` hook and cover it with
   a test in `tests/`.
