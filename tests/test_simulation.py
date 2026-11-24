"""Coupled simulation engine validation tests.

Validates stage chaining (mash -> boil -> ferment) and summary aggregation.
"""

from __future__ import annotations

import pytest

from brewlab.simulation.engine import CoupledSimulationResult, simulate_batch

_RECIPE = {
    "name": "Test Pale Ale",
    "grain_mass_kg": 5.0,
    "extract_potential": 0.80,
    "water_to_grain_ratio_l_per_kg": 3.0,
    "grain_temperature_degC": 20.0,
    "target_mash_temperature_degC": 65.0,
    "mash_duration_minutes": 60.0,
    "batch_size_liters": 20.0,
    "water": {
        "calcium_mg_per_l": 50.0,
        "magnesium_mg_per_l": 10.0,
        "bicarbonate_mg_per_l": 150.0,
    },
    "boil": {
        "pre_boil_volume_liters": 26.0,
        "boil_off_rate_l_per_hr": 4.0,
        "boil_duration_minutes": 60.0,
        "hops": [
            {"amount_kg": 0.06, "alpha_acid": 0.055, "time_minutes": 60},
            {"amount_kg": 0.03, "alpha_acid": 0.055, "time_minutes": 15},
        ],
    },
    "ferment": {
        "temperature_degC": 20.0,
        "duration_hours": 72.0,
    },
}


def test_simulate_batch_returns_result() -> None:
    result = simulate_batch(_RECIPE)
    assert isinstance(result, CoupledSimulationResult)
    d = result.as_dict()
    assert set(d.keys()) == {"mash", "boil", "ferment", "summary"}


def test_mash_stage_present() -> None:
    result = simulate_batch(_RECIPE)
    m = result.mash
    assert "strike_water_temperature_degC" in m
    assert "pre_boil_plato" in m
    assert m["strike_water_temperature_degC"] > m["target_mash_temperature_degC"]


def test_boil_stage_present() -> None:
    result = simulate_batch(_RECIPE)
    b = result.boil
    assert b["post_boil_volume_liters"] < b["pre_boil_volume_liters"]
    assert b["post_boil_plato"] > b["pre_boil_plato"]
    assert b["total_ibu"] > 0.0
    assert len(b["hop_additions"]) == 2


def test_ferment_stage_present() -> None:
    result = simulate_batch(_RECIPE)
    f = result.ferment
    assert 0.0 <= f["final_attenuation"] <= 1.0
    assert f["final_abv_percent"] > 0.0
    assert f["final_fg_plato"] >= 0.0


def test_summary_aggregation() -> None:
    result = simulate_batch(_RECIPE)
    s = result.summary
    assert s["og_plato"] == result.mash["pre_boil_plato"]
    assert s["fg_plato"] == result.ferment["final_fg_plato"]
    assert s["ibu"] == result.boil["total_ibu"]
    assert s["name"] == "Test Pale Ale"


def test_equipment_override() -> None:
    recipe = dict(_RECIPE)
    equipment = {"vessel_volume_liters": 30.0, "boil_off_rate_l_per_hr": 6.0}
    result = simulate_batch(recipe, equipment)
    assert result.boil["pre_boil_volume_liters"] == 30.0
    assert result.boil["boil_off_rate_l_per_hr"] == 6.0


def test_deterministic() -> None:
    a = simulate_batch(_RECIPE).as_dict()
    b = simulate_batch(_RECIPE).as_dict()
    assert a == b


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
