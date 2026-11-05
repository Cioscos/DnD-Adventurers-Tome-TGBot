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
    ritual_only: bool = False  # si lancia solo come rituale, anche da chi non ha il Lancio Rituale


GRANTED_SPELLS: dict[str, GrantedSpell] = {
    # Combattente Totemico 2014 (Cercatore di Spiriti, Viandante Spirituale): solo come rituali
    "beast-sense": GrantedSpell(
        "beast-sense", {"it": "Percezione delle bestie", "en": "Beast Sense"}, 2, "1 azione", "Contatto",
        "Concentrazione, fino a 1 ora", is_concentration=True, is_ritual=True, ritual_only=True),
    "speak-with-animals": GrantedSpell(
        "speak-with-animals", {"it": "Parlare con gli animali", "en": "Speak with Animals"}, 1, "1 azione",
        "Personale", "10 minuti", is_ritual=True, ritual_only=True),
    "commune-with-nature": GrantedSpell(
        "commune-with-nature", {"it": "Comunione con la natura", "en": "Commune with Nature"}, 5, "1 minuto",
        "Personale", "Istantanea", is_ritual=True, ritual_only=True),
}
