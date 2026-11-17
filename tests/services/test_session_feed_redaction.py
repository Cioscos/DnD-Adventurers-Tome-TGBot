"""Oscuramento delle righe del log della serata per gli altri giocatori (B10)."""
from api.routers.sessions import _redact_event_description
from core.db.models import CharacterHistory


def _hit_dice_event() -> CharacterHistory:
    return CharacterHistory(character_id=1, event_type="hit_dice",
                            description="Dado vita 1d8+2: tiri=[6], curati=0 HP (38 → 38)", meta={"healed": 0})


def test_hit_dice_hidden_from_other_players():
    assert _redact_event_description(_hit_dice_event(), "Sel", 2, 1, False) == "ha speso un dado vita"


def test_hit_dice_full_for_owner_and_gm():
    e = _hit_dice_event()
    assert _redact_event_description(e, "Sel", 1, 1, False) == e.description
    assert _redact_event_description(e, "Sel", 3, 1, True) == e.description


def test_damage_shows_amount_but_not_hp_to_other_players():
    e = CharacterHistory(character_id=1, event_type="hp_change", description="Danni: -7 HP (20 → 13)",
                         meta={"op": "DAMAGE", "amount": 7})
    assert _redact_event_description(e, "Brann", 2, 1, False) == "ha subito 7 danni"
    assert _redact_event_description(e, "Brann", 1, 1, False) == e.description
    legacy = CharacterHistory(character_id=1, event_type="hp_change", description="Danni: -7 HP (20 → 13)")
    assert _redact_event_description(legacy, "Brann", 2, 1, False) == "ha subito danni"


def test_redacted_lines_do_not_repeat_the_name_the_client_already_shows():
    heal = CharacterHistory(character_id=1, event_type="hp_change", description="Cura: +3 HP (10 → 13)",
                            meta={"op": "HEAL", "amount": 3})
    assert "Sel" not in _redact_event_description(heal, "Sel", 2, 1, False)


def test_damage_type_and_reduction_reach_the_table_without_hp():
    e = CharacterHistory(character_id=1, event_type="hp_change",
                         description="Danni da Taglio: -6 HP (38 → 32) — Schivata Prodigiosa (colpo 12)",
                         meta={"op": "DAMAGE", "amount": 6, "damage_type": "Taglio", "note": "Schivata Prodigiosa (colpo 12)"})
    out = _redact_event_description(e, "Sel", 2, 1, False)
    assert out == "ha subito 6 danni da Taglio — Schivata Prodigiosa (colpo 12)" and "38" not in out


def test_hit_dice_regained_on_long_rest_has_no_hp_and_stays_readable():
    e = CharacterHistory(character_id=1, event_type="hit_dice", description="Dadi vita recuperati: 1 (riposo lungo)")
    assert _redact_event_description(e, "Sel", 2, 1, False) == e.description
