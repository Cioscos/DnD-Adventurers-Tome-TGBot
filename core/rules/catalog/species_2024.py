"""Tratti delle specie 2024 nel motore delle regole di classe.

Come i talenti (``feats.py``): ``active_features`` restituisce ogni tratto con un ``SpeciesSource`` al posto della riga
di classe. La specie è ``Character.species_key`` (``2024_dwarf``); le scelte (lignaggio, ...) sono ``species_options``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.rules.catalog.feats import _abilities
from core.rules.edition import character_edition
from core.rules.types import FeatureSpec


@dataclass(frozen=True)
class SpeciesSource:
    """Al posto della riga di classe per i tratti di specie."""
    ability: Any
    level: int
    options: dict

    @property
    def id(self) -> None:
        return None

    @property
    def class_name(self) -> str:
        return "species"

    @property
    def subclass_key(self) -> None:
        return None


def trait(species: str, key: str, level: int, title: str, name: tuple[str, str], summary: tuple[str, str],
          **kw: Any) -> FeatureSpec:
    """Tratto di specie: ``species`` è la chiave senza anno (``dwarf``), la spec ha chiave ``species.2024_<species>_<key>``."""
    kw.setdefault("passive", kw.get("on_use") is None)
    return FeatureSpec(key=f"species.2024_{species}_{key}", class_key="species", edition="2024", level=level,
                       source_title=title, name={"it": name[0], "en": name[1]},
                       summary={"it": summary[0], "en": summary[1]}, action_type=kw.pop("action_type", None), **kw)


# Riempito dai moduli delle singole specie: chiave ``2024_dwarf`` -> tratti
SPECIES_TRAITS: dict[str, tuple[FeatureSpec, ...]] = {}


def owned_species(char: Any) -> list[tuple[FeatureSpec, SpeciesSource]]:
    if character_edition(char) != "2024":
        return []
    traits = SPECIES_TRAITS.get(getattr(char, "species_key", None) or "")
    if not traits:
        return []
    level = max(1, sum(getattr(c, "level", 0) or 0 for c in getattr(char, "classes", None) or []))
    chosen = getattr(char, "species_options", None) or {}
    rows = {a.feature_key: a for a in _abilities(char)}
    return [(s, SpeciesSource(rows.get(s.key), level, chosen)) for s in traits
            if s.level <= level and (s.option_group is None or s.option_key == chosen.get(s.option_group))]
