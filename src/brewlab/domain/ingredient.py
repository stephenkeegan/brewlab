"""Ingredients: Ingredient, Malt, Hop, Yeast, WaterProfile."""

from __future__ import annotations

from dataclasses import dataclass

from brewlab.units import Quantity


@dataclass
class Ingredient:
    name: str
    amount: Quantity


@dataclass
class Malt(Ingredient):
    color_lovibond: Quantity  # degLovibond
    extract_potential: Quantity  # fraction (e.g. 0.80)
    moisture: Quantity  # fraction
    diastatic_power: Quantity  # degrees Lintner


@dataclass
class Hop(Ingredient):
    alpha_acid: Quantity  # fraction
    beta_acid: Quantity  # fraction
    hsi: Quantity  # fraction, Hop Storage Index
    oil_content: Quantity  # fraction


@dataclass
class Yeast:
    strain_id: str
    attenuation_min: Quantity  # fraction
    attenuation_max: Quantity  # fraction
    flocculation: str  # low/medium/high
    temperature_min: Quantity  # degC
    temperature_max: Quantity  # degC


@dataclass
class WaterProfile:
    calcium: Quantity = Quantity(0, "milligram / liter")
    magnesium: Quantity = Quantity(0, "milligram / liter")
    sodium: Quantity = Quantity(0, "milligram / liter")
    potassium: Quantity = Quantity(0, "milligram / liter")
    chloride: Quantity = Quantity(0, "milligram / liter")
    sulfate: Quantity = Quantity(0, "milligram / liter")
    bicarbonate: Quantity = Quantity(0, "milligram / liter")


__all__ = ["Ingredient", "Malt", "Hop", "Yeast", "WaterProfile"]
