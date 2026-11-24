"""Process stages: MashStage, BoilStage base classes (Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass, field

from brewlab.units import Quantity


@dataclass
class MashStage:
    name: str = "mash"
    rest_temperatures: list[Quantity] = field(default_factory=list)  # degC
    rest_durations: list[Quantity] = field(default_factory=list)  # minutes
    water_to_grain_ratio: Quantity = Quantity(3, "liter / kilogram")
    mash_thickness: Quantity | None = None
    outputs: dict[str, Quantity] = field(default_factory=dict)


@dataclass
class BoilStage:
    name: str = "boil"
    duration: Quantity = Quantity(60, "minute")
    boil_off_rate: Quantity = Quantity(4, "liter / hour")
    start_volume: Quantity | None = None  # liter
    end_volume: Quantity | None = None  # liter
    outputs: dict[str, Quantity] = field(default_factory=dict)


__all__ = ["MashStage", "BoilStage"]
