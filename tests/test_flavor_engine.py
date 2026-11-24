"""Flavor back-propagation engine tests (Phase 10).

Validates flavor scoring, JSON log persistence, nearest-neighbor
back-propagation, and optional scipy refinement.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from brewlab.simulation.flavor_engine import (
    FlavorLogger,
    FlavorRecommendation,
    FlavorTarget,
    _distance,
    _normalize,
    _raw_flavor_scores,
    backpropagate_flavor,
    explore_and_log,
)

_SUMMARY_HIGH_BITTER = {
    "og_plato": 10.0,
    "fg_plato": 3.0,
    "abv_percent": 4.0,
    "ibu": 60.0,
    "attenuation": 0.7,
    "srm": 5.0,
    "chloride_sulfate_ratio": 1.0,
    "volume_liters": 20.0,
}
_BOIL_HIGH_BITTER = {
    "hop_additions": [
        {"time_minutes": 60, "ibu": 60.0, "amount_kg": 0.05},
    ],
}

_SUMMARY_LOW_BITTER = {
    "og_plato": 15.0,
    "fg_plato": 5.0,
    "abv_percent": 6.0,
    "ibu": 0.0,
    "attenuation": 0.6,
    "srm": 15.0,
    "chloride_sulfate_ratio": 1.0,
    "volume_liters": 20.0,
}
_BOIL_LOW_BITTER = {
    "hop_additions": [
        {"time_minutes": 5, "ibu": 0.0, "amount_kg": 0.02},
    ],
}


def _sample(summary: dict, boil: dict) -> dict:
    return {
        "grain_mass_kg": 6.0,
        "extract_potential": 0.80,
        "target_mash_temperature_degC": 65.0,
        "ferment": {
            "temperature_degC": 20.0,
            "yeast_strain_id": "US-05",
        },
        "summary": dict(summary),
        "boil": dict(boil),
    }


def test_flavor_target_defaults() -> None:
    t = FlavorTarget()
    assert t.bitterness == 50.0
    assert t.sweetness == 50.0
    assert t.body == 50.0
    assert t.alcohol == 50.0
    assert t.dryness == 50.0
    assert t.hop_aroma == 50.0


def test_normalize_clamps_to_100() -> None:
    raw = {
        "bitterness": 120.0,  # 2x max -> clamped to 100
        "sweetness": 16.0,  # 2x max -> clamped to 100
        "body": 22.0,
        "alcohol": 7.0,
        "dryness": 1.0,
        "hop_aroma": 1.0,
    }
    norm = _normalize(raw)
    assert all(v == pytest.approx(100.0) for v in norm.values())


def test_normalize_half_max() -> None:
    raw = {
        "bitterness": 30.0,
        "sweetness": 4.0,
        "body": 11.0,
        "alcohol": 3.5,
        "dryness": 0.5,
        "hop_aroma": 0.5,
    }
    norm = _normalize(raw)
    assert all(v == pytest.approx(50.0) for v in norm.values())


def test_raw_flavor_scores() -> None:
    result = {"summary": _SUMMARY_HIGH_BITTER, "boil": _BOIL_HIGH_BITTER}
    scores = _raw_flavor_scores(result)
    assert scores["bitterness"] == pytest.approx(60.0)
    assert scores["sweetness"] == pytest.approx(7.0)
    assert scores["body"] == pytest.approx(10.0)
    assert scores["alcohol"] == pytest.approx(4.0)
    assert scores["dryness"] == pytest.approx(0.7)
    assert scores["hop_aroma"] == pytest.approx(0.0)


def test_distance_symmetric() -> None:
    a = {
        "bitterness": 0.0,
        "sweetness": 0.0,
        "body": 0.0,
        "alcohol": 0.0,
        "dryness": 0.0,
        "hop_aroma": 0.0,
    }
    b = {
        "bitterness": 100.0,
        "sweetness": 0.0,
        "body": 0.0,
        "alcohol": 0.0,
        "dryness": 0.0,
        "hop_aroma": 0.0,
    }
    assert _distance(a, b) == pytest.approx(100.0)
    assert _distance(a, b) == _distance(b, a)


def test_logger_append_load(tmp_path: Path) -> None:
    log_path = tmp_path / "flavor.json"
    logger = FlavorLogger(log_path)
    samples = [
        _sample(_SUMMARY_HIGH_BITTER, _BOIL_HIGH_BITTER),
        _sample(_SUMMARY_LOW_BITTER, _BOIL_LOW_BITTER),
    ]
    logger.save(samples)
    loaded = logger.load()
    assert len(loaded) == 2
    assert loaded[0]["summary"]["ibu"] == 60.0
    assert loaded[1]["summary"]["ibu"] == 0.0


def test_logger_appends_without_duplicate(tmp_path: Path) -> None:
    log_path = tmp_path / "flavor.json"
    logger = FlavorLogger(log_path)
    logger.save([_sample(_SUMMARY_HIGH_BITTER, _BOIL_HIGH_BITTER)])
    logger.save([_sample(_SUMMARY_LOW_BITTER, _BOIL_LOW_BITTER)])
    assert len(logger.load()) == 2


def test_logger_clear(tmp_path: Path) -> None:
    log_path = tmp_path / "flavor.json"
    logger = FlavorLogger(log_path)
    logger.save([_sample(_SUMMARY_HIGH_BITTER, _BOIL_HIGH_BITTER)])
    logger.clear()
    assert logger.load() == []
    assert not log_path.exists()


def test_backpropagate_nearest_neighbor_picks_closest() -> None:
    """NN picks the logged sample whose flavor is closest to target."""
    samples = [
        _sample(_SUMMARY_HIGH_BITTER, _BOIL_HIGH_BITTER),
        _sample(_SUMMARY_LOW_BITTER, _BOIL_LOW_BITTER),
    ]
    target = FlavorTarget(
        bitterness=100.0,
        sweetness=0.0,
        body=0.0,
        alcohol=0.0,
        dryness=0.0,
        hop_aroma=0.0,
    )
    rec = backpropagate_flavor(target, samples, refine=False)
    assert isinstance(rec, FlavorRecommendation)
    assert rec.method == "nearest_neighbor"
    assert rec.matched_sample is not None
    assert rec.matched_sample["summary"]["ibu"] == 60.0
    assert rec.distance >= 0.0


def test_backpropagate_inputs_within_bounds() -> None:
    """Recommended inputs always lie within declared bounds."""
    samples = [
        _sample(_SUMMARY_HIGH_BITTER, _BOIL_HIGH_BITTER),
        _sample(_SUMMARY_LOW_BITTER, _BOIL_LOW_BITTER),
    ]
    target = FlavorTarget(
        bitterness=50.0, sweetness=50.0, body=50.0, alcohol=50.0, dryness=50.0, hop_aroma=50.0
    )
    bounds = {
        "grain_mass_kg": (0.5, 50.0),
        "extract_potential": (0.5, 0.95),
        "target_mash_temperature_degC": (45.0, 78.0),
        "ferment_temperature_degC": (10.0, 30.0),
        "bittering_hop_amount_kg": (0.0, 0.2),
    }
    rec = backpropagate_flavor(target, samples, input_bounds=bounds, refine=False)
    assert rec.matched_sample is not None
    grain = rec.matched_sample.get("grain_mass_kg", 0.0)
    assert bounds["grain_mass_kg"][0] <= grain <= bounds["grain_mass_kg"][1]


def test_backpropagate_empty_log_seeds_samples() -> None:
    """Empty log generates fresh samples instead of crashing."""
    target = FlavorTarget(
        bitterness=50.0, sweetness=50.0, body=50.0, alcohol=50.0, dryness=50.0, hop_aroma=50.0
    )
    rec = backpropagate_flavor(target, [], n_samples=10, seed=1, refine=False)
    assert isinstance(rec, FlavorRecommendation)
    assert rec.distance >= 0.0


def test_backpropagate_refine_does_not_increase_distance() -> None:
    """Scipy refinement (when it runs) does not increase distance vs NN."""
    samples = [
        _sample(_SUMMARY_HIGH_BITTER, _BOIL_HIGH_BITTER),
        _sample(_SUMMARY_LOW_BITTER, _BOIL_LOW_BITTER),
    ]
    target = FlavorTarget(
        bitterness=80.0, sweetness=20.0, body=40.0, alcohol=40.0, dryness=40.0, hop_aroma=20.0
    )
    rec_nn = backpropagate_flavor(target, samples, refine=False, seed=7)
    rec_ref = backpropagate_flavor(target, samples, refine=True, seed=7, n_samples=20)
    assert rec_ref.distance <= rec_nn.distance + 1e-6


def test_explore_and_log_writes_file(tmp_path: Path) -> None:
    log_path = tmp_path / "flavor.json"
    recipe = {
        "name": "explore",
        "grain_mass_kg": {"min": 4.0, "max": 6.0},
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
                {"amount_kg": {"min": 0.03, "max": 0.09}, "alpha_acid": 0.060, "time_minutes": 60},
                {"amount_kg": 0.02, "alpha_acid": 0.060, "time_minutes": 5},
            ],
        },
        "ferment": {
            "temperature_degC": {"min": 18.0, "max": 22.0},
            "duration_hours": 72.0,
            "initial_yeast_g_per_l": 0.1,
            "volume_liters": 20.0,
            "yeast_strain_id": ["US-05", "W-34/74"],
        },
    }
    result = explore_and_log(recipe, n_samples=5, seed=3, log_path=log_path)
    assert result["n_samples"] > 0
    assert result["logged_total"] > 0
    stored = json.loads(log_path.read_text(encoding="utf-8"))
    assert isinstance(stored, list)
    assert len(stored) == result["logged_total"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
