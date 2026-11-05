"""Druido 2014, giro di correzione 1: chiusura della forma (0 PF, riposi, ritorno volontario) e cura in forma."""
from __future__ import annotations

import pytest

from tests.integration.rules.test_2014_bard import _full
from tests.integration.rules.test_2014_druid import _activate, _beast, _druid, _form, _turn


async def _in_form(client, cid, hp=10, cr=0.25) -> int:
    form = await _form(client, cid, _beast(cr), hp=hp)
    r = await _activate(client, cid, form)
    assert r.status_code == 200, r.text
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "action", "used": False})
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus", "used": False})
    return form


async def _hp(client, cid) -> int:
    return (await _full(client, cid))["current_hit_points"]


# ---------------------------------------------------------------------------
# I1: la forma a 0 PF si chiude dalla sua scheda e l'eccesso passa al personaggio, come da PATCH /hp
# ---------------------------------------------------------------------------

async def test_damage_from_the_form_sheet_ends_it_and_carries_the_excess(client):
    cid = await _druid(client, 4)
    before = await _hp(client, cid)
    form = await _in_form(client, cid, hp=10)
    r = await client.patch(f"/characters/{cid}/companions/{form}/hp", json={"op": "damage", "value": 13})
    assert r.status_code == 200, r.text
    assert r.json()["current_hp"] == 0 and r.json()["is_active"] is False
    full = await _full(client, cid)
    assert full["active_form"] is None and full["current_hit_points"] == before - 3


async def test_the_form_sheet_and_the_hp_endpoint_give_the_same_outcome(client):
    a, b = await _druid(client, 4), await _druid(client, 4)
    fa, fb = await _in_form(client, a, hp=10), await _in_form(client, b, hp=10)
    await client.patch(f"/characters/{a}/companions/{fa}/hp", json={"op": "damage", "value": 15})
    await client.patch(f"/characters/{b}/hp", json={"op": "damage", "value": 15})
    assert await _hp(client, a) == await _hp(client, b)
    assert (await _full(client, a))["active_form"] is None and (await _full(client, b))["active_form"] is None


async def test_exactly_the_form_hp_ends_it_without_touching_the_character(client):
    cid = await _druid(client, 4)
    before = await _hp(client, cid)
    form = await _in_form(client, cid, hp=10)
    r = await client.patch(f"/characters/{cid}/companions/{form}/hp", json={"op": "damage", "value": 10})
    assert r.json()["is_active"] is False
    full = await _full(client, cid)
    assert full["active_form"] is None and full["current_hit_points"] == before


async def test_damage_below_zero_keeps_the_form(client):
    cid = await _druid(client, 4)
    form = await _in_form(client, cid, hp=10)
    r = await client.patch(f"/characters/{cid}/companions/{form}/hp", json={"op": "damage", "value": 4})
    assert r.json()["current_hp"] == 6 and r.json()["is_active"] is True


async def test_setting_the_active_form_to_zero_by_hand_closes_it(client):
    cid = await _druid(client, 4)
    form = await _in_form(client, cid, hp=10)
    r = await client.patch(f"/characters/{cid}/companions/{form}", json={"current_hp": 0})
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert (await _full(client, cid))["active_form"] is None


# ---------------------------------------------------------------------------
# I2: la durata decide se un riposo chiude la forma
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,circle,ended", [(2, "land", True), (3, "land", True), (4, "land", False),
                                                  (6, "moon", False), (12, "land", False)])
async def test_a_short_rest_only_ends_forms_lasting_an_hour_or_less(client, level, circle, ended):
    cid = await _druid(client, level, circle)
    await _in_form(client, cid)
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})).status_code == 200
    assert ((await _full(client, cid))["active_form"] is None) is ended


@pytest.mark.parametrize("level,circle,ended", [(4, "land", True), (6, "moon", True), (16, "land", True),
                                                  (18, "land", False), (20, "moon", False)])
async def test_a_long_rest_only_ends_forms_lasting_eight_hours_or_less(client, level, circle, ended):
    cid = await _druid(client, level, circle)
    await _in_form(client, cid)
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})).status_code == 200
    assert ((await _full(client, cid))["active_form"] is None) is ended


async def test_the_form_state_carries_no_fixed_rest_tokens(client):
    cid = await _druid(client, 6)
    await _in_form(client, cid)
    state = next(s for s in (await _full(client, cid))["active_states"] if s["key"] == "wild_shape")
    assert not {"rest_short", "rest_long"} & set(state["ends_on"])


# ---------------------------------------------------------------------------
# I5: tornare normali costa l'azione bonus da ogni percorso (2014), con rifiuto chiaro se è già spesa
# ---------------------------------------------------------------------------

async def test_ending_the_form_from_the_turn_bar_costs_the_bonus_action(client):
    cid = await _druid(client, 14, "moon")
    await _in_form(client, cid, cr=1)
    assert (await _turn(client, cid)).get("bonus_used") is not True
    r = await client.delete(f"/characters/{cid}/active-states/wild_shape")
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["active_form"] is None
    assert (await _turn(client, cid))["bonus_used"] is True


async def test_ending_the_form_with_the_bonus_action_spent_is_refused_and_keeps_the_form(client):
    cid = await _druid(client, 4)
    form = await _in_form(client, cid)
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus", "used": True})
    for call in (client.post(f"/characters/{cid}/companions/{form}/deactivate"),
                 client.delete(f"/characters/{cid}/active-states/wild_shape")):
        r = await call
        assert r.status_code == 409 and r.json()["detail"]["code"] == "turn_slot_used", r.text
    assert (await _full(client, cid))["active_form"] is not None


async def test_the_deactivate_button_and_the_turn_bar_cost_the_same(client):
    a, b = await _druid(client, 4), await _druid(client, 4)
    fa = await _in_form(client, a)
    await _in_form(client, b)
    await client.post(f"/characters/{a}/companions/{fa}/deactivate")
    await client.delete(f"/characters/{b}/active-states/wild_shape")
    assert (await _turn(client, a))["bonus_used"] is True and (await _turn(client, b))["bonus_used"] is True


async def test_in_2024_returning_to_normal_form_costs_nothing(client):
    cid = await _druid(client, 5)
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    form = await _in_form(client, cid)
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus", "used": False})
    assert (await client.delete(f"/characters/{cid}/active-states/wild_shape")).status_code == 200
    assert (await _turn(client, cid)).get("bonus_used") is not True
    assert form


# ---------------------------------------------------------------------------
# M1, M2, M3
# ---------------------------------------------------------------------------

async def test_the_heal_trusts_the_active_state_not_the_flag(client):
    cid = await _druid(client, 4, "moon")
    form = await _in_form(client, cid, hp=40)
    await client.patch(f"/characters/{cid}/companions/{form}/hp", json={"op": "damage", "value": 10})
    assert (await client.request("DELETE", f"/characters/{cid}/active-states/wild_shape")).status_code == 200
    r = await client.post(f"/characters/{cid}/companions/{form}/wild-heal", json={"slot_level": 1})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "form_not_active"
    assert {s["level"]: s["used"] for s in (await _full(client, cid))["spell_slots"]}[1] == 0


async def test_activating_the_form_while_stunned_is_refused_without_spending(client):
    cid = await _druid(client, 4)
    form = await _form(client, cid)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"stunned": True}})
    r = await _activate(client, cid, form)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "incapacitated"
    assert (await _turn(client, cid)).get("action_used") is not True


async def test_the_heal_at_full_hp_is_refused_without_spending(client):
    cid = await _druid(client, 4, "moon")
    form = await _in_form(client, cid, hp=40)
    r = await client.post(f"/characters/{cid}/companions/{form}/wild-heal", json={"slot_level": 1})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "form_full_hp"
    assert {s["level"]: s["used"] for s in (await _full(client, cid))["spell_slots"]}[1] == 0
    assert (await _turn(client, cid)).get("bonus_used") is not True


# ---------------------------------------------------------------------------
# I3: competenze e TS della bestia arrivano ai tiri (vale il più alto), solo nel 2014 e solo se salvate con la forma
# ---------------------------------------------------------------------------

WOLF = {**_beast(0.25), "abilities": {"str": 12, "dex": 15, "con": 12, "int": 3, "wis": 12, "cha": 6},
        "skills": {"perception": 3, "stealth": 4}, "saves": {"con": 6}}


async def _wolf(client, cid, **extra) -> None:
    form = await _form(client, cid, {**WOLF, **extra})
    r = await _activate(client, cid, form)
    assert r.status_code == 200, r.text


async def _skill_bonus(client, cid, skill) -> int:
    r = await client.post(f"/characters/{cid}/skills/{skill}/roll", json={})
    assert r.status_code == 200, r.text
    return r.json()["bonus"]


async def _save_bonus(client, cid, ability) -> int:
    r = await client.post(f"/characters/{cid}/saving_throws/{ability}/roll", json={})
    assert r.status_code == 200, r.text
    return r.json()["bonus"]


async def test_the_beast_skill_proficiencies_reach_the_rolls_when_higher(client):
    cid = await _druid(client, 2)  # competenza +2, Destrezza e Saggezza 10
    assert await _skill_bonus(client, cid, "stealth") == 0
    await _wolf(client, cid)
    assert await _skill_bonus(client, cid, "stealth") == 4  # Destrezza +2 e competenza +2, uguale alla bestia
    assert await _skill_bonus(client, cid, "perception") == 3  # competenza +2 e Saggezza 0 = 2: vale la bestia
    assert (await _full(client, cid))["skill_bonuses"]["perception"] == 3  # la scheda mostra lo stesso numero


async def test_the_druid_keeps_his_own_bonus_when_it_is_higher(client):
    cid = await _druid(client, 2, wisdom=18)
    await _wolf(client, cid)
    assert await _skill_bonus(client, cid, "perception") == 4 + 2  # Saggezza +4 più la competenza che acquisisce
    assert await _skill_bonus(client, cid, "athletics") == 1  # nessuna competenza: Forza 12 della bestia


async def test_a_skill_the_beast_lacks_stays_untouched(client):
    cid = await _druid(client, 2)
    base = await _skill_bonus(client, cid, "arcana")
    await _wolf(client, cid)
    assert await _skill_bonus(client, cid, "arcana") == base


async def test_the_beast_saving_throw_proficiency_reaches_the_roll(client):
    cid = await _druid(client, 2)
    assert await _save_bonus(client, cid, "constitution") == 0
    await _wolf(client, cid)
    assert await _save_bonus(client, cid, "constitution") == 6
    assert await _save_bonus(client, cid, "wisdom") == 0 + 2  # il TS di Saggezza del druido non cambia


async def test_the_proficiencies_end_with_the_form(client):
    cid = await _druid(client, 2)
    await _wolf(client, cid)
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus", "used": False})
    assert (await client.delete(f"/characters/{cid}/active-states/wild_shape")).status_code == 200
    assert await _skill_bonus(client, cid, "stealth") == 0 and await _save_bonus(client, cid, "constitution") == 0


@pytest.mark.parametrize("extra", [{"skills": None, "saves": "rotto"}, {"skills": {"stealth": "alto", "volo": 9}, "saves": {"xyz": 3}},
                                   {"skills": [1, 2], "saves": {"con": None}}])
async def test_a_form_saved_without_skills_or_saves_uses_the_normal_calculation(client, extra):
    cid = await _druid(client, 2)
    await _wolf(client, cid, **extra)
    assert await _skill_bonus(client, cid, "stealth") == 2  # Destrezza 15 della bestia, nessuna competenza
    assert await _save_bonus(client, cid, "constitution") == 1
