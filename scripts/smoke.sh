#!/usr/bin/env bash
# =============================================================================
#  Release smoke test - verifies the whole chain in a throwaway copy of the
#  project, without touching your working tree or your real .env.
#
#  Usage: bash scripts/smoke.sh [--keep]
#    --keep   keep the temporary directory for inspection (its path is printed)
# =============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
KEEP="no"
[[ "${1:-}" == "--keep" ]] && KEEP="yes"
cd "$ROOT_DIR"

PY="python3"
[[ -x .venv/bin/python ]] && PY="$ROOT_DIR/.venv/bin/python"

pass() { printf '\033[32m  ✓\033[0m %s\n' "$*"; }
fail() { printf '\033[31m  ✗\033[0m %s\n' "$*" >&2; exit 1; }
step() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/bot-smoke-XXXXXX")"
cleanup() { [[ "$KEEP" == "yes" ]] || rm -rf "$TMP"; }
trap cleanup EXIT

step "Copying the project to $TMP"
tar --exclude=.git --exclude=.venv --exclude=data --exclude=logs --exclude=sessions \
    --exclude='__pycache__' --exclude='.pytest_cache' --exclude='.ruff_cache' \
    --exclude='*.egg-info' -cf - . | (cd "$TMP" && tar -xf -)
cd "$TMP"
[[ -f bot/cli.py ]] || fail "copy looks wrong (bot/cli.py missing)"
pass "project copied"

step "Writing a disposable .env"
cat > .env <<'ENVEOF'
API_ID=987654321
API_HASH=4f1b7c9d2e5a8b3c6d9e0f1a2b3c4d5e
BOT_TOKEN=123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw
OWNER_IDS=123456789
ENVIRONMENT=production
TIMEZONE=Asia/Tehran
DEFAULT_LANGUAGE=fa
LOG_LEVEL=INFO
ENVEOF
pass ".env written"

step "CLI: version"
"$PY" -m bot --version | grep -q "telegram-community-bot" || fail "--version"
pass "$("$PY" -m bot --version)"

step "CLI: check (valid configuration)"
"$PY" -m bot check >/dev/null || fail "check with a valid .env must exit 0"
pass "configuration valid"

step "CLI: check (broken configuration must fail loudly)"
sed -i.bak 's/^BOT_TOKEN=.*/BOT_TOKEN=/' .env
if "$PY" -m bot check >/dev/null 2>&1; then fail "check must fail with a missing token"; fi
mv .env.bak .env
pass "invalid configuration rejected with a non-zero exit code"

step "CLI: migrate"
"$PY" -m bot migrate >/dev/null || fail "migrate"
[[ -f data/state.db ]] || fail "migrate did not create data/state.db"
pass "database created ($(du -h data/state.db | cut -f1))"

step "CLI: import-legacy"
cat > legacy.json <<'JSONEOF'
{"users": [11, 22], "blocked": [22], "user_lang": {"11": "fa"}, "support_tickets": {}}
JSONEOF
"$PY" -m bot import-legacy legacy.json >/dev/null || fail "import-legacy"
pass "legacy payload imported"

step "CLI: backup"
"$PY" -m bot backup >/dev/null || fail "backup"
ARCHIVE="$(ls -1t data/backups/*.tar.gz 2>/dev/null | head -1)"
[[ -n "$ARCHIVE" ]] || fail "no backup archive produced"
tar -tzf "$ARCHIVE" >/dev/null || fail "backup archive is not a readable tar.gz"
pass "archive verified: $(basename "$ARCHIVE")"

step "Modules load cleanly"
"$PY" - <<'PYEOF' || fail "importing the package failed"
import bot
from bot.app import build_context, install_event_loop_policy
from bot.config import load_settings
from bot.handlers import register_all
from bot.i18n import Translator
from bot.keyboards import main_menu

settings = load_settings()
context = build_context(settings)
assert context.settings is settings
assert context.repo is not None
translator = Translator()
assert translator.languages, "no locales loaded"
assert all(translator.t(key, "fa") for key in list(translator._catalogs["fa"])[:5])
print(f"      version={bot.__version__} locales={','.join(translator.languages)} loop={install_event_loop_policy()}")
PYEOF
pass "imports, context wiring and locales are healthy"

echo
printf '\033[1;32m✅ Smoke test passed\033[0m\n'
if [[ "$KEEP" == "yes" ]]; then
  echo "   kept: $TMP"
fi
exit 0
