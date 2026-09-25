# Legacy file notice

`srckde_6aaa664e8d9ed.py` is the **previous, single-file version of this project**.
It is kept in the repository, untouched, because the owner asked for it to stay —
but it is *not* part of the maintained project:

* nothing in `bot/`, `scripts/`, `deploy/`, the CLI or the tests imports, runs or
  deploys it;
* it is excluded from linting (`pyproject.toml` → `extend-exclude`), from type
  checking (which only walks `bot/`) and from the test/coverage scope;
* it is not copied into the container image (`deploy/docker/Dockerfile` copies
  only `bot/`, `main.py` and `pyproject.toml`);
* it is not referenced by any documented installation method.

## Read this before running it

* It contains **hard-coded credentials** (`API_ID`, `API_HASH`, `BOT_TOKEN`,
  owner ids). Treat them as leaked: revoke the bot token with
  [@BotFather](https://t.me/BotFather) → `/revoke` and recreate the application at
  <https://my.telegram.org>. Deleting the file does not remove them from the git
  history.
* It implements **unsolicited mass messaging / coordinated reporting**, which
  violates Telegram's terms of service and gets accounts limited or banned. It is
  not supported, not tested and receives no fixes.

The maintained replacement is the package under `bot/` — start with
[docs/quickstart.md](docs/quickstart.md). It only ever replies to users who
contact it, stores its credentials in `.env` (never in code) and ships with an
installer, tests and CI.
