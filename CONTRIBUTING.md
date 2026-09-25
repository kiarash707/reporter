# Contributing

Thanks for your interest! Bug reports, documentation fixes and pull requests are
all welcome.

## Getting started

```bash
git clone https://github.com/kiarash707/reporter.git && cd reporter
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # dummy values are enough for the test suite
pytest
```

## Before you open a pull request

```bash
ruff check .            # must pass
ruff format --check .   # must pass (run `ruff format .` to fix)
pytest --cov            # must pass
```

Guidelines:

* One topic per pull request; small and reviewable beats large and clever.
* Every new behaviour needs a test; every new user-facing string needs a key in
  **both** `bot/i18n/locales/fa.json` and `en.json`.
* New commands must define a module-level `*_PATTERN` so the registry (and the
  catch-all fallback) sees them, and must be wrapped in `@guard(...)`.
* Never commit credentials, `.env` files, session files, databases or logs.
* Update the docs when the configuration surface or commands change.

## Reporting bugs

Use the bug report template and include the output of `bash scripts/doctor.sh`
with secrets removed, the exact commands you ran and the relevant log lines.
Security issues go through [SECURITY.md](SECURITY.md), not the public tracker.

## Commit messages

Short imperative subject, optional body explaining *why*:

```text
Add per-group link whitelist

ANTISPAM_ALLOWED_DOMAINS now also accepts subdomains, which the previous
exact-match implementation rejected.
```

## Code of conduct

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
