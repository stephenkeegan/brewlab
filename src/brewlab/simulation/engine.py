"""Coupled simulation engine (Phase 4).

Chains brewing process stages so that each stage's outputs feed the next
stage's inputs, rather than treating each stage as an isolated calculator.

Pipeline: mash -> boil -> ferment.

The engine is deterministic given the same inputs and exposes per-stage
results plus an aggregated batch summary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
from brewlab.core.fermentation import fermentation_time_series
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
from brewlab.units import Quantity, ureg

_CP_GRAIN = ureg.Quantity(1.0, "kilojoule / (kilogram * degC)")
_CP_WATER = ureg.Quantity(4.186, "kilojoule / (kilogram * degC)")
_BOIL_TEMP = ureg.Quantity(100.0, "degC")


def _q(value: float, unit: str) -> Quantity:
    return ureg.Quantity(value, unit)


@dataclass
class CoupledSimulationResult:
    """Aggregated result of a full mash->boil->ferment simulation."""

    mash: dict[str, Any] = field(default_factory=dict)
    boil: dict[str, Any] = field(default_factory=dict)
    ferment: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "mash": self.mash,
            "boil": self.boil,
            "ferment": self.ferment,
            "summary": self.summary,
        }


def simulate_batch(
    recipe: dict[str, Any],
    equipment: dict[str, Any] | None = None,
) -> CoupledSimulationResult:
    """Run a full mash -> boil -> ferment simulation.

    Parameters
    ----------
    recipe : dict
        Keys (mash section or top-level):
            name, grain_mass_kg, extract_potential,
            water_to_grain_ratio_l_per_kg, grain_temperature_degC,
            target_mash_temperature_degC, mash_duration_minutes,
            batch_size_liters,
            water: {calcium_mg_per_l, magnesium_mg_per_l, bicarbonate_mg_per_l}
        boil section (or top-level):
            pre_boil_volume_liters, boil_off_rate_l_per_hr,
            boil_duration_minutes, hops: [{amount_kg, alpha_acid, time_minutes}]
        ferment section (or top-level):
            temperature_degC, duration_hours
    equipment : dict, optional
        {vessel_volume_liters, dead_space_liters, boil_off_rate_l_per_hr,
         efficiency, loss_to_trub_liters}. Overrides recipe boil values when
         provided.

    Returns
    -------
    CoupledSimulationResult
    """
    equip = equipment or {}

    # ---------- Mash ----------
    grain_mass = _q(recipe["grain_mass_kg"], "kilogram")
    grain_temp = _q(recipe["grain_temperature_degC"], "degC")
    target_temp = _q(recipe["target_mash_temperature_degC"], "degC")
    ratio = _q(recipe["water_to_grain_ratio_l_per_kg"], "liter / kilogram")

    strike_temp = strike_water_temperature(
        grain_mass, grain_temp, target_temp, ratio, _CP_GRAIN, _CP_WATER
    )

    water = recipe.get("water", {})
    alkalinity = alkalinity_as_caco3_from_bicarbonate(
        _q(water.get("bicarbonate_mg_per_l", 150.0), "milligram / liter")
    )
    ra = residual_alkalinity(
        alkalinity,
        _q(water.get("calcium_mg_per_l", 50.0), "milligram / liter"),
        _q(water.get("magnesium_mg_per_l", 10.0), "milligram / liter"),
    )
    water_ph = carbonate_system_ph(alkalinity, target_temp, _q(0.0004, "atm"))

    conversion = saccharification_conversion(
        _q(recipe["mash_duration_minutes"], "minute"), target_temp
    )

    # Pre-boil volume: mash water + extract, minus grain absorption.
    # Approx: strike water volume = grain_mass * ratio; absorbed ~ 1 L/kg grain.
    strike_volume_l = grain_mass.to("kilogram").magnitude * ratio.to("liter / kilogram").magnitude
    absorbed_l = grain_mass.to("kilogram").magnitude * 1.0
    pre_boil_volume = max(strike_volume_l - absorbed_l, 1.0)

    mash_plato = extract_plato(
        grain_mass,
        _q(recipe["extract_potential"], "dimensionless"),
        conversion,
        _q(pre_boil_volume, "liter"),
    )

    gel = gelatinization_factor(target_temp)

    mash = {
        "strike_water_temperature_degC": round(strike_temp.to("degC").magnitude, 2),
        "target_mash_temperature_degC": target_temp.to("degC").magnitude,
        "water_pH_at_mash_temp": round(water_ph.magnitude, 2),
        "residual_alkalinity_mg_per_L_as_CaCO3": round(ra.to("milligram / liter").magnitude, 2),
        "starch_conversion_fraction": round(conversion.magnitude, 4),
        "pre_boil_volume_liters": round(pre_boil_volume, 2),
        "pre_boil_plato": round(mash_plato.to("degPlato").magnitude, 2),
        "gelatinization_factor": round(gel.magnitude, 4),
        "grain_mass_kg": recipe["grain_mass_kg"],
        "model_contributions": {
            "thermodynamics": "strike-water heat balance",
            "equilibrium": "carbonate-system water pH (grist acidity pending)",
            "kinetics": "alpha/beta-amylase saccharification + extract",
        },
    }

    # ---------- Boil ----------
    boil_section = recipe.get("boil", {})
    boil_volume_l = boil_section.get("pre_boil_volume_liters", pre_boil_volume)
    if equip.get("vessel_volume_liters") is not None:
        boil_volume_l = equip["vessel_volume_liters"]
    boil_off_rate_l_hr = equip.get(
        "boil_off_rate_l_per_hr", boil_section.get("boil_off_rate_l_per_hr", 4.0)
    )
    boil_duration_min = boil_section.get("boil_duration_minutes", 60.0)

    boil_temp_q = _BOIL_TEMP
    post_boil_volume = boil_off_volume(
        _q(boil_volume_l, "liter"),
        _q(boil_off_rate_l_hr, "liter / hour"),
        _q(boil_duration_min / 60.0, "hour"),
    )
    post_boil_plato = wort_plato_after_boil(
        mash_plato,
        _q(boil_volume_l, "liter"),
        _q(boil_off_rate_l_hr, "liter / hour"),
        _q(boil_duration_min / 60.0, "hour"),
    )
    post_boil_sg = plato_to_specific_gravity(post_boil_plato)

    total_ibu = 0.0
    hop_additions = []
    for hop in boil_section.get("hops", []):
        amount = _q(hop["amount_kg"], "kilogram")
        alpha = _q(hop["alpha_acid"], "dimensionless")
        time_remaining = _q(hop["time_minutes"], "minute")
        iso_frac = alpha_acid_isomerization_fraction(time_remaining, boil_temp_q)
        iso_conc = iso_alpha_concentration(amount, alpha, _q(boil_volume_l, "liter"), iso_frac)
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

    boil = {
        "pre_boil_volume_liters": round(boil_volume_l, 2),
        "post_boil_volume_liters": round(post_boil_volume.to("liter").magnitude, 2),
        "boil_off_rate_l_per_hr": boil_off_rate_l_hr,
        "boil_duration_minutes": boil_duration_min,
        "pre_boil_plato": round(mash_plato.to("degPlato").magnitude, 2),
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

    # ---------- Ferment ----------
    ferment_section = recipe.get("ferment", {})
    ferm_temp = _q(ferment_section.get("temperature_degC", 20.0), "degC")
    ferm_duration = _q(ferment_section.get("duration_hours", 72.0), "hour")

    # Initial sugar from post-boil plato: approx plato * 10 g/L
    initial_sugar_g_per_l = post_boil_plato.to("degPlato").magnitude * 10.0
    ferm_result = fermentation_time_series(
        _q(initial_sugar_g_per_l, "gram / liter"),
        _q(
            ferment_section.get("initial_yeast_g_per_l", 0.1),
            "gram / liter",
        ),
        _q(ferment_section.get("volume_liters", post_boil_volume.to("liter").magnitude), "liter"),
        ferm_temp,
        ferm_duration,
    )

    ferment = {
        "initial_sugar_g_per_l": round(initial_sugar_g_per_l, 2),
        "temperature_degC": ferm_temp.to("degC").magnitude,
        "duration_hours": ferm_duration.to("hour").magnitude,
        "final_attenuation": round(ferm_result["final_attenuation"], 4),
        "final_fg_plato": round(ferm_result["final_fg_plato"], 3),
        "final_abv_percent": round(ferm_result["final_abv_percent"], 2),
        "final_ethanol_g_per_L": round(ferm_result["final_ethanol_g_per_L"], 2),
        "model_contributions": ferm_result["model_contributions"],
    }

    # ---------- Summary ----------
    summary = {
        "name": recipe.get("name", "batch"),
        "og_plato": round(mash_plato.to("degPlato").magnitude, 2),
        "fg_plato": round(ferm_result["final_fg_plato"], 3),
        "abv_percent": round(ferm_result["final_abv_percent"], 2),
        "ibu": round(total_ibu, 2),
        "srm": None,  # color model not yet implemented
        "volume_liters": round(post_boil_volume.to("liter").magnitude, 2),
        "attenuation": round(ferm_result["final_attenuation"], 4),
    }

    return CoupledSimulationResult(mash=mash, boil=boil, ferment=ferment, summary=summary)


__all__ = ["CoupledSimulationResult", "simulate_batch"]
