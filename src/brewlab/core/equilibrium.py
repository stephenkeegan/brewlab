"""Equilibrium: ionic strength, alkalinity, acid-base, mash pH (Phase 1).

Models implemented here:
    ionic_strength        mechanistic  (I = 0.5 * sum c_i z_i^2)
    alkalinity_as_caco3   mechanistic  (HCO3- -> mg/L as CaCO3, ASBC conversion)
    residual_alkalinity   empirical    (Kolbach-style RA, brewing convention)
    carbonate_system_ph   mechanistic  (charge-balance solve for carbonate water)

All acid-base constants are referenced to 25 °C with van't Hoff temperature
correction. The pH solver assumes the carbonate system dominates charge balance
and that dissolved CO2 is set by Henry's law at a given partial pressure.

Classification: each function is tagged in its docstring as ``mechanistic``
(first-principles) or ``empirical`` (brewing convention).
"""

from __future__ import annotations

import math
from math import log10
from typing import cast

from scipy.optimize import brentq  # type: ignore[import-untyped]

from brewlab.units import Quantity, ureg

# Reference temperature for constants (plain floats; only magnitudes are used
# in the van't Hoff corrections below).
_T_REF = 298.15  # kelvin
_R = 8.314462618  # joule / (mole * kelvin)

# Carbonic acid (apparent, CO2(aq) + H2O) first dissociation, 25 °C
_PKA1_25C = 6.35
# Enthalpy of Ka1 (apparent), J/mol
_DH_KA1 = 7700.0

# Bicarbonate second dissociation, 25 °C
_PKA2_25C = 10.33
# Enthalpy of Ka2, J/mol
_DH_KA2 = 14900.0

# Water ion product, 25 °C
_PKW_25C = 13.997
# Enthalpy of Kw, J/mol
_DH_KW = 55800.0

# Henry's law constant for CO2, mol/(L·atm), 25 °C
_KH_CO2_25C = 0.034
# Enthalpy of CO2 solution (exothermic), J/mol
_DH_KH = -24000.0

# Equivalent weight of CaCO3 (g per eq) and molar masses (g/mol)
_EQW_CACO3 = 50.044  # g/eq as CaCO3
_MW_HCO3 = 61.0168  # g/mol
_MW_CA = 40.078  # g/mol
_MW_MG = 24.305  # g/mol

_ATM_STD_CO2 = 0.0004  # atmospheric CO2 partial pressure, atm (~400 ppm)
_LN10 = math.log(10.0)


def _van_t_hoff_log10_ratio(dh_j_per_mol: float, t_kelvin: float) -> float:
    """log10(k_t / k_ref) from the van't Hoff equation."""
    log10_ratio = (-dh_j_per_mol / (2.303 * _R)) * (1.0 / t_kelvin - 1.0 / _T_REF)
    return log10_ratio


def _pka1(t_kelvin: float) -> float:
    return _PKA1_25C - _van_t_hoff_log10_ratio(_DH_KA1, t_kelvin)


def _pka2(t_kelvin: float) -> float:
    return _PKA2_25C - _van_t_hoff_log10_ratio(_DH_KA2, t_kelvin)


def _pkw(t_kelvin: float) -> float:
    return _PKW_25C - _van_t_hoff_log10_ratio(_DH_KW, t_kelvin)


def _kh_co2(t_kelvin: float) -> float:
    log10_ratio = _van_t_hoff_log10_ratio(_DH_KH, t_kelvin)
    return _KH_CO2_25C * math.exp(log10_ratio * _LN10)


def ionic_strength(concentrations: dict[str, Quantity]) -> Quantity:
    """Compute ionic strength I = 0.5 * sum(c_i * z_i^2).

    Parameters
    ----------
    concentrations : dict[str, Quantity]
        Ion name -> molarity (mol/L). Charge lookup by ion name.

    Returns
    -------
    Quantity [mol/L]

    Classification: mechanistic.
    """
    _charges = {
        "Ca": 2,
        "Mg": 2,
        "Na": 1,
        "K": 1,
        "Cl": -1,
        "SO4": -2,
        "HCO3": -1,
        "H": 1,
        "OH": -1,
        "CO3": -2,
        "H2PO4": -1,
        "HPO4": -2,
        "PO4": -3,
        "NH4": 1,
    }
    total_magnitude = 0.0
    for ion, conc in concentrations.items():
        z = _charges.get(ion, 0)
        total_magnitude += cast(float, conc.magnitude) * (z * z)
    return ureg.Quantity(0.5 * total_magnitude, "molar")


def alkalinity_as_caco3_from_bicarbonate(bicarbonate_mg_per_l: Quantity) -> Quantity:
    """Convert bicarbonate concentration to alkalinity expressed as CaCO3.

    Alkalinity (mg/L as CaCO3) = [HCO3-] (mg/L) * (eq_w_CaCO3 / MW_HCO3)
    because 1 mol HCO3- neutralizes 1 eq of acid.

    Parameters
    ----------
    bicarbonate_mg_per_l : Quantity [mass/volume]
        Bicarbonate concentration, e.g. mg/L or gram/liter.

    Returns
    -------
    Quantity [mg/L as CaCO3]

    Classification: mechanistic (ASBC equivalence).
    """
    conc = bicarbonate_mg_per_l.to("milligram / liter")
    moles_per_l = cast(float, conc.magnitude) / (_MW_HCO3 * 1000.0)
    mg_per_l_as_caco3 = moles_per_l * _EQW_CACO3 * 1000.0
    return ureg.Quantity(mg_per_l_as_caco3, "milligram / liter")


def calcium_hardness_as_caco3(calcium_mg_per_l: Quantity) -> Quantity:
    """Express calcium concentration as CaCO3-equivalent hardness."""
    conc = calcium_mg_per_l.to("milligram / liter")
    moles_per_l = cast(float, conc.magnitude) / (_MW_CA * 1000.0)
    return ureg.Quantity(moles_per_l * _EQW_CACO3 * 1000.0, "milligram / liter")


def magnesium_hardness_as_caco3(magnesium_mg_per_l: Quantity) -> Quantity:
    """Express magnesium concentration as CaCO3-equivalent hardness."""
    conc = magnesium_mg_per_l.to("milligram / liter")
    moles_per_l = cast(float, conc.magnitude) / (_MW_MG * 1000.0)
    return ureg.Quantity(moles_per_l * _EQW_CACO3 * 1000.0, "milligram / liter")


def residual_alkalinity(
    alkalinity_mg_per_l_as_caco3: Quantity,
    calcium_mg_per_l: Quantity,
    magnesium_mg_per_l: Quantity,
) -> Quantity:
    """Kolbach-style residual alkalinity.

    RA = Alkalinity - Calcium_hardness - Magnesium_hardness
    with all terms expressed as mg/L CaCO3. Positive RA raises mash pH;
    negative RA lowers it. This is the brewing-industry convention; the
    exact divisor (e.g. Ca/3.5) is an empirical mash-specific adjustment
    and is not applied here.

    Classification: empirical (brewing convention, not first-principles).
    """
    alk = cast(float, alkalinity_mg_per_l_as_caco3.to("milligram / liter").magnitude)
    ca = cast(float, calcium_hardness_as_caco3(calcium_mg_per_l).magnitude)
    mg = cast(float, magnesium_hardness_as_caco3(magnesium_mg_per_l).magnitude)
    return ureg.Quantity(alk - ca - mg, "milligram / liter")


def carbonate_system_ph(
    alkalinity_mg_per_l_as_caco3: Quantity,
    temperature: Quantity,
    pco2_atm: Quantity = ureg.Quantity(_ATM_STD_CO2, "atm"),
) -> Quantity:
    """Predict pH of a carbonate-dominated water by charge-balance solve.

    Solves for [H+] in:

        alkalinity = [HCO3-] + 2[CO3--] + [OH-] - [H+]

    where [CO2(aq)] = KH(T) * pCO2 (Henry's law),
          [HCO3-] = Ka1(T) * [CO2] / [H+],
          [CO3--] = Ka1(T)*Ka2(T)*[CO2] / [H+]^2,
          [OH-] = Kw(T) / [H+].

    Parameters
    ----------
    alkalinity_mg_per_l_as_caco3 : Quantity [mg/L as CaCO3]
        Total alkalinity.
    temperature : Quantity [temperature]
        Water temperature.
    pco2_atm : Quantity [pressure]
        CO2 partial pressure in equilibrium with the water.

    Returns
    -------
    Quantity [dimensionless]
        Predicted pH (-log10 [H+]).

    Classification: mechanistic (carbonate equilibrium + Henry's law).
    """
    t_k = cast(float, temperature.to("kelvin").magnitude)
    ka1 = math.exp(-_pka1(t_k) * _LN10)
    ka2 = math.exp(-_pka2(t_k) * _LN10)
    kw = math.exp(-_pkw(t_k) * _LN10)
    kh = _kh_co2(t_k)
    co2 = kh * cast(float, pco2_atm.to("atm").magnitude)  # mol/L

    alkalinity_eq_per_l = (
        cast(float, alkalinity_mg_per_l_as_caco3.to("milligram / liter").magnitude)
        / 1000.0
        / _EQW_CACO3
    )  # mol/L (eq/L) of alkalinity

    def residual(h: float) -> float:
        hco3 = ka1 * co2 / h
        co3 = ka1 * ka2 * co2 / (h * h)
        oh = kw / h
        return hco3 + 2.0 * co3 + oh - h - alkalinity_eq_per_l

    # Bracket [H+] over a wide pH range (1 to 13)
    lo = math.exp(-13.0 * _LN10)
    hi = math.exp(-1.0 * _LN10)
    if residual(lo) * residual(hi) > 0:
        # Degenerate case (e.g. zero alkalinity, zero CO2); return neutral pH
        return ureg.Quantity(7.0, "dimensionless")
    h = brentq(residual, lo, hi, xtol=1e-14, rtol=1e-12)
    return ureg.Quantity(-log10(h), "dimensionless")


__all__ = [
    "ionic_strength",
    "alkalinity_as_caco3_from_bicarbonate",
    "calcium_hardness_as_caco3",
    "magnesium_hardness_as_caco3",
    "residual_alkalinity",
    "carbonate_system_ph",
]
