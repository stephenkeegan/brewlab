# Model: Residual Alkalinity

**Module:** `brewlab.core.equilibrium.residual_alkalinity`
**Classification:** empirical (brewing convention)
**Test:** `tests/test_equilibrium.py`

## Equation

    RA = Alkalinity - Ca_hardness - Magnesium_hardness

with all terms expressed as mg/L as CaCO3.

- Calcium hardness (as CaCO3) = [Ca] (mg/L) * (EQW_CaCO3 / MW_CA)
- Magnesium hardness (as CaCO3) = [Mg] (mg/L) * (EQW_CaCO3 / MW_MG)

## Parameters

| Parameter | Unit | Notes |
|---|---|---|
| Alkalinity | mg/L as CaCO3 | from bicarbonate |
| [Ca] | mg/L | calcium |
| [Mg] | mg/L | magnesium |

## Assumptions

- All hardness is expressed as CaCO3-equivalent.
- Residual alkalinity linearly combines alkalinity and hardness.

## Limitations

- **Empirical:** the exact divisor used in brewing (e.g. Kolbach's
  Ca/3.5, Mg/7) is not applied here; this is the simpler convention.
- RA is a mash-pH predictor, not a first-principles pH calculation.
- Positive RA tends to raise mash pH; negative RA tends to lower it.

## Literature source

- Kolbach residual alkalinity concept (brewing convention); Palmer,
  *How to Brew* (water chapter).

## Validation

- `test_residual_alkalinity_arithmetic`: RA = alkalinity - Ca_hardness - Mg_hardness.
