"""Paladino 2014 (Task 25): Stile di Combattimento, Punizione Divina e la sua versione migliorata, le aure del paladino su
di sé (Protezione, Coraggio) e Salute Divina."""
from __future__ import annotations

import pytest

from tests.integration.rules.test_2014_bard import _full, _keys_of, _roll_keys, _use
from tests.integration.rules.test_2014_fighter_styles import _item, _pending
from tests.integration.rules.test_2014_paladin import _hurt, _paladin, _turn

STYLES = ("great_weapon", "defense", "dueling", "protection")
SMITE, FIEND, IMPROVED = "paladin.divine_smite", "paladin.divine_smite_fiend", "paladin.improved_divine_smite"
PROTECTION = "paladin.style_protection"


async def _choose(client, cid, *styles: str):
    choice = _pending(await _full(client, cid))
    return await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve",
                             json={"kind": "class_option", "options": list(styles)})


async def _styled(client, style, level=3, **scores) -> int:
    cid = await _paladin(client, level, **scores)
    r = await _choose(client, cid, style)
    assert r.status_code == 200, r.text
    return cid


def _sword(client, cid, **kw):
    return _item(client, cid, "Spada", damage_dice="1d8", weapon_type="melee", properties=[], **kw)


async def _attack(client, cid, wid, die=10, **body):
    return await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": die, "confirm_extra_attack": True, **body})


async def _deferred(client, cid, wid, die=10, **body) -> dict:
    r = await _attack(client, cid, wid, die, defer_damage=True, **body)
    assert r.status_code == 200, r.text
    return r.json()


async def _damage(client, cid, hit, options, **inputs):
    return await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage",
                             json={"options": options, "option_inputs": inputs})


# ---------------------------------------------------------------------------
# Stile di Combattimento
# ---------------------------------------------------------------------------

async def test_the_style_is_chosen_at_level_2_among_four(client):
    assert _pending(await _full(client, await _paladin(client, 1))) is None
    choice = _pending(await _full(client, await _paladin(client, 2)))
    assert choice["count"] == 1 and {o["key"] for o in choice["options"]} == set(STYLES)
    assert all(o["name"]["it"] and o["name"]["en"] and o["summary"]["it"] for o in choice["options"])


async def test_a_paladin_created_above_level_2_is_asked_for_the_style_too(client):
    assert _pending(await _full(client, await _paladin(client, 9, "devotion"))) is not None


async def test_the_chosen_style_becomes_a_row_and_the_choice_closes(client):
    cid = await _styled(client, "dueling")
    assert "paladin.style_dueling" in await _keys_of(client, cid) and _pending(await _full(client, cid)) is None
    assert not {f"paladin.style_{s}" for s in STYLES if s != "dueling"} & await _keys_of(client, cid)


@pytest.mark.parametrize("options", [[], ["defense", "dueling"], ["archery"], ["two_weapon"]])
async def test_exactly_one_of_the_four_styles_is_taken(client, options):
    cid = await _paladin(client, 3)
    assert (await _choose(client, cid, *options)).status_code == 422
    assert _pending(await _full(client, cid)) is not None


async def test_defense_adds_one_to_ac_only_while_wearing_armor(client):
    cid = await _paladin(client, 3)
    await _item(client, cid, "Maglia", "armor", armor_type="heavy", ac_value=16)
    await _choose(client, cid, "defense")
    plain = (await _full(client, cid))["ac"]
    assert (await _full(client, cid))["ac_breakdown"]["rules"] == 0
    iid = next(i["id"] for i in (await _full(client, cid))["items"] if i["name"] == "Maglia")
    await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": "body"})
    full = await _full(client, cid)
    assert full["ac_breakdown"]["rules"] == 1 and full["ac"] >= plain + 1


async def test_defense_is_not_given_by_a_shield_alone(client):
    cid = await _styled(client, "defense")
    await _item(client, cid, "Scudo", "shield", equip="off_hand", ac_bonus=2)
    assert (await _full(client, cid))["ac_breakdown"]["rules"] == 0


async def _bonus(client, cid, wid, **body) -> int:
    r = await _attack(client, cid, wid, **body)
    assert r.status_code == 200, r.text
    return r.json()["damage_bonus"]


async def test_dueling_adds_two_to_a_one_handed_melee_weapon_with_a_shield_but_not_with_another_weapon(client):
    cid = await _paladin(client, 3)
    wid = await _sword(client, cid, equip="main_hand")
    await _item(client, cid, "Scudo", "shield", equip="off_hand", ac_bonus=2)
    plain = await _bonus(client, cid, wid)
    await _choose(client, cid, "dueling")
    assert await _bonus(client, cid, wid) == plain + 2
    other = await _paladin(client, 3)
    wid = await _sword(client, other, equip="main_hand")
    await _item(client, other, "Pugnale", damage_dice="1d4", weapon_type="melee", properties=["light"], equip="off_hand")
    plain = await _bonus(client, other, wid)
    await _choose(client, other, "dueling")
    assert await _bonus(client, other, wid) == plain


async def test_dueling_is_not_for_two_handed_or_ranged_weapons(client):
    cid = await _paladin(client, 3)
    great = await _item(client, cid, "Spadone", damage_dice="2d6", weapon_type="melee", properties=["heavy", "two-handed"])
    bow = await _item(client, cid, "Arco", damage_dice="1d8", weapon_type="ranged", properties=["ammunition"])
    plain = [await _bonus(client, cid, great), await _bonus(client, cid, bow)]
    await _choose(client, cid, "dueling")
    assert [await _bonus(client, cid, great), await _bonus(client, cid, bow)] == plain


def _dice(monkeypatch, *values):
    it = iter(values)
    monkeypatch.setattr("api.routers.items.random.randint", lambda a, b: next(it))


async def test_great_weapon_rerolls_a_one_or_a_two_once_with_a_two_handed_melee_weapon(client, monkeypatch):
    cid = await _styled(client, "great_weapon", strength=10)
    wid = await _item(client, cid, "Spadone", damage_dice="2d6", weapon_type="melee", properties=["heavy", "two-handed"])
    _dice(monkeypatch, 1, 6, 4)
    body = (await _attack(client, cid, wid)).json()
    assert body["damage_rolls"] == [4, 6] and body["rerolled"] == [[1, 4]]


async def test_great_weapon_is_not_for_a_one_handed_sword_or_a_bow(client, monkeypatch):
    cid = await _styled(client, "great_weapon", strength=10)
    sword = await _sword(client, cid)
    bow = await _item(client, cid, "Arco", damage_dice="1d8", weapon_type="ranged", properties=["ammunition"])
    for wid in (sword, bow):
        _dice(monkeypatch, 1)
        assert (await _attack(client, cid, wid)).json().get("rerolled") is None


async def test_protection_is_a_reaction_with_a_shield_and_shows_the_disadvantage_to_the_gm(client):
    cid = await _styled(client, "protection")
    r = await _use(client, cid, PROTECTION)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "feature_unavailable"
    await _item(client, cid, "Scudo", "shield", equip="off_hand", ac_bonus=2)
    ok = await _use(client, cid, PROTECTION)
    assert ok.status_code == 200 and ok.json()["targets"] == [PROTECTION]
    assert (await _turn(client, cid))["reaction_used"] is True
    assert (await _use(client, cid, PROTECTION)).json()["detail"]["code"] == "turn_slot_used"


async def test_a_style_of_the_fighter_list_is_not_offered_to_the_paladin(client):
    keys = {f.key for f in __import__("core.rules.catalog", fromlist=["features_for"]).features_for("2014", "paladin")}
    assert not keys & {"paladin.style_archery", "paladin.style_two_weapon"}


# ---------------------------------------------------------------------------
# Punizione Divina
# ---------------------------------------------------------------------------

async def _slot(client, cid, level, total=2) -> None:
    r = await client.post(f"/characters/{cid}/spell_slots", json={"level": level, "total": total})
    assert r.status_code in (200, 201), r.text


async def _slots(client, cid) -> dict[int, int]:
    return {s["level"]: s["used"] for s in (await _full(client, cid))["spell_slots"]}


async def _listed(client, cid, wid, **query) -> list[dict]:
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": wid, **query})
    assert r.status_code == 200, r.text
    return r.json()


def _smite_dice(listed: list[dict]) -> dict[int, str]:
    smite = next(o for o in listed if o["key"] == SMITE)
    return {s["level"]: s["dice"] for s in smite["input_options"]}


async def test_smite_offers_two_dice_at_slot_one_plus_one_per_level_up_to_five(client):
    cid = await _paladin(client, 17)
    wid = await _sword(client, cid)
    assert _smite_dice(await _listed(client, cid, wid)) == {1: "2d8", 2: "3d8", 3: "4d8", 4: "5d8", 5: "5d8"}


async def test_smite_is_offered_only_after_a_melee_weapon_hit_and_needs_a_free_slot(client):
    cid = await _paladin(client, 5)
    wid = await _sword(client, cid)
    bow = await _item(client, cid, "Arco", damage_dice="1d8", weapon_type="ranged", properties=["ammunition"])
    axe = await _item(client, cid, "Accetta", damage_dice="1d6", weapon_type="melee", properties=["thrown"])
    assert SMITE in [o["key"] for o in await _listed(client, cid, wid, attack_mode="melee", grip="one")]
    assert SMITE not in [o["key"] for o in await _listed(client, cid, bow)]
    assert SMITE not in [o["key"] for o in await _listed(client, cid, axe, attack_mode="thrown", grip="one")]
    for slot in (await _full(client, cid))["spell_slots"]:
        await client.patch(f"/characters/{cid}/spell_slots/{slot['id']}", json={"used": slot["total"]})
    assert SMITE not in [o["key"] for o in await _listed(client, cid, wid, attack_mode="melee", grip="one")]


async def test_a_level_1_paladin_has_no_smite(client):
    cid = await _paladin(client, 1)
    assert SMITE not in [o["key"] for o in await _listed(client, cid, await _sword(client, cid))]


async def test_smite_spends_the_chosen_slot_and_adds_the_dice(client):
    cid = await _paladin(client, 5)
    wid = await _sword(client, cid)
    hit = await _deferred(client, cid, wid)
    r = await _damage(client, cid, hit, [SMITE], **{SMITE: {"slot_level": 2}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["option_result"]["extra_rolls"]) == 3 and all(1 <= v <= 8 for v in body["option_result"]["extra_rolls"])
    assert body["damage_total"] == hit["damage_total"] + sum(body["option_result"]["extra_rolls"])
    assert await _slots(client, cid) == {1: 0, 2: 1}
    assert any("radios" in e["it"].lower() for e in body["option_result"]["effects"])


async def test_smite_doubles_the_dice_on_a_critical(client):
    cid = await _paladin(client, 5)
    wid = await _sword(client, cid)
    hit = await _deferred(client, cid, wid, die=20)
    r = await _damage(client, cid, hit, [SMITE], **{SMITE: {"slot_level": 1}})
    assert hit["is_critical"] and len(r.json()["option_result"]["extra_rolls"]) == 4


async def test_smite_against_an_undead_or_fiend_adds_one_more_die_and_needs_the_smite(client):
    cid = await _paladin(client, 5)
    wid = await _sword(client, cid)
    hit = await _deferred(client, cid, wid)
    alone = await _damage(client, cid, hit, [FIEND])
    assert alone.status_code == 409 and alone.json()["detail"]["code"] == "option_unavailable"
    assert await _slots(client, cid) == {1: 0, 2: 0}
    r = await _damage(client, cid, hit, [SMITE, FIEND], **{SMITE: {"slot_level": 1}})
    assert r.status_code == 200, r.text
    assert len(r.json()["option_result"]["extra_rolls"]) == 3 and await _slots(client, cid) == {1: 1, 2: 0}


async def test_smite_with_a_slot_that_does_not_exist_or_is_used_up_changes_nothing(client):
    cid = await _paladin(client, 2)
    wid = await _sword(client, cid)
    hit = await _deferred(client, cid, wid)
    for level in (2, 5, 0):
        r = await _damage(client, cid, hit, [SMITE], **{SMITE: {"slot_level": level}})
        assert r.status_code == 409, level
    assert await _slots(client, cid) == {1: 0}


# ---------------------------------------------------------------------------
# Punizione Divina Migliorata
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,dice", [(10, 0), (11, 1), (20, 1)])
async def test_improved_smite_adds_a_radiant_die_to_every_melee_weapon_hit(client, level, dice):
    cid = await _paladin(client, level)
    wid = await _sword(client, cid)
    body = (await _attack(client, cid, wid)).json()
    block = body.get("option_result") or {}
    assert len(block.get("extra_rolls", [])) == dice
    if dice:
        assert IMPROVED in block["keys"] and body["damage_total"] == sum(body["damage_rolls"]) + body["damage_bonus"] + sum(block["extra_rolls"])
        assert any("radios" in e["it"].lower() for e in block["effects"])


async def test_improved_smite_is_not_offered_as_a_choice(client):
    cid = await _paladin(client, 11)
    wid = await _sword(client, cid)
    assert IMPROVED not in [o["key"] for o in await _listed(client, cid, wid)]


async def test_improved_smite_doubles_on_a_critical_and_skips_ranged_and_thrown_attacks(client):
    cid = await _paladin(client, 11)
    wid = await _sword(client, cid)
    bow = await _item(client, cid, "Arco", damage_dice="1d8", weapon_type="ranged", properties=["ammunition"])
    axe = await _item(client, cid, "Accetta", damage_dice="1d6", weapon_type="melee", properties=["thrown"])
    assert len((await _attack(client, cid, wid, die=20)).json()["option_result"]["extra_rolls"]) == 2
    assert (await _attack(client, cid, bow)).json().get("option_result") is None
    assert (await _attack(client, cid, axe, attack_mode="thrown")).json().get("option_result") is None


async def test_improved_smite_adds_to_a_divine_smite(client):
    cid = await _paladin(client, 11)
    wid = await _sword(client, cid)
    hit = await _deferred(client, cid, wid)
    assert len(hit["option_result"]["extra_rolls"]) == 1
    r = await _damage(client, cid, hit, [SMITE], **{SMITE: {"slot_level": 1}})
    assert r.status_code == 200, r.text
    assert len(r.json()["option_result"]["extra_rolls"]) == 3 and r.json()["option_result"]["keys"].count(IMPROVED) == 1


# ---------------------------------------------------------------------------
# Aura di Protezione, Aura di Coraggio, Salute Divina
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,charisma,bonus", [(5, 16, 0), (6, 16, 3), (6, 8, 1), (6, 10, 1), (20, 20, 5)])
async def test_aura_of_protection_adds_charisma_with_a_minimum_of_one_to_every_save(client, level, charisma, bonus):
    cid = await _paladin(client, level, charisma=charisma)
    flat = (await _full(client, cid))["computed"]["save_flat"]
    assert set(flat.values()) == {bonus}


async def test_aura_of_protection_shows_in_the_save_roll_notes(client):
    cid = await _paladin(client, 6, charisma=14)
    r = await client.post(f"/characters/{cid}/saving_throws/dexterity/roll", json={"die": 10})
    assert r.status_code == 200, r.text
    assert "feature:paladin.aura_of_protection" in r.json()["notes"]


async def test_aura_of_protection_does_not_work_while_the_paladin_is_at_zero_hp(client, test_session_factory):
    cid = await _paladin(client, 6, charisma=16)
    await _hurt(test_session_factory, cid, 0)
    assert set((await _full(client, cid))["computed"]["save_flat"].values()) == {0}


async def test_aura_of_protection_does_not_count_for_a_death_save_roll_with_the_paladin_unconscious(client, test_session_factory):
    cid = await _paladin(client, 6, charisma=16)
    await _hurt(test_session_factory, cid, 0)
    r = await client.post(f"/characters/{cid}/death_saves/roll", json={"die": 10})
    assert r.status_code == 200, r.text
    assert "feature:paladin.aura_of_protection" not in (r.json().get("notes") or [])


async def test_aura_of_courage_makes_the_paladin_immune_to_frightened_from_level_10(client):
    for level, frightened in ((9, True), (10, None)):
        cid = await _paladin(client, level)
        r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"frightened": True, "prone": True}})
        assert r.json()["conditions"].get("frightened") == frightened and r.json()["conditions"]["prone"] is True


async def test_aura_of_courage_stops_while_the_paladin_is_unconscious(client, test_session_factory):
    cid = await _paladin(client, 10)
    await _hurt(test_session_factory, cid, 0)
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"frightened": True}})
    assert r.json()["conditions"].get("frightened") is True


async def test_aura_improvements_row_is_there_from_18_and_the_range_grows(client):
    for level, rng in ((17, None), (18, 9)):
        keys = await _keys_of(client, await _paladin(client, level))
        assert ("paladin.aura_improvements" in keys) == (rng is not None)


def test_the_passive_rows_have_text_in_both_languages():
    from core.rules.catalog import features_for
    rows = {f.key: f for f in features_for("2014", "paladin")}
    for key in ("paladin.divine_health", "paladin.aura_improvements", "paladin.aura_of_courage", "paladin.aura_of_protection"):
        assert rows[key].summary["it"] and rows[key].summary["en"], key
