# BrewLab

Brewing Digital Twin: a physics-based brewing simulation and recipe optimization
platform.

## Status

Pre-release / foundation phase. Scientific core is under development.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,sci]"
```

## Test

```bash
pytest
```

## Lint / Typecheck

```bash
ruff check src tests
ruff format --check src tests
mypy src
```

## Scientific models

See `docs/models/` for per-model equations, assumptions, limitations, and
literature sources.
