# Model: °Plato <-> Specific Gravity

**Module:** `brewlab.core.boil`
**Classification:** empirical (approximate polynomial fit)
**Test:** `tests/test_boil.py`

## Equation

SG from Plato (ASBC/EBC approximate fit):

    SG = 1 + Plato / (258.6 - ((Plato / 258.2) * 227.1))

Plato from SG: numerical inversion of the same relation (fixed-point
iteration).

## Parameters

| Parameter | Unit | Range | Notes |
|---|---|---|---|
| Plato | degPlato | ~0-30 | typical beer wort |
| SG | dimensionless | ~1.000-1.120 | typical beer wort |

## Assumptions

- The relation is an empirical fit, not a fundamental equation of state.

## Limitations

- Degrades above ~30 °Plato (high-gravity worts); use a density meter or
  sucrose-based reference for strong worts.
- Temperature-dependent density is not corrected (reported at calibration
  temperature, typically 20 °C).

## Validation

- `test_plato_to_sg_known_point`: 10 degPlato -> SG ~1.040.
- `test_sg_to_plato_round_trip`: Plato -> SG -> Plato round trip.
- `test_sg_to_plato_zero`: SG 1.0 -> 0 Plato.
