"""CSV / structured data ingestion (Phase 5).

Parses measurement CSV files into domain ``Measurement`` objects with
timestamped, unit-checked values and full provenance (instrument, stage,
uncertainty).

Expected CSV columns:
    name, value, unit, timestamp, stage, instrument, uncertainty

``timestamp`` accepts ISO-8601 (e.g. 2026-11-24T01:20:00Z). ``unit`` must be a
pint-parseable unit string. ``uncertainty`` is optional.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import UTC, datetime

from brewlab.domain.batch import Measurement
from brewlab.units import ureg


@dataclass
class IngestionResult:
    source: str
    row_count: int
    parsed_at: datetime
    measurements: list[Measurement] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _parse_timestamp(value: str) -> datetime:
    text = value.strip()
    # Accept trailing Z or explicit offset; fall back to naive->UTC.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def ingest_measurements_csv(path: str) -> IngestionResult:
    """Ingest a CSV of measurements into domain Measurement objects.

    Parameters
    ----------
    path : str
        Path to the CSV file.

    Returns
    -------
    IngestionResult
        Parsed measurements plus any per-row errors. Rows with errors are
        skipped; ingestion continues for valid rows.
    """
    measurements: list[Measurement] = []
    errors: list[str] = []
    row_count = 0

    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for lineno, row in enumerate(reader, start=2):
            row_count += 1
            try:
                name = (row.get("name") or "").strip()
                if not name:
                    raise ValueError("missing name")
                value = float(row["value"])
                unit = (row.get("unit") or "dimensionless").strip()
                quantity = ureg.Quantity(value, unit)
                timestamp = _parse_timestamp(row.get("timestamp", ""))
                stage = (row.get("stage") or "").strip() or None
                instrument = (row.get("instrument") or "").strip() or None
                uncertainty = None
                if row.get("uncertainty"):
                    uncertainty = ureg.Quantity(float(row["uncertainty"]), unit)
                measurements.append(
                    Measurement(
                        name=name,
                        value=quantity,
                        timestamp=timestamp,
                        stage=stage,
                        instrument=instrument,
                        uncertainty=uncertainty,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - report per-row, continue
                errors.append(f"line {lineno}: {exc}")

    return IngestionResult(
        source=path,
        row_count=row_count,
        parsed_at=datetime.now(UTC),
        measurements=measurements,
        errors=errors,
    )


__all__ = ["IngestionResult", "ingest_measurements_csv"]
