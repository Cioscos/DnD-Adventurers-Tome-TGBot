"""Circolo della Luna 2014 (Task 22): cura in forma con uno slot, Forma Selvatica Elementale, Colpo Primordiale, Mille Forme."""
from __future__ import annotations

import asyncio

import pytest

from tests.integration.rules.test_2014_bard import _ability, _full, _spells
from tests.integration.rules.test_2014_druid import _activate, _beast, _druid, _form, _turn

WOLF_BITE = {"name": "Morso", "attack_bonus": 5, "damage_dice": "1d6+3", "damage_type": "piercing"}


async def _active_form(client, cid, hp=40, **statblock) -> int:
    form = await _form(client, cid, {**_beast(0.25), **statblock}, hp=hp)
    r = await _activate(client, cid, form)
    assert r.status_code == 200, r.text
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus", "used": False})
    return form


async def _slots(client, cid) -> dict[int, int]:
    return {s["level"]: s["used"] for s in (await _full(client, cid))["spell_slots"]}


async def _hurt(client, cid, form, amount):
    r = await client.patch(f"/characters/{cid}/companions/{form}/hp", json={"op": "damage", "value": amount})
    assert r.status_code == 200, r.text


async def _heal(client, cid, form, level):
    return await client.post(f"/characters/{cid}/companions/{form}/wild-heal", json={"slot_level": level})


def _fixed(monkeypatch, value=5):
    monkeypatch.setattr("api.routers.companions.random.randint", lambda _a, _b: value)


# ---------------------------------------------------------------------------
# Forma Selvatica da Combattimento: cura la forma con uno slot (azione bonus)
# ---------------------------------------------------------------------------

async def test_combat_wild_shape_is_listed_for_the_moon_from_level_2(client):
    assert await _ability(client, await _druid(client, 1), "druid.combat_wild_shape") is None
    assert (await _ability(client, await _druid(client, 2, "moon"), "druid.combat_wild_shape")) is not None
    assert await _ability(client, await _druid(client, 2, "land"), "druid.combat_wild_shape") is None


async def test_the_heal_rolls_one_d8_per_slot_level_and_heals_the_form_only(client, monkeypatch):
    _fixed(monkeypatch)
    cid = await _druid(client, 4, "moon")
    form = await _active_form(client, cid)
    await _hurt(client, cid, form, 30)
    hp_before = (await _full(client, cid))["current_hit_points"]
    r = await _heal(client, cid, form, 2)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["slot_level"] == 2 and body["rolls"] == [5, 5] and body["healed"] == 10
    assert body["companion"]["current_hp"] == 20  # 40 - 30 + 10
    assert (await _slots(client, cid))[2] == 1 and (await _turn(client, cid)).get("bonus_used") is True
    assert (await _full(client, cid))["current_hit_points"] == hp_before  # la cura è della forma, non del druido


async def test_the_heal_is_capped_at_the_form_maximum(client, monkeypatch):
    _fixed(monkeypatch, 8)
    cid = await _druid(client, 4, "moon")
    form = await _active_form(client, cid, hp=12)
    await _hurt(client, cid, form, 3)
    r = await _heal(client, cid, form, 1)
    assert r.json()["companion"]["current_hp"] == 12 and r.json()["healed"] == 3


async def test_the_heal_needs_an_active_form_a_slot_and_a_free_bonus_action(client, monkeypatch):
    _fixed(monkeypatch)
    cid = await _druid(client, 4, "moon")
    form = await _form(client, cid, _beast(1))
    r = await _heal(client, cid, form, 1)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "form_not_active"
    await _activate(client, cid, form)
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus", "used": False})
    await _hurt(client, cid, form, 5)
    r = await _heal(client, cid, form, 3)  # al 4° livello non ha slot di 3° livello
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_slot"
    assert (await _slots(client, cid)) == {1: 0, 2: 0}
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus", "used": True})
    r = await _heal(client, cid, form, 1)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "turn_slot_used"
    assert (await _slots(client, cid))[1] == 0  # nulla è stato speso
    assert (await _heal(client, cid, form, 0)).status_code == 422


async def test_the_heal_is_refused_to_the_land_and_to_a_regular_companion(client):
    land = await _druid(client, 4, "land")
    form = await _active_form(client, land)
    r = await _heal(client, land, form, 1)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "feature_unavailable"
    moon = await _druid(client, 4, "moon")
    pet = (await client.post(f"/characters/{moon}/companions", json={"kind": "familiar", "name": "Gufo", "max_hp": 5})).json()["id"]
    r = await _heal(client, moon, pet, 1)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "form_not_active"


async def test_a_spent_slot_is_not_spent_twice_by_two_requests_at_once(client, monkeypatch):
    _fixed(monkeypatch)
    cid = await _druid(client, 2, "moon")  # tre slot di 1° livello, uno solo ancora libero
    form = await _active_form(client, cid)
    await _hurt(client, cid, form, 20)
    for slot in (await _full(client, cid))["spell_slots"]:
        await client.patch(f"/characters/{cid}/spell_slots/{slot['id']}", json={"used": slot["total"] - 1})
    first, second = await asyncio.gather(_heal(client, cid, form, 1), _heal(client, cid, form, 1))
    assert sorted([first.status_code, second.status_code]) == [200, 409]
    assert (await _slots(client, cid))[1] == 3  # tutti spesi, mai oltre il totale


# ---------------------------------------------------------------------------
# Forma Selvatica Elementale: due usi, un elementale
# ---------------------------------------------------------------------------

async def _elemental(client, cid, index="fire-elemental", cr=5, kind="elemental"):
    r = await client.post(f"/characters/{cid}/companions", json={
        "kind": "wild_shape", "name": "Elementale", "srd_index": index, "max_hp": 102, "armor_class": 13,
        "statblock": _beast(cr, swim=90 if "water" in (index or "") else 0, fly=90 if "air" in (index or "") else 0, kind=kind)})
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.mark.parametrize("index", ["air-elemental", "earth-elemental", "fire-elemental", "water-elemental"])
async def test_the_moon_at_10_becomes_an_elemental_for_two_uses_and_a_bonus_action(client, index):
    cid = await _druid(client, 10, "moon")
    form = await _elemental(client, cid, index)
    r = await _activate(client, cid, form)
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, "druid.wild_shape"))["uses"] == 0  # costa tutti e due gli usi
    turn = await _turn(client, cid)
    assert turn.get("bonus_used") is True and not turn.get("action_used")


async def test_the_elemental_shape_needs_two_uses_and_never_spends_one_when_refused(client):
    cid = await _druid(client, 10, "moon")
    plain = await _form(client, cid, _beast(3))
    await _activate(client, cid, plain)  # un uso
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus", "used": False})
    form = await _elemental(client, cid)
    r = await _activate(client, cid, form)
    assert r.status_code == 409 and r.json()["detail"] == "no_wild_shape_uses"
    assert (await _ability(client, cid, "druid.wild_shape"))["uses"] == 1
    assert (await _activate(client, cid, form, force=True)).status_code == 200  # il giocatore può forzare
    assert (await _ability(client, cid, "druid.wild_shape"))["uses"] == 0


async def test_an_elemental_ignores_the_beast_limits_of_the_table(client):
    cid = await _druid(client, 10, "moon")
    form = await _elemental(client, cid, "water-elemental", cr=5)  # GS 5 con nuoto: oltre il GS 3 della Luna a 10°
    assert (await _activate(client, cid, form)).status_code == 200


@pytest.mark.parametrize("level,circle", [(9, "moon"), (10, "land"), (20, "land")])
async def test_the_elemental_shape_is_for_the_moon_from_level_10(client, level, circle):
    cid = await _druid(client, level, circle)
    r = await _activate(client, cid, await _elemental(client, cid))
    assert r.status_code == 409 and r.json()["detail"]["reasons"] == ["no_elemental_shape"]
    assert (await _ability(client, cid, "druid.wild_shape"))["uses"] in (2, None)


async def test_only_the_four_elementals_and_a_custom_elemental_qualify(client):
    cid = await _druid(client, 10, "moon")
    r = await _activate(client, cid, await _elemental(client, cid, "invisible-stalker"))
    assert r.status_code == 409 and r.json()["detail"]["reasons"] == ["not_elemental_form"]
    custom = await _elemental(client, cid, None)  # statblock scritto a mano, di tipo elementale
    assert (await _activate(client, cid, custom)).status_code == 200


async def test_the_archdruid_moon_changes_into_elementals_without_spending(client):
    cid = await _druid(client, 20, "moon")
    assert (await _activate(client, cid, await _elemental(client, cid))).status_code == 200
    assert (await _ability(client, cid, "druid.wild_shape"))["max_uses"] is None


async def test_the_elemental_shape_row_is_listed_for_the_moon_at_level_10(client):
    assert await _ability(client, await _druid(client, 9, "moon"), "druid.elemental_wild_shape") is None
    assert await _ability(client, await _druid(client, 10, "moon"), "druid.elemental_wild_shape") is not None


# ---------------------------------------------------------------------------
# Colpo Primordiale: gli attacchi in forma sono magici
# ---------------------------------------------------------------------------

async def _bite(client, cid, form):
    r = await client.post(f"/characters/{cid}/companions/{form}/attack", json={"action_index": 0, "dice": [12]})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("level,circle,magical", [(6, "moon", True), (5, "moon", False), (6, "land", False), (14, "moon", True)])
async def test_primal_strike_makes_the_attacks_in_beast_form_magical(client, level, circle, magical):
    cid = await _druid(client, level, circle)
    form = await _active_form(client, cid, actions=[WOLF_BITE])
    assert (await _bite(client, cid, form))["is_magical"] is magical


async def test_a_companion_that_is_not_a_beast_form_never_attacks_magically(client):
    cid = await _druid(client, 6, "moon")
    pet = (await client.post(f"/characters/{cid}/companions", json={
        "kind": "familiar", "name": "Gufo", "max_hp": 5, "statblock": {"actions": [WOLF_BITE]}})).json()["id"]
    assert (await _bite(client, cid, pet))["is_magical"] is False


async def test_a_deactivated_form_does_not_attack_magically(client):
    cid = await _druid(client, 6, "moon")
    form = await _active_form(client, cid, actions=[WOLF_BITE])
    await client.post(f"/characters/{cid}/companions/{form}/deactivate")
    assert (await _bite(client, cid, form))["is_magical"] is False


# ---------------------------------------------------------------------------
# Mille Forme: alterare se stessi a volontà
# ---------------------------------------------------------------------------

async def _alter_self(client, cid) -> dict:
    return next(s for s in (await _spells(client, cid)).values() if s["srd_index"] == "alter-self")


async def test_thousand_forms_grants_alter_self_at_will_from_level_14(client):
    spell = await _alter_self(client, await _druid(client, 14, "moon"))
    assert spell["always_prepared"] and spell["is_prepared"] and spell["at_will"] is True
    assert all(s["srd_index"] != "alter-self" for s in (await _spells(client, await _druid(client, 13, "moon"))).values())
    assert all(s["srd_index"] != "alter-self" for s in (await _spells(client, await _druid(client, 14, "land"))).values())


async def test_other_spells_are_not_at_will(client):
    cid = await _druid(client, 14, "moon")
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Dardo", "level": 0})
    assert r.status_code == 201
    assert all(s["at_will"] is False for s in (await _spells(client, cid)).values() if s["srd_index"] != "alter-self")


async def test_alter_self_is_cast_without_a_slot_any_number_of_times(client):
    cid = await _druid(client, 14, "moon")
    spell = await _alter_self(client, cid)
    before = await _slots(client, cid)
    for _ in range(3):
        r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"free_cast": True})
        assert r.status_code == 200, r.text
        assert await _slots(client, cid) == before
        assert (await _turn(client, cid))["action_used"] is True
        await client.post(f"/characters/{cid}/turn/new")


async def test_the_free_cast_still_costs_the_action(client):
    cid = await _druid(client, 14, "moon")
    spell = await _alter_self(client, cid)
    assert (await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"free_cast": True})).status_code == 200
    again = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"free_cast": True})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"
