"""Paladino 2024 (Task 37, parte B): i quattro giuramenti, i loro incantesimi e le opzioni di Incanalare Divinità.
Valori dalla scheda ``docs/superpowers/rules/2024/classes/paladin.md``."""
from __future__ import annotations

import pytest

from core.rules.catalog import features_for
from core.rules.catalog.granted_spells import GRANTED_SPELLS
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _spells, _states, _use
from tests.integration.rules.test_2014_paladin import _hp, _hurt, _new_turn, _rest, _turn
from tests.integration.rules.test_2014_fighter_styles import _item
from tests.integration.rules.test_2014_paladin_combat import _damage, _deferred
from tests.integration.rules.test_2024_paladin import _conditions, _paladin24, _table24

CD, FREE, SMITE = "paladin.channel_divinity", "paladin.divine_smite_free", "paladin.divine_smite"
NAMES = {"devotion": "Giuramento di Devozione", "glory": "Giuramento della Gloria", "ancients": "Giuramento degli Antichi",
         "vengeance": "Giuramento di Vendetta"}
SHEET_SPELLS = {
    "devotion": (("protection-from-evil-and-good", "shield-of-faith"), ("aid", "zone-of-truth"), ("beacon-of-hope", "dispel-magic"),
                 ("freedom-of-movement", "guardian-of-faith"), ("commune", "flame-strike")),
    "glory": (("guiding-bolt", "heroism"), ("enhance-ability", "magic-weapon"), ("haste", "protection-from-energy"),
              ("compulsion", "freedom-of-movement"), ("legend-lore", "yolandes-regal-presence")),
    "ancients": (("ensnaring-strike", "speak-with-animals"), ("misty-step", "moonbeam"), ("plant-growth", "protection-from-energy"),
                 ("ice-storm", "stoneskin"), ("commune-with-nature", "tree-stride")),
    "vengeance": (("bane", "hunters-mark"), ("hold-person", "misty-step"), ("haste", "protection-from-energy"),
                  ("banishment", "dimension-door"), ("hold-monster", "scrying")),
}


async def _oath(client, level, oath, **scores) -> int:
    cid = await _paladin24(client, level, **scores)
    klass = (await _full(client, cid))["classes"][0]["id"]
    r = await client.patch(f"/characters/{cid}/classes/{klass}", json={"subclass": NAMES[oath]})
    assert r.status_code == 200, r.text
    return cid


async def _sword(client, cid, name="Spada", **kw) -> int:
    return await _item(client, cid, name, damage_dice="1d8", weapon_type="melee", properties=[], **kw)


async def _state(client, cid, key) -> dict | None:
    return next((s for s in await _states(client, cid) if s["key"] == key), None)


async def _slots(client, cid) -> dict[int, int]:
    return {s["level"]: s["available"] for s in (await _full(client, cid))["spell_slots"]}


# ---------------------------------------------------------------------------
# Incantesimi di giuramento
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("oath", sorted(SHEET_SPELLS))
@pytest.mark.parametrize("level,tiers", [(3, 1), (4, 1), (5, 2), (9, 3), (13, 4), (17, 5), (20, 5)])
async def test_oath_spells_follow_the_level(client, oath, level, tiers):
    cid = await _oath(client, level, oath)
    expected = {name for tier in SHEET_SPELLS[oath][:tiers] for name in tier}
    got = {s["srd_index"] for s in (await _spells(client, cid)).values() if s.get("always_prepared") and s["srd_index"] not in ("divine-smite", "find-steed")}
    assert got == expected


def test_every_oath_spell_has_data_the_app_can_use():
    for key in (k for tiers in SHEET_SPELLS.values() for tier in tiers for k in tier):
        spell = GRANTED_SPELLS[key]
        assert spell.name["it"] and spell.name["en"] and spell.casting_time and spell.components, key


def test_every_oath_has_its_spell_row_and_the_rows_of_the_sheet():
    keys = {(f.subclass, f.key.split(".")[1]) for f in features_for("2024", "paladin") if f.subclass}
    assert {o for o, k in keys if k == f"{o}_spells"} == set(NAMES)
    assert {k for o, k in keys if o == "devotion"} >= {"sacred_weapon", "aura_of_devotion", "smite_of_protection", "holy_nimbus"}
    assert {k for o, k in keys if o == "glory"} >= {"inspiring_smite", "peerless_athlete", "aura_of_alacrity", "glorious_defense", "living_legend"}
    assert {k for o, k in keys if o == "ancients"} >= {"natures_wrath", "aura_of_warding", "undying_sentinel", "elder_champion"}
    assert {k for o, k in keys if o == "vengeance"} >= {"vow_of_enmity", "relentless_avenger", "soul_of_vengeance", "avenging_angel"}


# ---------------------------------------------------------------------------
# Devozione
# ---------------------------------------------------------------------------

SW, HN = "paladin.sacred_weapon", "paladin.holy_nimbus"


async def test_sacred_weapon_needs_a_wielded_weapon_and_spends_nothing_without_one(client):
    cid = await _oath(client, 3, "devotion", charisma=16)
    r = await _use(client, cid, SW)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "feature_unavailable"
    assert (await _ability(client, cid, CD))["uses"] == 2


async def test_sacred_weapon_binds_the_weapon_for_ten_minutes_with_no_action_and_adds_charisma_to_it_only(client):
    cid = await _oath(client, 3, "devotion", charisma=16)
    sword = await _sword(client, cid, equip="main_hand")
    dagger = await _sword(client, cid, "Pugnale", equip="off_hand")
    plain = {w: (await client.post(f"/characters/{cid}/items/{w}/attack", json={"die": 10, "confirm_extra_attack": True})).json()["to_hit_bonus"]
             for w in (sword, dagger)}
    r = await _use(client, cid, SW, params={"weapon": str(sword)})
    assert r.status_code == 200, r.text
    state = r.json()["state"]
    assert state["rounds_left"] == 100 and state["data"]["weapon_id"] == sword and state["data"]["attack_bonus"] == 3
    assert (await _ability(client, cid, CD))["uses"] == 1
    turn = await _turn(client, cid)
    assert turn["action_used"] is False and turn["bonus_used"] is False  # parte dell'azione Attacco
    after = {w: (await client.post(f"/characters/{cid}/items/{w}/attack", json={"die": 10, "confirm_extra_attack": True})).json()["to_hit_bonus"]
             for w in (sword, dagger)}
    assert after == {sword: plain[sword] + 3, dagger: plain[dagger]}


async def test_sacred_weapon_ends_when_the_weapon_is_no_longer_wielded(client):
    cid = await _oath(client, 3, "devotion", charisma=16)
    sword = await _sword(client, cid, equip="main_hand")
    await _use(client, cid, SW, params={"weapon": str(sword)})
    plain = (await client.post(f"/characters/{cid}/items/{sword}/attack", json={"die": 10, "confirm_extra_attack": True})).json()["to_hit_bonus"]
    assert (await client.patch(f"/characters/{cid}/items/{sword}", json={"is_equipped": False})).status_code == 200
    unequipped = (await client.post(f"/characters/{cid}/items/{sword}/attack", json={"die": 10, "confirm_extra_attack": True})).json()["to_hit_bonus"]
    assert unequipped == plain - 3


@pytest.mark.parametrize("level,immune", [(6, False), (7, True)])
async def test_aura_of_devotion_makes_the_paladin_immune_to_charmed_from_level_7(client, level, immune):
    cid = await _oath(client, level, "devotion")
    assert ((await _conditions(client, cid, charmed=True)).get("charmed") is True) is not immune


async def test_aura_of_devotion_stops_while_incapacitated(client):
    cid = await _oath(client, 7, "devotion")
    await _conditions(client, cid, stunned=True)
    assert (await _conditions(client, cid, charmed=True)).get("charmed") is True


async def test_smite_of_protection_gives_half_cover_to_the_paladin_until_the_next_turn(client):
    cid = await _oath(client, 15, "devotion")
    wid = await _sword(client, cid)
    base = (await _full(client, cid))["ac"]
    key = "paladin.smite_of_protection_free"
    dex_bonus = (await client.post(f"/characters/{cid}/saving_throws/dexterity/roll", json={"die": 10})).json()["bonus"]
    assert key in [o["key"] for o in await _listed(client, cid, wid)]
    r = await _damage(client, cid, await _deferred(client, cid, wid), [FREE, key])
    assert r.status_code == 200, r.text
    assert (await _state(client, cid, "smite_of_protection")) is not None
    assert (await _full(client, cid))["ac"] == base + 2
    assert (await client.post(f"/characters/{cid}/saving_throws/dexterity/roll", json={"die": 10})).json()["bonus"] == dex_bonus + 2
    await _new_turn(client, cid)
    assert (await _full(client, cid))["ac"] == base and await _state(client, cid, "smite_of_protection") is None


async def test_smite_of_protection_is_not_there_before_level_15_or_without_the_smite(client):
    cid = await _oath(client, 14, "devotion")
    assert "paladin.smite_of_protection_free" not in [o["key"] for o in await _listed(client, cid, await _sword(client, cid))]
    top = await _oath(client, 15, "devotion")
    wid = await _sword(client, top)
    r = await _damage(client, top, await _deferred(client, top, wid), ["paladin.smite_of_protection_free"])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"


async def _listed(client, cid, wid) -> list[dict]:
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": wid})
    assert r.status_code == 200, r.text
    return r.json()


async def test_holy_nimbus_is_a_bonus_action_for_ten_minutes_with_charisma_plus_proficiency_damage(client):
    cid = await _oath(client, 20, "devotion", charisma=16)
    row = await _ability(client, cid, HN)
    assert (row["max_uses"], row["restoration_type"], row["action_type"]) == (1, "long_rest", "bonus_action")
    r = await _use(client, cid, HN)
    assert r.status_code == 200, r.text
    state = r.json()["state"]
    assert state["rounds_left"] == 100 and state["data"]["damage"] == 3 + 6 and state["data"]["others"] == [HN]
    turn = await _turn(client, cid)
    assert turn["bonus_used"] is True and (await _ability(client, cid, HN))["uses"] == 0
    assert "paladin.holy_nimbus_save" in await _roll_keys(client, cid, "save", ability="wisdom")
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, HN))["uses"] == 1 and "paladin.holy_nimbus_save" not in await _roll_keys(client, cid, "save", ability="wisdom")


async def test_holy_nimbus_comes_back_with_a_level_5_slot_and_refuses_a_lower_one(client):
    cid = await _oath(client, 20, "devotion", charisma=16)
    assert (await _use(client, cid, HN)).status_code == 200
    await _new_turn(client, cid)
    before = await _slots(client, cid)
    low = await _use(client, cid, HN, params={"restore": True, "slot_level": "4"})
    assert low.status_code in (409, 422) and await _slots(client, cid) == before
    r = await _use(client, cid, HN, params={"restore": True, "slot_level": "5"})
    assert r.status_code == 200, r.text
    assert (await _slots(client, cid))[5] == before[5] - 1 and (await _ability(client, cid, HN))["uses"] == 0
    assert (await _state(client, cid, "holy_nimbus"))["rounds_left"] == 100


async def test_holy_nimbus_without_uses_or_a_restoring_slot_is_refused(client):
    cid = await _oath(client, 20, "devotion", charisma=16)
    assert (await _use(client, cid, HN)).status_code == 200
    await _new_turn(client, cid)
    assert (await _use(client, cid, HN)).status_code == 409


# ---------------------------------------------------------------------------
# Gloria
# ---------------------------------------------------------------------------

IS, PA, AA, GD, LL = ("paladin.inspiring_smite", "paladin.peerless_athlete", "paladin.aura_of_alacrity", "paladin.glorious_defense",
                      "paladin.living_legend")


async def test_inspiring_smite_needs_a_divine_smite_this_turn(client):
    cid = await _oath(client, 3, "glory", charisma=16)
    r = await _use(client, cid, IS, params={"keep": "all"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "feature_unavailable"
    assert (await _ability(client, cid, CD))["uses"] == 2


@pytest.mark.parametrize("keep,others", [("all", 0), ("half", 1), ("none", 1)])
async def test_inspiring_smite_rolls_2d8_plus_level_and_gives_the_chosen_share_to_the_paladin(client, keep, others):
    cid = await _oath(client, 5, "glory", charisma=16)
    wid = await _sword(client, cid)
    assert (await _damage(client, cid, await _deferred(client, cid, wid), [FREE])).status_code == 200
    r = await _use(client, cid, IS, params={"keep": keep})
    assert r.status_code == 200, r.text
    body = r.json()
    total = sum(body["rolls"]) + 5
    mine = {"all": total, "half": total // 2, "none": 0}[keep]
    assert len(body["rolls"]) == 2 and 7 <= total <= 21
    assert (body["given"] or 0) == total - mine  # agli altri va solo ciò che il paladino non tiene
    assert (await _full(client, cid))["temp_hp"] == mine
    assert (await _ability(client, cid, CD))["uses"] == 1


async def test_inspiring_smite_is_once_per_smite(client):
    cid = await _oath(client, 5, "glory", charisma=16)
    wid = await _sword(client, cid)
    assert (await _damage(client, cid, await _deferred(client, cid, wid), [FREE])).status_code == 200
    assert (await _use(client, cid, IS, params={"keep": "all"})).status_code == 200
    again = await _use(client, cid, IS, params={"keep": "all"})
    assert again.status_code == 409 and (await _ability(client, cid, CD))["uses"] == 1


async def test_inspiring_smite_keeps_the_higher_temporary_hit_points(client):
    cid = await _oath(client, 5, "glory", charisma=16)
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "set_temp", "value": 50})).status_code == 200
    wid = await _sword(client, cid)
    await _damage(client, cid, await _deferred(client, cid, wid), [FREE])
    assert (await _use(client, cid, IS, params={"keep": "all"})).status_code == 200
    assert (await _full(client, cid))["temp_hp"] == 50


async def test_peerless_athlete_gives_advantage_on_athletics_and_acrobatics_for_an_hour_and_longer_jumps(client):
    cid = await _oath(client, 3, "glory", charisma=16)
    r = await _use(client, cid, PA)
    assert r.status_code == 200, r.text
    assert r.json()["state"]["rounds_left"] == 600 and (await _turn(client, cid))["bonus_used"] is True
    assert (await _ability(client, cid, CD))["uses"] == 1
    for skill, mode in (("athletics", "advantage"), ("acrobatics", "advantage"), ("stealth", "normal")):
        body = (await client.post(f"/characters/{cid}/skills/{skill}/roll", json={"dice": [5, 12]} if mode == "advantage" else {"die": 5})).json()
        assert body["mode_applied"] == mode, skill
    assert (await _full(client, cid))["computed"]["long_jump_bonus_ft"] == 10
    other = await _oath(client, 3, "glory")
    assert (await client.post(f"/characters/{other}/skills/athletics/roll", json={"die": 5})).json()["mode_applied"] == "normal"


async def test_aura_of_alacrity_adds_3_m_of_speed_from_level_7(client):
    low, high = await _oath(client, 6, "glory"), await _oath(client, 7, "glory")
    assert (await _full(client, high))["computed"]["speed"] == (await _full(client, low))["computed"]["speed"] + 10
    assert (await _state(client, high, "aura_of_alacrity")) is not None  # il bonus agli alleati arriva a GM e gruppo


async def test_glorious_defense_has_charisma_uses_spends_the_reaction_and_shows_the_bonus(client):
    cid = await _oath(client, 15, "glory", charisma=16)
    row = await _ability(client, cid, GD)
    assert (row["max_uses"], row["restoration_type"], row["action_type"]) == (3, "long_rest", "reaction")
    assert GD not in await _keys_of(client, await _oath(client, 14, "glory"))
    r = await _use(client, cid, GD)
    assert r.status_code == 200, r.text
    assert "+3" in r.json()["message"]["it"] and (await _turn(client, cid))["reaction_used"] is True
    assert (await _ability(client, cid, GD))["uses"] == 2


async def test_living_legend_gives_advantage_on_charisma_checks_and_a_save_reroll_and_a_hit_for_a_miss(client):
    cid = await _oath(client, 20, "glory", charisma=16)
    assert "paladin.living_legend_save" not in await _roll_keys(client, cid, "save", ability="wisdom")
    r = await _use(client, cid, LL)
    assert r.status_code == 200, r.text
    assert r.json()["state"]["rounds_left"] == 100 and (await _turn(client, cid))["bonus_used"] is True
    persuasion = (await client.post(f"/characters/{cid}/skills/persuasion/roll", json={"dice": [5, 12]})).json()
    athletics = (await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 5})).json()
    cha = (await client.post(f"/characters/{cid}/ability_checks/charisma/roll", json={"dice": [5, 12]})).json()
    assert (persuasion["mode_applied"], athletics["mode_applied"], cha["mode_applied"]) == ("advantage", "normal", "advantage")
    assert "paladin.living_legend_save" in await _roll_keys(client, cid, "save", ability="wisdom")
    wid = await _sword(client, cid)
    assert "paladin.living_legend_hit" in [o["key"] for o in await _listed(client, cid, wid)]


async def test_living_legend_comes_back_with_a_level_5_slot(client):
    cid = await _oath(client, 20, "glory", charisma=16)
    assert (await _use(client, cid, LL)).status_code == 200
    await _new_turn(client, cid)
    assert (await _use(client, cid, LL)).status_code == 409
    before = await _slots(client, cid)
    assert (await _use(client, cid, LL, params={"restore": True, "slot_level": "5"})).status_code == 200
    assert (await _slots(client, cid))[5] == before[5] - 1


# ---------------------------------------------------------------------------
# Antichi
# ---------------------------------------------------------------------------

NW, AW, US, EC = "paladin.natures_wrath", "paladin.aura_of_warding", "paladin.undying_sentinel", "paladin.elder_champion"


async def test_natures_wrath_restrains_with_a_strength_save_repeated_each_turn_and_spends_the_pool_and_the_action(client):
    cid = await _oath(client, 5, "ancients", charisma=16)
    row = await _ability(client, cid, NW)
    assert row["action_type"] == "action"
    r = await _use(client, cid, NW)
    assert r.status_code == 200, r.text
    assert r.json()["state"]["data"]["save"] == "strength" and r.json()["state"]["rounds_left"] == 10
    effect = (await client.get(f"/characters/{cid}/target-effects/{NW}")).json()["result"]
    assert (effect["condition"], effect["save_ability"], effect["save_dc"], effect["repeat_save"]) == ("restrained", "strength", 14, "end")
    assert (await _turn(client, cid))["action_used"] is True and (await _ability(client, cid, CD))["uses"] == 1
    assert "paladin.turn_the_faithless" not in await _keys_of(client, cid)


@pytest.mark.parametrize("damage,resisted", [("necrotic", True), ("psychic", True), ("radiant", True), ("fire", False)])
async def test_aura_of_warding_gives_the_paladin_resistance_to_necrotic_psychic_and_radiant(client, damage, resisted):
    cid = await _oath(client, 7, "ancients")
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": damage})
    assert r.status_code == 200, r.text
    start = (await _full(client, cid))["hit_points"]
    assert start - (await _hp(client, cid)) == (5 if resisted else 10)


async def test_aura_of_warding_is_not_there_before_level_7_and_stops_while_incapacitated(client):
    low = await _oath(client, 6, "ancients")
    await client.patch(f"/characters/{low}/hp", json={"op": "damage", "value": 10, "damage_type": "necrotic"})
    assert (await _full(low and client, low))["hit_points"] - await _hp(client, low) == 10
    cid = await _oath(client, 7, "ancients")
    await _conditions(client, cid, stunned=True)
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "necrotic"})
    assert (await _full(client, cid))["hit_points"] - await _hp(client, cid) == 10


async def test_an_ally_is_offered_the_warding_for_those_three_types_only(client, test_session_factory):
    _, paladin, hero = await _table24(client, test_session_factory, level=7)
    as_user(GM_ID)
    klass = (await _full(client, paladin))["classes"][0]["id"]
    assert (await client.patch(f"/characters/{paladin}/classes/{klass}", json={"subclass": NAMES["ancients"]})).status_code == 200
    as_user(PLAYER_ID)
    key = "aura:warding_2024"
    assert key in await _roll_keys(client, hero, "damage_taken", damage_type="necrotic")
    assert key not in await _roll_keys(client, hero, "damage_taken", damage_type="fire")
    assert "aura:warding" not in await _roll_keys(client, hero, "damage_taken", damage_type="necrotic")


async def test_undying_sentinel_holds_at_one_and_heals_three_times_the_level(client, test_session_factory):
    cid = await _oath(client, 15, "ancients")
    row = await _ability(client, cid, US)
    assert (row["max_uses"], row["restoration_type"]) == (1, "long_rest")
    assert US not in await _keys_of(client, await _oath(client, 14, "ancients"))
    await _hurt(test_session_factory, cid, 5)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 9, "options": [US]})
    assert r.status_code == 200, r.text
    assert await _hp(client, cid) == 1 + 45 and (await _ability(client, cid, US))["uses"] == 0


async def test_undying_sentinel_is_not_spent_when_the_damage_does_not_reach_zero(client, test_session_factory):
    cid = await _oath(client, 15, "ancients")
    await _hurt(test_session_factory, cid, 50)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 3, "options": [US]})
    assert r.status_code == 200, r.text
    assert await _hp(client, cid) == 47 and (await _ability(client, cid, US))["uses"] == 1


async def test_elder_champion_is_a_bonus_action_for_a_minute_that_heals_ten_at_the_start_of_each_turn(client, test_session_factory):
    cid = await _oath(client, 20, "ancients", charisma=16)
    row = await _ability(client, cid, EC)
    assert (row["max_uses"], row["restoration_type"], row["action_type"]) == (1, "long_rest", "bonus_action")
    maximum = (await _full(client, cid))["hit_points"]
    await _hurt(test_session_factory, cid, maximum - 30)
    r = await _use(client, cid, EC)
    assert r.status_code == 200, r.text
    assert r.json()["state"]["rounds_left"] == 10 and (await _turn(client, cid))["bonus_used"] is True
    await _new_turn(client, cid)
    assert await _hp(client, cid) == maximum - 20


async def test_elder_champion_casts_one_action_spells_as_a_bonus_action(client):
    cid = await _oath(client, 20, "ancients", charisma=16)
    spell = next(s for s in (await _spells(client, cid)).values() if s["srd_index"] == "ice-storm")
    assert (await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"slot_level": 4})).status_code == 200
    assert (await _turn(client, cid))["bonus_spell_cast"] is False  # senza lo stato è un incantesimo da azione
    await _new_turn(client, cid)
    assert (await _use(client, cid, EC)).status_code == 200
    await _new_turn(client, cid)
    assert (await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"slot_level": 4})).status_code == 200
    turn = await _turn(client, cid)
    assert turn["bonus_spell_cast"] is True


# ---------------------------------------------------------------------------
# Vendetta
# ---------------------------------------------------------------------------

VOW, AV = "paladin.vow_of_enmity", "paladin.avenging_angel"


async def test_vow_of_enmity_is_part_of_the_attack_action_for_a_minute_and_gives_advantage(client):
    cid = await _oath(client, 3, "vengeance")
    sword = await _sword(client, cid)
    assert "paladin.vow_of_enmity_attack" not in [o["key"] for o in await _listed(client, cid, sword)]
    r = await _use(client, cid, VOW)
    assert r.status_code == 200, r.text
    turn = await _turn(client, cid)
    assert turn["bonus_used"] is False and turn["action_used"] is False
    assert r.json()["state"]["rounds_left"] == 10 and (await _ability(client, cid, CD))["uses"] == 1
    assert "paladin.vow_of_enmity_attack" in [o["key"] for o in await _listed(client, cid, sword)]


async def test_using_the_vow_again_replaces_it(client):
    cid = await _oath(client, 3, "vengeance")
    await _use(client, cid, VOW)
    assert (await _use(client, cid, VOW)).status_code == 200
    assert len([s for s in await _states(client, cid) if s["key"] == "vow_of_enmity"]) == 1 and (await _ability(client, cid, CD))["uses"] == 0


async def test_relentless_avenger_is_an_opportunity_attack_that_stops_the_target_and_moves_the_paladin(client):
    cid = await _oath(client, 7, "vengeance")
    sword = await _sword(client, cid)
    assert "paladin.opportunity_attack" in [o["key"] for o in await _listed(client, cid, sword)]
    low = await _oath(client, 6, "vengeance")
    assert "paladin.opportunity_attack" not in [o["key"] for o in await _listed(client, low, await _sword(client, low))]
    hit = await _deferred(client, cid, sword, options=["paladin.opportunity_attack"])
    assert (await _turn(client, cid))["reaction_used"] is True
    r = await _damage(client, cid, hit, ["paladin.relentless_avenger"])
    assert r.status_code == 200, r.text
    effect = r.json()["option_result"]["effects"][0]["it"]
    assert "Velocità a 0" in effect and "metà" in effect


async def test_soul_of_vengeance_is_a_reaction_attack_while_the_vow_is_on(client):
    cid = await _oath(client, 15, "vengeance")
    sword = await _sword(client, cid)
    assert "paladin.soul_of_vengeance" not in [o["key"] for o in await _listed(client, cid, sword)]
    await _use(client, cid, VOW)
    assert "paladin.soul_of_vengeance" in [o["key"] for o in await _listed(client, cid, sword)]
    low = await _oath(client, 14, "vengeance")
    await _use(client, low, VOW)
    assert "paladin.soul_of_vengeance" not in [o["key"] for o in await _listed(client, low, await _sword(client, low))]


async def test_avenging_angel_is_a_bonus_action_for_ten_minutes_with_flight_and_a_frightening_aura(client):
    cid = await _oath(client, 20, "vengeance", charisma=16)
    assert (await _full(client, cid))["computed"]["fly_speed"] is None
    row = await _ability(client, cid, AV)
    assert (row["max_uses"], row["restoration_type"], row["action_type"]) == (1, "long_rest", "bonus_action")
    r = await _use(client, cid, AV)
    assert r.status_code == 200, r.text
    state = r.json()["state"]
    assert state["rounds_left"] == 100 and state["data"]["save"] == "wisdom" and state["data"]["dc"] == 17
    assert (await _full(client, cid))["computed"]["fly_speed"] == 60 and (await _turn(client, cid))["bonus_used"] is True
    effect = (await client.get(f"/characters/{cid}/target-effects/{AV}")).json()["result"]
    assert (effect["condition"], effect["save_ability"], effect["save_dc"]) == ("frightened", "wisdom", 17)
    await _rest(client, cid, "long")
    assert (await _full(client, cid))["computed"]["fly_speed"] is None and (await _ability(client, cid, AV))["uses"] == 1


async def test_avenging_angel_comes_back_with_a_level_5_slot(client):
    cid = await _oath(client, 20, "vengeance", charisma=16)
    assert (await _use(client, cid, AV)).status_code == 200
    await _new_turn(client, cid)
    before = await _slots(client, cid)
    assert (await _use(client, cid, AV, params={"restore": True, "slot_level": "5"})).status_code == 200
    assert (await _slots(client, cid))[5] == before[5] - 1


# ---------------------------------------------------------------------------
# Riserva condivisa e cambio di giuramento
# ---------------------------------------------------------------------------

async def test_the_oath_options_spend_the_same_channel_divinity_pool_as_the_base_ones(client):
    cid = await _oath(client, 3, "ancients")
    assert (await _use(client, cid, NW)).status_code == 200
    assert (await _use(client, cid, "paladin.divine_sense")).status_code == 200
    assert (await _use(client, cid, "paladin.divine_sense")).status_code == 409


async def test_changing_the_oath_swaps_the_oath_rows(client):
    cid = await _oath(client, 7, "devotion")
    assert SW in await _keys_of(client, cid)
    klass = (await _full(client, cid))["classes"][0]["id"]
    assert (await client.patch(f"/characters/{cid}/classes/{klass}", json={"subclass": NAMES["vengeance"]})).status_code == 200
    keys = await _keys_of(client, cid)
    assert SW not in keys and VOW in keys and "paladin.relentless_avenger" in keys


async def test_avenging_angel_note_is_the_2024_one_start_of_turn_only(client):
    cid = await _oath(client, 20, "vengeance", charisma=16)
    assert (await _use(client, cid, AV)).status_code == 200
    effect = (await client.get(f"/characters/{cid}/target-effects/{AV}")).json()["result"]
    assert effect["note"] == "avenging_angel_2024"


async def test_sacred_weapon_is_for_melee_weapons_only(client):
    cid = await _oath(client, 3, "devotion", charisma=16)
    bow = await _item(client, cid, "Arco", damage_dice="1d8", weapon_type="ranged", properties=["ammunition"], equip="main_hand")
    r = await _use(client, cid, SW, params={"weapon": str(bow)})
    assert r.status_code == 409 and (await _ability(client, cid, CD))["uses"] == 2


async def test_sacred_weapon_saves_the_damage_type_and_the_hit_shows_radiant(client):
    cid = await _oath(client, 3, "devotion", charisma=16)
    sword = await _sword(client, cid, equip="main_hand")
    r = await _use(client, cid, SW, params={"weapon": str(sword), "damage_type": "radiant"})
    assert r.status_code == 200, r.text
    assert r.json()["state"]["data"]["damage_type"] == "radiant"
    body = (await client.post(f"/characters/{cid}/items/{sword}/attack", json={"die": 10, "confirm_extra_attack": True})).json()
    assert any("radios" in e["it"].lower() for e in body["option_result"]["effects"])
    other = await _oath(client, 3, "devotion", charisma=16)
    sword2 = await _sword(client, other, equip="main_hand")
    assert (await _use(client, other, SW, params={"weapon": str(sword2)})).json()["state"]["data"]["damage_type"] == "normal"
    body = (await client.post(f"/characters/{other}/items/{sword2}/attack", json={"die": 10, "confirm_extra_attack": True})).json()
    assert not any("radios" in e["it"].lower() for e in (body.get("option_result") or {}).get("effects", []))
