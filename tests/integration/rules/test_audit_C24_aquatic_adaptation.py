"""Audit C24: Adattamento Acquatico 2024 (Stregone, Stregoneria Aberrante 14, p.146): velocità di nuoto pari al DOPPIO della Velocità."""
from __future__ import annotations

from tests.integration.rules.test_2014_bard import _full, _use
from tests.integration.rules.test_2024_sorcerer_subclasses import P, _make


async def test_aquatic_adaptation_gives_a_swim_speed_double_the_walking_speed(client):
    cid = await _make(client, "aberrant", 14)
    assert (await _use(client, cid, P + "revelation_in_flesh", params={"swim": True})).status_code == 200
    computed = (await _full(client, cid))["computed"]
    assert computed["swim_speed"] == 2 * computed["speed"]
