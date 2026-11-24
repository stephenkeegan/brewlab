# Plan: Yeast strain database + range-based flavor solution space

## Goal
Maximize a user's ability to understand and manipulate the flavor profile of the resultant brew by (1) adding a yeast strain database whose selection actually changes FG/ABV/dryness/flavor character, and (2) letting users specify input ranges (instead of exact values) to see a solution space of possible outcomes across flavor-relevant parameters.

## Corrections / decisions (resolved)
- **SGD out of scope:** yeastgenome.org is a molecular biology database; it has an API but **no brewing strain phenotypes** (attenuation, flocculation, temperature range, alcohol tolerance). Use a small curated in-repo strain database instead.
- **Range parameters (confirmed by user):** `grain_mass_kg`, `extract_potential`, `target_mash_temperature_degC`, `ferment temperature_degC`, `bittering hop amount_kg`, `yeast` (list of strain IDs).
- **Solution-space sample size:** n_samples=200 default, configurable.
- **SRM MVP:** single-grain `color_lovibond` input + Morey equation `SRM = 1.4922 * MCU^0.6859`, `MCU = (grain_lbs * Lovibond) / volume_gals`. Multi-fermentable bill out of scope.

## Affected files
- `src/brewlab/domain/ingredient.py` — extend `Yeast` with species, alcohol_tolerance, flavor_notes
- `src/brewlab/domain/yeast_library.py` (new) — `YeastLibrary` with curated strains + lookup methods
- `src/brewlab/core/fermentation.py` — clamp attenuation to strain range, validate ferment temp, return temperature_warning
- `src/brewlab/simulation/engine.py` — wire strain through, add summary fields: srm, chloride_sulfate_ratio, yeast_strain_id, yeast attenuation bounds
- `src/brewlab/simulation/solution_space.py` (new) — `explore_solution_space(recipe, n_samples)` sampling within min/max + yeast list, returns per-output min/max/median/p10/p90 + samples
- `src/brewlab/gui/app.py` — yeast strain selector; range-input mode; solution space tab; SRM + Cl:SO4 in overview
- `tests/test_yeast_library.py`, `tests/test_fermentation_strain.py`, `tests/test_solution_space.py` (new)

## Ordered tasks

1. Extend `Yeast` dataclass (species, alcohol_tolerance, flavor_notes) in `domain/ingredient.py`.
2. Create `domain/yeast_library.py` with ~10 curated strains (US-05, WLP001, Wyeast 1056, W-34/74, S-23, S-04, London Ale III, Belgian ale, Hefeweizen, Kveik); `get`/`list`/`by_species`.
3. Wire strain into `core/fermentation.py`: optional `attenuation_min`/`attenuation_max` clamp on predicted attenuation; validate ferment temp vs strain range; return `temperature_warning`.
4. Wire strain + SRM + chloride_sulfate_ratio into `simulation/engine.py` summary.
5. Create `simulation/solution_space.py`: `explore_solution_space` sampling uniformly within each [min,max] and across yeast list; return min/max/median/p10/p90 + sample list.
6. GUI: yeast strain selector in ferment sidebar; global "solution space" toggle; ranged min/max inputs for the six confirmed parameters; solution space tab with range bars + parallel coordinates; SRM + Cl:SO4 columns in overview tab.
7. Add tests: yeast library lookup/defaults/list/species filter; attenuation clamping + temperature warning; solution-space bounds + point-estimate-in-range.
8. Run full validation: `pytest` + `ruff check` + `ruff format --check` + `mypy src`. All green.
9. Commit and push (no remote currently configured; user must add origin first).

## Validation contract
- Every sampled output's min/max must bound all samples; every point estimate must fall within [min,max].
- Strain attenuation clamp: predicted attenuation never exceeds strain's attenuation_max nor below attenuation_min.
- Ferment temp outside strain [temperature_min, temperature_max] triggers `temperature_warning`.
- All existing 93 tests still pass; new tests added.

## Out of scope
- SGD integration; multi-fermentable grain bill; whirlpool/dry-hop aroma; water ions beyond Ca/Mg/bicarbonate/Cl/SO4.
