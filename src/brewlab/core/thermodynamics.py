"""Thermodynamics: T-dependent cp, density, enthalpy, heat balances (Phase 1)."""

from __future__ import annotations

from brewlab.units import Quantity, ureg


def strike_water_temperature(
    grain_mass: Quantity,
    grain_temperature: Quantity,
    target_mash_temperature: Quantity,
    water_to_grain_ratio: Quantity,
    specific_heat_grain: Quantity,
    specific_heat_water: Quantity,
) -> Quantity:
    """Compute required strike-water temperature for a single-infusion mash.

    Heat balance: heat lost by strike water = heat gained by grain + vessel.
    Neglects vessel heat loss and assumes thermal equilibrium at target.

    Parameters
    ----------
    grain_mass : Quantity [mass]
    grain_temperature : Quantity [temperature]
    target_mash_temperature : Quantity [temperature]
    water_to_grain_ratio : Quantity [volume/mass] (e.g. liter/kilogram)
    specific_heat_grain : Quantity [energy/(mass*temperature)]
    specific_heat_water : Quantity [energy/(mass*temperature)]

    Returns
    -------
    Quantity [temperature]
        Required strike-water temperature.
    """
    water_mass: Quantity = grain_mass * water_to_grain_ratio
    # Density of water ~ 1 kg/L; convert strike-water volume to mass explicitly.
    water_density: Quantity = ureg.Quantity(1.0, "kilogram / liter")
    water_mass = water_mass * water_density
    # Work in kelvin (absolute) so heat-capacity (per K) times temperature
    # differences never triggers pint's offset-unit calculus.
    grain_temperature_k = grain_temperature.to("kelvin")
    target_mash_temperature_k = target_mash_temperature.to("kelvin")
    delta_t_k: Quantity = target_mash_temperature_k - grain_temperature_k

    heat_capacity_grain: Quantity = grain_mass * specific_heat_grain
    heat_capacity_water: Quantity = water_mass * specific_heat_water
    # Heat lost by strike water = heat gained by grain:
    #   m_w*cw*(T_strike - T_target) = m_g*cg*(T_target - T_grain)
    #   T_strike = T_target + m_g*cg*(T_target - T_grain) / (m_w*cw)
    adjustment_k: Quantity = (heat_capacity_grain * delta_t_k) / heat_capacity_water
    strike_temp_k: Quantity = target_mash_temperature_k + adjustment_k
    return strike_temp_k.to("degC")


__all__ = ["strike_water_temperature"]
