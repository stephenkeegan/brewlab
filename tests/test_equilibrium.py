"""Equilibrium model validation tests.

Validates against published / definitional values:
    ionic strength        -> textbook definition
    alkalinity conversion -> ASBC bicarbonate -> CaCO3 equivalence
    residual alkalinity   -> brewing convention arithmetic
    carbonate system pH   -> pure water in equilibrium with atmospheric CO2
                          (expected pH ~ 5.6 at 25 C)
"""

from __future__ import annotations

import pytest

from brewlab.core.equilibrium import (
    alkalinity_as_caco3_from_bicarbonate,
    calcium_hardness_as_caco3,
    carbonate_system_ph,
    ionic_strength,
    magnesium_hardness_as_caco3,
    residual_alkalinity,
)
from brewlab.units import ureg


def test_ionic_strength_nacl() -> None:
    """0.01 M NaCl -> I = 0.01 M."""
    result = ionic_strength(
        {"Na": ureg.Quantity(0.01, "molar"), "Cl": ureg.Quantity(0.01, "molar")}
    )
    assert result.magnitude == pytest.approx(0.01, rel=1e-6)
    assert str(result.units) == "molar"


def test_ionic_strength_cacl2() -> None:
    """0.01 M CaCl2 -> I = 0.5*(0.01*4 + 0.02*1) = 0.03 M."""
    result = ionic_strength(
        {"Ca": ureg.Quantity(0.01, "molar"), "Cl": ureg.Quantity(0.02, "molar")}
    )
    assert result.magnitude == pytest.approx(0.03, rel=1e-6)


def test_ionic_strength_mixed() -> None:
    """Known mixed-ion value."""
    result = ionic_strength(
        {
            "Ca": ureg.Quantity(0.002, "molar"),
            "Mg": ureg.Quantity(0.001, "molar"),
            "Na": ureg.Quantity(0.01, "molar"),
            "Cl": ureg.Quantity(0.004 + 0.002 + 0.01, "molar"),
            "SO4": ureg.Quantity(0.002, "molar"),
            "HCO3": ureg.Quantity(0.003, "molar"),
        }
    )
    # 0.5*(0.002*4 + 0.001*4 + 0.01*1 + 0.016*1 + 0.002*4 + 0.003*1)
    expected = 0.5 * (0.008 + 0.004 + 0.01 + 0.016 + 0.008 + 0.003)
    assert result.magnitude == pytest.approx(expected, rel=1e-6)


def test_alkalinity_conversion_definitional() -> None:
    """61.0168 mg/L HCO3- (=1 mmol/L) -> 50.044 mg/L as CaCO3."""
    result = alkalinity_as_caco3_from_bicarbonate(ureg.Quantity(61.0168, "milligram / liter"))
    assert result.magnitude == pytest.approx(50.044, rel=1e-3)
    assert str(result.units) == "milligram / liter"


def test_alkalinity_conversion_gram_per_liter() -> None:
    """Unit conversion path works for gram/liter input."""
    result = alkalinity_as_caco3_from_bicarbonate(ureg.Quantity(0.0610168, "gram / liter"))
    assert result.magnitude == pytest.approx(50.044, rel=1e-3)


def test_calcium_hardness_as_caco3() -> None:
    """40.078 mg/L Ca (=1 mmol/L) -> 50.044 mg/L as CaCO3."""
    result = calcium_hardness_as_caco3(ureg.Quantity(40.078, "milligram / liter"))
    assert result.magnitude == pytest.approx(50.044, rel=1e-3)


def test_magnesium_hardness_as_caco3() -> None:
    """24.305 mg/L Mg (=1 mmol/L) -> 50.044 mg/L as CaCO3."""
    result = magnesium_hardness_as_caco3(ureg.Quantity(24.305, "milligram / liter"))
    assert result.magnitude == pytest.approx(50.044, rel=1e-3)


def test_residual_alkalinity_arithmetic() -> None:
    """RA = alkalinity - Ca_hardness - Mg_hardness (all as CaCO3)."""
    result = residual_alkalinity(
        ureg.Quantity(100.0, "milligram / liter"),
        ureg.Quantity(40.078, "milligram / liter"),  # -> 50.044 as CaCO3
        ureg.Quantity(24.305, "milligram / liter"),  # -> 50.044 as CaCO3
    )
    assert result.magnitude == pytest.approx(100.0 - 50.044 - 50.044, rel=1e-3)


def test_carbonate_ph_pure_water_atmospheric_co2() -> None:
    """Pure water equilibrated with atmospheric CO2 at 25 C -> pH ~ 5.6."""
    result = carbonate_system_ph(
        ureg.Quantity(0.0, "milligram / liter"),
        ureg.Quantity(25.0, "degC"),
        ureg.Quantity(0.0004, "atm"),
    )
    assert 5.3 < result.magnitude < 5.9


def test_carbonate_ph_higher_alkalinity_is_higher_ph() -> None:
    """Alkalinity raises predicted pH (buffering)."""
    ph_low = carbonate_system_ph(
        ureg.Quantity(10.0, "milligram / liter"),
        ureg.Quantity(25.0, "degC"),
        ureg.Quantity(0.0004, "atm"),
    ).magnitude
    ph_high = carbonate_system_ph(
        ureg.Quantity(200.0, "milligram / liter"),
        ureg.Quantity(25.0, "degC"),
        ureg.Quantity(0.0004, "atm"),
    ).magnitude
    assert ph_high > ph_low


def test_carbonate_ph_temperature_effect() -> None:
    """At fixed atmospheric pCO2, higher T -> less CO2 dissolved -> higher pH."""
    ph_25 = carbonate_system_ph(
        ureg.Quantity(0.0, "milligram / liter"),
        ureg.Quantity(25.0, "degC"),
        ureg.Quantity(0.0004, "atm"),
    ).magnitude
    ph_60 = carbonate_system_ph(
        ureg.Quantity(0.0, "milligram / liter"),
        ureg.Quantity(60.0, "degC"),
        ureg.Quantity(0.0004, "atm"),
    ).magnitude
    assert ph_60 > ph_25


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
