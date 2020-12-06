#!/bin/bash
source venv/bin/activate
pip3 install -r setup/requirements.txt
gunicorn app:app --workers 2 --bind 0.0.0.0:8002 --reload

