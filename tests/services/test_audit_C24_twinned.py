"""Audit C24: Incantesimo Raddoppiato 2024 (Stregone p.142) vale per ogni incantesimo che, con uno slot superiore, prende un bersaglio in più.

Il manuale 2024 degli incantesimi (spells.md) dà il bersaglio in più per slot anche a Eroismo (p.285), Libertà di movimento (p.277)
e Forma gassosa (p.277), oltre a quelli già elencati.
"""
import pytest

from core.rules.catalog.y2024.sorcerer import TWINNED_SPELLS


@pytest.mark.parametrize("srd_index", ["heroism", "freedom-of-movement", "gaseous-form"])
def test_twinned_spell_covers_the_2024_spells_that_gain_a_target_with_a_higher_slot(srd_index):
    assert srd_index in TWINNED_SPELLS
