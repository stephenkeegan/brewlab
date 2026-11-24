"""BrewLab GUI — Streamlit app for recipe input, simulation, and visualization.

Separate from the scientific core per the project's strict boundary: this
module only imports from ``brewlab.simulation`` and ``brewlab.persistence``.
Run with:

    streamlit run src/brewlab/gui/app.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from brewlab.persistence.json_repo import JsonRepository
from brewlab.simulation.engine import simulate_batch

STORE_DIR = Path(".brewlab_store_gui")


def _default_recipe() -> dict[str, Any]:
    return {
        "name": "My Recipe",
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
            "hops": [
                {"amount_kg": 0.06, "alpha_acid": 0.055, "time_minutes": 60},
                {"amount_kg": 0.03, "alpha_acid": 0.055, "time_minutes": 15},
                {"amount_kg": 0.02, "alpha_acid": 0.015, "time_minutes": 5},
            ],
        },
        "ferment": {
            "temperature_degC": 20.0,
            "duration_hours": 72.0,
            "initial_yeast_g_per_l": 0.1,
            "volume_liters": 20.0,
        },
    }


def _sidebar_inputs(recipe: dict[str, Any]) -> dict[str, Any]:
    st.sidebar.header("Recipe inputs")

    r = dict(recipe)
    r["name"] = st.sidebar.text_input("Recipe name", value=r.get("name", "My Recipe"))

    st.sidebar.subheader("Mash")
    r["grain_mass_kg"] = st.sidebar.number_input(
        "Grain mass (kg)",
        min_value=0.5,
        max_value=50.0,
        value=float(r.get("grain_mass_kg", 6.0)),
        step=0.5,
    )
    r["extract_potential"] = st.sidebar.number_input(
        "Extract potential (fraction)",
        min_value=0.5,
        max_value=0.95,
        value=float(r.get("extract_potential", 0.80)),
        step=0.01,
    )
    r["water_to_grain_ratio_l_per_kg"] = st.sidebar.number_input(
        "Water-to-grain ratio (L/kg)",
        min_value=1.0,
        max_value=6.0,
        value=float(r.get("water_to_grain_ratio_l_per_kg", 3.0)),
        step=0.5,
    )
    r["grain_temperature_degC"] = st.sidebar.number_input(
        "Grain temperature (°C)",
        min_value=0.0,
        max_value=40.0,
        value=float(r.get("grain_temperature_degC", 20.0)),
        step=1.0,
    )
    r["target_mash_temperature_degC"] = st.sidebar.number_input(
        "Target mash temperature (°C)",
        min_value=45.0,
        max_value=78.0,
        value=float(r.get("target_mash_temperature_degC", 65.0)),
        step=1.0,
    )
    r["mash_duration_minutes"] = st.sidebar.number_input(
        "Mash duration (min)",
        min_value=15.0,
        max_value=180.0,
        value=float(r.get("mash_duration_minutes", 60.0)),
        step=5.0,
    )
    r["batch_size_liters"] = st.sidebar.number_input(
        "Batch size (L)",
        min_value=5.0,
        max_value=100.0,
        value=float(r.get("batch_size_liters", 20.0)),
        step=1.0,
    )

    st.sidebar.subheader("Water chemistry")
    w = r.get("water", {})
    w["calcium_mg_per_l"] = st.sidebar.number_input(
        "Calcium (mg/L)",
        min_value=0.0,
        max_value=500.0,
        value=float(w.get("calcium_mg_per_l", 50.0)),
        step=1.0,
    )
    w["magnesium_mg_per_l"] = st.sidebar.number_input(
        "Magnesium (mg/L)",
        min_value=0.0,
        max_value=100.0,
        value=float(w.get("magnesium_mg_per_l", 10.0)),
        step=1.0,
    )
    w["bicarbonate_mg_per_l"] = st.sidebar.number_input(
        "Bicarbonate (mg/L)",
        min_value=0.0,
        max_value=500.0,
        value=float(w.get("bicarbonate_mg_per_l", 150.0)),
        step=1.0,
    )
    r["water"] = w

    st.sidebar.subheader("Boil")
    b = r.get("boil", {})
    b["pre_boil_volume_liters"] = st.sidebar.number_input(
        "Pre-boil volume (L)",
        min_value=10.0,
        max_value=100.0,
        value=float(b.get("pre_boil_volume_liters", 26.0)),
        step=1.0,
    )
    b["boil_off_rate_l_per_hr"] = st.sidebar.number_input(
        "Boil-off rate (L/hr)",
        min_value=0.0,
        max_value=20.0,
        value=float(b.get("boil_off_rate_l_per_hr", 4.0)),
        step=0.5,
    )
    b["boil_duration_minutes"] = st.sidebar.number_input(
        "Boil duration (min)",
        min_value=15.0,
        max_value=180.0,
        value=float(b.get("boil_duration_minutes", 60.0)),
        step=5.0,
    )

    hops = b.get("hops", [])
    st.sidebar.write("Hop additions")
    new_hops = []
    for i, hop in enumerate(hops):
        cols = st.sidebar.columns(3)
        amount = cols[0].number_input(
            f"Hop {i + 1} amount (kg)",
            min_value=0.0,
            max_value=1.0,
            value=float(hop.get("amount_kg", 0.05)),
            step=0.005,
            key=f"hop_amt_{i}",
        )
        alpha = (
            cols[1].number_input(
                f"Hop {i + 1} alpha (%)",
                min_value=0.0,
                max_value=20.0,
                value=float(hop.get("alpha_acid", 0.055)) * 100.0,
                step=0.5,
                key=f"hop_alpha_{i}",
            )
            / 100.0
        )
        time_min = cols[2].number_input(
            f"Hop {i + 1} time (min)",
            min_value=0,
            max_value=120,
            value=int(hop.get("time_minutes", 60)),
            step=5,
            key=f"hop_time_{i}",
        )
        new_hops.append({"amount_kg": amount, "alpha_acid": alpha, "time_minutes": time_min})
    b["hops"] = new_hops
    r["boil"] = b

    st.sidebar.subheader("Ferment")
    f = r.get("ferment", {})
    f["temperature_degC"] = st.sidebar.number_input(
        "Ferment temperature (°C)",
        min_value=10.0,
        max_value=30.0,
        value=float(f.get("temperature_degC", 20.0)),
        step=1.0,
    )
    f["duration_hours"] = st.sidebar.number_input(
        "Duration (hours)",
        min_value=12.0,
        max_value=240.0,
        value=float(f.get("duration_hours", 72.0)),
        step=12.0,
    )
    f["initial_yeast_g_per_l"] = st.sidebar.number_input(
        "Initial yeast (g/L)",
        min_value=0.01,
        max_value=2.0,
        value=float(f.get("initial_yeast_g_per_l", 0.1)),
        step=0.01,
    )
    f["volume_liters"] = st.sidebar.number_input(
        "Volume (L)",
        min_value=5.0,
        max_value=100.0,
        value=float(f.get("volume_liters", 20.0)),
        step=1.0,
    )
    r["ferment"] = f

    return r


def _render_results(result: dict[str, Any]) -> None:
    summary = result.get("summary", {})
    mash = result.get("mash", {})
    boil = result.get("boil", {})
    ferment = result.get("ferment", {})

    st.header("Results")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("OG (°Plato)", f"{summary.get('og_plato')}")
    c2.metric("FG (°Plato)", f"{summary.get('fg_plato')}")
    c3.metric("ABV (%)", f"{summary.get('abv_percent')}")
    c4.metric("IBU", f"{summary.get('ibu')}")
    c5, c6 = st.columns(2)
    c5.metric("Volume (L)", f"{summary.get('volume_liters')}")
    c6.metric("Attenuation", f"{summary.get('attenuation')}")

    st.subheader("Mash")
    st.json(mash)

    st.subheader("Boil")
    st.json(boil)

    st.subheader("Ferment")
    st.json(ferment)

    st.subheader("Full result")
    st.json(result)


def _render_recipe_editor(store: JsonRepository[dict[str, Any]]) -> None:
    st.header("Save / load recipe")
    col1, col2 = st.columns(2)
    with col1:
        recipe_id = st.text_input("Recipe id", value="my-recipe")
        if st.button("Save recipe"):
            if "recipe" not in st.session_state:
                st.error("No recipe to save yet.")
            else:
                item = dict(st.session_state["recipe"])
                item["id"] = recipe_id
                store.add(item)
                st.success(f"Saved recipe '{recipe_id}'.")
    with col2:
        if st.button("List saved recipes"):
            items = store.list()
            ids = [i.get("id") if isinstance(i, dict) else getattr(i, "id", None) for i in items]
            st.write(ids if ids else "(none)")

    load_id = st.text_input("Load recipe id", value="my-recipe")
    if st.button("Load recipe"):
        loaded = store.get(load_id)
        if loaded is None:
            st.error(f"No recipe with id '{load_id}'.")
        else:
            st.session_state["recipe"] = loaded
            st.success(f"Loaded recipe '{load_id}'.")


def main() -> None:
    st.set_page_config(page_title="BrewLab", page_icon=":beer:", layout="wide")
    st.title("BrewLab — Brewing Digital Twin")
    st.caption("Physics-based brewing simulation and recipe optimization.")

    if "recipe" not in st.session_state:
        st.session_state["recipe"] = _default_recipe()

    store = JsonRepository[dict[str, Any]](STORE_DIR)

    recipe = _sidebar_inputs(st.session_state["recipe"])
    st.session_state["recipe"] = recipe

    if st.sidebar.button("Run simulation", type="primary"):
        try:
            result = simulate_batch(recipe)
            st.session_state["result"] = result.as_dict()
        except Exception as exc:  # noqa: BLE001 — surface to user
            st.error(f"Simulation failed: {exc}")
            return

    if "result" in st.session_state:
        _render_results(st.session_state["result"])

    st.divider()
    _render_recipe_editor(store)


if __name__ == "__main__":
    main()
