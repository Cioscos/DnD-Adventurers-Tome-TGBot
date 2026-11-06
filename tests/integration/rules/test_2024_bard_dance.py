"""Bardo 2024, Collegio della Danza (Task 32): Passo Abbagliante, Movimento Ispiratore, Passo a Due, Evasione Guida."""
from __future__ import annotations

import pytest

from tests.integration.rules.test_2014_bard import BI, _ability, _full, _keys_of, _roll_keys, _states, _use
from tests.integration.rules.test_2014_monk import ARMOR, SHIELD, _equip
from tests.integration.rules.test_2014_rogue import _full_hp, _hurt, _save
from tests.integration.rules.test_2024_bard import DANCE, LORE, _bard24, _set_uses, _turn

DANCING = "bard.dazzling_footwork_dance"
BARDIC_DAMAGE = "bard.bardic_damage"
AGILE = "bard.agile_strikes"
EVASION = "bard.leading_evasion"
EVASION_OK, EVASION_KO = "bard.leading_evasion_success", "bard.leading_evasion_failed"
SWORD = {"name": "Spada", "item_type": "weapon", "item_metadata": {"damage_dice": "1d8", "weapon_type": "melee", "properties": []}}


async def _unarmed(client, cid, *options, die=10):
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"die": die, "options": list(options), "confirm_extra_attack": True})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(autouse=True)
def _fixed_d20(monkeypatch):
    """I dadi di danno restano casuali, ma non l'altro d20 di un tiro con vantaggio."""
    monkeypatch.setattr("random.randint", lambda a, b: min(10, b))


# ---------------------------------------------------------------------------
# Passo Abbagliante
# ---------------------------------------------------------------------------

async def test_the_dance_college_brings_its_rows_at_the_right_level(client):
    assert {"bard.dazzling_footwork"} <= await _keys_of(client, await _bard24(client, 3, DANCE))
    assert "bard.dazzling_footwork" not in await _keys_of(client, await _bard24(client, 3, LORE))
    assert "bard.inspiring_movement" not in await _keys_of(client, await _bard24(client, 5, DANCE))
    assert {"bard.inspiring_movement", "bard.tandem_footwork"} <= await _keys_of(client, await _bard24(client, 6, DANCE))
    assert "bard.leading_evasion" in await _keys_of(client, await _bard24(client, 14, DANCE))
    assert "bard.leading_evasion" not in await _keys_of(client, await _bard24(client, 13, DANCE))


async def test_unarmored_defense_is_ten_plus_dexterity_and_charisma_and_yields_to_armor_or_shield(client):
    cid = await _bard24(client, 3, DANCE, dexterity=14, charisma=16)
    assert (await _full(client, cid))["ac_breakdown"]["base"] == 10 + 2 + 3
    armor = await _equip(client, cid, **ARMOR)
    assert armor["ac_breakdown"]["base"] == 11 + 2
    await client.patch(f"/characters/{cid}/items/{armor['item_id']}", json={"is_equipped": False})
    assert (await _full(client, cid))["ac_breakdown"]["base"] == 15
    shield = await _equip(client, cid, slot="off_hand", **SHIELD)
    assert shield["ac_breakdown"]["base"] == 10 + 2 and shield["unarmored_formula"] is None
    plain = await _bard24(client, 3, LORE, dexterity=14, charisma=16)
    assert (await _full(client, plain))["ac_breakdown"]["base"] == 12


async def test_dancing_gives_advantage_on_performance_only_without_armor_or_shield(client):
    cid = await _bard24(client, 3, DANCE)
    assert DANCING in await _roll_keys(client, cid, "skill", skill="performance")
    assert DANCING not in await _roll_keys(client, cid, "skill", skill="stealth")
    assert DANCING not in await _roll_keys(client, await _bard24(client, 3, LORE), "skill", skill="performance")
    r = await client.post(f"/characters/{cid}/skills/performance/roll", json={"die": 10, "options": [DANCING]})
    assert r.status_code == 200, r.text
    assert r.json()["mode_applied"] == "advantage"
    await _equip(client, cid, **ARMOR)
    assert DANCING not in await _roll_keys(client, cid, "skill", skill="performance")


async def test_unarmed_strikes_use_dexterity_for_the_attack_and_strength_for_the_damage(client):
    cid = await _bard24(client, 3, DANCE, strength=8, dexterity=16)
    body = await _unarmed(client, cid)
    assert body["to_hit_bonus"] == 3 + 2 and body["damage_dice"] == "1" and body["damage_bonus"] == -1
    lore = await _bard24(client, 3, LORE, strength=8, dexterity=16)
    assert (await _unarmed(client, lore))["to_hit_bonus"] == -1 + 2
    await _equip(client, cid, **ARMOR)
    assert (await _unarmed(client, cid))["to_hit_bonus"] == -1 + 2  # con l'armatura il privilegio non vale


async def test_bardic_damage_replaces_the_unarmed_damage_with_the_inspiration_die_and_dexterity(client):
    cid = await _bard24(client, 5, DANCE, strength=8, dexterity=16, charisma=16)
    assert BARDIC_DAMAGE in await _roll_keys(client, cid, "attack")
    body = await _unarmed(client, cid, BARDIC_DAMAGE)
    assert body["damage_dice"] == "1d8" and body["damage_bonus"] == 3 and len(body["damage_rolls"]) == 1  # d8 al 5°
    assert 1 <= body["damage_rolls"][0] <= 8 and body["damage_type"] == "bludgeoning"
    bi = await _ability(client, cid, BI)
    assert bi["uses"] == bi["max_uses"]  # il tiro del danno non consuma il dado


async def test_bardic_damage_is_only_for_unarmed_strikes_without_armor_or_shield(client):
    cid = await _bard24(client, 5, DANCE, dexterity=16)
    sword = (await _equip(client, cid, slot="main_hand", **SWORD))["item_id"]
    assert BARDIC_DAMAGE not in await _roll_keys(client, cid, "attack", item_id=sword)
    await client.patch(f"/characters/{cid}/items/{sword}", json={"is_equipped": False})
    assert BARDIC_DAMAGE in await _roll_keys(client, cid, "attack")
    await _equip(client, cid, **ARMOR)
    assert BARDIC_DAMAGE not in await _roll_keys(client, cid, "attack")
    assert BARDIC_DAMAGE not in await _roll_keys(client, await _bard24(client, 5, LORE), "attack")


async def test_agile_strikes_gives_an_unarmed_strike_for_each_use_spent_without_using_the_attack_action(client):
    cid = await _bard24(client, 3, DANCE, dexterity=16, charisma=16)
    assert AGILE not in await _roll_keys(client, cid, "attack")
    assert (await _use(client, cid, BI)).status_code == 200
    assert AGILE in await _roll_keys(client, cid, "attack")
    await _unarmed(client, cid, AGILE)
    turn = await _turn(client, cid)
    assert (turn["attacks_made"], turn["action_attacks"]) == (1, 0)
    assert AGILE not in await _roll_keys(client, cid, "attack")  # un uso, un colpo
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10, "options": [AGILE]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"


async def test_agile_strikes_needs_no_armor_and_comes_back_only_with_a_new_use(client):
    cid = await _bard24(client, 3, DANCE, dexterity=16, charisma=16)
    await _equip(client, cid, **ARMOR)
    await _use(client, cid, BI)
    assert AGILE not in await _roll_keys(client, cid, "attack")
    await client.post(f"/characters/{cid}/turn/new")
    assert AGILE not in await _roll_keys(client, cid, "attack")  # il segno vale per il turno


# ---------------------------------------------------------------------------
# Movimento Ispiratore
# ---------------------------------------------------------------------------

async def test_inspiring_movement_spends_a_use_and_the_reaction_and_tells_what_to_move(client):
    cid = await _bard24(client, 6, DANCE, charisma=16)
    r = await _use(client, cid, "bard.inspiring_movement")
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, BI))["uses"] == (await _ability(client, cid, BI))["max_uses"] - 1
    turn = await _turn(client, cid)
    assert turn["reaction_used"] is True and turn["bonus_used"] is False
    assert "metà" in r.json()["message"]["it"] and "half" in r.json()["message"]["en"]
    again = await _use(client, cid, "bard.inspiring_movement")
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"
    assert AGILE in await _roll_keys(client, cid, "attack")  # anche questo è un uso speso: Colpi Agili


async def test_inspiring_movement_without_inspiration_uses_keeps_the_reaction(client):
    cid = await _bard24(client, 6, DANCE, charisma=10)
    await _set_uses(client, cid, BI, 0)
    r = await _use(client, cid, "bard.inspiring_movement")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    assert (await _turn(client, cid))["reaction_used"] is False


# ---------------------------------------------------------------------------
# Passo a Due
# ---------------------------------------------------------------------------

async def test_tandem_footwork_adds_the_inspiration_die_to_the_initiative_and_spends_a_use(client):
    cid = await _bard24(client, 6, DANCE, dexterity=10, charisma=16)
    assert "bard.tandem_footwork" in await _roll_keys(client, cid, "initiative")
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 10, "options": ["bard.tandem_footwork"]})
    assert r.status_code == 200, r.text
    result = r.json()["option_result"]
    assert len(result["extra_rolls"]) == 1 and 1 <= result["extra_total"] <= 8  # d8 al 6°
    assert r.json()["total"] == 10 + r.json()["bonus"] + result["extra_total"]
    assert "9 m" in result["effects"][0]["it"] and "30 ft" in result["effects"][0]["en"]
    assert (await _ability(client, cid, BI))["uses"] == (await _ability(client, cid, BI))["max_uses"] - 1
    assert (await _turn(client, cid))["bonus_used"] is False  # non costa un'azione


async def test_tandem_footwork_is_not_offered_when_incapacitated_without_uses_or_to_other_colleges(client):
    cid = await _bard24(client, 6, DANCE, charisma=16)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"stunned": True}})
    assert "bard.tandem_footwork" not in await _roll_keys(client, cid, "initiative")
    free = await _bard24(client, 6, DANCE, charisma=16)
    await _set_uses(client, free, BI, 0)
    assert "bard.tandem_footwork" not in await _roll_keys(client, free, "initiative")
    assert "bard.tandem_footwork" not in await _roll_keys(client, await _bard24(client, 6, LORE), "initiative")


# ---------------------------------------------------------------------------
# Evasione Guida
# ---------------------------------------------------------------------------

async def test_leading_evasion_takes_no_damage_on_a_success_and_half_on_a_failure(client):
    cid = await _bard24(client, 14, DANCE)
    await _full_hp(client, cid)
    assert EVASION in await _roll_keys(client, cid, "save", ability="dexterity")
    assert EVASION not in await _roll_keys(client, cid, "save", ability="wisdom")
    body = await _save(client, cid, "dexterity", EVASION)
    assert "1,5 m" in body["option_result"]["effects"][0]["it"] and "5 ft" in body["option_result"]["effects"][0]["en"]
    keys = await _roll_keys(client, cid, "damage_taken")
    assert EVASION_OK in keys and EVASION_KO in keys
    assert (await _hurt(client, cid, 20, EVASION_OK)).json()["current_hit_points"] == 60
    assert EVASION_OK not in await _roll_keys(client, cid, "damage_taken")
    await _save(client, cid, "dexterity", EVASION)
    assert (await _hurt(client, cid, 20, EVASION_KO)).json()["current_hit_points"] == 50


async def test_leading_evasion_does_not_work_while_incapacitated_and_needs_the_confirmed_save(client):
    cid = await _bard24(client, 14, DANCE)
    await _full_hp(client, cid)
    r = await _hurt(client, cid, 20, EVASION_OK)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"stunned": True}})
    assert EVASION not in await _roll_keys(client, cid, "save", ability="dexterity")


async def test_the_evasion_state_can_be_undone_with_the_damage(client):
    cid = await _bard24(client, 14, DANCE)
    await _full_hp(client, cid)
    await _save(client, cid, "dexterity", EVASION)
    assert any(s["key"] == "evasion" for s in await _states(client, cid))
    hurt = await _hurt(client, cid, 20, EVASION_OK)
    assert not any(s["key"] == "evasion" for s in await _states(client, cid))
    r = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": hurt.json()["hp_undo_id"]})
    assert r.status_code == 200, r.text
    assert any(s["key"] == "evasion" for s in await _states(client, cid))  # refund_spent rimette lo stato com'era
    assert (await _full(client, cid))["current_hit_points"] == 60


async def test_the_option_list_tells_the_client_that_agile_strikes_is_outside_the_attack_action(client):
    cid = await _bard24(client, 3, DANCE, dexterity=16, charisma=16)
    await _use(client, cid, BI)
    options = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack"})).json()
    by_key = {o["key"]: o for o in options}
    assert by_key[AGILE]["outside_action"] is True and "outside_action" not in by_key[BARDIC_DAMAGE]
