# Create .venv and sync dependencies
install:
    uv sync

# Start the app via gunicorn
run:
    ./start.bash

# Start Flask dev server
dev:
    ./debug.bash

# Run tests
test:
    uv run python -m unittest tests.py

# Update uv.lock to the latest allowed versions
update:
    uv lock --upgrade
