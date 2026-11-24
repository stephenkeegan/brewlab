"""Boil model validation tests.

Validates:
    boil_off_volume       -> linear decrease, clamped at zero
    wort_plato_after_boil -> extract-mass conservation (Plato rises as
                             volume falls; zero boil-off -> unchanged Plato)
    plato<->SG            -> round trip, and known reference points
"""

from __future__ import annotations

import pytest

from brewlab.core.boil import (
    boil_off_volume,
    plato_to_specific_gravity,
    specific_gravity_to_plato,
    wort_plato_after_boil,
)
from brewlab.units import ureg


def test_boil_off_volume_linear() -> None:
    """20 L at 4 L/hr for 1 hr -> 16 L."""
    result = boil_off_volume(
        ureg.Quantity(20.0, "liter"),
        ureg.Quantity(4.0, "liter / hour"),
        ureg.Quantity(1.0, "hour"),
    )
    assert result.magnitude == pytest.approx(16.0)
    assert str(result.units) == "liter"


def test_boil_off_volume_clamped_at_zero() -> None:
    """Cannot boil off more than the starting volume."""
    result = boil_off_volume(
        ureg.Quantity(5.0, "liter"),
        ureg.Quantity(10.0, "liter / hour"),
        ureg.Quantity(1.0, "hour"),
    )
    assert result.magnitude == pytest.approx(0.0)


def test_boil_off_zero_time() -> None:
    """Zero time -> unchanged volume."""
    result = boil_off_volume(
        ureg.Quantity(20.0, "liter"),
        ureg.Quantity(4.0, "liter / hour"),
        ureg.Quantity(0.0, "hour"),
    )
    assert result.magnitude == pytest.approx(20.0)


def test_wort_plato_zero_boil_off_unchanged() -> None:
    """No boil-off -> Plato stays the same."""
    result = wort_plato_after_boil(
        ureg.Quantity(12.0, "degPlato"),
        ureg.Quantity(20.0, "liter"),
        ureg.Quantity(4.0, "liter / hour"),
        ureg.Quantity(0.0, "hour"),
    )
    assert result.magnitude == pytest.approx(12.0, abs=1e-6)


def test_wort_plato_rises_as_volume_falls() -> None:
    """Boiling off water concentrates the wort (Plato rises)."""
    base = wort_plato_after_boil(
        ureg.Quantity(10.0, "degPlato"),
        ureg.Quantity(20.0, "liter"),
        ureg.Quantity(4.0, "liter / hour"),
        ureg.Quantity(0.0, "hour"),
    ).magnitude
    high = wort_plato_after_boil(
        ureg.Quantity(10.0, "degPlato"),
        ureg.Quantity(20.0, "liter"),
        ureg.Quantity(4.0, "liter / hour"),
        ureg.Quantity(1.0, "hour"),
    ).magnitude
    assert high > base


def test_wort_plato_mass_balance() -> None:
    """Manual mass-balance check for a 10 Plato, 20 L wort boiled 1 hr."""
    # p0=0.10, water=20000 g, extract = 0.10*20000/0.90 = 2222.2 g
    # after 1 hr: volume=16 L, water=16000 g
    # plato = 2222.2 / (16000+2222.2) * 100 = 12.20
    result = wort_plato_after_boil(
        ureg.Quantity(10.0, "degPlato"),
        ureg.Quantity(20.0, "liter"),
        ureg.Quantity(4.0, "liter / hour"),
        ureg.Quantity(1.0, "hour"),
    )
    expected = 2222.2222 / (16000.0 + 2222.2222) * 100.0
    assert result.magnitude == pytest.approx(expected, rel=1e-2)


def test_plato_to_sg_known_point() -> None:
    """10 degPlato -> SG ~1.040 (standard reference)."""
    result = plato_to_specific_gravity(ureg.Quantity(10.0, "degPlato"))
    assert 1.038 < result.magnitude < 1.042


def test_sg_to_plato_round_trip() -> None:
    """Plato -> SG -> Plato round trip."""
    original = ureg.Quantity(12.5, "degPlato")
    sg = plato_to_specific_gravity(original)
    back = specific_gravity_to_plato(sg)
    assert back.magnitude == pytest.approx(original.magnitude, rel=1e-3)


def test_sg_to_plato_zero() -> None:
    """SG 1.0 -> 0 Plato."""
    result = specific_gravity_to_plato(ureg.Quantity(1.0, "dimensionless"))
    assert result.magnitude == pytest.approx(0.0)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
