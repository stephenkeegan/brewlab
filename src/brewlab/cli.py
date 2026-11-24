"""Command-line interface for brewlab.

Phase 1 provides ``brewlab simulate mash`` which runs a units-checked
single-infusion mash simulation end-to-end:

    strike-water temperature  (thermodynamics)
    water pH                  (equilibrium / carbonate system)
    saccharification          (kinetics / alpha-beta amylase)
    extract in degPlato       (kinetics)

Results are printed as JSON for easy inspection and downstream use.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from brewlab import __version__
from brewlab.core.equilibrium import (
    alkalinity_as_caco3_from_bicarbonate,
    carbonate_system_ph,
    residual_alkalinity,
)
from brewlab.core.kinetics import (
    extract_plato,
    gelatinization_factor,
    saccharification_conversion,
)
from brewlab.core.thermodynamics import strike_water_temperature
from brewlab.units import ureg


def _q(value: float, unit: str) -> Any:
    return ureg.Quantity(value, unit)


def simulate_mash(recipe: dict[str, Any]) -> dict[str, Any]:
    """Run a single-infusion mash simulation.

    Expected recipe keys:
        name, batch_size_liters, grain_mass_kg, extract_potential,
        water_to_grain_ratio_l_per_kg, grain_temperature_degC,
        target_mash_temperature_degC, mash_duration_minutes,
        water: {calcium_mg_per_l, magnesium_mg_per_l, bicarbonate_mg_per_l}
    """
    grain_mass = _q(recipe["grain_mass_kg"], "kilogram")
    grain_temp = _q(recipe["grain_temperature_degC"], "degC")
    target_temp = _q(recipe["target_mash_temperature_degC"], "degC")
    ratio = _q(recipe["water_to_grain_ratio_l_per_kg"], "liter / kilogram")
    cp_grain = _q(1.0, "kilojoule / (kilogram * degC)")
    cp_water = _q(4.186, "kilojoule / (kilogram * degC)")

    # 1. Strike-water temperature (thermodynamics)
    strike_temp = strike_water_temperature(
        grain_mass, grain_temp, target_temp, ratio, cp_grain, cp_water
    )

    # 2. Water chemistry -> mash pH (equilibrium)
    water = recipe.get("water", {})
    alkalinity = alkalinity_as_caco3_from_bicarbonate(
        _q(water.get("bicarbonate_mg_per_l", 150.0), "milligram / liter")
    )
    ra = residual_alkalinity(
        alkalinity,
        _q(water.get("calcium_mg_per_l", 50.0), "milligram / liter"),
        _q(water.get("magnesium_mg_per_l", 10.0), "milligram / liter"),
    )
    mash_ph = carbonate_system_ph(alkalinity, target_temp, _q(0.0004, "atm"))

    # 3. Saccharification over the mash duration (kinetics)
    conversion = saccharification_conversion(
        _q(recipe["mash_duration_minutes"], "minute"), target_temp
    )

    # 4. Extract in degPlato (kinetics)
    plato = extract_plato(
        grain_mass,
        _q(recipe["extract_potential"], "dimensionless"),
        conversion,
        _q(recipe["batch_size_liters"], "liter"),
    )

    # Gelatinization at mash temp (for the per-step breakdown)
    gel = gelatinization_factor(target_temp)

    return {
        "name": recipe.get("name", "mash"),
        "strike_water_temperature_degC": round(strike_temp.to("degC").magnitude, 2),
        "target_mash_temperature_degC": target_temp.to("degC").magnitude,
        # NOTE: this is the carbonate-system water pH at mash temperature.
        # True mash pH is depressed by grist acidity (phytin/phosphate) which
        # is not yet modeled; reported here for completeness and labeled
        # explicitly to avoid presenting water pH as mash pH.
        "water_pH_at_mash_temp": round(mash_ph.magnitude, 2),
        "water_pH_note": "Carbonate-system water pH only; grist acidity not "
        "modeled, so actual mash pH will be lower (typically ~5.2-5.6).",
        "residual_alkalinity_mg_per_L_as_CaCO3": round(ra.to("milligram / liter").magnitude, 2),
        "starch_conversion_fraction": round(conversion.magnitude, 4),
        "extract_degPlato": round(plato.to("degPlato").magnitude, 2),
        "gelatinization_factor": round(gel.magnitude, 4),
        "batch_size_liters": recipe["batch_size_liters"],
        "grain_mass_kg": recipe["grain_mass_kg"],
        "model_contributions": {
            "thermodynamics": "strike-water heat balance",
            "equilibrium": "carbonate-system water pH (grist acidity pending)",
            "kinetics": "alpha/beta-amylase saccharification + extract",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="brewlab", description="BrewLab CLI")
    sub = parser.add_subparsers(dest="command")

    sim = sub.add_parser("simulate", help="Run a simulation")
    sim_sub = sim.add_subparsers(dest="sim_command")

    mash = sim_sub.add_parser("mash", help="Single-infusion mash simulation")
    mash.add_argument(
        "recipe",
        help="Path to JSON recipe file (or '-' to read from stdin)",
    )
    mash.add_argument(
        "--format",
        choices=["json"],
        default="json",
        help="Output format",
    )

    parser.add_argument("--version", action="store_true", help="show version")
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    if args.command == "simulate" and args.sim_command == "mash":
        source = args.recipe
        if source == "-":
            recipe = json.load(sys.stdin)
        else:
            with open(source, encoding="utf-8") as fh:
                recipe = json.load(fh)
        result = simulate_mash(recipe)
        print(json.dumps(result, indent=2))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
