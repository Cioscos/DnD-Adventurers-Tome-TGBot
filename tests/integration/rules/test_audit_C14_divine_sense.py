"""Audit C14-38: Percezione del Divino 2014, PHB p.97: «1 + modificatore di Carisma» usi, senza minimo (Carisma 8 = 0 usi)."""
from __future__ import annotations

from tests.integration.rules.test_2014_bard import _ability
from tests.integration.rules.test_2014_paladin import DS, _paladin


async def test_divine_sense_has_no_use_with_charisma_8_phb_p97(client):
    cid = await _paladin(client, 1, charisma=8)
    assert await _ability(client, cid, DS) is None  # 0 usi: il privilegio non ha riga


async def test_divine_sense_with_charisma_10_has_one_use_phb_p97(client):
    assert (await _ability(client, await _paladin(client, 1, charisma=10), DS))["max_uses"] == 1
