"""Druido 2024, giro di correzione 1 (C1, I1-I10, m2): ogni rilievo ha il suo test, scritto prima della correzione."""
from __future__ import annotations

from types import SimpleNamespace

from core.rules.catalog.granted_spells import GRANTED_SPELLS
from core.rules.catalog.y2024.druid import CON_IN_FORM
from core.rules.types import RuleContext
from tests.integration.rules.test_2014_bard import _ability, _full, _roll_keys, _states, _use
from tests.integration.rules.test_2014_druid import _activate, _beast, _form, _turn
from tests.integration.rules.test_2024_druid import _druid24, _new_turn, _next_turn, _resolve
from tests.integration.rules.test_2024_druid_circles import _circle, _turn_flag

BITE = [{"name": "Morso", "attack_bonus": 4, "damage_dice": "1d6", "damage_type": "piercing"}]


async def _bite(client, cid, cr=0.5) -> int:
    form = await _form(client, cid, {**_beast(cr), "actions": BITE})
    assert (await _activate(client, cid, form)).status_code == 200
    await _new_turn(client, cid)
    return form


async def _hit(client, cid, form, *options):
    return await client.post(f"/characters/{cid}/companions/{form}/attack", json={"action_index": 0, "mode": "normal", "dice": [15], "options": list(options)})


async def _keys(client, cid) -> set[str]:
    return {s["key"] for s in await _states(client, cid) if s["key"] in ("wrath_of_the_sea", "oceanic_gift_ally")}


async def _hurt(client, cid) -> None:
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 40})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 5})


# C1 -------------------------------------------------------------------------------------------------------------

async def test_c1_lunar_options_are_listed_and_work_on_the_form_attack(client):
    cid = await _circle(client, "moon", 14, wisdom=16)
    form = await _bite(client, cid, 4)
    keys = await _roll_keys(client, cid, "attack", attack_mode="form")
    assert {"druid.lunar_radiance", "druid.radiant_moon"} <= set(keys)
    r = await _hit(client, cid, form, "druid.lunar_radiance", "druid.radiant_moon")
    assert r.status_code == 200, r.text
    body = r.json()
    assert 2 <= body["option_result"]["extra_total"] <= 20 and body["damage_type"] == "radiant"
    assert (await _hit(client, cid, form, "druid.lunar_radiance")).status_code == 409  # una volta per turno
    assert (await _hit(client, cid, form)).json()["damage_type"] == "piercing"


async def test_c1_primal_strike_works_on_the_form_attack_once_per_turn(client):
    cid = await _druid24(client, 7)
    await _resolve(client, cid, "elemental_fury", ["primal_strike"])
    form = await _bite(client, cid)
    assert "druid.primal_strike_fire_form" in await _roll_keys(client, cid, "attack", attack_mode="form")
    r = await _hit(client, cid, form, "druid.primal_strike_fire_form")
    assert r.status_code == 200, r.text
    assert 1 <= r.json()["option_result"]["extra_total"] <= 8
    assert (await _hit(client, cid, form, "druid.primal_strike_cold_form")).status_code == 409


# I1 -------------------------------------------------------------------------------------------------------------

async def test_i1_moonlight_step_advantage_ends_with_the_first_form_attack(client):
    cid = await _circle(client, "moon", 10, wisdom=16)
    form = await _bite(client, cid, 3)
    assert (await _use(client, cid, "druid.moonlight_step")).status_code == 200
    assert (await _hit(client, cid, form)).json()["mode"] == "advantage"
    assert (await _hit(client, cid, form)).json()["mode"] == "normal"
    assert not any(s["key"] == "moonlight_step" for s in await _states(client, cid))


# I2 -------------------------------------------------------------------------------------------------------------

def test_i2_improved_forms_add_wisdom_to_the_concentration_save_too():
    char = SimpleNamespace(active_states=[{"key": "wild_shape"}])

    def ctx(roll: str) -> RuleContext:
        return RuleContext(char=char, edition="2024", roll=roll, ability="constitution")

    assert CON_IN_FORM.when(ctx("save")) and CON_IN_FORM.when(ctx("concentration"))
    assert not CON_IN_FORM.when(ctx("skill"))


# I4 -------------------------------------------------------------------------------------------------------------

async def test_i4_the_free_archer_attack_is_shown_then_closed_with_the_turn(client):
    cid = await _circle(client, "stars", 10, wisdom=16)
    await _use(client, cid, "druid.starry_form", params={"constellation": "archer"})
    assert (await _ability(client, cid, "druid.archer"))["free_use"] is True  # l'azione bonus è spesa ma questo colpo è gratis
    assert (await _use(client, cid, "druid.archer")).status_code == 200
    assert (await _ability(client, cid, "druid.archer"))["free_use"] is False
    assert (await _use(client, cid, "druid.archer")).status_code == 409
    other = await _circle(client, "stars", 10, wisdom=16)
    await _use(client, other, "druid.starry_form", params={"constellation": "archer"})
    await _next_turn(client, other)  # il colpo gratuito era solo dell'attivazione
    assert (await _ability(client, other, "druid.archer"))["free_use"] is False
    assert (await _use(client, other, "druid.archer")).status_code == 200
    assert await _turn_flag(client, other, "bonus_used") is True


# I5 -------------------------------------------------------------------------------------------------------------

async def test_i5_the_archer_rolls_a_real_attack_and_no_damage_on_a_natural_1(client, monkeypatch):
    monkeypatch.setattr("api.services.d20.random.randint", lambda a, b: 1 if b == 20 else 5)
    cid = await _circle(client, "stars", 10, wisdom=16)
    await _use(client, cid, "druid.starry_form", params={"constellation": "archer"})
    r = await _use(client, cid, "druid.archer")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["attack"]["die"] == 1 and body["attack"]["is_fumble"] is True and body["rolls"] == []
    assert body["attack"]["bonus"] == 4 + 3 and body["attack"]["total"] == 1 + 7  # competenza al 10° + Saggezza


async def test_i5_the_archer_doubles_the_damage_dice_on_a_critical_and_rolls_normally_otherwise(client, monkeypatch):
    monkeypatch.setattr("api.services.d20.random.randint", lambda a, b: 20)
    cid = await _circle(client, "stars", 10, wisdom=16)
    await _use(client, cid, "druid.starry_form", params={"constellation": "archer"})
    body = (await _use(client, cid, "druid.archer")).json()
    assert body["attack"]["is_critical"] is True and len(body["rolls"]) == 4  # 2d8 raddoppiati
    monkeypatch.setattr("api.services.d20.random.randint", lambda a, b: 12)
    low = await _circle(client, "stars", 9, wisdom=16)
    await _use(client, low, "druid.starry_form", params={"constellation": "archer"})
    body = (await _use(client, low, "druid.archer")).json()
    assert body["attack"]["total"] == 12 + 4 + 3 and len(body["rolls"]) == 1 and not body["attack"]["is_critical"]


# I6 -------------------------------------------------------------------------------------------------------------

async def test_i6_the_constellation_changes_once_per_turn(client):
    cid = await _circle(client, "stars", 10, wisdom=16)
    await _use(client, cid, "druid.starry_form", params={"constellation": "archer"})
    await _next_turn(client, cid)
    assert (await _use(client, cid, "druid.twinkling_constellations", params={"constellation": "chalice"})).status_code == 200
    assert (await _use(client, cid, "druid.twinkling_constellations", params={"constellation": "dragon"})).status_code == 409
    await _next_turn(client, cid)
    assert (await _use(client, cid, "druid.twinkling_constellations", params={"constellation": "dragon"})).status_code == 200


# I7 -------------------------------------------------------------------------------------------------------------

async def test_i7_a_new_emanation_replaces_the_other_one(client):
    cid = await _circle(client, "sea", 14, wisdom=16)
    assert (await _use(client, cid, "druid.wrath_of_the_sea")).status_code == 200
    await _new_turn(client, cid)
    assert (await _use(client, cid, "druid.oceanic_gift", params={"target": "ally"})).status_code == 200
    assert await _keys(client, cid) == {"oceanic_gift_ally"}
    assert "cold" not in set((await _full(client, cid))["computed"]["resistances"])  # niente più Nato dalla Tempesta
    await _new_turn(client, cid)
    assert (await _use(client, cid, "druid.wrath_of_the_sea")).status_code == 200
    assert await _keys(client, cid) == {"wrath_of_the_sea"}
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    await _use(client, cid, "druid.oceanic_gift", params={"target": "ally"})
    await _new_turn(client, cid)
    assert (await _use(client, cid, "druid.oceanic_gift", params={"target": "both"})).status_code == 200
    assert await _keys(client, cid) == {"wrath_of_the_sea"}


async def test_i7_the_emanation_on_an_ally_ends_when_the_druid_is_incapacitated(client):
    cid = await _circle(client, "sea", 14, wisdom=16)
    await _use(client, cid, "druid.oceanic_gift", params={"target": "ally"})
    assert (await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"incapacitated": True}})).status_code == 200
    assert await _keys(client, cid) == set()


# I8 -------------------------------------------------------------------------------------------------------------

async def test_i8_the_resurgence_gives_a_level_1_slot_even_with_all_slots_unspent(client):
    cid = await _druid24(client, 5)
    before = {s["level"]: s["total"] for s in (await _full(client, cid))["spell_slots"]}[1]
    r = await _use(client, cid, "druid.wild_resurgence_slot")
    assert r.status_code == 200, r.text
    assert {s["level"]: s["total"] for s in (await _full(client, cid))["spell_slots"]}[1] == before + 1
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert {s["level"]: s["total"] for s in (await _full(client, cid))["spell_slots"]}[1] == before  # lo slot creato svanisce


# I9 -------------------------------------------------------------------------------------------------------------

async def test_i9_lands_aid_heals_the_druid_by_the_rolled_amount(client, monkeypatch):
    monkeypatch.setattr("api.services.rules_states.random.randint", lambda a, b: 3)
    monkeypatch.setattr("core.rules.catalog.y2024.druid.random.randint", lambda a, b: 3)
    cid = await _circle(client, "land", 3, wisdom=16)
    await _hurt(client, cid)
    r = await _use(client, cid, "druid.lands_aid", params={"mode": "self"})
    assert r.status_code == 200, r.text
    assert r.json()["healed"] == 6 and (await _full(client, cid))["current_hit_points"] == 11
    assert "6" in r.json()["message"]["it"]


async def test_i9_lands_aid_on_another_creature_out_of_the_evening_is_a_text_result(client, monkeypatch):
    monkeypatch.setattr("core.rules.catalog.y2024.druid.random.randint", lambda a, b: 3)
    cid = await _circle(client, "land", 3, wisdom=16)
    await _hurt(client, cid)
    assert (await _ability(client, cid, "druid.lands_aid"))["ally_modes"] == ["other"]
    r = await _use(client, cid, "druid.lands_aid", params={"mode": "other"})
    assert r.status_code == 200 and r.json()["healed"] == 0 and r.json()["given"] == 6
    assert (await _full(client, cid))["current_hit_points"] == 5


async def test_i9_the_chalice_heals_the_caster_for_the_rolled_amount(client, monkeypatch):
    monkeypatch.setattr("core.rules.catalog.y2024.druid.random.randint", lambda a, b: 4)
    cid = await _circle(client, "stars", 5, wisdom=16)
    await _use(client, cid, "druid.starry_form", params={"constellation": "chalice"})
    assert {"druid.chalice", "druid.chalice_other"} <= set(await _roll_keys(client, cid, "spell_healing", casting_level=1))
    await _hurt(client, cid)
    cure = (await client.post(f"/characters/{cid}/spells", json={"name": "Cura Ferite", "level": 1, "srd_index": "cure-wounds"})).json()
    r = await client.post(f"/characters/{cid}/spells/{cure['id']}/roll_healing", json={"casting_level": 1, "options": ["druid.chalice"]})
    assert r.status_code == 200, r.text
    assert r.json()["self_healed"] == 4 + 3 and (await _full(client, cid))["current_hit_points"] == 5 + 7


# I10 / m2 ---------------------------------------------------------------------------------------------------------

async def test_i10_potent_spellcasting_range_holds_with_feet_and_with_an_area(client):
    cid = await _druid24(client, 15, wisdom=16)
    await _resolve(client, cid, "elemental_fury", ["potent_spellcasting"])
    row = (await _full(client, cid))["classes"][0]["id"]
    shown = (("Piedi", "120 ft"), ("Area", "18 m (sfera di 6 m)"), ("Corto", "10 ft"), ("Metri", "18 m"), ("Breve", "5 ft"))
    for name, rng in shown:
        await client.post(f"/characters/{cid}/spells", json={"name": name, "level": 0, "class_id": row, "range_area": rng})
    got = {s["name"]: s["effective_range_area"] for s in (await client.get(f"/characters/{cid}/spells")).json() if s["name"] in dict(shown)}
    assert got == {"Piedi": "420 ft", "Area": "108 m (sfera di 6 m)", "Corto": "310 ft", "Metri": "108 m", "Breve": "5 ft"}


def test_m2_ray_of_sickness_scales_and_conjure_animals_has_its_2024_damage():
    assert GRANTED_SPELLS["ray-of-sickness"].higher_levels_dice == "1d8"
    conjure = GRANTED_SPELLS["conjure-animals"]
    assert (conjure.attack_save, conjure.damage_dice, conjure.damage_type, conjure.higher_levels_dice) == ("SAVE", "3d10", "slashing", "1d10")


# Giro 2: N1 (un colpo mancato non brucia l'opzione), N2 (l'attacco di un compagno non chiude gli stati del druido) ---------

async def _swing(client, cid, form, die, *options):
    return await client.post(f"/characters/{cid}/companions/{form}/attack", json={"action_index": 0, "mode": "normal", "dice": [die], "options": list(options)})


async def _refund(client, cid, succeeded):
    return await client.post(f"/characters/{cid}/last-roll/refund", json={"succeeded": succeeded})


async def test_n1_missed_form_attack_gives_the_once_per_turn_back(client):
    cid = await _circle(client, "moon", 14, wisdom=16)
    form = await _bite(client, cid, 4)
    r = await _swing(client, cid, form, 5, "druid.lunar_radiance")
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["last_roll"]["refundable"]  # il giocatore dice l'esito dopo aver visto il d20
    assert (await _refund(client, cid, False)).status_code == 200
    assert (await _swing(client, cid, form, 15, "druid.lunar_radiance")).status_code == 200  # il secondo attacco la ha ancora


async def test_n1_hit_form_attack_keeps_the_spend_once(client):
    cid = await _circle(client, "moon", 14, wisdom=16)
    form = await _bite(client, cid, 4)
    assert (await _swing(client, cid, form, 15, "druid.lunar_radiance")).status_code == 200
    assert (await _refund(client, cid, True)).status_code == 200
    assert (await _swing(client, cid, form, 15, "druid.lunar_radiance")).status_code == 409


async def test_n1_natural_one_refunds_by_itself_and_critical_asks_nothing(client):
    cid = await _circle(client, "moon", 14, wisdom=16)
    form = await _bite(client, cid, 4)
    r = await _swing(client, cid, form, 1, "druid.lunar_radiance")
    assert r.json()["damage_total"] == 0 and not ((await _turn(client, cid)).get("last_roll") or {}).get("refundable")
    r = await _swing(client, cid, form, 20, "druid.lunar_radiance")  # il 1 è stato rimborsato: ora il critico la spende
    assert r.status_code == 200 and not ((await _turn(client, cid)).get("last_roll") or {}).get("refundable")
    assert (await _swing(client, cid, form, 15, "druid.lunar_radiance")).status_code == 409


async def test_n1_primal_strike_form_misses_give_it_back_too(client):
    cid = await _druid24(client, 7)
    await _resolve(client, cid, "elemental_fury", ["primal_strike"])
    form = await _bite(client, cid)
    assert (await _swing(client, cid, form, 5, "druid.primal_strike_fire_form")).status_code == 200
    assert (await _refund(client, cid, False)).status_code == 200
    assert (await _swing(client, cid, form, 15, "druid.primal_strike_cold_form")).status_code == 200


async def test_n2_a_familiar_attack_does_not_end_moonlight_step(client):
    cid = await _circle(client, "moon", 10, wisdom=16)
    form = await _bite(client, cid, 3)
    assert (await _use(client, cid, "druid.moonlight_step")).status_code == 200
    r = await client.post(f"/characters/{cid}/companions", json={
        "kind": "familiar", "name": "Gufo", "statblock": {"actions": BITE}, "max_hp": 5, "armor_class": 11})
    owl = r.json()["id"]
    assert (await _swing(client, cid, owl, 12)).status_code == 200
    assert any(s["key"] == "moonlight_step" for s in await _states(client, cid))
    assert (await _swing(client, cid, form, 12)).json()["mode"] == "advantage"


def test_lands_aid_message_drops_the_gm_hint_when_the_seated_ally_is_already_healed():
    from types import SimpleNamespace
    from core.rules.catalog.y2024.druid import _aid_message
    ctx = SimpleNamespace(char=SimpleNamespace(turn_state={"lands_aid_heal": 7}, active_states=[]))
    told = _aid_message(ctx, {"mode": "other", "ally_healed": True})
    assert "Costituzione" in told["it"] and "GM" not in told["it"] and "GM" not in told["en"]
    assert "GM" in _aid_message(ctx, {"mode": "other"})["it"]


def test_lands_aid_message_29_has_no_trailing_space_when_the_ally_is_already_healed():
    from types import SimpleNamespace
    from core.rules.catalog.y2024.druid import _aid_message
    char = SimpleNamespace(active_states=[{"key": "lands_aid", "data": {"dc": 13, "damage": 9}}], turn_state={})
    msg = _aid_message(SimpleNamespace(char=char), {"mode": "other", "ally_healed": True})
    assert all(text == text.rstrip() for text in msg.values())
