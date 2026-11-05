"""Incantesimi concessi dai privilegi (D4): dati meccanici minimi scritti da noi, mai testo dei manuali.

La chiave è l'indice SRD quando esiste: un incantesimo che il giocatore ha già non viene duplicato.
I Task 19-42 riempiono il dizionario e lo citano in ``FeatureSpec.granted_spells``."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GrantedSpell:
    key: str
    name: dict[str, str]
    level: int
    casting_time: str | None = None
    range_area: str | None = None
    duration: str | None = None
    is_concentration: bool = False
    is_ritual: bool = False
    attack_save: str | None = None
    damage_dice: str | None = None
    damage_type: str | None = None
    higher_levels_dice: str | None = None


GRANTED_SPELLS: dict[str, GrantedSpell] = {}
