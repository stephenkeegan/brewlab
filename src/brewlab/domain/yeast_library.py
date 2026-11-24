"""Yeast strain library (Phase 9).

Curated brewing yeast strains with attenuation ranges, fermentation
temperature ranges, flocculation, species, alcohol tolerance, and flavor
notes. Data is sourced from brewing supplier references (White Labs,
Wyeast, Fermentis, Lallemand, Omega) and brewing literature — NOT from
SGD, which carries no brewing phenotypes.

Used by the GUI strain selector and by the fermentation engine to clamp
predicted attenuation to each strain's achievable range.
"""

from __future__ import annotations

from brewlab.domain.ingredient import Yeast
from brewlab.units import ureg

_STRAINS: dict[str, Yeast] = {
    "US-05": Yeast(
        strain_id="US-05",
        attenuation_min=ureg.Quantity(0.73, "dimensionless"),
        attenuation_max=ureg.Quantity(0.80, "dimensionless"),
        flocculation="medium",
        temperature_min=ureg.Quantity(18.0, "degC"),
        temperature_max=ureg.Quantity(22.0, "degC"),
        species="cerevisiae",
        alcohol_tolerance=ureg.Quantity(11.0, "percent"),
        flavor_notes="clean, neutral",
    ),
    "WLP001": Yeast(
        strain_id="WLP001",
        attenuation_min=ureg.Quantity(0.73, "dimensionless"),
        attenuation_max=ureg.Quantity(0.80, "dimensionless"),
        flocculation="medium",
        temperature_min=ureg.Quantity(18.0, "degC"),
        temperature_max=ureg.Quantity(22.0, "degC"),
        species="cerevisiae",
        alcohol_tolerance=ureg.Quantity(11.0, "percent"),
        flavor_notes="clean, neutral",
    ),
    "Wyeast 1056": Yeast(
        strain_id="Wyeast 1056",
        attenuation_min=ureg.Quantity(0.73, "dimensionless"),
        attenuation_max=ureg.Quantity(0.80, "dimensionless"),
        flocculation="medium",
        temperature_min=ureg.Quantity(18.0, "degC"),
        temperature_max=ureg.Quantity(22.0, "degC"),
        species="cerevisiae",
        alcohol_tolerance=ureg.Quantity(11.0, "percent"),
        flavor_notes="clean, neutral",
    ),
    "W-34/74": Yeast(
        strain_id="W-34/74",
        attenuation_min=ureg.Quantity(0.78, "dimensionless"),
        attenuation_max=ureg.Quantity(0.85, "dimensionless"),
        flocculation="high",
        temperature_min=ureg.Quantity(9.0, "degC"),
        temperature_max=ureg.Quantity(15.0, "degC"),
        species="pastorianus",
        alcohol_tolerance=ureg.Quantity(10.0, "percent"),
        flavor_notes="clean, crisp lager",
    ),
    "S-23": Yeast(
        strain_id="S-23",
        attenuation_min=ureg.Quantity(0.75, "dimensionless"),
        attenuation_max=ureg.Quantity(0.82, "dimensionless"),
        flocculation="medium",
        temperature_min=ureg.Quantity(9.0, "degC"),
        temperature_max=ureg.Quantity(15.0, "degC"),
        species="pastorianus",
        alcohol_tolerance=ureg.Quantity(10.0, "percent"),
        flavor_notes="clean, slightly malty",
    ),
    "S-04": Yeast(
        strain_id="S-04",
        attenuation_min=ureg.Quantity(0.68, "dimensionless"),
        attenuation_max=ureg.Quantity(0.75, "dimensionless"),
        flocculation="high",
        temperature_min=ureg.Quantity(14.0, "degC"),
        temperature_max=ureg.Quantity(20.0, "degC"),
        species="cerevisiae",
        alcohol_tolerance=ureg.Quantity(9.0, "percent"),
        flavor_notes="fruity, full-bodied English ale",
    ),
    "London Ale III": Yeast(
        strain_id="London Ale III",
        attenuation_min=ureg.Quantity(0.68, "dimensionless"),
        attenuation_max=ureg.Quantity(0.75, "dimensionless"),
        flocculation="medium",
        temperature_min=ureg.Quantity(18.0, "degC"),
        temperature_max=ureg.Quantity(22.0, "degC"),
        species="cerevisiae",
        alcohol_tolerance=ureg.Quantity(10.0, "percent"),
        flavor_notes="malty, slightly sweet, enhances body",
    ),
    "Belgian Ale": Yeast(
        strain_id="Belgian Ale",
        attenuation_min=ureg.Quantity(0.75, "dimensionless"),
        attenuation_max=ureg.Quantity(0.85, "dimensionless"),
        flocculation="low",
        temperature_min=ureg.Quantity(20.0, "degC"),
        temperature_max=ureg.Quantity(28.0, "degC"),
        species="cerevisiae",
        alcohol_tolerance=ureg.Quantity(12.0, "percent"),
        flavor_notes="spicy phenolics, fruity esters",
    ),
    "Hefeweizen": Yeast(
        strain_id="Hefeweizen",
        attenuation_min=ureg.Quantity(0.70, "dimensionless"),
        attenuation_max=ureg.Quantity(0.75, "dimensionless"),
        flocculation="low",
        temperature_min=ureg.Quantity(18.0, "degC"),
        temperature_max=ureg.Quantity(24.0, "degC"),
        species="cerevisiae",
        alcohol_tolerance=ureg.Quantity(10.0, "percent"),
        flavor_notes="banana, clove esters",
    ),
    "Kveik": Yeast(
        strain_id="Kveik",
        attenuation_min=ureg.Quantity(0.80, "dimensionless"),
        attenuation_max=ureg.Quantity(0.90, "dimensionless"),
        flocculation="medium",
        temperature_min=ureg.Quantity(30.0, "degC"),
        temperature_max=ureg.Quantity(40.0, "degC"),
        species="cerevisiae",
        alcohol_tolerance=ureg.Quantity(13.0, "percent"),
        flavor_notes="tropical fruit, orange, pineapple",
    ),
}


class YeastLibrary:
    """In-memory library of curated brewing yeast strains."""

    def __init__(self) -> None:
        self._strains = dict(_STRAINS)

    def get(self, strain_id: str) -> Yeast | None:
        """Return the strain for ``strain_id``, or ``None`` if unknown."""
        return self._strains.get(strain_id)

    def ids(self) -> list[str]:
        """Return all strain ids in the library."""
        return sorted(self._strains.keys())

    def by_species(self, species: str) -> list[Yeast]:
        """Return strains matching ``species`` (``cerevisiae`` or ``pastorianus``)."""
        return [s for s in self._strains.values() if s.species == species]

    def default(self) -> Yeast:
        """Return the default strain (US-05)."""
        return self._strains["US-05"]


__all__ = ["YeastLibrary", "_STRAINS"]
