"""Hops: alpha-acid isomerization kinetics and IBU prediction (Phase 2).

Models implemented here:
    alpha_acid_isomerization_fraction  mechanistic  (first-order Arrhenius)
    iso_alpha_concentration            mechanistic  (mass balance)
    predicted_ibu                      empirical     (utilization efficiency)

Alpha acids (humulone etc.) isomerize during the boil to iso-alpha acids,
the primary bittering compounds. The isomerization is modeled as a
first-order reaction whose rate constant follows the Arrhenius law. Not all
isomerized alpha acids remain in the finished beer (losses to trub/foam,
incomplete extraction), so a utilization efficiency (empirical, ~0.2-0.4 for
typical homebrew/pilot systems) converts produced iso-alpha acids to IBU.
1 mg/L iso-alpha acid is approximately 1 IBU.

All Arrhenius parameters (pre-exponential factor, activation energy) and the
utilization efficiency are calibration targets: they must be fit to measured
bitterness for a given equipment/process. Defaults are placeholders and are
flagged as such.

Classification: isomerization / iso-alpha concentration mechanistic
(first-order mass balance); predicted_ibu empirical (utilization factor).
"""

from __future__ import annotations

import math

from brewlab.core.kinetics import arrhenius_rate
from brewlab.units import Quantity, ureg

# Default calibration targets. These are NOT established constants; they must
# be fit to measured IBU for a specific system before predictions are trusted.
# Values below are chosen so a 60-minute boil at 100 C yields ~60% alpha-acid
# isomerization (a reasonable starting point); recalibrate per system.
_DEFAULT_PRE_EXPONENTIAL = 1.0e8  # 1/minute (calibration target)
_DEFAULT_ACTIVATION_ENERGY = 70000.0  # joule / mole (calibration target)
_DEFAULT_REF_TEMP = ureg.Quantity(100.0, "degC")  # reference boil temperature
_DEFAULT_UTILIZATION = 0.30  # fraction (placeholder, empirical)


def alpha_acid_isomerization_fraction(
    time: Quantity,
    temperature: Quantity,
    pre_exponential: Quantity = _DEFAULT_PRE_EXPONENTIAL * ureg.Quantity(1, "1 / minute"),
    activation_energy: Quantity = _DEFAULT_ACTIVATION_ENERGY * ureg.joule / ureg.mole,
) -> Quantity:
    """Fraction of alpha acids isomerized after `time` at `temperature`.

    First-order kinetics: fraction = 1 - exp(-k_iso(T) * t)
    k_iso(T) = A * exp(-Ea / (R * T))  (Arrhenius)

    Parameters
    ----------
    time : Quantity [time] (boil time remaining for the addition)
    temperature : Quantity [temperature] (boil temperature)
    pre_exponential : Quantity [1/time] (Arrhenius A; calibration target)
    activation_energy : Quantity [energy/mole] (Arrhenius Ea; calibration target)

    Returns
    -------
    Quantity [dimensionless]
        Fraction isomerized (0-1).

    Classification: mechanistic (first-order Arrhenius), but A and Ea are
    calibration targets, not established constants.
    """
    k = arrhenius_rate(pre_exponential, activation_energy, temperature).to("1 / minute").magnitude
    t_min = time.to("minute").magnitude
    fraction = 1.0 - math.exp(-k * t_min)
    return ureg.Quantity(fraction, "dimensionless")


def iso_alpha_concentration(
    alpha_acid_mass: Quantity,
    alpha_acid_fraction: Quantity,
    volume: Quantity,
    isomerized_fraction: Quantity,
) -> Quantity:
    """Iso-alpha acid concentration produced (mg/L), mass balance.

    iso_alpha_mg = alpha_acid_mass(g) * alpha_fraction * isomerized_fraction * 1e6 mg/g
    concentration (mg/L) = iso_alpha_mg / volume(L)

    Classification: mechanistic (mass balance).
    """
    mass_g = alpha_acid_mass.to("gram").magnitude
    frac = alpha_acid_fraction.to("dimensionless").magnitude
    iso_frac = isomerized_fraction.to("dimensionless").magnitude
    vol_l = volume.to("liter").magnitude
    if vol_l <= 0:
        return ureg.Quantity(0.0, "milligram / liter")
    iso_mg = mass_g * frac * iso_frac * 1000.0  # g -> mg
    conc = iso_mg / vol_l
    return ureg.Quantity(conc, "milligram / liter")


def predicted_ibu(
    iso_alpha_mg_per_l: Quantity,
    utilization_efficiency: Quantity = _DEFAULT_UTILIZATION * ureg.dimensionless,
) -> Quantity:
    """Predict IBU from iso-alpha acid concentration.

    IBU ~= iso_alpha (mg/L) * utilization_efficiency.
    1 mg/L iso-alpha acid ≈ 1 IBU (approximate).

    utilization_efficiency captures losses to trub/foam and imperfect
    extraction; it is empirical and system-specific.

    Classification: empirical (utilization factor).
    """
    conc = iso_alpha_mg_per_l.to("milligram / liter").magnitude
    eff = utilization_efficiency.to("dimensionless").magnitude
    return ureg.Quantity(conc * eff, "IBU")


__all__ = [
    "alpha_acid_isomerization_fraction",
    "iso_alpha_concentration",
    "predicted_ibu",
]
