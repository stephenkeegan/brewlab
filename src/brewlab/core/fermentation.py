"""Fermentation: yeast growth, substrate consumption, ethanol/CO2 (Phase 3).

Models implemented here:
    monod_growth_rate        mechanistic-structured (Monod + temperature factor)
    fermentation_time_series mechanistic-structured (Luedeking-Piret ODE batch)
    predicted_attenuation    mechanistic-structured (extract consumed)
    predicted_abv            empirical  (ABV from ethanol concentration)

Yeast growth and ethanol formation are modeled as a batch ODE system solved
with ``scipy.integrate.solve_ivp``:

    mu(T,S) = mu_max * fT(T) * S/(Ks + S)                     [Monod]
    dX/dt   = mu * X                                          [yeast growth]
    dP/dt   = (alpha*mu + beta) * X                           [ethanol, Luedeking-Piret]
    dS/dt   = -(1/Yxs)*mu*X - dP/dt / Yps_theoretical         [sugar consumed]

where CO2 is stoichiometrically tied to ethanol (C6H12O6 -> 2 C2H5OH + 2 CO2;
mass ratio CO2/ethanol = 88/92 ≈ 0.957).

All kinetic parameters (mu_max, Ks, Yxs, alpha, beta, Topt, ...) are
calibration targets and must be fit to measured fermentation curves for a
given yeast strain/equipment. Defaults are placeholders.

Classification: growth/ethanol/substrate balances mechanistic-structured
(Luedeking-Piret is a standard, defensible fermentation model); ABV from
ethanol concentration empirical; temperature factor empirical.
"""

from __future__ import annotations

import math
from typing import Any

from scipy.integrate import solve_ivp  # type: ignore[import-untyped]

from brewlab.units import Quantity, ureg

# Default calibration targets -- NOT established constants; fit per strain/system.
_DEFAULT_MU_MAX = 0.4  # 1/hour, max specific growth rate at Topt
_DEFAULT_KS = 2.0  # gram / liter, Monod half-saturation
_DEFAULT_YXS = 0.10  # gram yeast / gram sugar, biomass yield
_DEFAULT_ALPHA = 0.5  # gram ethanol / gram yeast (growth-associated)
_DEFAULT_BETA = 0.02  # gram ethanol / (gram yeast * hour), non-growth-associated
_DEFAULT_YPS = 0.511  # gram ethanol / gram sugar, theoretical (92/180)
_DEFAULT_CO2_RATIO = 88.0 / 92.0  # gram CO2 / gram ethanol, stoichiometric
_DEFAULT_TOPT = 20.0  # degC, yeast temperature optimum (strain-dependent)
_DEFAULT_TSIGMA = 8.0  # degC, temperature-response width
_DEFAULT_INITIAL_YEAST = 0.1  # gram / liter, pitching rate

# Public aliases for consumers (e.g. CLI) that need default parameter values.
DEFAULT_MU_MAX = _DEFAULT_MU_MAX
DEFAULT_KS = _DEFAULT_KS
DEFAULT_YXS = _DEFAULT_YXS
DEFAULT_ALPHA = _DEFAULT_ALPHA
DEFAULT_BETA = _DEFAULT_BETA
DEFAULT_YPS = _DEFAULT_YPS
DEFAULT_TOPT = _DEFAULT_TOPT
DEFAULT_TSIGMA = _DEFAULT_TSIGMA
DEFAULT_INITIAL_YEAST = _DEFAULT_INITIAL_YEAST


def _temperature_factor(temperature: Quantity, topt: float, tsigma: float) -> float:
    """Gaussian temperature response centered at Topt (empirical).

    temp_factor(T) = exp(-((T - Topt)^2) / (2 * Tsigma^2)), in (0, 1].

    Classification: empirical.
    """
    t = temperature.to("degC").magnitude
    return math.exp(-((t - topt) ** 2) / (2.0 * tsigma * tsigma))


def monod_growth_rate(
    mu_max: Quantity,
    ks: Quantity,
    substrate: Quantity,
    temperature: Quantity,
    topt: float = _DEFAULT_TOPT,
    tsigma: float = _DEFAULT_TSIGMA,
) -> Quantity:
    """Specific growth rate mu(T,S) = mu_max * fT(T) * S/(Ks + S) (1/hour).

    Classification: mechanistic-structured (Monod); mu_max/Ks are calibration
    targets; temperature factor empirical.
    """
    mu_max_v = mu_max.to("1 / hour").magnitude
    ks_v = ks.to("gram / liter").magnitude
    s_v = substrate.to("gram / liter").magnitude
    temp_factor = _temperature_factor(temperature, topt, tsigma)
    denom = ks_v + s_v
    mu = mu_max_v * temp_factor * (s_v / denom) if denom > 0 else 0.0
    return ureg.Quantity(mu, "1 / hour")


def _fermentation_ode(
    t: float,
    y: list[float],
    mu_max: float,
    temp_factor: float,
    ks: float,
    yxs: float,
    alpha: float,
    beta: float,
    yps: float,
) -> list[float]:
    x, s, p = y  # yeast g/L, sugar g/L, ethanol g/L
    if s <= 0.0:
        return [0.0, 0.0, 0.0]
    mu = mu_max * temp_factor * (s / (ks + s)) if (ks + s) > 0 else 0.0
    dxdt = mu * x
    dpdt = (alpha * mu + beta) * x
    dsdt = -(1.0 / yxs) * mu * x - dpdt / yps
    return [dxdt, dsdt, dpdt]


def fermentation_time_series(
    initial_sugar: Quantity,
    initial_yeast: Quantity,
    volume: Quantity,
    temperature: Quantity,
    duration_hours: Quantity,
    mu_max: Quantity = _DEFAULT_MU_MAX * ureg.Quantity(1, "1 / hour"),
    ks: Quantity = _DEFAULT_KS * ureg.Quantity(1, "gram / liter"),
    yxs: Quantity = _DEFAULT_YXS * ureg.dimensionless,
    alpha: Quantity = _DEFAULT_ALPHA * ureg.dimensionless,
    beta: Quantity = _DEFAULT_BETA * ureg.dimensionless,
    yps: Quantity = _DEFAULT_YPS * ureg.dimensionless,
    attenuation_min: Quantity | None = None,
    attenuation_max: Quantity | None = None,
    temperature_min: Quantity | None = None,
    temperature_max: Quantity | None = None,
) -> dict[str, Any]:
    """Simulate batch fermentation over ``duration_hours``.

    Returns a dict with time series (hours) and final values for yeast (g/L),
    sugar (g/L), ethanol (g/L), CO2 (g/L), attenuation (fraction), and
    predicted FG (°Plato) / ABV.

    If ``attenuation_min``/``attenuation_max`` are given (from a yeast
    strain), predicted attenuation is clamped to that range and FG/ABV are
    recomputed from the clamped attenuation. If ``temperature_min``/
    ``temperature_max`` are given and the ferment temperature falls outside,
    ``temperature_warning`` is set.

    Classification: mechanistic-structured ODE; parameters are calibration
    targets.
    """
    s0 = initial_sugar.to("gram / liter").magnitude
    x0 = initial_yeast.to("gram / liter").magnitude
    t_span = (0.0, duration_hours.to("hour").magnitude)
    temp_factor = _temperature_factor(temperature, _DEFAULT_TOPT, _DEFAULT_TSIGMA)

    sol = solve_ivp(
        _fermentation_ode,
        t_span,
        [x0, s0, 0.0],
        args=(
            mu_max.to("1 / hour").magnitude,
            temp_factor,
            ks.to("gram / liter").magnitude,
            yxs.to("dimensionless").magnitude,
            alpha.to("dimensionless").magnitude,
            beta.to("dimensionless").magnitude,
            yps.to("dimensionless").magnitude,
        ),
        dense_output=True,
        rtol=1e-8,
        atol=1e-10,
    )

    t = sol.t
    x = sol.y[0]
    s = sol.y[1]
    p = sol.y[2]
    co2 = p * _DEFAULT_CO2_RATIO

    raw_attenuation = (s0 - max(s[-1], 0.0)) / s0 if s0 > 0 else 0.0

    attenuation_min_v = (
        attenuation_min.to("dimensionless").magnitude if attenuation_min is not None else None
    )
    attenuation_max_v = (
        attenuation_max.to("dimensionless").magnitude if attenuation_max is not None else None
    )
    attenuation = raw_attenuation
    if attenuation_min_v is not None and attenuation < attenuation_min_v:
        attenuation = attenuation_min_v
    if attenuation_max_v is not None and attenuation > attenuation_max_v:
        attenuation = attenuation_max_v

    # Recompute residual sugar, FG, ethanol, ABV from clamped attenuation.
    residual_sugar_g_per_l = s0 * (1.0 - attenuation)
    fg_plato = max(residual_sugar_g_per_l / 10.0, 0.0)
    ethanol_g_per_l = max((s0 - residual_sugar_g_per_l) * yps.to("dimensionless").magnitude, 0.0)
    abv = ethanol_g_per_l / 7.89

    temperature_warning = False
    if temperature_min is not None:
        temperature_warning = temperature_warning or (
            temperature.to("degC").magnitude < temperature_min.to("degC").magnitude
        )
    if temperature_max is not None:
        temperature_warning = temperature_warning or (
            temperature.to("degC").magnitude > temperature_max.to("degC").magnitude
        )

    return {
        "time_hours": t.tolist(),
        "yeast_g_per_L": x.tolist(),
        "sugar_g_per_L": s.tolist(),
        "ethanol_g_per_L": p.tolist(),
        "co2_g_per_L": co2.tolist(),
        "final_attenuation": float(attenuation),
        "final_fg_plato": float(fg_plato),
        "final_abv_percent": float(abv),
        "final_ethanol_g_per_L": float(ethanol_g_per_l),
        "raw_attenuation": float(raw_attenuation),
        "temperature_warning": bool(temperature_warning),
        "model_contributions": {
            "kinetics": "Monod growth + Luedeking-Piret ethanol + stoichiometric CO2",
        },
    }


__all__ = [
    "monod_growth_rate",
    "fermentation_time_series",
]
