"""Paladino 2014, giro di correzione 1 (I1-I12 della revisione del Task 25)."""
from __future__ import annotations

import pytest

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard import _ability, _full, _use
from tests.integration.rules.test_2014_bard_inspiration import _seat
from tests.integration.rules.test_2014_cleric import DOMAINS, POOL, _cleric
from tests.integration.rules.test_2014_paladin import CD, OATHS, _hp, _hurt, _new_turn, _paladin, _turn


async def _add_class(client, cid, name, level, subclass=None, hit_die=8) -> None:
    r = await client.post(f"/characters/{cid}/classes",
                          json={"class_name": name, "level": level, "hit_die": hit_die, "subclass": subclass})
    assert r.status_code == 201, r.text


# ---------------------------------------------------------------------------
# I1: la riserva condivisa passa da `pool_key` per ogni consumatore
# ---------------------------------------------------------------------------

async def _table_paladin_cleric(client, factory, domain, paladin_first):
    """Una serata con un Paladino 3 / Chierico 2 (ordine a scelta) al posto del GM e un eroe."""
    sid, hero = await seed_session(factory)
    as_user(GM_ID)
    if paladin_first:
        cid = await _paladin(client, 3, "devotion", wisdom=16)
        await _add_class(client, cid, "cleric", 2, DOMAINS[domain])
    else:
        cid = await _cleric(client, 2, domain, wisdom=16)
        await _add_class(client, cid, "paladin", 3, OATHS["devotion"], hit_die=10)
    await _seat(factory, cid)
    return sid, cid, hero


def _holder(paladin_first: bool) -> str:
    return CD if paladin_first else POOL


@pytest.mark.parametrize("paladin_first", [True, False])
async def test_preserve_life_uses_the_shared_pool_whichever_class_holds_it(client, test_session_factory, paladin_first):
    sid, cid, hero = await _table_paladin_cleric(client, test_session_factory, "life", paladin_first)
    await _hurt(test_session_factory, cid, 3)
    info = await client.get(f"/characters/{cid}/preserve-life")
    assert info.status_code == 200, info.text
    r = await client.post(f"/characters/{cid}/preserve-life", json={
        "allocations": [{"character_id": cid, "amount": 5}], "confirm_living": True})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, _holder(paladin_first)))["uses"] == 0
    assert (await _turn(client, cid))["action_used"] is True


@pytest.mark.parametrize("paladin_first", [True, False])
async def test_destructive_wrath_spends_the_shared_pool_whichever_class_holds_it(client, test_session_factory, paladin_first):
    sid, cid, hero = await _table_paladin_cleric(client, test_session_factory, "tempest", paladin_first)
    key = "cleric.wrath_of_the_storm"
    r = await client.post(f"/characters/{cid}/features/{key}/use",
                          json={"params": {"damage_type": "lightning", "destructive": True}})
    assert r.status_code == 200, r.text
    assert r.json()["state"]["data"]["maximized"] is True
    assert (await _ability(client, cid, _holder(paladin_first)))["uses"] == 0
    await _new_turn(client, cid)
    again = await client.post(f"/characters/{cid}/features/{key}/use",
                              json={"params": {"damage_type": "lightning", "destructive": True}})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "no_uses"
