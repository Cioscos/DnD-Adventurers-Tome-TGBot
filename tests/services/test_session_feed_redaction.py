"""Oscuramento delle righe del log della serata per gli altri giocatori (B10)."""
from api.routers.sessions import _redact_event_description
from core.db.models import CharacterHistory


def _hit_dice_event() -> CharacterHistory:
    return CharacterHistory(character_id=1, event_type="hit_dice",
                            description="Dado vita 1d8+2: tiri=[6], curati=0 HP (38 → 38)", meta={"healed": 0})


def test_hit_dice_hidden_from_other_players():
    assert _redact_event_description(_hit_dice_event(), "Sel", 2, 1, False) == "Sel ha speso un dado vita"


def test_hit_dice_full_for_owner_and_gm():
    e = _hit_dice_event()
    assert _redact_event_description(e, "Sel", 1, 1, False) == e.description
    assert _redact_event_description(e, "Sel", 3, 1, True) == e.description


def test_damage_shows_amount_but_not_hp_to_other_players():
    e = CharacterHistory(character_id=1, event_type="hp_change", description="Danni: -7 HP (20 → 13)",
                         meta={"op": "DAMAGE", "amount": 7})
    assert _redact_event_description(e, "Brann", 2, 1, False) == "Brann ha subito 7 danni"
    assert _redact_event_description(e, "Brann", 1, 1, False) == e.description
    legacy = CharacterHistory(character_id=1, event_type="hp_change", description="Danni: -7 HP (20 → 13)")
    assert _redact_event_description(legacy, "Brann", 2, 1, False) == "Brann ha subito danni"
