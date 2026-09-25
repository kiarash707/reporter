#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: run this installer as root (without sudo)."
  exit 1
fi

echo "==> Installing Reporter Bot in $ROOT_DIR"

apt update
DEBIAN_FRONTEND=noninteractive apt install -y python3 python3-pip python3-venv git

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

./venv/bin/python -m pip install --upgrade pip setuptools wheel
./venv/bin/python -m pip install -r requirements.txt

if [ -f "systemd/reporter.service" ]; then
  install -m 644 systemd/reporter.service /etc/systemd/system/reporter.service
  systemctl daemon-reload
  systemctl enable reporter
fi

echo
echo "==> Installation completed."
echo "==> Test manually:"
echo "    $ROOT_DIR/venv/bin/python3 $ROOT_DIR/main.py"
echo
echo "==> Start 24/7 service:"
echo "    systemctl start reporter"
echo
echo "==> Check status:"
echo "    systemctl status reporter --no-pager"
