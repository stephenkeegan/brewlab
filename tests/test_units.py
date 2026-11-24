"""Unit handling tests for brewlab.units.

Verifies the single pint registry, brewing unit aliases, and that
quantities carry explicit units across boundaries.
"""

from __future__ import annotations

import pint.errors
import pytest

from brewlab.units import ureg
from brewlab.units import ureg as ureg_second


def test_registry_is_singleton() -> None:
    assert ureg is ureg_second


def test_quantity_carries_units() -> None:
    mass = ureg.Quantity(5.0, "kilogram")
    assert mass.magnitude == 5.0
    assert str(mass.units) == "kilogram"


def test_brewing_alias_deg_plato() -> None:
    plato = ureg.Quantity(12.0, "degPlato")
    assert plato.magnitude == 12.0
    assert str(plato.units) == "degPlato"


def test_brewing_alias_ibu() -> None:
    ibu = ureg.Quantity(45.0, "IBU")
    assert ibu.magnitude == 45.0
    assert str(ibu.units) == "IBU"


def test_brewing_alias_ppm_as_caco3() -> None:
    alk = ureg.Quantity(50.0, "ppm_as_CaCO3")
    assert alk.magnitude == 50.0
    assert str(alk.units) == "ppm_as_CaCO3"


def test_brewing_alias_point() -> None:
    pt = ureg.Quantity(4.0, "point")
    assert pt.magnitude == 4.0
    assert str(pt.units) == "point"


def test_conversion_preserves_units() -> None:
    mass_kg = ureg.Quantity(1.0, "kilogram")
    mass_g = mass_kg.to("gram")
    assert mass_g.magnitude == 1000.0
    assert str(mass_g.units) == "gram"


def test_dimensionless_incompatible_conversion_raises() -> None:
    plato = ureg.Quantity(12.0, "degPlato")
    with pytest.raises(pint.errors.DimensionalityError):
        plato.to("kilogram")


def test_temperature_quantity() -> None:
    temp = ureg.Quantity(65.0, "degC")
    kelvin = temp.to("kelvin")
    assert abs(kelvin.magnitude - 338.15) < 1e-6


def test_volume_quantity() -> None:
    vol = ureg.Quantity(20.0, "liter")
    ml = vol.to("milliliter")
    assert ml.magnitude == 20000.0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
