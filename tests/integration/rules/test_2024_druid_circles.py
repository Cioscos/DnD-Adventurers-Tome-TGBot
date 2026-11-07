"""Druido 2024 (Task 34, parte B): Circoli della Terra, della Luna, del Mare e delle Stelle. Valori dalla scheda
``docs/superpowers/rules/2024/classes/druid.md``."""
from __future__ import annotations

import pytest

from core.rules.catalog import features_for
from core.rules.catalog.granted_spells import GRANTED_SPELLS
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _states, _use
from tests.integration.rules.test_2014_druid import _activate, _beast, _form
from tests.integration.rules.test_2024_druid import WILD, _druid24, _new_turn, _next_turn, _resolve, _shape

CIRCLES = {"land": "Circolo della Terra", "moon": "Circolo della Luna", "sea": "Circolo del Mare", "stars": "Circolo delle Stelle"}
TERRAINS = {
    "arid": ((("blur", "burning-hands", "fire-bolt"), ("fireball",), ("blight",), ("wall-of-stone",)), "fire"),
    "polar": ((("fog-cloud", "hold-person", "ray-of-frost"), ("sleet-storm",), ("ice-storm",), ("cone-of-cold",)), "cold"),
    "temperate": ((("misty-step", "shocking-grasp", "sleep"), ("lightning-bolt",), ("freedom-of-movement",), ("tree-stride",)), "lightning"),
    "tropical": ((("acid-splash", "ray-of-sickness", "web"), ("stinking-cloud",), ("polymorph",), ("insect-plague",)), "poison"),
}
MOON = (("cure-wounds", "moonbeam", "starry-wisp"), ("conjure-animals",), ("fount-of-moonlight",), ("mass-cure-wounds",))
SEA = (("fog-cloud", "gust-of-wind", "ray-of-frost", "shatter", "thunderwave"), ("lightning-bolt", "water-breathing"),
       ("control-water", "ice-storm"), ("conjure-elemental", "hold-monster"))


async def _circle(client, circle, level=5, terrain="arid", **scores) -> int:
    body = {"name": "Druido", "initial_class": {"class_name": "druid", "level": level, "subclass": CIRCLES[circle]}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    for ability, value in scores.items():
        assert (await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})).status_code == 200
    full = await _full(client, cid)
    if any(c.get("group") == "primal_order" for c in full["pending_choices"]):
        assert (await _resolve(client, cid, "primal_order", ["warden"])).status_code == 200
    if circle == "land" and level >= 3:
        r = await _resolve(client, cid, "land_terrain", [terrain])
        assert r.status_code == 200, r.text
    return cid


async def _always(client, cid) -> set[str]:
    rows = (await client.get(f"/characters/{cid}/spells")).json()
    return {s["srd_index"] for s in rows if s.get("always_prepared")}


async def _rest(client, cid, kind="long") -> None:
    await client.post(f"/characters/{cid}/rest", json={"rest_type": kind, **({"confirm_early": True} if kind == "long" else {})})


async def _spend_slots(client, cid) -> None:
    for slot in (await _full(client, cid))["spell_slots"]:
        assert (await client.patch(f"/characters/{cid}/spell_slots/{slot['id']}", json={"used": slot["total"]})).status_code == 200


def _tiers(spells, level):
    return {s for tier, lv in zip(spells, (3, 5, 7, 9)) if level >= lv for s in tier}


# ---------------------------------------------------------------------------
# Catalogo e incantesimi di circolo
# ---------------------------------------------------------------------------

def test_every_2024_circle_spell_has_data_to_be_granted():
    wanted = {s for spells, _res in TERRAINS.values() for tier in spells for s in tier}
    wanted |= {s for tier in (*MOON, *SEA) for s in tier} | {"guidance", "guiding-bolt"}
    assert not wanted - set(GRANTED_SPELLS)


def test_every_circle_title_of_the_mapping_has_its_row():
    got = {c: {f.source_title for f in features_for("2024", "druid") if f.subclass == c} for c in CIRCLES}
    assert len(got["land"]) == 5 and len(got["moon"]) == 5 and len(got["sea"]) == 5 and len(got["stars"]) == 8, got


@pytest.mark.parametrize("terrain", sorted(TERRAINS))
@pytest.mark.parametrize("level,tiers", [(2, 0), (3, 1), (5, 2), (7, 3), (9, 4)])
async def test_land_spells_follow_the_chosen_terrain(client, terrain, level, tiers):
    cid = await _circle(client, "land", level, terrain)
    assert await _always(client, cid) >= _tiers(TERRAINS[terrain][0], level)
    other = {s for t, (spells, _r) in TERRAINS.items() if t != terrain for tier in spells for s in tier}
    assert not (await _always(client, cid)) & (other - {s for tier in TERRAINS[terrain][0] for s in tier})


async def test_the_terrain_can_be_changed_and_the_spells_follow(client):
    cid = await _circle(client, "land", 5, "arid")
    cls = (await _full(client, cid))["classes"][0]
    r = await client.post(f"/characters/{cid}/classes/{cls['id']}/options/replace",
                          json={"group": "land_terrain", "old_key": "arid", "new_key": "polar"})
    assert r.status_code == 200, r.text
    got = await _always(client, cid)
    assert "ray-of-frost" in got and "fireball" not in got


@pytest.mark.parametrize("circle,tiers", [("moon", MOON), ("sea", SEA)])
@pytest.mark.parametrize("level", [3, 5, 7, 9])
async def test_moon_and_sea_spells_arrive_at_3_5_7_and_9(client, circle, tiers, level):
    cid = await _circle(client, circle, level)
    assert await _always(client, cid) >= _tiers(tiers, level)


async def test_moon_spells_cast_in_wild_shape_without_the_form_warning_but_others_still_ask(client):
    cid = await _circle(client, "moon", 5)
    await _shape(client, cid)
    rows = {s["srd_index"]: s for s in (await client.get(f"/characters/{cid}/spells")).json()}
    ok = await client.get(f"/characters/{cid}/spells/{rows['cure-wounds']['id']}/cast-check")
    assert ok.status_code == 200 and "wild_shape" not in ok.json()
    other = await _druid24(client, 5, "warden")
    await _shape(client, other)
    spell = (await client.get(f"/characters/{other}/spells")).json()[0]
    assert "wild_shape" in (await client.get(f"/characters/{other}/spells/{spell['id']}/cast-check")).json()


# ---------------------------------------------------------------------------
# Terra
# ---------------------------------------------------------------------------

async def test_lands_aid_spends_a_wild_shape_use_and_scales_the_dice(client, monkeypatch):
    monkeypatch.setattr("api.services.rules_states.random.randint", lambda a, b: 3)
    monkeypatch.setattr("core.rules.catalog.y2024.druid.random.randint", lambda a, b: 3)
    for level, dice in ((3, 2), (10, 3), (14, 4)):
        cid = await _circle(client, "land", level, wisdom=16)
        r = await _use(client, cid, "druid.lands_aid", params={"mode": "self"})
        assert r.status_code == 200, r.text
        assert r.json()["rolls"] == [3] * dice
        assert (await _ability(client, cid, WILD))["uses"] == (await _ability(client, cid, WILD))["max_uses"] - 1
        state = next(s for s in await _states(client, cid) if s["key"] == "lands_aid")
        assert state["data"]["save"] == "constitution" and state["data"]["damage"] == 3 * dice
        assert state["data"]["damage_type"] == "necrotic" and state["data"]["dc"] == 8 + {3: 2, 10: 4, 14: 5}[level] + 3
        assert "heal" not in state["data"]  # la cura si applica subito, non resta nello stato


async def test_natural_recovery_returns_slots_after_a_short_rest_from_level_6(client):
    assert await _ability(client, await _circle(client, "land", 5), "druid.natural_recovery") is None
    cid = await _circle(client, "land", 6)
    row = await _ability(client, cid, "druid.natural_recovery")
    assert (row["max_uses"], row["restoration_type"]) == (1, "long_rest")
    await _spend_slots(client, cid)
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "natural_recovery": {"1": 1, "2": 1}})
    assert r.status_code == 200, r.text
    over = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "natural_recovery": {"1": 1}})
    assert over.status_code == 409


async def test_natural_recovery_casts_a_prepared_circle_spell_without_a_slot_once_per_long_rest(client):
    cid = await _circle(client, "land", 6, "arid")
    key = "druid.natural_recovery_cast"
    assert (await _use(client, cid, key, params={"spell": "fire-bolt"})).status_code == 422  # un trucchetto non vale
    assert (await _use(client, cid, key, params={"spell": "burning-hands"})).status_code == 200
    state = next(s for s in await _states(client, cid) if (s.get("data") or {}).get("free_cast"))
    assert state["data"]["free_cast"] == "burning-hands"
    rows = {s["srd_index"]: s for s in (await client.get(f"/characters/{cid}/spells")).json()}
    r = await client.post(f"/characters/{cid}/spells/{rows['burning-hands']['id']}/use", json={"free_cast": True})
    assert r.status_code == 200, r.text
    assert all(s["used"] == 0 for s in (await _full(client, cid))["spell_slots"])
    assert (await _use(client, cid, key, params={"spell": "burning-hands"})).status_code == 409
    await _rest(client, cid)
    assert (await _use(client, cid, key, params={"spell": "burning-hands"})).status_code == 200


@pytest.mark.parametrize("terrain", sorted(TERRAINS))
async def test_natures_ward_gives_poison_condition_immunity_and_the_terrain_resistance(client, terrain):
    cid = await _circle(client, "land", 10, terrain)
    full = await _full(client, cid)
    assert TERRAINS[terrain][1] in full["computed"]["resistances"]
    await client.patch(f"/characters/{cid}/conditions", json={"poisoned": True})
    assert not (await _full(client, cid))["conditions"].get("poisoned")
    low = await _circle(client, "land", 9, terrain)
    assert TERRAINS[terrain][1] not in (await _full(client, low))["computed"]["resistances"]


async def test_natures_sanctuary_lasts_a_minute_gives_half_cover_and_can_be_moved(client):
    cid = await _circle(client, "land", 14, "polar")
    ac = (await _full(client, cid))["ac"]
    r = await _use(client, cid, "druid.natures_sanctuary")
    assert r.status_code == 200, r.text
    state = next(s for s in await _states(client, cid) if s["key"] == "natures_sanctuary")
    assert state["rounds_left"] == 10 and state["data"]["resistance"] == "cold"
    assert (await _full(client, cid))["ac"] == ac + 2
    assert (await _ability(client, cid, WILD))["uses"] == 2  # 3 usi al 14°
    await _new_turn(client, cid)
    assert (await _use(client, cid, "druid.natures_sanctuary_move")).status_code == 200
    assert (await _ability(client, cid, WILD))["uses"] == 2  # lo spostamento non costa un uso


# ---------------------------------------------------------------------------
# Luna
# ---------------------------------------------------------------------------

async def test_circle_forms_use_level_over_three_for_the_challenge_rating_and_give_ac_and_temp_hp(client):
    cid = await _circle(client, "moon", 6, wisdom=16)
    big = await _form(client, cid, _beast(3), name="Orso")
    assert (await _activate(client, cid, big)).status_code in (409, 422)  # GS 3 > 6 / 3
    form = await _form(client, cid, _beast(2))
    assert (await _activate(client, cid, form)).status_code == 200
    assert (await _full(client, cid))["temp_hp"] == 18  # 3 x livello
    assert (await client.get(f"/characters/{cid}/companions")).json()  # la forma resta fra i compagni


async def test_improved_circle_forms_offers_radiant_and_adds_wisdom_to_constitution_saves_in_form(client):
    cid = await _circle(client, "moon", 6, wisdom=16, constitution=10)
    assert "druid.radiant_moon" not in await _roll_keys(client, cid, "attack")
    await _shape(client, cid)
    assert "druid.radiant_moon" in await _roll_keys(client, cid, "attack", attack_mode="form")
    assert (await _full(client, cid))["computed"]["save_flat"]["constitution"] == 3
    low = await _circle(client, "moon", 5, wisdom=16, constitution=10)
    await _shape(client, low)
    assert (await _full(client, low))["computed"]["save_flat"]["constitution"] == 0


async def test_moonlight_step_has_wisdom_uses_gives_advantage_and_recovers_one_use_with_a_slot(client):
    cid = await _circle(client, "moon", 10, wisdom=16)
    row = await _ability(client, cid, "druid.moonlight_step")
    assert (row["max_uses"], row["restoration_type"]) == (3, "long_rest")
    assert (await _use(client, cid, "druid.moonlight_step")).status_code == 200
    assert any(s["key"] == "moonlight_step" for s in await _states(client, cid))
    assert (await _turn_flag(client, cid, "bonus_used")) is True
    r = await _use(client, cid, "druid.moonlight_step_slot", params={"slot_level": "2"})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, "druid.moonlight_step"))["uses"] == 3
    assert (await _use(client, cid, "druid.moonlight_step_slot", params={"slot_level": "1"})).status_code == 422


async def _turn_flag(client, cid, flag):
    return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"].get(flag)


async def test_moonlight_step_minimum_is_one_use(client):
    cid = await _circle(client, "moon", 10, wisdom=8)
    assert (await _ability(client, cid, "druid.moonlight_step"))["max_uses"] == 1


async def test_lunar_form_adds_2d10_radiant_once_per_turn_to_a_form_attack(client):
    cid = await _circle(client, "moon", 14, wisdom=16)
    assert "druid.lunar_radiance" not in await _roll_keys(client, cid, "attack", attack_mode="form")
    await _shape(client, cid)
    assert "druid.lunar_radiance" in await _roll_keys(client, cid, "attack", attack_mode="form")
    assert "druid.lunar_radiance" not in await _roll_keys(client, await _circle(client, "moon", 13), "attack", attack_mode="form")


# ---------------------------------------------------------------------------
# Mare
# ---------------------------------------------------------------------------

async def test_wrath_of_the_sea_costs_a_use_and_a_bonus_action_and_rolls_wisdom_d6(client, monkeypatch):
    monkeypatch.setattr("api.services.rules_states.random.randint", lambda a, b: 4)
    cid = await _circle(client, "sea", 5, wisdom=16)
    r = await _use(client, cid, "druid.wrath_of_the_sea")
    assert r.status_code == 200, r.text
    assert r.json()["rolls"] == [4, 4, 4]
    state = next(s for s in await _states(client, cid) if s["key"] == "wrath_of_the_sea")
    assert state["rounds_left"] == 100 and state["data"]["save"] == "constitution" and state["data"]["radius_m"] == 1.5
    assert (await _ability(client, cid, WILD))["uses"] == 1
    assert (await _turn_flag(client, cid, "bonus_used")) is True
    await _new_turn(client, cid)
    again = await _use(client, cid, "druid.wrath_of_the_sea_again")
    assert again.status_code == 200 and again.json()["rolls"] == [4, 4, 4]
    assert (await _ability(client, cid, WILD))["uses"] == 1
    big = await _circle(client, "sea", 6, wisdom=8)
    await _use(client, big, "druid.wrath_of_the_sea")
    state = next(s for s in await _states(client, big) if s["key"] == "wrath_of_the_sea")
    assert state["data"]["radius_m"] == 3 and (await _use(client, big, "druid.wrath_of_the_sea_again")).status_code == 409


async def test_wrath_again_needs_the_emanation(client):
    cid = await _circle(client, "sea", 5)
    assert (await _use(client, cid, "druid.wrath_of_the_sea_again")).status_code == 409


async def test_aquatic_affinity_gives_a_swim_speed_from_level_6(client):
    low, high = await _circle(client, "sea", 5), await _circle(client, "sea", 6)
    assert not (await _full(client, low))["computed"]["swim_speed"]
    computed = (await _full(client, high))["computed"]
    assert computed["swim_speed"] == computed["speed"]


async def test_stormborn_gives_flight_and_three_resistances_only_while_the_emanation_lasts(client):
    cid = await _circle(client, "sea", 10, wisdom=16)
    assert not {"cold", "lightning", "thunder"} & set((await _full(client, cid))["computed"]["resistances"])
    assert (await _use(client, cid, "druid.wrath_of_the_sea")).status_code == 200
    computed = (await _full(client, cid))["computed"]
    assert {"cold", "lightning", "thunder"} <= set(computed["resistances"]) and computed["fly_speed"] == computed["speed"]


@pytest.mark.parametrize("target,cost", [("ally", 1), ("both", 2)])
async def test_oceanic_gift_costs_one_or_two_uses(client, target, cost):
    cid = await _circle(client, "sea", 14, wisdom=16)
    r = await _use(client, cid, "druid.oceanic_gift", params={"target": target})
    assert r.status_code == 200, r.text
    row = await _ability(client, cid, WILD)
    assert row["uses"] == row["max_uses"] - cost
    assert any(s["key"] == ("wrath_of_the_sea" if target == "both" else "oceanic_gift_ally") for s in await _states(client, cid))


# ---------------------------------------------------------------------------
# Stelle
# ---------------------------------------------------------------------------

async def test_star_map_gives_guidance_and_guiding_bolt_and_free_bolts_equal_to_wisdom(client):
    cid = await _circle(client, "stars", 3, wisdom=16)
    assert {"guidance", "guiding-bolt"} <= await _always(client, cid)
    row = await _ability(client, cid, "druid.star_map")
    assert (row["max_uses"], row["restoration_type"]) == (3, "long_rest")
    rows = {s["srd_index"]: s for s in (await client.get(f"/characters/{cid}/spells")).json()}
    r = await client.post(f"/characters/{cid}/spells/{rows['guiding-bolt']['id']}/use", json={"free_cast": True})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, "druid.star_map"))["uses"] == 2


async def test_starry_form_costs_a_use_a_bonus_action_and_keeps_one_constellation(client):
    cid = await _circle(client, "stars", 3, wisdom=16)
    r = await _use(client, cid, "druid.starry_form", params={"constellation": "chalice"})
    assert r.status_code == 200, r.text
    state = next(s for s in await _states(client, cid) if s["key"] == "starry_form")
    assert state["rounds_left"] == 100 and state["data"]["constellation"] == "chalice"
    assert (await _ability(client, cid, WILD))["uses"] == 1 and (await _turn_flag(client, cid, "bonus_used")) is True
    await _new_turn(client, cid)
    assert (await _use(client, cid, "druid.starry_form", params={"constellation": "dragon"})).status_code == 200
    forms = [s for s in await _states(client, cid) if s["key"] == "starry_form"]
    assert len(forms) == 1 and forms[0]["data"]["constellation"] == "dragon"
    assert (await _use(client, cid, "druid.starry_form", params={"constellation": "owl"})).status_code == 422


async def test_archer_attacks_with_a_bonus_action_for_1d8_then_2d8_plus_wisdom(client, monkeypatch):
    monkeypatch.setattr("api.services.rules_states.random.randint", lambda a, b: 5)
    cid = await _circle(client, "stars", 10, wisdom=16)
    assert (await _use(client, cid, "druid.archer")).status_code == 409  # senza la Forma Stellare
    r = await _use(client, cid, "druid.starry_form", params={"constellation": "archer"})
    assert r.status_code == 200, r.text
    free = await _use(client, cid, "druid.archer")  # il primo colpo è dell'attivazione: nessuna seconda azione bonus
    assert free.status_code == 200 and free.json()["rolls"] == [5, 5], free.text
    await _new_turn(client, cid)
    r = await _use(client, cid, "druid.archer")
    assert r.status_code == 200 and r.json()["rolls"] == [5, 5]
    assert (await _use(client, cid, "druid.archer")).status_code == 409  # la seconda azione bonus del turno non c'è
    low = await _circle(client, "stars", 9, wisdom=16)
    await _use(client, low, "druid.starry_form", params={"constellation": "archer"})
    assert (await _use(client, low, "druid.archer")).json()["rolls"] == [5]


async def test_chalice_is_offered_on_a_slot_healing_spell_only_in_the_chalice_constellation(client):
    cid = await _circle(client, "stars", 5, wisdom=16)
    q = {"roll": "spell_healing", "casting_level": 1}
    assert "druid.chalice" not in await _roll_keys(client, cid, **q)
    await _use(client, cid, "druid.starry_form", params={"constellation": "chalice"})
    assert "druid.chalice" in await _roll_keys(client, cid, **q)
    await _new_turn(client, cid)
    await _use(client, cid, "druid.starry_form", params={"constellation": "dragon"})
    assert "druid.chalice" not in await _roll_keys(client, cid, **q)


async def test_dragon_floors_the_d20_at_ten_for_int_wis_checks_in_the_dragon_form_only(client):
    cid = await _circle(client, "stars", 5, wisdom=16)
    off = (await client.post(f"/characters/{cid}/ability_checks/wisdom/roll", json={"die": 7})).json()
    assert off["die"] == 7
    await _use(client, cid, "druid.starry_form", params={"constellation": "dragon"})
    on = (await client.post(f"/characters/{cid}/ability_checks/wisdom/roll", json={"die": 7})).json()
    assert on["die"] == 10 and on["total"] == 10 + on["bonus"]
    assert (await client.post(f"/characters/{cid}/ability_checks/intelligence/roll", json={"die": 9})).json()["die"] == 10
    assert (await client.post(f"/characters/{cid}/ability_checks/strength/roll", json={"die": 7})).json()["die"] == 7
    other = await _circle(client, "stars", 5, wisdom=16)
    await _use(client, other, "druid.starry_form", params={"constellation": "archer"})
    assert (await client.post(f"/characters/{other}/ability_checks/wisdom/roll", json={"die": 7})).json()["die"] == 7


async def test_dragon_flies_from_level_10_and_full_of_stars_resists_physical_damage_in_the_form(client):
    cid = await _circle(client, "stars", 14, wisdom=16)
    assert not {"bludgeoning", "piercing", "slashing"} & set((await _full(client, cid))["computed"]["resistances"])
    await _use(client, cid, "druid.starry_form", params={"constellation": "dragon"})
    computed = (await _full(client, cid))["computed"]
    assert {"bludgeoning", "piercing", "slashing"} <= set(computed["resistances"]) and computed["fly_speed"] == 20  # 6 m, non la velocità a terra
    low = await _circle(client, "stars", 9, wisdom=16)
    await _use(client, low, "druid.starry_form", params={"constellation": "dragon"})
    assert not (await _full(client, low))["computed"]["fly_speed"]


async def test_twinkling_constellations_change_the_constellation_at_the_start_of_the_turn_from_level_10(client):
    cid = await _circle(client, "stars", 10, wisdom=16)
    assert (await _use(client, cid, "druid.twinkling_constellations", params={"constellation": "dragon"})).status_code == 409
    await _use(client, cid, "druid.starry_form", params={"constellation": "archer"})
    await _next_turn(client, cid)
    r = await _use(client, cid, "druid.twinkling_constellations", params={"constellation": "chalice"})
    assert r.status_code == 200, r.text
    state = next(s for s in await _states(client, cid) if s["key"] == "starry_form")
    assert state["data"]["constellation"] == "chalice" and state["rounds_left"] > 90
    assert (await _ability(client, cid, WILD))["uses"] == 2  # 3 usi al 10°, uno solo speso: cambiare non ne costa altri


async def test_cosmic_omen_is_rolled_at_the_long_rest_and_the_reaction_rolls_a_d6(client, monkeypatch):
    roll = {"die": 4}
    monkeypatch.setattr("core.rules.catalog.y2024.druid.random.randint", lambda a, b: roll["die"])
    cid = await _circle(client, "stars", 6, wisdom=16)
    row = await _ability(client, cid, "druid.cosmic_omen")
    assert (row["max_uses"], row["restoration_type"]) == (3, "long_rest")
    assert (await _use(client, cid, "druid.cosmic_omen")).status_code == 409  # nessun riposo lungo ancora
    await _rest(client, cid)
    state = next(s for s in await _states(client, cid) if s["key"] == "cosmic_omen")
    assert state["data"]["omen"] == "weal" and state["data"]["roll"] == 4  # pari: Prosperità
    r = await _use(client, cid, "druid.cosmic_omen")
    assert r.status_code == 200 and r.json()["rolls"] == [4]
    assert (await _turn_flag(client, cid, "reaction_used")) is True
    roll["die"] = 3
    await _rest(client, cid)
    assert next(s for s in await _states(client, cid) if s["key"] == "cosmic_omen")["data"]["omen"] == "woe"
