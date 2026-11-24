"""BrewLab GUI — Streamlit app for recipe input, simulation, and visualization.

Separate from the scientific core per the project's strict boundary: this
module only imports from ``brewlab.simulation``, ``brewlab.persistence``,
``brewlab.domain`` and ``brewlab.units``.
Run with:

    streamlit run src/brewlab/gui/app.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd  # type: ignore[import-untyped]
import streamlit as st

from brewlab.core.fermentation import fermentation_time_series
from brewlab.domain.yeast_library import YeastLibrary
from brewlab.persistence.json_repo import JsonRepository
from brewlab.simulation.engine import simulate_batch
from brewlab.simulation.flavor_engine import (
    FlavorLogger,
    FlavorTarget,
    _normalize,
    _raw_flavor_scores,
    backpropagate_flavor,
    explore_and_log,
)
from brewlab.simulation.solution_space import explore_solution_space
from brewlab.units import ureg

STORE_DIR = Path(".brewlab_store_gui")
TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "recipes" / "templates"

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

_RANGE_PARAMS = [
    ("grain_mass_kg", "Grain mass (kg)", 0.5, 50.0, 0.5),
    ("extract_potential", "Extract potential (fraction)", 0.5, 0.95, 0.01),
    ("target_mash_temperature_degC", "Target mash temp (°C)", 45.0, 78.0, 1.0),
    ("ferment_temperature_degC", "Ferment temp (°C)", 10.0, 30.0, 1.0),
    ("bittering_hop_amount_kg", "Bittering hop amount (kg)", 0.0, 0.2, 0.005),
]


def _load_template_recipes() -> dict[str, dict[str, Any]]:
    """Load all preloaded benchmark recipes from recipes/templates/."""
    templates: dict[str, dict[str, Any]] = {}
    if not TEMPLATES_DIR.exists():
        return templates
    for path in sorted(TEMPLATES_DIR.glob("*.json")):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            name = data.get("name", path.stem.replace("_", " ").title())
            templates[name] = data
        except Exception:  # noqa: BLE001 — skip malformed templates
            continue
    return templates


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
        "grain_color_lovibond": 2.5,
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
            "yeast_strain_id": "US-05",
        },
    }


def _flavor_exploration_recipe() -> dict[str, Any]:
    """Base recipe with ranges used for flavor exploration sampling."""
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
                {
                    "amount_kg": {"min": 0.03, "max": 0.09},
                    "alpha_acid": 0.060,
                    "time_minutes": 60,
                },
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
                "srm": float(s.get("srm") or 0.0),
                "chloride_sulfate_ratio": float(s.get("chloride_sulfate_ratio") or 0.0),
                "attenuation": float(s.get("attenuation") or 0.0),
                "volume_liters": float(s.get("volume_liters") or 0.0),
            }
        )
    return pd.DataFrame(rows)


def _ferment_df(
    results: dict[str, dict[str, Any]],
    recipes: dict[str, dict[str, Any]],
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
                    {
                        "scenario": name,
                        "time_hours": float(t),
                        "variable": label,
                        "value": float(v),
                    }
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


def _solution_space_df(samples: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for sample in samples:
        s = sample.get("summary", {})
        rows.append(
            {
                "og_plato": float(s.get("og_plato") or 0.0),
                "fg_plato": float(s.get("fg_plato") or 0.0),
                "abv_percent": float(s.get("abv_percent") or 0.0),
                "ibu": float(s.get("ibu") or 0.0),
                "srm": float(s.get("srm") or 0.0),
                "attenuation": float(s.get("attenuation") or 0.0),
            }
        )
    return pd.DataFrame(rows)


def _sidebar_range_inputs(recipe: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Render min/max range inputs for confirmed range parameters."""
    r = dict(recipe)
    for key, label, min_v, max_v, step in _RANGE_PARAMS:
        current = r.get(key, min_v)
        if isinstance(current, dict) and "min" in current and "max" in current:
            cur_min = float(current["min"])
            cur_max = float(current["max"])
        else:
            cur_min = float(current)
            cur_max = float(current)
        cols = st.sidebar.columns(2)
        lo = cols[0].number_input(
            f"{label} min",
            min_value=min_v,
            max_value=max_v,
            value=cur_min,
            step=step,
            key=f"{prefix}{key}_min",
        )
        hi = cols[1].number_input(
            f"{label} max",
            min_value=min_v,
            max_value=max_v,
            value=cur_max,
            step=step,
            key=f"{prefix}{key}_max",
        )
        if lo > hi:
            hi = lo
        r[key] = {"min": lo, "max": hi}
    return r


def _sidebar_single_inputs(recipe: dict[str, Any], yeast_lib: YeastLibrary) -> dict[str, Any]:
    """Render single-value inputs for all recipe parameters."""
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
    r["grain_color_lovibond"] = st.sidebar.number_input(
        "Grain color (°Lovibond)",
        min_value=1.0,
        max_value=60.0,
        value=float(r.get("grain_color_lovibond", 2.5)),
        step=0.5,
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
    w["chloride_mg_per_l"] = st.sidebar.number_input(
        "Chloride (mg/L)",
        min_value=0.0,
        max_value=500.0,
        value=float(w.get("chloride_mg_per_l", 50.0)),
        step=1.0,
    )
    w["sulfate_mg_per_l"] = st.sidebar.number_input(
        "Sulfate (mg/L)",
        min_value=0.0,
        max_value=500.0,
        value=float(w.get("sulfate_mg_per_l", 50.0)),
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
    yeast_ids = yeast_lib.ids()
    current_yeast = f.get("yeast_strain_id", "US-05")
    yeast_index = yeast_ids.index(current_yeast) if current_yeast in yeast_ids else 0
    f["yeast_strain_id"] = st.sidebar.selectbox("Yeast strain", yeast_ids, index=yeast_index)
    r["ferment"] = f

    return r


def _run_single_scenarios(
    scenarios: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for name, recipe in scenarios.items():
        try:
            result = simulate_batch(recipe)
            results[name] = result.as_dict()
        except Exception as exc:  # noqa: BLE001 — surface to user
            st.error(f"Scenario '{name}' failed: {exc}")
    return results


def _run_solution_space(
    recipe: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        return explore_solution_space(recipe)
    except Exception as exc:  # noqa: BLE001 — surface to user
        st.error(f"Solution space exploration failed: {exc}")
        return None


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
    c5, c6 = st.columns(2)
    c5.metric("Avg SRM", f"{agg.get('srm', 0):.1f}")
    c6.metric("Avg Cl:SO4", f"{agg.get('chloride_sulfate_ratio', 0):.2f}")

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
            x=alt.X(
                "dimension:N",
                sort=[dim for dim, _ in FLAVOR_DIMS],
                title="Flavor dimension",
            ),
            y=alt.Y("score:Q", title="Score (0-100)", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color("scenario:N", title="Scenario"),
            tooltip=[
                "scenario",
                "dimension",
                alt.Tooltip("score:Q", format=".1f"),
            ],
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


def _render_solution_space(
    solution: dict[str, Any],
) -> None:
    st.header("Solution space — parameter range exploration")
    stats = solution.get("stats", {})
    samples = solution.get("samples", [])
    n_samples = solution.get("n_samples", 0)
    requested = solution.get("requested_samples", 0)
    st.caption(f"{n_samples} of {requested} requested samples simulated successfully.")

    if not samples:
        st.info("No solution space samples available.")
        return

    # Range bars per output: min to max, median marker.
    st.subheader("Output range bands")
    range_rows: list[dict[str, Any]] = []
    for key, stat in stats.items():
        if stat.get("min") is None:
            continue
        range_rows.append(
            {
                "output": key.replace("_", " ").title(),
                "min": stat["min"],
                "max": stat["max"],
                "median": stat["median"],
                "p10": stat["p10"],
                "p90": stat["p90"],
            }
        )
    range_df = pd.DataFrame(range_rows)
    if not range_df.empty:
        melted = range_df.melt(
            id_vars=["output"],
            value_vars=["min", "p10", "median", "p90", "max"],
            var_name="statistic",
            value_name="value",
        )
        chart = (
            alt.Chart(melted)
            .mark_point()
            .encode(
                x=alt.X("output:N", sort="-y", title="Output"),
                y=alt.Y("value:Q", title="Value"),
                color=alt.Color("statistic:N", title="Statistic"),
                tooltip=["output", "statistic", alt.Tooltip("value:Q", format=".2f")],
            )
            .properties(height=300)
            .interactive()
        )
        st.altair_chart(chart, use_container_width=True)

    # Sample scatter matrix: ABV vs IBU colored by attenuation.
    st.subheader("Sample scatter — ABV vs IBU")
    sample_df = pd.DataFrame(samples)
    if not sample_df.empty and "abv_percent" in sample_df.columns and "ibu" in sample_df.columns:
        scatter = (
            alt.Chart(sample_df)
            .mark_circle(size=60, opacity=0.7)
            .encode(
                x=alt.X("ibu:Q", title="IBU"),
                y=alt.Y("abv_percent:Q", title="ABV (%)"),
                color=alt.Color(
                    "attenuation:Q", title="Attenuation", scale=alt.Scale(scheme="viridis")
                ),
                tooltip=[
                    alt.Tooltip("ibu:Q", format=".1f"),
                    alt.Tooltip("abv_percent:Q", format=".2f"),
                    alt.Tooltip("attenuation:Q", format=".3f"),
                    alt.Tooltip("srm:Q", format=".1f"),
                ],
            )
            .properties(height=300)
            .interactive()
        )
        st.altair_chart(scatter, use_container_width=True)

    st.subheader("Sample table")
    show_cols = ["og_plato", "fg_plato", "abv_percent", "ibu", "srm", "attenuation"]
    available = [c for c in show_cols if c in sample_df.columns]
    st.dataframe(sample_df[available].round(3), use_container_width=True, hide_index=True)


def _flatten_sample(sample: dict[str, Any]) -> dict[str, Any]:
    """Flatten a logged sample into a single row of inputs + flavor scores."""
    ferment = sample.get("ferment", {})
    boil = sample.get("boil", {})
    hops = boil.get("hop_additions", [])
    bittering_kg = 0.0
    for h in hops:
        if int(h.get("time_minutes", 0)) >= 45:
            bittering_kg = float(h.get("amount_kg", 0.0))
            break
    summary = sample.get("summary", {})
    flavor = _normalize(_raw_flavor_scores({"summary": summary, "boil": boil}))
    return {
        "grain_mass_kg": float(sample.get("grain_mass_kg", 0.0)),
        "extract_potential": float(sample.get("extract_potential", 0.0)),
        "mash_temp_degC": float(sample.get("target_mash_temperature_degC", 0.0)),
        "ferment_temp_degC": float(ferment.get("temperature_degC", 0.0)),
        "bittering_hop_kg": bittering_kg,
        "yeast_strain": ferment.get("yeast_strain_id", ""),
        **flavor,
    }


def _render_flavor_impact(logged_samples: list[dict[str, Any]]) -> None:
    """Show how each input impacts each flavor dimension (correlation view)."""
    st.header("Input → flavor impact")
    if not logged_samples:
        st.info("Run flavor exploration to see input→flavor impact.")
        return
    rows = [_flatten_sample(s) for s in logged_samples]
    df = pd.DataFrame(rows)
    input_cols = [
        "grain_mass_kg",
        "extract_potential",
        "mash_temp_degC",
        "ferment_temp_degC",
        "bittering_hop_kg",
    ]
    flavor_cols = [
        "bitterness",
        "sweetness",
        "body",
        "alcohol",
        "dryness",
        "hop_aroma",
    ]
    col1, col2 = st.columns(2)
    with col1:
        x_input = st.selectbox("Input", input_cols, index=0, key="impact_x")
    with col2:
        y_flavor = st.selectbox("Flavor dimension", flavor_cols, index=0, key="impact_y")
    chart = (
        alt.Chart(df)
        .mark_circle(size=60, opacity=0.7)
        .encode(
            x=alt.X(f"{x_input}:Q", title=x_input.replace("_", " ").title()),
            y=alt.Y(f"{y_flavor}:Q", title=y_flavor.title()),
            tooltip=[
                alt.Tooltip(f"{x_input}:Q", format=".3f"),
                alt.Tooltip(f"{y_flavor}:Q", format=".1f"),
                "yeast_strain",
            ],
        )
        .properties(height=300)
        .interactive()
    )
    st.altair_chart(chart, use_container_width=True)

    # Correlation table
    corr_rows: list[dict[str, Any]] = []
    for inp in input_cols:
        for fl in flavor_cols:
            c = df[inp].corr(df[fl])
            corr_rows.append(
                {
                    "input": inp.replace("_", " ").title(),
                    "flavor": fl.title(),
                    "correlation": round(float(c), 3) if c == c else 0.0,
                }
            )
    corr_df = pd.DataFrame(corr_rows)
    st.subheader("Input–flavor correlation")
    st.dataframe(corr_df, use_container_width=True, hide_index=True)


def _render_target_flavor(logged_samples: list[dict[str, Any]], yeast_lib: YeastLibrary) -> None:
    """Target flavor sliders + back-propagation to recommended inputs."""
    st.header("Target flavor → recipe (back-propagation)")
    if not logged_samples:
        st.info(
            "Run flavor exploration first to build a sample base, then set a "
            "target flavor profile below."
        )
        return

    st.caption(
        "Set your desired flavor profile (0-100 each), then click "
        "**Back-propagate** to find recipe inputs that best match it."
    )

    # Target sliders
    cols = st.columns(3)
    target_vals: dict[str, float] = {}
    default_target = {
        "bitterness": 50.0,
        "sweetness": 50.0,
        "body": 50.0,
        "alcohol": 50.0,
        "dryness": 50.0,
        "hop_aroma": 50.0,
    }
    saved = st.session_state.get("flavor_target", default_target)
    for i, (dim, key) in enumerate(
        [
            ("Bitterness", "bitterness"),
            ("Sweetness", "sweetness"),
            ("Body", "body"),
            ("Alcohol warmth", "alcohol"),
            ("Dryness", "dryness"),
            ("Hop aroma", "hop_aroma"),
        ]
    ):
        with cols[i % 3]:
            target_vals[key] = st.slider(
                dim,
                min_value=0.0,
                max_value=100.0,
                value=float(saved.get(key, 50.0)),
                step=5.0,
                key=f"target_{key}",
            )
    st.session_state["flavor_target"] = target_vals

    target = FlavorTarget(**target_vals)

    col_run, col_refine = st.columns(2)
    with col_run:
        run_backprop = st.button("Back-propagate", type="primary", use_container_width=True)
    with col_refine:
        refine = st.toggle("Refine with optimizer", value=True)

    rec = st.session_state.get("flavor_recommendation")
    if run_backprop:
        input_bounds = {
            "grain_mass_kg": (0.5, 50.0),
            "extract_potential": (0.5, 0.95),
            "target_mash_temperature_degC": (45.0, 78.0),
            "ferment_temperature_degC": (10.0, 30.0),
            "bittering_hop_amount_kg": (0.0, 0.2),
        }
        try:
            rec = backpropagate_flavor(
                target,
                logged_samples,
                input_bounds=input_bounds,
                n_samples=int(st.session_state.get("n_flavor_samples", 100)),
                refine=refine,
            )
            st.session_state["flavor_recommendation"] = rec
        except Exception as exc:  # noqa: BLE001 — surface to user
            st.error(f"Back-propagation failed: {exc}")
            rec = None

    if rec is None:
        rec = st.session_state.get("flavor_recommendation")

    if rec:
        st.subheader("Recommended inputs")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Method", rec.method)
        c2.metric("Distance", f"{rec.distance:.2f}")
        c3.metric("Predicted bitterness", f"{rec.predicted.get('bitterness', 0):.0f}")
        c4.metric("Predicted ABV warmth", f"{rec.predicted.get('alcohol', 0):.0f}")

        st.write("**Predicted flavor (0-100):**")
        pred_cols = st.columns(3)
        for i, (dim, key) in enumerate(
            [
                ("Bitterness", "bitterness"),
                ("Sweetness", "sweetness"),
                ("Body", "body"),
                ("Alcohol warmth", "alcohol"),
                ("Dryness", "dryness"),
                ("Hop aroma", "hop_aroma"),
            ]
        ):
            with pred_cols[i % 3]:
                st.metric(dim, f"{rec.predicted.get(key, 0):.0f}")

        st.write("**Recommended recipe inputs:**")
        inputs = rec.inputs
        disp = {
            "Grain mass (kg)": inputs.get("grain_mass_kg"),
            "Extract potential": inputs.get("extract_potential"),
            "Mash temp (°C)": inputs.get("target_mash_temperature_degC"),
            "Ferment temp (°C)": (
                inputs.get("ferment", {}).get("temperature_degC")
                if isinstance(inputs.get("ferment"), dict)
                else None
            ),
            "Bittering hop (kg)": (
                inputs.get("boil", {}).get("hops", [{}])[0].get("amount_kg")
                if isinstance(inputs.get("boil"), dict)
                else None
            ),
            "Yeast strain": (
                inputs.get("ferment", {}).get("yeast_strain_id")
                if isinstance(inputs.get("ferment"), dict)
                else None
            ),
        }
        st.json(disp)

        if st.button("Apply recommendation to active scenario", use_container_width=True):
            scenarios = st.session_state.get("scenarios", {})
            active = st.session_state.get("active_scenario")
            if active and active in scenarios:
                scenarios[active] = inputs
                st.session_state["scenarios"] = scenarios
                st.session_state["results"] = {}
                st.session_state["solution"] = None
                st.session_state["flavor_recommendation"] = None
                st.success(
                    f"Applied recommendation to '{active}'. Run simulation(s) to see results."
                )
                st.rerun()
            else:
                st.error("No active scenario to apply to.")


def _render_recipe_editor(store: JsonRepository[dict[str, Any]]) -> None:
    st.header("Save / load recipe")
    col1, col2 = st.columns(2)
    with col1:
        recipe_id = st.text_input("Recipe id", value="my-recipe")
        if st.button("Save current scenario"):
            if "scenarios" not in st.session_state:
                st.error("No recipe to save yet.")
            else:
                active = st.session_state.get("active_scenario")
                scenarios = st.session_state.get("scenarios", {})
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
            scenarios = st.session_state.get("scenarios", {})
            active = st.session_state.get("active_scenario")
            scenarios[active] = loaded
            st.session_state["scenarios"] = scenarios
            st.success(f"Loaded '{load_id}' into '{active}'.")


def _render_scenario_manager() -> tuple[dict[str, dict[str, Any]], str, bool]:
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
        st.session_state["solution"] = None
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
            "Edit scenario",
            names,
            index=names.index(active) if active in names else 0,
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

    solution_space_mode = st.sidebar.toggle(
        "Solution space mode", value=False, help="Explore parameter ranges instead of single values"
    )

    if st.sidebar.button("Run simulation(s)", type="primary", use_container_width=True):
        if solution_space_mode:
            active_recipe = scenarios.get(active, {})
            st.session_state["solution"] = _run_solution_space(active_recipe)
            st.session_state["results"] = {}
        else:
            st.session_state["results"] = _run_single_scenarios(scenarios)
            st.session_state["solution"] = None

    st.sidebar.divider()
    st.sidebar.subheader("Flavor exploration")
    n_flavor_samples = st.sidebar.number_input(
        "Exploration samples",
        min_value=10,
        max_value=1000,
        value=int(st.session_state.get("n_flavor_samples", 100)),
        step=10,
        help="Randomized simulations to log for flavor back-propagation",
    )
    st.session_state["n_flavor_samples"] = n_flavor_samples
    if st.sidebar.button("Run flavor exploration", use_container_width=True):
        try:
            exploration = explore_and_log(
                _flavor_exploration_recipe(),
                n_samples=n_flavor_samples,
            )
            st.session_state["flavor_logged_count"] = exploration.get("logged_total", 0)
            st.session_state["flavor_recommendation"] = None
            st.sidebar.success(
                f"Logged {exploration.get('n_samples', 0)} samples "
                f"({exploration.get('logged_total', 0)} total)."
            )
        except Exception as exc:  # noqa: BLE001 — surface to user
            st.error(f"Flavor exploration failed: {exc}")
    logger_count = len(FlavorLogger().load())
    st.sidebar.caption(f"Logged flavor samples: {logger_count}")
    if st.sidebar.button("Clear exploration log", use_container_width=True):
        FlavorLogger().clear()
        st.session_state["flavor_logged_count"] = 0
        st.session_state["flavor_recommendation"] = None
        st.sidebar.success("Exploration log cleared.")
        st.rerun()

    st.sidebar.divider()
    st.sidebar.subheader("Benchmark templates")
    templates = _load_template_recipes()
    if templates:
        tmpl_name = st.sidebar.selectbox(
            "Load template", ["(none)"] + sorted(templates.keys()), key="tmpl_select"
        )
        col_load, col_load_all = st.sidebar.columns(2)
        if col_load.button("Load into active", use_container_width=True) and tmpl_name != "(none)":
            scenarios[active] = templates[tmpl_name]
            st.session_state["scenarios"] = scenarios
            st.session_state["results"] = {}
            st.session_state["solution"] = None
            st.sidebar.success(f"Loaded '{tmpl_name}' into '{active}'.")
            st.rerun()
        if col_load_all.button("Add all as scenarios", use_container_width=True):
            added = 0
            for name, recipe in templates.items():
                if name not in scenarios:
                    scenarios[name] = recipe
                    added += 1
            st.session_state["scenarios"] = scenarios
            st.session_state["results"] = {}
            st.session_state["solution"] = None
            st.sidebar.success(f"Added {added} template scenario(s).")
            st.rerun()
    else:
        st.sidebar.caption("No benchmark templates found.")

    return scenarios, active, solution_space_mode


def main() -> None:
    st.set_page_config(page_title="BrewLab", page_icon=":beer:", layout="wide")
    st.title("BrewLab — Brewing Digital Twin")
    st.caption("Interactive recipe simulation and multi-scenario comparison.")

    yeast_lib = YeastLibrary()
    scenarios, active, solution_space_mode = _render_scenario_manager()

    logged_samples = FlavorLogger().load()

    recipe = scenarios.get(active, _default_recipe())
    if solution_space_mode:
        recipe = _sidebar_range_inputs(recipe, prefix="ss_")
    else:
        recipe = _sidebar_single_inputs(recipe, yeast_lib)
    scenarios[active] = recipe
    st.session_state["scenarios"] = scenarios

    results = st.session_state.get("results", {})
    solution = st.session_state.get("solution")
    selection = st.multiselect(
        "Scenarios to include in charts",
        options=list(scenarios.keys()),
        default=list(scenarios.keys()),
    )

    if solution:
        (
            tab_solution,
            tab_flavor,
            tab_impact,
            tab_ferment,
            tab_bitter,
            tab_target,
        ) = st.tabs(
            [
                "Solution space",
                "Flavor profile",
                "Flavor impact",
                "Fermentation",
                "Bitterness",
                "Target flavor",
            ]
        )
        with tab_solution:
            _render_solution_space(solution)
        with tab_flavor:
            _render_flavor(results, selection)
        with tab_impact:
            _render_flavor_impact(logged_samples)
        with tab_ferment:
            _render_fermentation(results, scenarios, selection)
        with tab_bitter:
            _render_bitterness(results, selection)
        with tab_target:
            _render_target_flavor(logged_samples, yeast_lib)
    elif results:
        (
            tab_overview,
            tab_flavor,
            tab_impact,
            tab_ferment,
            tab_bitter,
            tab_target,
        ) = st.tabs(
            [
                "Overview",
                "Flavor profile",
                "Flavor impact",
                "Fermentation",
                "Bitterness",
                "Target flavor",
            ]
        )
        with tab_overview:
            _render_overview(results, selection)
        with tab_flavor:
            _render_flavor(results, selection)
        with tab_impact:
            _render_flavor_impact(logged_samples)
        with tab_ferment:
            _render_fermentation(results, scenarios, selection)
        with tab_bitter:
            _render_bitterness(results, selection)
        with tab_target:
            _render_target_flavor(logged_samples, yeast_lib)
    else:
        st.info(
            "Configure scenarios in the sidebar, then click "
            "**Run simulation(s)** or **Run flavor exploration**."
        )

    st.divider()
    st.header("Save / load recipes")
    store = JsonRepository[dict[str, Any]](STORE_DIR)
    _render_recipe_editor(store)


if __name__ == "__main__":
    main()
