"""Solution-space exploration (Phase 9).

Given a recipe whose numeric parameters may be scalars or ``{"min", "max"}``
range dicts, and whose yeast may be a single strain id or a list of strain
ids, this module samples uniformly within the ranges and runs the coupled
simulation for each sample. It returns per-output min/max/median/p10/p90
bands plus the full sample list, so a GUI can render a solution space for
flavor-relevant parameters.

Range parameters (confirmed set):
    grain_mass_kg, extract_potential, target_mash_temperature_degC,
    ferment.temperature_degC, boil hops[].amount_kg (bittering addition),
    yeast (strain id or list of strain ids).
"""

from __future__ import annotations

import random
import statistics
from typing import Any

from brewlab.simulation.engine import simulate_batch

_RANGE_PARAMS = (
    "grain_mass_kg",
    "extract_potential",
    "target_mash_temperature_degC",
)

_OUTPUT_KEYS = (
    "og_plato",
    "fg_plato",
    "abv_percent",
    "ibu",
    "srm",
    "chloride_sulfate_ratio",
    "attenuation",
    "volume_liters",
)

_DEFAULT_SEED = 42


def _resolve(param: Any, rng: random.Random) -> Any:
    """Resolve a parameter that may be a scalar or a ``{"min", "max"}`` dict."""
    if isinstance(param, dict) and "min" in param and "max" in param:
        return rng.uniform(float(param["min"]), float(param["max"]))
    return param


def _resolve_recipe(recipe: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    """Build a resolved copy of ``recipe`` with all range params sampled."""
    resolved: dict[str, Any] = {}
    for key, value in recipe.items():
        if key in _RANGE_PARAMS:
            resolved[key] = _resolve(value, rng)
        elif key == "water":
            resolved[key] = dict(value)
        elif key == "boil":
            boil = dict(value)
            hops = boil.get("hops", [])
            resolved_hops: list[dict[str, Any]] = []
            for hop in hops:
                resolved_hop = dict(hop)
                if "amount_kg" in hop:
                    resolved_hop["amount_kg"] = _resolve(hop["amount_kg"], rng)
                resolved_hops.append(resolved_hop)
            boil["hops"] = resolved_hops
            resolved[key] = boil
        elif key == "ferment":
            ferment = dict(value)
            ferment["temperature_degC"] = _resolve(ferment.get("temperature_degC", 20.0), rng)
            if "yeast_strain_id" in ferment:
                ferment["yeast_strain_id"] = _resolve_yeast(ferment["yeast_strain_id"], rng)
            resolved[key] = ferment
        elif key == "yeast_strain_id":
            resolved[key] = _resolve_yeast(value, rng)
        else:
            resolved[key] = value
    return resolved


def _resolve_yeast(yeast_spec: Any, rng: random.Random) -> str | None:
    """Resolve yeast: a single id or a random choice from a list of ids."""
    if yeast_spec is None:
        return None
    if isinstance(yeast_spec, list):
        return str(rng.choice(yeast_spec))
    return str(yeast_spec)


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Linear-interpolation percentile (0-100) of sorted values."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    d0 = sorted_values[f] * (c - k)
    d1 = sorted_values[c] * (k - f)
    return d0 + d1


def _output_stats(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute min/max/median/p10/p90 for each output key across samples."""
    stats: dict[str, Any] = {}
    for key in _OUTPUT_KEYS:
        values = sorted(float(s.get(key) or 0.0) for s in samples if s.get(key) is not None)
        if not values:
            stats[key] = {
                "min": None,
                "max": None,
                "median": None,
                "p10": None,
                "p90": None,
            }
            continue
        stats[key] = {
            "min": values[0],
            "max": values[-1],
            "median": statistics.median(values),
            "p10": _percentile(values, 10.0),
            "p90": _percentile(values, 90.0),
        }
    return stats


def explore_solution_space(
    recipe: dict[str, Any],
    n_samples: int = 200,
    seed: int = _DEFAULT_SEED,
) -> dict[str, Any]:
    """Explore the solution space of a ranged recipe.

    Parameters
    ----------
    recipe : dict
        Recipe dict where any of the range parameters may be a scalar or a
        ``{"min", "max"}`` dict, and ``yeast_strain_id`` may be a string or
        list of strings.
    n_samples : int
        Number of Monte Carlo samples to draw.
    seed : int
        RNG seed for reproducibility.

    Returns
    -------
    dict
        {"stats": {output_key: {min, max, median, p10, p90}},
         "samples": [ {scenario inputs + outputs}, ... ]}
    """
    rng = random.Random(seed)
    samples: list[dict[str, Any]] = []

    for _ in range(n_samples):
        resolved = _resolve_recipe(recipe, rng)
        try:
            result = simulate_batch(resolved)
            summary = result.summary
        except Exception:
            # Skip samples that fail to simulate (e.g. out-of-range inputs).
            continue
        entry = dict(resolved)
        entry.update(summary)
        samples.append(entry)

    return {
        "n_samples": len(samples),
        "requested_samples": n_samples,
        "stats": _output_stats(samples),
        "samples": samples,
    }


__all__ = ["explore_solution_space"]
