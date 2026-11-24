"""Simulation engine: time-stepping orchestrator (out of MVP)."""

from __future__ import annotations

from dataclasses import dataclass, field

from brewlab.simulation.state import SimulationState


@dataclass
class Engine:
    state: SimulationState = field(default_factory=SimulationState)

    def step(self, dt: float) -> SimulationState:
        raise NotImplementedError("Engine.step not implemented in MVP")


__all__ = ["Engine", "SimulationState"]
