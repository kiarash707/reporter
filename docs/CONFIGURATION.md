# Configuration notes

The current source defines its Telegram and application configuration directly in the Python source.

Before running your own deployment, review the configuration section near the top of the source and set the values required by your own Telegram bot and administrators.

Typical values used by this project include:

- API_ID
- API_HASH
- BOT_TOKEN
- OWNER_IDS
- REPORT_GROUP_ID
- SUPPORT_USERNAME

The source also contains runtime settings and data paths. Keep the source logic unchanged unless you intentionally maintain your own fork.
