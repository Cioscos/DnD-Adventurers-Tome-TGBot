"""Audit C24: Deflagrazione Respingente 2024 (Warlock p.157) vale per ogni trucchetto Warlock con tiro per colpire.

Spruzzo Velenoso 2024 è un attacco a distanza con incantesimo (spells.md p.306): la supplica deve valere anche per lui.
"""
from core.rules.catalog.y2024.warlock_invocations import INVOCATION_ROWS


def test_repelling_blast_is_offered_for_poison_spray_which_has_an_attack_roll_in_2024():
    keys = {s.option_key for s in INVOCATION_ROWS}
    assert {"repelling_blast__eldritch_blast", "repelling_blast__chill_touch", "repelling_blast__poison_spray"} <= keys
