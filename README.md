Albumscrobbles.com
==================
Calculate your _real_ last.fm album stats
--


Fetches your album stats and the track count for each album. Based on this, the album playcount is calculated.

## Setup

Prerequisites: [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/).

```
just install
```

Copy `config.example` to `config.py` and edit it before running.

## Available recipes

| Recipe | Description |
|--------|-------------|
| `just install` | Create venv and sync dependencies |
| `just run` | Start the app (gunicorn) |
| `just dev` | Start Flask dev server |
| `just test` | Run tests |
| `just compile` | Regenerate `setup/requirements.txt` from `setup/requirements.in` |
