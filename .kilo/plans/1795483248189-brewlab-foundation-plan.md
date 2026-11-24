# BrewLab Foundation Plan

**Plan file:** `.kilo/plans/1795483248189-brewlab-foundation-plan.md`
**Status:** Implementation-ready (plan mode complete)
**Branch:** `flint-motorcycle` (greenfield; only `.git` + `.kilo/plans/` present)

---

## 1. Repository assessment

- Empty greenfield repository. Single initial commit `1ad6871`; working tree clean.
- No source code, no package config, no tests, no CI.
- Available toolchain: Python 3.11+ (conda at `/opt/homebrew/Caskroom/miniconda/base/bin/python3`).
- NOT installed: `uv`, `poetry`, `pytest`, `ruff`, `mypy`, `node`, `npm`. These must be provisioned before implementation.

## 2. Resolved decisions

| Decision | Resolution | Rationale |
|---|---|---|
| Language | Python 3.11+ | Available in environment; standard scientific stack (NumPy/SciPy/pint); strong ODE/optimization ecosystem |
| Project/package name | `brewlab` | Confirmed by user |
| Units / dimensional analysis | `pint` (single `UnitRegistry`) | Prevents unit bugs at scientific boundaries; explicit conversions; deterministic |
| Package layout | `src/brewlab` + `tests/` | Keeps importable package separate from tests; standard for Python libs |
| Package manager | `uv` (recommended) / `pip` + venv fallback | `uv` not installed; plan notes provisioning step |
| Testing | `pytest` | Not installed; will be added to dev dependencies |
| Lint / types | `ruff` + `mypy` | Not installed; added to dev dependencies |
| First scientific model | Water chemistry + mash enzymatics | Foundational, well-established in literature, independent of later boil/fermentation stages |

Decisions marked "(Recommended)" were accepted by user. The MVP first model was not explicitly chosen by user; water chemistry + mash enzymatics is my architect recommendation and is adopted as the plan default.

## 3. Technology architecture (layered)

Per the vision, keep strict boundaries. Scientific core must be importable and testable with zero UI/application dependency.

Repo root:
```
pyproject.toml
src/brewlab/
  __init__.py
  units.py              # pint UnitRegistry singleton + Quantity helpers; single source of units
  core/                 # SCIENTIFIC CORE (no domain/app imports)
    __init__.py
    thermodynamics.py   # T-dependent cp, density, enthalpy, heat balances
    transport.py        # heat/mass transfer stubs (out of MVP)
    equilibrium.py      # acid-base, ionic strength, solubility/phase equilibria
    kinetics.py         # ODE framework, Arrhenius, reaction-rate expressions
    validation.py       # solver tolerance/reproducibility helpers
  domain/               # BREWING DOMAIN MODEL
    __init__.py
    ingredient.py       # Ingredient, Malt, Hop, Yeast, WaterProfile
    recipe.py           # Recipe, Fermentable, HopAddition
    batch.py            # Batch, ProcessStage, Measurement
    equipment.py        # Equipment (geometry, dead space, losses)
    stage.py            # MashStage, BoilStage base classes
  simulation/           # SIMULATION ENGINE (out of MVP phase 1)
    __init__.py
    engine.py           # time-stepping orchestrator
    state.py            # SimulationState
  data/                 # DATA INTEGRATION (out of MVP phase 1)
    __init__.py
    ingestion.py        # CSV/structured import
    measurement.py      # Measurement + provenance + units
  optimization/         # OPTIMIZATION ENGINE (out of MVP)
    __init__.py
    interfaces.py       # future interfaces only
  persistence/          # PERSISTENCE LAYER (abstract interface, out of MVP)
    __init__.py
    repository.py       # abstract Repository
tests/
  test_units.py
  test_thermo.py
  test_equilibrium.py
  test_kinetics.py
  test_domain.py
docs/models/            # per-model: equation, parameters, assumptions, limitations, literature source
```

Units pattern: module-level `ureg = UnitRegistry()` in `units.py`; all models import and use this single registry. Register brewing aliases: `degPlato`, `degLovibond`, `IBU`, `ppm_as_CaCO3`, `gpl`, `point` (gravity points). All scientific quantities are `pint.Quantity`; no bare floats cross layer boundaries.

Data flow (one stage): `Ingredient/Recipe + Equipment + stage params` → units-checked scientific model → `SimulationState` outputs → next stage inputs → batch record → measurement comparison.

## 4. Scientific subsystem breakdown

| Subsystem | Responsibility | MVP? | Key equations / references |
|---|---|---|---|
| units | Single pint registry + brewing aliases; explicit conversions | Yes | pint |
| thermodynamics | T-dependent cp, density, enthalpy, strike-water heat balance | Yes | Q = m·cp·ΔT |
| equilibrium | Ionic strength, charge balance, acid-base (carbonate/phosphate), mash pH | Yes | ionic strength I; Henderson-Hasselbalch; alkalinity |
| kinetics | ODE framework, Arrhenius rate k(T)=A·exp(-Ea/RT), saccharification rate | Yes | Arrhenius; first-order/Michaelis-Menten |
| domain | Ingredient, Recipe, Batch, Equipment, MashStage/BoilStage | Yes | — |
| transport | heat/mass transfer | No | — |
| simulation | time-stepping orchestrator, SimulationState | No | — |
| data | CSV ingestion, Measurement + provenance | No | — |
| optimization | constraint solving, sensitivity, multi-objective | No | — |
| persistence | abstract Repository | No | — |

## 5. Core domain model (MVP)

- `WaterProfile`: ion concentrations (Ca, Mg, Na, K, Cl, SO4, HCO3), alkalinity; computes ionic strength, pH via acid-base equilibrium.
- `Malt`: color (Lovibond/EBC), extract potential, moisture, diastatic power.
- `Hop`: alpha/beta acid %, HSI, oil content.
- `Yeast`: strain id, attenuation range, flocculation, temp range.
- `Recipe`: collection of fermentables/hop additions/yeast/water adjustments; target OG/FG/ABV/IBU/SRM.
- `Batch`: links Recipe + Equipment + actual measurements; process stage log.
- `Equipment`: vessel volume, dead space, boil-off rate, efficiency.
- `MashStage` / `BoilStage`: configurable inputs, time-temperature profile, outputs to next stage.

All scientific quantities carry `pint.Quantity` with explicit units; no bare floats cross layer boundaries.

## 6. Scientific model implementation priorities (MVP = Phase 1)

1. **Units & dimensional analysis** — `pint` registry, brewing unit aliases (°Plato, °Lovibond, IBU, ppm as CaCO3), conversion helpers.
2. **Water chemistry** — ionic strength, charge balance, acid-base equilibria (carbonate/phosphate), pH prediction, mineral adjustment to target profile. Document equations (e.g., alkalinity, Henderson-Hasselbalch), assumptions, limits.
3. **Mash enzymatics** — starch gelatinization temperature window, alpha/beta amylase saccharification kinetics (Arrhenius temperature dependence), extract/yield prediction, mash pH coupling to water chemistry.
4. **Domain models** — Ingredient, Recipe, Batch, Equipment, MashStage/BoilStage base classes.
5. **Validation tests** — each model tested against published values (ASBC/EBC methods, known buffer pH, known extract yields); deterministic; solver tolerance tests.

Explicitly OUT of MVP: molecular dynamics, ML, Bayesian optimization, fermentation model, instrumentation API, GUI/app layer, persistence backend, hardware connectivity.

## 7. Testing and validation strategy

- Framework: `pytest` (to be installed).
- Every scientific model: unit test with asserted numeric outputs vs. published literature values; tolerance documented.
- Determinism: same inputs → same outputs (fixed ODE tolerances, no randomness in core).
- Unit consistency: tests assert `pint.Quantity` units at model boundaries; no dimensionless bare floats where units required.
- Solver validation: convergence test (tightening tolerances does not change result beyond tolerance).
- Sensitivity/uncertainty: one-at-a-time input perturbation tests documenting output sensitivity.
- Empirical vs. mechanistic: every model tagged `mechanistic` or `empirical`; empirical models flagged as replaceable, never presented as established physics.
- CI: run `pytest`, `ruff`, `mypy` on every change (CI config added in Phase 0).
- `docs/models/<model>.md`: equation, parameters, assumptions, limitations, literature source for each model.

## 8. Phased development roadmap

**Phase 0 — Foundation** — DONE (committed b7f0c57)
- Python venv provisioned; `numpy scipy pint pytest ruff mypy` installed
- Repo layout per §3; `pyproject.toml` (package `brewlab`, Python >=3.11)
- `units.py` (pint singleton + brewing aliases) + `test_units.py`
- CI config (pytest, ruff, mypy); `.github/workflows/ci.yml`
- `docs/models/` template

**Phase 1 — MVP scientific core** — DONE (committed b7f0c57)
- Water chemistry: ionic strength, alkalinity-as-CaCO3, hardness,
  residual alkalinity, carbonate-system pH solver + `test_equilibrium.py`
- Mash enzymatics: gelatinization, alpha/beta-amylase, saccharification
  conversion, extract/°Plato + `test_kinetics.py`
- Thermodynamics: strike-water heat balance + `test_thermo.py`
- Domain models: WaterProfile, Malt, Hop, Yeast, Recipe, Batch, Equipment,
  MashStage/BoilStage + `test_domain.py`
- `docs/models/*.md` for each model
- CLI `brewlab simulate mash`
- `pytest`/`ruff`/`mypy` all green

**Phase 2 — Boil & hop utilization** — DONE (committed 7958322)
- `core/boil.py`: boil-off volume, wort plato after boil (extract-mass
  balance), plato<->specific gravity (ASBC/EBC fit)
- `core/hops.py`: alpha-acid isomerization (first-order Arrhenius),
  iso-alpha acid concentration, predicted IBU (utilization efficiency);
  Arrhenius/utilization parameters flagged as calibration targets
- `test_boil.py`, `test_hops.py`; `docs/models` for boil + hops
- CLI `brewlab simulate boil`
- `pytest`/`ruff`/`mypy` all green

**Phase 3 — Fermentation basics** (next)
- Yeast growth (Monod/logistic), substrate consumption, ethanol & CO2
  production, attenuation, temperature-dependent rates
- `core/fermentation.py` + `test_fermentation.py`; `docs/models`
- Couple mash → boil → ferment stage outputs

**Out of MVP (deferred):** molecular dynamics, ML, Bayesian optimization,
instrumentation API, GUI/app layer, persistence backend, hardware
connectivity, coupled simulation engine (Phase 4), data integration
(Phase 5), optimization engine (Phase 6).



## 9. Identified technical and scientific risks

| Risk | Mitigation |
|---|---|
| Empirical equations presented as authoritative physics | Tag every model `mechanistic`/`empirical`; document assumptions & limits; empirical models marked replaceable |
| Numerical stiffness in ODE kinetics | Use `scipy.integrate.solve_ivp` with appropriate method + tolerance convergence tests |
| Unit inconsistencies across layers | Single `pint` registry; boundary assertions; no bare floats in scientific core |
| Overbuilding before validation | Phased scope; literature-validation gate before promoting a model to MVP |
| No validation data for some parameters | Clearly mark estimated vs. measured; flag as calibration target for Phase 5 |
| Premature complexity (MD/ML/optimization) | Explicitly out of MVP; deferred until underlying models + datasets exist |

## 10. Open questions (non-blocking)

None blocking implementation. Adopted defaults are documented in §2; user may adjust package name or MVP model order before Phase 0 begins.

## 11. Validation plan for the implementation agent

1. Provision Python env (`uv` or `venv` + pip), install `numpy scipy pint pytest ruff mypy`.
2. Scaffold repo per §3 layout; add `pyproject.toml` (package `brewlab`, Python >=3.11).
3. Implement `units.py` + tests (`test_units.py`).
4. Implement water chemistry + mash enzymatics + domain models + tests; each model against literature values.
5. Add `docs/models/*.md` for each model.
6. Add CLI `brewlab simulate mash`.
7. Run `pytest`, `ruff`, `mypy` — all green.
8. Commit to `flint-motorcycle` branch only if user explicitly requests (plan mode: do not commit).
