# Model: Alpha-Acid Isomerization Fraction

**Module:** `brewlab.core.hops.alpha_acid_isomerization_fraction`
**Classification:** mechanistic (first-order Arrhenius); parameters are
calibration targets
**Test:** `tests/test_hops.py`

## Equation

Alpha acids (humulone) isomerize to iso-alpha acids during the boil:

    fraction_iso(t) = 1 - exp(-k_iso(T) * t)
    k_iso(T) = A * exp(-Ea / (R * T))        (Arrhenius)

## Parameters

| Parameter | Unit | Default | Notes |
|---|---|---|---|
| t | minute | input | boil time remaining for the addition |
| T | degC | input | boil temperature |
| A (pre-exponential) | 1/min | 1.0e8 | calibration target |
| Ea (activation energy) | J/mol | 70000 | calibration target |

## Assumptions

- First-order isomerization kinetics.
- Constant boil temperature.
- Isomerization is irreversible on the boil timescale.

## Limitations

- **A and Ea are not established constants** for a general system; they must
  be fit to measured bitterness for the specific equipment/process. The
  defaults are placeholders.
- Does not model alpha-acid degradation/oxidation or isomerization reversal.
- Temperature ramps (heat-up/cool-down) are treated as constant at boil T.

## Validation

- `test_isomerization_zero_time`: zero time -> zero isomerization.
- `test_isomerization_bounded`: fraction in [0, 1].
- `test_isomerization_increases_with_time` / `with_temperature`: monotonic.
