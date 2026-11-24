"""Mash enzymatics and kinetics validation tests.

Validates:
    gelatinization        -> sigmoidal, low at 50 C, high at 65-80 C
    alpha amylase         -> peaks near 70 C
    beta amylase          -> peaks near 58 C, drops above 65 C
    saccharification      -> ~80 % conversion at 65 C / 60 min (by calibration),
                             monotonic in time
    extract plato         -> definitional arithmetic from grain bill
"""

from __future__ import annotations

import math

import pytest

from brewlab.core.kinetics import (
    alpha_amylase_activity,
    beta_amylase_activity,
    extract_plato,
    gelatinization_factor,
    saccharification_conversion,
    saccharification_rate_constant,
)
from brewlab.units import ureg


def test_gelatinization_low_below_onset() -> None:
    """Below ~52 C gelatinization is small."""
    g = gelatinization_factor(ureg.Quantity(50.0, "degC")).magnitude
    assert 0.0 < g < 0.2


def test_gelatinization_high_at_mash_temp() -> None:
    """At typical mash temps gelatinization is substantial."""
    g = gelatinization_factor(ureg.Quantity(65.0, "degC")).magnitude
    assert 0.6 < g < 0.95


def test_gelatinization_saturates() -> None:
    """At high temperature gelatinization approaches 1."""
    g = gelatinization_factor(ureg.Quantity(80.0, "degC")).magnitude
    assert g > 0.9


def test_gelatinization_monotonic() -> None:
    """Gelatinization factor increases with temperature."""
    g55 = gelatinization_factor(ureg.Quantity(55.0, "degC")).magnitude
    g65 = gelatinization_factor(ureg.Quantity(65.0, "degC")).magnitude
    g75 = gelatinization_factor(ureg.Quantity(75.0, "degC")).magnitude
    assert g55 < g65 < g75


def test_alpha_amylase_peaks_near_70c() -> None:
    """Alpha-amylase activity maximal around 70 C."""
    a60 = alpha_amylase_activity(ureg.Quantity(60.0, "degC")).magnitude
    a70 = alpha_amylase_activity(ureg.Quantity(70.0, "degC")).magnitude
    a80 = alpha_amylase_activity(ureg.Quantity(80.0, "degC")).magnitude
    assert a70 > a60 and a70 > a80


def test_beta_amylase_peaks_near_58c() -> None:
    """Beta-amylase activity maximal around 55-60 C."""
    b50 = beta_amylase_activity(ureg.Quantity(50.0, "degC")).magnitude
    b58 = beta_amylase_activity(ureg.Quantity(58.0, "degC")).magnitude
    b70 = beta_amylase_activity(ureg.Quantity(70.0, "degC")).magnitude
    assert b58 > b50
    assert b70 < b58  # denaturation above ~65 C suppresses activity


def test_saccharification_rate_at_reference() -> None:
    """k(65 C) equals the calibrated k_65C by construction."""
    k = saccharification_rate_constant(ureg.Quantity(65.0, "degC")).to("1 / minute").magnitude
    assert k == pytest.approx(0.037, rel=1e-6)


def test_saccharification_conversion_60min_65c() -> None:
    """Calibrated so 60 min at 65 C -> ~80 % conversion."""
    x = saccharification_conversion(
        ureg.Quantity(60.0, "minute"), ureg.Quantity(65.0, "degC")
    ).magnitude
    assert x == pytest.approx(1.0 - math.exp(-0.037 * 60.0), rel=1e-6)
    assert 0.7 < x < 0.9


def test_saccharification_monotonic_in_time() -> None:
    """Conversion increases with time at fixed temperature."""
    x30 = saccharification_conversion(
        ureg.Quantity(30.0, "minute"), ureg.Quantity(65.0, "degC")
    ).magnitude
    x60 = saccharification_conversion(
        ureg.Quantity(60.0, "minute"), ureg.Quantity(65.0, "degC")
    ).magnitude
    assert 0.0 < x30 < x60 < 1.0


def test_saccharification_faster_at_higher_temperature() -> None:
    """Within the active range, higher T gives faster conversion (60 min)."""
    x60_at_60 = saccharification_conversion(
        ureg.Quantity(60.0, "minute"), ureg.Quantity(60.0, "degC")
    ).magnitude
    x60_at_68 = saccharification_conversion(
        ureg.Quantity(60.0, "minute"), ureg.Quantity(68.0, "degC")
    ).magnitude
    assert x60_at_68 > x60_at_60


def test_extract_plato_definitional() -> None:
    """5 kg grain, 0.80 potential, 0.80 conversion, 20 L -> ~13.8 degPlato."""
    plato = extract_plato(
        ureg.Quantity(5.0, "kilogram"),
        ureg.Quantity(0.80, "dimensionless"),
        ureg.Quantity(0.80, "dimensionless"),
        ureg.Quantity(20.0, "liter"),
    ).magnitude
    # extract_g = 5000*0.8*0.8 = 3200 g; water=20000 g; plato=3200/23200*100
    assert plato == pytest.approx(3200.0 / 23200.0 * 100.0, rel=1e-6)
    assert 10.0 < plato < 18.0


def test_extract_plato_scales_with_conversion() -> None:
    """Higher conversion -> higher plato for same grain bill."""
    base = extract_plato(
        ureg.Quantity(5.0, "kilogram"),
        ureg.Quantity(0.80, "dimensionless"),
        ureg.Quantity(0.80, "dimensionless"),
        ureg.Quantity(20.0, "liter"),
    ).magnitude
    high = extract_plato(
        ureg.Quantity(5.0, "kilogram"),
        ureg.Quantity(0.80, "dimensionless"),
        ureg.Quantity(0.95, "dimensionless"),
        ureg.Quantity(20.0, "liter"),
    ).magnitude
    assert high > base


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
