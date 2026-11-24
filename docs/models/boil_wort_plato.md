# Model: Wort Strength (°Plato) After Boil

**Module:** `brewlab.core.boil.wort_plato_after_boil`
**Classification:** mechanistic
**Test:** `tests/test_boil.py`

## Equation

Boil-off removes water only, so extract mass is conserved:

    extract_mass = p0 * water_mass_0 / (1 - p0)     [p0 = initial Plato fraction]
    water_mass(t) = (V0 - R * t) * 1000             [g, density ~1 kg/L]
    Plato(t) = extract_mass / (water_mass(t) + extract_mass) * 100

## Parameters

| Parameter | Unit | Typical value | Notes |
|---|---|---|---|
| initial Plato | degPlato | input | pre-boil wort strength |
| V0 | liter | input | pre-boil volume |
| R | liter/hour | ~4 | boil-off rate |
| t | hour | input | boil time |

## Assumptions

- Boil-off is pure water; dissolved extract mass is constant.
- Water density = 1 kg/L.
- Neglects extract losses to foam/trub and temperature-dependent density.

## Limitations

- At very high boil-off (volume approaching zero), the model diverges
  appropriately but is not physically meaningful near dryness.
- Does not model sugar caramelization or Maillard reactions during the boil.

## Validation

- `test_wort_plato_zero_boil_off_unchanged`: Plato unchanged with no boil-off.
- `test_wort_plato_rises_as_volume_falls`: Plato increases as water evaporates.
- `test_wort_plato_mass_balance`: manual mass-balance check (10 Plato, 20 L,
  1 hr at 4 L/hr -> ~12.20 Plato).
