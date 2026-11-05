"""Monaco 2014 (Task 24): Via dei Quattro Elementi: Discepolo degli Elementi (scelta, sostituzione, lanci col ki), le
discipline con incantesimo, Sintonia Elementale, Forma del Fiume Fluente, Frusta d'Acqua, Pugno dell'Aria Inviolabile e
Zanne del Serpente di Fuoco."""
from __future__ import annotations

import pytest

from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _use
from tests.integration.rules.test_2014_monk import _monk, _turn
from tests.integration.rules.test_2014_monk_ki import _damage, _hit, _ki, _set_ki, _states, _strike

GROUP = "elemental_disciplines"
# (chiave, incantesimo, ki, livello minimo)
SPELL_DISCIPLINES = [
    ("sweeping_cinder_strike", "Mani brucianti", 2, 3), ("fist_of_four_thunders", "Onda tonante", 2, 3),
    ("rush_of_the_gale_spirits", "Folata di vento", 2, 3), ("gong_of_the_summit", "Frantumare", 3, 6),
    ("clench_of_the_north_wind", "Bloccare persone", 3, 6), ("ride_the_wind", "Volare", 4, 11),
    ("flames_of_the_phoenix", "Palla di fuoco", 4, 11), ("mist_stance", "Forma gassosa", 4, 11),
    ("eternal_mountain_defense", "Pelle di pietra", 5, 17), ("river_of_hungry_flame", "Muro di fuoco", 5, 17),
    ("wave_of_rolling_earth", "Muro di pietra", 6, 17), ("breath_of_winter", "Cono di freddo", 6, 17),
]
OTHER_DISCIPLINES = ["shape_the_flowing_river", "water_whip", "fist_of_unbroken_air", "fangs_of_the_fire_snake"]
ALL = [d[0] for d in SPELL_DISCIPLINES] + OTHER_DISCIPLINES


def _key(discipline: str) -> str:
    return f"monk.discipline_{discipline}"


def _pending(full: dict) -> dict | None:
    return next((c for c in full["pending_choices"] if c.get("group") == GROUP), None)


async def _resolve(client, cid, *picks: str):
    choice = _pending(await _full(client, cid))
    return await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve", json={"kind": "class_option", "options": list(picks)})


async def _disciple(client, level=3, *picks: str, **scores) -> int:
    """Un monaco dei Quattro Elementi con le discipline indicate; le altre scelte aperte sono riempite con altre qualsiasi."""
    cid = await _monk(client, level, "four_elements", **scores)
    choice = _pending(await _full(client, cid))
    if picks and choice:
        fill = [o["key"] for o in choice["options"] if o["key"] not in picks]
        r = await _resolve(client, cid, *picks, *fill[:choice["count"] - len(picks)])
        assert r.status_code == 200, r.text
    return cid


async def _spells(client, cid) -> dict[str, dict]:
    return {s["name"]: s for s in (await client.get(f"/characters/{cid}/spells")).json()}


async def _cast_ki(client, cid, spell, **body):
    return await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"ki": True, **body})


# ---------------------------------------------------------------------------
# La scelta delle discipline
# ---------------------------------------------------------------------------

async def test_level_3_asks_for_one_discipline_and_the_attunement_is_always_known(client):
    cid = await _monk(client, 3, "four_elements")
    choice = _pending(await _full(client, cid))
    assert choice["count"] == 1
    offered = {o["key"] for o in choice["options"]}
    assert offered == {"sweeping_cinder_strike", "fist_of_four_thunders", "rush_of_the_gale_spirits", "shape_the_flowing_river",
                       "water_whip", "fist_of_unbroken_air", "fangs_of_the_fire_snake"}
    assert all(o["name"]["it"] and o["name"]["en"] and o["summary"]["it"] for o in choice["options"])
    row = await _ability(client, cid, "monk.elemental_attunement")
    assert row is not None and row["is_passive"] is True and row["has_on_use"] is False and row["uses"] is None
    assert row["max_uses"] is None


async def test_new_disciplines_arrive_at_6_11_and_17_and_the_options_follow_the_level(client):
    cid = await _disciple(client, 3, "water_whip")
    assert _pending(await _full(client, cid)) is None
    klass = (await _full(client, cid))["classes"][0]
    expected = {6: (2, {"gong_of_the_summit", "clench_of_the_north_wind"}), 11: (3, {"ride_the_wind", "flames_of_the_phoenix", "mist_stance"}),
                17: (4, {"eternal_mountain_defense", "river_of_hungry_flame", "wave_of_rolling_earth", "breath_of_winter"})}
    chosen = 1
    for level, (total, new) in expected.items():
        await client.patch(f"/characters/{cid}/classes/{klass['id']}", json={"level": level})
        choice = _pending(await _full(client, cid))
        assert choice["count"] == total - chosen and new <= {o["key"] for o in choice["options"]}
        pick = sorted(new)[0]
        picks = [pick] + [o["key"] for o in choice["options"] if o["key"] != pick][:choice["count"] - 1]
        assert (await _resolve(client, cid, *picks)).status_code == 200
        chosen = total
    assert _pending(await _full(client, cid)) is None


async def test_a_discipline_above_the_level_is_not_in_the_list_and_is_refused(client):
    cid = await _monk(client, 3, "four_elements")
    assert "ride_the_wind" not in {o["key"] for o in _pending(await _full(client, cid))["options"]}
    assert (await _resolve(client, cid, "ride_the_wind")).status_code == 422
    assert _pending(await _full(client, cid)) is not None


async def test_exactly_the_right_number_of_disciplines_is_taken(client):
    cid = await _monk(client, 3, "four_elements")
    for picks in ([], ["water_whip", "fist_of_unbroken_air"], ["nothing"]):
        assert (await _resolve(client, cid, *picks)).status_code == 422


async def test_a_chosen_discipline_becomes_a_row_and_the_others_do_not(client):
    cid = await _disciple(client, 3, "water_whip")
    keys = await _keys_of(client, cid)
    assert _key("water_whip") in keys and _key("fist_of_unbroken_air") not in keys


async def test_only_the_four_elements_tradition_has_disciplines(client):
    for sub in (None, "open_hand", "shadow"):
        cid = await _monk(client, 6, sub)
        assert _pending(await _full(client, cid)) is None
        assert not {k for k in await _keys_of(client, cid) if k.startswith("monk.discipline_")}
        assert "monk.elemental_attunement" not in await _keys_of(client, cid)


async def test_a_discipline_can_be_replaced_with_another_of_the_allowed_level(client):
    cid = await _disciple(client, 6, "water_whip", "gong_of_the_summit")
    klass = (await _full(client, cid))["classes"][0]
    state = (await client.get(f"/characters/{cid}/classes/{klass['id']}/options/{GROUP}")).json()
    assert state["replaceable"] is True and {o["key"] for o in state["chosen"]} == {"water_whip", "gong_of_the_summit"}
    r = await client.post(f"/characters/{cid}/classes/{klass['id']}/options/replace",
                          json={"group": GROUP, "old_key": "water_whip", "new_key": "fist_of_unbroken_air"})
    assert r.status_code == 200, r.text
    keys = await _keys_of(client, cid)
    assert _key("fist_of_unbroken_air") in keys and _key("water_whip") not in keys
    r = await client.post(f"/characters/{cid}/classes/{klass['id']}/options/replace",
                          json={"group": GROUP, "old_key": "fist_of_unbroken_air", "new_key": "ride_the_wind"})
    assert r.status_code == 422  # livello minimo 11


# ---------------------------------------------------------------------------
# Lanciare con il ki
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("discipline,spell,cost,level", SPELL_DISCIPLINES)
async def test_each_discipline_with_a_spell_gives_it_at_its_ki_cost(client, discipline, spell, cost, level):
    cid = await _disciple(client, level, discipline)
    spells = await _spells(client, cid)
    assert spell in spells, sorted(spells)
    info = spells[spell]["ki_cast"]
    assert info["cost"] == cost and spells[spell]["always_prepared"] is True
    assert (await _ability(client, cid, _key(discipline)))["is_passive"] is True


async def test_a_discipline_with_a_higher_level_cannot_be_taken_early(client):
    cid = await _monk(client, 10, "four_elements")
    assert "flames_of_the_phoenix" not in {o["key"] for o in _pending(await _full(client, cid))["options"]}


@pytest.mark.parametrize("level,extra", [(3, 0), (4, 0), (5, 1), (8, 1), (9, 2), (12, 2), (13, 3), (16, 3), (17, 4), (20, 4)])
async def test_the_extra_ki_follows_the_cap_of_the_level(client, level, extra):
    cid = await _disciple(client, level, "sweeping_cinder_strike")
    info = (await _spells(client, cid))["Mani brucianti"]["ki_cast"]
    assert info["max_extra"] == extra and info["ki_left"] == level


async def test_a_ki_cast_spends_the_cost_and_the_action_and_no_slot(client):
    cid = await _disciple(client, 5, "sweeping_cinder_strike", wisdom=16)
    spell = (await _spells(client, cid))["Mani brucianti"]
    assert spell["save_dc"] == 8 + 3 + 3  # la CD del ki
    r = await _cast_ki(client, cid, spell)
    assert r.status_code == 200, r.text
    assert await _ki(client, cid) == 3 and (await _turn(client, cid))["action_used"] is True
    assert all(s["used"] == 0 for s in (await _full(client, cid))["spell_slots"])


async def test_extra_ki_raises_the_level_of_the_spell_up_to_the_cap(client, monkeypatch):
    cid = await _disciple(client, 5, "sweeping_cinder_strike")
    spell = (await _spells(client, cid))["Mani brucianti"]
    r = await _cast_ki(client, cid, spell, ki_extra=1)
    assert r.status_code == 200, r.text
    assert await _ki(client, cid) == 2  # 2 + 1 extra
    rolled = await client.post(f"/characters/{cid}/spells/{spell['id']}/roll_damage", json={"casting_level": 2})
    assert rolled.status_code == 200 and rolled.json()["scaled_dice"] == "4d6"  # 3d6 + 1d6 del livello in più


async def test_extra_ki_above_the_cap_or_before_level_5_is_refused_and_costs_nothing(client):
    cid = await _disciple(client, 5, "sweeping_cinder_strike")
    spell = (await _spells(client, cid))["Mani brucianti"]
    r = await _cast_ki(client, cid, spell, ki_extra=2)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "ki_cap"
    assert await _ki(client, cid) == 5 and not (await _turn(client, cid))["action_used"]
    low = await _disciple(client, 3, "sweeping_cinder_strike")
    r = await _cast_ki(client, low, (await _spells(client, low))["Mani brucianti"], ki_extra=1)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "ki_cap"


async def test_a_ki_cast_needs_the_ki_and_a_free_action(client):
    cid = await _disciple(client, 5, "sweeping_cinder_strike")
    spell = (await _spells(client, cid))["Mani brucianti"]
    await _set_ki(client, cid, 1)
    r = await _cast_ki(client, cid, spell)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses" and await _ki(client, cid) == 1
    await _set_ki(client, cid, 5)
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "action"})
    r = await _cast_ki(client, cid, spell)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "turn_slot_used" and await _ki(client, cid) == 5


async def test_the_spell_of_a_ki_cast_follows_its_own_rules_for_concentration(client):
    cid = await _disciple(client, 3, "rush_of_the_gale_spirits")
    spell = (await _spells(client, cid))["Folata di vento"]
    assert (await _cast_ki(client, cid, spell)).status_code == 200
    assert (await _full(client, cid))["concentrating_spell_id"] == spell["id"]


async def test_the_ki_cast_is_not_offered_for_a_spell_of_another_source(client):
    cid = await _disciple(client, 3, "water_whip")
    spells = await _spells(client, cid)
    assert "Mani brucianti" not in spells and not any(s.get("ki_cast") for s in spells.values())


# ---------------------------------------------------------------------------
# Le altre discipline
# ---------------------------------------------------------------------------

async def test_shape_the_flowing_river_is_an_action_for_one_ki(client):
    cid = await _disciple(client, 3, "shape_the_flowing_river")
    row = await _ability(client, cid, _key("shape_the_flowing_river"))
    assert row["action_type"] == "action" and row["has_on_use"] is True
    assert (await _use(client, cid, _key("shape_the_flowing_river"))).status_code == 200
    assert await _ki(client, cid) == 2 and (await _turn(client, cid))["action_used"] is True
    again = await _use(client, cid, _key("shape_the_flowing_river"))
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used" and await _ki(client, cid) == 2


@pytest.mark.parametrize("discipline,ability,dice_sides", [("water_whip", "dexterity", 10), ("fist_of_unbroken_air", "strength", 10)])
async def test_the_ki_attacks_roll_3d10_plus_1d10_per_extra_ki_and_show_the_ki_dc(client, discipline, ability, dice_sides):
    cid = await _disciple(client, 5, discipline, wisdom=16)  # competenza +3, Saggezza +3
    row = await _ability(client, cid, _key(discipline))
    assert row["choose_amount"] is True and row["min_amount"] == 2
    r = await _use(client, cid, _key(discipline), amount=2)
    assert r.status_code == 200, r.text
    assert len(r.json()["rolls"]) == 3 and all(1 <= v <= dice_sides for v in r.json()["rolls"])
    assert await _ki(client, cid) == 3 and r.json()["targets"] == [_key(discipline)]
    effect = (await client.get(f"/characters/{cid}/target-effects/{_key(discipline)}")).json()["result"]
    assert (effect["condition"], effect["save_ability"], effect["save_dc"]) == ("prone", ability, 14)
    await client.post(f"/characters/{cid}/turn/new")
    r = await _use(client, cid, _key(discipline), amount=3)
    assert len(r.json()["rolls"]) == 4 and await _ki(client, cid) == 0


async def test_the_ki_attacks_need_at_least_two_ki_and_the_action(client):
    cid = await _disciple(client, 5, "water_whip")
    r = await _use(client, cid, _key("water_whip"), amount=1)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "amount_too_low" and await _ki(client, cid) == 5
    await _set_ki(client, cid, 1)
    r = await _use(client, cid, _key("water_whip"), amount=2)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    assert not (await _turn(client, cid))["action_used"]


async def test_fangs_of_the_fire_snake_makes_the_unarmed_strikes_fire_for_the_turn(client):
    cid = await _disciple(client, 3, "fangs_of_the_fire_snake", dexterity=16)
    assert (await _strike(client, cid)).json()["damage_type"] == "bludgeoning"
    await client.post(f"/characters/{cid}/turn/new")
    r = await _use(client, cid, _key("fangs_of_the_fire_snake"))
    assert r.status_code == 200, r.text
    assert await _ki(client, cid) == 2 and not (await _turn(client, cid))["action_used"]  # non costa azioni
    state = (await _states(client, cid))["fangs_of_the_fire_snake"]
    assert state["data"]["reach_bonus_ft"] == 10 and state["rounds_left"] == 1
    assert (await _strike(client, cid)).json()["damage_type"] == "fire"
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _strike(client, cid)).json()["damage_type"] == "bludgeoning"


async def test_fangs_extra_die_costs_one_more_ki_on_a_hit_and_adds_a_d10_of_fire(client, monkeypatch):
    cid = await _disciple(client, 3, "fangs_of_the_fire_snake", dexterity=16)
    extra = "monk.fangs_extra_damage"
    assert extra not in await _roll_keys(client, cid, "attack")  # senza lo stato non c'è
    await _use(client, cid, _key("fangs_of_the_fire_snake"))
    assert extra in await _roll_keys(client, cid, "attack")
    hit = await _hit(client, cid)
    body = (await _damage(client, cid, hit, extra)).json()
    assert await _ki(client, cid) == 1 and len(body["option_result"]["extra_rolls"]) == 1
    assert extra in await _roll_keys(client, cid, "attack")
    await _set_ki(client, cid, 0)
    assert extra not in await _roll_keys(client, cid, "attack")


async def test_the_attunement_has_no_ki_cost_and_no_use_button(client):
    cid = await _disciple(client, 3, "water_whip")
    row = await _ability(client, cid, "monk.elemental_attunement")
    assert row["has_on_use"] is False and row["is_passive"] is True
    assert await _ki(client, cid) == 3
