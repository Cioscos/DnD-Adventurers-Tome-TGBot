"""Bardo 2024, Collegi della Sapienza e del Valore (Task 32)."""
from __future__ import annotations

import pytest

from tests.integration._encounter_helpers import PLAYER_ID, as_user
from tests.integration.rules.test_2014_bard import (
    BI, _ability, _add_spell, _choice, _full, _keys_of, _resolve, _roll_keys, _skills, _spells, _use,
)
from tests.integration.rules.test_2014_bard_inspiration import _give, _states_of
from tests.integration.rules.test_2014_fighter_eldritch_knight import _cast, _spell
from tests.integration.rules.test_2024_bard import LORE, VALOR, _bard24, _set_uses, _table, _turn

CUTTING = "bard.cutting_words"
PEERLESS = "bard.peerless_skill"
BATTLE_MAGIC = "bard.battle_magic"
CANTRIP_ATTACK = "bard.extra_attack_cantrip"


# ---------------------------------------------------------------------------
# Collegio della Sapienza
# ---------------------------------------------------------------------------

async def test_the_lore_college_brings_its_rows_at_the_right_level(client):
    assert {CUTTING, "bard.lore_bonus_proficiencies"} <= await _keys_of(client, await _bard24(client, 3, LORE))
    assert "bard.magical_discoveries" not in await _keys_of(client, await _bard24(client, 5, LORE))
    assert "bard.magical_discoveries" in await _keys_of(client, await _bard24(client, 6, LORE))
    assert PEERLESS not in await _keys_of(client, await _bard24(client, 13, LORE))
    assert PEERLESS in await _keys_of(client, await _bard24(client, 14, LORE))
    assert not {CUTTING, PEERLESS} & await _keys_of(client, await _bard24(client, 14, VALOR))


async def test_lore_bonus_proficiencies_pick_three_skills_and_come_before_expertise(client):
    cid = await _bard24(client, 3, LORE)
    await _skills(client, cid, acrobatics=True)
    pending = [c for c in (await _full(client, cid))["pending_choices"] if c["kind"] == "class_option"]
    assert [c["group"] for c in pending][:2] == ["lore_skills", "expertise"]
    choice = _choice(await _full(client, cid), "lore_skills")
    assert choice["count"] == 3 and "acrobatics" not in {o["key"] for o in choice["options"]}
    assert (await _resolve(client, cid, "lore_skills", ["acrobatics", "arcana", "history"])).status_code == 422
    r = await _resolve(client, cid, "lore_skills", ["arcana", "history", "insight"])
    assert r.status_code == 200, r.text
    assert all(r.json()["skills"][s] is True for s in ("arcana", "history", "insight"))


@pytest.mark.parametrize("level,die", [(3, 6), (5, 8), (10, 10), (15, 12)])
async def test_cutting_words_rolls_the_die_and_spends_a_use_and_the_reaction(client, level, die):
    cid = await _bard24(client, level, LORE, charisma=16)
    r = await _use(client, cid, CUTTING)
    assert r.status_code == 200, r.text
    [roll] = r.json()["rolls"]
    assert 1 <= roll <= die and "sottrai" in r.json()["message"]["it"].lower()
    bi = await _ability(client, cid, BI)
    assert bi["uses"] == bi["max_uses"] - 1
    turn = await _turn(client, cid)
    assert turn["reaction_used"] is True and turn["bonus_used"] is False
    again = await _use(client, cid, CUTTING)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"


async def test_cutting_words_without_inspiration_uses_keeps_the_reaction(client):
    cid = await _bard24(client, 3, LORE, charisma=10)
    await _set_uses(client, cid, BI, 0)
    r = await _use(client, cid, CUTTING)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    assert (await _turn(client, cid))["reaction_used"] is False


async def test_magical_discoveries_are_two_spells_of_other_lists_always_prepared_outside_the_limits(client):
    cid = await _bard24(client, 6, LORE)
    choice = _choice(await _full(client, cid), "magical_discoveries")
    assert choice["count"] == 2 and choice["spell_pick"]["max_level"] == 3 and choice["spell_pick"]["free"] is True
    too_high = await _add_spell(client, cid, "Volare", 5, pick_id=choice["id"])
    assert too_high.status_code == 422 and too_high.json()["detail"]["code"] == "spell_pick_level"
    one = await _add_spell(client, cid, "Palla di fuoco", 3, pick_id=choice["id"])
    assert one.status_code == 201, one.text
    two = await _add_spell(client, cid, "Luce", 0, pick_id=_choice(await _full(client, cid), "magical_discoveries")["id"])
    assert two.status_code == 201, two.text  # un trucchetto è ammesso
    full = await _full(client, cid)
    assert _choice(full, "magical_discoveries") is None
    names = await _spells(client, cid)
    fireball = names["Palla di fuoco"]
    assert fireball["always_prepared"] and fireball["is_prepared"] and fireball["class_id"] == full["classes"][0]["id"]
    limits = full["spellcasting"]["limits"][0]
    assert (limits["prepared_count"], limits["cantrips_count"]) == (0, 0)  # fuori dal limite e dai trucchetti


async def test_a_magical_discovery_can_be_replaced_by_removing_it(client):
    cid = await _bard24(client, 6, LORE)
    choice = _choice(await _full(client, cid), "magical_discoveries")
    spell = (await _add_spell(client, cid, "Palla di fuoco", 3, pick_id=choice["id"])).json()
    await _add_spell(client, cid, "Luce", 0, pick_id=_choice(await _full(client, cid), "magical_discoveries")["id"])
    assert (await client.delete(f"/characters/{cid}/spells/{spell['id']}")).status_code == 204
    again = _choice(await _full(client, cid), "magical_discoveries")
    assert again is not None and again["count"] == 1  # la scelta torna da fare


async def test_peerless_skill_adds_the_die_after_a_check_or_an_attack_and_is_only_paid_if_it_works(client):
    cid = await _bard24(client, 14, LORE, charisma=16)
    for roll, query in (("skill", {"skill": "athletics"}), ("ability", {"ability": "strength"}), ("attack", {}), ("initiative", {})):
        keys = await _roll_keys(client, cid, roll, **query)
        assert PEERLESS in keys, roll
    assert PEERLESS not in await _roll_keys(client, cid, "save", ability="wisdom")  # il testo non cita i TS
    options = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "skill", "skill": "athletics"})).json()
    peerless = next(o for o in options if o["key"] == PEERLESS)
    assert peerless["phase"] == "after_roll" and peerless["pay_if_success"] is True
    first = (await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 5})).json()
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [PEERLESS]})
    assert r.status_code == 200, r.text
    extra = r.json()["option_result"]
    assert len(extra["extra_rolls"]) == 1 and 1 <= extra["extra_total"] <= 10  # d10 al 14°
    assert r.json()["total"] == first["total"] + extra["extra_total"]
    bi = await _ability(client, cid, BI)
    assert bi["uses"] == bi["max_uses"] - 1
    assert r.json()["option_result"]["spent"] == [f"feature:{BI}:1"]  # il dado speso, rimborsabile sotto
    refund = await client.post(f"/characters/{cid}/last-roll/refund")  # il tiro è fallito comunque
    assert refund.status_code == 200, refund.text
    bi = await _ability(client, cid, BI)
    assert bi["uses"] == bi["max_uses"]


async def test_peerless_skill_is_kept_when_the_roll_succeeds(client):
    cid = await _bard24(client, 14, LORE, charisma=16)
    await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 5})
    await client.post(f"/characters/{cid}/last-roll/options", json={"options": [PEERLESS]})
    assert (await client.post(f"/characters/{cid}/last-roll/refund", json={"succeeded": True})).status_code == 200
    bi = await _ability(client, cid, BI)
    assert bi["uses"] == bi["max_uses"] - 1


# ---------------------------------------------------------------------------
# Collegio del Valore
# ---------------------------------------------------------------------------

async def test_the_valor_college_brings_its_rows_at_the_right_level(client):
    assert {"bard.combat_inspiration", "bard.martial_training"} <= await _keys_of(client, await _bard24(client, 3, VALOR))
    assert "bard.extra_attack" not in await _keys_of(client, await _bard24(client, 5, VALOR))
    assert "bard.extra_attack" in await _keys_of(client, await _bard24(client, 6, VALOR))
    assert BATTLE_MAGIC not in await _keys_of(client, await _bard24(client, 13, VALOR))
    assert BATTLE_MAGIC in await _keys_of(client, await _bard24(client, 14, VALOR))
    assert not {"bard.martial_training", BATTLE_MAGIC} & await _keys_of(client, await _bard24(client, 14, LORE))


async def test_martial_training_grants_martial_weapons_medium_armor_and_shields(client):
    valor, lore = await _bard24(client, 3, VALOR), await _bard24(client, 3, LORE)
    got = (await _full(client, valor))["general_proficiencies"]
    assert {"Armature medie", "Scudi"} <= set(got["armor"]) and "Armi da guerra" in got["weapons"]
    plain = (await _full(client, lore))["general_proficiencies"]
    assert "Armature medie" not in plain["armor"] and "Armi da guerra" not in plain["weapons"]


async def test_combat_inspiration_comes_with_the_die_of_a_2024_valor_bard(client, test_session_factory):
    sid, bard, hero = await _table(client, test_session_factory, level=3, subclass=VALOR)
    assert (await _give(client, bard, hero)).status_code == 200
    as_user(PLAYER_ID)
    [state] = _states_of(await _full(client, hero), "bardic_die")
    assert state["data"]["combat"] is True and state["rounds_left"] == 600
    assert "bardic_die:damage" in await _roll_keys(client, hero, "attack")
    r = await client.post(f"/characters/{hero}/bardic-die/ac")
    assert r.status_code == 200, r.text
    assert 1 <= r.json()["roll"] <= 6
    assert (await _turn(client, hero))["reaction_used"] is True


async def test_a_lore_die_has_no_combat_use(client, test_session_factory):
    sid, bard, hero = await _table(client, test_session_factory, level=3, subclass=LORE)
    await _give(client, bard, hero)
    as_user(PLAYER_ID)
    assert "bardic_die:damage" not in await _roll_keys(client, hero, "attack")
    assert (await client.post(f"/characters/{hero}/bardic-die/ac")).status_code == 409


async def test_valor_extra_attack_is_two_from_level_6_and_does_not_stack(client):
    five, six, lore = await _bard24(client, 5, VALOR), await _bard24(client, 6, VALOR), await _bard24(client, 6, LORE)
    attacks = {c: (await client.get(f"/characters/{c}/turn-state")).json()["attacks_allowed"] for c in (five, six, lore)}
    assert attacks == {five: 1, six: 2, lore: 1}
    assert (await client.post(f"/characters/{six}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})).status_code == 201
    assert (await client.get(f"/characters/{six}/turn-state")).json()["attacks_allowed"] == 2


async def test_a_cantrip_can_replace_one_of_the_two_attacks(client):
    cid = await _bard24(client, 6, VALOR)
    first = await _spell(client, cid, "Luce", 0)
    second = await _spell(client, cid, "Mano magica", 0)
    third = await _spell(client, cid, "Fiamma", 0)
    leveled = await _spell(client, cid, "Dardo incantato", 1)
    assert CANTRIP_ATTACK in await _roll_keys(client, cid, "cast", spell_id=first)
    assert CANTRIP_ATTACK not in await _roll_keys(client, cid, "cast", spell_id=leveled)
    assert (await _cast(client, cid, first, options=[CANTRIP_ATTACK])).status_code == 200
    assert (await _turn(client, cid))["action_attacks"] == 1
    assert (await _cast(client, cid, second, options=[CANTRIP_ATTACK])).status_code == 200
    assert (await _turn(client, cid))["action_attacks"] == 2
    assert CANTRIP_ATTACK not in await _roll_keys(client, cid, "cast", spell_id=third)  # i due attacchi sono finiti
    refused = await _cast(client, cid, third, options=[CANTRIP_ATTACK])
    assert refused.status_code == 409


async def test_a_cantrip_in_place_of_an_attack_counts_with_the_weapon_attacks(client):
    cid = await _bard24(client, 6, VALOR)
    cantrip = await _spell(client, cid, "Luce", 0)
    sword = (await client.post(f"/characters/{cid}/items", json={"name": "Spada", "item_type": "weapon", "item_metadata": {
        "damage_dice": "1d8", "weapon_type": "melee", "properties": []}})).json()["items"][-1]["id"]
    await client.patch(f"/characters/{cid}/items/{sword}", json={"is_equipped": True, "equipment_slot": "main_hand"})
    assert (await client.post(f"/characters/{cid}/items/{sword}/attack", json={"die": 10})).status_code == 200
    assert CANTRIP_ATTACK in await _roll_keys(client, cid, "cast", spell_id=cantrip)
    assert (await _cast(client, cid, cantrip, options=[CANTRIP_ATTACK])).status_code == 200
    assert (await _turn(client, cid))["action_attacks"] == 2
    assert CANTRIP_ATTACK not in await _roll_keys(client, cid, "cast", spell_id=cantrip)


async def _sword(client, cid) -> int:
    meta = {"damage_dice": "1d8", "weapon_type": "melee", "properties": []}
    r = await client.post(f"/characters/{cid}/items", json={"name": "Spada", "item_type": "weapon", "item_metadata": meta})
    wid = max(i["id"] for i in r.json()["items"] if i["name"] == "Spada")
    r = await client.patch(f"/characters/{cid}/items/{wid}", json={"is_equipped": True, "equipment_slot": "main_hand"})
    assert r.status_code == 200, r.text
    return wid


async def test_battle_magic_after_a_spell_cast_with_the_action_of_any_class(client):
    cid = await _bard24(client, 14, VALOR)
    sword = await _sword(client, cid)
    assert BATTLE_MAGIC not in await _roll_keys(client, cid, "attack", item_id=sword)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 3, "hit_die": 6})
    assert r.status_code == 201, r.text
    wizard = next(c["id"] for c in (await _full(client, cid))["classes"] if c["class_name"] == "wizard")
    foreign = (await _add_spell(client, cid, "Dardo magico", 0, casting_time="1 azione", class_id=wizard)).json()
    assert (await client.post(f"/characters/{cid}/spells/{foreign['id']}/use", json={})).status_code == 200
    assert BATTLE_MAGIC in await _roll_keys(client, cid, "attack", item_id=sword)  # il testo del 2024 non chiede una magia da bardo
    r = await client.post(f"/characters/{cid}/items/{sword}/attack", json={"die": 10, "options": [BATTLE_MAGIC]})
    assert r.status_code == 200, r.text
    turn = await _turn(client, cid)
    assert turn["bonus_used"] is True and turn["attacks_made"] == 1 and turn["action_attacks"] == 0
    assert BATTLE_MAGIC not in await _roll_keys(client, cid, "attack", item_id=sword)


async def test_battle_magic_needs_a_spell_cast_with_the_action_in_this_turn(client):
    cid = await _bard24(client, 14, VALOR)
    sword = await _sword(client, cid)
    bard_class = (await _full(client, cid))["classes"][0]["id"]
    bonus = (await _add_spell(client, cid, "Parola", 0, casting_time="1 azione bonus", class_id=bard_class)).json()
    await client.post(f"/characters/{cid}/spells/{bonus['id']}/use", json={})
    assert BATTLE_MAGIC not in await _roll_keys(client, cid, "attack", item_id=sword)
    action = (await _add_spell(client, cid, "Dardo", 0, casting_time="1 azione", class_id=bard_class)).json()
    await client.post(f"/characters/{cid}/spells/{action['id']}/use", json={})
    assert BATTLE_MAGIC in await _roll_keys(client, cid, "attack", item_id=sword)
    await client.post(f"/characters/{cid}/turn/new")
    assert BATTLE_MAGIC not in await _roll_keys(client, cid, "attack", item_id=sword)
