"""Concentrazione e durata di un lancio secondo lo slot, per i lanci dalla scheda, da un oggetto e per le finestre dei privilegi."""
from __future__ import annotations

from typing import Any

from core.game.actions import parse_duration_rounds
from core.rules.catalog.spells import spell_effect
from core.rules.edition import character_edition

# Concentrazione che cambia con lo slot e che la riga non dice: (edizione -> slot da cui non serve più, slot -> round).
# Immagine Maggiore 2014 pag. 242, 2024 pag. 295; Scagliare Maledizione 2014 pag. 273, 2024 pag. 245 (10 minuti con lo slot del 4°);
# Dominare Bestie / Persone / Mostri 2014 pag. 231-232, 2024 pag. 265-266 (10 minuti, 1 ora, 8 ore)
_SLOT_CONCENTRATION = {"major-image": ({"2014": 6, "2024": 4}, {}), "bestow-curse": ({"2014": 5, "2024": 5}, {4: 100}),
                       "dominate-beast": ({}, {5: 100, 6: 600, 7: 4800, 8: 4800, 9: 4800}),
                       "dominate-person": ({}, {6: 100, 7: 600, 8: 4800, 9: 4800}),
                       "dominate-monster": ({}, {9: 4800})}
# la riga senza srd_index (scritta a mano, homebrew, import vecchi) si riconosce dal nome it/en, come per gli effetti del lancio
_SLOT_CONCENTRATION_NAMES = {n.lower(): k for k, names in {
    "major-image": ("Immagine Maggiore", "Major Image"), "bestow-curse": ("Scagliare Maledizione", "Maledizione", "Bestow Curse"),
    "dominate-beast": ("Dominare Bestie", "Dominate Beast"), "dominate-person": ("Dominare Persone", "Dominate Person"),
    "dominate-monster": ("Dominare Mostri", "Dominate Monster")}.items() for n in names}


def slot_concentration(char: Any, spell: Any, level: int) -> tuple[bool, int | None]:
    """Se il lancio a questo livello chiede concentrazione e per quanti round: quelli dello slot (la tabella sopra, Sortilegio
    e Marchio del Cacciatore dal catalogo degli effetti), altrimenti la durata scritta sulla riga."""
    edition = character_edition(char)
    key = spell.srd_index if spell.srd_index in _SLOT_CONCENTRATION else next(
        (_SLOT_CONCENTRATION_NAMES[n] for p in (spell.name or "").split("/") if (n := p.strip().lower()) in _SLOT_CONCENTRATION_NAMES), "")
    until, rounds = _SLOT_CONCENTRATION.get(key, ({}, {}))
    if level >= until.get(edition, 10):
        return False, None
    if level in rounds:
        return True, rounds[level]
    found = spell_effect(edition, spell.srd_index, spell.name)
    if found and found[1].concentration and found[1].rounds_by_slot:
        return True, found[1].rounds_by_slot(level)
    rounds = parse_duration_rounds(spell.duration)
    if rounds == 1 and found and found[1].concentration:  # Colpo Accurato 2014 (pag. 222): serve nel turno dopo, il «Nuovo turno» non lo chiude
        rounds = found[1].rounds or rounds
    return True, rounds
