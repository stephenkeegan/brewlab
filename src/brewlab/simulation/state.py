"""SimulationState shared state container (out of MVP)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SimulationState:
    time: float = 0.0
    temperature: float | None = None
    volume: float | None = None
    gravity: float | None = None
    ph: float | None = None
    variables: dict[str, float] = field(default_factory=dict)


__all__ = ["SimulationState"]
