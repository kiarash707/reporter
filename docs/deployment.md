# Deployment & operations

## Choosing a method

| Situation | Use |
| --- | --- |
| One small VPS, you want sane defaults | `sudo bash scripts/install.sh --service` |
| You already manage containers | Docker Compose file in `deploy/docker/` |
| No root access | user-space install, `cron`/`tmux` watchdog |
| Several environments (staging/prod) | one directory each, separate `.env` and `--venv` |

## Production checklist

- [ ] `.env` filled in, mode `600`, owned by the service user
- [ ] `OWNER_IDS` contains only your accounts
- [ ] `LOG_CHAT_ID` set to a private channel for alerts (recommended)
- [ ] `ENVIRONMENT=production`, `LOG_LEVEL=INFO` (use `DEBUG` temporarily, never permanently)
- [ ] bot promoted to administrator in every managed group, with *Delete messages* and *Restrict members*
- [ ] backups verified once: `bash scripts/backup.sh` then `ls -lh data/backups`
- [ ] `systemctl status reporter` shows `active (running)` and no restart loop
- [ ] `bash scripts/doctor.sh` output archived for the first incident

## systemd

```bash
sudo bash scripts/install.sh --service
systemctl status reporter
journalctl -u reporter -f
journalctl -u reporter -p err -n 50
sudo systemctl restart reporter          # after .env changes
```

The unit is derived from `deploy/systemd/reporter.service.in` and includes
`Restart=always`, `RestartSec=5`, a 30-second stop timeout and filesystem
hardening. Runtime paths are listed in `ReadWritePaths`, so moving the install
directory means re-running the installer (or re-rendering the template).

Logs go to the journal. `logs/bot.log` and `logs/errors.log` still exist and
rotate at `LOG_ROTATE_MB`; set `LOG_JSON=true` if a collector expects JSON lines.

## Docker

```bash
docker compose -f deploy/docker/docker-compose.yml up -d
docker compose -f deploy/docker/docker-compose.yml ps
docker stats telegram-community-bot
```

* The container runs as uid 10001 (`botuser`) — make sure the mounted host
  directories are writable by that uid (`chown -R 10001:10001 data logs sessions`).
* `HEALTHCHECK` opens the database every minute; `docker inspect --format
  '{{.State.Health.Status}}' telegram-community-bot` shows the verdict.
* Update with `git pull && docker compose ... up -d --build`; the named volumes
  keep the session and the database.

## Updates

```bash
bash scripts/backup.sh      # 1. snapshot
bash scripts/update.sh      # 2. pull + deps + migrate + restart (does 1. for you)
bash scripts/doctor.sh      # 3. verify
```

`update.sh` stashes local modifications instead of discarding them, aborts if
`git pull` cannot fast-forward, and prints the exact command to roll back the
service. Rolling back is `git checkout <previous-tag> && .venv/bin/python -m bot migrate && sudo systemctl restart reporter`;
the database schema is upgraded in place, so keep the backup taken before the
update.

## Backups

| What | Where | How |
| --- | --- | --- |
| Database + locales | `data/backups/state-<ts>.tar.gz` | `bash scripts/backup.sh`, `/backup`, automatic every 24 h |
| Session file | `sessions/*.session` | only with `--with-sessions` (it is a credential) |
| `.env` | outside the archive on purpose | copy it by hand to your secret store |

Retention defaults to the newest seven archives. Restore:

```bash
sudo systemctl stop reporter
tar -xzf data/backups/state-2026-01-31-120000.tar.gz -C data/
sudo systemctl start reporter
```

## Monitoring

* `/ping` in Telegram answers with uptime and latency — usable from any device.
* `scripts/doctor.sh` collects system, configuration and service state in one
  paste-ready report.
* Health from the shell:

  ```bash
  .venv/bin/python -m bot check && journalctl -u reporter -p err -n 20
  ```

* Prometheus/Grafana are intentionally out of scope; `logs/errors.log` plus the
  optional `LOG_CHAT_ID` channel cover the common needs of a community bot.

## Uninstall

```bash
sudo bash scripts/uninstall.sh            # service only, data kept
sudo bash scripts/uninstall.sh --purge    # data, logs, sessions, .env, venv removed
```
