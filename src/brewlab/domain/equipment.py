"""Equipment: vessel geometry, dead space, boil-off rate, efficiency."""

from __future__ import annotations

from dataclasses import dataclass

from brewlab.units import Quantity


@dataclass
class Equipment:
    name: str
    vessel_volume: Quantity  # liter
    dead_space: Quantity = Quantity(0, "liter")  # liter
    boil_off_rate: Quantity = Quantity(4, "liter / hour")  # liter/hour
    efficiency: Quantity = Quantity(0.75, "dimensionless")  # brewhouse efficiency
    loss_to_trub: Quantity = Quantity(2, "liter")  # liter


__all__ = ["Equipment"]
