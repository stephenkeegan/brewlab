"""BrewLab GUI — Streamlit app for recipe input, simulation, and visualization.

Separate from the scientific core per the project's strict boundary: this
module only imports from ``brewlab.simulation`` and ``brewlab.persistence``.
Run with:

    streamlit run src/brewlab/gui/app.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd  # type: ignore[import-untyped]
import streamlit as st

from brewlab.core.fermentation import fermentation_time_series
from brewlab.persistence.json_repo import JsonRepository
from brewlab.simulation.engine import simulate_batch
from brewlab.units import ureg

STORE_DIR = Path(".brewlab_store_gui")

FLAVOR_DIMS = [
    ("Bitterness", "ibu"),
    ("Sweetness", "sweetness"),
    ("Body", "body"),
    ("Alcohol warmth", "alcohol"),
    ("Dryness", "dryness"),
    ("Hop aroma", "hop_aroma"),
]

_FLAVOR_MAX = {
    "ibu": 60.0,
    "sweetness": 8.0,
    "body": 22.0,
    "alcohol": 7.0,
    "dryness": 1.0,
    "hop_aroma": 1.0,
}


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


def _flavor_scores(result: dict[str, Any]) -> dict[str, float]:
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
        "ibu": ibu,
        "sweetness": max(og - fg, 0.0),
        "body": og,
        "alcohol": abv,
        "dryness": attenuation,
        "hop_aroma": aroma_frac,
    }


def _flavor_df(results: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, result in results.items():
        scores = _flavor_scores(result)
        for dim, key in FLAVOR_DIMS:
            raw = scores.get(key, 0.0)
            maximum = _FLAVOR_MAX[key]
            score = min(raw / maximum, 1.0) * 100.0
            rows.append({"scenario": name, "dimension": dim, "score": score})
    return pd.DataFrame(rows)


def _metrics_df(results: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, result in results.items():
        s = result.get("summary", {})
        rows.append(
            {
                "scenario": name,
                "og_plato": float(s.get("og_plato") or 0.0),
                "fg_plato": float(s.get("fg_plato") or 0.0),
                "abv_percent": float(s.get("abv_percent") or 0.0),
                "ibu": float(s.get("ibu") or 0.0),
                "attenuation": float(s.get("attenuation") or 0.0),
                "volume_liters": float(s.get("volume_liters") or 0.0),
            }
        )
    return pd.DataFrame(rows)


def _ferment_df(
    results: dict[str, dict[str, Any]], recipes: dict[str, dict[str, Any]]
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, result in results.items():
        recipe = recipes.get(name, {})
        ferment = recipe.get("ferment", {})
        boil = result.get("boil", {})
        post_boil_plato = float(boil.get("post_boil_plato") or 0.0)
        initial_sugar = post_boil_plato * 10.0
        volume = float(ferment.get("volume_liters", 20.0))
        temp = float(ferment.get("temperature_degC", 20.0))
        duration = float(ferment.get("duration_hours", 72.0))
        yeast = float(ferment.get("initial_yeast_g_per_l", 0.1))
        try:
            ts = fermentation_time_series(
                ureg.Quantity(initial_sugar, "gram / liter"),
                ureg.Quantity(yeast, "gram / liter"),
                ureg.Quantity(volume, "liter"),
                ureg.Quantity(temp, "degC"),
                ureg.Quantity(duration, "hour"),
            )
        except Exception:
            continue
        times = ts.get("time_hours", [])
        for key, label in (
            ("sugar_g_per_L", "Sugar (g/L)"),
            ("ethanol_g_per_L", "Ethanol (g/L)"),
            ("yeast_g_per_L", "Yeast (g/L)"),
            ("co2_g_per_L", "CO2 (g/L)"),
        ):
            values = ts.get(key, [])
            for t, v in zip(times, values, strict=False):
                rows.append(
                    {"scenario": name, "time_hours": float(t), "variable": label, "value": float(v)}
                )
    return pd.DataFrame(rows)


def _bitterness_df(results: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, result in results.items():
        boil = result.get("boil", {})
        for hop in boil.get("hop_additions", []):
            rows.append(
                {
                    "scenario": name,
                    "hop": f"{int(hop.get('time_minutes', 0))} min",
                    "ibu": float(hop.get("ibu", 0.0)),
                }
            )
    return pd.DataFrame(rows)


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
    new_hops: list[dict[str, Any]] = []
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


def _run_all(scenarios: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for name, recipe in scenarios.items():
        try:
            result = simulate_batch(recipe)
            results[name] = result.as_dict()
        except Exception as exc:  # noqa: BLE001 — surface to user
            st.error(f"Scenario '{name}' failed: {exc}")
    return results


def _render_overview(results: dict[str, dict[str, Any]], selection: list[str]) -> None:
    st.header("Overview — compare scenarios")
    df = _metrics_df({k: v for k, v in results.items() if k in selection})
    if df.empty:
        st.info("Run simulations to compare.")
        return
    c1, c2, c3, c4 = st.columns(4)
    agg = df.mean(numeric_only=True)
    c1.metric("Avg OG (°Plato)", f"{agg.get('og_plato', 0):.2f}")
    c2.metric("Avg FG (°Plato)", f"{agg.get('fg_plato', 0):.2f}")
    c3.metric("Avg ABV (%)", f"{agg.get('abv_percent', 0):.2f}")
    c4.metric("Avg IBU", f"{agg.get('ibu', 0):.1f}")

    melted = df.melt(id_vars=["scenario"], var_name="metric", value_name="value")
    chart = (
        alt.Chart(melted)
        .mark_bar()
        .encode(
            x=alt.X("metric:N", sort="-y", title="Metric"),
            y=alt.Y("value:Q", title="Value"),
            color=alt.Color("scenario:N", title="Scenario"),
            column=alt.Column("scenario:N", title="Scenario"),
        )
        .properties(width=120, height=250)
    )
    st.altair_chart(chart, use_container_width=True)

    st.subheader("Metrics table")
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_flavor(results: dict[str, dict[str, Any]], selection: list[str]) -> None:
    st.header("Flavor profile — compare scenarios")
    df = _flavor_df({k: v for k, v in results.items() if k in selection})
    if df.empty:
        st.info("Run simulations to compare flavor profiles.")
        return
    st.caption(
        "Each dimension is normalized 0-100 from the simulation outputs "
        "(bitterness from IBU, sweetness from OG−FG, body from OG, alcohol from ABV, "
        "dryness from attenuation, hop aroma from late-hop IBU share)."
    )
    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("dimension:N", sort=[dim for dim, _ in FLAVOR_DIMS], title="Flavor dimension"),
            y=alt.Y("score:Q", title="Score (0-100)", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color("scenario:N", title="Scenario"),
            tooltip=["scenario", "dimension", alt.Tooltip("score:Q", format=".1f")],
        )
        .properties(height=300)
        .interactive()
    )
    st.altair_chart(chart, use_container_width=True)

    st.subheader("Flavor matrix")
    pivot = df.pivot_table(index="scenario", columns="dimension", values="score", aggfunc="first")
    st.dataframe(pivot.round(1), use_container_width=True)


def _render_fermentation(
    results: dict[str, dict[str, Any]],
    recipes: dict[str, dict[str, Any]],
    selection: list[str],
) -> None:
    st.header("Fermentation kinetics — time course")
    df = _ferment_df({k: v for k, v in results.items() if k in selection}, recipes)
    if df.empty:
        st.info("No fermentation time-course data available.")
        return
    variable = st.selectbox("Variable", sorted(df["variable"].unique()), index=0)
    sub = df[df["variable"] == variable]
    chart = (
        alt.Chart(sub)
        .mark_line(point=True)
        .encode(
            x=alt.X("time_hours:Q", title="Time (hours)"),
            y=alt.Y("value:Q", title=variable),
            color=alt.Color("scenario:N", title="Scenario"),
            tooltip=["scenario", "time_hours", alt.Tooltip("value:Q", format=".2f")],
        )
        .properties(height=300)
        .interactive()
    )
    st.altair_chart(chart, use_container_width=True)


def _render_bitterness(results: dict[str, dict[str, Any]], selection: list[str]) -> None:
    st.header("Bitterness breakdown — by hop addition")
    df = _bitterness_df({k: v for k, v in results.items() if k in selection})
    if df.empty:
        st.info("No hop data available.")
        return
    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("scenario:N", title="Scenario"),
            y=alt.Y("ibu:Q", title="IBU"),
            color=alt.Color("hop:N", title="Hop addition"),
            tooltip=["scenario", "hop", alt.Tooltip("ibu:Q", format=".1f")],
        )
        .properties(height=300)
        .interactive()
    )
    st.altair_chart(chart, use_container_width=True)


def _render_scenario_manager() -> tuple[dict[str, dict[str, Any]], str]:
    st.sidebar.header("Scenarios")
    if "scenarios" not in st.session_state:
        st.session_state["scenarios"] = {"Default": _default_recipe()}
    if "active_scenario" not in st.session_state:
        st.session_state["active_scenario"] = "Default"

    scenarios = st.session_state["scenarios"]
    active = st.session_state["active_scenario"]

    sig = tuple(sorted((name, str(recipe)) for name, recipe in scenarios.items()))
    if st.session_state.get("scenario_sig") != sig:
        st.session_state["results"] = {}
    st.session_state["scenario_sig"] = sig

    new_name = st.sidebar.text_input("New scenario name", value="")
    if st.sidebar.button("Add scenario"):
        name = new_name.strip() or f"Scenario {len(scenarios) + 1}"
        if name in scenarios:
            st.sidebar.error(f"Scenario '{name}' already exists.")
        else:
            scenarios[name] = _default_recipe()
            st.session_state["active_scenario"] = name
            st.rerun()

    names = list(scenarios.keys())
    if names:
        active = st.sidebar.selectbox(
            "Edit scenario", names, index=names.index(active) if active in names else 0
        )
        st.session_state["active_scenario"] = active
        col_del, col_dup = st.sidebar.columns(2)
        if col_del.button("Delete scenario", use_container_width=True) and len(scenarios) > 1:
            del scenarios[active]
            remaining = list(scenarios.keys())
            st.session_state["active_scenario"] = remaining[0]
            st.rerun()
        if col_dup.button("Duplicate scenario", use_container_width=True):
            scenarios[f"{active} (copy)"] = dict(scenarios[active])
            st.session_state["active_scenario"] = f"{active} (copy)"
            st.rerun()

    if st.sidebar.button("Run all simulations", type="primary", use_container_width=True):
        st.session_state["results"] = _run_all(scenarios)
        st.sidebar.success(f"Ran {len(scenarios)} scenario(s).")

    return scenarios, active


def main() -> None:
    st.set_page_config(page_title="BrewLab", page_icon=":beer:", layout="wide")
    st.title("BrewLab — Brewing Digital Twin")
    st.caption("Interactive recipe simulation and multi-scenario comparison.")

    scenarios, active = _render_scenario_manager()

    recipe = scenarios.get(active, _default_recipe())
    recipe = _sidebar_inputs(recipe)
    scenarios[active] = recipe
    st.session_state["scenarios"] = scenarios

    results = st.session_state.get("results", {})
    selection = st.multiselect(
        "Scenarios to include in charts",
        options=list(scenarios.keys()),
        default=list(scenarios.keys()),
    )

    if results:
        tab_overview, tab_flavor, tab_ferment, tab_bitter = st.tabs(
            ["Overview", "Flavor profile", "Fermentation", "Bitterness"]
        )
        with tab_overview:
            _render_overview(results, selection)
        with tab_flavor:
            _render_flavor(results, selection)
        with tab_ferment:
            _render_fermentation(results, scenarios, selection)
        with tab_bitter:
            _render_bitterness(results, selection)
    else:
        st.info("Configure scenarios in the sidebar, then click **Run all simulations**.")

    st.divider()
    st.header("Save / load recipes")
    store = JsonRepository[dict[str, Any]](STORE_DIR)
    col1, col2 = st.columns(2)
    with col1:
        recipe_id = st.text_input("Recipe id", value="my-recipe")
        if st.button("Save current scenario"):
            item = dict(scenarios.get(active, {}))
            item["id"] = recipe_id
            store.add(item)
            st.success(f"Saved '{recipe_id}'.")
    with col2:
        if st.button("List saved recipes"):
            items = store.list()
            ids = [i.get("id") if isinstance(i, dict) else getattr(i, "id", None) for i in items]
            st.write(ids if ids else "(none)")
    load_id = st.text_input("Load recipe id", value="my-recipe", key="load_id")
    if st.button("Load recipe into current scenario"):
        loaded = store.get(load_id)
        if loaded is None:
            st.error(f"No recipe with id '{load_id}'.")
        else:
            scenarios[active] = loaded
            st.session_state["scenarios"] = scenarios
            st.success(f"Loaded '{load_id}' into '{active}'.")


if __name__ == "__main__":
    main()
