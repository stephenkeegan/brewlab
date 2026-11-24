"""Domain model construction tests.

Validates that domain entities carry units correctly and compose without
unit errors, per the architectural rule that no bare floats cross layer
boundaries.
"""

from __future__ import annotations

import pytest

from brewlab.domain.equipment import Equipment
from brewlab.domain.ingredient import Hop, Malt, WaterProfile, Yeast
from brewlab.domain.recipe import Fermentable, HopAddition, Recipe
from brewlab.units import ureg


def test_malt_carries_units() -> None:
    malt = Malt(
        name="Pilsner",
        amount=ureg.Quantity(5.0, "kilogram"),
        color_lovibond=ureg.Quantity(1.8, "degLovibond"),
        extract_potential=ureg.Quantity(0.80, "dimensionless"),
        moisture=ureg.Quantity(0.045, "dimensionless"),
        diastatic_power=ureg.Quantity(120.0, "dimensionless"),
    )
    assert malt.amount.magnitude == 5.0
    assert str(malt.amount.units) == "kilogram"
    assert malt.color_lovibond.magnitude == 1.8


def test_water_profile_ions() -> None:
    water = WaterProfile(
        calcium=ureg.Quantity(50.0, "milligram / liter"),
        bicarbonate=ureg.Quantity(150.0, "milligram / liter"),
    )
    assert water.calcium.magnitude == 50.0
    assert str(water.calcium.units) == "milligram / liter"


def test_recipe_composition() -> None:
    malt = Malt(
        name="Pilsner",
        amount=ureg.Quantity(5.0, "kilogram"),
        color_lovibond=ureg.Quantity(1.8, "degLovibond"),
        extract_potential=ureg.Quantity(0.80, "dimensionless"),
        moisture=ureg.Quantity(0.045, "dimensionless"),
        diastatic_power=ureg.Quantity(120.0, "dimensionless"),
    )
    hop = Hop(
        name="Saaz",
        amount=ureg.Quantity(0.05, "kilogram"),
        alpha_acid=ureg.Quantity(0.035, "dimensionless"),
        beta_acid=ureg.Quantity(0.04, "dimensionless"),
        hsi=ureg.Quantity(0.25, "dimensionless"),
        oil_content=ureg.Quantity(0.008, "dimensionless"),
    )
    yeast = Yeast(
        strain_id="WLP800",
        attenuation_min=ureg.Quantity(0.72, "dimensionless"),
        attenuation_max=ureg.Quantity(0.78, "dimensionless"),
        flocculation="medium",
        temperature_min=ureg.Quantity(10.0, "degC"),
        temperature_max=ureg.Quantity(14.0, "degC"),
    )
    recipe = Recipe(
        name="Test Pilsner",
        fermentables=[Fermentable(malt=malt, amount=ureg.Quantity(5.0, "kilogram"))],
        hops=[
            HopAddition(
                hop=hop,
                amount=ureg.Quantity(0.05, "kilogram"),
                time_min=ureg.Quantity(60.0, "minute"),
                use="bittering",
            )
        ],
        yeast=yeast,
        batch_size=ureg.Quantity(20.0, "liter"),
    )
    assert recipe.name == "Test Pilsner"
    assert len(recipe.fermentables) == 1
    assert len(recipe.hops) == 1
    assert recipe.yeast.strain_id == "WLP800"
    assert str(recipe.batch_size.units) == "liter"


def test_equipment_units() -> None:
    equip = Equipment(
        name="10 gal system",
        vessel_volume=ureg.Quantity(40.0, "liter"),
        dead_space=ureg.Quantity(2.0, "liter"),
        boil_off_rate=ureg.Quantity(4.0, "liter / hour"),
        efficiency=ureg.Quantity(0.75, "dimensionless"),
        loss_to_trub=ureg.Quantity(1.5, "liter"),
    )
    assert str(equip.vessel_volume.units) == "liter"
    assert str(equip.boil_off_rate.units) == "liter / hour"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
