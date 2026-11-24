"""Persistence layer: abstract Repository (out of MVP)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class Repository(ABC, Generic[T]):
    """Abstract repository for aggregates (Recipe, Batch, SimulationResult)."""

    @abstractmethod
    def add(self, item: T) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, id: str) -> T | None:
        raise NotImplementedError

    @abstractmethod
    def list(self) -> list[T]:
        raise NotImplementedError


__all__ = ["Repository", "T"]
