"""Barbaro 2024 (Task 31): Attacco Irruento e Colpo Brutale, con i suoi effetti."""
from __future__ import annotations

import pytest

from tests.integration.rules.test_2014_barbarian import _attack, _keys, _states, _weapon
from tests.integration.rules.test_2024_barbarian import _barbarian, _new_turn

RECKLESS, BRUTAL = "barbarian.reckless_attack", "barbarian.brutal_strike"
FORCEFUL, HAMSTRING = "barbarian.forceful_blow", "barbarian.hamstring_blow"
STAGGERING, SUNDERING = "barbarian.staggering_blow", "barbarian.sundering_blow"


async def _deferred(client, cid, wid, die=10, **body) -> dict:
    r = await client.post(f"/characters/{cid}/items/{wid}/attack",
                          json={"die": die, "confirm_extra_attack": True, "defer_damage": True, **body})
    assert r.status_code == 200, r.text
    return r.json()


async def _damage(client, cid, hit, options):
    return await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": options})


async def _hit_with(client, cid, wid, before, after, die=10):
    hit = await _deferred(client, cid, wid, die, options=before)
    return hit, await _damage(client, cid, hit, after)


async def _armed(client, level, subclass=None, **scores):
    cid = await _barbarian(client, level, subclass, strength=16, **scores)
    return cid, await _weapon(client, cid)


# ---------------------------------------------------------------------------
# Attacco Irruento
# ---------------------------------------------------------------------------

async def test_reckless_attack_is_offered_on_the_first_attack_roll_with_strength_only(client):
    cid = await _barbarian(client, 5, strength=16, dexterity=10)
    sword = await _weapon(client, cid)
    javelin = await _weapon(client, cid, "Giavellotto", None, properties=["thrown"], damage_dice="1d6")
    rapier = await _weapon(client, cid, "Stocco", None, properties=["finesse"], damage_dice="1d8")
    assert RECKLESS in await _keys(client, cid, "attack", item_id=sword)
    assert RECKLESS in await _keys(client, cid, "attack", item_id=javelin, attack_mode="thrown")
    await client.patch(f"/characters/{cid}/ability_scores/dexterity", json={"value": 18})
    assert RECKLESS not in await _keys(client, cid, "attack", item_id=rapier)  # Destrezza
    await _attack(client, cid, sword)  # il primo tiro senza dichiararlo: non si può più
    assert RECKLESS not in await _keys(client, cid, "attack", item_id=sword)


async def test_reckless_attack_gives_strength_attacks_advantage_until_the_next_turn_and_to_attackers(client):
    cid, sword = await _armed(client, 5)
    first = await _attack(client, cid, sword, options=[RECKLESS])
    second = await _attack(client, cid, sword)
    assert first["mode_applied"] == "advantage" and second["mode_applied"] == "advantage"
    state = next(s for s in await _states(client, cid) if s["key"] == "reckless")
    assert state["rounds_left"] == 1 and state["data"]["others"] == [RECKLESS]
    await _new_turn(client, cid)
    assert (await _attack(client, cid, sword))["mode_applied"] == "normal"  # nuovo turno: va deciso di nuovo


async def test_reckless_attack_advantage_survives_another_creatures_turn(client):
    """«Fino all'inizio del tuo turno seguente»: il turno di un altro non lo tocca (I1)."""
    cid, sword = await _armed(client, 5)
    await _attack(client, cid, sword, options=[RECKLESS])
    assert (await client.post(f"/characters/{cid}/turn/other")).status_code == 200
    assert (await _attack(client, cid, sword))["mode_applied"] == "advantage"
    await _new_turn(client, cid)
    assert (await _attack(client, cid, sword))["mode_applied"] == "normal"


async def test_reckless_attack_and_brutal_strike_ask_the_client_to_defer_the_damage(client):
    """Frenesia e gli effetti del Colpo Brutale arrivano dopo il colpo: il client deve saperlo prima (C1)."""
    cid, sword = await _armed(client, 17, "berserker")
    listed = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": sword})).json()
    assert {o["key"] for o in listed if o.get("defers_damage")} == {RECKLESS, BRUTAL}


async def test_reckless_attack_advantage_also_covers_thrown_strength_attacks(client):
    cid, sword = await _armed(client, 5)
    javelin = await _weapon(client, cid, "Giavellotto", None, properties=["thrown"], damage_dice="1d6")
    await _attack(client, cid, sword, options=[RECKLESS])
    assert (await _attack(client, cid, javelin, attack_mode="thrown"))["mode_applied"] == "advantage"


# ---------------------------------------------------------------------------
# Colpo Brutale
# ---------------------------------------------------------------------------

async def test_brutal_strike_needs_level_9_and_reckless_attack_declared_this_turn(client):
    cid, sword = await _armed(client, 8)
    assert BRUTAL not in await _keys(client, cid, "attack", item_id=sword)
    cid, sword = await _armed(client, 9)
    listed = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": sword})).json()
    assert next(o for o in listed if o["key"] == BRUTAL)["needs"] == RECKLESS  # nella stessa richiesta
    refused = await client.post(f"/characters/{cid}/items/{sword}/attack", json={"die": 10, "options": [BRUTAL]})
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "option_unavailable"
    assert (await _attack(client, cid, sword, options=[RECKLESS, BRUTAL]))["mode_applied"] == "normal"  # rinuncia al vantaggio


async def test_brutal_strike_forgoes_the_advantage_and_adds_the_extra_die(client):
    cid, sword = await _armed(client, 9)
    plain = await _attack(client, cid, sword, options=[RECKLESS])
    await _new_turn(client, cid)
    brutal = await _attack(client, cid, sword, options=[RECKLESS, BRUTAL])
    assert plain["mode_applied"] == "advantage" and brutal["mode_applied"] == "normal"
    assert len(brutal["option_result"]["extra_rolls"]) == 1 and 1 <= brutal["option_result"]["extra_rolls"][0] <= 10


async def test_brutal_strike_can_be_chosen_on_a_later_attack_once_reckless_was_declared(client):
    cid, sword = await _armed(client, 9)
    await _attack(client, cid, sword, options=[RECKLESS])
    assert BRUTAL in await _keys(client, cid, "attack", item_id=sword)
    second = await _attack(client, cid, sword, options=[BRUTAL])
    assert second["mode_applied"] == "normal"  # il vantaggio dell'Attacco Irruento è rinunciato
    assert BRUTAL not in await _keys(client, cid, "attack", item_id=sword)  # una sola rinuncia per turno


@pytest.mark.parametrize("level,dice", [(9, 1), (16, 1), (17, 2), (20, 2)])
async def test_brutal_strike_adds_one_die_and_two_from_level_17(client, level, dice):
    cid, sword = await _armed(client, level)
    body = await _attack(client, cid, sword, options=[RECKLESS, BRUTAL])
    assert len(body["option_result"]["extra_rolls"]) == dice


async def test_brutal_strike_doubles_its_dice_on_a_critical_hit(client):
    cid, sword = await _armed(client, 9)
    body = await _attack(client, cid, sword, die=20, options=[RECKLESS, BRUTAL])
    assert len(body["option_result"]["extra_rolls"]) == 2


async def test_brutal_strike_is_not_offered_when_the_attack_has_disadvantage(client):
    cid, sword = await _armed(client, 9)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"poisoned": True}})
    assert BRUTAL not in await _keys(client, cid, "attack", item_id=sword)


async def test_brutal_strike_is_only_for_strength_attacks(client):
    cid = await _barbarian(client, 9, strength=10, dexterity=18)
    rapier = await _weapon(client, cid, "Stocco", properties=["finesse"], damage_dice="1d8")
    assert BRUTAL not in await _keys(client, cid, "attack", item_id=rapier)


# --- effetti (dopo il colpo) --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("level,effects", [
    (9, {FORCEFUL, HAMSTRING}), (12, {FORCEFUL, HAMSTRING}), (13, {FORCEFUL, HAMSTRING, STAGGERING, SUNDERING}), (20, {FORCEFUL, HAMSTRING, STAGGERING, SUNDERING})])
async def test_the_effects_offered_depend_on_the_level(client, level, effects):
    cid, sword = await _armed(client, level)
    hit = await _deferred(client, cid, sword, options=[RECKLESS, BRUTAL])
    listed = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": sword})).json()
    offered = {o["key"] for o in listed if o["phase"] == "after_hit"}
    assert effects <= offered and offered & {FORCEFUL, HAMSTRING, STAGGERING, SUNDERING} == effects


async def test_an_effect_needs_the_brutal_strike_of_this_attack(client):
    cid, sword = await _armed(client, 9)
    hit = await _deferred(client, cid, sword, options=[RECKLESS])
    refused = await _damage(client, cid, hit, [HAMSTRING])
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "option_unavailable"


async def test_one_effect_up_to_level_16_and_two_different_ones_from_17(client):
    cid, sword = await _armed(client, 16)
    hit = await _deferred(client, cid, sword, options=[RECKLESS, BRUTAL])
    assert (await _damage(client, cid, hit, [FORCEFUL, HAMSTRING])).status_code == 409
    cid, sword = await _armed(client, 17)
    hit = await _deferred(client, cid, sword, options=[RECKLESS, BRUTAL])
    assert (await _damage(client, cid, hit, [FORCEFUL, HAMSTRING, STAGGERING])).status_code == 409
    ok = await _damage(client, cid, hit, [FORCEFUL, HAMSTRING])
    assert ok.status_code == 200, ok.text


async def test_the_option_read_tells_the_client_how_many_effects_can_be_picked(client):
    for level, expected in ((16, 1), (17, 2)):
        cid, sword = await _armed(client, level)
        hit = await _deferred(client, cid, sword, options=[RECKLESS, BRUTAL])
        listed = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": sword})).json()
        assert {o["group_max"] for o in listed if o["key"] == HAMSTRING} == {expected}


async def test_forceful_blow_tells_the_push_and_the_half_speed_move(client):
    cid, sword = await _armed(client, 9)  # velocità 30 + 10 di Movimento Veloce: metà = 20
    _, r = await _hit_with(client, cid, sword, [RECKLESS, BRUTAL], [FORCEFUL])
    effect = r.json()["option_result"]["effects"][0]
    assert "4,5 m" in effect["it"] and "6 m" in effect["it"] and "15 ft" in effect["en"] and "20 ft" in effect["en"]


@pytest.mark.parametrize("key,condition,level", [(HAMSTRING, "custom:hamstring", 9), (STAGGERING, "custom:staggered", 13),
                                                  (SUNDERING, "custom:sundered", 13)])
async def test_the_effect_labels_apply_to_the_target_until_the_start_of_the_next_turn(client, key, condition, level):
    cid, sword = await _armed(client, level)
    _, r = await _hit_with(client, cid, sword, [RECKLESS, BRUTAL], [key])
    assert r.json()["option_result"]["targets"] == [key]
    preview = (await client.get(f"/characters/{cid}/target-effects/{key}")).json()["result"]
    assert preview["condition"] == condition and preview["ends_at"] == {"anchor": "source", "edge": "start", "count": 1}


async def test_the_barbarian_rage_does_not_have_to_be_active_for_brutal_strike(client):
    cid, sword = await _armed(client, 9)
    assert (await _attack(client, cid, sword, options=[RECKLESS, BRUTAL]))["mode_applied"] == "normal"  # nessuna Ira richiesta
    assert not await _states(client, cid) or all(s["key"] != "rage" for s in await _states(client, cid))
