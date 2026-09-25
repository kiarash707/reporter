# Development

## Local setup

```bash
git clone <repository-url> reporter && cd reporter
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt     # runtime + pytest/ruff/mypy/build
cp .env.example .env                    # dummy values are fine for tests
pre-commit --version 2>/dev/null || pip install pre-commit   # optional
```

Run the test suite without touching Telegram:

```bash
pytest                     # all tests
pytest -q -x               # stop at the first failure
pytest --cov --cov-report=term-missing
pytest tests/test_flows.py -k ticket -v
```

Everything is unit-tested through the fakes in `tests/conftest.py`; no network
access and no real credentials are required.

## Quality gates

```bash
ruff check .              # lint
ruff format .             # format (CI checks with --check)
mypy bot                  # types (must stay clean)
bash -n scripts/*.sh      # shell syntax
```

Run **everything CI runs** with one command:

```bash
bash scripts/ci.sh              # lint, format, tests+coverage, mypy, shell, YAML
bash scripts/ci.sh --quick      # lint, format, tests only
bash scripts/ci.sh --fix        # let ruff rewrite files instead of failing
bash scripts/ci.sh --docker     # additionally build the container image
bash scripts/ci.sh --install-dev  # install the dev tools first if they are missing
bash scripts/smoke.sh           # end-to-end: install → check → migrate → import → backup
                              # (run scripts/install.sh first if there is no .venv)
bash scripts/ci.sh --smoke      # include the smoke test in the pipeline run
```

On a production-only install (no dev dependencies) or a checkout without a
virtual environment, the script explains what is missing — with the exact
`scripts/install.sh --dev …` command — and still runs the checks that work,
instead of failing with `No module named pytest`.

The same steps are available through `make`: `make ci`, `make ci-quick`,
`make lint`, `make fmt`, `make test`, `make cov`, `make typecheck`,
`make doctor`.

> The test suite is hermetic: it never reads your local `.env` and never touches
> the network, so `bash scripts/ci.sh` passes on a fresh clone.

## Code style

* Line length 120, double quotes, sorted imports (ruff `I` rules enabled).
* Type hints on every public function; `from __future__ import annotations`
  everywhere.
* Services never import from `bot.handlers`; handlers never import from
  `bot.handlers` at module level (use local imports for cross-handler calls, as
  `bot/handlers/__init__.py` imports modules eagerly).
* All user-facing text lives in `bot/i18n/locales/*.json` — never hardcode a
  string in a handler.
* Prefer explicit, small functions over clever one-liners; a reviewer should be
  able to follow the flow in one pass.

## Adding a feature

1. Behaviour goes into `bot/services/` (pure logic, no Telegram imports).
2. Persistence goes into `bot/storage/repository.py` (+ migration if the schema changes).
3. The Telegram surface goes into a handler with a module-level `*_PATTERN`,
   wrapped in `@guard(...)`.
4. Add the locale keys to `fa.json` **and** `en.json`.
5. Add tests: service unit tests, a handler/flow test, and a config test when a
   new variable appears.
6. Update `docs/commands.md` / `docs/configuration.md` if the user-visible
   surface changed.

## Tests layout

| File | Scope |
| --- | --- |
| `test_config.py` | `.env` parsing, validation, placeholder rejection |
| `test_utils.py` | text/time/telegram helpers |
| `test_i18n.py` | locale parity and interpolation |
| `test_storage.py` | database migrations and repository queries |
| `test_services.py` | roles, limits, anti-spam, states, stats, backups |
| `test_broadcast.py` | broadcast delivery, retries, blocked users |
| `test_moderation_service.py` | mute/ban/kick logic and permissions |
| `test_telegram_utils.py` | entity helpers, error classification, flood guard |
| `test_handlers.py` | guard behaviour, handler registration order |
| `test_flows.py` | ticket flows, buttons, escalation |
| `test_logging_and_keyboards.py` | logging filters, JSON mode, keyboard layout |

## Releasing

```bash
# 1. bump the version
$EDITOR pyproject.toml bot/__init__.py CHANGELOG.md
# 2. verify
ruff check . && ruff format --check . && pytest
# 3. tag
git commit -am "Release v2.1.0"
git tag -a v2.1.0 -m "v2.1.0"
git push origin main --tags
```

The `Release` workflow builds a wheel/sdist, attaches them to the GitHub release
and publishes a container image to `ghcr.io/<owner>/<repo>`. The `CI` workflow
runs lint, format check, tests with coverage, shell syntax checking and a Docker
build on every push and pull request.
