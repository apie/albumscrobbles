# Create venv and sync dependencies
install:
    #!/usr/bin/env bash
    if [ ! -d "venv" ]; then
        uv venv --python 3.14 venv
    fi
    uv pip sync setup/requirements.txt

# Start the app via gunicorn
run:
    GOATCOUNTER=1 BLASTFROMTHEPAST=1 OVERVIEW=1 SUBSCRIPTION=1 RSS=1 \
        venv/bin/gunicorn app:app --workers 12 --bind 0.0.0.0:8002 --timeout 60 --max-requests=100 --max-requests-jitter=10

# Start Flask dev server
dev:
    FLASK_DEBUG=1 venv/bin/flask run

# Run tests
test:
    venv/bin/python -m unittest tests.py

# Regenerate requirements.txt from requirements.in
compile:
    uv pip compile setup/requirements.in -o setup/requirements.txt --python-version 3.14
