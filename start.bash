#!/bin/bash
set -e
if [ ! -f 'app.py' ]; then
  echo 'Only run from within the dir'
  exit 1
fi
if [ ! -f 'config.py' ]; then
  cp config.example config.py
  touch confirmed_subscriptions.txt
  echo 'Please edit the config file: config.py'
  exit 1
fi
if [ ! -d "venv" ]; then
  virtualenv --python=python3.8 venv
fi
source venv/bin/activate
pip3 install pip==23.1.2 pip-tools==6.14.0
pip-sync setup/requirements.txt

GOATCOUNTER=1 BLASTFROMTHEPAST=1 OVERVIEW=1 SUBSCRIPTION=1 RSS=1 gunicorn app:app --workers 12 --bind 0.0.0.0:8002 --timeout 60

