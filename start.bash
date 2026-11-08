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
uv sync --no-dev

GOATCOUNTER=1 BLASTFROMTHEPAST=1 OVERVIEW=1 SUBSCRIPTION=1 RSS=1 uv run --no-dev gunicorn app:app --workers 12 --bind localhost:${PORT:-8002} --timeout 60 --max-requests=100 --max-requests-jitter=10

