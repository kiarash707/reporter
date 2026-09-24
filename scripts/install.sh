#!/bin/bash
set -e

echo 'Installing Reporter Bot...'

sudo apt update
sudo apt install -y python3 python3-pip python3-venv git

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

echo 'Installation completed.'
echo 'Run: ./scripts/start.sh'
