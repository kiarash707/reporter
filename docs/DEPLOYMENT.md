# Deployment Guide

## Requirements
- Ubuntu 22.04/24.04/26.04
- Node.js 18+
- npm
- Telegram bot token from @BotFather

## Install and configure
```bash
node -v
npm -v
npm install
cp .env.example .env
nano .env
```

Set `BOT_TOKEN` and comma-separated `ADMIN_IDS` in `.env`. Never commit `.env`.

## Start
```bash
npm start
```

## systemd
Create `/etc/systemd/system/telegram-mail-bot.service`:

```ini
[Unit]
Description=Telegram Mail Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/telegram-mail-bot
ExecStart=/usr/bin/node /opt/telegram-mail-bot/gmasaz.js
Restart=always
RestartSec=5
Environment=NODE_ENV=production
EnvironmentFile=/opt/telegram-mail-bot/.env

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-mail-bot
sudo systemctl status telegram-mail-bot
journalctl -u telegram-mail-bot -f
```

## Runtime data
The application creates `Accounts/`, `Backups/`, `BannedUsers/`, and `bot_settings.json`. These are intentionally ignored by Git.

## Security
Keep `.env` private. Rotate the Telegram bot token immediately if it has ever been exposed.
