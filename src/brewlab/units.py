"""Unit handling and dimensional analysis.

Single source of units for the scientific core. All models import this
module's ``ureg`` (singleton registry) and ``Quantity`` (pint type, usable in
type annotations). Runtime quantities are created through ``ureg.Quantity`` so
they are bound to the singleton registry.

Brewing-specific unit aliases registered on ``ureg``:
    degPlato       - extract concentration (°Plato); SG<->Plato uses an
                     empirical ASBC relation, not a native pint conversion.
    degLovibond    - color (°Lovibond); dimensionless.
    IBU            - International Bitterness Units; dimensionless.
    ppm_as_CaCO3   - alkalinity/hardness expressed as ppm CaCO3.
    gpl            - grams per liter.
    point          - gravity point (specific gravity 1.001 = 1 point).
"""

from __future__ import annotations

from pint import Quantity, UnitRegistry

ureg = UnitRegistry()

# Dimensionless brewing unit aliases (SG<->Plato handled empirically, not natively)
ureg.define("degPlato = dimensionless")
ureg.define("degLovibond = dimensionless")
ureg.define("IBU = dimensionless")
ureg.define("ppm_as_CaCO3 = milligram / kilogram")
ureg.define("gpl = gram / liter")
ureg.define("point = 0.001 * dimensionless")

__all__ = ["ureg", "Quantity"]
