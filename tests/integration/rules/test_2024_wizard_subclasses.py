"""Mago 2024, parte B (Task 42): Abiuratore, Divinatore, Invocatore e Illusionista. Nessun d20 casuale: i dadi si fissano."""
from __future__ import annotations

import random

import pytest

from core.rules.catalog import features_for
from tests.integration.rules.test_2014_bard import _ability, _full, _roll_keys, _use
from tests.integration.rules.test_2014_fighter_eldritch_knight import _cast, _spell
from tests.integration.rules.test_2014_paladin import _rest
from tests.integration.rules.test_2014_wizard import _choice, _spend, _used, _wizard_id
from tests.integration.rules.test_2014_wizard_abjuration import _abjuration, _cast_at, _damage, _hp, _ward
from tests.integration.rules.test_2014_wizard_illusion_evocation import _illusion, _states, _turn

NAMES = {"abjurer": "Abiuratore", "diviner": "Divinatore", "evoker": "Invocatore", "illusionist": "Illusionista"}
SCHOOL = {"abjurer": "abjuration", "diviner": "divination", "evoker": "evocation", "illusionist": "illusion"}
P = "wizard."
WARD, PROJECTED, BREAKER, BREAKER_CHECK, BREAKER_REFUND = P + "arcane_ward", P + "projected_ward", P + "spell_breaker", P + "spell_breaker_check", P + "spell_breaker_refund"
PORTENT, THIRD_EYE, EXPERT = P + "portent", P + "third_eye", P + "expert_divination"
SCULPT, EMPOWERED, OVERCHANNEL = P + "sculpt_spells", P + "empowered_evocation", P + "overchannel"
SELF, REALITY = P + "illusory_self", P + "illusory_reality"
BEAST, FEY = P + "phantasmal_beast", P + "phantasmal_fey"

ROWS = {
    "abjurer": {3: ["abjuration_savant", "arcane_ward"], 6: ["projected_ward"], 10: ["spell_breaker"], 14: ["spell_resistance"]},
    "diviner": {3: ["divination_savant", "portent"], 6: ["expert_divination"],
                10: ["third_eye", "darkvision", "greater_comprehension", "see_invisibility"], 14: ["greater_portent"]},
    "evoker": {3: ["evocation_savant", "potent_cantrip"], 6: ["sculpt_spells"], 10: ["empowered_evocation"], 14: ["overchannel"]},
    "illusionist": {3: ["illusion_savant", "improved_illusions"], 6: ["phantasmal_beast", "phantasmal_fey"], 10: ["illusory_self"],
                    14: ["illusory_reality"]},
}
FLAT = [(sub, lv, key) for sub, levels in ROWS.items() for lv, keys in levels.items() for key in keys]


async def _make(client, sub, level=10, **scores) -> int:
    body = {"name": "Mago", "initial_class": {"class_name": "wizard", "level": level, "subclass": NAMES[sub]}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    for ability, value in {"intelligence": 16, **scores}.items():
        assert (await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})).status_code == 200
    return cid


async def _by_index(client, cid) -> dict[str, dict]:
    return {s["srd_index"]: s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"]}


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

def test_every_subclass_mapping_title_has_its_row_with_both_languages():
    rows = features_for("2024", "wizard")
    titles = {f.source_title for f in rows}
    mapping = open("docs/superpowers/rules/mapping/2024/wizard.md", encoding="utf-8").read().splitlines()[4:]
    wanted = [l.split("|")[1].strip() for l in mapping if l.startswith("|") and any(
        f"({n} " in l.split("|")[1] for n in NAMES.values())]
    assert len(wanted) == 23 and [t for t in wanted if t not in titles] == []
    assert all(f.summary["it"] and f.summary["en"] and len(f.summary["it"]) <= 200 and len(f.summary["en"]) <= 200 for f in rows)


@pytest.mark.parametrize("sub,level,key", FLAT)
def test_a_subclass_row_appears_at_its_level_and_only_for_its_subclass(sub, level, key):
    spec = {f.key: f for f in features_for("2024", "wizard")}[P + key]
    assert spec.level == level and spec.subclass == sub


@pytest.mark.parametrize("sub", sorted(NAMES))
async def test_the_four_subclasses_are_recognised_and_a_text_outside_the_catalog_is_not(client, sub):
    full = await _full(client, await _make(client, sub, 3))
    assert full["classes"][0]["subclass_key"] == sub
    other = await _full(client, await _wizard_id_free(client))
    assert other["classes"][0]["subclass_key"] is None


async def _wizard_id_free(client) -> int:
    body = {"name": "Mago", "initial_class": {"class_name": "wizard", "level": 3, "subclass": "Scuola di Abiurazione"}}
    cid = (await client.post("/characters", json=body)).json()["id"]
    await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})
    return cid  # il nome della scuola del 2014 non è una sottoclasse 2024


# ---------------------------------------------------------------------------
# I quattro Sapienti: due incantesimi della scuola gratis al libro, poi uno per ogni nuovo livello di slot
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sub", sorted(NAMES))
async def test_the_savant_is_a_free_book_pick_restricted_to_its_school(client, sub):
    cid = await _make(client, sub, 3)
    pick = _choice(await _full(client, cid), f"{SCHOOL[sub]}_savant")
    assert pick["count"] == 2 and pick["spell_pick"]["book"] is True and pick["spell_pick"]["max_level"] == 2
    assert pick["spell_pick"]["school"] == SCHOOL[sub]
    body = {"name": "Prova", "level": 1, "pick_id": pick["id"]}
    wrong = await client.post(f"/characters/{cid}/spells", json={**body, "school": "necromancy"})
    assert wrong.status_code == 422 and wrong.json()["detail"]["code"] == "spell_pick_school"
    none = await client.post(f"/characters/{cid}/spells", json=body)
    assert none.status_code == 422 and none.json()["detail"]["code"] == "spell_pick_school"
    high = await client.post(f"/characters/{cid}/spells", json={**body, "level": 3, "school": SCHOOL[sub]})
    assert high.status_code == 422 and high.json()["detail"]["code"] == "spell_pick_level"
    ok = await client.post(f"/characters/{cid}/spells", json={**body, "school": SCHOOL[sub]})
    assert ok.status_code == 201, ok.text
    assert ok.json()["in_spellbook"] is True and ok.json()["is_prepared"] is False
    assert _choice(await _full(client, cid), f"{SCHOOL[sub]}_savant")["count"] == 1


async def test_the_savant_gives_one_more_pick_at_each_new_slot_level_and_only_to_its_subclass(client):
    for level, total in ((4, 2), (5, 3), (6, 3), (7, 4), (17, 9)):
        pick = _choice(await _full(client, await _make(client, "diviner", level)), "divination_savant")
        assert pick["count"] == total
    assert _choice(await _full(client, await _make(client, "diviner", 5)), "divination_savant")["spell_pick"]["max_level"] == 3
    assert _choice(await _full(client, await _make(client, "diviner", 3)), "abjuration_savant") is None
    assert _choice(await _full(client, await _make(client, "evoker", 5)), "divination_savant") is None


# ---------------------------------------------------------------------------
# Abiuratore
# ---------------------------------------------------------------------------

async def _warded(client, level=6) -> int:
    cid = await _make(client, "abjurer", level)  # 2 x 6 + 3 = 15
    await _hp(client, cid)
    await _cast_at(client, cid, await _abjuration(client, cid))
    return cid


async def test_an_abjuration_with_a_slot_makes_a_ward_of_twice_the_level_plus_intelligence_that_takes_damage_first(client):
    cid = await _warded(client)
    ward = _ward(await _full(client, cid))
    assert ward["data"]["hp"] == ward["data"]["max"] == 15
    after = await _damage(client, cid, 20)
    assert after["current_hit_points"] == 95 and _ward(after)["data"]["hp"] == 0
    other = await _make(client, "evoker", 6)
    await _cast_at(client, other, await _abjuration(client, other))
    assert _ward(await _full(client, other)) is None


async def test_the_ward_can_be_recharged_with_a_bonus_action_spending_a_slot(client):
    cid = await _warded(client)
    await _damage(client, cid, 15)
    r = await _use(client, cid, WARD, params={"slot_level": "2"})
    assert r.status_code == 200, r.text
    assert _ward(await _full(client, cid))["data"]["hp"] == 4  # 2 x livello dello slot
    assert (await _used(client, cid))[2] == 1 and (await _turn(client, cid))["bonus_used"] is True
    again = await _use(client, cid, WARD, params={"slot_level": "3"})
    assert again.status_code == 409  # l'azione bonus è già spesa
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid, WARD, params={"slot_level": "3"})).status_code == 200
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid, WARD, params={"slot_level": "3"})).status_code == 200
    assert _ward(await _full(client, cid))["data"]["hp"] == 15  # mai oltre il massimo


async def test_the_recharge_needs_a_ward_a_free_slot_and_refuses_without_spending(client):
    cid = await _make(client, "abjurer", 6)
    refused = await _use(client, cid, WARD, params={"slot_level": "1"})
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "feature_unavailable"
    cid = await _warded(client)
    bad = await _use(client, cid, WARD, params={"slot_level": "5"})
    assert bad.status_code == 422 and (await _turn(client, cid))["bonus_used"] is False


async def test_projected_ward_is_a_reaction_from_level_6(client):
    low = await _make(client, "abjurer", 5)
    assert PROJECTED not in {a["feature_key"] for a in (await _full(client, low))["abilities"]}
    cid = await _warded(client)
    r = await _use(client, cid, PROJECTED, params={"damage": "10"})
    assert r.status_code == 200, r.text
    assert _ward(await _full(client, cid))["data"]["hp"] == 5 and (await _turn(client, cid))["reaction_used"] is True


async def test_spell_breaker_makes_counterspell_and_dispel_magic_always_prepared(client):
    assert BREAKER not in {a["feature_key"] for a in (await _full(client, await _make(client, "abjurer", 9)))["abilities"]}
    cid = await _make(client, "abjurer", 10)
    spells = await _by_index(client, cid)
    assert spells["counterspell"]["always_prepared"] is True and spells["dispel-magic"]["always_prepared"] is True
    assert spells["counterspell"]["school"] == "abjuration" and spells["dispel-magic"]["level"] == 3
    assert "dispel-magic" not in await _by_index(client, await _make(client, "evoker", 10))


async def test_spell_breaker_casts_dispel_magic_as_a_bonus_action(client):
    cid = await _make(client, "abjurer", 10)
    dispel = (await _by_index(client, cid))["dispel-magic"]["id"]
    assert (await _cast(client, cid, dispel, slot_level=3)).status_code == 200
    assert (await _turn(client, cid))["bonus_spell_cast"] is True
    plain = await _make(client, "evoker", 10)
    own = await _spell(client, plain, "Dissolvi magie", 3, srd_index="dispel-magic", school="abjuration")
    await _cast(client, plain, own, slot_level=3)
    assert (await _turn(client, plain))["bonus_spell_cast"] is False


async def test_spell_breaker_adds_proficiency_to_the_dispel_magic_check_only(client):
    cid = await _make(client, "abjurer", 10)
    spells = await _by_index(client, cid)
    assert BREAKER_CHECK not in await _roll_keys(client, cid, "ability", ability="intelligence")
    await _cast(client, cid, spells["counterspell"]["id"], slot_level=3)
    assert BREAKER_CHECK not in await _roll_keys(client, cid, "ability", ability="intelligence")  # il controincantesimo non ha prove
    await client.post(f"/characters/{cid}/turn/new")
    await _cast(client, cid, spells["dispel-magic"]["id"], slot_level=3)
    assert BREAKER_CHECK in await _roll_keys(client, cid, "ability", ability="intelligence")
    assert BREAKER_CHECK not in await _roll_keys(client, cid, "ability", ability="strength")
    plain = (await client.post(f"/characters/{cid}/ability_checks/intelligence/roll", json={"die": 10})).json()
    boosted = (await client.post(f"/characters/{cid}/ability_checks/intelligence/roll", json={"die": 10, "options": [BREAKER_CHECK]})).json()
    assert boosted["total"] == plain["total"] + 4


async def test_spell_breaker_gives_the_slot_back_after_the_cast_not_before_it(client):
    cid = await _make(client, "abjurer", 10)
    spells = await _by_index(client, cid)
    assert BREAKER_REFUND not in await _roll_keys(client, cid, "cast", spell_id=spells["counterspell"]["id"], casting_level=3)
    assert (await _use(client, cid, BREAKER)).status_code == 409  # nessun lancio con slot in questo turno
    assert (await _cast(client, cid, spells["counterspell"]["id"], slot_level=3)).status_code == 200
    assert (await _used(client, cid))[3] == 1
    assert (await _use(client, cid, BREAKER)).status_code == 200  # l'esito si dichiara dopo il lancio
    assert (await _used(client, cid))[3] == 0
    assert (await _use(client, cid, BREAKER)).status_code == 409  # una sola volta per lancio
    other = await _spell(client, cid, "Scudo", 1, srd_index="shield", school="abjuration")
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _cast(client, cid, other, slot_level=1)).status_code == 200
    assert (await _use(client, cid, BREAKER)).status_code == 409  # solo Controincantesimo e Dissolvi Magie
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _cast(client, cid, spells["dispel-magic"]["id"], slot_level=3)).status_code == 200
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid, BREAKER)).status_code == 409  # il turno è finito


async def test_spell_resistance_is_advantage_on_saves_against_spells_and_resistance_to_their_damage(client):
    low = await _make(client, "abjurer", 13)
    assert P + "spell_resistance" not in await _roll_keys(client, low, "save", ability="dexterity")
    cid = await _make(client, "abjurer", 14)
    assert P + "spell_resistance" in await _roll_keys(client, cid, "save", ability="dexterity")
    await _hp(client, cid)
    halved = await _damage(client, cid, 20, damage_type="fire", options=[P + "spell_resistance_damage"])
    assert halved["current_hit_points"] == 90


# ---------------------------------------------------------------------------
# Divinatore
# ---------------------------------------------------------------------------

def _saved(full: dict) -> list[int]:
    return (full["settings"].get("saved_dice") or {}).get(PORTENT, [])


@pytest.mark.parametrize("level,dice", [(3, 2), (13, 2), (14, 3)])
async def test_a_long_rest_rolls_the_portent_dice_two_and_three_from_level_14(client, monkeypatch, level, dice):
    cid = await _make(client, "diviner", level)
    monkeypatch.setattr(random, "randint", lambda a, b: 13 if b == 20 else a)
    await _rest(client, cid, "long")
    assert _saved(await _full(client, cid)) == [13] * dice


async def test_portent_replaces_a_d20_once_per_turn_and_belongs_to_the_diviner_from_level_3(client, monkeypatch):
    monkeypatch.setattr(random, "randint", lambda a, b: 17 if b == 20 else a)
    for sub, level in (("diviner", 2), ("evoker", 6)):
        cid = await _make(client, sub, level)
        await _rest(client, cid, "long")
        assert _saved(await _full(client, cid)) == []
    cid = await _make(client, "diviner", 3)
    await _rest(client, cid, "long")
    r = await client.post(f"/characters/{cid}/skills/arcana/roll", json={
        "die": 2, "mode": "normal", "options": [PORTENT], "option_inputs": {PORTENT: {"die": 17}}})
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 17 and _saved(await _full(client, cid)) == [17]
    assert PORTENT not in await _roll_keys(client, cid, "skill", skill="arcana")


async def test_expert_divination_returns_a_lower_spent_slot_from_level_6(client):
    cid = await _make(client, "diviner", 6)
    spell = await _spell(client, cid, "Chiaroveggenza", 3, school="divination", casting_time="1 azione")
    await _spend(client, cid, l1=3, l2=2)
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={
        "slot_level": 3, "options": [EXPERT], "option_inputs": {EXPERT: {"slot_level": 2}}})
    assert r.status_code == 200, r.text
    used = await _used(client, cid)
    assert (used[1], used[2], used[3]) == (3, 1, 1)
    low = await _make(client, "diviner", 5)
    lowered = await _spell(client, low, "Chiaroveggenza", 3, school="divination", casting_time="1 azione")
    assert EXPERT not in await _roll_keys(client, low, "cast", spell_id=lowered, casting_level=3)


async def test_the_third_eye_is_a_bonus_action_with_one_use_and_darkvision_is_120_feet(client):
    assert await _ability(client, await _make(client, "diviner", 9), THIRD_EYE) is None
    cid = await _make(client, "diviner", 10)
    row = await _ability(client, cid, THIRD_EYE)
    assert (row["max_uses"], row["restoration_type"]) == (1, "short_rest")
    assert (await _use(client, cid, THIRD_EYE, params={"option": "ethereal_sight"})).status_code == 422
    assert (await _use(client, cid, THIRD_EYE, params={"option": "darkvision"})).status_code == 200
    assert {"type": "darkvision", "range_ft": 120} in (await _full(client, cid))["computed"]["senses"]
    assert (await _turn(client, cid))["bonus_used"] is True
    assert (await _use(client, cid, THIRD_EYE, params={"option": "darkvision"})).status_code == 409
    await _rest(client, cid, "short")
    assert "third_eye" not in await _states(client, cid)
    assert (await _ability(client, cid, THIRD_EYE))["uses"] == 1
    assert not any(s["range_ft"] == 120 for s in (await _full(client, cid))["computed"]["senses"] if s["type"] == "darkvision")


async def test_greater_comprehension_is_a_state_without_a_sense(client):
    cid = await _make(client, "diviner", 10)
    senses = (await _full(client, cid))["computed"]["senses"]
    await _use(client, cid, THIRD_EYE, params={"option": "greater_comprehension"})
    assert (await _states(client, cid))["third_eye"]["data"]["option"] == "greater_comprehension"
    assert (await _full(client, cid))["computed"]["senses"] == senses


async def test_see_invisibility_is_cast_without_slots_only_while_the_third_eye_lasts(client):
    cid = await _make(client, "diviner", 10)
    spell = (await _by_index(client, cid))["see-invisibility"]
    assert spell["in_spellbook"] is False and spell["always_prepared"] is True and spell["school"] == "divination"  # minori 11
    nope = await _cast(client, cid, spell["id"], free_cast=True)
    assert nope.status_code == 409 and nope.json()["detail"]["code"] == "free_cast_unavailable"
    await _use(client, cid, THIRD_EYE, params={"option": "see_invisibility"})
    before = await _used(client, cid)
    for _ in range(2):
        assert (await _cast(client, cid, spell["id"], free_cast=True)).status_code == 200
        await client.post(f"/characters/{cid}/turn/new")
    assert await _used(client, cid) == before
    await _rest(client, cid, "short")
    assert (await _cast(client, cid, spell["id"], free_cast=True)).status_code == 409


# ---------------------------------------------------------------------------
# Invocatore
# ---------------------------------------------------------------------------

async def _evocation(client, cid, name="Palla di fuoco", level=3, save="DEX", **extra) -> int:
    return await _spell(client, cid, name, level, school="evocation", attack_save=save, casting_time="1 azione",
                        damage_dice="8d6", damage_type="fire", **extra)


async def _roll_damage(client, cid, spell, **body):
    r = await client.post(f"/characters/{cid}/spells/{spell}/roll_damage", json=body)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("save", ["ATK", "CON"])
async def test_potent_cantrip_gives_half_damage_on_a_miss_or_a_passed_save(client, save):
    cid = await _make(client, "evoker", 3)
    cantrip = await _spell(client, cid, "Prova", 0, school="evocation", attack_save=save, damage_dice="1d10", damage_type="fire")
    assert (await _roll_damage(client, cid, cantrip, main_rolls=[8]))["save_success_damage"] == 4
    leveled = await _evocation(client, cid, save=save)
    assert (await _roll_damage(client, cid, leveled, casting_level=3)).get("save_success_damage") is None
    other = await _make(client, "abjurer", 3)
    spell = await _spell(client, other, "Prova", 0, school="evocation", attack_save=save, damage_dice="1d10", damage_type="fire")
    assert (await _roll_damage(client, other, spell, main_rolls=[8])).get("save_success_damage") is None


async def test_sculpt_spells_counts_one_plus_the_spell_level_for_any_evocation_that_hits_others(client):
    cid = await _make(client, "evoker", 7)
    ball = await _evocation(client, cid)
    assert SCULPT in await _roll_keys(client, cid, "cast", spell_id=ball, casting_level=3)
    r = await client.post(f"/characters/{cid}/spells/{ball}/use", json={"slot_level": 4, "options": [SCULPT]})
    assert r.status_code == 200 and " 5 " in r.json()["option_result"]["effects"][0]["it"]
    other = await _spell(client, cid, "Sonno", 1, school="enchantment", attack_save="WIS", casting_time="1 azione")
    assert SCULPT not in await _roll_keys(client, cid, "cast", spell_id=other, casting_level=1)
    low = await _make(client, "evoker", 5)
    assert SCULPT not in await _roll_keys(client, low, "cast", spell_id=await _evocation(client, low), casting_level=3)


async def test_empowered_evocation_adds_intelligence_to_an_evocation_damage_roll_only(client):
    cid = await _make(client, "evoker", 10, intelligence=18)
    ball = await _evocation(client, cid)
    other = await _spell(client, cid, "Raggio", 1, school="necromancy", attack_save="CON", damage_dice="8d6", damage_type="necrotic")
    plain = await _roll_damage(client, cid, ball, casting_level=3, main_rolls=[3] * 8, options=[])
    assert plain["total"] == 24 + 4
    assert (await _roll_damage(client, cid, other, casting_level=1, main_rolls=[3] * 8))["total"] == 24
    low = await _make(client, "evoker", 9, intelligence=18)
    assert (await _roll_damage(client, low, await _evocation(client, low), casting_level=3, main_rolls=[3] * 8))["total"] == 24


async def test_overchannel_maximises_the_damage_and_hurts_from_the_second_use(client, monkeypatch):
    cid = await _make(client, "evoker", 14)
    await _hp(client, cid, 200)
    ball = await _evocation(client, cid)
    monkeypatch.setattr(random, "randint", lambda a, b: 1)
    r = await client.post(f"/characters/{cid}/spells/{ball}/roll_damage", json={"casting_level": 3, "options": [OVERCHANNEL]})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["current_hit_points"] == 200 and (await _states(client, cid))["overchannel"]["data"]["uses"] == 1
    await client.post(f"/characters/{cid}/spells/{ball}/roll_damage", json={"casting_level": 3, "options": [OVERCHANNEL]})
    assert (await _full(client, cid))["current_hit_points"] == 200 - 6  # 2d12 x 3 livelli con ogni dado a 1: 6
    low = await _make(client, "evoker", 13)
    assert OVERCHANNEL not in await _roll_keys(client, low, "spell_damage", spell_id=await _evocation(client, low))


# ---------------------------------------------------------------------------
# Illusionista
# ---------------------------------------------------------------------------

async def test_improved_illusions_gives_a_free_cantrip_and_stretches_range_and_drops_verbal(client):
    cid = await _make(client, "illusionist", 3)
    pick = _choice(await _full(client, cid), "improved_illusions")
    assert pick["count"] == 1 and pick["spell_pick"]["free"] is True and pick["spell_pick"]["max_level"] == 0
    assert _choice(await _full(client, await _make(client, "evoker", 3)), "improved_illusions") is None
    far = await _spell(client, cid, "Immagine maggiore", 3, school="illusion", range_area="36 m", components="V, S, M")
    near = await _spell(client, cid, "Prova vicina", 1, school="illusion", range_area="1,5 m", components="V, S")
    self_ = await _spell(client, cid, "Prova personale", 1, school="illusion", range_area="Personale", components="V")
    fire = await _spell(client, cid, "Fuoco", 1, school="evocation", range_area="36 m", components="V, S")
    shown = {s["id"]: s for s in (await client.get(f"/characters/{cid}/spells")).json()}
    assert (shown[far]["range_area"], shown[far]["components"]) == ("54 m", "S, M")
    assert (shown[near]["range_area"], shown[near]["components"]) == ("1,5 m", "S")
    assert (shown[self_]["range_area"], shown[self_]["components"]) == ("Personale", "")
    assert (shown[fire]["range_area"], shown[fire]["components"]) == ("36 m", "V, S")
    feet = await _spell(client, cid, "Prova piedi", 1, school="illusion", range_area="120 ft", components="S")
    assert {s["id"]: s for s in (await client.get(f"/characters/{cid}/spells")).json()}[feet]["range_area"] == "180 ft"


async def test_phantasmal_creatures_are_always_prepared_and_each_casts_once_without_a_slot(client):
    assert BEAST not in {a["feature_key"] for a in (await _full(client, await _make(client, "illusionist", 5)))["abilities"]}
    cid = await _make(client, "illusionist", 6)
    spells = await _by_index(client, cid)
    assert spells["summon-beast"]["always_prepared"] is True and spells["summon-fey"]["always_prepared"] is True
    assert (spells["summon-beast"]["level"], spells["summon-fey"]["level"]) == (2, 3)
    before = await _used(client, cid)
    r = await _cast(client, cid, spells["summon-beast"]["id"], free_cast=True)
    if r.status_code == 409 and r.json()["detail"]["code"] == "cast_confirm":
        r = await _cast(client, cid, spells["summon-beast"]["id"], free_cast=True, confirm=r.json()["detail"]["warnings"])
    assert r.status_code == 200, r.text
    assert await _used(client, cid) == before
    assert (await _ability(client, cid, BEAST))["uses"] == 0 and (await _ability(client, cid, FEY))["uses"] == 1
    await client.post(f"/characters/{cid}/turn/new")
    again = await _cast(client, cid, spells["summon-beast"]["id"], free_cast=True)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "no_uses"
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, BEAST))["uses"] == 1


async def test_illusory_self_is_a_reaction_restored_by_a_short_rest_or_by_a_slot_of_level_2_or_more(client):
    assert await _ability(client, await _make(client, "illusionist", 9), SELF) is None
    cid = await _make(client, "illusionist", 10)
    assert (await _ability(client, cid, SELF))["restoration_type"] == "short_rest"
    assert (await _use(client, cid, SELF)).status_code == 200
    assert (await _turn(client, cid))["reaction_used"] is True and (await _ability(client, cid, SELF))["uses"] == 0
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid, SELF)).status_code == 409  # senza usi e senza pagare
    no_slot = await _use(client, cid, SELF, params={"restore": True})
    assert no_slot.status_code == 422
    low = await _use(client, cid, SELF, params={"restore": True, "slot_level": "1"})
    assert low.status_code == 422
    paid = await _use(client, cid, SELF, params={"restore": True, "slot_level": "2"})
    assert paid.status_code == 200, paid.text
    assert (await _used(client, cid))[2] == 1 and (await _ability(client, cid, SELF))["uses"] == 0


async def test_illusory_reality_follows_an_illusion_cast_with_a_slot_for_one_minute(client):
    cid = await _make(client, "illusionist", 14)
    assert (await _use(client, cid, REALITY, params={"object": "ponte"})).status_code == 409
    assert (await _cast(client, cid, await _illusion(client, cid), slot_level=1)).status_code == 200
    r = await _use(client, cid, REALITY, params={"object": "ponte"})
    assert r.status_code == 200, r.text
    state = (await _states(client, cid))["illusory_reality"]
    assert state["data"]["object"] == "ponte" and (await _turn(client, cid))["bonus_used"] is True
    assert (await _use(client, await _make(client, "illusionist", 13), REALITY, params={"object": "x"})).status_code == 404


async def test_a_ritual_abjuration_makes_no_ward_and_the_recharge_counts_the_slot_level_not_the_spell_level(client):
    cid = await _make(client, "abjurer", 10)  # 2 x 10 + 3 = 23
    await _hp(client, cid)
    rite = await _spell(client, cid, "Allarme", 1, school="abjuration", is_ritual=True, casting_time="1 azione")
    assert (await _cast(client, cid, rite, as_ritual=True, confirm=["ritual_unprepared"])).status_code == 200
    assert _ward(await _full(client, cid)) is None  # il 2024 vuole uno slot
    await _cast_at(client, cid, await _abjuration(client, cid))
    await _damage(client, cid, 23)
    assert _ward(await _full(client, cid))["data"]["hp"] == 0
    counter = (await _by_index(client, cid))["counterspell"]["id"]  # 3° livello
    await _cast_at(client, cid, counter, 5)
    assert _ward(await _full(client, cid))["data"]["hp"] == 10  # 2 x livello dello slot (5), non dell'incantesimo (3)
    await _cast(client, cid, rite, as_ritual=True, confirm=["ritual_unprepared"])
    assert _ward(await _full(client, cid))["data"]["hp"] == 10  # il rituale non ricarica


async def test_improved_illusions_casts_minor_illusion_as_a_bonus_action(client):
    cid = await _make(client, "illusionist", 3)
    minor = await _spell(client, cid, "Illusione Minore", 0, school="illusion", srd_index="minor-illusion", is_prepared=True)
    assert (await _cast(client, cid, minor)).status_code == 200
    turn = await _turn(client, cid)
    assert turn["bonus_spell_cast"] is True
    other = await _make(client, "evoker", 3)
    minor_other = await _spell(client, other, "Illusione Minore", 0, school="illusion", srd_index="minor-illusion", is_prepared=True)
    assert (await _cast(client, other, minor_other)).status_code == 200
    assert (await _turn(client, other))["bonus_spell_cast"] is False


async def test_illusory_reality_lasts_as_long_as_the_illusion_and_not_for_a_ritual(client):
    cid = await _make(client, "illusionist", 14)
    assert (await _cast(client, cid, await _illusion(client, cid), slot_level=1)).status_code == 200
    await client.post(f"/characters/{cid}/turn/new")  # il turno dopo, con l'illusione ancora in corso
    assert (await _use(client, cid, REALITY, params={"object": "ponte"})).status_code == 200
    rite = await _illusion(client, cid, name="Rito", is_ritual=True)
    await _rest(client, cid, "long")
    assert (await _cast(client, cid, rite, as_ritual=True, confirm=["ritual_unprepared"])).status_code == 200
    assert (await _use(client, cid, REALITY, params={"object": "x"})).status_code == 409  # il 2024 vuole uno slot


async def test_the_savant_retrofit_lists_and_accepts_only_spells_of_its_school(client, test_session_factory):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from api.services.catalog_migration import migrate_catalog
    from core.db.models import Character

    cid = await _make(client, "abjurer", 3)
    good = await _spell(client, cid, "Scudo", 1, school="abjuration")
    bad = await _spell(client, cid, "Dardo", 1, school="evocation")
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).options(selectinload(Character.classes)).where(Character.id == cid))).scalar_one()
        char.pending_choices = [c for c in char.pending_choices if c["kind"] != "class_option"]
        char.settings = {k: v for k, v in (char.settings or {}).items() if k != "retrofit_done"}
        for cls in char.classes:
            cls.options = {}
        await s.commit()
    assert await migrate_catalog(test_session_factory) >= 1
    choice = _choice(await _full(client, cid), "abjuration_savant")
    assert choice["retrofit"] is True and {o["id"] for o in choice["spell_pick"]["owned"]} == {good}
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve", json={"kind": "class_option", "options": [str(bad)]})
    assert r.status_code == 422 and r.json()["detail"] == "spell_not_known"
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve", json={"kind": "class_option", "options": [str(good)]})
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------
# Estensioni del modulo comune
# ---------------------------------------------------------------------------

def test_school_range_bonus_only_stretches_ranges_of_3_metres_or_more():
    from types import SimpleNamespace
    from core.rules.spellcasting import school_boost_range
    spell = lambda rng: SimpleNamespace(range_area=rng, school="Illusion", srd_index=None, name="x")
    assert school_boost_range(spell("9 m"), "illusion", 18) == "27 m"
    assert school_boost_range(spell("60 ft"), "illusion", 18) == "120 ft"
    assert school_boost_range(spell("1,5 m"), "illusion", 18) is None
    assert school_boost_range(spell("Contatto"), "illusion", 18) is None
    assert school_boost_range(SimpleNamespace(range_area="9 m", school="evocation"), "illusion", 18) is None
