"""Monaco 2014 (Task 24): Via della Mano Aperta (Tecnica, Integrità del Corpo, Tranquillità, Palmo Tremante) e Via
dell'Ombra (Arti dell'Ombra, Passo dell'Ombra, Manto di Ombre, Opportunista)."""
from __future__ import annotations

from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _use
from tests.integration.rules.test_2014_monk import _monk, _rest, _turn
from tests.integration.rules.test_2014_monk_ki import (
    FLURRY, STRIKE, _damage, _hit, _ki, _set_ki, _shortsword, _states, _strike,
)

PRONE, PUSH, NO_REACTIONS = "monk.open_hand_prone", "monk.open_hand_push", "monk.open_hand_no_reactions"
WHOLENESS, TRANQUILITY, PALM = "monk.wholeness_of_body", "monk.tranquility", "monk.quivering_palm"
PALM_OPTION = "monk.quivering_palm_start"
ARTS, STEP, CLOAK, OPPORTUNIST = "monk.shadow_arts", "monk.shadow_step", "monk.cloak_of_shadows", "monk.opportunist"
STEP_ADVANTAGE = "monk.shadow_step_advantage"
LIGHT = {"light": "dim_or_dark"}
ILLUSION = "Illusione minore"


async def _hurt(client, cid, current, maximum=60):
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": maximum})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": current})


# ---------------------------------------------------------------------------
# Via della Mano Aperta: Tecnica della Mano Aperta
# ---------------------------------------------------------------------------

async def _flurry_strike(client, cid, **body):
    """Un colpo della Raffica di Colpi, a segno e con il danno ancora da tirare."""
    await _strike(client, cid)  # l'azione Attacco
    assert (await _use(client, cid, FLURRY)).status_code == 200
    return await _hit(client, cid, options=[STRIKE], **body)


async def test_the_technique_is_offered_only_on_the_hits_of_the_flurry(client):
    cid = await _monk(client, 3, "open_hand", wisdom=16, dexterity=16)
    plain = await _hit(client, cid)
    keys = await _roll_keys(client, cid, "attack")
    assert not {PRONE, PUSH, NO_REACTIONS} & set(keys)  # un colpo qualunque non la dà
    assert (await _damage(client, cid, plain, PRONE)).status_code == 409
    await client.post(f"/characters/{cid}/turn/new")
    hit = await _flurry_strike(client, cid)
    assert {PRONE, PUSH, NO_REACTIONS} <= set(await _roll_keys(client, cid, "attack"))
    assert hit["attack_id"]


async def test_the_technique_is_only_for_the_open_hand(client):
    cid = await _monk(client, 3, "shadow", dexterity=16)
    await _flurry_strike(client, cid)
    assert not {PRONE, PUSH, NO_REACTIONS} & set(await _roll_keys(client, cid, "attack"))
    assert not {PRONE, PUSH} & await _keys_of(client, await _monk(client, 3, "open_hand"))


async def test_the_technique_costs_nothing_and_shows_the_save_with_the_ki_dc(client):
    cid = await _monk(client, 3, "open_hand", wisdom=16, dexterity=16)  # competenza +2, Saggezza +3
    hit = await _flurry_strike(client, cid)
    body = (await _damage(client, cid, hit, PRONE)).json()
    assert await _ki(client, cid) == 2 and body["option_result"]["targets"] == [PRONE]
    assert "CD 13" in body["option_result"]["effects"][0]["it"] and "DC 13" in body["option_result"]["effects"][0]["en"]
    effect = (await client.get(f"/characters/{cid}/target-effects/{PRONE}")).json()["result"]
    assert (effect["condition"], effect["save_ability"], effect["save_dc"]) == ("prone", "dexterity", 13)


async def test_the_technique_strength_save_pushes_and_the_third_choice_stops_reactions(client):
    cid = await _monk(client, 3, "open_hand", wisdom=16, dexterity=16)
    hit = await _flurry_strike(client, cid)
    push = (await _damage(client, cid, hit, PUSH)).json()
    assert "4,5 m" in push["option_result"]["effects"][0]["it"] and "15 ft" in push["option_result"]["effects"][0]["en"]
    effect = (await client.get(f"/characters/{cid}/target-effects/{PUSH}")).json()["result"]
    assert (effect["save_ability"], effect["save_dc"]) == ("strength", 13) and not effect["condition"]
    second = await _hit(client, cid, options=[STRIKE])
    quiet = (await _damage(client, cid, second, NO_REACTIONS)).json()
    effect = (await client.get(f"/characters/{cid}/target-effects/{NO_REACTIONS}")).json()["result"]
    assert effect["condition"] == "custom:no_reactions" and not effect["save_ability"]
    assert effect["ends_at"] == {"anchor": "source", "edge": "end", "count": 1}
    assert quiet["option_result"]["targets"] == [NO_REACTIONS]


async def test_the_technique_allows_one_choice_for_each_hit(client):
    cid = await _monk(client, 3, "open_hand", dexterity=16)
    hit = await _flurry_strike(client, cid)
    r = await _damage(client, cid, hit, PRONE, PUSH)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"


# ---------------------------------------------------------------------------
# Integrità del Corpo
# ---------------------------------------------------------------------------

async def test_wholeness_of_body_heals_three_times_the_level_with_an_action_and_one_use(client):
    cid = await _monk(client, 6, "open_hand")
    await _hurt(client, cid, 10)
    r = await _use(client, cid, WHOLENESS)
    assert r.status_code == 200 and r.json()["healed"] == 18
    assert (await _full(client, cid))["current_hit_points"] == 28
    row = await _ability(client, cid, WHOLENESS)
    assert (row["uses"], row["max_uses"], row["restoration_type"], row["action_type"]) == (0, 1, "long_rest", "action")
    assert (await _turn(client, cid))["action_used"] is True


async def test_wholeness_of_body_never_passes_the_maximum_and_follows_the_level(client):
    cid = await _monk(client, 6, "open_hand")
    await _hurt(client, cid, 55)
    assert (await _use(client, cid, WHOLENESS)).json()["healed"] == 5
    other = await _monk(client, 10, "open_hand")
    await _hurt(client, other, 1)
    assert (await _use(client, other, WHOLENESS)).json()["healed"] == 30


async def test_wholeness_of_body_is_refused_without_the_use_or_the_action_and_comes_back_with_a_long_rest_only(client):
    cid = await _monk(client, 6, "open_hand")
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "action"})
    r = await _use(client, cid, WHOLENESS)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "turn_slot_used"
    assert (await _ability(client, cid, WHOLENESS))["uses"] == 1
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid, WHOLENESS)).status_code == 200
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid, WHOLENESS)).json()["detail"]["code"] == "no_uses"
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, WHOLENESS))["uses"] == 0
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, WHOLENESS))["uses"] == 1


# ---------------------------------------------------------------------------
# Tranquillità
# ---------------------------------------------------------------------------

async def test_tranquility_starts_at_the_end_of_a_long_rest_with_the_ki_dc(client):
    cid = await _monk(client, 11, "open_hand", wisdom=16)  # competenza +4, Saggezza +3
    assert "tranquility" not in await _states(client, cid)
    await _rest(client, cid, "long")
    state = (await _states(client, cid))["tranquility"]
    assert state["data"]["dc"] == 8 + 4 + 3 and state["data"]["save"] == "wisdom" and state["rounds_left"] is None and state["data"]["others"] == [TRANQUILITY]
    assert {"attack", "cast", "rest_long"} <= set(state["ends_on"])


async def test_tranquility_does_not_start_with_a_short_rest_or_before_level_11_or_in_another_tradition(client):
    cid = await _monk(client, 11, "open_hand")
    await _rest(client, cid, "short")
    assert "tranquility" not in await _states(client, cid)
    for level, sub in ((10, "open_hand"), (11, "shadow")):
        other = await _monk(client, level, sub)
        await _rest(client, other, "long")
        assert "tranquility" not in await _states(client, other)


async def test_tranquility_ends_when_the_monk_attacks_and_comes_back_with_the_next_long_rest_only(client):
    cid = await _monk(client, 11, "open_hand")
    await _rest(client, cid, "long")
    assert (await _strike(client, cid)).status_code == 200
    assert "tranquility" not in await _states(client, cid)
    await _rest(client, cid, "short")
    assert "tranquility" not in await _states(client, cid)
    await _rest(client, cid, "long")
    assert "tranquility" in await _states(client, cid)


async def test_tranquility_survives_a_short_rest_and_is_renewed_not_doubled_by_the_next_long_rest(client):
    cid = await _monk(client, 11, "open_hand")
    await _rest(client, cid, "long")
    await _rest(client, cid, "short")
    assert "tranquility" in await _states(client, cid)
    await _rest(client, cid, "long")
    assert [s["key"] for s in (await _full(client, cid))["active_states"]].count("tranquility") == 1


# ---------------------------------------------------------------------------
# Palmo Tremante
# ---------------------------------------------------------------------------

async def test_quivering_palm_is_offered_on_an_unarmed_hit_from_level_17(client):
    low = await _monk(client, 16, "open_hand")
    assert PALM_OPTION not in await _roll_keys(client, low, "attack")
    cid = await _monk(client, 17, "open_hand", dexterity=16)
    options = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack"})).json()
    assert next(o for o in options if o["key"] == PALM_OPTION)["phase"] == "after_hit"
    sword = await _shortsword(client, cid)
    assert PALM_OPTION not in await _roll_keys(client, cid, "attack", item_id=sword)
    assert PALM_OPTION not in await _roll_keys(client, await _monk(client, 17, "shadow"), "attack")


async def test_quivering_palm_spends_three_ki_and_keeps_the_vibrations_for_as_many_days_as_the_level(client):
    cid = await _monk(client, 17, "open_hand", dexterity=16)
    hit = await _hit(client, cid)
    assert (await _damage(client, cid, hit, PALM_OPTION)).status_code == 200
    assert await _ki(client, cid) == 14
    state = (await _states(client, cid))["quivering_palm"]
    assert state["rounds_left"] == 17 * 14400 and "manual" in state["ends_on"]
    assert PALM_OPTION not in await _roll_keys(client, cid, "attack")  # un solo bersaglio alla volta
    await _rest(client, cid, "long")
    assert (await _states(client, cid))["quivering_palm"]["rounds_left"] == 17 * 14400 - 4800


async def test_quivering_palm_needs_the_ki(client):
    cid = await _monk(client, 17, "open_hand", dexterity=16)
    await _set_ki(client, cid, 2)
    assert PALM_OPTION not in await _roll_keys(client, cid, "attack")


async def test_ending_the_vibrations_is_an_action_with_a_constitution_save_and_ten_d10(client):
    cid = await _monk(client, 17, "open_hand", dexterity=16, wisdom=16)  # competenza +6, Saggezza +3
    assert (await _use(client, cid, PALM)).json()["detail"]["code"] == "feature_unavailable"
    hit = await _hit(client, cid)
    await _damage(client, cid, hit, PALM_OPTION)
    await client.post(f"/characters/{cid}/turn/new")
    r = await _use(client, cid, PALM)
    assert r.status_code == 200, r.text
    assert len(r.json()["rolls"]) == 10 and r.json()["targets"] == [PALM] and r.json()["notes"] == ["quivering_palm"]
    effect = (await client.get(f"/characters/{cid}/target-effects/{PALM}")).json()["result"]
    assert (effect["save_ability"], effect["save_dc"], effect["damage_dice"]) == ("constitution", 8 + 6 + 3, "10d10")
    assert effect["on_failure_only"] is False and effect["condition"] is None  # il danno c'è comunque: non è un effetto «se fallisce»
    assert "quivering_palm" not in await _states(client, cid) and (await _turn(client, cid))["action_used"] is True
    assert await _ki(client, cid) == 14  # la fine non costa ki


async def test_the_vibrations_can_end_harmlessly_without_an_action(client):
    cid = await _monk(client, 17, "open_hand", dexterity=16)
    hit = await _hit(client, cid)
    await _damage(client, cid, hit, PALM_OPTION)
    r = await client.delete(f"/characters/{cid}/active-states/quivering_palm")
    assert r.status_code == 200
    assert "quivering_palm" not in await _states(client, cid) and not (await _turn(client, cid))["action_used"]


# ---------------------------------------------------------------------------
# Via dell'Ombra: Arti dell'Ombra
# ---------------------------------------------------------------------------

async def _spells(client, cid) -> dict[str, dict]:
    return {s["name"]: s for s in (await client.get(f"/characters/{cid}/spells")).json()}


async def _cast_ki(client, cid, spell, **body):
    return await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"ki": True, **body})


async def test_shadow_arts_gives_four_spells_for_ki_and_the_minor_illusion_cantrip(client):
    cid = await _monk(client, 3, "shadow")
    spells = await _spells(client, cid)
    assert {"Oscurità", "Passare senza tracce", "Scurovisione", "Silenzio", ILLUSION} <= set(spells)
    assert spells[ILLUSION]["level"] == 0 and spells["Oscurità"]["ki_cast"]["cost"] == 2
    assert spells["Oscurità"]["ki_cast"]["max_extra"] == 0 and spells["Oscurità"]["always_prepared"] is True
    assert spells["Oscurità"]["save_dc"] == 8 + 2 + 0  # la CD del ki, non quella di un incantatore


async def test_shadow_arts_spells_are_for_the_shadow_tradition_from_level_3_only(client):
    low = await _spells(client, await _monk(client, 2))
    assert "Oscurità" not in low
    assert "Oscurità" not in await _spells(client, await _monk(client, 3, "open_hand"))
    assert ILLUSION in await _spells(client, await _monk(client, 3, "shadow"))


async def test_a_shadow_arts_cast_spends_two_ki_and_the_action_and_no_slot(client):
    cid = await _monk(client, 3, "shadow")
    spell = (await _spells(client, cid))["Oscurità"]
    r = await _cast_ki(client, cid, spell)
    assert r.status_code == 200, r.text
    assert await _ki(client, cid) == 1 and (await _turn(client, cid))["action_used"] is True
    assert (await _full(client, cid))["concentrating_spell_id"] == spell["id"]
    assert all(s["used"] == 0 for s in (await _full(client, cid))["spell_slots"])


async def test_a_shadow_arts_cast_is_refused_without_ki_or_with_extra_ki_and_costs_nothing(client):
    cid = await _monk(client, 3, "shadow")
    spell = (await _spells(client, cid))["Silenzio"]
    r = await _cast_ki(client, cid, spell, ki_extra=1)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "ki_extra_not_allowed"
    await _set_ki(client, cid, 1)
    r = await _cast_ki(client, cid, spell)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    assert await _ki(client, cid) == 1 and not (await _turn(client, cid))["action_used"]


async def test_a_ki_cast_is_refused_for_a_spell_the_monk_cannot_cast_with_ki(client):
    cid = await _monk(client, 3, "shadow")
    illusion = (await _spells(client, cid))[ILLUSION]
    assert illusion.get("ki_cast") is None
    dark = (await _spells(client, cid))["Oscurità"]
    await client.patch(f"/characters/{cid}/spells/{dark['id']}", json={"srd_index": "web"})
    r = await _cast_ki(client, cid, dark)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "ki_cast_unavailable"


# ---------------------------------------------------------------------------
# Passo dell'Ombra, Manto di Ombre, Opportunista
# ---------------------------------------------------------------------------

async def test_shadow_step_is_a_bonus_action_that_needs_the_light_confirmed(client):
    cid = await _monk(client, 6, "shadow")
    row = await _ability(client, cid, STEP)
    assert row["action_type"] == "bonus_action" and [o["key"] for o in row["use_choices"][0]["options"]] == ["dim_or_dark"]
    r = await _use(client, cid, STEP, params={})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice"
    assert not (await _turn(client, cid))["bonus_used"]
    assert (await _use(client, cid, STEP, params=LIGHT)).status_code == 200
    assert (await _turn(client, cid))["bonus_used"] is True and "shadow_step" in await _states(client, cid)
    assert await _ki(client, cid) == 6  # nessun costo


async def test_shadow_step_gives_advantage_to_the_first_melee_attack_only(client):
    cid = await _monk(client, 6, "shadow", dexterity=16)
    await _use(client, cid, STEP, params=LIGHT)
    assert STEP_ADVANTAGE in await _roll_keys(client, cid, "attack")
    r = await _strike(client, cid, STEP_ADVANTAGE)
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "advantage"
    assert STEP_ADVANTAGE not in await _roll_keys(client, cid, "attack") and "shadow_step" not in await _states(client, cid)
    second = await _strike(client, cid, STEP_ADVANTAGE)
    assert second.status_code == 409 and second.json()["detail"]["code"] == "option_unavailable"


async def test_shadow_step_advantage_ends_with_the_turn_and_is_not_for_ranged_attacks(client):
    cid = await _monk(client, 6, "shadow", dexterity=16)
    await _use(client, cid, STEP, params=LIGHT)
    await client.post(f"/characters/{cid}/turn/new")
    assert "shadow_step" not in await _states(client, cid) and STEP_ADVANTAGE not in await _roll_keys(client, cid, "attack")
    other = await _monk(client, 6, "shadow")
    assert await _ability(client, other, STEP) is not None
    assert await _ability(client, await _monk(client, 5, "shadow"), STEP) is None


async def test_cloak_of_shadows_makes_the_monk_invisible_until_attack_or_spell(client):
    cid = await _monk(client, 11, "shadow", dexterity=16)
    row = await _ability(client, cid, CLOAK)
    assert row["action_type"] == "action"
    r = await _use(client, cid, CLOAK, params={})
    assert r.status_code == 422 and not (await _turn(client, cid))["action_used"]
    assert (await _use(client, cid, CLOAK, params=LIGHT)).status_code == 200
    assert (await _full(client, cid))["conditions"]["invisible"] is True and (await _turn(client, cid))["action_used"] is True
    state = (await _states(client, cid))["cloak_of_shadows"]
    assert {"attack", "cast"} <= set(state["ends_on"]) and state["rounds_left"] is None
    assert (await _strike(client, cid)).status_code == 200
    full = await _full(client, cid)
    assert "cloak_of_shadows" not in await _states(client, cid) and not full["conditions"].get("invisible")


async def test_cloak_of_shadows_ends_when_the_monk_casts_a_spell(client):
    cid = await _monk(client, 11, "shadow")
    await _use(client, cid, CLOAK, params=LIGHT)
    illusion = (await _spells(client, cid))[ILLUSION]
    assert (await client.post(f"/characters/{cid}/spells/{illusion['id']}/use", json={})).status_code == 200
    assert "cloak_of_shadows" not in await _states(client, cid)
    assert not (await _full(client, cid))["conditions"].get("invisible")


async def test_cloak_of_shadows_can_end_by_hand_in_bright_light(client):
    cid = await _monk(client, 11, "shadow")
    await _use(client, cid, CLOAK, params=LIGHT)
    assert (await client.delete(f"/characters/{cid}/active-states/cloak_of_shadows")).status_code == 200
    assert not (await _full(client, cid))["conditions"].get("invisible")


async def test_opportunist_is_a_melee_attack_with_the_reaction_that_is_not_an_attack_of_the_action(client):
    low = await _monk(client, 16, "shadow")
    assert OPPORTUNIST not in await _roll_keys(client, low, "attack")
    assert OPPORTUNIST not in await _roll_keys(client, await _monk(client, 17, "open_hand"), "attack")
    cid = await _monk(client, 17, "shadow", dexterity=16)
    options = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack"})).json()
    opportunist = next(o for o in options if o["key"] == OPPORTUNIST)
    assert opportunist["slot"] == "reaction" and opportunist["offered_on_damage"] is False
    for _ in range(2):
        await _strike(client, cid)  # le due azioni Attacco
    r = await _strike(client, cid, OPPORTUNIST)
    assert r.status_code == 200, r.text
    turn = await _turn(client, cid)
    assert turn["reaction_used"] is True and turn["action_attacks"] == 2
    again = await _strike(client, cid, OPPORTUNIST)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "option_unavailable"


async def test_opportunist_is_not_proposed_after_the_monk_takes_damage(client):
    cid = await _monk(client, 17, "shadow")
    await _hurt(client, cid, 50, 60)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 5})
    assert OPPORTUNIST not in [o["key"] for o in r.json()["reactions"]]


async def test_the_flurry_strike_makes_the_damage_wait_so_the_open_hand_technique_is_not_lost(client):
    cid = await _monk(client, 3, "open_hand", wisdom=16, dexterity=16)
    await _strike(client, cid)
    assert (await _use(client, cid, FLURRY)).status_code == 200
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack"})
    assert STRIKE in {o["key"] for o in r.json() if o.get("defers_damage")}
