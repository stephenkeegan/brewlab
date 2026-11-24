"""Yeast library tests (Phase 9).

Validates curated strain lookup, ids listing, species filtering, and
default strain selection.
"""

from __future__ import annotations

import pytest

from brewlab.domain.yeast_library import YeastLibrary


def test_library_get_known_strain() -> None:
    lib = YeastLibrary()
    yeast = lib.get("US-05")
    assert yeast is not None
    assert yeast.strain_id == "US-05"
    assert yeast.species == "cerevisiae"
    assert yeast.flavor_notes == "clean, neutral"


def test_library_get_unknown_strain() -> None:
    lib = YeastLibrary()
    assert lib.get("Does Not Exist") is None


def test_library_ids_sorted() -> None:
    lib = YeastLibrary()
    ids = lib.ids()
    assert ids == sorted(ids)
    assert "US-05" in ids
    assert "W-34/74" in ids
    assert "Kveik" in ids


def test_library_by_species() -> None:
    lib = YeastLibrary()
    lager = lib.by_species("pastorianus")
    assert all(y.species == "pastorianus" for y in lager)
    assert {y.strain_id for y in lager} == {"W-34/74", "S-23"}


def test_library_default() -> None:
    lib = YeastLibrary()
    assert lib.default().strain_id == "US-05"


def test_strain_attenuation_range() -> None:
    lib = YeastLibrary()
    kveik = lib.get("Kveik")
    assert kveik is not None
    assert kveik.attenuation_min.magnitude == pytest.approx(0.80)
    assert kveik.attenuation_max.magnitude == pytest.approx(0.90)
    assert kveik.temperature_min.magnitude == pytest.approx(30.0)
    assert kveik.temperature_max.magnitude == pytest.approx(40.0)


def test_strain_flavor_notes() -> None:
    lib = YeastLibrary()
    belgian = lib.get("Belgian Ale")
    assert belgian is not None
    assert "phenolics" in belgian.flavor_notes


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
