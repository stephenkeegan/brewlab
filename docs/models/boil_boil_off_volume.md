# Model: Boil-Off Volume

**Module:** `brewlab.core.boil.boil_off_volume`
**Classification:** mechanistic
**Test:** `tests/test_boil.py`

## Equation

    V(t) = V0 - R * t

where `V0` is the pre-boil volume, `R` is the boil-off rate (volume/time), and
`t` is boil time. Result is clamped at zero (boil-off cannot remove more than
the starting volume).

## Parameters

| Parameter | Unit | Typical value | Notes |
|---|---|---|---|
| V0 | liter | input | pre-boil volume |
| R | liter/hour | ~4 | system-dependent boil-off rate |
| t | hour | input | boil time |

## Assumptions

- Boil-off removes water only; the rate is constant over the boil.
- No volume gain from added hops/finings (neglected).

## Limitations

- Constant boil-off rate ignores ramp-up, evaporation surface area, and
  power variations. Treat `R` as a calibration parameter per system.

## Validation

- `test_boil_off_volume_linear`: 20 L at 4 L/hr for 1 hr -> 16 L.
- `test_boil_off_volume_clamped_at_zero`: long boil -> 0 L.
- `test_boil_off_zero_time`: unchanged volume.
