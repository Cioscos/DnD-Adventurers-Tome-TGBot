"""Tiro di cura degli incantesimi (R41) e i privilegi del Dominio della Vita che lo toccano."""
from __future__ import annotations

import pytest

from tests.integration.rules.test_2014_bard import _full, _roll_keys
from tests.integration.rules.test_2014_cleric import _cleric


async def _heal_spell(client, cid, index="cure-wounds", level=1, name="Cura ferite") -> int:
    r = await client.post(f"/characters/{cid}/spells", json={
        "name": name, "level": level, "srd_index": index, "is_prepared": True,
        "class_id": (await _full(client, cid))["classes"][0]["id"]})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _roll(client, cid, spell, **body):
    """``main_rolls``: i dadi che il server tira (il client non li sceglie), fissati qui per il test."""
    from unittest.mock import patch
    rolls = body.pop("main_rolls", None)
    if rolls is None:
        return await client.post(f"/characters/{cid}/spells/{spell}/roll_healing", json=body)
    with patch("api.routers.spells.random.randint", side_effect=list(rolls)):
        return await client.post(f"/characters/{cid}/spells/{spell}/roll_healing", json=body)


async def test_cure_wounds_rolls_the_dice_and_adds_the_casting_modifier(client):
    cid = await _cleric(client, 5, wisdom=16)  # Saggezza +3
    spell = await _heal_spell(client, cid)
    r = await _roll(client, cid, spell, main_rolls=[5])
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 5 + 3 and r.json()["modifier"] == 3 and r.json()["main_kind"] == "d8"
    up = await _roll(client, cid, spell, casting_level=3, main_rolls=[1, 2, 3])
    assert up.json()["total"] == 6 + 3 and up.json()["casting_level"] == 3


async def test_the_server_rolls_when_the_client_sends_no_dice(client):
    cid = await _cleric(client, 5, wisdom=10)
    spell = await _heal_spell(client, cid, "healing-word", 1, "Parola curativa")
    totals = {(await _roll(client, cid, spell)).json()["total"] for _ in range(30)}
    assert totals <= {1, 2, 3, 4} and len(totals) > 1  # 1d4, modificatore 0


async def test_the_dice_sent_by_the_client_are_ignored(client):
    cid = await _cleric(client, 5, wisdom=10)
    spell = await _heal_spell(client, cid, "healing-word", 1, "Parola curativa")
    from api.schemas.spell import RollHealingRequest
    assert "main_rolls" not in RollHealingRequest.model_fields
    r = await client.post(f"/characters/{cid}/spells/{spell}/roll_healing", json={"main_rolls": [4]})
    assert r.status_code == 200 and r.json()["total"] in {1, 2, 3, 4}


async def test_a_spell_that_does_not_heal_is_refused_and_the_level_is_checked(client):
    cid = await _cleric(client, 5)
    other = (await client.post(f"/characters/{cid}/spells", json={"name": "Dardo", "level": 1, "srd_index": "magic-missile"})).json()["id"]
    assert (await _roll(client, cid, other)).status_code == 400
    spell = await _heal_spell(client, cid)
    assert (await _roll(client, cid, spell, casting_level=0)).status_code == 400
    assert (await _roll(client, cid, spell, casting_level=10)).status_code == 400


async def test_heal_is_fixed_and_grows_with_the_slot(client):
    cid = await _cleric(client, 11, wisdom=20)
    spell = await _heal_spell(client, cid, "heal", 6, "Cura completa")
    assert (await _roll(client, cid, spell)).json()["total"] == 70
    assert (await _roll(client, cid, spell, casting_level=8)).json()["total"] == 90


async def test_apply_to_self_adds_the_hit_points_and_revives_from_zero(client):
    cid = await _cleric(client, 5, wisdom=10)
    spell = await _heal_spell(client, cid)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 0})
    assert (await client.post(f"/characters/{cid}/death_saves/roll", json={"die": 5})).status_code == 200
    assert (await _full(client, cid))["death_saves"]["failures"] == 1
    r = await _roll(client, cid, spell, main_rolls=[4], apply_to_self=True)
    assert r.status_code == 200 and r.json()["healed"] == 4
    full = await _full(client, cid)
    assert full["current_hit_points"] == 4 and full["death_saves"]["failures"] == 0 and full["death_saves"]["successes"] == 0
    plain = await _roll(client, cid, spell, main_rolls=[4])
    assert plain.json()["healed"] == 0 and (await _full(client, cid))["current_hit_points"] == 4


async def test_disciple_of_life_adds_two_plus_the_slot_level(client):
    life = await _cleric(client, 1, "life", wisdom=10)
    spell = await _heal_spell(client, life)
    assert (await _roll(client, life, spell, main_rolls=[4])).json()["total"] == 4 + 3
    assert (await _roll(client, life, spell, casting_level=2, main_rolls=[4, 4])).json()["total"] == 8 + 4
    war = await _cleric(client, 1, "war", wisdom=10)
    assert (await _roll(client, war, await _heal_spell(client, war), main_rolls=[4])).json()["total"] == 4


async def test_supreme_healing_maximises_the_dice_from_level_17(client):
    life = await _cleric(client, 17, "life", wisdom=10)
    spell = await _heal_spell(client, life)
    r = await _roll(client, life, spell, casting_level=2, main_rolls=[1, 1])
    assert r.json()["maximized"] is True and r.json()["main_rolls"] == [8, 8] and r.json()["total"] == 16 + 4
    low = await _cleric(client, 16, "life", wisdom=10)
    assert (await _roll(client, low, await _heal_spell(client, low), main_rolls=[1])).json()["maximized"] is False


async def test_blessed_healer_heals_the_caster_when_confirmed(client):
    cid = await _cleric(client, 6, "life", wisdom=10)
    spell = await _heal_spell(client, cid)
    assert "cleric.blessed_healer" in await _roll_keys(client, cid, "spell_healing", spell_id=spell, casting_level=2)
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20})
    hp = (await _full(client, cid))["current_hit_points"]
    r = await _roll(client, cid, spell, casting_level=2, main_rolls=[2, 2], options=["cleric.blessed_healer"])
    assert r.status_code == 200, r.text
    assert r.json()["self_healed"] == 4 and (await _full(client, cid))["current_hit_points"] == hp + 4
    nope = await _roll(client, cid, spell, main_rolls=[2])
    assert nope.json()["self_healed"] == 0


async def test_blessed_healer_is_not_offered_before_level_6_or_to_other_domains(client):
    for level, domain in ((5, "life"), (6, "war")):
        cid = await _cleric(client, level, domain)
        spell = await _heal_spell(client, cid)
        assert "cleric.blessed_healer" not in await _roll_keys(client, cid, "spell_healing", spell_id=spell, casting_level=1)
        r = await _roll(client, cid, spell, main_rolls=[2], options=["cleric.blessed_healer"])
        assert r.status_code == 409


@pytest.mark.parametrize("index,level,base", [("revivify", 3, 1), ("raise-dead", 5, 1), ("goodberry", 1, 1), ("mass-heal", 9, 700)])
async def test_disciple_of_life_covers_every_spell_of_first_level_or_more_that_restores_hit_points(client, index, level, base):
    life = await _cleric(client, 1, "life", wisdom=10)
    spell = await _heal_spell(client, life, index, level, index)
    r = await _roll(client, life, spell)
    assert r.status_code == 200, r.text
    assert r.json()["total"] == base + 2 + level and r.json()["main_rolls"] == []
    war = await _cleric(client, 1, "war", wisdom=10)
    assert (await _roll(client, war, await _heal_spell(client, war, index, level, index))).json()["total"] == base
