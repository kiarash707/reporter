#!/usr/bin/env bash
# =============================================================================
#  Run the exact same checks as the GitHub Actions pipeline, locally.
#
#  Usage: bash scripts/ci.sh [--fix] [--quick] [--docker] [--no-mypy]
#    --fix     let ruff rewrite files instead of failing
#    --quick   skip the slow checks (mypy, docker, coverage report)
#    --docker  also build the container image (needs docker)
#    --no-mypy skip mypy
# =============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

FIX="no"; QUICK="no"; DOCKER="no"; MYPY="yes"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --fix) FIX="yes"; shift ;;
    --quick) QUICK="yes"; shift ;;
    --docker) DOCKER="yes"; shift ;;
    --no-mypy) MYPY="no"; shift ;;
    -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

if [[ -x .venv/bin/python ]]; then
  PY=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
  echo "! .venv not found - falling back to the system python" >&2
else
  echo "No python interpreter found." >&2; exit 1
fi

FAILED=0
step() { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
pass() { printf '\033[32m  ✓ %s\033[0m\n' "$*"; }
fail() { printf '\033[31m  ✗ %s\033[0m\n' "$*"; FAILED=1; }
skip() { printf '\033[33m  – %s\033[0m\n' "$*"; }

# ------------------------------------------------------------------- ruff lint
step "Ruff (lint)"
if [[ "$FIX" == "yes" ]]; then
  "$PY" -m ruff check . --fix && pass "lint clean after autofix" || fail "ruff check"
else
  "$PY" -m ruff check . && pass "lint clean" || fail "ruff check"
fi

# ------------------------------------------------------------------ ruff format
step "Ruff (format)"
if [[ "$FIX" == "yes" ]]; then
  "$PY" -m ruff format . >/dev/null && pass "formatting applied"
else
  "$PY" -m ruff format --check . && pass "formatting clean" || fail "ruff format --check"
fi

# ------------------------------------------------------------------------- tests
step "Tests"
if [[ "$QUICK" == "yes" ]]; then
  "$PY" -m pytest -q && pass "tests passed" || fail "pytest"
else
  "$PY" -m pytest --cov --cov-report=term-missing:skip-covered && pass "tests passed (coverage above)" || fail "pytest"
fi

# ------------------------------------------------------------------------ mypy
step "Mypy"
if [[ "$MYPY" == "no" ]]; then
  skip "mypy skipped (--no-mypy)"
elif "$PY" -m mypy bot; then
  pass "no type errors"
else
  fail "mypy"
fi

# ---------------------------------------------------------------- shell scripts
step "Shell scripts"
SHELL_OK=1
for script in scripts/*.sh; do
  bash -n "$script" || { fail "bash -n $script"; SHELL_OK=0; }
done
[[ "$SHELL_OK" == "1" ]] && pass "all scripts parse" || true

# ------------------------------------------------------------------------- config
step "Configuration check"
"$PY" -m bot check >/dev/null 2>&1 && pass "configuration valid" \
  || skip "configuration incomplete (fill in .env, then rerun 'python -m bot check')"

# --------------------------------------------------------------------- yaml/lint
if [[ "$QUICK" == "no" ]] && "$PY" -c "import yaml" 2>/dev/null; then
  step "YAML files"
  "$PY" - <<'PY' && pass "all YAML files parse" || fail "YAML validation"
import pathlib, sys, yaml
files = ["deploy/docker/docker-compose.yml", ".github/dependabot.yml"] + [
    str(p) for p in pathlib.Path(".github").rglob("*.yml")
]
bad = 0
for path in sorted(set(files)):
    try:
        yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"  invalid: {path}: {exc}")
        bad = 1
sys.exit(bad)
PY
fi

# ---------------------------------------------------------------------- docker
if [[ "$DOCKER" == "yes" ]]; then
  step "Docker build"
  if command -v docker >/dev/null 2>&1; then
    docker build -f deploy/docker/Dockerfile -t telegram-community-bot:ci . \
      && pass "image built" || fail "docker build"
  else
    skip "docker is not installed"
  fi
fi

echo
if [[ "$FAILED" == "0" ]]; then
  printf '\033[1;32m✅ All checks passed\033[0m\n'
else
  printf '\033[1;31m❌ Some checks failed\033[0m\n'
fi
exit "$FAILED"
