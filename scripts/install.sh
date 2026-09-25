#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."
echo 'Installing Reporter Bot...'

apt update
apt install -y python3 python3-pip python3-venv git

python3 -m venv venv
source venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo 'Installation completed.'
echo 'Run: ./scripts/start.sh'
