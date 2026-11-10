"""Barbaro 2014 (Task 19): progressione, Ira, opzioni al tiro, stati, sottoclassi e Cammino Totemico."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from core.db.models import Character
from core.rules.catalog import features_for

BERSERKER = "Cammino del Berserker"
TOTEM = "Cammino del Combattente Totemico"
RAGE = "barbarian.rage"


async def _barbarian(client, level=5, subclass=None, **scores) -> int:
    body = {"name": "Barbaro", "initial_class": {"class_name": "barbarian", "level": level, "subclass": subclass}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


async def _full(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def _rage(client, cid, **params):
    return await client.post(f"/characters/{cid}/features/{RAGE}/use", json={"params": params} if params else {})


async def _states(client, cid) -> list[dict]:
    return (await _full(client, cid))["active_states"] or []


async def _weapon(client, cid, name="Ascia", equip="main_hand", **meta) -> int:
    meta = {"damage_dice": "1d12", "weapon_type": "melee", "properties": [], **meta}
    r = await client.post(f"/characters/{cid}/items", json={"name": name, "item_type": "weapon", "item_metadata": meta})
    assert r.status_code == 201, r.text
    wid = max(i["id"] for i in r.json()["items"] if i["name"] == name)
    if equip:
        r = await client.patch(f"/characters/{cid}/items/{wid}", json={"is_equipped": True, "equipment_slot": equip})
        assert r.status_code == 200, r.text
    return wid


async def _armor(client, cid, armor_type, value=18) -> None:
    r = await client.post(f"/characters/{cid}/items", json={
        "name": f"Armatura {armor_type}", "item_type": "armor", "item_metadata": {"ac_value": value, "armor_type": armor_type}})
    item = next(i for i in r.json()["items"] if i["name"] == f"Armatura {armor_type}")
    r = await client.patch(f"/characters/{cid}/items/{item['id']}", json={"is_equipped": True, "equipment_slot": "body"})
    assert r.status_code == 200, r.text


async def _attack(client, cid, wid, die=10, **body):
    r = await client.post(f"/characters/{cid}/items/{wid}/attack",
                          json={"die": die, "confirm_extra_attack": True, **body})
    assert r.status_code == 200, r.text
    return r.json()


async def _keys(client, cid, roll, **query) -> list[str]:
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": roll, **query})
    assert r.status_code == 200, r.text
    return [o["key"] for o in r.json()]


async def _turn(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]


async def _ability(client, cid, key) -> dict | None:
    return next((a for a in (await _full(client, cid))["abilities"] if a["feature_key"] == key), None)


# ---------------------------------------------------------------------------
# Progressione e catalogo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,uses", [(1, 2), (2, 2), (3, 3), (5, 3), (6, 4), (11, 4), (12, 5), (16, 5), (17, 6), (19, 6)])
async def test_rage_uses_follow_the_class_table(client, level, uses):
    cid = await _barbarian(client, level)
    rage = await _ability(client, cid, RAGE)
    assert (rage["name"], rage["max_uses"], rage["uses"], rage["restoration_type"]) == ("Ira", uses, uses, "long_rest")


async def test_rage_is_unlimited_at_20_and_still_usable(client):
    cid = await _barbarian(client, 20)
    rage = await _ability(client, cid, RAGE)
    assert rage["max_uses"] is None and rage["restoration_type"] == "long_rest" and rage["has_on_use"]
    assert (await _rage(client, cid)).status_code == 200


@pytest.mark.parametrize("level,present", [
    (1, {"rage", "unarmored_defense"}), (2, {"reckless_attack", "danger_sense"}), (5, {"extra_attack", "fast_movement"}),
    (7, {"feral_instinct"}), (9, {"brutal_critical"}), (11, {"relentless_rage"}), (15, {"persistent_rage"}),
    (18, {"indomitable_might"}), (20, {"primal_champion"}),
])
async def test_features_appear_at_their_level(client, level, present):
    cid = await _barbarian(client, level)
    keys = {a["feature_key"] for a in (await _full(client, cid))["abilities"]}
    assert {f"barbarian.{k}" for k in present} <= keys
    below = await _barbarian(client, level - 1) if level > 1 else None
    if below:
        low = {a["feature_key"] for a in (await _full(client, below))["abilities"]}
        assert not {f"barbarian.{k}" for k in present} & low


async def test_rules_only_rows_do_not_clutter_the_sheet(client):
    cid = await _barbarian(client, 20)
    keys = {a["feature_key"] for a in (await _full(client, cid))["abilities"]}
    assert not keys & {f"barbarian.{k}" for k in (
        "hit_points", "proficiencies", "equipment", "primal_path", "ability_score_improvement", "multiclassing")}
    # ma stanno nel catalogo, con il titolo della scheda
    titles = {s.source_title for s in features_for("2014", "barbarian")}
    assert "Punti Ferita / Hit Points (Barbaro 1, pag. 47)" in titles


@pytest.mark.parametrize("level", [4, 8, 12, 16, 19])
async def test_asi_choice_is_pending_at_each_asi_level(client, level):
    cid = await _barbarian(client, level)
    levels = sorted(c["level"] for c in (await _full(client, cid))["pending_choices"] if c["kind"] == "asi")
    assert levels == [lv for lv in (4, 8, 12, 16, 19) if lv <= level]


async def test_hit_points_use_the_d12_and_follow_constitution(client):
    cid = await _barbarian(client, 3)
    full = await _full(client, cid)
    assert full["classes"][0]["hit_die"] == 12
    assert full["hit_points"] == 12 + 7 + 7  # 12 + COS al 1°, poi la media 7 (COS 10)
    await client.patch(f"/characters/{cid}/ability_scores/constitution", json={"value": 14})
    assert (await _full(client, cid))["hit_points"] == 12 + 7 + 7 + 2 * 3


async def test_attack_extra_is_two_and_does_not_stack_with_fighter(client):
    cid = await _barbarian(client, 5)
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["attacks_allowed"] == 2
    low = await _barbarian(client, 4)
    assert (await client.get(f"/characters/{low}/turn-state")).json()["attacks_allowed"] == 1
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})
    assert r.status_code == 201
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["attacks_allowed"] == 2


# ---------------------------------------------------------------------------
# Ira
# ---------------------------------------------------------------------------

async def test_rage_spends_bonus_action_and_a_use_and_starts_the_state(client):
    cid = await _barbarian(client, 5)
    r = await _rage(client, cid)
    assert r.status_code == 200, r.text
    state = r.json()["state"]
    assert (state["key"], state["rounds_left"], state["name"]) == ("rage", 10, "Ira")
    assert state["data"]["damage"] == 2 and state["blocks_casting"] is True
    assert (await _turn(client, cid))["bonus_used"] is True
    assert (await _ability(client, cid, RAGE))["uses"] == 2
    again = await _rage(client, cid)  # già in ira: niente secondo uso
    assert again.status_code == 409 and again.json()["detail"]["code"] in ("feature_unavailable", "turn_slot_used")
    assert (await _ability(client, cid, RAGE))["uses"] == 2


async def test_rage_ends_on_unconscious_and_rests_and_without_attacking_before_15(client):
    low = (await _rage(client, await _barbarian(client, 14))).json()["state"]
    high = (await _rage(client, await _barbarian(client, 15))).json()["state"]
    assert "turn_end_inactive" in low["ends_on"] and "turn_end_inactive" not in high["ends_on"]
    assert {"unconscious", "rest_short", "rest_long"} <= set(low["ends_on"]) & set(high["ends_on"])


@pytest.mark.parametrize("level,bonus", [(1, 2), (8, 2), (9, 3), (15, 3), (16, 4), (20, 4)])
async def test_rage_damage_bonus_by_level_on_melee_strength_only(client, level, bonus):
    cid = await _barbarian(client, level, strength=16, dexterity=10)
    sword = await _weapon(client, cid)
    plain = (await _attack(client, cid, sword))["damage_bonus"]
    await _rage(client, cid)
    assert (await _attack(client, cid, sword))["damage_bonus"] == plain + bonus


async def test_rage_damage_not_on_thrown_ranged_or_dexterity_attacks(client):
    cid = await _barbarian(client, 5, strength=16, dexterity=18)
    javelin = await _weapon(client, cid, "Giavellotto", None, properties=["thrown"], damage_dice="1d6")
    bow = await _weapon(client, cid, "Arco", None, weapon_type="ranged", damage_dice="1d8")
    rapier = await _weapon(client, cid, "Stocco", None, properties=["finesse"], damage_dice="1d8")
    before = {w: (await _attack(client, cid, w, **({"attack_mode": "thrown"} if w == javelin else {})))["damage_bonus"]
              for w in (javelin, bow, rapier)}
    await client.post(f"/characters/{cid}/turn/new")
    await _rage(client, cid)
    after = {w: (await _attack(client, cid, w, **({"attack_mode": "thrown"} if w == javelin else {})))["damage_bonus"]
             for w in (javelin, bow, rapier)}
    assert after == before


async def test_rage_gives_no_benefit_in_heavy_armor(client, monkeypatch):
    monkeypatch.setattr("api.services.d20.random.randint", lambda a, b: 10)  # svantaggio: il secondo d20 è fisso, il colpo riesce
    cid = await _barbarian(client, 5, strength=16)
    sword = await _weapon(client, cid)
    await _armor(client, cid, "heavy")
    before = (await _attack(client, cid, sword))["damage_bonus"]
    await _rage(client, cid)
    assert (await _attack(client, cid, sword))["damage_bonus"] == before
    full = await _full(client, cid)
    assert full["computed"]["resistances"] == []
    skill = await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 8})
    assert "feature:barbarian.rage" not in skill.json()["notes"]  # (lo svantaggio è dell'armatura senza addestramento)


@pytest.mark.parametrize("damage_type,taken", [("slashing", 5), ("piercing", 5), ("bludgeoning", 5), ("fire", 10), ("psychic", 10)])
async def test_rage_resists_physical_damage_only(client, damage_type, taken):
    cid = await _barbarian(client, 5)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 60})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 60})
    await _rage(client, cid)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": damage_type})
    assert r.json()["current_hit_points"] == 60 - taken


async def test_rage_advantage_on_strength_checks_and_saves_only(client):
    cid = await _barbarian(client, 5)
    await _rage(client, cid)
    athletics = (await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 8})).json()
    acrobatics = (await client.post(f"/characters/{cid}/skills/acrobatics/roll", json={"die": 8})).json()
    str_save = (await client.post(f"/characters/{cid}/saving_throws/strength/roll", json={"die": 8})).json()
    dex_save = (await client.post(f"/characters/{cid}/saving_throws/dexterity/roll", json={"die": 8})).json()
    assert [r["mode_applied"] for r in (athletics, acrobatics, str_save, dex_save)] == [
        "advantage", "normal", "advantage", "normal"]
    assert "feature:barbarian.rage" in athletics["notes"]


async def test_rage_ends_concentration_and_blocks_casting(client):
    cid = await _barbarian(client, 5)
    r = await client.post(f"/characters/{cid}/spells", json={
        "name": "Luce guida", "level": 0, "is_concentration": True, "duration": "Concentrazione, fino a 1 minuto"})
    spell = r.json()
    assert (await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={})).status_code == 200
    assert (await _full(client, cid))["concentrating_spell_id"] == spell["id"]
    await _rage(client, cid)
    assert (await _full(client, cid))["concentrating_spell_id"] is None
    check = await client.get(f"/characters/{cid}/spells/{spell['id']}/cast-check")
    assert "state_blocks_casting" in check.json()
    forced = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={})
    assert forced.status_code == 409 and "state_blocks_casting" in forced.json()["detail"]["warnings"]
    assert (await client.post(f"/characters/{cid}/spells/{spell['id']}/use",
                              json={"confirm": ["state_blocks_casting"]})).status_code == 200


async def test_rage_state_ends_with_a_rest_and_without_a_use_back(client):
    cid = await _barbarian(client, 5)
    await _rage(client, cid)
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "confirm_early": True})
    assert r.status_code == 200, r.text
    assert await _states(client, cid) == []
    assert (await _ability(client, cid, RAGE))["uses"] == 2


# ---------------------------------------------------------------------------
# Difesa Senza Armatura, Movimento Veloce, Istinto Ferino, Potenza Indomabile
# ---------------------------------------------------------------------------

async def test_unarmored_defense_uses_dex_and_con_and_yields_to_armor(client):
    cid = await _barbarian(client, 1, dexterity=14, constitution=16)
    assert (await _full(client, cid))["ac"] == 15
    await _armor(client, cid, "heavy", 16)
    assert (await _full(client, cid))["ac"] == 16


async def test_unarmored_defense_with_a_second_formula_takes_the_better_one_once(client):
    cid = await _barbarian(client, 1, dexterity=14, constitution=16, wisdom=18)
    r = await client.post(f"/characters/{cid}/ac/unarmored-defense", json={"ability": "wisdom"})  # il Monaco
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["ac"] == 16  # 10 + DES 2 + SAG 4, non 10 + 2 + 3 + 4


@pytest.mark.parametrize("level,speed", [(4, 30), (5, 40), (20, 40)])
async def test_fast_movement(client, level, speed):
    cid = await _barbarian(client, level)
    assert (await _full(client, cid))["computed"]["speed"] == speed


async def test_fast_movement_not_in_heavy_armor(client):
    cid = await _barbarian(client, 5, strength=18)
    await _armor(client, cid, "heavy")
    assert (await _full(client, cid))["computed"]["speed"] == 30


async def test_feral_instinct_advantage_on_initiative(client):
    early, late = await _barbarian(client, 6), await _barbarian(client, 7)
    assert (await client.post(f"/characters/{early}/dice/initiative", json={"die": 9})).json()["mode_applied"] == "normal"
    assert (await client.post(f"/characters/{late}/dice/initiative", json={"die": 9})).json()["mode_applied"] == "advantage"


async def test_feral_instinct_surprised_barbarian_acts_only_after_raging(client, test_session_factory):
    cid = await _barbarian(client, 7)
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == cid))).scalar_one()
        char.turn_state = {"surprised": True}
        await s.commit()
    assert (await _full(client, cid))["computed"]["incapacitated"] is True
    assert (await _rage(client, cid)).status_code == 200
    full = await _full(client, cid)
    assert full["computed"]["incapacitated"] is False and full["computed"]["surprised"] is False
    # chi non ha l'Istinto Ferino resta sorpreso anche in ira
    other = await _barbarian(client, 6)
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == other))).scalar_one()
        char.turn_state = {"surprised": True}
        await s.commit()
    await _rage(client, other)
    assert (await _full(client, other))["computed"]["incapacitated"] is True


async def test_indomitable_might_raises_low_strength_checks_to_the_score(client):
    cid = await _barbarian(client, 18, strength=20)
    low = await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 1})
    assert low.json()["total"] >= 20
    plain = await _barbarian(client, 17, strength=20)
    assert (await client.post(f"/characters/{plain}/skills/athletics/roll", json={"die": 1})).json()["total"] < 20
    other = await client.post(f"/characters/{cid}/skills/acrobatics/roll", json={"die": 1})  # non è una prova di Forza
    assert other.json()["total"] < 20


async def test_primal_champion_adds_four_to_strength_and_constitution_with_cap_24(client):
    cid = await _barbarian(client, 19, strength=18, constitution=20)
    before = await _full(client, cid)
    scores = {a["name"]: a["value"] for a in before["ability_scores"]}
    r = await client.patch(f"/characters/{cid}/classes/{before['classes'][0]['id']}", json={"level": 20})
    assert r.status_code == 200, r.text
    after = await _full(client, cid)
    got = {a["name"]: a["value"] for a in after["ability_scores"]}
    assert (got["strength"], got["constitution"]) == (22, 24)  # 18 + 4; 20 + 4 al massimo 24
    assert scores["strength"] == 18
    # il 20° livello dà 7 + 5 (CON 20), poi CON 24 vale +2 al modificatore per ognuno dei 20 livelli
    assert after["hit_points"] == before["hit_points"] + (7 + 5) + 2 * 20
    down = await client.patch(f"/characters/{cid}/classes/{before['classes'][0]['id']}", json={"level": 19})
    got = {a["name"]: a["value"] for a in (await _full(client, cid))["ability_scores"]}
    assert (got["strength"], got["constitution"]) == (18, 20)


# ---------------------------------------------------------------------------
# Attacco Irruento, Percezione del Pericolo, Critico Brutale
# ---------------------------------------------------------------------------

async def test_reckless_attack_is_offered_on_the_first_melee_strength_attack_only(client):
    cid = await _barbarian(client, 5, strength=16, dexterity=10)
    sword = await _weapon(client, cid)
    bow = await _weapon(client, cid, "Arco", None, weapon_type="ranged")
    assert "barbarian.reckless_attack" in await _keys(client, cid, "attack", item_id=sword)
    assert "barbarian.reckless_attack" not in await _keys(client, cid, "attack", item_id=bow)
    await _attack(client, cid, sword)  # il primo attacco senza dichiararlo: non si può più
    assert "barbarian.reckless_attack" not in await _keys(client, cid, "attack", item_id=sword)


async def test_reckless_attack_gives_advantage_to_every_attack_of_the_turn_and_to_attackers(client):
    cid = await _barbarian(client, 5, strength=16, dexterity=10)
    sword = await _weapon(client, cid)
    first = await _attack(client, cid, sword, options=["barbarian.reckless_attack"])
    second = await _attack(client, cid, sword)
    assert first["mode_applied"] == "advantage" and second["mode_applied"] == "advantage"
    states = {s["key"]: s for s in await _states(client, cid)}
    assert states["reckless"]["rounds_left"] == 1 and states["reckless"]["data"]["others"] == ["barbarian.reckless_attack"]
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _attack(client, cid, sword))["mode_applied"] == "normal"  # nuovo turno: va deciso di nuovo
    await client.post(f"/characters/{cid}/rounds/tick")
    assert not [s for s in await _states(client, cid) if s["key"] == "reckless"]  # fino al suo turno successivo


async def test_reckless_attack_not_for_dexterity_attack_with_finesse(client):
    cid = await _barbarian(client, 5, strength=10, dexterity=18)
    rapier = await _weapon(client, cid, "Stocco", properties=["finesse"], damage_dice="1d8")
    assert "barbarian.reckless_attack" not in await _keys(client, cid, "attack", item_id=rapier)


async def test_danger_sense_option_on_dexterity_saves_unless_blinded_deafened_or_incapacitated(client):
    cid = await _barbarian(client, 2)
    assert "barbarian.danger_sense" in await _keys(client, cid, "save", ability="dexterity")
    assert "barbarian.danger_sense" not in await _keys(client, cid, "save", ability="strength")
    for condition in ("blinded", "deafened", "incapacitated"):
        await client.patch(f"/characters/{cid}/conditions", json={"conditions": {condition: True}})
        assert "barbarian.danger_sense" not in await _keys(client, cid, "save", ability="dexterity"), condition
        await client.patch(f"/characters/{cid}/conditions", json={"conditions": {condition: False}})
    r = await client.post(f"/characters/{cid}/saving_throws/dexterity/roll",
                          json={"die": 8, "options": ["barbarian.danger_sense"]})
    assert r.json()["mode_applied"] == "advantage"


@pytest.mark.parametrize("level,extra", [(8, 0), (9, 1), (13, 2), (17, 3)])
async def test_brutal_critical_extra_dice_on_melee_crits_only(client, level, extra):
    cid = await _barbarian(client, level, strength=16, dexterity=10)
    sword = await _weapon(client, cid, damage_dice="1d12")
    crit = await _attack(client, cid, sword, die=20)
    plain = await _attack(client, cid, sword, die=10)
    assert len(crit["damage_rolls"]) == 2 + extra and len(plain["damage_rolls"]) == 1
    bow = await _weapon(client, cid, "Arco", None, weapon_type="ranged", damage_dice="1d8")
    assert len((await _attack(client, cid, bow, die=20))["damage_rolls"]) == 2  # a distanza nessun dado in più


# ---------------------------------------------------------------------------
# Ira Implacabile
# ---------------------------------------------------------------------------

async def _hp(client, cid, current=40, maximum=40):
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": maximum})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": current})


async def _hit(client, cid, value):
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": value})
    assert r.status_code == 200, r.text
    return r.json()


async def test_relentless_rage_save_keeps_the_barbarian_up_at_one_hp(client, monkeypatch):
    monkeypatch.setattr("api.services.d20.random.randint", lambda a, b: 20)
    cid = await _barbarian(client, 11, constitution=14)
    await _hp(client, cid)
    await _rage(client, cid)
    body = await _hit(client, cid, 45)  # 5 oltre lo zero: niente morte istantanea
    assert body["zero_hp_save"]["dc"] == 10 and body["zero_hp_save"]["success"] is True
    assert body["current_hit_points"] == 1 and body["is_dead"] is False
    assert not (body["conditions"] or {}).get("unconscious")
    assert [s["key"] for s in body["active_states"]] == ["rage"]


async def test_relentless_rage_dc_grows_by_five_until_a_rest(client, monkeypatch):
    monkeypatch.setattr("api.services.d20.random.randint", lambda a, b: 20)
    cid = await _barbarian(client, 11, constitution=14)
    await _hp(client, cid)
    await _rage(client, cid)
    dcs = []
    for _ in range(3):
        dcs.append((await _hit(client, cid, 50))["zero_hp_save"]["dc"])
        await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 40})
    assert dcs == [10, 15, 20]
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "confirm_early": True})
    await client.post(f"/characters/{cid}/turn/new")
    await _rage(client, cid)
    assert (await _hit(client, cid, 50))["zero_hp_save"]["dc"] == 10


async def test_relentless_rage_failed_save_falls_as_usual_and_ends_the_rage(client, monkeypatch):
    monkeypatch.setattr("api.services.d20.random.randint", lambda a, b: 1)
    cid = await _barbarian(client, 11, constitution=10)
    await _hp(client, cid)
    await _rage(client, cid)
    body = await _hit(client, cid, 45)
    assert body["zero_hp_save"]["success"] is False and body["current_hit_points"] == 0
    assert body["conditions"]["unconscious"] is True and body["active_states"] == []


async def test_relentless_rage_not_on_instant_death_outside_rage_or_before_level_11(client, monkeypatch):
    monkeypatch.setattr("api.services.d20.random.randint", lambda a, b: 20)
    cid = await _barbarian(client, 11)
    await _hp(client, cid)
    await _rage(client, cid)
    dead = await _hit(client, cid, 80)  # 40 oltre lo zero = il massimo
    assert dead["is_dead"] is True and dead.get("zero_hp_save") is None
    calm = await _barbarian(client, 11)
    await _hp(client, calm)
    assert (await _hit(client, calm, 45)).get("zero_hp_save") is None
    young = await _barbarian(client, 10)
    await _hp(client, young)
    await _rage(client, young)
    assert (await _hit(client, young, 45)).get("zero_hp_save") is None


# ---------------------------------------------------------------------------
# Cammino del Berserker
# ---------------------------------------------------------------------------

async def test_berserker_features_need_the_recognised_subclass(client):
    keys = lambda full: {a["feature_key"] for a in full["abilities"]}  # noqa: E731
    berserker = keys(await _full(client, await _barbarian(client, 14, BERSERKER)))
    unknown = keys(await _full(client, await _barbarian(client, 14, "Cammino Sconosciuto")))
    assert {"barbarian.mindless_rage", "barbarian.intimidating_presence", "barbarian.retaliation"} <= berserker
    assert not {k for k in unknown if k.startswith("barbarian.") and k.split(".")[1] in {
        "frenzy", "mindless_rage", "intimidating_presence", "retaliation"}}
    assert "barbarian.rage" in unknown


async def test_frenzy_is_chosen_when_entering_rage_and_costs_exhaustion_when_it_ends(client):
    cid = await _barbarian(client, 3, BERSERKER)
    rage = await _ability(client, cid, RAGE)
    assert [t["key"] for t in rage["use_toggles"]] == ["frenzy"]
    assert (await _rage(client, cid, frenzy=True)).json()["state"]["data"]["frenzy"] is True
    sword = await _weapon(client, cid)
    assert "barbarian.frenzy_attack" not in await _keys(client, cid, "attack", item_id=sword)  # l'ira ha speso il bonus
    await client.post(f"/characters/{cid}/turn/new")
    assert "barbarian.frenzy_attack" in await _keys(client, cid, "attack", item_id=sword)
    end = await client.delete(f"/characters/{cid}/active-states/rage")
    assert end.status_code == 200
    assert (await _full(client, cid))["conditions"]["exhaustion"] == 1


async def test_rage_without_frenzy_leaves_no_exhaustion_and_no_frenzy_attack(client):
    cid = await _barbarian(client, 3, BERSERKER)
    sword = await _weapon(client, cid)
    await _rage(client, cid)
    assert "barbarian.frenzy_attack" not in await _keys(client, cid, "attack", item_id=sword)
    await client.delete(f"/characters/{cid}/active-states/rage")
    assert not (await _full(client, cid))["conditions"].get("exhaustion")


async def test_frenzy_attack_spends_the_bonus_action(client):
    cid = await _barbarian(client, 3, BERSERKER, strength=16)
    sword = await _weapon(client, cid)
    await _rage(client, cid, frenzy=True)
    await client.post(f"/characters/{cid}/turn/new")  # il bonus dell'ira è speso: nuovo turno
    await _attack(client, cid, sword, options=["barbarian.frenzy_attack"])
    assert (await _turn(client, cid))["bonus_used"] is True
    assert "barbarian.frenzy_attack" not in await _keys(client, cid, "attack", item_id=sword)


async def test_toggle_is_offered_only_to_the_berserker(client):
    cid = await _barbarian(client, 5, TOTEM)
    assert (await _ability(client, cid, RAGE))["use_toggles"] == []
    assert (await _rage(client, cid, frenzy=True)).json()["state"]["data"]["frenzy"] is False


async def test_mindless_rage_blocks_and_suspends_charm_and_fear_while_raging(client):
    cid = await _barbarian(client, 6, BERSERKER)
    sword = await _weapon(client, cid)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"frightened": True}})
    assert "condition:frightened" in await _keys(client, cid, "attack", item_id=sword)
    await _rage(client, cid)
    assert "condition:frightened" not in await _keys(client, cid, "attack", item_id=sword)  # sospesa
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"charmed": True}})
    assert not r.json()["conditions"].get("charmed")  # non si aggiunge
    await client.delete(f"/characters/{cid}/active-states/rage")
    assert "condition:frightened" in await _keys(client, cid, "attack", item_id=sword)  # finita l'ira, torna
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"charmed": True}})
    assert r.json()["conditions"]["charmed"] is True


async def test_no_mindless_rage_before_level_6(client):
    cid = await _barbarian(client, 5, BERSERKER)
    await _rage(client, cid)
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"charmed": True}})
    assert r.json()["conditions"]["charmed"] is True


async def test_intimidating_presence_computes_dc_and_keeps_the_target_effect(client):
    cid = await _barbarian(client, 10, BERSERKER, charisma=14)
    r = await client.post(f"/characters/{cid}/features/barbarian.intimidating_presence/use", json={})
    assert r.status_code == 200, r.text
    assert r.json()["targets"] == ["barbarian.intimidating_presence"]
    assert (await _turn(client, cid))["action_used"] is True
    preview = await client.get(f"/characters/{cid}/target-effects/barbarian.intimidating_presence")
    effect = preview.json()["result"]
    assert (effect["condition"], effect["save_ability"], effect["save_dc"]) == ("frightened", "wisdom", 8 + 4 + 2)
    assert effect["ends_at"] == {"anchor": "source", "edge": "end", "count": 1}
    again = await client.post(f"/characters/{cid}/features/barbarian.intimidating_presence/use", json={})
    assert again.status_code == 409  # l'azione è già spesa; per prolungare serve un'altra azione


async def test_retaliation_is_a_reaction_attack_after_taking_damage(client):
    cid = await _barbarian(client, 14, BERSERKER, strength=16)
    sword = await _weapon(client, cid)
    assert "barbarian.retaliation" not in await _keys(client, cid, "attack", item_id=sword)
    await _hit(client, cid, 3)
    assert "barbarian.retaliation" in await _keys(client, cid, "attack", item_id=sword)
    await _attack(client, cid, sword, options=["barbarian.retaliation"])
    assert (await _turn(client, cid))["reaction_used"] is True
    assert "barbarian.retaliation" not in await _keys(client, cid, "attack", item_id=sword)


# ---------------------------------------------------------------------------
# Cammino del Combattente Totemico
# ---------------------------------------------------------------------------

async def _spells(client, cid) -> dict[str, dict]:
    return {s["name"]: s for s in (await client.get(f"/characters/{cid}/spells")).json()}


async def _pick(client, cid, group, animal) -> dict:
    full = await _full(client, cid)
    choice = next(c for c in full["pending_choices"] if c.get("group") == group)
    assert {o["key"] for o in choice["options"]} == {"eagle", "wolf", "bear"}
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve",
                          json={"kind": "class_option", "options": [animal]})
    assert r.status_code == 200, r.text
    return r.json()


async def _keys_of(client, cid) -> set[str]:
    return {a["feature_key"] for a in (await _full(client, cid))["abilities"]}


async def test_totem_choices_are_pending_at_3_6_and_14(client):
    cid = await _barbarian(client, 14, TOTEM)
    groups = {c["group"] for c in (await _full(client, cid))["pending_choices"] if c.get("kind") == "class_option"}
    assert groups == {"totem_spirit", "totem_aspect", "totem_attunement"}
    low = await _barbarian(client, 5, TOTEM)
    assert {c["group"] for c in (await _full(client, low))["pending_choices"] if c.get("kind") == "class_option"} == {
        "totem_spirit"}


async def test_totem_animal_choice_activates_only_that_animal(client):
    cid = await _barbarian(client, 3, TOTEM)
    assert not {k for k in await _keys_of(client, cid) if "totem_" in k}
    await _pick(client, cid, "totem_spirit", "wolf")
    keys = await _keys_of(client, cid)
    assert "barbarian.totem_wolf" in keys and not {"barbarian.totem_eagle", "barbarian.totem_bear"} & keys


async def test_spirit_seeker_and_spirit_walker_grant_ritual_only_spells(client):
    cid = await _barbarian(client, 3, TOTEM)
    spells = await _spells(client, cid)
    assert {"Percezione delle bestie", "Parlare con gli animali"} <= set(spells)
    assert all(spells[n]["always_prepared"] and spells[n]["is_ritual"] for n in ("Percezione delle bestie", "Parlare con gli animali"))
    assert "Comunione con la natura" not in spells
    speak = spells["Parlare con gli animali"]
    assert "ritual_only" in (await client.get(f"/characters/{cid}/spells/{speak['id']}/cast-check")).json()
    assert "ritual_only" not in (await client.get(
        f"/characters/{cid}/spells/{speak['id']}/cast-check", params={"ritual": True})).json()
    assert (await _full(client, cid))["spellcasting"]["ritual_only_spell_ids"] == sorted(
        s["id"] for s in spells.values())
    done = await client.post(f"/characters/{cid}/spells/{speak['id']}/use", json={"as_ritual": True})
    assert done.status_code == 200, done.text
    walker = await _barbarian(client, 10, TOTEM)
    assert "Comunione con la natura" in await _spells(client, walker)


async def test_ritual_spell_from_another_source_is_not_ritual_only(client):
    cid = await _barbarian(client, 3, TOTEM)
    await client.post(f"/characters/{cid}/classes", json={"class_name": "druid", "level": 1, "hit_die": 8})
    own = (await client.post(f"/characters/{cid}/spells", json={
        "name": "Altro rituale", "level": 1, "is_ritual": True})).json()
    assert "ritual_only" not in (await client.get(f"/characters/{cid}/spells/{own['id']}/cast-check")).json()


async def test_eagle_dash_as_bonus_action_needs_rage_and_no_heavy_armor(client):
    cid = await _barbarian(client, 5, TOTEM)
    await _pick(client, cid, "totem_spirit", "eagle")
    dash = "barbarian.totem_eagle"
    out = await client.post(f"/characters/{cid}/features/{dash}/use", json={})
    assert out.status_code == 409 and out.json()["detail"]["code"] == "feature_unavailable"
    await _rage(client, cid)
    await client.post(f"/characters/{cid}/turn/new")
    ok = await client.post(f"/characters/{cid}/features/{dash}/use", json={})
    assert ok.status_code == 200 and (await _turn(client, cid))["bonus_used"] is True
    await client.post(f"/characters/{cid}/turn/new")
    await _armor(client, cid, "heavy")
    assert (await client.post(f"/characters/{cid}/features/{dash}/use", json={})).status_code == 409


async def test_rage_state_lists_the_effects_that_act_on_others(client):
    cid = await _barbarian(client, 3, TOTEM)
    await _pick(client, cid, "totem_spirit", "wolf")
    assert (await _rage(client, cid)).json()["state"]["data"]["others"] == ["barbarian.totem_wolf"]
    bear = await _barbarian(client, 3, TOTEM)
    await _pick(client, bear, "totem_spirit", "bear")
    assert (await _rage(client, bear)).json()["state"]["data"]["others"] == []


@pytest.mark.parametrize("damage_type,taken", [("slashing", 5), ("fire", 5), ("poison", 5), ("necrotic", 5), ("psychic", 10)])
async def test_bear_resists_everything_but_psychic_in_rage(client, damage_type, taken):
    cid = await _barbarian(client, 3, TOTEM)
    await _pick(client, cid, "totem_spirit", "bear")
    await _hp(client, cid, 60, 60)
    await _rage(client, cid)
    assert (await _hit_typed(client, cid, damage_type))["current_hit_points"] == 60 - taken


async def _hit_typed(client, cid, damage_type):
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": damage_type})
    return r.json()


async def test_bear_resistance_does_not_apply_outside_rage(client):
    cid = await _barbarian(client, 3, TOTEM)
    await _pick(client, cid, "totem_spirit", "bear")
    await _hp(client, cid, 60, 60)
    assert (await _hit_typed(client, cid, "fire"))["current_hit_points"] == 50


async def test_bear_aspect_doubles_carrying_capacity_and_helps_strength_checks(client):
    cid = await _barbarian(client, 6, TOTEM, strength=16)
    base = (await _full(client, cid))["carry_capacity"]
    await _pick(client, cid, "totem_aspect", "bear")
    assert (await _full(client, cid))["carry_capacity"] == base * 2
    assert "barbarian.aspect_bear_check" in await _keys(client, cid, "skill", skill="athletics")
    assert "barbarian.aspect_bear_check" not in await _keys(client, cid, "skill", skill="acrobatics")
    r = await client.post(f"/characters/{cid}/skills/athletics/roll",
                          json={"die": 8, "options": ["barbarian.aspect_bear_check"]})
    assert r.json()["mode_applied"] == "advantage"


async def test_bear_aspect_is_not_rage_dependent_unlike_the_other_aspects(client):
    cid = await _barbarian(client, 6, TOTEM)
    await _pick(client, cid, "totem_aspect", "eagle")
    assert "barbarian.aspect_eagle" in await _keys_of(client, cid)
    assert (await _full(client, cid))["carry_capacity"] == (await _full(client, await _barbarian(client, 6)))["carry_capacity"]


async def test_eagle_attunement_flies_at_walking_speed_only_while_raging(client):
    cid = await _barbarian(client, 14, TOTEM)
    await _pick(client, cid, "totem_spirit", "wolf")
    await _pick(client, cid, "totem_aspect", "wolf")
    await _pick(client, cid, "totem_attunement", "eagle")
    assert (await _full(client, cid))["computed"]["fly_speed"] is None
    await _rage(client, cid)
    assert (await _full(client, cid))["computed"]["fly_speed"] == 40
    await _armor(client, cid, "heavy")
    # Il manuale lega l'armatura pesante all'Ira e all'Aquila 3, non a questo privilegio: vola alla velocità a terra
    # di quel momento (30: Movimento Veloce cede all'armatura pesante).
    full = await _full(client, cid)
    assert full["computed"]["fly_speed"] == full["computed"]["speed"] == 30


async def test_wolf_attunement_offers_a_prone_effect_after_a_melee_hit_in_rage(client):
    cid = await _barbarian(client, 14, TOTEM, strength=16)
    for group in ("totem_spirit", "totem_aspect"):
        await _pick(client, cid, group, "eagle")
    await _pick(client, cid, "totem_attunement", "wolf")
    sword = await _weapon(client, cid)
    key = "barbarian.attunement_wolf_knock"
    assert key not in await _keys(client, cid, "attack", item_id=sword)
    await _rage(client, cid)
    await client.post(f"/characters/{cid}/turn/new")
    opts = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": sword})).json()
    assert [(o["key"], o["phase"], o["slot"]) for o in opts if o["key"] == key] == [(key, "after_hit", "bonus")]


async def test_bear_attunement_lists_its_effect_under_the_rage(client):
    cid = await _barbarian(client, 14, TOTEM)
    for group in ("totem_spirit", "totem_aspect"):
        await _pick(client, cid, group, "eagle")
    await _pick(client, cid, "totem_attunement", "bear")
    assert "barbarian.attunement_bear" in (await _rage(client, cid)).json()["state"]["data"]["others"]


async def test_totem_features_are_not_granted_to_an_unrecognised_subclass(client):
    cid = await _barbarian(client, 14, "Cammino dei Totem Strani")
    keys = await _keys_of(client, cid)
    assert not {k for k in keys if "totem" in k or "spirit" in k or "aspect" in k}
    assert not [c for c in (await _full(client, cid))["pending_choices"] if c.get("kind") == "class_option"]


# ---------------------------------------------------------------------------
# Multiclasse e competenze
# ---------------------------------------------------------------------------

def test_multiclass_and_class_proficiencies_from_the_class_table():
    from core.rules.proficiencies import class_proficiencies

    first = class_proficiencies("2014", "barbarian", False)
    assert set(first.armor) == {"light", "medium", "shields"} and set(first.weapons) == {"simple", "martial"}
    assert set(first.saves) == {"strength", "constitution"} and first.skills_count == 2
    multi = class_proficiencies("2014", "barbarian", True)
    assert multi.armor == ("shields",) and set(multi.weapons) == {"simple", "martial"}
    assert not multi.saves and multi.skills_count == 0


async def test_barbarian_added_as_second_class_keeps_one_rage_and_extra_attack_at_two(client):
    cid = await _barbarian(client, 5)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 3, "hit_die": 6})
    assert r.status_code == 201
    keys = [a["feature_key"] for a in (await _full(client, cid))["abilities"]]
    assert keys.count(RAGE) == 1


async def test_beyond_totem_options_find_the_catalog_choices(test_session_factory):
    from api.services.ddb_import import apply_class_options
    from api.services.ddb_import import ImportReport
    from core.rules.sample_characters import build_rules_character

    async with test_session_factory() as s:
        spec = {"name": "x", "edition": "2014", "classes": [("Barbaro", 14, TOTEM, 12)]}
        char = await build_rules_character(s, spec, 1)
        report = ImportReport()
        apply_class_options(char, [{"class_index": 0, "name": n} for n in ("Eagle", "Wolf", "Bear", "Otter")], report, "it")
        options = char.classes[0].options
        assert options == {"totem_spirit": ["eagle"], "totem_aspect": ["wolf"], "totem_attunement": ["bear"]}
        assert [e.name for e in report.approximated] == ["Otter"]
