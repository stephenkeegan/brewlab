"""Kinetics: ODE framework, Arrhenius rate law, mash enzymatics (Phase 1).

Models implemented here:
    arrhenius_rate              mechanistic  (k = A exp(-Ea/RT))
    gelatinization_factor       empirical    (starch gelatinization vs T)
    alpha_amylase_activity      empirical    (relative activity vs T)
    beta_amylase_activity       empirical    (relative activity vs T, denaturation)
    saccharification_rate       empirical-structured (first-order conversion)
    saccharification_conversion empirical-structured (X(t) = 1-exp(-kt))
    extract_plato               empirical    (grain bill + conversion -> degPlato)

The saccharification model combines a first-order conversion structure with an
empirical temperature-response profile. k_ref is calibrated to a typical
60-minute mash reaching ~80% starch conversion at 65 C. All enzyme
temperature-response curves are empirical and marked as such.
"""

from __future__ import annotations

import math

from brewlab.units import Quantity, ureg

# Empirical calibration: first-order rate constant (1/min) at 65 C chosen so a
# 60-minute mash reaches roughly 80 % conversion (X = 1-exp(-k t)).
_K_65C_PER_MIN = 0.037
_REF_TEMP = ureg.Quantity(65.0, "degC")


def _to_celsius(temperature: Quantity) -> float:
    return float(temperature.to("degC").magnitude)


def gelatinization_factor(temperature: Quantity) -> Quantity:
    """Fraction of starch gelatinized (accessible to enzymes) vs temperature.

    Onset ~52-55 C, substantially complete by 65-70 C. Modeled as a logistic
    centered near 60 C. No sharp phase boundary; real gelatinization depends on
    starch variety, water, and time.

    Classification: empirical.
    """
    t = _to_celsius(temperature)
    factor = 1.0 / (1.0 + math.exp(-(t - 60.0) / 6.0))
    return ureg.Quantity(factor, "dimensionless")


def alpha_amylase_activity(temperature: Quantity) -> Quantity:
    """Relative alpha-amylase activity vs temperature (optimum ~68-72 C).

    Alpha-amylase liquefies starch (random endohydrolysis). Modeled as a
    Gaussian centered at 70 C.

    Classification: empirical.
    """
    t = _to_celsius(temperature)
    act = math.exp(-((t - 70.0) ** 2) / (2.0 * 10.0**2))
    return ureg.Quantity(act, "dimensionless")


def beta_amylase_activity(temperature: Quantity) -> Quantity:
    """Relative beta-amylase activity vs temperature (optimum ~55-60 C).

    Beta-amylase produces maltose and denatures appreciably above ~65 C.
    Activity includes an exponential thermal-denaturation penalty above 65 C.

    Classification: empirical.
    """
    t = _to_celsius(temperature)
    act = math.exp(-((t - 58.0) ** 2) / (2.0 * 7.0**2))
    if t > 65.0:
        act *= math.exp(-(t - 65.0) / 5.0)
    return ureg.Quantity(act, "dimensionless")


def _combined_enzyme_activity(temperature: Quantity) -> float:
    """Weighted alpha/beta activity, dimensionless (0-1)."""
    alpha = float(alpha_amylase_activity(temperature).magnitude)
    beta = float(beta_amylase_activity(temperature).magnitude)
    return 0.5 * alpha + 0.5 * beta


def saccharification_rate_constant(temperature: Quantity) -> Quantity:
    """Effective first-order starch-conversion rate constant k(T) (1/min).

    k(T) = k_65C * [gelatinization(T) * enzyme_activity(T)] /
           [gelatinization(65C) * enzyme_activity(65C)]

    so that k(65 C) == k_65C by construction. The temperature-response
    component is empirical; the first-order structure is a standard
    simplifying assumption for batch saccharification.

    Classification: empirical-structured.
    """
    t = temperature
    g = gelatinization_factor(t).magnitude
    a = _combined_enzyme_activity(t)
    g_ref = gelatinization_factor(_REF_TEMP).magnitude
    a_ref = _combined_enzyme_activity(_REF_TEMP)
    k = _K_65C_PER_MIN * (g * a) / (g_ref * a_ref)
    return ureg.Quantity(k, "1 / minute")


def saccharification_conversion(time: Quantity, temperature: Quantity) -> Quantity:
    """Fraction of convertible starch converted after `time` at `temperature`.

    X(t) = 1 - exp(-k(T) * t), first-order batch conversion.

    Classification: empirical-structured.
    """
    k = saccharification_rate_constant(temperature).to("1 / minute").magnitude
    t_min = time.to("minute").magnitude
    x = 1.0 - math.exp(-k * t_min)
    return ureg.Quantity(x, "dimensionless")


def extract_plato(
    grain_mass: Quantity,
    extract_potential: Quantity,
    conversion_fraction: Quantity,
    volume_liters: Quantity,
) -> Quantity:
    """Estimate wort strength in degPlato from a grain bill.

    extract (g) = grain_mass * extract_potential * conversion_fraction
    Plato ~= extract_g / (solution mass g) * 100, with solution mass
    approximated as water mass (1 kg/L) + extract mass.

    Classification: empirical (dilute-solution Plato approximation).
    """
    grain_g = grain_mass.to("kilogram").magnitude * 1000.0
    potential = extract_potential.to("dimensionless").magnitude
    x = conversion_fraction.to("dimensionless").magnitude
    extract_g = grain_g * potential * x
    water_g = volume_liters.to("liter").magnitude * 1000.0
    solution_g = water_g + extract_g
    if solution_g <= 0:
        return ureg.Quantity(0.0, "degPlato")
    plato = extract_g / solution_g * 100.0
    return ureg.Quantity(plato, "degPlato")


def arrhenius_rate(
    pre_exponential: Quantity,
    activation_energy: Quantity,
    temperature: Quantity,
    gas_constant: Quantity = 8.314462618 * ureg.joule / (ureg.mole * ureg.kelvin),
) -> Quantity:
    """Arrhenius rate constant k(T) = A * exp(-Ea / (R * T)).

    Classification: mechanistic.
    """
    exponent: Quantity = -(activation_energy / (gas_constant * temperature)).to("dimensionless")
    return (pre_exponential * ureg.Quantity(exponent.magnitude, "dimensionless")).to(
        pre_exponential.units
    )


__all__ = [
    "arrhenius_rate",
    "gelatinization_factor",
    "alpha_amylase_activity",
    "beta_amylase_activity",
    "saccharification_rate_constant",
    "saccharification_conversion",
    "extract_plato",
]
