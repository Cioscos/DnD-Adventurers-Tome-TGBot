"""Paladino 2014, giro di correzione 1: Sentinella Imperitura prima dello 0 PF (I2) e resistenza una volta sola (I12)."""
from __future__ import annotations

from core.db.models import Character
from tests.integration.rules.test_2014_bard import _ability, _full, _use
from tests.integration.rules.test_2014_paladin import _hp, _hurt, _paladin

US = "paladin.undying_sentinel"
WARD = "paladin.aura_of_warding"


async def _damage(client, cid, value, **extra):
    return await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": value, **extra})


async def _ancients(client, level=15) -> int:
    return await _paladin(client, level, "ancients")


async def _keys_for_damage(client, cid, damage=None) -> list[str]:
    params = {"roll": "damage_taken", **({"damage": damage} if damage is not None else {})}
    r = await client.get(f"/characters/{cid}/roll-options", params=params)
    assert r.status_code == 200, r.text
    return [o["key"] for o in r.json()]


# ---------------------------------------------------------------------------
# I2: Sentinella Imperitura è una conferma prima dello 0 PF
# ---------------------------------------------------------------------------

async def test_the_sentinel_is_offered_only_when_the_damage_would_drop_the_paladin_to_zero(client):
    cid = await _ancients(client)
    hp = await _hp(client, cid)
    assert US in await _keys_for_damage(client, cid, hp)
    assert US in await _keys_for_damage(client, cid, hp + 50)
    assert US not in await _keys_for_damage(client, cid, hp - 1)


async def test_the_sentinel_is_not_offered_at_zero_hp_or_without_uses(client, test_session_factory):
    cid = await _ancients(client)
    await _hurt(test_session_factory, cid, 0)
    assert US not in await _keys_for_damage(client, cid, 5)
    spent = await _ancients(client)
    assert (await _damage(client, spent, await _hp(client, spent), options=[US])).status_code == 200
    await _hurt(test_session_factory, spent, 10)
    assert US not in await _keys_for_damage(client, spent, 10)  # nessun uso


async def test_confirming_the_sentinel_stops_the_paladin_at_one_hp_with_no_zero_hp_consequences(client, test_session_factory):
    cid = await _ancients(client)
    async with test_session_factory() as s:
        char = await s.get(Character, cid)
        char.settings = {**(char.settings or {}), "concentration_item_spell": "x"}
        await s.commit()
    hp = await _hp(client, cid)
    r = await _damage(client, cid, hp + 4, options=[US])
    assert r.status_code == 200, r.text
    full = r.json()
    assert full["current_hit_points"] == 1
    assert not full["conditions"].get("unconscious") and not full["conditions"].get("prone")
    assert not (full["death_saves"] or {}).get("failures") and not (full["death_saves"] or {}).get("stable")
    assert full["concentration_save"] is not None  # non è privo di sensi: si tira, non cade da sola
    assert (await _ability(client, cid, US))["uses"] == 0


async def test_without_the_confirmation_the_paladin_drops_to_zero_as_usual(client):
    cid = await _ancients(client)
    r = await _damage(client, cid, await _hp(client, cid))
    assert r.json()["current_hit_points"] == 0 and (await _ability(client, cid, US))["uses"] == 1


async def test_a_confirmed_sentinel_is_not_spent_when_the_damage_does_not_reach_zero(client):
    cid = await _ancients(client)
    hp = await _hp(client, cid)
    r = await _damage(client, cid, 3, options=[US])
    assert r.status_code == 200 and r.json()["current_hit_points"] == hp - 3
    assert (await _ability(client, cid, US))["uses"] == 1


async def test_a_confirmed_sentinel_does_not_save_from_an_instant_death_and_is_not_spent(client):
    cid = await _ancients(client)
    hp = await _hp(client, cid)
    r = await _damage(client, cid, hp * 3, options=[US])
    assert r.status_code == 200 and r.json()["is_dead"] is True
    assert (await _ability(client, cid, US))["uses"] == 1


async def test_the_sentinel_cannot_be_chosen_from_zero_hp(client, test_session_factory):
    cid = await _ancients(client)
    await _hurt(test_session_factory, cid, 0)
    r = await _damage(client, cid, 2, options=[US])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"
    assert (await _ability(client, cid, US))["uses"] == 1


async def test_undoing_the_damage_gives_the_sentinel_use_back(client):
    cid = await _ancients(client)
    hp = await _hp(client, cid)
    r = await _damage(client, cid, hp, options=[US])
    assert r.json()["current_hit_points"] == 1
    undo = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": r.json()["hp_undo_id"]})
    assert undo.status_code == 200 and undo.json()["current_hit_points"] == hp
    assert (await _ability(client, cid, US))["uses"] == 1


async def test_the_sentinel_is_a_confirmation_not_a_feature_to_use_after_the_fact(client):
    cid = await _ancients(client)
    assert (await _ability(client, cid, US))["has_on_use"] is False
    assert (await _use(client, cid, US)).status_code in (404, 409)


# ---------------------------------------------------------------------------
# I12: la resistenza conta una volta sola
# ---------------------------------------------------------------------------

async def test_the_warding_aura_does_not_stack_with_a_resistance_the_client_already_sent(client):
    cid = await _paladin(client, 7, "ancients")
    start = await _hp(client, cid)
    r = await _damage(client, cid, 10, raw_value=20, damage_type="fire", damage_modifier="half", options=[WARD])
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == start - 10


async def test_the_warding_aura_does_not_stack_with_a_resistance_of_the_sheet(client, test_session_factory):
    cid = await _paladin(client, 7, "ancients")
    async with test_session_factory() as s:
        char = await s.get(Character, cid)
        char.damage_modifiers = {"resistances": ["fire"]}
        await s.commit()
    start = await _hp(client, cid)
    r = await _damage(client, cid, 20, damage_type="fire", options=[WARD])
    assert r.json()["current_hit_points"] == start - 10


async def test_the_warding_aura_alone_halves_and_with_a_vulnerability_it_cancels_out(client, test_session_factory):
    cid = await _paladin(client, 7, "ancients")
    start = await _hp(client, cid)
    assert (await _damage(client, cid, 20, damage_type="fire", options=[WARD])).json()["current_hit_points"] == start - 10
    async with test_session_factory() as s:
        char = await s.get(Character, cid)
        char.damage_modifiers = {"vulnerabilities": ["cold"]}
        await s.commit()
    cold = await _damage(client, cid, 20, damage_type="cold", options=[WARD])
    assert cold.json()["current_hit_points"] == start - 10 - 20  # resistenza e vulnerabilità: danno normale
