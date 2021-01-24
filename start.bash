#!/bin/bash
set -e
if [ ! -f 'app.py' ]; then
  echo 'Only run from within the dir'
  exit 1
fi
#if [ ! -f 'config.py' ]; then
#  cp config.example config.py
#  echo 'Please edit the config file: config.py'
#  exit 1
#fi
if [ ! -d "venv" ]; then
  virtualenv --python=python3 venv
fi
source venv/bin/activate
pip3 install pip-tools
pip-sync setup/requirements.txt

gunicorn app:app --workers 5 --bind 0.0.0.0:8002 --reload --timeout 120

