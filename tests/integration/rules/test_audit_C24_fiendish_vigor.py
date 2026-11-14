"""Audit C24: Vigore Immondo 2024 (Warlock p.155): Vita Falsa 2024 dà 2d4+4 PF temporanei (p.271), quindi il massimo è 12."""
from __future__ import annotations

from tests.integration.rules.test_2014_bard import _full, _use
from tests.integration.rules.test_2024_warlock import _caster24


async def test_fiendish_vigor_gives_12_temporary_hit_points_the_maximum_of_2d4_plus_4(client):
    cid = await _caster24(client, 2, "fiendish_vigor")
    r = await _use(client, cid, "warlock.fiendish_vigor")
    assert r.status_code == 200, r.text
    assert r.json()["temp_hp"] == 12 and (await _full(client, cid))["temp_hp"] == 12
