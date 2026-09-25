#!/usr/bin/env bash
# =============================================================================
#  Collect everything needed to understand a problem (no changes are made).
#  Usage: bash scripts/doctor.sh [> report.txt]
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR" || exit 1

section() { printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
have()    { command -v "$1" >/dev/null 2>&1 && echo yes || echo no; }

section "Bot"
printf 'version      : %s\n' "$(sed -n 's/^__version__ = "\(.*\)"/\1/p' bot/__init__.py 2>/dev/null || echo unknown)"
printf 'project dir  : %s\n' "$ROOT_DIR"
printf 'git revision : %s\n' "$(git rev-parse --short HEAD 2>/dev/null || echo 'not a git checkout')"
printf 'git status   : %s\n' "$(git status --porcelain 2>/dev/null | wc -l) changed file(s)"

section "System"
printf 'os           : %s\n' "$(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME" || uname -sr)"
printf 'kernel       : %s\n' "$(uname -r)"
printf 'arch         : %s\n' "$(uname -m)"
printf 'uptime       : %s\n' "$(uptime -p 2>/dev/null || uptime)"
printf 'disk (root)  : %s\n' "$(df -h / | awk 'NR==2 {print $4" free of "$2}')"

section "Python"
if command -v python3 >/dev/null 2>&1; then printf 'python3      : %s\n' "$(python3 --version 2>&1)"; else printf 'python3      : MISSING\n'; fi
if [[ -x .venv/bin/python ]]; then
  printf 'venv         : %s\n' "$(.venv/bin/python --version 2>&1)"
  printf 'telethon     : %s\n' "$(.venv/bin/python -c 'import telethon; print(telethon.__version__)' 2>/dev/null || echo MISSING)"
  printf 'pydantic     : %s\n' "$(.venv/bin/python -c 'import pydantic; print(pydantic.VERSION)' 2>/dev/null || echo MISSING)"
  printf 'cryptg       : %s\n' "$(.venv/bin/python -c 'import cryptg; print("installed")' 2>/dev/null || echo 'not installed (optional, slower uploads)')"
else
  printf 'venv         : MISSING (run scripts/install.sh)\n'
fi

section "Configuration"
if [[ -f .env ]]; then
  printf '.env         : present (%s lines)\n' "$(wc -l < .env)"
  printf '.env perms   : %s\n' "$(stat -c '%a %U:%G' .env 2>/dev/null || echo unknown)"
  for key in API_ID API_HASH BOT_TOKEN OWNER_IDS LOG_CHAT_ID ENVIRONMENT TIMEZONE DEFAULT_LANGUAGE; do
    value="$(grep -E "^${key}=" .env 2>/dev/null | head -1 | cut -d= -f2-)"
    if [[ -z "$value" ]]; then printf '%-13s: (empty)\n' "$key"
    elif [[ "$key" =~ TOKEN|HASH ]]; then printf '%-13s: set (%s chars)\n' "$key" "${#value}"
    else printf '%-13s: %s\n' "$key" "$value"; fi
  done
else
  printf '.env         : MISSING - copy .env.example to .env and fill it in\n'
fi

section "Runtime data"
for path in data data/state.db logs logs/bot.log sessions; do
  if [[ -e "$path" ]]; then printf '%-14s: %s\n' "$path" "$(du -sh "$path" 2>/dev/null | cut -f1)"; else printf '%-14s: (absent)\n' "$path"; fi
done
printf 'backups      : %s archive(s)\n' "$(ls -1 data/backups/*.tar.gz 2>/dev/null | wc -l)"

section "Configuration check"
if [[ -x .venv/bin/python ]]; then .venv/bin/python -m bot check 2>&1 | tail -n 15; else echo "skipped (no venv)"; fi

section "Service"
if [[ "$(have systemctl)" == "yes" ]] && systemctl list-unit-files 2>/dev/null | grep -q '^reporter.service'; then
  systemctl --no-pager --lines=0 status reporter.service 2>&1 | head -n 12
  echo "--- last log lines ---"
  journalctl -u reporter.service -n 15 --no-pager 2>&1
else
  echo "reporter.service is not installed"
fi

section "Log tail (logs/errors.log)"
[[ -f logs/errors.log ]] && tail -n 20 logs/errors.log || echo "no error log yet"
