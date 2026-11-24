# Model: Ionic Strength

**Module:** `brewlab.core.equilibrium.ionic_strength`
**Classification:** mechanistic
**Test:** `tests/test_equilibrium.py`

## Equation

Ionic strength:

    I = 0.5 * sum_i (c_i * z_i^2)

where `c_i` is the molar concentration (mol/L) of ion `i` and `z_i` is its
signed charge.

## Parameters

| Parameter | Unit | Typical range | Notes |
|---|---|---|---|
| c_i (Ca) | mol/L | 0 - 0.002 | Charge +2 |
| c_i (Mg) | mol/L | 0 - 0.001 | Charge +2 |
| c_i (Na) | mol/L | 0 - 0.005 | Charge +1 |
| c_i (Cl) | mol/L | 0 - 0.005 | Charge -1 |
| c_i (SO4) | mol/L | 0 - 0.002 | Charge -2 |
| c_i (HCO3) | mol/L | 0 - 0.005 | Charge -1 |

## Assumptions

- Fully dissociated ions (no ion pairing).
- Charge lookup by ion name; unknown ions assigned charge 0.

## Limitations

- Does not account for activity coefficients (ionic strength is a precursor
  to activity calculations, not a substitute).
- Charge table is hard-coded for common brewing ions.

## Literature source

- Standard definition (e.g., Atkins & de Paula, *Physical Chemistry*);
  ASBC water-analysis methods.

## Validation

- `test_ionic_strength_nacl`: 0.01 M NaCl -> I = 0.01 M.
- `test_ionic_strength_cacl2`: 0.01 M CaCl2 -> I = 0.03 M.
- `test_ionic_strength_mixed`: known mixed-ion value.
