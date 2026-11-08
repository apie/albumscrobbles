# Create .venv and sync dependencies
install:
    uv sync


# Start the app via gunicorn
run:
    GOATCOUNTER=1 BLASTFROMTHEPAST=1 OVERVIEW=1 SUBSCRIPTION=1 RSS=1 \
        uv run --no-dev gunicorn app:app --workers 12 --bind 0.0.0.0:8002 --timeout 60 --max-requests=100 --max-requests-jitter=10

# Start Flask dev server
dev:
    FLASK_DEBUG=1 uv run flask run

# Run tests
test:
    uv run python -m unittest tests.py

# Update uv.lock to the latest allowed versions
update:
    uv lock --upgrade
