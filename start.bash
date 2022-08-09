#!/bin/bash
set -e
if [ ! -f 'app.py' ]; then
  echo 'Only run from within the dir'
  exit 1
fi
if [ ! -d "venv" ]; then
  virtualenv --python=python3.8 venv
fi
source venv/bin/activate
pip3 install pip==22.2.2 pip-tools==6.8.0
pip-sync setup/requirements.txt

GOATCOUNTER=1 gunicorn app:app --workers 12 --bind 0.0.0.0:8002 --reload --timeout 60

