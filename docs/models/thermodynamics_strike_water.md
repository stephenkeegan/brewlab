# Model: Strike-Water Temperature (Heat Balance)

**Module:** `brewlab.core.thermodynamics.strike_water_temperature`
**Classification:** mechanistic
**Test:** `tests/test_thermo.py`

## Equation

Single-infusion mash heat balance, neglecting vessel heat loss and assuming
thermal equilibrium at the target temperature:

    m_w * c_w * (T_strike - T_target) = m_g * c_g * (T_target - T_grain)

    T_strike = T_target + m_g * c_g * (T_target - T_grain) / (m_w * c_w)

where strike-water volume is converted to mass using water density
(1 kg/L).

## Parameters

| Parameter | Unit | Typical value | Notes |
|---|---|---|---|
| m_g | kg | input | grain mass |
| T_grain | degC | input | grain temperature |
| T_target | degC | input | target mash temperature |
| m_w/g | L/kg | input | water-to-grain ratio |
| c_g | kJ/(kg·K) | ~1.0 | grain specific heat |
| c_w | kJ/(kg·K) | 4.186 | water specific heat |

## Assumptions

- No vessel heat loss (adiabatic).
- Thermal equilibrium reached at T_target.
- Water density = 1 kg/L (volume-to-mass conversion).
- Constant specific heats over the temperature range.

## Limitations

- Vessel thermal mass and heat loss are neglected (under-predicts required
  strike temp for uninsulated systems).
- Grain specific heat is uncertain (~0.4-1.0 kJ/(kg·K) depending on source);
  treat as calibration parameter.
- Does not account for boil or decoction.

## Literature source

- Standard single-infusion strike-water calculation (Palmer, *How to Brew*;
  brewing water calculations).

## Validation

- `test_strike_warmer_than_target_when_grain_cold`: strike > target.
- `test_strike_equals_target_when_grain_at_target`: strike == target.
- `test_strike_cooler_than_target_when_grain_hot`: strike < target.
- `test_strike_deterministic`, `test_strike_carries_temperature_units`,
  `test_strike_lower_ratio_raises_strike_temp`.
