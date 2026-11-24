# Scientific Model Documentation

Each model in `brewlab.core` has a corresponding file here describing:

- **Equation**: the mathematical expression (with units).
- **Parameters**: names, units, typical ranges, source.
- **Assumptions**: what is assumed/simplified.
- **Limitations**: where the model breaks down.
- **Literature source**: citation (ASBC, EBC, textbook, paper).
- **Classification**: `mechanistic` or `empirical`.
- **Validation**: which test file checks it and against what values.

## Convention

File name: `<module>_<model>.md`, e.g. `equilibrium_ionic_strength.md`.

## MVP models (Phase 1)

- `core/units.py` → unit handling (no scientific equation)
- `core/thermodynamics.py` → strike-water heat balance
- `core/equilibrium.py` → ionic strength, acid-base, mash pH
- `core/kinetics.py` → Arrhenius rate law, saccharification kinetics
