"""Monaco 2014 (Task 24): i privilegi del ki e le conferme al tiro: Raffica di Colpi, Arti Marziali (colpo extra), Difesa
Paziente, Passo del Vento, Deviare Proiettili, Caduta Lenta, Colpo Stordente, Elusione, Mente Lucida, Anima Adamantina,
Corpo Vuoto e Perfezione Interiore."""
from __future__ import annotations

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, setup_full_encounter
from tests.integration._telegram_stub import install_fake_telegram
from tests.integration.rules.test_2014_bard import _ability, _full, _roll_keys, _use
from tests.integration.rules.test_2014_monk import KI, SHIELD, ARMOR, _equip, _monk, _turn

FLURRY, STRIKE, BONUS = "monk.flurry_of_blows", "monk.flurry_strike", "monk.martial_arts_bonus"
PATIENT, STEP = "monk.patient_defense", "monk.step_of_the_wind"
DEFLECT, THROW, SLOW_FALL = "monk.deflect_missiles", "monk.deflect_missiles_throw", "monk.slow_fall"
STUN, EVASION, EVASION_OK, EVASION_KO = "monk.stunning_strike", "monk.evasion", "monk.evasion_success", "monk.evasion_failed"
STILLNESS, DIAMOND, EMPTY, PERFECT = "monk.stillness_of_mind", "monk.diamond_soul", "monk.empty_body", "monk.perfect_self"


async def _ki(client, cid) -> int:
    return (await _ability(client, cid, KI))["uses"]


async def _set_ki(client, cid, uses) -> None:
    ability = await _ability(client, cid, KI)
    await client.patch(f"/characters/{cid}/abilities/{ability['id']}", json={"uses": uses})


async def _strike(client, cid, *options, die=10, **body):
    return await client.post(f"/characters/{cid}/attack/unarmed", json={"die": die, "options": list(options), **body})


async def _states(client, cid) -> dict[str, dict]:
    return {s["key"]: s for s in (await _full(client, cid))["active_states"] or []}


async def _shortsword(client, cid) -> int:
    meta = {"damage_dice": "1d6", "weapon_type": "melee", "properties": ["finesse", "light"], "weapon_category": "martial",
            "damage_type": "piercing"}
    return (await _equip(client, cid, slot="main_hand", name="Spada corta", item_type="weapon", item_metadata=meta))["item_id"]


async def _heavy_weapon(client, cid) -> int:
    meta = {"damage_dice": "1d12", "weapon_type": "melee", "properties": ["heavy", "two_handed"], "weapon_category": "martial",
            "damage_type": "slashing"}
    return (await _equip(client, cid, slot="main_hand", name="Ascia bipenne", item_type="weapon", item_metadata=meta))["item_id"]


async def _bow(client, cid) -> int:
    meta = {"damage_dice": "1d8", "weapon_type": "ranged", "properties": ["ammunition"], "weapon_category": "martial",
            "damage_type": "piercing"}
    return (await _equip(client, cid, slot="main_hand", name="Arco lungo", item_type="weapon", item_metadata=meta))["item_id"]


def _fixed(monkeypatch, value: int) -> None:
    monkeypatch.setattr("random.randint", lambda a, b: min(value, b))


async def _conditions(client, cid, **conditions):
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": conditions})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Arti Marziali: il colpo senz'armi extra
# ---------------------------------------------------------------------------

async def test_the_bonus_strike_appears_only_after_the_attack_action(client):
    cid = await _monk(client, 1)
    assert BONUS not in await _roll_keys(client, cid, "attack")
    assert (await _strike(client, cid)).status_code == 200
    assert BONUS in await _roll_keys(client, cid, "attack")


async def test_the_bonus_strike_spends_the_bonus_action_and_not_the_attacks_of_the_action(client):
    cid = await _monk(client, 1)
    await _strike(client, cid)
    r = await _strike(client, cid, BONUS)
    assert r.status_code == 200, r.text
    turn = await _turn(client, cid)
    assert (turn["bonus_used"], turn["action_attacks"], turn["attacks_made"]) == (True, 1, 2)
    assert BONUS not in await _roll_keys(client, cid, "attack")
    again = await _strike(client, cid, BONUS)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "option_unavailable"


async def test_the_bonus_strike_needs_a_free_bonus_action_and_costs_nothing_otherwise(client):
    cid = await _monk(client, 1)
    await _strike(client, cid)
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus"})
    assert BONUS not in await _roll_keys(client, cid, "attack")
    r = await _strike(client, cid, BONUS)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"
    assert (await _turn(client, cid))["attacks_made"] == 1


async def test_the_bonus_strike_follows_a_monk_weapon_attack_but_not_another_weapon(client):
    cid = await _monk(client, 1, dexterity=16)
    sword = await _shortsword(client, cid)
    assert (await client.post(f"/characters/{cid}/items/{sword}/attack", json={"die": 10})).status_code == 200
    await client.patch(f"/characters/{cid}/items/{sword}", json={"is_equipped": False})
    assert BONUS in await _roll_keys(client, cid, "attack")
    other = await _monk(client, 1, dexterity=16)
    axe = await _heavy_weapon(client, other)
    assert (await client.post(f"/characters/{other}/items/{axe}/attack", json={"die": 10})).status_code == 200
    await client.patch(f"/characters/{other}/items/{axe}", json={"is_equipped": False})
    assert BONUS not in await _roll_keys(client, other, "attack")


async def test_the_bonus_strike_is_for_unarmed_attacks_without_armor_or_shield(client):
    cid = await _monk(client, 1, dexterity=16)
    await _strike(client, cid)
    sword = await _shortsword(client, cid)
    assert BONUS not in await _roll_keys(client, cid, "attack", item_id=sword)
    await client.patch(f"/characters/{cid}/items/{sword}", json={"is_equipped": False})
    await _equip(client, cid, slot="off_hand", **SHIELD)
    assert BONUS not in await _roll_keys(client, cid, "attack")


# ---------------------------------------------------------------------------
# Raffica di Colpi
# ---------------------------------------------------------------------------

async def test_flurry_is_refused_before_the_attack_action_and_costs_nothing(client):
    cid = await _monk(client, 3)
    r = await _use(client, cid, FLURRY)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "feature_unavailable"
    assert await _ki(client, cid) == 3 and not (await _turn(client, cid))["bonus_used"]


async def test_flurry_after_the_attack_spends_one_ki_and_the_bonus_action(client):
    cid = await _monk(client, 3)
    await _strike(client, cid)
    assert (await _use(client, cid, FLURRY)).status_code == 200
    assert await _ki(client, cid) == 2 and (await _turn(client, cid))["bonus_used"] is True
    state = (await _states(client, cid))["flurry_of_blows"]
    assert state["data"]["charges"] == 2
    row = await _ability(client, cid, FLURRY)
    assert row["action_type"] == "bonus_action" and row["has_on_use"] is True


async def test_flurry_gives_two_unarmed_strikes_that_are_not_attacks_of_the_action(client):
    cid = await _monk(client, 3)  # un solo attacco per azione
    await _strike(client, cid)
    assert (await _strike(client, cid)).json()["detail"]["code"] == "attack_limit"
    await _use(client, cid, FLURRY)
    assert STRIKE in await _roll_keys(client, cid, "attack")
    for _ in range(2):
        r = await _strike(client, cid, STRIKE)
        assert r.status_code == 200, r.text
    turn = await _turn(client, cid)
    assert (turn["action_attacks"], turn["attacks_made"]) == (1, 3)
    assert STRIKE not in await _roll_keys(client, cid, "attack")
    third = await _strike(client, cid, STRIKE)
    assert third.status_code == 409 and third.json()["detail"]["code"] == "option_unavailable"
    assert "flurry_of_blows" not in await _states(client, cid)


async def test_flurry_strikes_are_unarmed_only(client):
    cid = await _monk(client, 3, dexterity=16)
    await _strike(client, cid)
    await _use(client, cid, FLURRY)
    sword = await _shortsword(client, cid)
    assert STRIKE not in await _roll_keys(client, cid, "attack", item_id=sword)


async def test_flurry_is_refused_without_ki_or_without_the_bonus_action_and_costs_nothing(client):
    cid = await _monk(client, 3)
    await _strike(client, cid)
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus"})
    r = await _use(client, cid, FLURRY)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "turn_slot_used" and await _ki(client, cid) == 3
    other = await _monk(client, 3)
    await _strike(client, other)
    await _set_ki(client, other, 0)
    r = await _use(client, other, FLURRY)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    assert not (await _turn(client, other))["bonus_used"]


async def test_flurry_works_in_armor_and_ends_with_the_new_turn(client):
    cid = await _monk(client, 3)
    await _equip(client, cid, **ARMOR)
    await _strike(client, cid)
    assert (await _use(client, cid, FLURRY)).status_code == 200
    await client.post(f"/characters/{cid}/turn/new")
    assert "flurry_of_blows" not in await _states(client, cid)
    assert STRIKE not in await _roll_keys(client, cid, "attack")


async def test_there_is_no_flurry_before_level_2(client):
    assert await _ability(client, await _monk(client, 1), FLURRY) is None


# ---------------------------------------------------------------------------
# Difesa Paziente, Passo del Vento
# ---------------------------------------------------------------------------

async def test_patient_defense_spends_one_ki_and_the_bonus_action_and_starts_the_dodge(client):
    cid = await _monk(client, 2)
    assert (await _use(client, cid, PATIENT)).status_code == 200
    assert await _ki(client, cid) == 1 and (await _turn(client, cid))["bonus_used"] is True
    state = (await _states(client, cid))["patient_defense"]
    assert state["rounds_left"] == 1 and "new_turn" in state["ends_on"] and state["data"]["others"] == [PATIENT]
    assert (await _ability(client, cid, PATIENT))["action_type"] == "bonus_action"


async def test_patient_defense_is_refused_without_the_bonus_action_or_ki_and_costs_nothing(client):
    cid = await _monk(client, 2)
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus"})
    r = await _use(client, cid, PATIENT)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "turn_slot_used" and await _ki(client, cid) == 2
    other = await _monk(client, 2)
    await _set_ki(client, other, 0)
    assert (await _use(client, other, PATIENT)).json()["detail"]["code"] == "no_uses"


async def test_patient_defense_ends_at_the_new_turn_and_when_incapacitated(client):
    cid = await _monk(client, 2)
    await _use(client, cid, PATIENT)
    await client.post(f"/characters/{cid}/turn/new")
    assert "patient_defense" not in await _states(client, cid)
    await _use(client, cid, PATIENT)
    await _conditions(client, cid, stunned=True)
    assert "patient_defense" not in await _states(client, cid)


async def test_patient_defense_is_visible_to_gm_and_group(client, test_session_factory, monkeypatch):
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)
    pc = (await client.post(f"/sessions/{sid}/encounter/start", json={})).json()["combatants"][0]
    as_user(PLAYER_ID)
    cid = pc["character_id"]
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "monk", "level": 2, "hit_die": 8})
    assert r.status_code == 201, r.text
    assert (await _use(client, cid, PATIENT)).status_code == 200
    for viewer in (GM_ID, PLAYER_ID):
        as_user(viewer)
        live = (await client.get(f"/sessions/{sid}/live")).json()
        states = next(c for c in live["encounter"]["combatants"] if c["kind"] == "pc")["active_states"]
        assert [o["key"] for s in states for o in s["others"]] == [PATIENT], viewer
        assert all(o["text"] and o["name"] for s in states for o in s["others"])
    as_user(PLAYER_ID)


async def test_step_of_the_wind_gives_the_chosen_action_as_a_bonus_action(client):
    for mode in ("dash", "disengage"):
        cid = await _monk(client, 2)
        row = await _ability(client, cid, STEP)
        assert [o["key"] for o in row["use_choices"][0]["options"]] == ["dash", "disengage"]
        r = await _use(client, cid, STEP, params={"mode": mode})
        assert r.status_code == 200, r.text
        assert await _ki(client, cid) == 1 and (await _turn(client, cid))["bonus_used"] is True
        state = (await _states(client, cid))["step_of_the_wind"]
        assert state["data"]["mode"] == mode and state["data"]["jump_doubled"] is True and state["rounds_left"] == 1


async def test_step_of_the_wind_refuses_a_missing_choice_and_costs_nothing(client):
    cid = await _monk(client, 2)
    for params in (None, {"mode": "fly"}):
        r = await _use(client, cid, STEP, params=params)
        assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice"
    assert await _ki(client, cid) == 2 and not (await _turn(client, cid))["bonus_used"]
    await client.post(f"/characters/{cid}/turn/new")
    await _use(client, cid, STEP, params={"mode": "dash"})
    await client.post(f"/characters/{cid}/turn/new")
    assert "step_of_the_wind" not in await _states(client, cid)


# ---------------------------------------------------------------------------
# Deviare Proiettili, Caduta Lenta
# ---------------------------------------------------------------------------

async def test_deflect_missiles_is_a_reaction_on_damage_from_level_3(client):
    assert DEFLECT not in await _roll_keys(client, await _monk(client, 2), "damage_taken", damage_type="piercing")
    cid = await _monk(client, 3)
    options = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "damage_taken", "damage_type": "piercing"})).json()
    deflect = next(o for o in options if o["key"] == DEFLECT)
    assert deflect["slot"] == "reaction" and deflect["phase"] == "damage_in"


async def test_deflect_missiles_reduces_the_damage_by_the_die_plus_dexterity_plus_the_level(client, monkeypatch):
    cid = await _monk(client, 5, dexterity=16)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 60})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 60})
    _fixed(monkeypatch, 6)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20, "damage_type": "piercing", "options": [DEFLECT]})
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == 60 - (20 - (6 + 3 + 5))
    assert r.json()["option_result"]["damage_after"] == 6
    assert (await _turn(client, cid))["reaction_used"] is True and await _ki(client, cid) == 5
    assert DEFLECT not in await _roll_keys(client, cid, "damage_taken", damage_type="piercing")
    assert DEFLECT not in [o["key"] for o in r.json()["reactions"]]  # non è un attacco in reazione al danno


async def test_deflect_missiles_never_goes_below_zero_damage(client, monkeypatch):
    cid = await _monk(client, 5, dexterity=16)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 60})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 60})
    _fixed(monkeypatch, 10)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 5, "damage_type": "piercing", "options": [DEFLECT]})
    assert r.json()["current_hit_points"] == 60 and r.json()["option_result"]["damage_after"] == 0


async def test_the_throw_back_needs_a_missile_caught_at_zero_damage_and_is_an_unarmed_throw(client, monkeypatch):
    cid = await _monk(client, 5, dexterity=16)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 60})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 60})
    bow = await _bow(client, cid)
    assert THROW not in await _roll_keys(client, cid, "attack")
    _fixed(monkeypatch, 3)
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 40, "damage_type": "piercing", "options": [DEFLECT]})
    assert THROW not in await _roll_keys(client, cid, "attack")  # il danno non è sceso a 0
    await client.post(f"/characters/{cid}/turn/new")
    _fixed(monkeypatch, 10)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 5, "damage_type": "piercing", "options": [DEFLECT]})
    offers = r.json()["reactions"]  # con l'arco impugnato la proposta c'è lo stesso: il lancio non usa l'arma
    assert [o["key"] for o in offers] == [THROW] and offers[0]["ranged_unarmed"] is True
    assert "deflected_missile" in await _states(client, cid)
    assert THROW in await _roll_keys(client, cid, "attack")
    assert THROW not in await _roll_keys(client, cid, "attack", item_id=bow)  # mai con l'oggetto impugnato


async def test_the_throw_back_has_its_own_profile_dexterity_martial_arts_die_proficiency_and_costs_one_ki(client, monkeypatch):
    cid = await _monk(client, 5, strength=8, dexterity=16)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 60})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 60})
    _fixed(monkeypatch, 10)
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 5, "damage_type": "piercing", "options": [DEFLECT]})
    ki = await _ki(client, cid)
    # senz'armi, e con FOR 8: Destrezza +3 e competenza +3 al colpire, 1d6 +3 al danno
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10, "options": [THROW]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["to_hit_bonus"], body["damage_dice"], body["damage_bonus"]) == (3 + 3, "1d6", 3)
    assert not body.get("proficiency_warning") and await _ki(client, cid) == ki - 1
    assert "deflected_missile" not in await _states(client, cid)
    assert (await _turn(client, cid))["action_attacks"] == 0  # non è un attacco dell'azione Attacco
    again = await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10, "options": [THROW]})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "option_unavailable"


async def test_the_throw_back_is_ranged_so_it_never_offers_the_stunning_strike(client, monkeypatch):
    cid = await _monk(client, 5, dexterity=16)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 60})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 60})
    _fixed(monkeypatch, 10)
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 5, "damage_type": "piercing", "options": [DEFLECT]})
    hit = await _hit(client, cid, options=[THROW])
    assert (await _damage(client, cid, hit, STUN)).status_code == 409  # il Colpo Stordente vale solo in mischia
    assert (await _damage(client, cid, hit)).status_code == 200


async def test_the_throw_back_has_no_invented_damage_type_and_is_not_a_magic_strike(client, monkeypatch):
    cid = await _monk(client, 6, dexterity=16)  # dal 6° i colpi senz'armi sono magici: il proiettile no
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 60})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 60})
    _fixed(monkeypatch, 10)
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 5, "damage_type": "piercing", "options": [DEFLECT]})
    body = (await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10, "options": [THROW]})).json()
    assert body.get("damage_type") is None and not body.get("is_magic")
    plain = (await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10, "confirm_extra_attack": True})).json()
    assert plain["damage_type"] == "bludgeoning" and plain["is_magic"] is True  # il colpo senz'armi resta com'era


async def test_the_listing_of_a_thrown_unarmed_attack_is_ranged(client, monkeypatch):
    cid = await _monk(client, 5, dexterity=16)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 60})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 60})
    assert STUN in await _roll_keys(client, cid, "attack")
    assert STUN not in await _roll_keys(client, cid, "attack", attack_mode="thrown")  # il Colpo Stordente è solo in mischia


async def test_the_throw_back_with_a_sword_in_hand_ignores_the_sword(client, monkeypatch):
    cid = await _monk(client, 5, strength=8, dexterity=16)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 60})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 60})
    await _equip(client, cid, slot="main_hand", name="Spada lunga", item_type="weapon", item_metadata={
        "damage_dice": "1d8", "weapon_type": "melee", "properties": ["versatile"], "weapon_category": "martial"})
    _fixed(monkeypatch, 10)
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 5, "damage_type": "piercing", "options": [DEFLECT]})
    body = (await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10, "options": [THROW]})).json()
    assert (body["to_hit_bonus"], body["damage_dice"], body["damage_bonus"]) == (6, "1d6", 3)


async def test_the_throw_back_is_refused_without_ki(client, monkeypatch):
    cid = await _monk(client, 5, dexterity=16)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 60})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 60})
    _fixed(monkeypatch, 10)
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 5, "damage_type": "piercing", "options": [DEFLECT]})
    await _set_ki(client, cid, 0)
    assert THROW not in await _roll_keys(client, cid, "attack")


async def test_slow_fall_cuts_five_times_the_level_and_spends_the_reaction(client):
    assert SLOW_FALL not in await _roll_keys(client, await _monk(client, 3), "damage_taken", damage_type="bludgeoning")
    cid = await _monk(client, 6)
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 60})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 60})
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 40, "damage_type": "bludgeoning", "options": [SLOW_FALL]})
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == 60 - 10 and (await _turn(client, cid))["reaction_used"] is True
    assert SLOW_FALL not in [o["key"] for o in r.json()["reactions"]]
    again = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 5, "options": [SLOW_FALL]})
    assert again.status_code == 409


# ---------------------------------------------------------------------------
# Colpo Stordente
# ---------------------------------------------------------------------------

async def _hit(client, cid, *, item=None, die=15, **body) -> dict:
    path = f"/characters/{cid}/attack/unarmed" if item is None else f"/characters/{cid}/items/{item}/attack"
    r = await client.post(path, json={"die": die, "defer_damage": True, "confirm_extra_attack": True, **body})
    assert r.status_code == 200, r.text
    return r.json()


async def _damage(client, cid, hit, *options, **body):
    return await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": list(options), **body})


async def test_stunning_strike_is_offered_on_a_melee_hit_from_level_5(client):
    low = await _monk(client, 4)
    assert STUN not in await _roll_keys(client, low, "attack")
    cid = await _monk(client, 5, dexterity=16)
    options = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack"})).json()
    assert next(o for o in options if o["key"] == STUN)["phase"] == "after_hit"
    sword = await _shortsword(client, cid)
    assert STUN in await _roll_keys(client, cid, "attack", item_id=sword)
    await client.patch(f"/characters/{cid}/items/{sword}", json={"is_equipped": False})
    bow = await _bow(client, cid)
    assert STUN not in await _roll_keys(client, cid, "attack", item_id=bow)


async def test_stunning_strike_spends_one_ki_and_keeps_a_stun_for_the_target_with_the_ki_dc(client):
    cid = await _monk(client, 5, wisdom=16, dexterity=16)  # competenza +3, Saggezza +3
    hit = await _hit(client, cid)
    body = (await _damage(client, cid, hit, STUN)).json()
    assert await _ki(client, cid) == 4 and body["option_result"]["targets"] == [STUN]
    assert "CD 14" in body["option_result"]["effects"][0]["it"] and "DC 14" in body["option_result"]["effects"][0]["en"]
    effect = (await client.get(f"/characters/{cid}/target-effects/{STUN}")).json()["result"]
    assert (effect["condition"], effect["save_ability"], effect["save_dc"]) == ("stunned", "constitution", 14)
    assert effect["ends_at"] == {"anchor": "source", "edge": "end", "count": 1}
    assert (await _turn(client, cid))["bonus_used"] is False  # nessuna azione: è un colpo a segno


async def test_stunning_strike_has_no_limit_per_turn_but_needs_ki_and_a_hit(client):
    cid = await _monk(client, 5, dexterity=16)
    for _ in range(2):
        hit = await _hit(client, cid)
        assert (await _damage(client, cid, hit, STUN)).status_code == 200
    assert await _ki(client, cid) == 3
    await _set_ki(client, cid, 0)
    hit = await _hit(client, cid)
    r = await _damage(client, cid, hit, STUN)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"
    miss = await _hit(client, cid, die=1)
    assert miss.get("attack_id") is None  # un mancato non ha danno da aspettare: non c'è nulla su cui confermare
    assert (await client.post(f"/characters/{cid}/attack/deadbeef/damage", json={"options": [STUN]})).status_code == 404


async def test_stunning_strike_works_with_a_melee_weapon(client):
    cid = await _monk(client, 5, dexterity=16)
    sword = await _shortsword(client, cid)
    hit = await _hit(client, cid, item=sword)
    assert (await _damage(client, cid, hit, STUN)).status_code == 200 and await _ki(client, cid) == 4


# ---------------------------------------------------------------------------
# Elusione
# ---------------------------------------------------------------------------

async def _dex_save(client, cid, *options, die=10):
    r = await client.post(f"/characters/{cid}/saving_throws/dexterity/roll", json={"die": die, "options": list(options)})
    assert r.status_code == 200, r.text
    return r.json()


async def _hurt(client, cid, value, *options):
    return await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": value, "options": list(options)})


async def _full_hp(client, cid, hp=60):
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": hp})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": hp})


async def test_evasion_is_asked_on_dexterity_saves_from_level_7_only(client):
    assert EVASION not in await _roll_keys(client, await _monk(client, 6), "save", ability="dexterity")
    cid = await _monk(client, 7)
    assert EVASION in await _roll_keys(client, cid, "save", ability="dexterity")
    assert EVASION not in await _roll_keys(client, cid, "save", ability="wisdom")


async def test_evasion_takes_no_damage_on_a_success_and_half_on_a_failure(client):
    cid = await _monk(client, 7)
    await _full_hp(client, cid)
    body = await _dex_save(client, cid, EVASION)
    assert "Elusione" in body["option_result"]["effects"][0]["it"]
    keys = await _roll_keys(client, cid, "damage_taken")
    assert EVASION_OK in keys and EVASION_KO in keys
    r = await _hurt(client, cid, 20, EVASION_OK)
    assert r.json()["current_hit_points"] == 60
    assert "evasion" not in await _states(client, cid) and EVASION_OK not in await _roll_keys(client, cid, "damage_taken")
    await _dex_save(client, cid, EVASION)
    r = await _hurt(client, cid, 20, EVASION_KO)
    assert r.json()["current_hit_points"] == 50


async def test_evasion_damage_options_need_the_confirmed_save_and_do_not_survive_the_new_turn(client):
    cid = await _monk(client, 7)
    await _full_hp(client, cid)
    assert EVASION_OK not in await _roll_keys(client, cid, "damage_taken")
    r = await _hurt(client, cid, 20, EVASION_OK)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"
    await _dex_save(client, cid, EVASION)
    await client.post(f"/characters/{cid}/turn/new")
    assert EVASION_OK not in await _roll_keys(client, cid, "damage_taken")


async def test_evasion_does_not_work_while_incapacitated(client):
    cid = await _monk(client, 7)
    await _conditions(client, cid, incapacitated=True)
    assert EVASION not in await _roll_keys(client, cid, "save", ability="dexterity")


# ---------------------------------------------------------------------------
# Mente Lucida
# ---------------------------------------------------------------------------

async def test_stillness_of_mind_removes_the_chosen_condition_with_an_action_and_no_cost(client):
    cid = await _monk(client, 7)
    await _conditions(client, cid, charmed=True, frightened=True)
    row = await _ability(client, cid, STILLNESS)
    assert [o["key"] for o in row["use_choices"][0]["options"]] == ["charmed", "frightened"]
    r = await _use(client, cid, STILLNESS, params={"condition": "charmed"})
    assert r.status_code == 200, r.text
    conditions = (await _full(client, cid))["conditions"]
    assert not conditions.get("charmed") and conditions["frightened"] is True
    assert (await _turn(client, cid))["action_used"] is True and await _ki(client, cid) == 7


async def test_stillness_of_mind_offers_only_the_conditions_the_monk_has_and_costs_nothing_when_refused(client):
    cid = await _monk(client, 7)
    r = await _use(client, cid, STILLNESS, params={"condition": "charmed"})
    assert r.status_code in (409, 422)
    assert not (await _turn(client, cid))["action_used"]
    await _conditions(client, cid, frightened=True)
    row = await _ability(client, cid, STILLNESS)
    assert [o["key"] for o in row["use_choices"][0]["options"]] == ["frightened"]
    bad = await _use(client, cid, STILLNESS, params={"condition": "charmed"})
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "invalid_choice"
    assert not (await _turn(client, cid))["action_used"]
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "action"})
    spent = await _use(client, cid, STILLNESS, params={"condition": "frightened"})
    assert spent.status_code == 409 and spent.json()["detail"]["code"] == "turn_slot_used"
    assert (await _full(client, cid))["conditions"]["frightened"] is True


# ---------------------------------------------------------------------------
# Anima Adamantina
# ---------------------------------------------------------------------------

async def _wis_save(client, cid, *options, die=10):
    r = await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": die, "options": list(options)})
    assert r.status_code == 200, r.text
    return r.json()


async def test_diamond_soul_gives_proficiency_in_every_saving_throw(client):
    low = await _monk(client, 13, wisdom=14)
    assert (await _wis_save(client, low))["total"] == 10 + 2
    cid = await _monk(client, 14, wisdom=14)  # competenza +5
    assert (await _wis_save(client, cid))["total"] == 10 + 2 + 5
    # Forza e Destrezza erano già competenze: non si contano due volte
    dex = (await client.post(f"/characters/{cid}/saving_throws/dexterity/roll", json={"die": 10})).json()
    assert dex["total"] == 10 + 0 + 5


async def test_diamond_soul_rerolls_a_failed_save_for_one_ki_and_the_new_result_stands(client):
    cid = await _monk(client, 14)
    first = await _wis_save(client, cid, die=2)
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [DIAMOND], "dice": [18]})
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 18 and r.json()["total"] == first["total"] + 16 and await _ki(client, cid) == 13
    again = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [DIAMOND], "dice": [3]})
    assert again.status_code == 409  # una sola ripetizione per tiro


async def test_diamond_soul_new_result_is_final_even_when_worse(client):
    cid = await _monk(client, 14)
    first = await _wis_save(client, cid, die=15)
    body = (await client.post(f"/characters/{cid}/last-roll/options", json={"options": [DIAMOND], "dice": [1]})).json()
    assert body["die"] == 1 and body["total"] == first["total"] - 14


async def test_diamond_soul_needs_level_14_and_a_ki_point(client):
    low = await _monk(client, 13)
    assert DIAMOND not in await _roll_keys(client, low, "save", ability="wisdom")
    cid = await _monk(client, 14)
    assert DIAMOND in await _roll_keys(client, cid, "save", ability="wisdom")
    await _set_ki(client, cid, 0)
    assert DIAMOND not in await _roll_keys(client, cid, "save", ability="wisdom")
    assert DIAMOND not in await _roll_keys(client, cid, "attack")


# ---------------------------------------------------------------------------
# Corpo Vuoto
# ---------------------------------------------------------------------------

async def test_empty_body_spends_four_ki_and_an_action_and_makes_the_monk_invisible_for_a_minute(client):
    cid = await _monk(client, 18)
    r = await _use(client, cid, EMPTY)
    assert r.status_code == 200, r.text
    assert await _ki(client, cid) == 14 and (await _turn(client, cid))["action_used"] is True
    state = (await _states(client, cid))["empty_body"]
    assert state["rounds_left"] == 10 and state["condition"] == "invisible"
    assert (await _full(client, cid))["conditions"]["invisible"] is True


async def test_empty_body_resists_every_damage_type_but_force_while_it_lasts(client):
    cid = await _monk(client, 18)
    await _full_hp(client, cid, 100)
    await _use(client, cid, EMPTY)
    resistances = set((await _full(client, cid))["computed"]["resistances"])
    assert {"fire", "slashing", "psychic", "necrotic", "bludgeoning"} <= resistances and "force" not in resistances
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20, "damage_type": "fire"})
    assert r.json()["current_hit_points"] == 90
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20, "damage_type": "force"})
    assert r.json()["current_hit_points"] == 70


async def test_empty_body_ends_after_ten_rounds_with_the_invisibility_and_the_resistance(client):
    cid = await _monk(client, 18)
    await _use(client, cid, EMPTY)
    for _ in range(10):
        assert (await client.post(f"/characters/{cid}/rounds/tick")).status_code == 200
    assert "empty_body" not in await _states(client, cid)
    full = await _full(client, cid)
    assert not full["conditions"].get("invisible") and "fire" not in full["computed"]["resistances"]


async def test_empty_body_needs_level_18_four_ki_and_the_action(client):
    assert await _ability(client, await _monk(client, 17), EMPTY) is None
    cid = await _monk(client, 18)
    await _set_ki(client, cid, 3)
    r = await _use(client, cid, EMPTY)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    assert not (await _turn(client, cid))["action_used"] and not (await _full(client, cid))["conditions"].get("invisible")
    await _set_ki(client, cid, 18)
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "action"})
    r = await _use(client, cid, EMPTY)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "turn_slot_used" and await _ki(client, cid) == 18


# ---------------------------------------------------------------------------
# Perfezione Interiore
# ---------------------------------------------------------------------------

async def test_perfect_self_gives_back_four_ki_at_initiative_only_with_none_left(client):
    low = await _monk(client, 19)
    await _set_ki(client, low, 0)
    assert PERFECT not in await _roll_keys(client, low, "initiative")
    cid = await _monk(client, 20)
    assert PERFECT not in await _roll_keys(client, cid, "initiative")  # i ki non sono finiti
    await _set_ki(client, cid, 1)
    assert PERFECT not in await _roll_keys(client, cid, "initiative")
    await _set_ki(client, cid, 0)
    assert PERFECT in await _roll_keys(client, cid, "initiative")
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 8, "options": [PERFECT]})
    assert r.status_code == 200, r.text
    assert await _ki(client, cid) == 4
    effect = r.json()["option_result"]["effects"][0]
    assert "4 punti ki" in effect["it"] and "4 ki points" in effect["en"]


async def test_empty_body_casts_astral_projection_for_eight_ki_and_no_action_of_the_turn(client):
    low = await _monk(client, 17)
    assert "Proiezione astrale" not in {s["name"] for s in (await client.get(f"/characters/{low}/spells")).json()}
    cid = await _monk(client, 18)
    spells = {s["name"]: s for s in (await client.get(f"/characters/{cid}/spells")).json()}
    astral = spells["Proiezione astrale"]
    assert astral["ki_cast"]["cost"] == 8 and astral["ki_cast"]["max_extra"] == 0 and astral["level"] == 9 and astral["ki_cast"]["self_only"] is True
    r = await client.post(f"/characters/{cid}/spells/{astral['id']}/use", json={"ki": True})
    assert r.status_code == 200, r.text
    assert await _ki(client, cid) == 10 and not (await _turn(client, cid))["action_used"]  # dura un'ora: non è un'azione del turno
    assert all(s["used"] == 0 for s in (await _full(client, cid))["spell_slots"])


async def test_astral_projection_is_refused_with_fewer_than_eight_ki(client):
    cid = await _monk(client, 18)
    astral = next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["name"] == "Proiezione astrale")
    await _set_ki(client, cid, 7)
    r = await client.post(f"/characters/{cid}/spells/{astral['id']}/use", json={"ki": True})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses" and await _ki(client, cid) == 7


async def test_perfect_self_works_at_the_initiative_of_an_encounter_too(client, test_session_factory, monkeypatch):
    from tests.integration._encounter_helpers import seed_session
    install_fake_telegram(monkeypatch)
    sid, cid = await seed_session(test_session_factory)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    assert r.status_code == 201, r.text
    pc = next(c for c in r.json()["combatants"] if c["kind"] == "pc")
    as_user(PLAYER_ID)
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "monk", "level": 20, "hit_die": 8})).status_code == 201
    await _set_ki(client, cid, 0)
    assert PERFECT in await _roll_keys(client, cid, "initiative")
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{pc['id']}/initiative", json={"die": 8, "options": [PERFECT]})
    assert r.status_code == 200, r.text
    assert await _ki(client, cid) == 4
