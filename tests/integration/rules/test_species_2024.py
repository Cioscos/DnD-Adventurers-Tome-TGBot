"""Specie 2024 come sorgente di privilegi del motore (Task 1: registro e filtri)."""
from __future__ import annotations

from types import SimpleNamespace

from core.rules.catalog import active_features
from core.rules.catalog.species_2024 import SPECIES_TRAITS, owned_species, trait


def _char(edition: str, species_key: str | None, level: int = 3, options: dict | None = None):
    return SimpleNamespace(rules_edition=edition, species_key=species_key, species_options=options,
                           classes=[SimpleNamespace(level=level)], abilities=[])


def test_owned_species_empty_without_key_and_for_2014():
    assert owned_species(_char("2024", None)) == []
    assert owned_species(_char("2014", "2024_dwarf")) == []
    assert owned_species(_char("2024", "2024_sconosciuta")) == []


def test_owned_species_filters_level_and_lineage(monkeypatch):
    monkeypatch.setitem(SPECIES_TRAITS, "2024_test", (
        trait("test", "base", 1, "T", ("Base", "Base"), ("a", "a")),
        trait("test", "late", 5, "T", ("Tardo", "Late"), ("b", "b")),
        trait("test", "drow", 1, "T", ("Drow", "Drow"), ("c", "c"), option_group="lineage", option_key="drow"),
        trait("test", "elf", 1, "T", ("Elfo", "Elf"), ("d", "d"), option_group="lineage", option_key="high"),
    ))
    char = _char("2024", "2024_test", 3, {"lineage": "drow"})
    owned = owned_species(char)
    assert [s.key for s, _ in owned] == ["species.2024_test_base", "species.2024_test_drow"]
    assert owned[0][1].class_name == "species" and owned[0][1].level == 3 and owned[0][1].ability is None
    assert [s.key for s, _ in active_features(char)] == [s.key for s, _ in owned]
