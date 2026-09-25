#!/usr/bin/env bash
# =============================================================================
#  Convenience wrapper around systemctl for the reporter service.
#  Usage: bash scripts/service.sh {start|stop|restart|status|logs|enable|disable}
# =============================================================================
set -Eeuo pipefail

UNIT="reporter.service"
ACTION="${1:-status}"

command -v systemctl >/dev/null 2>&1 || { echo "systemd is not available on this system." >&2; exit 1; }
systemctl list-unit-files 2>/dev/null | grep -q "^${UNIT}" || {
  echo "$UNIT is not installed. Run: sudo bash scripts/install.sh --service" >&2; exit 1;
}

case "$ACTION" in
  start|stop|restart|status|enable|disable)
    sudo systemctl "$ACTION" "$UNIT" --no-pager
    ;;
  logs)
    sudo journalctl -u "$UNIT" -f --no-pager
    ;;
  errors)
    sudo journalctl -u "$UNIT" -p err -n 100 --no-pager
    ;;
  *)
    echo "Usage: bash scripts/service.sh {start|stop|restart|status|logs|errors|enable|disable}" >&2
    exit 2
    ;;
esac
