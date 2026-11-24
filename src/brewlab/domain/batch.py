"""Batches: Batch, ProcessStage, Measurement."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from brewlab.domain.equipment import Equipment
from brewlab.domain.recipe import Recipe
from brewlab.units import Quantity


@dataclass
class ProcessStage:
    name: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    temperature_profile: list[tuple[datetime, Quantity]] = field(default_factory=list)
    parameters: dict[str, Quantity] = field(default_factory=dict)
    outputs: dict[str, Quantity] = field(default_factory=dict)


@dataclass
class Measurement:
    name: str
    value: Quantity
    timestamp: datetime
    stage: str | None = None
    instrument: str | None = None
    uncertainty: Quantity | None = None
    calibrated_at: datetime | None = None


@dataclass
class Batch:
    id: str
    recipe: Recipe
    equipment: Equipment
    stages: list[ProcessStage] = field(default_factory=list)
    measurements: list[Measurement] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


__all__ = ["Batch", "ProcessStage", "Measurement"]
