#!/usr/bin/env bash
# =============================================================================
#  Update an existing installation: backup -> pull -> dependencies -> restart
#
#  Usage: bash scripts/update.sh [--branch main] [--no-git] [--no-restart] [--yes]
# =============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
BRANCH=""
USE_GIT="yes"
RESTART="yes"
ASSUME_YES="no"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --branch) BRANCH="$2"; shift 2 ;;
    --no-git) USE_GIT="no"; shift ;;
    --no-restart) RESTART="no"; shift ;;
    --yes|-y) ASSUME_YES="yes"; shift ;;
    -h|--help) sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

step() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[32m  ✓\033[0m %s\n' "$*"; }
warn() { printf '\033[33m  !\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31m  ✗\033[0m %s\n' "$*" >&2; exit 1; }
confirm() {
  [[ "$ASSUME_YES" == "yes" ]] && return 0
  [[ ! -t 0 ]] && return 1
  read -r -p "  $1 [y/N] " reply; [[ "$reply" =~ ^[Yy]$ ]]
}

cd "$ROOT_DIR"
[[ -x .venv/bin/python ]] || die "No virtual environment found. Run scripts/install.sh first."

step "1/5 Creating a safety backup"
if .venv/bin/python -m bot backup >/dev/null 2>&1; then
  ok "Backup written to $(ls -1t data/backups 2>/dev/null | head -1)"
else
  warn "Backup skipped (the database may not exist yet)"
fi

step "2/5 Updating the source tree"
if [[ "$USE_GIT" == "yes" ]]; then
  if [[ -d .git ]]; then
    if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
      warn "Local changes detected:"
      git status --short >&2
      confirm "Continue and keep local changes (git stash)?" || die "Update aborted."
      git stash push --include-untracked -m "update.sh $(date +%F-%H%M%S)" && ok "Local changes stashed (git stash list)"
    fi
    if [[ -n "$BRANCH" ]]; then
      git fetch --quiet origin "$BRANCH" && git checkout --quiet "$BRANCH" || die "Cannot switch to branch $BRANCH"
    fi
    git pull --ff-only && ok "Repository updated"
  else
    warn "Not a git checkout - skipping the source update"
  fi
else
  warn "Skipping git (--no-git)"
fi

step "3/5 Installing updated dependencies"
.venv/bin/python -m pip install --quiet --upgrade pip setuptools wheel
.venv/bin/python -m pip install --quiet -r requirements.txt && ok "Dependencies up to date"

step "4/5 Applying database migrations"
.venv/bin/python -m bot migrate && ok "Database is current"

step "5/5 Validating configuration and restarting"
if .venv/bin/python -m bot check >/dev/null; then ok "Configuration valid"; else warn "Configuration needs attention: run '.venv/bin/python -m bot check'"; fi

if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files 2>/dev/null | grep -q '^reporter.service'; then
  if [[ "$RESTART" == "yes" ]]; then
    sudo systemctl restart reporter.service && ok "Service restarted" || warn "Could not restart the service (try: sudo systemctl restart reporter)"
  else
    warn "Restart requested to be skipped - run: sudo systemctl restart reporter"
  fi
else
  ok "No systemd service detected - start manually with '.venv/bin/python -m bot run'"
fi

echo
ok "Update finished."
