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
  virtualenv --python=python3.10 venv
fi
source venv/bin/activate
pip3 install pip==24.3.1 pip-tools==7.4.1
pip-sync setup/requirements.txt

GOATCOUNTER=1 BLASTFROMTHEPAST=1 OVERVIEW=1 SUBSCRIPTION=1 RSS=1 gunicorn app:app --workers 12 --bind 0.0.0.0:8002 --timeout 60 --max-requests=100 --max-requests-jitter=10

