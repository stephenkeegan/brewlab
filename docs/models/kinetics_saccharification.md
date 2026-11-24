# Model: Mash Enzymatics (Saccharification)

**Module:** `brewlab.core.kinetics`
**Classification:** empirical-structured
**Test:** `tests/test_kinetics.py`

## Equation

Starch conversion follows first-order batch kinetics:

    X(t) = 1 - exp(-k(T) * t)

where `X` is the fraction of convertible starch converted and

    k(T) = k_65C * [gelatinization(T) * enzyme_activity(T)] /
           [gelatinization(65C) * enzyme_activity(65C)]

so `k(65 C) == k_65C` by construction (k_65C = 0.037 1/min, calibrated so a
60-minute mash at 65 C reaches ~80% conversion).

Temperature response:

- Gelatinization (logistic, center 60 C, width 6 C):
    f_gel(T) = 1 / (1 + exp(-(T - 60) / 6))
- Alpha-amylase activity (Gaussian, center 70 C, sigma 10 C):
    f_alpha(T) = exp(-((T - 70)^2) / (2 * 10^2))
- Beta-amylase activity (Gaussian center 58 C, sigma 7 C, with
  exponential denaturation penalty above 65 C):
    f_beta(T) = exp(-((T - 58)^2) / (2 * 7^2)) * exp(-(T - 65) / 5) for T > 65
- Combined enzyme activity = 0.5 * f_alpha + 0.5 * f_beta

Extract (°Plato):

    extract_g = grain_mass(g) * extract_potential * X
    Plato = extract_g / (water_g + extract_g) * 100

## Parameters

| Parameter | Unit | Default | Notes |
|---|---|---|---|
| k_65C | 1/min | 0.037 | calibrated to ~80% conversion at 65 C/60 min |
| gelatinization center | degC | 60 | logistic |
| gelatinization width | degC | 6 | logistic |
| alpha optimum | degC | 70 | Gaussian |
| beta optimum | degC | 58 | Gaussian |
| extract_potential | fraction | input | grain-specific (e.g. 0.80) |

## Assumptions

- First-order conversion (single lumped rate constant).
- Enzyme activity is instantaneous vs temperature (no time-dependent
  thermal denaturation except the beta-amylase penalty above 65 C).
- Alpha and beta amylase weighted equally.
- Water density = 1 kg/L for Plato calculation (dilute approximation).

## Limitations

- **Empirical:** k_65C and the temperature-response curves are fitted to
  typical brewhouse behavior, not derived from enzyme mechanism.
- No time-dependent enzyme inactivation (a real mash loses activity over
  time, especially beta-amylase above 65 C).
- Does not model individual sugar profiles (maltose vs dextrins).

## Literature source

- Bamforth, *Principles of Brewing Science* (mash enzymology).
- Kunze, *Technology Brewing and Malting* (mash temperature rests).

## Validation

- `test_saccharification_rate_at_reference`: k(65 C) == 0.037 1/min.
- `test_saccharification_conversion_60min_65c`: ~80% conversion.
- `test_saccharification_monotonic_in_time`, `test_saccharification_faster_at_higher_temperature`.
- `test_extract_plato_definitional`, `test_extract_plato_scales_with_conversion`.
- Gelatinization/amylase activity curve-shape tests.
