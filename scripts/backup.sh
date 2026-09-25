#!/usr/bin/env bash
# =============================================================================
#  Create a timestamped backup of the runtime data.
#  Usage: bash scripts/backup.sh [--with-sessions] [--keep N]
# =============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
ORIGINAL_ARGS=("$@")
WITH_SESSIONS=""
KEEP=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-sessions) WITH_SESSIONS="yes"; shift ;;
    --keep) KEEP="$2"; shift 2 ;;
    -h|--help) sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

cd "$ROOT_DIR"
[[ -x .venv/bin/python ]] || { echo "No virtual environment - run scripts/install.sh first." >&2; exit 1; }

.venv/bin/python - "${ORIGINAL_ARGS[@]}" <<'PY'
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from bot.config import load_settings
from bot.services.backup import create_backup
from bot.storage.database import Database
from bot.storage.repository import Repository

with_sessions = "--with-sessions" in sys.argv
keep = 7
if "--keep" in sys.argv:
    keep = int(sys.argv[sys.argv.index("--keep") + 1])

settings = load_settings()
settings.prepare_directories()
db = Database(settings.db_file)
try:
    db.migrate()
    result = create_backup(
        settings,
        Repository(db, timezone=settings.timezone),
        keep=keep,
        include_sessions=with_sessions,
    )
finally:
    db.close()
print(f"✅ Backup created: {result.path}")
print(f"   size: {result.size_kb} KB | files: {result.files} | retention: {keep}")
PY
