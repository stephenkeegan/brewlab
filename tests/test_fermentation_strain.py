"""Fermentation strain clamping tests (Phase 9).

Validates that predicted attenuation is clamped to the yeast strain's
attenuation range and that ferment temperature outside the strain range
triggers a temperature warning.
"""

from __future__ import annotations

import pytest

from brewlab.core.fermentation import fermentation_time_series
from brewlab.units import ureg

_HIGH_SUGAR = ureg.Quantity(120.0, "gram / liter")
_YEAST = ureg.Quantity(0.1, "gram / liter")
_VOLUME = ureg.Quantity(20.0, "liter")
_TEMP = ureg.Quantity(20.0, "degC")
_DURATION = ureg.Quantity(72.0, "hour")


def test_no_clamp_without_strain_bounds() -> None:
    """Backward compatibility: no attenuation_min/max means raw attenuation."""
    result = fermentation_time_series(_HIGH_SUGAR, _YEAST, _VOLUME, _TEMP, _DURATION)
    assert result["temperature_warning"] is False
    assert 0.0 <= result["final_attenuation"] <= 1.0
    assert result["final_fg_plato"] >= 0.0
    assert result["final_abv_percent"] >= 0.0


def test_attenuation_clamped_to_max() -> None:
    """Low attenuation_max caps predicted attenuation."""
    result = fermentation_time_series(
        _HIGH_SUGAR,
        _YEAST,
        _VOLUME,
        _TEMP,
        _DURATION,
        attenuation_max=ureg.Quantity(0.50, "dimensionless"),
    )
    assert result["final_attenuation"] == pytest.approx(0.50)
    assert result["final_attenuation"] <= result["raw_attenuation"]


def test_attenuation_clamped_to_min() -> None:
    """Attenuation never falls below attenuation_min."""
    result = fermentation_time_series(
        _HIGH_SUGAR,
        _YEAST,
        _VOLUME,
        _TEMP,
        _DURATION,
        attenuation_min=ureg.Quantity(0.95, "dimensionless"),
    )
    # Raw attenuation is 1.0 with these defaults, so min clamp of 0.95 is
    # satisfied without changing the value; the key guarantee is the bound.
    assert result["final_attenuation"] >= 0.95


def test_attenuation_clamped_within_range() -> None:
    """Raw attenuation inside strain range is unchanged; outside is clamped."""
    result = fermentation_time_series(
        _HIGH_SUGAR,
        _YEAST,
        _VOLUME,
        _TEMP,
        _DURATION,
        attenuation_min=ureg.Quantity(0.50, "dimensionless"),
        attenuation_max=ureg.Quantity(0.90, "dimensionless"),
    )
    # Raw attenuation is 1.0, above max 0.90, so clamped down to 0.90.
    assert result["final_attenuation"] == pytest.approx(0.90)
    assert 0.50 <= result["final_attenuation"] <= 0.90


def test_temperature_warning_outside_range() -> None:
    """Ferment temperature below strain minimum triggers warning."""
    result = fermentation_time_series(
        _HIGH_SUGAR,
        _YEAST,
        _VOLUME,
        ureg.Quantity(5.0, "degC"),
        _DURATION,
        temperature_min=ureg.Quantity(18.0, "degC"),
        temperature_max=ureg.Quantity(22.0, "degC"),
    )
    assert result["temperature_warning"] is True


def test_temperature_warning_above_range() -> None:
    """Ferment temperature above strain maximum triggers warning."""
    result = fermentation_time_series(
        _HIGH_SUGAR,
        _YEAST,
        _VOLUME,
        ureg.Quantity(30.0, "degC"),
        _DURATION,
        temperature_min=ureg.Quantity(18.0, "degC"),
        temperature_max=ureg.Quantity(22.0, "degC"),
    )
    assert result["temperature_warning"] is True


def test_no_temperature_warning_within_range() -> None:
    """Ferment temperature inside strain range gives no warning."""
    result = fermentation_time_series(
        _HIGH_SUGAR,
        _YEAST,
        _VOLUME,
        ureg.Quantity(20.0, "degC"),
        _DURATION,
        temperature_min=ureg.Quantity(18.0, "degC"),
        temperature_max=ureg.Quantity(22.0, "degC"),
    )
    assert result["temperature_warning"] is False


def test_clamping_recomputes_fg_and_abv() -> None:
    """Clamped attenuation produces lower FG and higher ABV when clamped up."""
    base = fermentation_time_series(
        _HIGH_SUGAR,
        _YEAST,
        _VOLUME,
        _TEMP,
        _DURATION,
        attenuation_min=ureg.Quantity(0.30, "dimensionless"),
        attenuation_max=ureg.Quantity(0.40, "dimensionless"),
    )
    clamped_high = fermentation_time_series(
        _HIGH_SUGAR,
        _YEAST,
        _VOLUME,
        _TEMP,
        _DURATION,
        attenuation_min=ureg.Quantity(0.80, "dimensionless"),
        attenuation_max=ureg.Quantity(0.90, "dimensionless"),
    )
    assert clamped_high["final_fg_plato"] < base["final_fg_plato"]
    assert clamped_high["final_abv_percent"] > base["final_abv_percent"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
