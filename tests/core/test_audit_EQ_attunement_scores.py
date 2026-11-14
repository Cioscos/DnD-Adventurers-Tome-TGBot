"""Audit EQ: sintonia (PHB 2024 p.232): senza sintonia nessun beneficio magico, nemmeno i punteggi di caratteristica
(Cintura del Gigante, Guanti della Forza...).
La carta 2014 (equipment.md) non tratta la sintonia, che nel 2014 e' nella Guida del DM: la regola e' la stessa, il fix vale per le due edizioni."""
from types import SimpleNamespace

from core.game.stats import effective_ability_score


def _belt(**meta):
    meta = {"ability_modifiers": [{"ability": "strength", "kind": "absolute", "value": 21}], **meta}
    return SimpleNamespace(id=1, name="Cintura", item_metadata=meta)


def test_unattuned_item_gives_no_ability_score():
    assert effective_ability_score("strength", 10, [_belt(requires_attunement=True)])[0] == 10


def test_attuned_item_gives_its_ability_score():
    assert effective_ability_score("strength", 10, [_belt(requires_attunement=True, attuned=True)])[0] == 21


def test_item_without_attunement_requirement_keeps_its_score():
    assert effective_ability_score("strength", 10, [_belt()])[0] == 21
