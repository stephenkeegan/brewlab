# Model: Carbonate-System pH

**Module:** `brewlab.core.equilibrium.carbonate_system_ph`
**Classification:** mechanistic
**Test:** `tests/test_equilibrium.py`

## Equation

Solves for [H+] in the charge balance:

    alkalinity = [HCO3-] + 2[CO3--] + [OH-] - [H+]

with:

- [CO2(aq)] = KH(T) * pCO2   (Henry's law)
- [HCO3-] = Ka1(T) * [CO2] / [H+]
- [CO3--] = Ka1(T) * Ka2(T) * [CO2] / [H+]^2
- [OH-] = Kw(T) / [H+]

Constants are temperature-corrected via van't Hoff from 25 °C reference
values:

    log10(k_t / k_ref) = -dH / (2.303 * R) * (1/t - 1/t_ref)

pH = -log10([H+]), solved by 1-D root finding (brentq) over pH 1-13.

## Parameters

| Parameter | Unit | Default | Notes |
|---|---|---|---|
| alkalinity | mg/L as CaCO3 | input | total alkalinity |
| temperature | degC | input | water temperature |
| pCO2 | atm | 0.0004 | ~400 ppm atmospheric |

Constants (25 °C): pKa1 = 6.35, pKa2 = 10.33, pKw = 13.997,
KH_CO2 = 0.034 mol/(L·atm).

## Assumptions

- Carbonate system dominates charge balance (other ions ignored).
- Water is in equilibrium with a fixed CO2 partial pressure.
- Activity coefficients = 1 (concentrations used directly).

## Limitations

- Not validated for high-ionic-strength wort (activity coefficients matter).
- pKa/pKw temperature corrections use constant enthalpies (van't Hoff).
- Open-to-atmosphere assumption may not hold in closed vessels.

## Literature source

- Stumm & Morgan, *Aquatic Chemistry* (carbonate system).
- Plummer & Parkhurst (pKa temperature dependence).

## Validation

- `test_carbonate_ph_pure_water_atmospheric_co2`: pure water + atmospheric
  CO2 at 25 C -> pH ~5.6 (expected for rainwater in equilibrium with air).
- `test_carbonate_ph_higher_alkalinity_is_higher_ph`: buffering raises pH.
- `test_carbonate_ph_temperature_effect`: at fixed pCO2, higher T -> less
  dissolved CO2 -> higher pH.
