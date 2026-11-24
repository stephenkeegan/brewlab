"""Optimization engine (Phase 6).

Recipe generation and constraint solving built on top of the coupled
simulation engine. Given target finished-product characteristics (OG, FG,
ABV, IBU, batch size), the optimizer searches ingredient and process
parameters to minimize deviation from the targets.

Approach: weighted-sum multi-objective scalarization solved with
scipy.optimize.differential_evolution (deterministic via a fixed seed).
Decision variables are grain mass, extract potential, and hop amounts; the
coupled simulation (mash->boil->ferment) evaluates each candidate.

All quantities carry explicit units; the optimizer works internally in
scalar units for the solver and re-wraps results as pint.Quantity.

Classification: numerical optimization (constrained, single-objective via
weighted sum); parameters are calibration targets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from scipy.optimize import differential_evolution  # type: ignore[import-untyped]

from brewlab.simulation.engine import simulate_batch

# Default target scales for normalizing deviations (dimensionless weights).
_DEFAULT_SCALES = {
    "og_plato": 10.0,
    "fg_plato": 5.0,
    "abv_percent": 5.0,
    "ibu": 20.0,
}

# Bounds for decision variables: (grain_kg, extract_potential,
# bittering_hop_kg, aroma_hop_kg)
_DEFAULT_BOUNDS = [
    (3.0, 12.0),  # grain mass, kg
    (0.70, 0.85),  # extract potential, fraction
    (0.0, 0.15),  # bittering hop (60 min), kg
    (0.0, 0.08),  # aroma hop (5 min), kg
]

_DEFAULT_SEED = 42  # deterministic


@dataclass
class OptimizationTarget:
    og_plato: float | None = None
    fg_plato: float | None = None
    abv_percent: float | None = None
    ibu: float | None = None
    scales: dict[str, float] = field(default_factory=dict)


@dataclass
class OptimizationResult:
    success: bool
    score: float
    message: str
    grain_mass_kg: float
    extract_potential: float
    bittering_hop_kg: float
    aroma_hop_kg: float
    predicted: dict[str, Any] = field(default_factory=dict)
    simulation: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "score": self.score,
            "message": self.message,
            "grain_mass_kg": self.grain_mass_kg,
            "extract_potential": self.extract_potential,
            "bittering_hop_kg": self.bittering_hop_kg,
            "aroma_hop_kg": self.aroma_hop_kg,
            "predicted": self.predicted,
            "simulation": self.simulation,
        }


def _build_recipe(
    x: list[float],
    base_recipe: dict[str, Any],
) -> dict[str, Any]:
    """Overlay optimized decision variables onto a base recipe template."""
    grain_kg, extract_potential, bitter_kg, aroma_kg = x
    recipe = dict(base_recipe)
    recipe["grain_mass_kg"] = grain_kg
    recipe["extract_potential"] = extract_potential
    boil = dict(recipe.get("boil", {}))
    hops = []
    if bitter_kg > 0:
        hops.append({"amount_kg": bitter_kg, "alpha_acid": 0.055, "time_minutes": 60})
    if aroma_kg > 0:
        hops.append({"amount_kg": aroma_kg, "alpha_acid": 0.055, "time_minutes": 5})
    boil["hops"] = hops
    recipe["boil"] = boil
    return recipe


def _score(
    x: list[float],
    base_recipe: dict[str, Any],
    target: OptimizationTarget,
) -> float:
    """Weighted-sum squared deviation from targets."""
    recipe = _build_recipe(x, base_recipe)
    result = simulate_batch(recipe)
    s = result.summary
    score = 0.0
    scales = target.scales or _DEFAULT_SCALES
    if target.og_plato is not None and s.get("og_plato") is not None:
        score += ((s["og_plato"] - target.og_plato) / scales["og_plato"]) ** 2
    if target.fg_plato is not None and s.get("fg_plato") is not None:
        score += ((s["fg_plato"] - target.fg_plato) / scales["fg_plato"]) ** 2
    if target.abv_percent is not None and s.get("abv_percent") is not None:
        score += ((s["abv_percent"] - target.abv_percent) / scales["abv_percent"]) ** 2
    if target.ibu is not None and s.get("ibu") is not None:
        score += ((s["ibu"] - target.ibu) / scales["ibu"]) ** 2
    return score


def optimize_recipe(
    target: OptimizationTarget,
    base_recipe: dict[str, Any],
    bounds: list[tuple[float, float]] | None = None,
    seed: int = _DEFAULT_SEED,
    maxiter: int = 100,
) -> OptimizationResult:
    """Find ingredient/process parameters minimizing target deviation.

    Parameters
    ----------
    target : OptimizationTarget
        Desired finished-product characteristics (OG, FG, ABV, IBU). At
        least one must be set.
    base_recipe : dict
        Recipe template; fixed values (water, temperatures, durations,
        ferment params) are preserved. grain_mass_kg, extract_potential,
        and boil hops are overwritten by the optimizer.
    bounds : list[tuple[float, float]], optional
        Decision-variable bounds; defaults to _DEFAULT_BOUNDS.
    seed : int
        RNG seed for differential_evolution (deterministic).

    Returns
    -------
    OptimizationResult
        Best-found parameters, predicted outcomes, and the full simulation.

    Classification: numerical optimization (constrained weighted sum).
    """
    if all(
        v is None
        for v in (
            target.og_plato,
            target.fg_plato,
            target.abv_percent,
            target.ibu,
        )
    ):
        return OptimizationResult(
            success=False,
            score=float("inf"),
            message="At least one target must be specified.",
            grain_mass_kg=0.0,
            extract_potential=0.0,
            bittering_hop_kg=0.0,
            aroma_hop_kg=0.0,
        )

    bounds_used = bounds or _DEFAULT_BOUNDS

    result = differential_evolution(
        _score,
        bounds_used,
        args=(base_recipe, target),
        seed=seed,
        maxiter=maxiter,
        tol=1e-7,
        polish=True,
        updating="immediate",
    )

    best_x = result.x
    best_recipe = _build_recipe(best_x, base_recipe)
    sim = simulate_batch(best_recipe)
    summary = sim.summary

    return OptimizationResult(
        success=bool(result.success),
        score=float(result.fun),
        message=result.message,
        grain_mass_kg=float(best_x[0]),
        extract_potential=float(best_x[1]),
        bittering_hop_kg=float(best_x[2]),
        aroma_hop_kg=float(best_x[3]),
        predicted={
            "og_plato": summary.get("og_plato"),
            "fg_plato": summary.get("fg_plato"),
            "abv_percent": summary.get("abv_percent"),
            "ibu": summary.get("ibu"),
            "volume_liters": summary.get("volume_liters"),
            "attenuation": summary.get("attenuation"),
        },
        simulation=sim.as_dict(),
    )


def sensitivity(
    base_recipe: dict[str, Any],
    param: str,
    values: list[float],
) -> list[dict[str, Any]]:
    """One-at-a-time sensitivity: sweep a recipe parameter and record outputs.

    Parameters
    ----------
    base_recipe : dict
        Baseline recipe.
    param : str
        Top-level recipe key to vary (e.g. "grain_mass_kg",
        "target_mash_temperature_degC").
    values : list[float]
        Values to sweep.

    Returns
    -------
    list[dict]
        One entry per swept value with the parameter value and predicted
        OG/FG/ABV/IBU.
    """
    out: list[dict[str, Any]] = []
    for v in values:
        recipe = dict(base_recipe)
        recipe[param] = v
        sim = simulate_batch(recipe)
        s = sim.summary
        out.append(
            {
                param: v,
                "og_plato": s.get("og_plato"),
                "fg_plato": s.get("fg_plato"),
                "abv_percent": s.get("abv_percent"),
                "ibu": s.get("ibu"),
                "volume_liters": s.get("volume_liters"),
            }
        )
    return out


__all__ = [
    "OptimizationTarget",
    "OptimizationResult",
    "optimize_recipe",
    "sensitivity",
]
