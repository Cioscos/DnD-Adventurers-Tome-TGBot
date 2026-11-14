"""GEN-C-18: Guerriero 2014, Campione (pag. 72)."""
from __future__ import annotations

import pytest

from tests.integration.rules.test_2014_bard import _full
from tests.integration.rules.test_2014_fighter import _fighter


@pytest.mark.parametrize("strength,bonus", [(8, 0), (10, 0), (14, 2), (20, 5)])
async def test_remarkable_athlete_adds_one_foot_per_strength_modifier_to_the_long_jump(client, strength, bonus):
    """Atleta Straordinario (Campione 7, p.72): il salto in lungo con rincorsa cresce di 30 cm per punto di modificatore di Forza."""
    cid = await _fighter(client, 7, "champion", strength=strength)
    assert (await _full(client, cid))["computed"]["long_jump_bonus_ft"] == bonus


async def test_no_long_jump_bonus_before_level_7_or_other_archetypes(client):
    assert not (await _full(client, await _fighter(client, 6, "champion", strength=16)))["computed"].get("long_jump_bonus_ft")
    assert not (await _full(client, await _fighter(client, 7, "battle_master", strength=16)))["computed"].get("long_jump_bonus_ft")
