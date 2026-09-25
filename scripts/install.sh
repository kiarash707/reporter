#!/usr/bin/env bash
# =============================================================================
#  Telegram Community Bot - one-shot installer
#
#  Usage:
#    bash scripts/install.sh [options]
#
#  Options:
#    --dir PATH        Install/run from PATH            (default: repository root)
#    --user NAME       System user that runs the service (default: current user)
#    --service         Install and start the systemd service
#    --no-service      Do not touch systemd (default when not running as root)
#    --venv NAME       Virtual environment directory    (default: .venv)
#    --dev             Also install development dependencies
#    --yes             Answer "yes" to every question (non-interactive)
#    --skip-system-deps  Do not install OS packages
#    --dry-run         Show what would happen and exit
#    -h, --help        Show this help
# =============================================================================
set -Eeuo pipefail

# ------------------------------------------------------------------ rendering
if [[ -t 1 ]]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_DIM=$'\033[2m'
  C_RED=$'\033[31m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_BLUE=$'\033[34m'
else
  C_RESET=""; C_BOLD=""; C_DIM=""; C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""
fi

step()  { printf '%s==>%s %s\n' "$C_BLUE$C_BOLD" "$C_RESET" "$*"; }
ok()    { printf '%s  ✓%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
warn()  { printf '%s  !%s %s\n' "$C_YELLOW" "$C_RESET" "$*" >&2; }
fail()  { printf '%s  ✗%s %s\n' "$C_RED" "$C_RESET" "$*" >&2; }
die()   { fail "$*"; exit 1; }
note()  { printf '%s    %s%s\n' "$C_DIM" "$*" "$C_RESET"; }

on_error() {
  local exit_code=$?
  fail "Installation failed (exit code ${exit_code}) on line ${BASH_LINENO[0]}."
  note "Re-run with 'bash -x scripts/install.sh' to see the full trace."
  exit "$exit_code"
}
trap on_error ERR

# ------------------------------------------------------------------- arguments
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

INSTALL_DIR="$REPO_ROOT"
VENV_NAME=".venv"
SERVICE_USER="$(id -un)"
SERVICE_MODE="auto"     # auto | yes | no
INSTALL_DEV="no"
ASSUME_YES="no"
SKIP_SYSTEM_DEPS="no"
START_SERVICE="yes"

usage() {
  cat <<'USAGE'
Telegram Community Bot - one-shot installer

Usage:
  bash scripts/install.sh [options]

Options:
  --dir PATH           Install/run from PATH               (default: repository root)
  --user NAME          System user that runs the service   (default: current user)
  --service            Install and start the systemd service
  --no-service         Do not touch systemd (default when not running as root)
  --venv NAME          Virtual environment directory       (default: .venv)
  --dev                Also install development dependencies
  --yes, -y            Answer "yes" to every question (non-interactive)
  --skip-system-deps   Do not install OS packages
  --no-start           Install the service but do not start it yet
  --dry-run            Show what would happen and exit
  -h, --help           Show this help

Examples:
  bash scripts/install.sh                     # local install, keeps everything in the repo
  sudo bash scripts/install.sh --service      # production install with systemd
  bash scripts/install.sh --dir /opt/reporter --venv venv --dev
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir) INSTALL_DIR="$2"; shift 2 ;;
    --user) SERVICE_USER="$2"; shift 2 ;;
    --venv) VENV_NAME="$2"; shift 2 ;;
    --service) SERVICE_MODE="yes"; shift ;;
    --no-service|--no-systemd) SERVICE_MODE="no"; shift ;;
    --dev) INSTALL_DEV="yes"; shift ;;
    --yes|-y) ASSUME_YES="yes"; shift ;;
    --skip-system-deps) SKIP_SYSTEM_DEPS="yes"; shift ;;
    --no-start) START_SERVICE="no"; shift ;;
    --dry-run) DRY_RUN="yes"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown option: $1 (use --help)" ;;
  esac
done

DRY_RUN="${DRY_RUN:-no}"
run() { if [[ "$DRY_RUN" == "yes" ]]; then note "[dry-run] $*"; else "$@"; fi; }

confirm() {
  [[ "$ASSUME_YES" == "yes" ]] && return 0
  [[ ! -t 0 ]] && return 1              # non-interactive: default to "no"
  read -r -p "  ${1} [y/N] " reply
  [[ "$reply" =~ ^[Yy]$ ]]
}

# ----------------------------------------------------------------- environment
IS_ROOT="no"; [[ "$(id -u)" -eq 0 ]] && IS_ROOT="yes"
SUDO=""; if [[ "$IS_ROOT" != "yes" ]] && command -v sudo >/dev/null 2>&1; then SUDO="sudo"; fi

detect_pm() {
  for pm in apt-get dnf yum apk pacman zypper; do
    command -v "$pm" >/dev/null 2>&1 && { echo "$pm"; return; }
  done
  echo ""
}

install_system_deps() {
  [[ "$SKIP_SYSTEM_DEPS" == "yes" ]] && { warn "Skipping OS packages (--skip-system-deps)"; return; }
  local pm; pm="$(detect_pm)"
  [[ -z "$pm" ]] && { warn "No supported package manager found; install python3, python3-venv, git manually."; return; }

  step "Installing system packages with $pm"
  case "$pm" in
    apt-get)
      run $SUDO env DEBIAN_FRONTEND=noninteractive apt-get update -qq
      run $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 python3-venv python3-pip git ca-certificates
      ;;
    dnf|yum)
      run $SUDO "$pm" install -y -q python3 python3-pip git ca-certificates
      ;;
    apk)
      run $SUDO apk add --no-cache python3 py3-pip git ca-certificates
      ;;
    pacman)
      run $SUDO pacman -Sy --noconfirm python python-pip git ca-certificates
      ;;
    zypper)
      run $SUDO zypper --non-interactive install python3 python3-pip git ca-certificates
      ;;
  esac
  ok "System packages ready"
}

require_python() {
  command -v python3 >/dev/null 2>&1 || die "python3 was not found. Install Python 3.10+ and re-run."
  local version major minor
  version="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
  major="${version%%.*}"; minor="${version##*.}"
  if (( major < 3 || (major == 3 && minor < 10) )); then
    die "Python >= 3.10 is required (found $version)."
  fi
  ok "Python $version detected"
}

venv_python() { echo "$INSTALL_DIR/$VENV_NAME/bin/python"; }

create_venv() {
  local python_bin; python_bin="$(venv_python)"
  if [[ -x "$python_bin" ]]; then
    ok "Virtual environment already present: $INSTALL_DIR/$VENV_NAME"
    return
  fi
  step "Creating virtual environment ($VENV_NAME)"
  if ! run python3 -m venv "$INSTALL_DIR/$VENV_NAME" 2>/dev/null; then
    warn "venv module missing, installing python3-venv"
    local pm; pm="$(detect_pm)"
    case "$pm" in
      apt-get) run $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv ;;
      dnf|yum) run $SUDO "$pm" install -y -q python3-virtualenv || true ;;
      apk) run $SUDO apk add --no-cache py3-virtualenv || true ;;
      *) : ;;
    esac
    run python3 -m venv "$INSTALL_DIR/$VENV_NAME" || die "Could not create the virtual environment."
  fi
  ok "Virtual environment ready"
}

install_python_deps() {
  local python_bin; python_bin="$(venv_python)"
  step "Installing Python dependencies"
  run "$python_bin" -m pip install --quiet --upgrade pip setuptools wheel
  run "$python_bin" -m pip install --quiet -r "$INSTALL_DIR/requirements.txt"
  if [[ "$INSTALL_DEV" == "yes" ]]; then
    run "$python_bin" -m pip install --quiet -r "$INSTALL_DIR/requirements-dev.txt"
    ok "Development dependencies installed"
  fi
  ok "Python dependencies installed"
}

prepare_env_file() {
  local env_file="$INSTALL_DIR/.env"
  if [[ -f "$env_file" ]]; then
    ok "Configuration file already exists: .env"
    return
  fi
  [[ -f "$INSTALL_DIR/.env.example" ]] || { warn ".env.example not found - skipping"; return; }
  run cp "$INSTALL_DIR/.env.example" "$env_file"
  run chmod 600 "$env_file" 2>/dev/null || true
  warn "Created .env from the template - fill in API_ID, API_HASH and BOT_TOKEN."
  note "Get credentials: API_ID/API_HASH -> https://my.telegram.org | BOT_TOKEN -> https://t.me/BotFather"
}

verify_installation() {
  local python_bin; python_bin="$(venv_python)"
  step "Verifying the installation"
  if [[ "$DRY_RUN" == "yes" ]]; then run "$python_bin" -m bot check; return; fi
  if "$python_bin" -m bot check; then
    ok "Configuration check passed"
  else
    warn "Configuration is incomplete."
    note "Edit $INSTALL_DIR/.env and run: $python_bin -m bot check"
  fi
}

install_service() {
  local python_bin; python_bin="$(venv_python)"
  local unit_src="$INSTALL_DIR/deploy/systemd/reporter.service.in"
  local unit_dst="/etc/systemd/system/reporter.service"

  [[ -f "$unit_src" ]] || { warn "systemd template missing; skipping service setup"; return; }
  command -v systemctl >/dev/null 2>&1 || { warn "systemd not available on this system; skipping service setup"; return; }
  [[ "$IS_ROOT" == "yes" ]] || die "Installing the systemd service requires root (re-run with sudo)."

  step "Installing systemd service"
  run sed -e "s|__WORKDIR__|$INSTALL_DIR|g" \
          -e "s|__PYTHON__|$python_bin|g" \
          -e "s|__USER__|$SERVICE_USER|g" \
          "$unit_src" > /tmp/reporter.service.$$ || die "Could not render the unit file."
  run install -m 644 /tmp/reporter.service.$$ "$unit_dst"
  run rm -f /tmp/reporter.service.$$
  run systemctl daemon-reload
  run systemctl enable reporter.service
  ok "Service installed: $unit_dst"

  if [[ "$START_SERVICE" == "yes" ]]; then
    run systemctl restart reporter.service || warn "Service failed to start - check: journalctl -u reporter -n 50"
    ok "Service started (systemctl status reporter)"
  fi
}

print_summary() {
  local python_bin; python_bin="$(venv_python)"
  printf '\n%s%s Installation complete %s\n\n' "$C_BOLD" "$C_GREEN" "$C_RESET"
  printf '  %sProject%s      %s\n' "$C_BOLD" "$C_RESET" "$INSTALL_DIR"
  printf '  %sPython%s       %s\n' "$C_BOLD" "$C_RESET" "$python_bin"
  printf '  %sConfig%s       %s/.env\n' "$C_BOLD" "$C_RESET" "$INSTALL_DIR"
  printf '\n  %sNext steps%s\n' "$C_BOLD" "$C_RESET"
  note "1. Put your credentials into .env (API_ID, API_HASH, BOT_TOKEN, OWNER_IDS)"
  note "2. Validate:   $python_bin -m bot check"
  note "3. Run once:   $python_bin -m bot run"
  if systemctl list-unit-files 2>/dev/null | grep -q '^reporter.service'; then
    note "4. Service:    systemctl status reporter   |   journalctl -u reporter -f"
  else
    note "4. Service:    sudo bash scripts/install.sh --service"
  fi
  printf '\n'
}

# ----------------------------------------------------------------------- main
printf '\n%sTelegram Community Bot installer%s\n' "$C_BOLD" "$C_RESET"

step "Checking the environment"
require_python
[[ -d "$INSTALL_DIR" ]] || die "Directory not found: $INSTALL_DIR"

if [[ "$SKIP_SYSTEM_DEPS" == "no" ]]; then
  install_system_deps
fi

step "Preparing $INSTALL_DIR"
create_venv
install_python_deps
prepare_env_file
verify_installation

SERVICE_DECISION="$SERVICE_MODE"
if [[ "$SERVICE_DECISION" == "auto" ]]; then
  if [[ "$IS_ROOT" == "yes" ]]; then
    if confirm "Install the bot as a systemd service so it starts automatically?"; then
      SERVICE_DECISION="yes"
    else
      SERVICE_DECISION="no"
    fi
  else
    SERVICE_DECISION="no"
    note "Not running as root: skipping systemd (use --service with sudo to enable it)."
  fi
fi

if [[ "$SERVICE_DECISION" == "yes" ]]; then
  install_service
else
  note "Systemd setup skipped."
fi

print_summary
