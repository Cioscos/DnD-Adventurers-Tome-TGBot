"""Stregone 2014 (Task 28): Metamagia, le otto opzioni e la loro conferma al lancio e al danno."""
from __future__ import annotations

import pytest

from core.rules.catalog.y2014.sorcerer import METAMAGIC
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys
from tests.integration.rules.test_2014_fighter_eldritch_knight import _cast, _spell
from tests.integration.rules.test_2014_paladin import _new_turn, _rest, _turn
from tests.integration.rules.test_2014_sorcerer import SP, _points, _set_points, _sorcerer

OPTIONS = ["subtle", "distant", "extended", "heightened", "empowered", "careful", "twinned", "quickened"]
SUBTLE, DISTANT, EXTENDED, HEIGHTENED, EMPOWERED, CAREFUL, TWINNED, QUICKENED = (f"sorcerer.metamagic_{k}" for k in OPTIONS)


def _pending(full: dict) -> dict | None:
    return next((c for c in full["pending_choices"] if c.get("group") == "metamagic"), None)


async def _caster(client, level=10, *picks: str, **scores) -> int:
    """Uno stregone con le opzioni indicate (le altre scelte sono riempite con altre qualsiasi)."""
    cid = await _sorcerer(client, level, "draconic", **{"charisma": 18, **scores})
    choice = _pending(await _full(client, cid))
    chosen = list(picks) + [k for k in OPTIONS if k not in picks]
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve", json={"kind": "class_option", "options": chosen[:choice["count"]]})
    assert r.status_code == 200, r.text
    return cid


async def _use_spell(client, cid, spell, *options, slot_level=None, **inputs):
    body = {"options": list(options), "option_inputs": inputs}
    if slot_level is not None:
        body["slot_level"] = slot_level
    return await client.post(f"/characters/{cid}/spells/{spell}/use", json=body)


async def _damage(client, cid, spell, **body):
    r = await client.post(f"/characters/{cid}/spells/{spell}/roll_damage", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# La scelta
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,count", [(2, None), (3, 2), (9, 2), (10, 3), (16, 3), (17, 4), (20, 4)])
async def test_metamagic_options_known_follow_the_level(client, level, count):
    pending = _pending(await _full(client, await _sorcerer(client, level)))
    assert (pending["count"] if pending else None) == count


async def test_the_eight_options_are_offered_each_with_a_name_and_a_summary(client):
    choice = _pending(await _full(client, await _sorcerer(client, 3)))
    assert {o["key"] for o in choice["options"]} == set(OPTIONS) and len(METAMAGIC) == 8
    assert all(o["name"]["it"] and o["name"]["en"] and 0 < len(o["summary"]["it"]) <= 200 for o in choice["options"])


async def test_each_chosen_option_becomes_a_row_and_the_others_do_not(client):
    cid = await _caster(client, 3, "twinned", "quickened")
    keys = await _keys_of(client, cid)
    assert {TWINNED, QUICKENED} <= keys and not keys & {SUBTLE, DISTANT, EXTENDED, HEIGHTENED, EMPOWERED, CAREFUL}


async def test_the_new_pick_at_level_10_adds_to_the_old_ones_and_one_can_be_replaced(client):
    cid = await _caster(client, 3, "twinned", "quickened")
    klass = (await _full(client, cid))["classes"][0]
    await client.patch(f"/characters/{cid}/classes/{klass['id']}", json={"level": 10})
    choice = _pending(await _full(client, cid))
    assert choice["count"] == 1 and not {"twinned", "quickened"} & {o["key"] for o in choice["options"]}
    state = (await client.get(f"/characters/{cid}/classes/{klass['id']}/options/metamagic")).json()
    assert state["replaceable"] is True and {o["key"] for o in state["chosen"]} == {"twinned", "quickened"}
    r = await client.post(f"/characters/{cid}/classes/{klass['id']}/options/replace",
                          json={"group": "metamagic", "old_key": "twinned", "new_key": "subtle"})
    assert r.status_code == 200, r.text
    assert SUBTLE in await _keys_of(client, cid) and TWINNED not in await _keys_of(client, cid)


async def test_an_option_not_chosen_is_never_offered_at_the_cast(client):
    cid = await _caster(client, 3, "subtle")
    spell = await _spell(client, cid, "Raggio di gelo", 0, attack_save="ATK")
    keys = await _roll_keys(client, cid, "cast", spell_id=spell)
    assert SUBTLE in keys and not set(keys) & {TWINNED, QUICKENED, DISTANT}


# ---------------------------------------------------------------------------
# Costi e regola «una sola opzione per incantesimo»
# ---------------------------------------------------------------------------

async def test_an_option_spends_its_points_and_a_second_one_for_the_same_spell_is_refused_without_paying(client):
    cid = await _caster(client, 10, "subtle", "distant")
    spell = await _spell(client, cid, "Dardo", 1, range_area="36 m", components="V, S")
    r = await _use_spell(client, cid, spell, SUBTLE, DISTANT, slot_level=1)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"
    assert await _points(client, cid) == 10
    r = await _use_spell(client, cid, spell, SUBTLE, slot_level=1)
    assert r.status_code == 200, r.text
    assert await _points(client, cid) == 9 and r.json()["option_result"]["keys"] == [SUBTLE]


async def test_an_option_is_not_offered_without_enough_points(client):
    cid = await _caster(client, 10, "heightened")
    spell = await _spell(client, cid, "Ragnatela", 2, attack_save="DEX")
    await _set_points(client, cid, 2)
    assert HEIGHTENED not in await _roll_keys(client, cid, "cast", spell_id=spell)
    await _set_points(client, cid, 3)
    assert HEIGHTENED in await _roll_keys(client, cid, "cast", spell_id=spell)


# ---------------------------------------------------------------------------
# Incantesimo Celato
# ---------------------------------------------------------------------------

async def test_subtle_spell_says_there_are_no_somatic_or_verbal_components_and_keeps_the_hiding(client, test_session_factory):
    from core.db.models import Character
    cid = await _caster(client, 3, "subtle")
    spell = await _spell(client, cid, "Charme", 1, components="V, S")
    async with test_session_factory() as s:
        char = await s.get(Character, cid)
        char.conditions = {**(char.conditions or {}), "invisible": True}
        char.settings = {**(char.settings or {}), "hiding": {"was_invisible": False}}
        await s.commit()
    r = await _use_spell(client, cid, spell, SUBTLE, slot_level=1)
    assert r.status_code == 200, r.text
    assert "verbal" in r.json()["option_result"]["effects"][0]["en"].lower()
    full = await _full(client, cid)
    assert full["conditions"].get("invisible") is True and "hiding" in full["settings"]


async def test_without_subtle_a_verbal_cast_ends_the_hiding(client, test_session_factory):
    from core.db.models import Character
    cid = await _caster(client, 3, "subtle")
    spell = await _spell(client, cid, "Charme", 1, components="V, S")
    async with test_session_factory() as s:
        char = await s.get(Character, cid)
        char.conditions = {**(char.conditions or {}), "invisible": True}
        char.settings = {**(char.settings or {}), "hiding": {"was_invisible": False}}
        await s.commit()
    assert (await _use_spell(client, cid, spell, slot_level=1)).status_code == 200
    assert "hiding" not in (await _full(client, cid))["settings"]


# ---------------------------------------------------------------------------
# Incantesimo Distante
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("range_area,shown", [("18 m", "36 m"), ("9 m", "18 m"), ("1,5 m", "3 m"), ("Contatto", "9 m"), ("Tocco", "9 m"),
                                              ("150 ft", "300 ft"), ("Touch", "30 ft")])
async def test_distant_spell_doubles_the_range_and_touch_becomes_9_meters(client, range_area, shown):
    cid = await _caster(client, 3, "distant")
    spell = await _spell(client, cid, "Prova", 1, range_area=range_area)
    r = await _use_spell(client, cid, spell, DISTANT, slot_level=1)
    assert r.status_code == 200, r.text
    effect = r.json()["option_result"]["effects"][0]
    assert shown in (effect["it"] if "ft" not in shown else effect["en"])
    assert await _points(client, cid) == 2


@pytest.mark.parametrize("range_area", ["Personale", "Self", None])
async def test_distant_spell_is_not_offered_for_a_self_spell(client, range_area):
    cid = await _caster(client, 3, "distant")
    spell = await _spell(client, cid, "Scudo", 1, range_area=range_area)
    assert DISTANT not in await _roll_keys(client, cid, "cast", spell_id=spell)


# ---------------------------------------------------------------------------
# Incantesimo Esteso
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("duration,shown", [("1 minuto", "2 minuti"), ("10 minuti", "20 minuti"), ("1 ora", "2 ore"),
                                            ("8 ore", "16 ore"), ("12 ore", "24 ore"), ("24 ore", "24 ore")])
async def test_extended_spell_doubles_the_duration_up_to_24_hours(client, duration, shown):
    cid = await _caster(client, 3, "extended")
    spell = await _spell(client, cid, "Prova", 1, duration=duration)
    r = await _use_spell(client, cid, spell, EXTENDED, slot_level=1)
    assert r.status_code == 200, r.text
    assert shown in r.json()["option_result"]["effects"][0]["it"]


@pytest.mark.parametrize("duration", ["Istantaneo", "1 round", "6 round", None])
async def test_extended_spell_is_not_offered_below_one_minute(client, duration):
    cid = await _caster(client, 3, "extended")
    spell = await _spell(client, cid, "Prova", 1, duration=duration)
    assert EXTENDED not in await _roll_keys(client, cid, "cast", spell_id=spell)


async def test_extended_spell_doubles_the_concentration_counter(client):
    cid = await _caster(client, 3, "extended")
    spell = await _spell(client, cid, "Benedizione", 1, duration="Concentrazione, fino a 1 minuto", is_concentration=True)
    r = await _use_spell(client, cid, spell, EXTENDED, slot_level=1)
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["settings"]["concentration_rounds_left"] == 20


async def test_extended_spell_caps_the_concentration_counter_at_24_hours(client):
    cid = await _caster(client, 3, "extended")
    spell = await _spell(client, cid, "Lunga", 1, duration="Concentrazione, fino a 20 ore", is_concentration=True)
    await _use_spell(client, cid, spell, EXTENDED, slot_level=1)
    assert (await _full(client, cid))["settings"]["concentration_rounds_left"] == 24 * 600


# ---------------------------------------------------------------------------
# Incantesimo Intensificato
# ---------------------------------------------------------------------------

async def test_heightened_spell_costs_3_and_marks_one_target_with_disadvantage_on_its_first_save(client):
    cid = await _caster(client, 3, "heightened")
    spell = await _spell(client, cid, "Ragnatela", 2, attack_save="DEX")
    ray = await _spell(client, cid, "Raggio di gelo", 0, attack_save="ATK")
    assert HEIGHTENED in await _roll_keys(client, cid, "cast", spell_id=spell)
    assert HEIGHTENED not in await _roll_keys(client, cid, "cast", spell_id=ray)
    r = await _use_spell(client, cid, spell, HEIGHTENED, slot_level=2)
    assert r.status_code == 200, r.text
    block = r.json()["option_result"]
    assert await _points(client, cid) == 0 and block["targets"] == [HEIGHTENED] and "svantaggio" in block["effects"][0]["it"]
    effect = (await client.get(f"/characters/{cid}/target-effects/{HEIGHTENED}")).json()["result"]
    assert effect["condition"] == "custom:heightened_spell"


# ---------------------------------------------------------------------------
# Incantesimo Preciso
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("charisma,creatures", [(8, 1), (10, 1), (14, 2), (18, 4), (20, 5)])
async def test_careful_spell_spares_as_many_creatures_as_the_charisma_modifier_with_a_minimum_of_one(client, charisma, creatures):
    cid = await _caster(client, 5, "careful", charisma=charisma)
    spell = await _spell(client, cid, "Palla di fuoco", 3, attack_save="DEX")
    ray = await _spell(client, cid, "Raggio di gelo", 0, attack_save="ATK")
    assert CAREFUL not in await _roll_keys(client, cid, "cast", spell_id=ray)
    r = await _use_spell(client, cid, spell, CAREFUL, slot_level=3)
    assert r.status_code == 200, r.text
    assert f"{creatures} " in r.json()["option_result"]["effects"][0]["it"] and await _points(client, cid) == 4


# ---------------------------------------------------------------------------
# Incantesimo Raddoppiato
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,cost", [(0, 1), (1, 1), (2, 2), (3, 3), (5, 5)])
async def test_twinned_spell_costs_the_spell_level_and_one_for_a_cantrip(client, level, cost):
    cid = await _caster(client, 10, "twinned")
    await _set_points(client, cid, 10)
    spell = await _spell(client, cid, "Bersaglio singolo", level, range_area="18 m")
    entry = next(o for o in (await client.get(f"/characters/{cid}/roll-options", params={"roll": "cast", "spell_id": spell})).json()
                 if o["key"] == TWINNED)
    assert entry["cost"]["amount"] == cost
    r = await _use_spell(client, cid, spell, TWINNED, slot_level=max(level, 1))
    assert r.status_code == 200, r.text
    assert await _points(client, cid) == 10 - cost


async def test_twinned_spell_is_not_offered_for_the_spells_that_reach_more_creatures(client):
    cid = await _caster(client, 10, "twinned")
    for name, index in (("Dardo incantato", "magic-missile"), ("Raggio rovente", "scorching-ray")):
        spell = await _spell(client, cid, name, 2, srd_index=index, range_area="36 m")
        assert TWINNED not in await _roll_keys(client, cid, "cast", spell_id=spell)
    ok = await _spell(client, cid, "Raggio di gelo", 0, srd_index="ray-of-frost", range_area="18 m")
    assert TWINNED in await _roll_keys(client, cid, "cast", spell_id=ok)


async def test_twinned_spell_is_not_offered_for_a_self_spell(client):
    cid = await _caster(client, 10, "twinned")
    spell = await _spell(client, cid, "Scudo", 1, range_area="Personale")
    assert TWINNED not in await _roll_keys(client, cid, "cast", spell_id=spell)


async def test_twinned_spell_repeats_the_attack_and_the_damage_for_the_second_creature(client, monkeypatch):
    # il d20 del secondo bersaglio è casuale: fisso un 10 (né 1 né 20) così il danno c'è e i dadi non raddoppiano
    monkeypatch.setattr("random.randint", lambda lo, hi: min(10, hi))
    cid = await _caster(client, 10, "twinned")
    spell = await _spell(client, cid, "Raggio di gelo", 0, attack_save="ATK", damage_dice="2d8", damage_type="cold", range_area="18 m")
    r = await client.post(f"/characters/{cid}/spells/{spell}/attack",
                          json={"die": 12, "cast_options": [TWINNED], "cast_option_inputs": {}})
    assert r.status_code == 200, r.text
    body = r.json()
    second = body["twinned_attack"]
    assert 1 <= second["die"] <= 20 and second["total"] == second["die"] + body["to_hit_bonus"]
    damage = await _damage(client, cid, spell)
    assert len(damage["twinned_damage"]["rolls"]) == len(damage["main_rolls"]) and damage["twinned_damage"]["total"] == sum(damage["twinned_damage"]["rolls"])
    assert "twinned_damage" not in await _damage(client, cid, spell)  # un solo secondo bersaglio per lancio


async def test_twinned_spell_with_a_save_shares_the_damage_roll(client):
    cid = await _caster(client, 10, "twinned")
    spell = await _spell(client, cid, "Fiamma", 1, attack_save="DEX", damage_dice="2d6", damage_type="fire", range_area="18 m")
    assert (await _use_spell(client, cid, spell, TWINNED, slot_level=1)).status_code == 200
    assert not (await _damage(client, cid, spell, casting_level=1)).get("twinned_damage")


# ---------------------------------------------------------------------------
# Incantesimo Rapido
# ---------------------------------------------------------------------------

async def test_quickened_spell_costs_2_and_makes_the_cast_a_bonus_action(client):
    cid = await _caster(client, 3, "quickened")
    spell = await _spell(client, cid, "Charme", 1)
    slow = await _spell(client, cid, "Rituale", 1, casting_time="1 minuto")
    assert QUICKENED in await _roll_keys(client, cid, "cast", spell_id=spell)
    assert QUICKENED not in await _roll_keys(client, cid, "cast", spell_id=slow)
    r = await _use_spell(client, cid, spell, QUICKENED, slot_level=1)
    assert r.status_code == 200, r.text
    turn = await _turn(client, cid)
    assert await _points(client, cid) == 1 and turn["bonus_used"] is True and turn["action_used"] is False
    assert turn["bonus_spell_cast"] is True


async def test_quickened_spell_needs_the_bonus_action_and_is_refused_without_paying(client):
    cid = await _caster(client, 3, "quickened")
    spell = await _spell(client, cid, "Charme", 1)
    assert (await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus", "used": True})).status_code == 200
    assert QUICKENED not in await _roll_keys(client, cid, "cast", spell_id=spell)
    await _new_turn(client, cid)
    assert QUICKENED in await _roll_keys(client, cid, "cast", spell_id=spell)


# ---------------------------------------------------------------------------
# Incantesimo Potenziato
# ---------------------------------------------------------------------------

async def test_empowered_spell_rerolls_up_to_the_charisma_modifier_dice_after_the_damage(client):
    cid = await _caster(client, 3, "empowered", charisma=16)
    spell = await _spell(client, cid, "Dardo", 1, attack_save="DEX", damage_dice="4d6", damage_type="fire")
    first = await _damage(client, cid, spell, casting_level=1, main_rolls=[1, 1, 1, 1])
    assert EMPOWERED in await _roll_keys(client, cid, "spell_damage", spell_id=spell)
    r = await client.post(f"/characters/{cid}/last-damage/options", json={"options": [EMPOWERED], "option_inputs": {}, "reroll": [0, 1, 2]})
    assert r.status_code == 200, r.text
    assert await _points(client, cid) == 2 and r.json()["rolls"][3] == 1 and first["total"] == 4


async def test_empowered_spell_refuses_more_dice_than_the_modifier_and_does_not_pay(client):
    cid = await _caster(client, 3, "empowered", charisma=16)
    spell = await _spell(client, cid, "Dardo", 1, attack_save="DEX", damage_dice="4d6", damage_type="fire")
    await _damage(client, cid, spell, casting_level=1, main_rolls=[1, 1, 1, 1])
    r = await client.post(f"/characters/{cid}/last-damage/options", json={"options": [EMPOWERED], "option_inputs": {}, "reroll": [0, 1, 2, 3]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "bad_reroll" and await _points(client, cid) == 3


@pytest.mark.parametrize("charisma,limit", [(8, 1), (10, 1), (12, 1), (14, 2), (20, 5)])
async def test_empowered_spell_allows_at_least_one_die(client, charisma, limit):
    cid = await _caster(client, 3, "empowered", charisma=charisma)
    spell = await _spell(client, cid, "Dardo", 1, attack_save="DEX", damage_dice="6d6", damage_type="fire")
    await _damage(client, cid, spell, casting_level=1, main_rolls=[1] * 6)
    option = next(o for o in (await client.get(f"/characters/{cid}/roll-options", params={"roll": "spell_damage", "spell_id": spell})).json()
                  if o["key"] == EMPOWERED)
    assert option["phase"] == "after_damage" and option["reroll_limit"] == limit


async def test_empowered_spell_adds_to_another_option_on_the_same_spell(client):
    cid = await _caster(client, 5, "empowered", "careful", charisma=16)
    spell = await _spell(client, cid, "Palla di fuoco", 3, attack_save="DEX", damage_dice="8d6", damage_type="fire")
    assert (await _use_spell(client, cid, spell, CAREFUL, slot_level=3)).status_code == 200
    await _damage(client, cid, spell, casting_level=3, main_rolls=[1] * 8)
    r = await client.post(f"/characters/{cid}/last-damage/options", json={"options": [EMPOWERED], "option_inputs": {}, "reroll": [0]})
    assert r.status_code == 200, r.text
    assert await _points(client, cid) == 5 - 1 - 1


async def test_metamagic_points_come_back_with_a_long_rest(client):
    cid = await _caster(client, 3, "careful")
    spell = await _spell(client, cid, "Palla di fuoco", 2, attack_save="DEX")
    await _use_spell(client, cid, spell, CAREFUL, slot_level=2)
    assert await _points(client, cid) == 2
    await _rest(client, cid, "long")
    assert await _points(client, cid) == 3


async def test_beyond_metamagic_options_find_the_catalog_choices(test_session_factory):
    from api.routers.transfer import _apply_class_options
    from api.services.ddb_import import ImportReport
    from core.rules.sample_characters import build_rules_character

    async with test_session_factory() as s:
        spec = {"name": "x", "edition": "2014", "classes": [("Stregone", 10, "Discendenza Draconica", 6)]}
        char = await build_rules_character(s, spec, 1)
        report = ImportReport()
        _apply_class_options(char, [{"class_index": 0, "name": n} for n in ("Careful Spell", "Twinned Spell", "Quickened Spell", "Mystery")],
                             report, "it")
        assert char.classes[0].options == {"metamagic": ["careful", "twinned", "quickened"]}
        assert [e.name for e in report.approximated] == ["Mystery"]


# ---------------------------------------------------------------------------
# Giro di correzione 1
# ---------------------------------------------------------------------------

async def _cost_offered(client, cid, spell, **params) -> int:
    options = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "cast", "spell_id": spell, **params})).json()
    return next(o for o in options if o["key"] == TWINNED)["cost"]["amount"]


async def test_twinned_spell_costs_the_level_it_is_cast_at_not_the_base_level(client):  # I1, R31
    cid = await _caster(client, 10, "twinned")
    await _set_points(client, cid, 10)
    spell = await _spell(client, cid, "Globo", 1, range_area="18 m")
    assert await _cost_offered(client, cid, spell) == 1 and await _cost_offered(client, cid, spell, casting_level=3) == 3
    assert (await _use_spell(client, cid, spell, TWINNED, slot_level=3)).status_code == 200
    assert await _points(client, cid) == 7


async def test_twinned_spell_with_an_attack_roll_pays_the_cast_level_too(client):  # I1, percorso /attack
    cid = await _caster(client, 10, "twinned")
    await _set_points(client, cid, 10)
    spell = await _spell(client, cid, "Raggio", 1, attack_save="ATK", damage_dice="2d8", damage_type="cold", range_area="18 m")
    r = await client.post(f"/characters/{cid}/spells/{spell}/attack", json={"die": 12, "slot_level": 4, "cast_options": [TWINNED], "cast_option_inputs": {}})
    assert r.status_code == 200, r.text
    assert await _points(client, cid) == 6


async def test_careful_spell_says_the_creatures_pass_the_save_and_still_take_the_half_damage_of_the_2014_rules(client):  # I2
    cid = await _caster(client, 5, "careful")
    spell = await _spell(client, cid, "Palla di fuoco", 3, attack_save="DEX")
    r = await _use_spell(client, cid, spell, CAREFUL, slot_level=3)
    text = r.json()["option_result"]["effects"][0]
    assert "non subiscono" not in text["it"] and "take no damage" not in text["en"]
    assert "superano" in text["it"] and "automatically pass" in text["en"]


async def test_the_sign_of_a_twinned_cast_does_not_survive_a_new_attack_with_the_same_spell(client):  # I7
    cid = await _caster(client, 10, "twinned")
    spell = await _spell(client, cid, "Raggio di gelo", 0, attack_save="ATK", damage_dice="1d8", damage_type="cold", range_area="18 m")
    first = await client.post(f"/characters/{cid}/spells/{spell}/attack", json={"die": 12, "cast_options": [TWINNED], "cast_option_inputs": {}})
    assert first.json()["twinned_attack"] is not None
    points = await _points(client, cid)
    again = await client.post(f"/characters/{cid}/spells/{spell}/attack", json={"die": 12})  # un nuovo lancio, senza l'opzione
    assert again.status_code == 200 and again.json().get("twinned_attack") is None
    assert "twinned_damage" not in await _damage(client, cid, spell) and await _points(client, cid) == points


async def test_a_natural_one_on_the_second_target_gives_it_no_damage_roll_but_the_first_still_has_one(client, monkeypatch):  # I7
    cid = await _caster(client, 10, "twinned")
    spell = await _spell(client, cid, "Raggio di gelo", 0, attack_save="ATK", damage_dice="1d8", damage_type="cold", range_area="18 m")
    monkeypatch.setattr("random.randint", lambda a, b: 1 if b == 20 else a)
    body = (await client.post(f"/characters/{cid}/spells/{spell}/attack", json={"die": 12, "cast_options": [TWINNED], "cast_option_inputs": {}})).json()
    assert body["twinned_attack"]["is_fumble"] is True
    assert body["twinned_attack"]["is_critical"] is False
    damage = await _damage(client, cid, spell)
    assert "twinned_damage" not in damage and damage["main_rolls"]
