#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
source venv/bin/activate
exec python3 main.py
