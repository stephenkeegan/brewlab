"""Fermentation model validation tests.

Validates physical bounds and structure (parameters are calibration targets,
so exact literature values are asserted only where definitional):
    monod_growth_rate    -> zero at S=0, monotonic in S, max at Topt,
                            bounded [0, mu_max]
    fermentation_time_series -> sugar non-increasing, ethanol/CO2 non-decreasing,
                                attenuation in [0,1], CO2 = ethanol * 88/92,
                                deterministic
"""

from __future__ import annotations

import pytest

from brewlab.core.fermentation import (
    fermentation_time_series,
    monod_growth_rate,
)
from brewlab.units import ureg

_INITIAL_SUGAR = ureg.Quantity(100.0, "gram / liter")
_INITIAL_YEAST = ureg.Quantity(0.1, "gram / liter")
_VOLUME = ureg.Quantity(20.0, "liter")
_TEMP = ureg.Quantity(20.0, "degC")
_DURATION = ureg.Quantity(72.0, "hour")


def test_monod_zero_at_zero_substrate() -> None:
    """No sugar -> no growth."""
    result = monod_growth_rate(
        ureg.Quantity(0.4, "1 / hour"),
        ureg.Quantity(2.0, "gram / liter"),
        ureg.Quantity(0.0, "gram / liter"),
        _TEMP,
    )
    assert result.magnitude == pytest.approx(0.0, abs=1e-12)


def test_monod_monotonic_in_substrate() -> None:
    """Growth rate increases with substrate (toward mu_max)."""
    low = monod_growth_rate(
        ureg.Quantity(0.4, "1 / hour"),
        ureg.Quantity(2.0, "gram / liter"),
        ureg.Quantity(1.0, "gram / liter"),
        _TEMP,
    ).magnitude
    high = monod_growth_rate(
        ureg.Quantity(0.4, "1 / hour"),
        ureg.Quantity(2.0, "gram / liter"),
        ureg.Quantity(100.0, "gram / liter"),
        _TEMP,
    ).magnitude
    assert 0.0 < low < high


def test_monod_max_at_topt() -> None:
    """Temperature factor maximal at Topt (20 C default)."""
    at_topt = monod_growth_rate(
        ureg.Quantity(0.4, "1 / hour"),
        ureg.Quantity(2.0, "gram / liter"),
        ureg.Quantity(100.0, "gram / liter"),
        ureg.Quantity(20.0, "degC"),
    ).magnitude
    off_topt = monod_growth_rate(
        ureg.Quantity(0.4, "1 / hour"),
        ureg.Quantity(2.0, "gram / liter"),
        ureg.Quantity(100.0, "gram / liter"),
        ureg.Quantity(5.0, "degC"),
    ).magnitude
    assert 0.0 < off_topt < at_topt <= 0.4


def test_fermentation_sugar_non_increasing() -> None:
    """Residual sugar never increases over the batch."""
    result = fermentation_time_series(_INITIAL_SUGAR, _INITIAL_YEAST, _VOLUME, _TEMP, _DURATION)
    s = result["sugar_g_per_L"]
    assert all(s[i + 1] <= s[i] + 1e-9 for i in range(len(s) - 1))


def test_fermentation_ethanol_and_co2_non_decreasing() -> None:
    """Ethanol and CO2 never decrease over the batch."""
    result = fermentation_time_series(_INITIAL_SUGAR, _INITIAL_YEAST, _VOLUME, _TEMP, _DURATION)
    p = result["ethanol_g_per_L"]
    c = result["co2_g_per_L"]
    assert all(p[i + 1] >= p[i] - 1e-9 for i in range(len(p) - 1))
    assert all(c[i + 1] >= c[i] - 1e-9 for i in range(len(c) - 1))


def test_fermentation_attenuation_bounded() -> None:
    """Attenuation is a fraction in [0, 1]."""
    result = fermentation_time_series(_INITIAL_SUGAR, _INITIAL_YEAST, _VOLUME, _TEMP, _DURATION)
    assert 0.0 <= result["final_attenuation"] <= 1.0


def test_fermentation_co2_stoichiometry() -> None:
    """CO2 mass = ethanol mass * 88/92 (stoichiometric)."""
    result = fermentation_time_series(_INITIAL_SUGAR, _INITIAL_YEAST, _VOLUME, _TEMP, _DURATION)
    p = result["ethanol_g_per_L"][-1]
    c = result["co2_g_per_L"][-1]
    if p > 0:
        assert c == pytest.approx(p * (88.0 / 92.0), rel=1e-6)


def test_fermentation_produces_ethanol() -> None:
    """A normal batch produces positive ethanol."""
    result = fermentation_time_series(_INITIAL_SUGAR, _INITIAL_YEAST, _VOLUME, _TEMP, _DURATION)
    assert result["final_ethanol_g_per_L"] > 0.0


def test_fermentation_deterministic() -> None:
    """Same inputs produce identical outputs."""
    a = fermentation_time_series(_INITIAL_SUGAR, _INITIAL_YEAST, _VOLUME, _TEMP, _DURATION)
    b = fermentation_time_series(_INITIAL_SUGAR, _INITIAL_YEAST, _VOLUME, _TEMP, _DURATION)
    assert a["final_ethanol_g_per_L"] == b["final_ethanol_g_per_L"]
    assert a["final_attenuation"] == b["final_attenuation"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
