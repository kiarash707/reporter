# Telegram Temporary Email Bot

A Node.js Telegram bot for managing temporary email accounts and inboxes through Telegram.

## ⚠️ Security

**Never commit a real Telegram bot token, API key, password, session, or private runtime data.**

The original uploaded source contained hard-coded sensitive values. They must not be stored in Git history. This repository therefore uses environment variables for secrets.

If a real bot token was ever committed to any Git repository, rotate it through **@BotFather** before using the project again.

## Requirements

- Node.js 18+ recommended
- npm
- A Telegram bot token
- Telegram user ID(s) for administrators

## Installation

```bash
git clone https://github.com/kiarash707/reporter.git
cd reporter
npm install
```

Create the environment file:

```bash
cp .env.example .env
```

Edit `.env`:

```env
BOT_TOKEN=YOUR_BOT_TOKEN_HERE
ADMIN_IDS=YOUR_TELEGRAM_USER_ID_HERE
```

Start:

```bash
npm start
```

## Configuration

### BOT_TOKEN

Create/manage the bot with Telegram's **@BotFather** and place the token in `.env`.

### ADMIN_IDS

Set one or more numeric Telegram user IDs separated by commas:

```env
ADMIN_IDS=123456789,987654321
```

Do not put usernames in this variable.

## Runtime data

The application can create local runtime data such as:

- `Accounts/`
- `Accounts/mails/`
- `Backups/`
- `BannedUsers/`
- `bot_settings.json`

These paths are intentionally excluded from Git by `.gitignore`.

## Project structure

```text
.
├── gmasaz.js
├── package.json
├── .env.example
├── .gitignore
├── CHANGELOG.md
└── README.md
```

## Troubleshooting

### Bot does not start

Check:

1. Node.js is installed: `node --version`
2. Dependencies are installed: `npm install`
3. `.env` exists.
4. `BOT_TOKEN` is set.
5. The token is valid and has not been revoked.

### No admin access

Verify that `ADMIN_IDS` contains your numeric Telegram user ID and that there are no accidental spaces or non-numeric values.

### Polling errors

Check the terminal output for Telegram API errors. Make sure another running instance is not using the same bot token.

## Deployment

For a private VPS/Ubuntu deployment:

```bash
git clone https://github.com/kiarash707/reporter.git
cd reporter
npm install
cp .env.example .env
nano .env
npm start
```

For production, use a process manager such as systemd or PM2 and keep `.env` outside version control.

## Development notes

The uploaded project is a single-file Node.js application. Before adding major features, consider separating configuration, Telegram handlers, email-provider integration, persistence, and administrative logic into dedicated modules.

## License

No license has been declared yet. Until a license is added by the project owner, the repository should be treated as **all rights reserved**.
