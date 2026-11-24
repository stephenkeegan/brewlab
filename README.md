# BrewLab

Brewing Digital Twin: a physics-based brewing simulation and recipe optimization
platform.

## Status

Pre-release. Scientific core (water chemistry, mash enzymatics, boil/hops,
fermentation) plus a coupled simulation engine and a constrained optimization
engine are implemented. See `docs/models/` for per-model equations, assumptions,
limitations, and literature sources.

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

## CLI

The package installs a `brewlab` entry point (also runnable as
`python -m brewlab.cli`).

### Simulate a mash

```bash
brewlab simulate mash recipes/example.json
```

### Simulate a full batch (mash → boil → ferment)

```bash
brewlab simulate all recipes/example.json
```

## Python API

### Coupled simulation

```python
from brewlab.simulation.engine import simulate_batch

result = simulate_batch(recipe_dict)
print(result.summary)   # {"og_plato": ..., "fg_plato": ..., "abv_percent": ..., "ibu": ..., ...}
print(result.as_dict()) # full nested result
```

`simulate_batch` chains mash → boil → ferment and returns a
`CoupledSimulationResult` with `.mash`, `.boil`, `.ferment`, and `.summary`.

### Optimization (Phase 6)

Given target finished-product characteristics, `optimize_recipe` searches grain
mass, extract potential, and hop amounts to minimize weighted deviation from the
targets using `scipy.optimize.differential_evolution` (deterministic, fixed
seed).

```python
from brewlab.optimization.engine import (
    OptimizationTarget,
    optimize_recipe,
)

target = OptimizationTarget(og_plato=23.0, abv_percent=4.5, ibu=25.0)
result = optimize_recipe(target, base_recipe, maxiter=80)
print(result.grain_mass_kg, result.extract_potential)
print(result.predicted)   # {"og_plato": ..., "ibu": ..., ...}
print(result.simulation)  # full coupled simulation at the optimum
```

### Sensitivity

One-at-a-time parameter sweep:

```python
from brewlab.optimization.engine import sensitivity

out = sensitivity(base_recipe, "grain_mass_kg", [4.0, 6.0, 8.0])
# [{"grain_mass_kg": 4.0, "og_plato": ..., ...}, ...]
```

## Project layout

```
src/brewlab/        # source package
  core/             # units, thermodynamics, equilibrium, kinetics
  domain/           # domain models (recipe, batch, measurement)
  data/             # CSV ingestion, measurement calibration
  persistence/      # JSON/CSV persistence
  simulation/       # coupled mash→boil→ferment engine
  optimization/     # recipe optimization + sensitivity (Phase 6)
  cli.py            # command-line interface
tests/              # pytest suite
docs/models/        # per-model scientific documentation
recipes/            # example recipe JSON files
```

## Validation

75+ tests covering units, chemistry, kinetics, simulation, data ingestion, and
optimization. `ruff` (lint + format) and `mypy --strict` are enforced in CI.

## License

MIT
