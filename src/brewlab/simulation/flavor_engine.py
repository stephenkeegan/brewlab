"""Flavor back-propagation engine (Phase 10).

Given logged simulation samples (inputs -> normalized 0-100 flavor scores),
this module finds recipe inputs that best match a user-specified target
flavor profile. Approach: nearest-neighbor over logged samples (bounded to
the explored range) plus optional ``scipy.optimize.differential_evolution``
refinement to extrapolate beyond the logged range.

All flavor dimensions are normalized to 0-100 using the same scales as the
GUI flavor profile tab:

    Bitterness  -> IBU            (max 60)
    Sweetness   -> OG - FG        (max 8 plato)
    Body        -> OG             (max 22 plato)
    Alcohol     -> ABV percent    (max 7)
    Dryness     -> attenuation    (max 1.0)
    Hop aroma   -> late-hop IBU   (max 1.0 fraction)
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scipy.optimize import differential_evolution  # type: ignore[import-untyped]

from brewlab.simulation.engine import simulate_batch
from brewlab.simulation.solution_space import explore_solution_space

_FLAVOR_MAX = {
    "bitterness": 60.0,
    "sweetness": 8.0,
    "body": 22.0,
    "alcohol": 7.0,
    "dryness": 1.0,
    "hop_aroma": 1.0,
}

# Order must match FlavorTarget fields for vector math.
_FLAVOR_KEYS = (
    "bitterness",
    "sweetness",
    "body",
    "alcohol",
    "dryness",
    "hop_aroma",
)

# Decision-variable bounds for back-propagation.
_DEFAULT_INPUT_BOUNDS = {
    "grain_mass_kg": (0.5, 50.0),
    "extract_potential": (0.5, 0.95),
    "target_mash_temperature_degC": (45.0, 78.0),
    "ferment_temperature_degC": (10.0, 30.0),
    "bittering_hop_amount_kg": (0.0, 0.2),
}

_DEFAULT_LOG_PATH = Path(".brewlab_flavor_exploration.json")
_DEFAULT_SEED = 42


@dataclass
class FlavorTarget:
    """Desired flavor profile, each dimension normalized 0-100."""

    bitterness: float = 50.0
    sweetness: float = 50.0
    body: float = 50.0
    alcohol: float = 50.0
    dryness: float = 50.0
    hop_aroma: float = 50.0


@dataclass
class FlavorRecommendation:
    """Recommended inputs and predicted flavor for a target."""

    method: str  # "nearest_neighbor" or "nearest_neighbor + scipy_refine"
    distance: float  # Euclidean distance in normalized flavor space
    target: dict[str, float]  # normalized target 0-100
    predicted: dict[str, float]  # normalized predicted flavor 0-100
    inputs: dict[str, Any]  # recommended recipe inputs (partial, mergeable)
    matched_sample: dict[str, Any] | None = None  # nearest logged sample


class FlavorLogger:
    """Append-only JSON log of explored samples."""

    def __init__(self, log_path: Path = _DEFAULT_LOG_PATH) -> None:
        self.log_path = Path(log_path)

    def _load(self) -> list[dict[str, Any]]:
        if not self.log_path.exists():
            return []
        try:
            with open(self.log_path, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
        return []

    def save(self, samples: list[dict[str, Any]]) -> None:
        existing = self._load()
        existing.extend(samples)
        self.log_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    def load(self) -> list[dict[str, Any]]:
        return self._load()

    def clear(self) -> None:
        if self.log_path.exists():
            self.log_path.unlink()


def _raw_flavor_scores(result: dict[str, Any]) -> dict[str, float]:
    """Raw (unnormalized) flavor values from a simulation result."""
    summary = result.get("summary", {})
    boil = result.get("boil", {})
    og = float(summary.get("og_plato") or 0.0)
    fg = float(summary.get("fg_plato") or 0.0)
    abv = float(summary.get("abv_percent") or 0.0)
    ibu = float(summary.get("ibu") or 0.0)
    attenuation = float(summary.get("attenuation") or 0.0)
    hops = boil.get("hop_additions", [])
    total_ibu = float(summary.get("ibu") or 0.0)
    late_ibu = sum(float(h.get("ibu", 0.0)) for h in hops if int(h.get("time_minutes", 0)) <= 15)
    aroma_frac = (late_ibu / total_ibu) if total_ibu > 0 else 0.0
    return {
        "bitterness": ibu,
        "sweetness": max(og - fg, 0.0),
        "body": og,
        "alcohol": abv,
        "dryness": attenuation,
        "hop_aroma": aroma_frac,
    }


def _normalize(raw: dict[str, float]) -> dict[str, float]:
    """Normalize raw flavor values to 0-100 using _FLAVOR_MAX."""
    return {key: min(raw.get(key, 0.0) / _FLAVOR_MAX[key], 1.0) * 100.0 for key in _FLAVOR_KEYS}


def _sample_flavor(sample: dict[str, Any]) -> dict[str, float]:
    """Normalized 0-100 flavor scores for a logged sample."""
    result = {
        "summary": sample.get("summary", {}),
        "boil": sample.get("boil", {}),
    }
    raw = _raw_flavor_scores(result)
    return _normalize(raw)


def _flavor_vector(scores: dict[str, float]) -> tuple[float, ...]:
    return tuple(float(scores.get(k, 0.0)) for k in _FLAVOR_KEYS)


def _distance(a: dict[str, float], b: dict[str, float]) -> float:
    va = _flavor_vector(a)
    vb = _flavor_vector(b)
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(va, vb, strict=False)))


def _inputs_from_sample(sample: dict[str, Any]) -> dict[str, Any]:
    """Extract the mergeable input subset from a logged sample."""
    inputs: dict[str, Any] = {}
    for key in (
        "grain_mass_kg",
        "extract_potential",
        "target_mash_temperature_degC",
        "mash_duration_minutes",
        "batch_size_liters",
        "grain_color_lovibond",
        "grain_temperature_degC",
        "water_to_grain_ratio_l_per_kg",
    ):
        if key in sample:
            inputs[key] = sample[key]
    if "water" in sample:
        inputs["water"] = dict(sample["water"])
    if "boil" in sample:
        boil = dict(sample["boil"])
        boil["hops"] = [dict(h) for h in boil.get("hops", [])]
        inputs["boil"] = boil
    if "ferment" in sample:
        ferment = dict(sample["ferment"])
        inputs["ferment"] = ferment
    return inputs


def _simulate_inputs(
    bounds: dict[str, tuple[float, float]],
    yeast_list: list[str],
    x: list[float],
) -> dict[str, Any]:
    """Build a resolved recipe from decision vector ``x`` and simulate it."""
    recipe: dict[str, Any] = {
        "name": "backprop candidate",
        "grain_mass_kg": x[0],
        "extract_potential": x[1],
        "target_mash_temperature_degC": x[2],
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
                {"amount_kg": x[4], "alpha_acid": 0.060, "time_minutes": 60},
                {"amount_kg": 0.02, "alpha_acid": 0.060, "time_minutes": 5},
            ],
        },
        "ferment": {
            "temperature_degC": x[3],
            "duration_hours": 72.0,
            "initial_yeast_g_per_l": 0.1,
            "volume_liters": 20.0,
            "yeast_strain_id": yeast_list[int(round(x[5])) % len(yeast_list)],
        },
    }
    result = simulate_batch(recipe)
    return {
        "summary": result.summary,
        "boil": result.boil if hasattr(result, "boil") else {},
    }


def _result_from_sample(sample: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct a result-like dict from a logged sample for scoring."""
    return {
        "summary": sample.get("summary", {}),
        "boil": sample.get("boil", {}),
    }


def _nearest_neighbor(
    target: dict[str, float], samples: list[dict[str, Any]]
) -> tuple[dict[str, float], dict[str, Any], float]:
    """Find the logged sample with min Euclidean distance to target flavor."""
    best_sample = None
    best_scores = None
    best_dist = math.inf
    for sample in samples:
        scores = _sample_flavor(sample)
        dist = _distance(target, scores)
        if dist < best_dist:
            best_dist = dist
            best_scores = scores
            best_sample = sample
    return best_scores or {}, best_sample or {}, best_dist


def backpropagate_flavor(
    target: FlavorTarget,
    logged_samples: list[dict[str, Any]],
    input_bounds: dict[str, tuple[float, float]] | None = None,
    n_samples: int = 100,
    seed: int = _DEFAULT_SEED,
    refine: bool = True,
) -> FlavorRecommendation:
    """Back-propagate a target flavor profile to recommended recipe inputs.

    Parameters
    ----------
    target : FlavorTarget
        Desired flavor profile, each dimension 0-100.
    logged_samples : list[dict]
        Previously explored samples (inputs + summary outputs).
    input_bounds : dict[str, tuple[float, float]], optional
        Bounds for the scipy refinement. Defaults to _DEFAULT_INPUT_BOUNDS.
    n_samples : int
        Number of fresh randomized samples to generate if the log is empty.
    seed : int
        RNG seed for reproducibility.
    refine : bool
        Whether to run scipy differential_evolution refinement.

    Returns
    -------
    FlavorRecommendation
        Recommended inputs, predicted flavor, distance, and method used.
    """
    bounds = input_bounds or _DEFAULT_INPUT_BOUNDS
    target_norm = _normalize(
        {
            "bitterness": target.bitterness,
            "sweetness": target.sweetness,
            "body": target.body,
            "alcohol": target.alcohol,
            "dryness": target.dryness,
            "hop_aroma": target.hop_aroma,
        }
    )

    samples = list(logged_samples)

    # If the log is empty, generate fresh samples to seed the neighbor search.
    if not samples:
        base_recipe = _default_recipe()
        exploration = explore_solution_space(base_recipe, n_samples=n_samples, seed=seed)
        samples = exploration.get("samples", [])

    # Nearest-neighbor over logged samples.
    nn_scores, nn_sample, nn_dist = _nearest_neighbor(target_norm, samples)

    method = "nearest_neighbor"
    best_scores = nn_scores
    best_sample: dict[str, Any] | None = nn_sample
    best_dist = nn_dist
    best_inputs = _inputs_from_sample(best_sample) if best_sample else {}

    # Optional scipy refinement to extrapolate beyond the logged range.
    if refine and samples:
        yeast_list = sorted(
            {
                s.get("ferment", {}).get("yeast_strain_id")
                for s in samples
                if s.get("ferment", {}).get("yeast_strain_id")
            }
        ) or ["US-05"]

        def objective(x: list[float]) -> float:
            result_dict = _simulate_inputs(bounds, yeast_list, x)
            scores = _normalize(_raw_flavor_scores(result_dict))
            return _distance(target_norm, scores)

        var_names = list(bounds.keys())
        var_bounds = [bounds[k] for k in var_names]
        # yeast index bound appended separately
        var_bounds.append((0, len(yeast_list) - 1))

        result = differential_evolution(
            objective,
            var_bounds,
            seed=seed,
            tol=1e-7,
            polish=True,
            updating="immediate",
        )

        if result.fun < best_dist:
            best_dist = float(result.fun)
            best_inputs = _simulate_inputs(bounds, yeast_list, result.x)
            best_scores = _normalize(_raw_flavor_scores(best_inputs))
            best_sample = None
            method = "nearest_neighbor + scipy_refine"

    return FlavorRecommendation(
        method=method,
        distance=best_dist,
        target={k: target_norm[k] for k in _FLAVOR_KEYS},
        predicted={k: best_scores.get(k, 0.0) for k in _FLAVOR_KEYS},
        inputs=best_inputs,
        matched_sample=best_sample,
    )


def explore_and_log(
    recipe_ranges: dict[str, Any],
    n_samples: int = 100,
    seed: int = _DEFAULT_SEED,
    log_path: Path = _DEFAULT_LOG_PATH,
) -> dict[str, Any]:
    """Run randomized exploration and append results to the JSON log.

    Parameters
    ----------
    recipe_ranges : dict
        Recipe dict with scalar or ``{"min", "max"}`` range params.
    n_samples : int
        Number of Monte Carlo samples.
    seed : int
        RNG seed.
    log_path : Path
        JSON log file path.

    Returns
    -------
    dict
        ``explore_solution_space`` result plus ``logged_total`` count.
    """
    exploration = explore_solution_space(recipe_ranges, n_samples=n_samples, seed=seed)
    samples = exploration.get("samples", [])
    logger = FlavorLogger(log_path)
    logger.save(samples)
    exploration["logged_total"] = len(logger.load())
    return exploration


def _default_recipe() -> dict[str, Any]:
    """Base recipe used to seed an empty log."""
    return {
        "name": "Exploration base",
        "grain_mass_kg": {"min": 4.0, "max": 8.0},
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
            "yeast_strain_id": ["US-05", "W-34/74", "S-04"],
        },
    }


__all__ = [
    "FlavorTarget",
    "FlavorRecommendation",
    "FlavorLogger",
    "backpropagate_flavor",
    "explore_and_log",
]
