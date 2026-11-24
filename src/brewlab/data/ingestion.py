"""CSV / structured data ingestion (out of MVP)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class IngestionResult:
    source: str
    row_count: int
    parsed_at: datetime
    errors: list[str] = field(default_factory=list)


def ingest_csv(path: str) -> IngestionResult:
    raise NotImplementedError("CSV ingestion not implemented in MVP")


__all__ = ["IngestionResult", "ingest_csv"]
