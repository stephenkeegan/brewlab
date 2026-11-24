"""Command-line interface for brewlab.

Phase 1 provides ``brewlab simulate mash`` (single-infusion mash) and Phase 2
adds ``brewlab simulate boil`` (boil-off, wort concentration, hop
isomerization, IBU). Results are printed as JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from brewlab import __version__
from brewlab.core.boil import (
    boil_off_volume,
    plato_to_specific_gravity,
    wort_plato_after_boil,
)
from brewlab.core.equilibrium import (
    alkalinity_as_caco3_from_bicarbonate,
    carbonate_system_ph,
    residual_alkalinity,
)
from brewlab.core.fermentation import (
    DEFAULT_ALPHA,
    DEFAULT_BETA,
    DEFAULT_INITIAL_YEAST,
    DEFAULT_KS,
    DEFAULT_MU_MAX,
    DEFAULT_YPS,
    DEFAULT_YXS,
    fermentation_time_series,
)
from brewlab.core.hops import (
    alpha_acid_isomerization_fraction,
    iso_alpha_concentration,
    predicted_ibu,
)
from brewlab.core.kinetics import (
    extract_plato,
    gelatinization_factor,
    saccharification_conversion,
)
from brewlab.core.thermodynamics import strike_water_temperature
from brewlab.persistence.json_repo import JsonRepository
from brewlab.simulation.engine import simulate_batch
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
        "stage": "mash",
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


def simulate_boil(boil: dict[str, Any], pre_boil_plato: float) -> dict[str, Any]:
    """Run a boil stage simulation.

    Expected boil keys:
        pre_boil_volume_liters, boil_off_rate_l_per_hr,
        boil_duration_minutes, hops: [{amount_kg, alpha_acid, time_minutes}]

    ``pre_boil_plato`` is the wort strength entering the boil (from mash).
    """
    pre_boil_volume = _q(boil["pre_boil_volume_liters"], "liter")
    boil_off_rate = _q(boil["boil_off_rate_l_per_hr"], "liter / hour")
    duration = _q(boil["boil_duration_minutes"], "minute")

    # 1. Boil-off volume
    post_boil_volume = boil_off_volume(pre_boil_volume, boil_off_rate, duration)

    # 2. Wort concentration after boil (extract conserved)
    post_boil_plato = wort_plato_after_boil(
        _q(pre_boil_plato, "degPlato"),
        pre_boil_volume,
        boil_off_rate,
        duration,
    )
    post_boil_sg = plato_to_specific_gravity(post_boil_plato)

    # 3. Hop isomerization + IBU per addition (all at boil temperature)
    boil_temp = _q(100.0, "degC")  # atmospheric boil; calibration target
    total_ibu = 0.0
    hop_additions = []
    for hop in boil.get("hops", []):
        amount = _q(hop["amount_kg"], "kilogram")
        alpha = _q(hop["alpha_acid"], "dimensionless")
        time_remaining = _q(hop["time_minutes"], "minute")
        iso_frac = alpha_acid_isomerization_fraction(time_remaining, boil_temp)
        iso_conc = iso_alpha_concentration(amount, alpha, pre_boil_volume, iso_frac)
        ibu = predicted_ibu(iso_conc)
        total_ibu += ibu.to("IBU").magnitude
        hop_additions.append(
            {
                "amount_kg": hop["amount_kg"],
                "alpha_acid": hop["alpha_acid"],
                "time_minutes": hop["time_minutes"],
                "isomerized_fraction": round(iso_frac.magnitude, 4),
                "iso_alpha_mg_per_L": round(iso_conc.to("milligram / liter").magnitude, 2),
                "ibu": round(ibu.to("IBU").magnitude, 2),
            }
        )

    return {
        "stage": "boil",
        "pre_boil_volume_liters": pre_boil_volume.to("liter").magnitude,
        "post_boil_volume_liters": round(post_boil_volume.to("liter").magnitude, 2),
        "boil_off_rate_l_per_hr": boil_off_rate.to("liter / hour").magnitude,
        "boil_duration_minutes": duration.to("minute").magnitude,
        "pre_boil_plato": pre_boil_plato,
        "post_boil_plato": round(post_boil_plato.to("degPlato").magnitude, 2),
        "post_boil_specific_gravity": round(post_boil_sg.magnitude, 4),
        "total_ibu": round(total_ibu, 2),
        "hop_additions": hop_additions,
        "model_contributions": {
            "thermodynamics": "boil-off volume / wort concentration",
            "kinetics": "alpha-acid isomerization (first-order Arrhenius)",
            "hops": "IBU from iso-alpha acid + utilization efficiency",
        },
    }


def simulate_ferment(ferm: dict[str, Any]) -> dict[str, Any]:
    """Run a fermentation simulation.

    Expected ferm keys:
        initial_sugar_g_per_l, initial_yeast_g_per_l, volume_liters,
        temperature_degC, duration_hours
    Optional kinetic overrides: mu_max_1_per_hour, ks_gram_per_liter,
    yxs, alpha, beta, yps
    """
    result = fermentation_time_series(
        _q(ferm["initial_sugar_g_per_l"], "gram / liter"),
        _q(ferm.get("initial_yeast_g_per_l", DEFAULT_INITIAL_YEAST), "gram / liter"),
        _q(ferm["volume_liters"], "liter"),
        _q(ferm["temperature_degC"], "degC"),
        _q(ferm["duration_hours"], "hour"),
        mu_max=_q(ferm.get("mu_max_1_per_hour", DEFAULT_MU_MAX), "1 / hour"),
        ks=_q(ferm.get("ks_gram_per_liter", DEFAULT_KS), "gram / liter"),
        yxs=_q(ferm.get("yxs", DEFAULT_YXS), "dimensionless"),
        alpha=_q(ferm.get("alpha", DEFAULT_ALPHA), "dimensionless"),
        beta=_q(ferm.get("beta", DEFAULT_BETA), "dimensionless"),
        yps=_q(ferm.get("yps", DEFAULT_YPS), "dimensionless"),
    )
    return {
        "stage": "ferment",
        "initial_sugar_g_per_l": ferm["initial_sugar_g_per_l"],
        "temperature_degC": ferm["temperature_degC"],
        "duration_hours": ferm["duration_hours"],
        "final_attenuation": round(result["final_attenuation"], 4),
        "final_fg_plato": round(result["final_fg_plato"], 3),
        "final_abv_percent": round(result["final_abv_percent"], 2),
        "final_ethanol_g_per_L": round(result["final_ethanol_g_per_L"], 2),
        "model_contributions": result["model_contributions"],
    }


def simulate_all(recipe: dict[str, Any]) -> dict[str, Any]:
    """Run the full mash -> boil -> ferment batch simulation."""
    result = simulate_batch(recipe)
    return result.as_dict()


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

    boil = sim_sub.add_parser("boil", help="Boil stage simulation")
    boil.add_argument(
        "recipe",
        help="Path to JSON recipe file (or '-' to read from stdin)",
    )
    boil.add_argument(
        "--format",
        choices=["json"],
        default="json",
        help="Output format",
    )

    ferment = sim_sub.add_parser("ferment", help="Fermentation simulation")
    ferment.add_argument(
        "recipe",
        help="Path to JSON recipe file (or '-' to read from stdin)",
    )
    ferment.add_argument(
        "--format",
        choices=["json"],
        default="json",
        help="Output format",
    )

    all_cmd = sim_sub.add_parser("all", help="Full mash->boil->ferment batch")
    all_cmd.add_argument(
        "recipe",
        help="Path to JSON recipe file (or '-' to read from stdin)",
    )
    all_cmd.add_argument(
        "--format",
        choices=["json"],
        default="json",
        help="Output format",
    )

    store = sub.add_parser("store", help="Persist recipes / simulation results")
    store_sub = store.add_subparsers(dest="store_command")

    save = store_sub.add_parser("save", help="Save an item to the store")
    save.add_argument("id", help="Item id")
    save.add_argument("file", help="Path to JSON file (or '-' to read from stdin)")

    load = store_sub.add_parser("load", help="Load and print a stored item")
    load.add_argument("id", help="Item id")

    store_sub.add_parser("list", help="List stored item ids")

    parser.add_argument("--version", action="store_true", help="show version")
    parser.add_argument(
        "--store",
        default=".brewlab_store",
        help="Directory for the JSON persistence store",
    )
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

    if args.command == "simulate" and args.sim_command == "boil":
        source = args.recipe
        if source == "-":
            recipe = json.load(sys.stdin)
        else:
            with open(source, encoding="utf-8") as fh:
                recipe = json.load(fh)
        boil_section = recipe.get("boil", recipe)
        pre_boil_plato = recipe.get("pre_boil_plato", recipe.get("extract_degPlato", 10.0))
        result = simulate_boil(boil_section, pre_boil_plato)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "simulate" and args.sim_command == "ferment":
        source = args.recipe
        if source == "-":
            recipe = json.load(sys.stdin)
        else:
            with open(source, encoding="utf-8") as fh:
                recipe = json.load(fh)
        result = simulate_ferment(recipe)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "simulate" and args.sim_command == "all":
        source = args.recipe
        if source == "-":
            recipe = json.load(sys.stdin)
        else:
            with open(source, encoding="utf-8") as fh:
                recipe = json.load(fh)
        result = simulate_all(recipe)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "store":
        store_dir = Path(args.store)
        repo = JsonRepository[dict[str, Any]](store_dir)
        if args.store_command == "save":
            source = args.file
            if source == "-":
                item = json.load(sys.stdin)
            else:
                with open(source, encoding="utf-8") as fh:
                    item = json.load(fh)
            repo.add(item)
            print(json.dumps({"id": args.id, "saved": True}, indent=2))
            return 0
        if args.store_command == "load":
            item = repo.get(args.id)
            if item is None:
                print(json.dumps({"error": f"not found: {args.id}"}, indent=2))
                return 1
            print(json.dumps(item, indent=2))
            return 0
        if args.store_command == "list":
            items = repo.list()
            print(
                json.dumps(
                    [i.get("id") if isinstance(i, dict) else getattr(i, "id", None) for i in items],
                    indent=2,
                )
            )
            return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
