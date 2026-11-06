"""Scuola di Divinazione e di Evocazione 2014 (Task 30): Portento, Divinazione Esperta, Terzo Occhio; Evocazione Minore,
Trasposizione Benevola, Evocazione Focalizzata, Evocazioni Perduranti."""
from __future__ import annotations

import random

import pytest

from tests.integration.rules.test_2014_bard import _ability, _full, _roll_keys, _use
from tests.integration.rules.test_2014_fighter_eldritch_knight import _cast, _spell
from tests.integration.rules.test_2014_paladin import _rest
from tests.integration.rules.test_2014_wizard import _spend, _used, _wizard

PORTENT, THIRD_EYE = "wizard.portent", "wizard.third_eye"
EXPERT = "wizard.expert_divination"
MINOR, TRANSPOSITION, FOCUSED = "wizard.minor_conjuration", "wizard.benign_transposition", "wizard.focused_conjuration"


async def _turn(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]


async def _states(client, cid) -> dict[str, dict]:
    return {s["key"]: s for s in (await _full(client, cid))["active_states"] or []}


def _saved(full: dict) -> list[int]:
    return (full["settings"].get("saved_dice") or {}).get(PORTENT, [])


# ---------------------------------------------------------------------------
# Portento
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,dice", [(2, 2), (13, 2), (14, 3), (20, 3)])
async def test_a_long_rest_rolls_two_d20_and_three_from_level_14(client, monkeypatch, level, dice):
    cid = await _wizard(client, level, "divination")
    assert _saved(await _full(client, cid)) == []  # prima del riposo lungo non c'è nulla
    monkeypatch.setattr(random, "randint", lambda a, b: 13 if b == 20 else a)
    await _rest(client, cid, "long")
    assert _saved(await _full(client, cid)) == [13] * dice


async def test_a_short_rest_keeps_the_dice_and_the_next_long_rest_replaces_them(client, monkeypatch):
    cid = await _wizard(client, 6, "divination")
    monkeypatch.setattr(random, "randint", lambda a, b: 7 if b == 20 else a)
    await _rest(client, cid, "long")
    monkeypatch.setattr(random, "randint", lambda a, b: 19 if b == 20 else a)
    await _rest(client, cid, "short")
    assert _saved(await _full(client, cid)) == [7, 7]
    await _rest(client, cid, "long")
    assert _saved(await _full(client, cid)) == [19, 19]  # i dadi non usati si perdono


async def test_portent_belongs_to_the_diviner_from_level_2(client, monkeypatch):
    monkeypatch.setattr(random, "randint", lambda a, b: 13 if b == 20 else a)
    for level, school in ((1, None), (6, "evocation")):
        cid = await _wizard(client, level, school)
        await _rest(client, cid, "long")
        assert _saved(await _full(client, cid)) == [] and await _ability(client, cid, PORTENT) is None
    assert await _ability(client, await _wizard(client, 2, "divination"), PORTENT) is not None


@pytest.mark.parametrize("roll,query", [("attack", {}), ("save", {"ability": "dexterity"}), ("skill", {"skill": "arcana"}),
                                         ("initiative", {}), ("ability", {"ability": "intelligence"}), ("death_save", {})])
async def test_portent_is_offered_on_attacks_saves_and_checks_with_the_saved_dice(client, monkeypatch, roll, query):
    cid = await _wizard(client, 6, "divination")
    assert PORTENT not in await _roll_keys(client, cid, roll, **query)  # nessun dado salvato
    monkeypatch.setattr(random, "randint", lambda a, b: 17 if b == 20 else a)
    await _rest(client, cid, "long")
    options = (await client.get(f"/characters/{cid}/roll-options", params={"roll": roll, **query})).json()
    portent = next(o for o in options if o["key"] == PORTENT)
    assert portent["saved_dice"] == [17, 17] and portent["once_per_turn"] is True and portent["phase"] == "before"


async def test_portent_replaces_the_d20_consumes_the_die_and_works_once_per_turn(client, monkeypatch):
    cid = await _wizard(client, 6, "divination")
    monkeypatch.setattr(random, "randint", lambda a, b: 17 if b == 20 else a)
    await _rest(client, cid, "long")
    url = f"/characters/{cid}/skills/arcana/roll"
    wrong = await client.post(url, json={"die": 2, "options": [PORTENT], "option_inputs": {PORTENT: {"die": 9}}})
    assert wrong.status_code == 409  # non è fra i dadi salvati
    r = await client.post(url, json={"die": 2, "mode": "normal", "options": [PORTENT], "option_inputs": {PORTENT: {"die": 17}}})
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 17 and r.json()["total"] == 17 + r.json()["bonus"]
    assert _saved(await _full(client, cid)) == [17]
    assert PORTENT not in await _roll_keys(client, cid, "skill", skill="arcana")  # una sola sostituzione per turno
    await client.post(f"/characters/{cid}/turn/new")
    assert PORTENT in await _roll_keys(client, cid, "skill", skill="arcana")


# ---------------------------------------------------------------------------
# Divinazione Esperta
# ---------------------------------------------------------------------------

async def _divination(client, cid, level, name="Scrutare", **extra) -> int:
    return await _spell(client, cid, name, level, school="divination", casting_time="1 azione", **extra)


async def test_expert_divination_offers_the_spent_slots_below_the_spell(client):
    cid = await _wizard(client, 6, "divination")
    spell = await _divination(client, cid, 2)
    await _spend(client, cid, l1=2)
    query = {"spell_id": spell, "casting_level": 2}
    options = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "cast", **query})).json()
    found = next(o for o in options if o["key"] == EXPERT)
    assert found["requires_input"] == "recover" and [c["level"] for c in found["input_options"]] == [1]
    assert found["input_options"][0]["available"] == 2  # slot spesi di quel livello
    assert EXPERT not in await _roll_keys(client, cid, "cast", spell_id=spell, casting_level=1)  # un 1° livello non lo apre


async def test_expert_divination_is_not_offered_without_a_spent_lower_slot_or_for_other_schools(client):
    cid = await _wizard(client, 6, "divination")
    spell = await _divination(client, cid, 2)
    assert EXPERT not in await _roll_keys(client, cid, "cast", spell_id=spell, casting_level=2)  # niente di speso
    await _spend(client, cid, l2=1)
    assert EXPERT not in await _roll_keys(client, cid, "cast", spell_id=spell, casting_level=2)  # il 2° non è inferiore
    other = await _spell(client, cid, "Sonno", 2, school="enchantment", casting_time="1 azione")
    await _spend(client, cid, l1=1)
    assert EXPERT not in await _roll_keys(client, cid, "cast", spell_id=other, casting_level=2)
    low = await _wizard(client, 5, "divination")
    await _spend(client, low, l1=1)
    assert EXPERT not in await _roll_keys(client, low, "cast", spell_id=await _divination(client, low, 2), casting_level=2)


async def test_expert_divination_returns_the_chosen_slot_after_the_cast(client):
    cid = await _wizard(client, 6, "divination")
    spell = await _divination(client, cid, 3, "Chiaroveggenza")
    await _spend(client, cid, l1=3, l2=2)
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={
        "slot_level": 3, "options": [EXPERT], "option_inputs": {EXPERT: {"slot_level": 2}}})
    assert r.status_code == 200, r.text
    used = await _used(client, cid)
    assert (used[1], used[2], used[3]) == (3, 1, 1)  # un 2° recuperato, un 3° speso dal lancio


async def test_expert_divination_refuses_a_slot_that_is_not_lower_or_not_spent_and_changes_nothing(client):
    cid = await _wizard(client, 6, "divination")
    spell = await _divination(client, cid, 2)
    await _spend(client, cid, l1=1, l2=1)
    for bad in (2, 3, 4):
        r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={
            "slot_level": 2, "options": [EXPERT], "option_inputs": {EXPERT: {"slot_level": bad}}})
        assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"
    used = await _used(client, cid)
    assert (used[1], used[2]) == (1, 1)  # il lancio rifiutato non ha speso nulla


async def test_expert_divination_never_returns_a_slot_above_the_fifth(client):
    cid = await _wizard(client, 20, "divination")
    spell = await _divination(client, cid, 9, "Presagio")
    await _spend(client, cid, l6=1, l5=1, l9=0)
    options = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "cast", "spell_id": spell, "casting_level": 9})).json()
    found = next(o for o in options if o["key"] == EXPERT)
    assert [c["level"] for c in found["input_options"]] == [5]


# ---------------------------------------------------------------------------
# Terzo Occhio
# ---------------------------------------------------------------------------

THIRD_OPTIONS = {"greater_comprehension", "darkvision", "see_invisibility", "ethereal_sight"}


async def test_the_third_eye_is_an_action_with_one_use_back_on_a_short_rest(client):
    assert await _ability(client, await _wizard(client, 9, "divination"), THIRD_EYE) is None
    cid = await _wizard(client, 10, "divination")
    row = await _ability(client, cid, THIRD_EYE)
    assert (row["max_uses"], row["restoration_type"], row["has_on_use"]) == (1, "short_rest", True)
    assert {o["key"] for o in next(c for c in row["use_choices"] if c["key"] == "option")["options"]} == THIRD_OPTIONS
    assert (await _use(client, cid, THIRD_EYE, params={"option": "mud"})).status_code == 422
    assert (await _use(client, cid, THIRD_EYE, params={"option": "darkvision"})).status_code == 200
    assert (await _turn(client, cid))["action_used"] is True
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid, THIRD_EYE, params={"option": "darkvision"})).status_code == 409
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, THIRD_EYE))["uses"] == 1


@pytest.mark.parametrize("option,sense,feet", [("darkvision", "darkvision", 60), ("see_invisibility", "see_invisible", 10),
                                               ("ethereal_sight", "ethereal_sight", 60)])
async def test_each_sense_option_adds_its_sense_while_the_third_eye_lasts(client, option, sense, feet):
    cid = await _wizard(client, 10, "divination")
    before = (await _full(client, cid))["computed"]["senses"]
    assert not any(s["type"] == sense and s["range_ft"] == feet for s in before)
    await _use(client, cid, THIRD_EYE, params={"option": option})
    assert {"type": sense, "range_ft": feet} in (await _full(client, cid))["computed"]["senses"]
    assert (await _states(client, cid))["third_eye"]["data"]["option"] == option


async def test_greater_comprehension_is_a_state_without_a_sense(client):
    cid = await _wizard(client, 10, "divination")
    senses = (await _full(client, cid))["computed"]["senses"]
    await _use(client, cid, THIRD_EYE, params={"option": "greater_comprehension"})
    assert (await _full(client, cid))["computed"]["senses"] == senses
    assert (await _states(client, cid))["third_eye"]["data"]["option"] == "greater_comprehension"


@pytest.mark.parametrize("ending", ["short", "long"])
async def test_the_third_eye_ends_with_a_rest(client, ending):
    cid = await _wizard(client, 10, "divination")
    await _use(client, cid, THIRD_EYE, params={"option": "darkvision"})
    await _rest(client, cid, ending)
    assert "third_eye" not in await _states(client, cid)
    assert not any(s["type"] == "darkvision" and s["range_ft"] == 60 for s in (await _full(client, cid))["computed"]["senses"])


async def test_the_third_eye_ends_when_the_wizard_is_incapacitated(client):
    cid = await _wizard(client, 10, "divination")
    await _use(client, cid, THIRD_EYE, params={"option": "darkvision"})
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"incapacitated": True}})
    assert r.status_code == 200, r.text
    assert "third_eye" not in await _states(client, cid)


# ---------------------------------------------------------------------------
# Evocazione Minore
# ---------------------------------------------------------------------------

async def test_minor_conjuration_makes_an_object_for_an_hour_and_a_new_one_replaces_it(client):
    cid = await _wizard(client, 2, "conjuration")
    row = await _ability(client, cid, MINOR)
    assert row["has_on_use"] is True and {t["key"] for t in row["use_texts"]} == {"object"}
    assert (await _use(client, cid, MINOR)).status_code == 422  # serve il nome dell'oggetto
    r = await _use(client, cid, MINOR, params={"object": "Chiave di ferro"})
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["action_used"] is True
    state = (await _states(client, cid))["minor_conjuration"]
    assert state["rounds_left"] == 600 and state["data"]["object"] == "Chiave di ferro"
    await client.post(f"/characters/{cid}/turn/new")
    await _use(client, cid, MINOR, params={"object": "Candela"})
    states = [s for s in (await _full(client, cid))["active_states"] if s["key"] == "minor_conjuration"]
    assert len(states) == 1 and states[0]["data"]["object"] == "Candela"


async def test_minor_conjuration_is_the_conjurers(client):
    assert await _ability(client, await _wizard(client, 5, "evocation"), MINOR) is None


# ---------------------------------------------------------------------------
# Trasposizione Benevola
# ---------------------------------------------------------------------------

async def test_benign_transposition_is_an_action_back_with_a_long_rest(client):
    assert await _ability(client, await _wizard(client, 5, "conjuration"), TRANSPOSITION) is None
    cid = await _wizard(client, 6, "conjuration")
    row = await _ability(client, cid, TRANSPOSITION)
    assert (row["max_uses"], row["restoration_type"], row["has_on_use"]) == (1, "long_rest", True)
    assert (await _use(client, cid, TRANSPOSITION)).status_code == 200
    assert (await _turn(client, cid))["action_used"] is True and (await _ability(client, cid, TRANSPOSITION))["uses"] == 0
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid, TRANSPOSITION)).status_code == 409
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, TRANSPOSITION))["uses"] == 0
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, TRANSPOSITION))["uses"] == 1


@pytest.mark.parametrize("school,level,returns", [("conjuration", 1, True), ("conjuration", 0, False), ("evocation", 1, False),
                                                  ("conjuration", 3, True)])
async def test_a_conjuration_of_first_level_or_higher_recharges_the_transposition(client, school, level, returns):
    cid = await _wizard(client, 6, "conjuration")
    await _use(client, cid, TRANSPOSITION)
    await client.post(f"/characters/{cid}/turn/new")
    spell = await _spell(client, cid, "Prova", level, school=school, casting_time="1 azione")
    assert (await _cast(client, cid, spell, slot_level=max(1, level))).status_code == 200
    assert (await _ability(client, cid, TRANSPOSITION))["uses"] == (1 if returns else 0)


# ---------------------------------------------------------------------------
# Evocazione Focalizzata
# ---------------------------------------------------------------------------

async def _concentrating(client, cid, school) -> None:
    spell = await _spell(client, cid, "Nube", 2, school=school, is_concentration=True, casting_time="1 azione",
                         duration="Concentrazione, fino a 1 minuto")
    assert (await _cast(client, cid, spell, slot_level=2)).status_code == 200
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 100})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 100})


async def test_focused_conjuration_keeps_the_concentration_on_a_conjuration(client):
    cid = await _wizard(client, 10, "conjuration")
    await _concentrating(client, cid, "conjuration")
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 30})
    assert r.json().get("concentration_save") is None and r.json()["concentrating_spell_id"] is not None


async def test_focused_conjuration_does_not_cover_other_schools_or_lower_levels(client):
    cid = await _wizard(client, 10, "conjuration")
    await _concentrating(client, cid, "enchantment")
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 5})).json()["concentration_save"] is not None
    low = await _wizard(client, 9, "conjuration")
    await _concentrating(client, low, "conjuration")
    assert (await client.patch(f"/characters/{low}/hp", json={"op": "damage", "value": 5})).json()["concentration_save"] is not None


async def test_focused_conjuration_still_loses_the_concentration_at_zero_hp(client):
    cid = await _wizard(client, 10, "conjuration")
    await _concentrating(client, cid, "conjuration")
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 100})
    assert r.json()["current_hit_points"] == 0 and r.json()["concentrating_spell_id"] is None


# ---------------------------------------------------------------------------
# Evocazioni Perduranti
# ---------------------------------------------------------------------------

async def _summon(client, cid, **extra):
    body = {"kind": "summon", "name": "Elementale", "max_hp": 40, **extra}
    return await client.post(f"/characters/{cid}/companions", json=body)


async def test_a_conjured_summon_gets_30_temporary_hit_points_from_level_14(client):
    cid = await _wizard(client, 14, "conjuration")
    r = await _summon(client, cid, spell_school="conjuration")
    assert r.status_code == 201, r.text
    assert r.json()["temp_hp"] == 30


@pytest.mark.parametrize("level,school,extra,expected", [
    (13, "conjuration", {}, 0), (14, "necromancy", {}, 0), (14, None, {}, 0), (14, "conjuration", {"temp_hp": 50}, 50),
    (14, "conjuration", {"temp_hp": 10}, 30)])
async def test_durable_summons_only_help_conjured_summons_of_a_conjurer_of_level_14(client, level, school, extra, expected):
    cid = await _wizard(client, level, "conjuration")
    r = await _summon(client, cid, **({"spell_school": school} if school else {}), **extra)
    assert r.status_code == 201, r.text
    assert r.json()["temp_hp"] == expected  # i PF temporanei non si sommano: vale il maggiore


async def test_only_the_conjurer_has_durable_summons(client):
    r = await _summon(client, await _wizard(client, 14, "necromancy"), spell_school="conjuration")
    assert r.json()["temp_hp"] == 0
