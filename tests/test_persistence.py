"""Persistence tests (Phase 7).

Validates JSON round-tripping of dataclasses, pint.Quantity, and datetime,
plus the JsonRepository add/get/list contract.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from brewlab.domain.equipment import Equipment
from brewlab.domain.ingredient import Malt
from brewlab.domain.recipe import Fermentable, Recipe
from brewlab.persistence.json_repo import JsonRepository, from_jsonable, to_jsonable
from brewlab.units import ureg


def _malt() -> object:
    return Malt(
        name="Pilsner",
        amount=ureg.Quantity(5.0, "kilogram"),
        color_lovibond=ureg.Quantity(1.8, "degLovibond"),
        extract_potential=ureg.Quantity(0.80, "dimensionless"),
        moisture=ureg.Quantity(0.045, "dimensionless"),
        diastatic_power=ureg.Quantity(120.0, "dimensionless"),
    )


def test_quantity_round_trip() -> None:
    q = ureg.Quantity(50.0, "milligram / liter")
    data = to_jsonable(q)
    assert data["__quantity__"] is True
    assert data["magnitude"] == 50.0
    assert data["units"] == "milligram / liter"
    back = from_jsonable(data)
    assert back.magnitude == pytest.approx(50.0)
    assert str(back.units) == "milligram / liter"


def test_datetime_round_trip() -> None:
    dt = datetime(2026, 11, 24, 12, 0, 0)
    data = to_jsonable(dt)
    assert data["__datetime__"] is True
    back = from_jsonable(data)
    assert back == dt


def test_dataclass_round_trip() -> None:
    recipe = Recipe(
        name="Test IPA",
        fermentables=[Fermentable(malt=_malt(), amount=ureg.Quantity(6.0, "kilogram"))],
        batch_size=ureg.Quantity(20.0, "liter"),
    )
    data = to_jsonable(recipe)
    assert data["__dataclass__"] == "Recipe"
    assert data["name"] == "Test IPA"
    back = from_jsonable(data)
    assert back.name == "Test IPA"
    assert back.batch_size.magnitude == pytest.approx(20.0)
    assert str(back.batch_size.units) == "liter"
    assert back.fermentables[0].malt.name == "Pilsner"


def test_nested_dict_list_round_trip() -> None:
    obj = {
        "name": "batch",
        "q": ureg.Quantity(1.5, "kilogram"),
        "when": datetime(2026, 1, 1),
        "items": [ureg.Quantity(2.0, "liter"), {"x": ureg.Quantity(3.0, "degC")}],
    }
    back = from_jsonable(to_jsonable(obj))
    assert back["name"] == "batch"
    assert back["q"].magnitude == pytest.approx(1.5)
    assert back["when"] == datetime(2026, 1, 1)
    assert back["items"][0].magnitude == pytest.approx(2.0)
    assert back["items"][1]["x"].magnitude == pytest.approx(3.0)


def test_repository_add_get_list(tmp_path: Path) -> None:
    repo = JsonRepository[dict](tmp_path / "store")
    assert (tmp_path / "store").exists()

    repo.add({"id": "a", "name": "first", "q": ureg.Quantity(1.0, "kilogram")})
    repo.add({"id": "b", "name": "second"})

    assert repo.get("a") is not None
    assert repo.get("a")["name"] == "first"
    assert repo.get("missing") is None

    ids = [i["id"] for i in repo.list()]
    assert ids == ["a", "b"]


def test_repository_domain_dataclass(tmp_path: Path) -> None:
    repo = JsonRepository[Recipe](tmp_path / "store")
    recipe = Recipe(
        name="Persisted IPA",
        batch_size=ureg.Quantity(20.0, "liter"),
    )
    repo.add(recipe)

    back = repo.get("Persisted IPA")
    assert back is not None
    assert back.name == "Persisted IPA"
    assert back.batch_size.magnitude == pytest.approx(20.0)

    ids = [r.name for r in repo.list()]
    assert ids == ["Persisted IPA"]


def test_repository_uses_id_field_when_absent(tmp_path: Path) -> None:
    repo = JsonRepository[dict](tmp_path / "store")
    repo.add({"name": "no-id"})
    files = list((tmp_path / "store").glob("*.json"))
    assert len(files) == 1
    assert repo.get(files[0].stem) is not None


def test_equipment_round_trip() -> None:
    equip = Equipment(
        name="Kettle",
        vessel_volume=ureg.Quantity(30.0, "liter"),
        boil_off_rate=ureg.Quantity(4.0, "liter / hour"),
    )
    back = from_jsonable(to_jsonable(equip))
    assert back.name == "Kettle"
    assert back.vessel_volume.magnitude == pytest.approx(30.0)
    assert str(back.vessel_volume.units) == "liter"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
