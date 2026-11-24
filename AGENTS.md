# BrewLab — Agent Instructions

This file guides AI agents working on the BrewLab repository.

## Project

BrewLab is a physics-based brewing simulation and recipe optimization platform
in Python 3.11+. Package name `brewlab`, layout `src/brewlab` + `tests/`.

## Key conventions

- **Units:** `src/brewlab/units.py` provides a pint `ureg` singleton. All
  scientific quantities are `pint.Quantity`. Never mix bare floats with units
  in the core/domain layers.
- **Strict boundary:** the scientific core has zero UI/app imports. CLI lives
  in `src/brewlab/cli.py` only.
- **Typing:** `mypy --strict` on `src/`. No `Any` generics, `warn_return_any`
  enabled. Add `# type: ignore[import-untyped]` for untyped third-party imports
  (e.g. scipy).
- **Lint/format:** `ruff` with line-length 100, double quotes, space indent.
  Ignored: E501, B008.
- **No comments in code** unless asked (project rule).

## Commands

| Purpose | Command |
|---|---|
| Tests | `.venv/bin/pytest -q` (or `pytest`) |
| GUI | `streamlit run src/brewlab/gui/app.py` |
| Lint | `.venv/bin/ruff check src tests` |
| Format | `.venv/bin/ruff format src tests` |
| Format check | `.venv/bin/ruff format --check src tests` |
| Typecheck | `.venv/bin/mypy src` |
| Full validation | pytest + ruff check + ruff format --check + mypy src |

Always run the full validation before marking work complete.

## Module map

- `src/brewlab/units.py` — pint registry + unit helpers
- `src/brewlab/core/` — thermodynamics, equilibrium, kinetics
- `src/brewlab/domain/` — domain models (recipe, batch, measurement)
- `src/brewlab/data/` — CSV ingestion, measurement calibration
- `src/brewlab/persistence/` — JSON/CSV persistence (`json_repo.py`: `JsonRepository`)
- `src/brewlab/simulation/engine.py` — `simulate_batch()` (mash→boil→ferment)
- `src/brewlab/optimization/engine.py` — `optimize_recipe()` + `sensitivity()`
- `src/brewlab/gui/app.py` — Streamlit GUI for recipe input + simulation (run `streamlit run src/brewlab/gui/app.py`)
- `src/brewlab/cli.py` — `brewlab simulate mash|all` and `brewlab store save|load|list`

## Current work state

- Phases 0-5 complete: foundation, scientific core, boil/hops, fermentation,
  coupled simulation engine, data integration.
- Phase 6 complete: optimization engine (`optimize_recipe`, `sensitivity`),
  tests in `tests/test_optimization.py`.
- Phase 7 complete: persistence layer (`JsonRepository`, CLI `store save|load|list`),
  tests in `tests/test_persistence.py`.
- Docs: README.md + this AGENTS.md written. `docs/models/` has 6 model docs.

## Tests

- `tests/test_data.py` — ingestion + calibration (Measurement now has
  `calibrated_at` field)
- `tests/test_optimization.py` — optimization + sensitivity (Phase 6)
- `tests/test_persistence.py` — JSON repository round-trips (Phase 7)
- Other test files cover core/domain/simulation.

When adding a feature, add tests in the matching `tests/test_*.py` file and
keep the suite green.

## Do NOT

- Commit unless explicitly asked by the user.
- Add comments to code unless requested.
- Guess URLs or external endpoints.
- Introduce bare floats where quantities are expected.
