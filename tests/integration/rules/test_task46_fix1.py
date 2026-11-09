"""Task 46, correzioni della revisione: Resilienza Celestiale (riposo e Astuzia Magica), Passo Rinfrescante verso un'altra creatura,
Incantesimi Potenti, Forza Vivificante che svanisce con l'Ira, etichette di Punizione Ispiratrice."""
from __future__ import annotations

import pytest

from core.rules.catalog.y2024.paladin_oaths import _KEEP
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard import _ability, _full, _resolve
from tests.integration.rules.test_2014_bard_inspiration import _second_ally, _seat
from tests.integration.rules.test_2014_warlock import _pact_slots
from tests.integration.rules.test_2014_warlock_invocations import _cast, _spells_by_index
from tests.integration.rules.test_2024_barbarian import _new_turn, _rage
from tests.integration.rules.test_2024_barbarian_paths import TREE, _barbarian
from tests.integration.rules.test_2024_cleric import _cantrip, _cleric24
from tests.integration.rules.test_2024_warlock_patrons import STEPS, P, _make

CUNNING, LIFE, POTENT = P + "magical_cunning", "barbarian.life_giving_force", "cleric.improved_potent_spellcasting"


@pytest.fixture(autouse=True)
def _dice_at_five(monkeypatch):
    monkeypatch.setattr("random.randint", lambda a, b: min(5, b))


async def _table(client, test_session_factory, build):
    sid, hero = await seed_session(test_session_factory)
    as_user(GM_ID)
    cid = await build(client)
    await _seat(test_session_factory, cid)
    return sid, cid, hero


async def _temp(client, cid, user=PLAYER_ID) -> int:
    as_user(user)
    return (await client.get(f"/characters/{cid}")).json()["temp_hp"]


async def _set_temp(client, cid, value, user=PLAYER_ID):
    as_user(user)
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "set_temp", "value": value})).status_code == 200


async def _celestial(client):
    return await _make(client, "celestial", 10, charisma=16)  # livello 10 + Car 3 a te, 5 + 3 = 8 agli altri


# ---------------------------------------------------------------------------
# I1: Resilienza Celestiale
# ---------------------------------------------------------------------------

async def _spend_pact_slot(client, cid):
    slot = (await _pact_slots(client, cid))[0]
    await client.patch(f"/characters/{cid}/spell_slots/{slot['id']}", json={"used": 1})


async def test_magical_cunning_delivers_the_celestial_value_to_up_to_five_seated_creatures(client, test_session_factory):
    sid, cid, hero = await _table(client, test_session_factory, _celestial)
    second = await _second_ally(test_session_factory, sid)
    as_user(GM_ID)
    row = next(a for a in (await _full(client, cid))["abilities"] if a["feature_key"] == CUNNING)
    assert row["gives_to_ally"] is True and row["ally_max"] == 5
    await _spend_pact_slot(client, cid)
    r = await client.post(f"/characters/{cid}/features/{CUNNING}/use", json={"params": {"target_character_ids": [hero, second]}})
    assert r.status_code == 200, r.text
    assert [e["given"] for e in r.json()["temp_received"]] == [8, 8] and r.json()["given"] is None
    assert await _temp(client, hero) == 8 and await _temp(client, second, 9001) == 8
    assert await _temp(client, cid, GM_ID) == 13  # a te: livello + Carisma


async def test_magical_cunning_refuses_a_creature_outside_the_table_and_spends_nothing(client, test_session_factory):
    _sid, cid, _hero = await _table(client, test_session_factory, _celestial)
    as_user(9999)
    outsider = (await client.post("/characters", json={"name": "Estraneo"})).json()["id"]
    as_user(GM_ID)
    await _spend_pact_slot(client, cid)
    r = await client.post(f"/characters/{cid}/features/{CUNNING}/use", json={"params": {"target_character_ids": [outsider]}})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_target"
    assert (await _pact_slots(client, cid))[0]["used"] == 1 and await _temp(client, cid, GM_ID) == 0


async def test_magical_cunning_of_a_non_celestial_warlock_does_not_ask_for_allies(client, test_session_factory):
    _sid, cid, _hero = await _table(client, test_session_factory, lambda c: _make(c, "fiend", 10, charisma=16))
    as_user(GM_ID)
    row = next(a for a in (await _full(client, cid))["abilities"] if a["feature_key"] == CUNNING)
    assert row["gives_to_ally"] is False


@pytest.mark.parametrize("kind", ["short", "long"])
async def test_the_rest_delivers_celestial_resilience_to_the_chosen_creatures(client, test_session_factory, kind):
    _sid, cid, hero = await _table(client, test_session_factory, _celestial)
    as_user(GM_ID)
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": kind, "confirm_early": True, "temp_hp_allies": [hero]})
    assert r.status_code == 200, r.text
    assert r.json()["temp_received"] == [{"name": "Eroe", "given": 8, "temp_hp": 8, "applied": True}]
    assert await _temp(client, hero) == 8 and await _temp(client, cid, GM_ID) == 13


async def test_the_rest_keeps_the_higher_temporary_hp_of_the_receiver(client, test_session_factory):
    _sid, cid, hero = await _table(client, test_session_factory, _celestial)
    await _set_temp(client, hero, 20)
    as_user(GM_ID)
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "temp_hp_allies": [hero]})
    assert r.json()["temp_received"][0]["applied"] is False and await _temp(client, hero) == 20


async def test_the_rest_refuses_bad_receivers_before_resting(client, test_session_factory):
    sid, cid, hero = await _table(client, test_session_factory, _celestial)
    others = [await _second_ally(test_session_factory, sid, user=9000 + i) for i in range(1, 6)]
    as_user(GM_ID)
    for ids in ([cid], [987654], [hero, hero], [hero, *others]):  # sé stessi, inesistente, doppio, sei creature
        r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "temp_hp_allies": ids})
        assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_target", (ids, r.text)
    assert await _temp(client, cid, GM_ID) == 0  # il riposo non è avvenuto


async def test_a_character_without_celestial_resilience_cannot_hand_out_temporary_hp_on_rest(client, test_session_factory):
    _sid, cid, hero = await _table(client, test_session_factory, lambda c: _make(c, "celestial", 9, charisma=16))
    as_user(GM_ID)
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "temp_hp_allies": [hero]})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_target"


# ---------------------------------------------------------------------------
# I1: Passo Rinfrescante verso un'altra creatura
# ---------------------------------------------------------------------------

OTHER = STEPS + "_refreshing_other"


async def _archfey(client):
    return await _make(client, "archfey", 5)


async def _misty(client, cid) -> int:
    return (await _spells_by_index(client, cid))["misty-step"]["id"]


async def test_refreshing_step_offers_the_ally_and_delivers_the_d10_to_the_seated_creature(client, test_session_factory):
    _sid, cid, hero = await _table(client, test_session_factory, _archfey)
    as_user(GM_ID)
    spell = await _misty(client, cid)
    listed = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "cast", "spell_id": spell})).json()
    assert next(o for o in listed if o["key"] == OTHER)["gives_to_ally"] is True
    assert not next(o for o in listed if o["key"] == STEPS + "_refreshing")["gives_to_ally"]
    r = await _cast(client, cid, spell, free_cast=True, options=[OTHER], option_inputs={OTHER: {"target_character_id": hero}})
    assert r.status_code == 200, r.text
    assert await _temp(client, hero) == 5 and await _temp(client, cid, GM_ID) == 0
    assert (await _ability(client, cid, STEPS))["uses"] == 2
    assert any("Eroe" in e["it"] for e in r.json()["option_result"]["effects"])
    as_user(PLAYER_ID)
    assert any(e["description"].startswith("PF temporanei: 5 (0") for e in (await client.get(f"/characters/{hero}/history")).json())


async def test_refreshing_step_without_a_target_stays_textual(client, test_session_factory):
    _sid, cid, hero = await _table(client, test_session_factory, _archfey)
    as_user(GM_ID)
    r = await _cast(client, cid, await _misty(client, cid), free_cast=True, options=[OTHER])
    assert r.status_code == 200 and await _temp(client, hero) == 0 and "GM" in r.json()["option_result"]["effects"][0]["it"]


async def test_refreshing_step_refuses_a_stranger_and_spends_nothing(client, test_session_factory):
    _sid, cid, _hero = await _table(client, test_session_factory, _archfey)
    as_user(GM_ID)
    for target in (cid, 987654):
        r = await _cast(client, cid, await _misty(client, cid), free_cast=True, options=[OTHER], option_inputs={OTHER: {"target_character_id": target}})
        assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_target", r.text
    assert (await _ability(client, cid, STEPS))["uses"] == 3


# ---------------------------------------------------------------------------
# I1: Incantesimi Potenti
# ---------------------------------------------------------------------------

async def _potent(client):
    cid = await _cleric24(client, 14, wisdom=16)
    await _resolve(client, cid, "blessed_strikes", ["potent_spellcasting"])
    return cid


async def test_improved_potent_spellcasting_delivers_twice_wisdom_to_the_seated_creature(client, test_session_factory):
    _sid, cid, hero = await _table(client, test_session_factory, _potent)
    as_user(GM_ID)
    spell = await _cantrip(client, cid)
    listed = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "spell_damage", "spell_id": spell})).json()
    assert next(o for o in listed if o["key"] == POTENT)["gives_to_ally"] is True
    body = {"main_rolls": [4, 3, 2], "options": [POTENT], "option_inputs": {POTENT: {"target_character_id": hero}}}
    r = await client.post(f"/characters/{cid}/spells/{spell}/roll_damage", json=body)
    assert r.status_code == 200, r.text
    assert await _temp(client, hero) == 6  # 2 x Saggezza (+3)
    as_user(GM_ID)
    r = await client.post(f"/characters/{cid}/spells/{spell}/roll_damage", json={**body, "option_inputs": {POTENT: {"target_character_id": cid}}})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_target"


# ---------------------------------------------------------------------------
# I2: Forza Vivificante svanisce con l'Ira
# ---------------------------------------------------------------------------

async def _life(client):
    cid = await _barbarian(client, 3, TREE)
    assert (await _rage(client, cid)).status_code == 200
    await _new_turn(client, cid)
    return cid


async def _give_life(client, cid, hero):
    as_user(GM_ID)
    r = await client.post(f"/characters/{cid}/features/{LIFE}/use", json={"params": {"target_character_id": hero}})
    assert r.status_code == 200 and r.json()["temp_received"][0]["applied"] is True, r.text


async def _end_rage(client, cid, how):
    as_user(GM_ID)
    if how == "manual":
        assert (await client.delete(f"/characters/{cid}/active-states/rage")).status_code == 200
    elif how == "long_rest":
        assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})).status_code == 200
    else:  # i round passano: l'Ira scade
        for _ in range(101):
            r = await client.post(f"/characters/{cid}/rounds/tick")
            assert r.status_code == 200, r.text


@pytest.mark.parametrize("how", ["manual", "long_rest", "rounds"])
async def test_life_giving_temporary_hp_vanish_when_the_rage_ends(client, test_session_factory, how):
    _sid, cid, hero = await _table(client, test_session_factory, _life)
    await _give_life(client, cid, hero)
    assert await _temp(client, hero) == 10
    await _end_rage(client, cid, how)
    assert await _temp(client, hero) == 0
    as_user(PLAYER_ID)
    assert any("Ira" in e["description"] for e in (await client.get(f"/characters/{hero}/history")).json())


async def test_what_is_left_of_the_life_giving_points_vanishes_too(client, test_session_factory):
    _sid, cid, hero = await _table(client, test_session_factory, _life)
    await _give_life(client, cid, hero)
    await _set_temp(client, hero, 4)  # ne ha spesi 6
    await _end_rage(client, cid, "manual")
    assert await _temp(client, hero) == 0


async def test_higher_temporary_hp_from_another_source_survive_the_end_of_the_rage(client, test_session_factory):
    _sid, cid, hero = await _table(client, test_session_factory, _life)
    await _give_life(client, cid, hero)
    await _set_temp(client, hero, 30)  # un altro privilegio, più alto: il maggiore resta
    await _end_rage(client, cid, "manual")
    assert await _temp(client, hero) == 30


async def test_temporary_hp_the_receiver_already_had_are_not_touched(client, test_session_factory):
    _sid, cid, hero = await _table(client, test_session_factory, _life)
    await _set_temp(client, hero, 30)
    as_user(GM_ID)
    r = await client.post(f"/characters/{cid}/features/{LIFE}/use", json={"params": {"target_character_id": hero}})
    assert r.json()["temp_received"][0]["applied"] is False
    await _end_rage(client, cid, "manual")
    assert await _temp(client, hero) == 30


# ---------------------------------------------------------------------------
# Punizione Ispiratrice: un solo ricevente, e le etichette lo dicono
# ---------------------------------------------------------------------------

def test_inspiring_smite_labels_say_that_only_one_creature_receives_the_share():
    for key in ("half", "none"):
        for lang in ("it", "en"):
            label = _KEEP[key][lang].lower()
            assert "tutti agli altri" not in label and "all to others" not in label
            assert "un solo" in label or "only one" in label
