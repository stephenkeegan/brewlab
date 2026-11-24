# Model: Fermentation (Yeast Growth, Ethanol, CO2)

**Module:** `brewlab.core.fermentation`
**Classification:** mechanistic-structured (Luedeking-Piret ODE batch); parameters
are calibration targets
**Test:** `tests/test_fermentation.py`

## Equation

Batch ODE system (yeast X g/L, sugar S g/L, ethanol P g/L), solved with
``scipy.integrate.solve_ivp``:

    mu(T,S) = mu_max * temp_factor(T) * S/(Ks + S)                 [Monod]
    dX/dt   = mu * X                                               [yeast growth]
    dP/dt   = (alpha * mu + beta) * X                              [ethanol, Luedeking-Piret]
    dS/dt   = -(1/Yxs) * mu * X - dP/dt / Yps_theoretical          [sugar consumed]
    CO2     = P * (88/92)                                          [stoichiometric]

where `temp_factor(T) = exp(-((T - Topt)^2)/(2*Tsigma^2))` (empirical Gaussian).

## Parameters

| Parameter | Unit | Default | Notes |
|---|---|---|---|
| mu_max | 1/hr | 0.4 | max specific growth rate at Topt (calibrate) |
| Ks | g/L | 2.0 | Monod half-saturation (calibrate) |
| Yxs | g yeast/g sugar | 0.10 | biomass yield (calibrate) |
| alpha | g ethanol/g yeast | 0.5 | growth-associated ethanol (calibrate) |
| beta | g ethanol/(g yeast·hr) | 0.02 | non-growth-associated ethanol (calibrate) |
| Yps | g ethanol/g sugar | 0.511 | theoretical (92/180) |
| Topt | degC | 20 | yeast temperature optimum (strain-dependent) |
| Tsigma | degC | 8 | temperature-response width |

## Assumptions

- Well-mixed batch, constant temperature and volume.
- Sugar consumed for biomass (Yxs) and ethanol (Luedeking-Piret).
- CO2 stoichiometric with ethanol; no CO2 loss to headspace modeled.

## Limitations

- **All kinetic parameters are calibration targets** (defaults are
  placeholders); fit to measured fermentation curves per strain/system.
- Does not model esters, higher alcohols, diacetyl, yeast flocculation,
  oxygen requirements, or stress.
- Temperature response is a simple Gaussian, not a cardinal model.
- ABV from ethanol concentration is approximate (ethanol density 0.789).

## Validation

- `test_monod_zero_at_zero_substrate`, `test_monod_monotonic_in_substrate`,
  `test_monod_max_at_topt`
- `test_fermentation_sugar_non_increasing`,
  `test_fermentation_ethanol_and_co2_non_decreasing`,
  `test_fermentation_attenuation_bounded`,
  `test_fermentation_co2_stoichiometry`,
  `test_fermentation_produces_ethanol`,
  `test_fermentation_deterministic`
