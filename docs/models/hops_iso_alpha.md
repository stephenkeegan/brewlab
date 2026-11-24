# Model: Iso-Alpha Acid Concentration

**Module:** `brewlab.core.hops.iso_alpha_concentration`
**Classification:** mechanistic (mass balance)
**Test:** `tests/test_hops.py`

## Equation

    iso_alpha_mg = alpha_acid_mass(g) * alpha_fraction *
                   isomerized_fraction * 1000        [g -> mg]
    concentration (mg/L) = iso_alpha_mg / volume(L)

## Parameters

| Parameter | Unit | Notes |
|---|---|---|
| alpha_acid_mass | gram | hops mass |
| alpha_acid_fraction | dimensionless | alpha-acid % of hops (e.g. 0.05) |
| isomerized_fraction | dimensionless | from isomerization model |
| volume | liter | wort volume |

## Assumptions

- All isomerized alpha acids dissolve into the wort (no loss at this step;
  losses are handled by utilization efficiency in predicted_ibu).

## Validation

- `test_iso_alpha_mass_balance`: 100 g hops at 5% alpha, fully isomerized,
  20 L -> 250 mg/L.
