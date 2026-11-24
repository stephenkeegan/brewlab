"""Thermodynamics validation tests.

Validates the strike-water heat balance against physical bounds:
    strike temp > target when grain is colder than target
    strike temp == target when grain is already at target
    strike temp < target when grain is hotter than target
    deterministic: same inputs -> same output
    carries temperature units
"""

from __future__ import annotations

import pytest

from brewlab.core.thermodynamics import strike_water_temperature
from brewlab.units import Quantity, ureg

_CP_GRAIN = ureg.Quantity(1.0, "kilojoule / (kilogram * degC)")
_CP_WATER = ureg.Quantity(4.186, "kilojoule / (kilogram * degC)")


def _strike(
    grain_mass: Quantity = ureg.Quantity(5.0, "kilogram"),
    grain_temp: Quantity = ureg.Quantity(20.0, "degC"),
    target: Quantity = ureg.Quantity(65.0, "degC"),
    ratio: Quantity = ureg.Quantity(3.0, "liter / kilogram"),
) -> Quantity:
    return strike_water_temperature(grain_mass, grain_temp, target, ratio, _CP_GRAIN, _CP_WATER)


def test_strike_warmer_than_target_when_grain_cold() -> None:
    """Cold grain requires strike water above the target mash temperature."""
    result = _strike(grain_temp=ureg.Quantity(20.0, "degC"), target=ureg.Quantity(65.0, "degC"))
    assert result.magnitude > 65.0
    assert result.magnitude < 90.0


def test_strike_equals_target_when_grain_at_target() -> None:
    """Grain already at target -> strike water at target (equilibrium)."""
    result = _strike(grain_temp=ureg.Quantity(65.0, "degC"), target=ureg.Quantity(65.0, "degC"))
    assert result.magnitude == pytest.approx(65.0, abs=1e-6)


def test_strike_cooler_than_target_when_grain_hot() -> None:
    """Hot grain requires strike water below the target mash temperature."""
    result = _strike(grain_temp=ureg.Quantity(80.0, "degC"), target=ureg.Quantity(65.0, "degC"))
    assert result.magnitude < 65.0


def test_strike_deterministic() -> None:
    """Same inputs produce the same output."""
    a = _strike()
    b = _strike()
    assert a.magnitude == b.magnitude


def test_strike_carries_temperature_units() -> None:
    result = _strike()
    assert result.dimensionality == ureg.Quantity(1, "degC").dimensionality


def test_strike_lower_ratio_raises_strike_temp() -> None:
    """Less water per grain (lower ratio) -> higher required strike temp."""
    low_ratio = _strike(ratio=ureg.Quantity(2.0, "liter / kilogram")).magnitude
    high_ratio = _strike(ratio=ureg.Quantity(4.0, "liter / kilogram")).magnitude
    assert low_ratio > high_ratio


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
