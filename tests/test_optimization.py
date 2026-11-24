"""Optimization engine validation tests (Phase 6).

Validates that optimize_recipe finds parameters driving predicted outputs
toward targets, and that sensitivity sweeps return structured output.
"""

from __future__ import annotations

import pytest

from brewlab.optimization.engine import (
    OptimizationTarget,
    optimize_recipe,
    sensitivity,
)

_BASE_RECIPE = {
    "name": "Optimization Test",
    "grain_mass_kg": 6.0,
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
        "hops": [],
    },
    "ferment": {
        "temperature_degC": 20.0,
        "duration_hours": 72.0,
    },
}


def test_optimize_recipe_target_og() -> None:
    """Optimizer should drive OG plato toward target."""
    target = OptimizationTarget(og_plato=23.0)
    result = optimize_recipe(target, _BASE_RECIPE, maxiter=60)
    assert result.success
    assert result.predicted["og_plato"] is not None
    assert abs(result.predicted["og_plato"] - 23.0) < 2.0
    assert result.grain_mass_kg > 0.0


def test_optimize_recipe_target_ibu() -> None:
    """Optimizer should drive IBU toward target via hop amount."""
    target = OptimizationTarget(ibu=30.0)
    result = optimize_recipe(target, _BASE_RECIPE, maxiter=60)
    assert result.success
    assert result.predicted["ibu"] is not None
    assert abs(result.predicted["ibu"] - 30.0) < 8.0


def test_optimize_recipe_multi_objective() -> None:
    """OG + ABV + IBU targets simultaneously."""
    target = OptimizationTarget(og_plato=23.0, abv_percent=4.5, ibu=25.0)
    result = optimize_recipe(target, _BASE_RECIPE, maxiter=80)
    assert result.success
    assert result.predicted["og_plato"] is not None
    assert result.predicted["abv_percent"] is not None
    assert result.predicted["ibu"] is not None


def test_optimize_recipe_no_target() -> None:
    """No targets -> failure result, no crash."""
    target = OptimizationTarget()
    result = optimize_recipe(target, _BASE_RECIPE)
    assert not result.success
    assert result.score == float("inf")


def test_optimize_recipe_deterministic() -> None:
    """Same inputs -> same result (fixed seed)."""
    target = OptimizationTarget(og_plato=23.0, ibu=30.0)
    a = optimize_recipe(target, _BASE_RECIPE, maxiter=60)
    b = optimize_recipe(target, _BASE_RECIPE, maxiter=60)
    assert a.score == b.score
    assert a.grain_mass_kg == b.grain_mass_kg


def test_sensitivity_structure() -> None:
    """Sensitivity returns one entry per value with outputs."""
    out = sensitivity(_BASE_RECIPE, "grain_mass_kg", [4.0, 6.0, 8.0])
    assert len(out) == 3
    assert [o["grain_mass_kg"] for o in out] == [4.0, 6.0, 8.0]
    for o in out:
        assert "og_plato" in o
        assert "abv_percent" in o


def test_sensitivity_monotonic_og_vs_extract() -> None:
    """Higher extract potential -> higher OG (sanity check on coupling)."""
    out = sensitivity(_BASE_RECIPE, "extract_potential", [0.70, 0.80, 0.90])
    ogs = [o["og_plato"] for o in out]
    assert all(o is not None for o in ogs)
    assert ogs[0] < ogs[1] < ogs[2]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
