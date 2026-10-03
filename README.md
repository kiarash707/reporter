# Reporter Dashboard

Independent read-only monitoring dashboard for the Reporter Telegram bot.

## Features

- Live bot status
- Telegram connection status
- Uptime
- Users/admins/session counts
- Daily/weekly send counters
- Live runtime logs
- Automatic refresh

## Environment variables

```text
BOT_INTERNAL_URL=http://reporter.railway.internal:8080
MONITOR_TOKEN=<same token configured on reporter>
DASHBOARD_USER=admin
DASHBOARD_PASSWORD=<strong password>
PORT=8080
```

The dashboard is intentionally a separate Railway service. If the dashboard service crashes or is redeployed, the Telegram bot remains independent.
