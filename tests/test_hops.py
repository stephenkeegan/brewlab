"""Hops model validation tests.

Validates:
    alpha_acid_isomerization_fraction -> monotonic in time/temperature,
                                        bounded [0,1], zero at zero time
    iso_alpha_concentration           -> mass balance arithmetic
    predicted_ibu                     -> scales with utilization efficiency
"""

from __future__ import annotations

import pytest

from brewlab.core.hops import (
    alpha_acid_isomerization_fraction,
    iso_alpha_concentration,
    predicted_ibu,
)
from brewlab.units import ureg


def test_isomerization_zero_time() -> None:
    """Zero boil time -> zero isomerization."""
    result = alpha_acid_isomerization_fraction(
        ureg.Quantity(0.0, "minute"),
        ureg.Quantity(100.0, "degC"),
    )
    assert result.magnitude == pytest.approx(0.0, abs=1e-9)


def test_isomerization_bounded() -> None:
    """Fraction always in [0, 1] even for long boils."""
    short = alpha_acid_isomerization_fraction(
        ureg.Quantity(5.0, "minute"), ureg.Quantity(100.0, "degC")
    ).magnitude
    long_ = alpha_acid_isomerization_fraction(
        ureg.Quantity(500.0, "minute"), ureg.Quantity(100.0, "degC")
    ).magnitude
    assert 0.0 <= short <= 1.0
    assert 0.0 <= long_ <= 1.0


def test_isomerization_increases_with_time() -> None:
    """Longer boil -> more isomerization (at fixed T)."""
    t15 = alpha_acid_isomerization_fraction(
        ureg.Quantity(15.0, "minute"), ureg.Quantity(100.0, "degC")
    ).magnitude
    t60 = alpha_acid_isomerization_fraction(
        ureg.Quantity(60.0, "minute"), ureg.Quantity(100.0, "degC")
    ).magnitude
    assert 0.0 < t15 < t60 < 1.0


def test_isomerization_increases_with_temperature() -> None:
    """Higher boil T -> faster isomerization (fixed time), within range."""
    t90 = alpha_acid_isomerization_fraction(
        ureg.Quantity(60.0, "minute"), ureg.Quantity(90.0, "degC")
    ).magnitude
    t100 = alpha_acid_isomerization_fraction(
        ureg.Quantity(60.0, "minute"), ureg.Quantity(100.0, "degC")
    ).magnitude
    assert 0.0 < t90 < t100 < 1.0


def test_iso_alpha_mass_balance() -> None:
    """100 g hops at 5% alpha, fully isomerized, 20 L -> 250 mg/L."""
    result = iso_alpha_concentration(
        ureg.Quantity(100.0, "gram"),
        ureg.Quantity(0.05, "dimensionless"),
        ureg.Quantity(20.0, "liter"),
        ureg.Quantity(1.0, "dimensionless"),
    )
    # 100 g * 0.05 alpha * 1.0 isomerized = 5 g = 5000 mg / 20 L = 250 mg/L
    assert result.magnitude == pytest.approx(250.0, rel=1e-6)


def test_predicted_ibu_scales_with_utilization() -> None:
    """Higher utilization -> higher IBU for same iso-alpha concentration."""
    base = predicted_ibu(
        ureg.Quantity(50.0, "milligram / liter"),
        ureg.Quantity(0.30, "dimensionless"),
    ).magnitude
    high = predicted_ibu(
        ureg.Quantity(50.0, "milligram / liter"),
        ureg.Quantity(0.60, "dimensionless"),
    ).magnitude
    assert high == pytest.approx(2 * base)


def test_predicted_ibu_units() -> None:
    result = predicted_ibu(
        ureg.Quantity(50.0, "milligram / liter"),
        ureg.Quantity(0.30, "dimensionless"),
    )
    assert str(result.units) == "IBU"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
