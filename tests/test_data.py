"""Data integration validation tests (Phase 5).

Validates CSV ingestion of measurements into domain Measurement objects and
linear calibration.
"""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from brewlab.data.ingestion import IngestionResult, ingest_measurements_csv
from brewlab.data.measurement import calibrate_measurement
from brewlab.domain.batch import Measurement
from brewlab.units import ureg


def test_ingest_measurements_csv_basic() -> None:
    csv_text = (
        "name,value,unit,timestamp,stage,instrument,uncertainty\n"
        "mash_temp,65.0,degC,2026-11-24T10:00:00Z,mash,thermometer,0.5\n"
        "ph,5.3,dimensionless,2026-11-24T10:05:00Z,mash,pH meter,\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as fh:
        fh.write(csv_text)
        path = fh.name
    try:
        result = ingest_measurements_csv(path)
    finally:
        Path(path).unlink()

    assert isinstance(result, IngestionResult)
    assert result.row_count == 2
    assert len(result.measurements) == 2
    assert len(result.errors) == 0

    m1 = result.measurements[0]
    assert m1.name == "mash_temp"
    assert m1.value.magnitude == pytest.approx(65.0)
    assert m1.value.check("degC")
    assert m1.stage == "mash"
    assert m1.instrument == "thermometer"
    assert m1.uncertainty.magnitude == pytest.approx(0.5)
    assert m1.timestamp.tzinfo is not None

    m2 = result.measurements[1]
    assert m2.name == "ph"
    assert m2.value.magnitude == pytest.approx(5.3)
    assert str(m2.value.units) == "dimensionless"


def test_ingest_csv_skips_bad_rows_continues() -> None:
    csv_text = (
        "name,value,unit,timestamp,stage,instrument,uncertainty\n"
        "good,10.0,degC,2026-11-24T10:00:00Z,,,\n"
        "bad,not_a_number,degC,2026-11-24T10:01:00Z,,,\n"
        "also_good,20.0,degLovibond,2026-11-24T10:02:00Z,boil,spectro,\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as fh:
        fh.write(csv_text)
        path = fh.name
    try:
        result = ingest_measurements_csv(path)
    finally:
        Path(path).unlink()

    assert result.row_count == 3
    assert len(result.measurements) == 2
    assert len(result.errors) == 1
    assert "line 3" in result.errors[0]
    assert result.measurements[1].name == "also_good"


def test_calibrate_measurement_preserves_raw() -> None:
    raw = Measurement(
        name="ph",
        value=ureg.Quantity(5.3, "dimensionless"),
        timestamp=datetime(2026, 11, 24, 10, 0, tzinfo=UTC),
        stage="mash",
        instrument="pH meter",
    )
    cal = calibrate_measurement(
        raw,
        offset=ureg.Quantity(0.1, "dimensionless"),
        slope=ureg.Quantity(1.0, "dimensionless"),
        note="offset correction",
    )
    # Raw untouched
    assert raw.value.magnitude == pytest.approx(5.3)
    assert raw.calibrated_at is None
    # Calibrated value adjusted
    assert cal.value.magnitude == pytest.approx(5.4)
    assert cal.calibrated_at is not None
    assert "calibrated" in cal.instrument


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
