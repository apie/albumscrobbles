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
pip3 install --upgrade pip
pip3 install --upgrade pip-tools
pip-sync setup/requirements.txt

gunicorn app:app --workers 5 --bind 0.0.0.0:8002 --reload --timeout 120

