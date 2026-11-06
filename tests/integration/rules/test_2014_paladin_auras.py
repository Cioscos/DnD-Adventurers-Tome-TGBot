"""Paladino 2014 (Task 25): le aure di Protezione e di Interdizione sui compagni della serata, con la conferma al tiro (D1)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from core.db.models import Character, SessionParticipant
from core.rules.auras import projected_auras
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard import _full, _roll_keys
from tests.integration.rules.test_2014_paladin import _hurt, _paladin

PROTECTION, WARDING = "aura:protection", "aura:warding"


async def _table(client, test_session_factory, level=6, oath=None, charisma=16):
    """Una serata con il paladino (GM) e un eroe: `(session_id, paladin, hero)`."""
    sid, hero = await seed_session(test_session_factory)
    as_user(GM_ID)
    paladin = await _paladin(client, level, oath, charisma=charisma)
    async with test_session_factory() as s:
        part = (await s.execute(select(SessionParticipant).where(SessionParticipant.user_id == GM_ID))).scalar_one()
        part.character_id = paladin
        await s.commit()
    as_user(PLAYER_ID)
    return sid, paladin, hero


async def _set_hp(factory, cid, hp):
    await _hurt(factory, cid, hp)


async def test_an_ally_is_offered_the_aura_of_protection_with_the_paladin_charisma(client, test_session_factory):
    _, _, hero = await _table(client, test_session_factory, charisma=16)
    listed = (await client.get(f"/characters/{hero}/roll-options", params={"roll": "save", "ability": "dexterity"})).json()
    option = next(o for o in listed if o["key"] == PROTECTION)
    assert option["phase"] == "before" and "gittata" in option["label"]
    assert PROTECTION in await _roll_keys(client, hero, "death_save")


@pytest.mark.parametrize("charisma,bonus", [(16, 3), (8, 1)])
async def test_the_aura_bonus_is_the_paladin_charisma_with_a_minimum_of_one_and_goes_into_the_save(
        client, test_session_factory, charisma, bonus):
    _, _, hero = await _table(client, test_session_factory, charisma=charisma)
    plain = (await client.post(f"/characters/{hero}/saving_throws/dexterity/roll", json={"die": 10})).json()
    r = await client.post(f"/characters/{hero}/saving_throws/dexterity/roll", json={"die": 10, "options": [PROTECTION]})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == plain["total"] + bonus


async def test_no_aura_without_a_session_or_a_paladin_of_level_6(client, test_session_factory):
    alone = await _paladin(client, 6, charisma=16)
    assert PROTECTION not in await _roll_keys(client, alone, "save", ability="dexterity")
    _, _, hero = await _table(client, test_session_factory, level=5)
    assert PROTECTION not in await _roll_keys(client, hero, "save", ability="dexterity")


async def test_the_aura_needs_a_conscious_paladin(client, test_session_factory):
    _, paladin, hero = await _table(client, test_session_factory)
    await _set_hp(test_session_factory, paladin, 0)
    assert PROTECTION not in await _roll_keys(client, hero, "save", ability="dexterity")


async def test_a_paladin_does_not_stack_a_fellow_paladin_aura_on_his_own(client, test_session_factory):
    sid, hero = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    own = await _paladin(client, 6, charisma=10)
    async with test_session_factory() as s:
        part = (await s.execute(select(SessionParticipant).where(SessionParticipant.user_id == PLAYER_ID))).scalar_one()
        part.character_id = own
        await s.commit()
    as_user(GM_ID)
    friend = await _paladin(client, 9, charisma=20)
    async with test_session_factory() as s:
        part = (await s.execute(select(SessionParticipant).where(SessionParticipant.user_id == GM_ID))).scalar_one()
        part.character_id = friend
        await s.commit()
    as_user(PLAYER_ID)
    assert PROTECTION not in await _roll_keys(client, own, "save", ability="dexterity")


async def test_the_aura_of_warding_halves_spell_damage_for_an_ally_even_if_the_paladin_is_down(client, test_session_factory):
    _, paladin, hero = await _table(client, test_session_factory, level=7, oath="ancients")
    assert WARDING in await _roll_keys(client, hero, "damage_taken")
    await _set_hp(test_session_factory, paladin, 0)  # il manuale non chiede che sia cosciente
    assert WARDING in await _roll_keys(client, hero, "damage_taken")
    await client.patch(f"/characters/{hero}/hp", json={"op": "set_max", "value": 40})
    await client.patch(f"/characters/{hero}/hp", json={"op": "set_current", "value": 40})
    r = await client.patch(f"/characters/{hero}/hp", json={"op": "damage", "value": 11, "options": [WARDING]})
    assert r.status_code == 200, r.text
    assert r.json()["option_result"]["damage_after"] == 5


async def test_other_oaths_do_not_ward_the_party(client, test_session_factory):
    _, _, hero = await _table(client, test_session_factory, level=7, oath="devotion")
    assert WARDING not in await _roll_keys(client, hero, "damage_taken")


async def test_the_option_is_refused_when_nobody_projects_the_aura(client, test_session_factory):
    hero = (await seed_session(test_session_factory))[1]
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{hero}/saving_throws/dexterity/roll", json={"die": 10, "options": [PROTECTION]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"


async def test_the_aura_range_grows_at_level_18(client, test_session_factory):
    ranges = {}
    for level in (17, 18):
        char = await _paladin(client, level, charisma=16)
        async with test_session_factory() as s:
            row = await s.get(Character, char)
            await s.refresh(row, ["classes", "ability_scores", "items"])
            ranges[level] = [a["range_ft"] for a in projected_auras(row)]
    assert ranges == {17: [10], 18: [30]}
