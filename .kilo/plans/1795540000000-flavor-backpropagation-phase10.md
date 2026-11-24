# Plan: Phase 10 — Flavor back-propagation (target-driven recipe design)

## Goal
Let a user explore how inputs impact flavor via randomized simulations logged to a persistent JSON file, then set a desired flavor profile (6 normalized dimensions, 0–100 each) and back-propagate to recommended recipe inputs.

## Decisions (all confirmed by user)
- **Persistence:** persistent JSON log file `.brewlab_flavor_exploration.json` in the working directory (survives across app runs).
- **Algorithm:** nearest-neighbor from logged samples (primary, bounded to explored range) + optional `scipy.optimize.differential_evolution` refinement to extrapolate beyond the logged range.
- **Flavor dimensions:** all 6 (bitterness, sweetness, body, alcohol warmth, dryness, hop aroma), normalized 0–100.
- **Sample count:** 100 default, user-configurable via GUI slider.
- **Input space for back-prop:** same as Phase 9: grain_mass_kg, extract_potential, mash temp, ferment temp, bittering hop amount, yeast list.
- **Apply:** one-click to load recommended inputs into the active scenario.

## Corrections from prior plan
- `simulate_batch` results merge resolved inputs + `summary` outputs already (solution_space.py line 167–169); the flavor dimension mapping lives in GUI `_flavor_scores()` (app.py:112). The back-propagation engine must reuse `_flavor_scores` logic in the core package (not the GUI) so it can be tested without Streamlit.

## Affected files
- `src/brewlab/simulation/flavor_engine.py` (new) — `FlavorTarget`, `backpropagate_flavor()`, `explore_and_log()`, nearest-neighbor + optional scipy refinement, JSON log persistence.
- `src/brewlab/gui/app.py` — add "Explore flavor space" button (N randomized sims → log), "Target flavor" tab with 6 sliders + +/- adjustments, nearest-neighbor recommendation + optional scipy refine, one-click apply to active scenario, input→flavor impact chart.
- `src/brewlab/simulation/solution_space.py` — reuse `explore_solution_space` for the explore step (no change needed; call it with `n_samples` from GUI).
- `tests/test_flavor_engine.py` (new) — nearest-neighbor selection, clamping to logged range, scipy refinement, JSON log round-trip, flavor dimension mapping.
- `.github/workflows/ci.yml` — no change (gui extras already installed).

## Ordered tasks

1. **Create `src/brewlab/simulation/flavor_engine.py`:**
   - `FlavorTarget(bitterness, sweetness, body, alcohol, dryness, hop_aroma)` dataclass (each 0–100 float).
   - `_flavor_scores_from_result(result)` — replicate GUI `_flavor_scores` mapping from `summary`/`boil` to 6 raw flavor values + normalized 0–100 scores.
   - `FlavorLogger(log_path)` — append `{inputs, flavor_scores}` to JSON log; load all entries.
   - `backpropagate_flavor(target, logged_samples, input_bounds, n_samples=100, seed=42, refine=True)`:
     - Normalize target to 0–100.
     - Nearest-neighbor: find logged sample with min Euclidean distance in normalized flavor space.
     - Optional scipy refine: `differential_evolution` over `input_bounds` minimizing distance(target, flavor(simulate(inputs))).
     - Return recommended inputs + predicted flavor + distance + method used.
   - `explore_and_log(recipe_ranges, n_samples, seed, log_path)` — call `explore_solution_space`, append samples to log, return stats.
   - Input bounds: `{grain_mass_kg: (0.5,50), extract_potential:(0.5,0.95), mash_temp:(45,78), ferment_temp:(10,30), bittering_hop_kg:(0,0.2), yeast: list[str]}`.

2. **Update `src/brewlab/gui/app.py`:**
   - Add "Explore flavor space" section in sidebar: sample count slider (default 100), "Run exploration" button, status message + count of logged samples.
   - Add "Target flavor" tab: 6 sliders (0–100 each) for desired flavor; show current recommendation; "Back-propagate" button; optional "Refine with optimizer" toggle; recommended inputs displayed with apply button.
   - Add input→flavor impact: scatter/correlation of each input vs each flavor dimension from logged samples (parallel coordinates or grouped scatter).
   - When "apply" clicked, set active scenario inputs to recommended recipe and clear results (force re-run).

3. **Add `tests/test_flavor_engine.py`:**
   - nearest-neighbor picks the logged sample with closest flavor.
   - back-propagation respects input bounds.
   - JSON log append + load round-trip.
   - flavor dimension mapping produces expected normalized scores.
   - scipy refine reduces distance (monotonic improvement or equal).

4. **Full validation:** `pytest` + `ruff check` + `ruff format --check` + `mypy src`. All green.
5. Commit and push (no remote currently configured; user must add origin first — already exists: `origin` → `stephenkeegan/brewlab`).

## Validation contract
- All 6 flavor dimensions normalized 0–100.
- Nearest-neighbor always returns a logged sample that exists.
- Recommended inputs always within declared input bounds.
- JSON log appends without duplicating header; loads back as list.
- scipy refinement (when enabled) does not increase distance vs nearest-neighbor baseline.
- Existing 113 tests still pass; new tests added.

## Out of scope
- Multi-objective Pareto optimization (single scalar distance only).
- Whirlpool/dry-hop aroma modeling (hops stay boil-only → IBU).
- Water ions beyond Ca/Mg/bicarbonate/Cl/SO4.
- Multi-fermentable grain bill.
