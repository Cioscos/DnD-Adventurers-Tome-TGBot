"""Unit tests for api/services/dice_stats.py (no DB session needed)."""
from __future__ import annotations

from api.services.dice_stats import record_dice
from core.db.models import Character


def test_record_creates_faces_from_scratch():
    char = Character(user_id=1, name="X")  # dice_stats None
    record_dice(char, [("d20", 20), ("d20", 20), ("d20", 1)])
    assert char.dice_stats == {"d20": {"20": 2, "1": 1}}


def test_record_increments_existing_counts():
    char = Character(user_id=1, name="X", dice_stats={"d6": {"4": 10}})
    record_dice(char, [("d6", 4), ("d6", 6)])
    assert char.dice_stats == {"d6": {"4": 11, "6": 1}}


def test_record_mixed_kinds_single_call():
    char = Character(user_id=1, name="X")
    record_dice(char, [("d20", 17), ("d8", 5), ("d8", 5)])
    assert char.dice_stats == {"d20": {"17": 1}, "d8": {"5": 2}}


def test_record_empty_is_noop():
    char = Character(user_id=1, name="X", dice_stats={"d4": {"2": 1}})
    before = char.dice_stats
    record_dice(char, [])
    assert char.dice_stats is before  # nessuna riassegnazione


def test_record_reassigns_dict_for_change_tracking():
    """Il dict esterno e quelli interni vengono sostituiti (no mutazione in place),
    così flag_modified + l'identità nuova garantiscono il persist SQLAlchemy."""
    original = {"d20": {"10": 1}}
    char = Character(user_id=1, name="X", dice_stats=original)
    record_dice(char, [("d20", 10)])
    assert char.dice_stats is not original
    assert original == {"d20": {"10": 1}}  # input non mutato
    assert char.dice_stats == {"d20": {"10": 2}}
