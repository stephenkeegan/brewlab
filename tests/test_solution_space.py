"""Solution space tests (Phase 9).

Validates that range parameters are sampled within bounds, yeast list
sampling works, n_samples is respected, and scalar-only recipes still run.
"""

from __future__ import annotations

import pytest

from brewlab.simulation.solution_space import explore_solution_space

_BASE_RECIPE = {
    "name": "Solution Space Test",
    "grain_mass_kg": {"min": 5.0, "max": 7.0},
    "extract_potential": {"min": 0.75, "max": 0.85},
    "target_mash_temperature_degC": {"min": 63.0, "max": 67.0},
    "water_to_grain_ratio_l_per_kg": 3.0,
    "grain_temperature_degC": 20.0,
    "mash_duration_minutes": 60.0,
    "batch_size_liters": 20.0,
    "grain_color_lovibond": 3.0,
    "water": {
        "calcium_mg_per_l": 50.0,
        "magnesium_mg_per_l": 10.0,
        "bicarbonate_mg_per_l": 150.0,
        "chloride_mg_per_l": 50.0,
        "sulfate_mg_per_l": 50.0,
    },
    "boil": {
        "pre_boil_volume_liters": 26.0,
        "boil_off_rate_l_per_hr": 4.0,
        "boil_duration_minutes": 60.0,
        "hops": [
            {"amount_kg": {"min": 0.04, "max": 0.08}, "alpha_acid": 0.060, "time_minutes": 60},
            {"amount_kg": 0.02, "alpha_acid": 0.060, "time_minutes": 5},
        ],
    },
    "ferment": {
        "temperature_degC": {"min": 18.0, "max": 22.0},
        "duration_hours": 72.0,
        "initial_yeast_g_per_l": 0.1,
        "volume_liters": 20.0,
        "yeast_strain_id": ["US-05", "W-34/74", "S-04"],
    },
}


def test_solution_space_returns_stats() -> None:
    solution = explore_solution_space(_BASE_RECIPE, n_samples=40, seed=7)
    assert solution["n_samples"] > 0
    assert solution["n_samples"] <= solution["requested_samples"]
    assert "stats" in solution
    assert "samples" in solution


def test_output_stats_within_bounds() -> None:
    solution = explore_solution_space(_BASE_RECIPE, n_samples=40, seed=7)
    stats = solution["stats"]
    for key in ("og_plato", "fg_plato", "abv_percent", "ibu", "srm", "attenuation"):
        stat = stats[key]
        assert stat["min"] is not None
        assert stat["max"] is not None
        assert stat["median"] is not None
        assert stat["min"] <= stat["median"] <= stat["max"]
        assert stat["p10"] <= stat["p90"]


def test_samples_match_stats() -> None:
    solution = explore_solution_space(_BASE_RECIPE, n_samples=40, seed=7)
    samples = solution["samples"]
    stats = solution["stats"]
    for key in ("og_plato", "fg_plato", "abv_percent", "ibu", "srm", "attenuation"):
        values = [float(s.get(key) or 0.0) for s in samples]
        assert min(values) == pytest.approx(stats[key]["min"])
        assert max(values) == pytest.approx(stats[key]["max"])


def test_yeast_list_sampling() -> None:
    solution = explore_solution_space(_BASE_RECIPE, n_samples=30, seed=11)
    strains_used = {s.get("ferment", {}).get("yeast_strain_id") for s in solution["samples"]}
    strains_used.discard(None)
    assert strains_used.issubset({"US-05", "W-34/74", "S-04"})
    # With 30 samples across 3 strains, at least 2 distinct strains should appear.
    assert len(strains_used) >= 2


def test_scalar_only_recipe() -> None:
    """Recipe with no range params still produces identical samples."""
    recipe = dict(_BASE_RECIPE)
    recipe["grain_mass_kg"] = 6.0
    recipe["extract_potential"] = 0.80
    recipe["target_mash_temperature_degC"] = 65.0
    recipe["ferment"] = dict(recipe["ferment"])
    recipe["ferment"]["temperature_degC"] = 20.0
    recipe["ferment"]["yeast_strain_id"] = "US-05"
    recipe["boil"] = dict(recipe["boil"])
    recipe["boil"]["hops"] = [
        {"amount_kg": 0.06, "alpha_acid": 0.060, "time_minutes": 60},
        {"amount_kg": 0.02, "alpha_acid": 0.060, "time_minutes": 5},
    ]
    solution = explore_solution_space(recipe, n_samples=5, seed=3)
    assert solution["n_samples"] == 5
    stats = solution["stats"]
    for key in ("og_plato", "fg_plato", "abv_percent", "ibu", "srm", "attenuation"):
        assert stats[key]["min"] == pytest.approx(stats[key]["max"])


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
