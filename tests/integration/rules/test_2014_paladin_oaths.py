"""Paladino 2014 (Task 25): i tre giuramenti, gli incantesimi di giuramento e le opzioni di Incanalare Divinità."""
from __future__ import annotations

import pytest

from core.db.models import Character
from core.rules.catalog.granted_spells import GRANTED_SPELLS
from core.rules.catalog.y2014.paladin import OATH_SPELLS
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _spells, _states, _use
from tests.integration.rules.test_2014_fighter_styles import _item
from tests.integration.rules.test_2014_paladin import CD, _hp, _hurt, _new_turn, _paladin, _rest, _turn

LEVELS = (3, 5, 9, 13, 17)


async def _effect(client, cid, key) -> dict:
    return (await client.get(f"/characters/{cid}/target-effects/{key}")).json()["result"]


async def _state(client, cid, key) -> dict | None:
    return next((s for s in await _states(client, cid) if s["key"] == key), None)


# ---------------------------------------------------------------------------
# Incantesimi di giuramento
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("oath", sorted(OATH_SPELLS))
@pytest.mark.parametrize("level,tiers", [(3, 1), (4, 1), (5, 2), (8, 2), (9, 3), (13, 4), (17, 5), (20, 5)])
async def test_oath_spells_follow_the_level(client, oath, level, tiers):
    cid = await _paladin(client, level, oath)
    spells = await _spells(client, cid)
    expected = {name for tier in OATH_SPELLS[oath][:tiers] for name in tier}
    got = {s["srd_index"] for s in spells.values() if s.get("always_prepared")}
    assert got == expected
    assert all(s["is_prepared"] and s["class_id"] for s in spells.values() if s["srd_index"] in expected)


@pytest.mark.parametrize("oath,first", [
    ("devotion", {"protection-from-evil-and-good", "sanctuary"}), ("ancients", {"ensnaring-strike", "speak-with-animals"}),
    ("vengeance", {"bane", "hunters-mark"})])
async def test_each_oath_starts_with_its_two_spells_from_the_manual(client, oath, first):
    assert set(OATH_SPELLS[oath][0]) == first


def test_the_oath_spell_lists_are_the_ones_of_the_sheet():
    assert OATH_SPELLS["devotion"] == (
        ("protection-from-evil-and-good", "sanctuary"), ("lesser-restoration", "zone-of-truth"),
        ("dispel-magic", "beacon-of-hope"), ("guardian-of-faith", "freedom-of-movement"), ("flame-strike", "commune"))
    assert OATH_SPELLS["ancients"] == (
        ("ensnaring-strike", "speak-with-animals"), ("moonbeam", "misty-step"), ("plant-growth", "protection-from-energy"),
        ("stoneskin", "ice-storm"), ("commune-with-nature", "tree-stride"))
    assert OATH_SPELLS["vengeance"] == (
        ("bane", "hunters-mark"), ("hold-person", "misty-step"), ("haste", "protection-from-energy"),
        ("banishment", "dimension-door"), ("hold-monster", "scrying"))


def test_every_oath_spell_has_data_the_app_can_use():
    for tiers in OATH_SPELLS.values():
        for key in (k for tier in tiers for k in tier):
            spell = GRANTED_SPELLS[key]
            assert spell.name["it"] and spell.name["en"] and spell.casting_time and spell.components, key


async def test_oath_spells_do_not_count_against_the_prepared_cap(client):
    cid = await _paladin(client, 9, "devotion", charisma=10)
    assert (await _full(client, cid))["spellcasting"]["prepared_count"] == 0


async def test_an_oath_that_changes_keeps_the_spells_as_normal_ones(client):
    cid = await _paladin(client, 5, "devotion")
    klass = (await _full(client, cid))["classes"][0]["id"]
    await client.patch(f"/characters/{cid}/classes/{klass}", json={"subclass": "Giuramento di Vendetta"})
    spells = await _spells(client, cid)
    assert all(not s["always_prepared"] for s in spells.values() if s["srd_index"] in OATH_SPELLS["devotion"][0])
    assert {"bane", "hunters-mark", "hold-person", "misty-step"} <= {s["srd_index"] for s in spells.values() if s["always_prepared"]}


async def test_the_tenets_are_a_text_row_of_the_oath(client):
    from core.rules.catalog import features_for
    rows = {f.key: f for f in features_for("2014", "paladin")}
    for key, oath in (("tenets_of_devotion", "devotion"), ("tenets_of_ancients", "ancients"), ("tenets_of_vengeance", "vengeance")):
        assert rows[f"paladin.{key}"].passive and rows[f"paladin.{key}"].subclass == oath
    assert not {k for k in await _keys_of(client, await _paladin(client, 3, "devotion")) if "tenets" in k} - {"paladin.tenets_of_devotion"}


# ---------------------------------------------------------------------------
# Devozione
# ---------------------------------------------------------------------------

SW = "paladin.sacred_weapon"


async def _sword(client, cid, name="Spada", **kw) -> int:
    return await _item(client, cid, name, damage_dice="1d8", weapon_type="melee", properties=[], **kw)


async def _attack(client, cid, wid, **body) -> dict:
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10, "confirm_extra_attack": True, **body})
    assert r.status_code == 200, r.text
    return r.json()


async def test_sacred_weapon_needs_a_wielded_weapon_and_spends_nothing_without_one(client):
    cid = await _paladin(client, 3, "devotion", charisma=16)
    r = await _use(client, cid, SW)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "feature_unavailable"
    assert (await _ability(client, cid, CD))["uses"] == 1 and (await _turn(client, cid))["action_used"] is False


async def test_sacred_weapon_binds_the_chosen_weapon_for_ten_rounds_and_spends_the_pool_and_the_action(client):
    cid = await _paladin(client, 3, "devotion", charisma=16)
    sword = await _sword(client, cid, equip="main_hand")
    row = next(a for a in (await _full(client, cid))["abilities"] if a["feature_key"] == SW)
    assert [o["key"] for o in row["use_choices"][0]["options"]] == [str(sword)]
    assert row["use_choices"][0]["options"][0]["label"]["it"] == "Spada"
    r = await _use(client, cid, SW, params={"weapon": str(sword)})
    assert r.status_code == 200, r.text
    state = r.json()["state"]
    assert state["rounds_left"] == 10 and state["data"]["weapon_id"] == sword and state["data"]["bonus"] == 3
    assert (await _ability(client, cid, CD))["uses"] == 0 and (await _turn(client, cid))["action_used"] is True


async def test_sacred_weapon_adds_charisma_with_a_minimum_of_one_to_the_chosen_weapon_only(client):
    cid = await _paladin(client, 3, "devotion", charisma=16)
    sword = await _sword(client, cid, equip="main_hand")
    dagger = await _item(client, cid, "Pugnale", damage_dice="1d4", weapon_type="melee", properties=["light"], equip="off_hand")
    plain = {w: (await _attack(client, cid, w))["to_hit_bonus"] for w in (sword, dagger)}
    assert (await _use(client, cid, SW, params={"weapon": str(sword)})).status_code == 200
    after = {w: await _attack(client, cid, w) for w in (sword, dagger)}
    assert after[sword]["to_hit_bonus"] == plain[sword] + 3 and f"feature:{SW}" in after[sword]["notes"]
    assert after[dagger]["to_hit_bonus"] == plain[dagger]


async def test_sacred_weapon_bonus_is_at_least_one_and_the_weapon_must_be_wielded(client):
    cid = await _paladin(client, 3, "devotion", charisma=8)
    sword = await _sword(client, cid, equip="main_hand")
    plain = (await _attack(client, cid, sword))["to_hit_bonus"]
    await _use(client, cid, SW, params={"weapon": str(sword)})
    assert (await _attack(client, cid, sword))["to_hit_bonus"] == plain + 1
    await client.patch(f"/characters/{cid}/items/{sword}", json={"is_equipped": False})
    assert (await _attack(client, cid, sword))["to_hit_bonus"] == plain  # non più impugnata: il bonus si ferma


async def test_sacred_weapon_refuses_a_weapon_that_is_not_wielded(client):
    cid = await _paladin(client, 3, "devotion")
    await _sword(client, cid, equip="main_hand")
    stray = await _sword(client, cid, "Altra")
    r = await _use(client, cid, SW, params={"weapon": str(stray)})
    assert r.status_code == 422
    assert (await _ability(client, cid, CD))["uses"] == 1 and (await _turn(client, cid))["action_used"] is False


async def test_sacred_weapon_ends_by_hand_at_zero_hp_and_after_ten_rounds(client, test_session_factory):
    cid = await _paladin(client, 3, "devotion")
    sword = await _sword(client, cid, equip="main_hand")
    await _use(client, cid, SW, params={"weapon": str(sword)})
    assert (await _state(client, cid, "sacred_weapon")) is not None
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": await _hp(client, cid)})
    assert r.status_code == 200 and r.json()["current_hit_points"] == 0
    assert (await _state(client, cid, "sacred_weapon")) is None


async def test_sacred_weapon_is_not_there_for_other_oaths(client):
    for oath in ("ancients", "vengeance", None):
        assert SW not in await _keys_of(client, await _paladin(client, 20, oath))


async def test_turn_the_unholy_spends_the_pool_and_gives_the_spell_dc_to_apply_to_the_gm_targets(client):
    cid = await _paladin(client, 5, "devotion", charisma=16)  # competenza +3, Carisma +3
    r = await _use(client, cid, "paladin.turn_the_unholy")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["targets"] == ["paladin.turn_the_unholy"]
    assert body["state"]["data"]["dc"] == 14 and body["state"]["data"]["save"] == "wisdom" and body["state"]["rounds_left"] == 10
    fx = await _effect(client, cid, "paladin.turn_the_unholy")
    assert (fx["condition"], fx["save_ability"], fx["save_dc"], fx["rounds"]) == ("custom:turned", "wisdom", 14, 10)
    assert (await _ability(client, cid, CD))["uses"] == 0 and (await _turn(client, cid))["action_used"] is True


async def test_turn_the_unholy_without_a_use_is_refused_before_spending_the_action(client):
    cid = await _paladin(client, 3, "devotion")
    assert (await _use(client, cid, "paladin.turn_the_unholy")).status_code == 200
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "action", "used": False})
    r = await _use(client, cid, "paladin.turn_the_unholy")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    assert (await _turn(client, cid))["action_used"] is False


async def test_the_two_channel_divinity_options_of_one_oath_share_the_single_use(client):
    cid = await _paladin(client, 3, "devotion")
    sword = await _sword(client, cid, equip="main_hand")
    assert (await _use(client, cid, "paladin.turn_the_unholy")).status_code == 200
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "action", "used": False})
    r = await _use(client, cid, SW, params={"weapon": str(sword)})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"


async def test_aura_of_devotion_makes_the_paladin_immune_to_charmed_from_level_7_when_conscious(client, test_session_factory):
    for level, charmed in ((6, True), (7, None)):
        cid = await _paladin(client, level, "devotion")
        r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"charmed": True}})
        assert r.json()["conditions"].get("charmed") == charmed
    cid = await _paladin(client, 7, "devotion")
    await _hurt(test_session_factory, cid, 0)
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"charmed": True}})
    assert r.json()["conditions"].get("charmed") is True
    other = await _paladin(client, 7, "ancients")
    r = await client.patch(f"/characters/{other}/conditions", json={"conditions": {"charmed": True}})
    assert r.json()["conditions"].get("charmed") is True


async def test_purity_of_spirit_offers_advantage_and_immunity_on_saves_against_those_creatures(client):
    cid = await _paladin(client, 15, "devotion")
    keys = await _roll_keys(client, cid, "save", ability="wisdom")
    assert {"paladin.purity_of_spirit", "paladin.purity_of_spirit_immune"} <= set(keys)
    assert not {"paladin.purity_of_spirit", "paladin.purity_of_spirit_immune"} & set(
        await _roll_keys(client, await _paladin(client, 14, "devotion"), "save", ability="wisdom"))
    assert not {"paladin.purity_of_spirit"} & set(await _roll_keys(client, await _paladin(client, 15, "ancients"), "save", ability="wisdom"))


async def test_purity_of_spirit_is_visible_to_the_group_as_a_permanent_state(client):
    cid = await _paladin(client, 15, "devotion")
    state = await _state(client, cid, "purity_of_spirit")
    assert state is not None and state["rounds_left"] is None and state["data"]["others"] == ["paladin.purity_of_spirit"]
    assert await _state(client, await _paladin(client, 14, "devotion"), "purity_of_spirit") is None


HN = "paladin.holy_nimbus"


async def test_holy_nimbus_is_an_action_with_one_use_for_a_long_rest_and_lasts_ten_rounds(client):
    cid = await _paladin(client, 20, "devotion")
    row = await _ability(client, cid, HN)
    assert (row["max_uses"], row["restoration_type"], row["action_type"]) == (1, "long_rest", "action")
    r = await _use(client, cid, HN)
    assert r.status_code == 200, r.text
    state = r.json()["state"]
    assert state["rounds_left"] == 10 and state["data"]["others"] == [HN] and state["data"]["damage"] == 10
    assert (await _ability(client, cid, HN))["uses"] == 0 and (await _turn(client, cid))["action_used"] is True
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "action", "used": False})
    assert (await _use(client, cid, HN)).status_code == 409
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, HN))["uses"] == 0
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, HN))["uses"] == 1


async def test_holy_nimbus_gives_advantage_on_saves_against_fiend_and_undead_spells_only_while_active(client):
    cid = await _paladin(client, 20, "devotion")
    assert "paladin.holy_nimbus_save" not in await _roll_keys(client, cid, "save", ability="wisdom")
    await _use(client, cid, HN)
    assert "paladin.holy_nimbus_save" in await _roll_keys(client, cid, "save", ability="wisdom")


# ---------------------------------------------------------------------------
# Antichi
# ---------------------------------------------------------------------------

async def test_natures_wrath_restrains_with_a_save_repeated_at_the_end_of_each_turn(client):
    cid = await _paladin(client, 5, "ancients", charisma=16)
    r = await _use(client, cid, "paladin.natures_wrath")
    assert r.status_code == 200, r.text
    assert r.json()["targets"] == ["paladin.natures_wrath"]
    fx = await _effect(client, cid, "paladin.natures_wrath")
    assert fx["condition"] == "restrained" and fx["save_dc"] == 14 and fx["save_ability"] in ("strength", "dexterity")
    assert fx["repeat_save"] == "end"
    assert (await _ability(client, cid, CD))["uses"] == 0 and (await _turn(client, cid))["action_used"] is True


async def test_turn_the_faithless_turns_fey_and_fiends_not_undead(client):
    cid = await _paladin(client, 5, "ancients", charisma=16)
    r = await _use(client, cid, "paladin.turn_the_faithless")
    assert r.status_code == 200, r.text
    fx = await _effect(client, cid, "paladin.turn_the_faithless")
    assert (fx["condition"], fx["save_ability"], fx["save_dc"]) == ("custom:turned", "wisdom", 14)
    from core.rules.catalog import features_for
    row = next(f for f in features_for("2014", "paladin") if f.key == "paladin.turn_the_faithless")
    assert "folletti" in row.summary["it"] and "non morti" in row.summary["it"]


async def test_aura_of_warding_halves_spell_damage_as_a_confirmation_for_the_paladin(client):
    cid = await _paladin(client, 7, "ancients")
    assert "paladin.aura_of_warding" in await _roll_keys(client, cid, "damage_taken")
    assert "paladin.aura_of_warding" not in await _roll_keys(client, await _paladin(client, 6, "ancients"), "damage_taken")
    assert "paladin.aura_of_warding" not in await _roll_keys(client, await _paladin(client, 7, "devotion"), "damage_taken")
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 11, "options": ["paladin.aura_of_warding"]})
    assert r.status_code == 200, r.text
    assert r.json()["option_result"]["damage_after"] == 5  # dimezzato per difetto


async def test_aura_of_warding_works_even_at_zero_hp_because_the_manual_does_not_ask_for_consciousness(client, test_session_factory):
    cid = await _paladin(client, 7, "ancients")
    await _hurt(test_session_factory, cid, 0)
    assert "paladin.aura_of_warding" in await _roll_keys(client, cid, "damage_taken")


US = "paladin.undying_sentinel"


async def test_undying_sentinel_is_a_single_use_for_a_long_rest(client):
    row = await _ability(client, await _paladin(client, 15, "ancients"), US)
    assert (row["max_uses"], row["restoration_type"]) == (1, "long_rest")
    assert US not in await _keys_of(client, await _paladin(client, 14, "ancients"))


async def test_undying_sentinel_keeps_the_paladin_at_one_hp_after_dropping_to_zero(client, test_session_factory):
    cid = await _paladin(client, 15, "ancients")
    hp = await _hp(client, cid)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": hp})
    assert r.status_code == 200 and r.json()["current_hit_points"] == 0
    use = await _use(client, cid, US)
    assert use.status_code == 200, use.text
    full = await _full(client, cid)
    assert full["current_hit_points"] == 1 and not full["conditions"].get("unconscious")
    assert full["death_saves"]["failures"] == 0 and (await _ability(client, cid, US))["uses"] == 0
    assert (await _use(client, cid, US)).status_code in (409, 404)


async def test_undying_sentinel_cannot_be_used_while_the_paladin_still_stands(client):
    cid = await _paladin(client, 15, "ancients")
    r = await _use(client, cid, US)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "feature_unavailable"
    assert (await _ability(client, cid, US))["uses"] == 1


async def test_undying_sentinel_does_not_save_the_paladin_from_an_instant_death(client):
    cid = await _paladin(client, 15, "ancients")
    hp = await _hp(client, cid)
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": hp * 3})
    assert (await _full(client, cid))["is_dead"] is True
    r = await _use(client, cid, US)
    assert r.status_code == 409


EC = "paladin.elder_champion"


async def test_elder_champion_lasts_ten_rounds_and_heals_ten_at_the_start_of_each_turn(client, test_session_factory):
    cid = await _paladin(client, 20, "ancients")
    row = await _ability(client, cid, EC)
    assert (row["max_uses"], row["restoration_type"], row["action_type"]) == (1, "long_rest", "action")
    maximum = (await _full(client, cid))["hit_points"]
    await _hurt(test_session_factory, cid, maximum - 30)
    r = await _use(client, cid, EC)
    assert r.status_code == 200, r.text
    assert r.json()["state"]["rounds_left"] == 10 and r.json()["state"]["data"]["others"] == [EC]
    await _new_turn(client, cid)
    assert await _hp(client, cid) == maximum - 20
    await _new_turn(client, cid)
    assert await _hp(client, cid) == maximum - 10
    await _new_turn(client, cid)
    await _new_turn(client, cid)
    assert await _hp(client, cid) == maximum  # mai oltre il massimo


async def test_elder_champion_does_not_heal_without_the_state_and_not_at_zero_hp(client, test_session_factory):
    cid = await _paladin(client, 20, "ancients")
    await _hurt(test_session_factory, cid, 5)
    await _new_turn(client, cid)
    assert await _hp(client, cid) == 5
    await _use(client, cid, EC)
    await _hurt(test_session_factory, cid, 0)
    await _new_turn(client, cid)
    assert await _hp(client, cid) == 0


# ---------------------------------------------------------------------------
# Vendetta
# ---------------------------------------------------------------------------

async def test_abjure_enemy_frightens_with_the_spell_dc_and_spends_the_pool(client):
    cid = await _paladin(client, 5, "vengeance", charisma=16)
    r = await _use(client, cid, "paladin.abjure_enemy")
    assert r.status_code == 200, r.text
    fx = await _effect(client, cid, "paladin.abjure_enemy")
    assert (fx["condition"], fx["save_ability"], fx["save_dc"], fx["rounds"]) == ("frightened", "wisdom", 14, 10)
    assert r.json()["state"]["data"]["others"] == ["paladin.abjure_enemy"]
    assert (await _ability(client, cid, CD))["uses"] == 0 and (await _turn(client, cid))["action_used"] is True


VOW = "paladin.vow_of_enmity"


async def test_vow_of_enmity_is_a_bonus_action_for_ten_rounds_and_spends_the_pool(client):
    cid = await _paladin(client, 3, "vengeance")
    r = await _use(client, cid, VOW)
    assert r.status_code == 200, r.text
    turn = await _turn(client, cid)
    assert turn["bonus_used"] is True and turn["action_used"] is False
    assert r.json()["state"]["rounds_left"] == 10 and (await _ability(client, cid, CD))["uses"] == 0


async def test_vow_of_enmity_offers_advantage_on_attacks_until_it_ends(client):
    cid = await _paladin(client, 3, "vengeance")
    sword = await _sword(client, cid)
    assert "paladin.vow_of_enmity_attack" not in await _roll_keys(client, cid, "attack", item_id=sword)
    await _use(client, cid, VOW)
    assert "paladin.vow_of_enmity_attack" in await _roll_keys(client, cid, "attack", item_id=sword)
    body = await _attack(client, cid, sword, options=["paladin.vow_of_enmity_attack"])
    assert body["mode"] == "advantage"


async def test_relentless_avenger_is_an_opportunity_attack_that_ends_with_half_the_speed(client):
    cid = await _paladin(client, 7, "vengeance")
    sword = await _sword(client, cid)
    keys = await _roll_keys(client, cid, "attack", item_id=sword)
    assert "paladin.opportunity_attack" in keys
    low = await _paladin(client, 6, "vengeance")
    assert "paladin.opportunity_attack" not in await _roll_keys(client, low, "attack", item_id=await _sword(client, low))
    hit = await client.post(f"/characters/{cid}/items/{sword}/attack",
                            json={"die": 10, "defer_damage": True, "options": ["paladin.opportunity_attack"]})
    assert hit.status_code == 200, hit.text
    assert (await _turn(client, cid))["reaction_used"] is True and (await _turn(client, cid))["action_attacks"] == 0
    r = await client.post(f"/characters/{cid}/attack/{hit.json()['attack_id']}/damage", json={"options": ["paladin.relentless_avenger"]})
    assert r.status_code == 200, r.text
    effect = r.json()["option_result"]["effects"][0]["it"]
    assert "4,5 m" in effect  # metà dei 30 piedi (9 m) della velocità salvata


async def test_soul_of_vengeance_is_a_reaction_attack_while_the_vow_is_on(client):
    cid = await _paladin(client, 15, "vengeance")
    sword = await _sword(client, cid)
    assert "paladin.soul_of_vengeance" not in await _roll_keys(client, cid, "attack", item_id=sword)
    await _use(client, cid, VOW)
    assert "paladin.soul_of_vengeance" in await _roll_keys(client, cid, "attack", item_id=sword)
    low = await _paladin(client, 14, "vengeance")
    assert "paladin.soul_of_vengeance" not in await _roll_keys(client, low, "attack", item_id=await _sword(client, low))
    body = await _attack(client, cid, sword, options=["paladin.soul_of_vengeance"])
    assert (await _turn(client, cid))["reaction_used"] is True and body["to_hit_total"]


AA = "paladin.avenging_angel"


async def test_avenging_angel_lasts_an_hour_and_gives_a_flying_speed_of_sixty_feet(client):
    cid = await _paladin(client, 20, "vengeance")
    assert (await _full(client, cid))["computed"]["fly_speed"] is None
    row = await _ability(client, cid, AA)
    assert (row["max_uses"], row["restoration_type"], row["action_type"]) == (1, "long_rest", "action")
    r = await _use(client, cid, AA)
    assert r.status_code == 200, r.text
    assert r.json()["state"]["rounds_left"] == 600 and r.json()["state"]["data"]["others"] == [AA]
    assert (await _full(client, cid))["computed"]["fly_speed"] == 60
    assert (await _turn(client, cid))["action_used"] is True and (await _ability(client, cid, AA))["uses"] == 0
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, AA))["uses"] == 1 and (await _full(client, cid))["computed"]["fly_speed"] is None


async def test_avenging_angel_flying_speed_never_lowers_a_higher_one(client):
    cid = await _paladin(client, 20, "vengeance")
    await _use(client, cid, AA)
    walk = (await _full(client, cid))["computed"]["speed"]
    assert (await _full(client, cid))["computed"]["fly_speed"] == 60 and walk <= 60


async def test_the_vengeance_reactions_are_not_proposed_after_taking_damage(client):
    cid = await _paladin(client, 15, "vengeance")
    await _sword(client, cid, equip="main_hand")
    await _use(client, cid, VOW)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 3})
    assert r.status_code == 200, r.text
    offered = [o["key"] for o in r.json().get("reactions") or []]
    assert not {"paladin.opportunity_attack", "paladin.soul_of_vengeance"} & set(offered)
