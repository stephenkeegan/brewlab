"""Measurement calibration helpers (Phase 5).

Operates on domain ``Measurement`` objects (canonical model lives in
``brewlab.domain.batch``). Returns *new* calibrated measurements so the raw
value is preserved for provenance, with calibration metadata attached.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from brewlab.domain.batch import Measurement
from brewlab.units import Quantity, ureg


def calibrate_measurement(
    measurement: Measurement,
    offset: Quantity,
    slope: Quantity = ureg.Quantity(1.0, "dimensionless"),
    calibrated_at: datetime | None = None,
    note: str | None = None,
) -> Measurement:
    """Apply a linear calibration: calibrated = slope * raw + offset.

    The returned measurement carries the calibrated value and a
    ``calibrated_at`` timestamp; the original measurement is left untouched
    for provenance.

    Parameters
    ----------
    measurement : Measurement
        Raw measurement to calibrate.
    offset : Quantity
        Offset (same units as measurement value).
    slope : Quantity
        Multiplicative slope (dimensionless).
    calibrated_at : datetime, optional
        Calibration timestamp; defaults to now (UTC).
    note : str, optional
        Free-text calibration note.

    Returns
    -------
    Measurement
        Calibrated measurement (original preserved via provenance note).
    """
    raw_value = measurement.value.to(offset.units).magnitude
    calibrated_value = (
        slope.to("dimensionless").magnitude * raw_value + offset.to(offset.units).magnitude
    )
    calibrated = ureg.Quantity(calibrated_value, offset.units)

    provenance = f"calibrated: slope={slope.magnitude}, offset={offset.magnitude} {offset.units}"
    if note:
        provenance += f"; {note}"

    return replace(
        measurement,
        value=calibrated,
        calibrated_at=calibrated_at or datetime.now(UTC),
        instrument=(measurement.instrument or "") + " | " + provenance,
    )


__all__ = ["calibrate_measurement"]
