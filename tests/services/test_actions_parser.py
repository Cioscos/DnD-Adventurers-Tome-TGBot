"""Parser dei tempi di lancio / durate e attacchi per azione (core/game/actions.py)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.game.actions import attacks_per_action, parse_casting_time, parse_duration_rounds

CASTING_TIME_CASES = [
    ("1 azione", "action"),
    ("1 action", "action"),
    ("1 Action", "action"),
    ("1 azione bonus", "bonus_action"),
    ("1 bonus action", "bonus_action"),
    ("1 Bonus Action", "bonus_action"),
    ("1 reazione", "reaction"),
    ("1 reaction", "reaction"),
    ("1 reazione, che effettui quando vieni colpito", "reaction"),
    ("1 reaction, which you take when you are hit", "reaction"),
    ("1 azione, o 8 ore", "action"),
    ("  1 azione bonus  ", "bonus_action"),
    ("1 minuto", None),
    ("10 minutes", None),
    ("1 ora", None),
    ("8 hours", None),
    ("", None),
    (None, None),
]

DURATION_CASES = [
    ("1 round", 1),
    ("Up to 1 round", 1),
    ("Concentrazione, fino a 1 round", 1),
    ("1 minuto", 10),
    ("1 minute", 10),
    ("10 minuti", 100),
    ("10 minutes", 100),
    ("Concentrazione, fino a 1 minuto", 10),
    ("Concentration, up to 1 minute", 10),
    ("Up to 10 minutes", 100),
    ("1 ora", 600),
    ("1 hour", 600),
    ("8 ore", 4800),
    ("Up to 2 hours", 1200),
    ("Concentrazione, fino a 24 ore", 14400),
    ("Istantanea", None),
    ("Instantaneous", None),
    ("Speciale", None),
    ("Special", None),
    ("Until dispelled", None),
    ("10 giorni", None),
    ("", None),
    (None, None),
]


@pytest.mark.parametrize(("text", "expected"), CASTING_TIME_CASES)
def test_parse_casting_time(text, expected):
    assert parse_casting_time(text) == expected


@pytest.mark.parametrize(("text", "expected"), DURATION_CASES)
def test_parse_duration_rounds(text, expected):
    assert parse_duration_rounds(text) == expected


def _cls(name: str, level: int):
    return SimpleNamespace(class_name=name, level=level)


@pytest.mark.parametrize(
    ("name", "level", "expected"),
    [
        ("fighter", 1, 1), ("fighter", 4, 1), ("fighter", 5, 2), ("fighter", 10, 2),
        ("fighter", 11, 3), ("fighter", 19, 3), ("fighter", 20, 4), ("Guerriero", 11, 3),
        ("barbarian", 4, 1), ("barbarian", 5, 2), ("monk", 5, 2), ("Paladino", 5, 2),
        ("ranger", 5, 2), ("wizard", 20, 1), ("rogue", 11, 1), ("homebrew-class", 20, 1),
    ],
)
def test_attacks_per_action_table(name, level, expected):
    assert attacks_per_action([_cls(name, level)]) == expected


def test_attacks_per_action_fighter_11_is_3():
    assert attacks_per_action([_cls("fighter", 11)]) == 3


def test_attacks_per_action_multiclass_takes_max():
    assert attacks_per_action([_cls("fighter", 5), _cls("paladin", 5)]) == 2


def test_attacks_per_action_no_classes():
    assert attacks_per_action([]) == 1
