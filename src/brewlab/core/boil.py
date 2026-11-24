"""Boil: boil-off volume, wort concentration / gravity evolution (Phase 2).

Models implemented here:
    boil_off_volume       mechanistic  (V(t) = V0 - R * t; pure water evaporates)
    wort_plato_after_boil mechanistic  (extract mass conserved; volume decreases)
    plato_to_specific_gravity empirical  (ASBC/EBC approximate relation)
    specific_gravity_to_plato empirical  (inverse of above)

The boil model assumes boil-off is pure water vapor, so dissolved extract
mass is conserved (neglecting minor losses to foam/trub) and wort strength
rises as volume falls. Specific gravity<->Plato uses the standard approximate
ASBC polynomial; for high-gravity worts a density measurement is preferred.

Classification: boil_off_volume / wort_plato_after_boil mechanistic (mass
balance); plato<->SG empirical (approximate fit).
"""

from __future__ import annotations

from brewlab.units import Quantity, ureg


def boil_off_volume(
    initial_volume: Quantity,
    boil_off_rate: Quantity,
    time: Quantity,
) -> Quantity:
    """Remaining wort volume after boiling for `time` at `boil_off_rate`.

    V(t) = V0 - R * t

    Parameters
    ----------
    initial_volume : Quantity [volume]
    boil_off_rate : Quantity [volume/time]
    time : Quantity [time]

    Returns
    -------
    Quantity [volume]
        Remaining volume, clamped at zero (boil-off cannot remove more than
        the starting volume).
    """
    remaining: Quantity = initial_volume - boil_off_rate * time
    zero = ureg.Quantity(0, initial_volume.units)
    return max(remaining, zero)


def wort_plato_after_boil(
    initial_plato: Quantity,
    initial_volume: Quantity,
    boil_off_rate: Quantity,
    time: Quantity,
) -> Quantity:
    """Wort strength (°Plato) after a boil, conserving extract mass.

    Boil-off removes water only; extract mass stays constant. As volume
    falls, °Plato rises.

    Parameters
    ----------
    initial_plato : Quantity [degPlato]
    initial_volume : Quantity [volume]
    boil_off_rate : Quantity [volume/time]
    time : Quantity [time]

    Returns
    -------
    Quantity [degPlato]

    Classification: mechanistic (extract-mass balance).
    """
    p0 = initial_plato.to("degPlato").magnitude / 100.0  # fraction
    v0_l = initial_volume.to("liter").magnitude
    rate_l_per_hr = boil_off_rate.to("liter / hour").magnitude
    t_hr = time.to("hour").magnitude

    water_mass_0_g = v0_l * 1000.0  # water density ~1 kg/L
    # extract_mass / (water_mass + extract_mass) = p0
    # extract_mass = p0 * water_mass_0 / (1 - p0)
    if p0 >= 1.0:
        return initial_plato
    extract_mass_g = p0 * water_mass_0_g / (1.0 - p0)

    remaining_volume_l = max(v0_l - rate_l_per_hr * t_hr, 0.0)
    water_mass_g = remaining_volume_l * 1000.0
    solution_mass_g = water_mass_g + extract_mass_g
    if solution_mass_g <= 0:
        return ureg.Quantity(0.0, "degPlato")
    plato = extract_mass_g / solution_mass_g * 100.0
    return ureg.Quantity(plato, "degPlato")


def plato_to_specific_gravity(plato: Quantity) -> Quantity:
    """Approximate specific gravity from °Plato (ASBC/EBC fit).

    SG = 1 + Plato / (258.6 - ((Plato / 258.2) * 227.1))

    Valid for typical beer wort (roughly 0-30 °Plato). Above that, the fit
    degrades and a density meter is preferred.

    Classification: empirical (approximate polynomial fit).
    """
    p = plato.to("degPlato").magnitude
    sg = 1.0 + p / (258.6 - (p / 258.2) * 227.1)
    return ureg.Quantity(sg, "dimensionless")


def specific_gravity_to_plato(sg: Quantity) -> Quantity:
    """Approximate °Plato from specific gravity (inverse ASBC/EBC fit).

    Classification: empirical (inverse approximate fit).
    """
    s = sg.to("dimensionless").magnitude
    if s <= 1.0:
        return ureg.Quantity(0.0, "degPlato")
    # Invert the Plato->SG relation numerically via a closed approximation:
    # Plato ~= (SG - 1) * (258.6 - (Plato/258.2)*227.1). Solve iteratively.
    plato = (s - 1.0) * 258.6
    for _ in range(8):
        denom = 258.6 - (plato / 258.2) * 227.1
        if denom <= 0:
            break
        new_plato = (s - 1.0) * denom
        if abs(new_plato - plato) < 1e-9:
            break
        plato = new_plato
    return ureg.Quantity(max(plato, 0.0), "degPlato")


__all__ = [
    "boil_off_volume",
    "wort_plato_after_boil",
    "plato_to_specific_gravity",
    "specific_gravity_to_plato",
]
