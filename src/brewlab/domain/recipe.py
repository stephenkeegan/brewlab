"""Recipes: Recipe, Fermentable, HopAddition."""

from __future__ import annotations

from dataclasses import dataclass, field

from brewlab.domain.ingredient import Hop, Malt, Yeast
from brewlab.units import Quantity


@dataclass
class Fermentable:
    malt: Malt
    amount: Quantity  # mass


@dataclass
class HopAddition:
    hop: Hop
    amount: Quantity  # mass
    time_min: Quantity  # minutes (boil time remaining)
    use: str  # bittering/flavor/aroma


@dataclass
class Recipe:
    name: str
    fermentables: list[Fermentable] = field(default_factory=list)
    hops: list[HopAddition] = field(default_factory=list)
    yeast: Yeast | None = None
    target_og: Quantity | None = None  # specific gravity
    target_fg: Quantity | None = None  # specific gravity
    target_ibu: Quantity | None = None  # IBU
    target_srm: Quantity | None = None  # degLovibond
    target_abv: Quantity | None = None  # percent
    batch_size: Quantity = Quantity(20, "liter")


__all__ = ["Fermentable", "HopAddition", "Recipe"]
