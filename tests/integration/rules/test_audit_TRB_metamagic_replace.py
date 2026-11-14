"""Audit TRB: Metamagia, sostituzione delle opzioni.

Stregone 2014 (PHB 2014 p.109): le opzioni di Metamagia si scelgono al 3°, 10° e 17° livello e non si cambiano.
Stregone 2024 (PHB 2024 p.141): a ogni livello da stregone si può sostituire un'opzione."""
from __future__ import annotations

from tests.integration.rules.test_2014_bard import _full
from tests.integration.rules.test_2014_sorcerer_metamagic import _caster
from tests.integration.rules.test_2024_sorcerer import _caster24


async def _replace(client, cid):
    klass = (await _full(client, cid))["classes"][0]
    state = (await client.get(f"/characters/{cid}/classes/{klass['id']}/options/metamagic")).json()
    r = await client.post(f"/characters/{cid}/classes/{klass['id']}/options/replace",
                          json={"group": "metamagic", "old_key": "twinned", "new_key": "subtle"})
    return state, r


async def test_metamagic_2014_cannot_be_replaced(client):
    cid = await _caster(client, 3, "twinned", "quickened")
    state, r = await _replace(client, cid)
    assert state["replaceable"] is False
    assert r.status_code >= 400 and "option_not_replaceable" in r.text


async def test_metamagic_2024_can_be_replaced(client):
    cid = await _caster24(client, 2, "twinned", "quickened")
    state, r = await _replace(client, cid)
    assert state["replaceable"] is True
    assert r.status_code == 200, r.text
