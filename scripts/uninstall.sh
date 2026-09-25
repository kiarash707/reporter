#!/usr/bin/env bash
# =============================================================================
#  Remove the bot. By default only the service is removed; runtime data (the
#  database and your .env) is kept unless --purge is given.
#
#  Usage: sudo bash scripts/uninstall.sh [--purge] [--yes]
# =============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PURGE="no"; ASSUME_YES="no"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --purge) PURGE="yes"; shift ;;
    --yes|-y) ASSUME_YES="yes"; shift ;;
    -h|--help) sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

step() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[32m  ✓\033[0m %s\n' "$*"; }
warn() { printf '\033[33m  !\033[0m %s\n' "$*" >&2; }
confirm() {
  [[ "$ASSUME_YES" == "yes" ]] && return 0
  [[ ! -t 0 ]] && return 1
  read -r -p "  $1 [y/N] " reply; [[ "$reply" =~ ^[Yy]$ ]]
}

if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files 2>/dev/null | grep -q '^reporter.service'; then
  step "Stopping and removing the systemd service"
  sudo systemctl stop reporter.service 2>/dev/null || true
  sudo systemctl disable reporter.service 2>/dev/null || true
  sudo rm -f /etc/systemd/system/reporter.service
  sudo systemctl daemon-reload
  ok "Service removed"
else
  warn "No reporter.service unit found"
fi

if [[ "$PURGE" == "yes" ]]; then
  if confirm "Delete runtime data (data/, logs/, sessions/, .env, .venv) in $ROOT_DIR?"; then
    step "Removing runtime data"
    rm -rf "$ROOT_DIR/data" "$ROOT_DIR/logs" "$ROOT_DIR/sessions" "$ROOT_DIR/.venv"
    rm -f "$ROOT_DIR/.env"
    ok "Runtime data removed"
  else
    warn "Kept runtime data"
  fi
else
  ok "Runtime data kept (use --purge to delete it as well)"
fi

echo
ok "Uninstall finished. The source tree in $ROOT_DIR was not deleted."
