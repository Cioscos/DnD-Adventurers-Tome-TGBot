"""Ranger 2014, Signore delle Bestie (Task 26): Compagno del Ranger con ordini, Dadi Vita e riposi, Addestramento Straordinario,
Furia Bestiale e Condividere Incantesimi."""
from __future__ import annotations

import pytest

from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys
from tests.integration.rules.test_2014_fighter_styles import _item
from tests.integration.rules.test_2014_paladin import _new_turn, _rest, _turn
from tests.integration.rules.test_2014_ranger import _ranger, _states
from core.db.models import Companion
from tests.integration.test_rules_forms import beast

COMPANION, TRAINING, FURY, SHARE = ("ranger.rangers_companion", "ranger.exceptional_training", "ranger.bestial_fury",
                                    "ranger.share_spells")
SHARE_OPTION = "ranger.share_spells_extend"


def _panther() -> dict:
    sb = beast(cr=0.25, dex=15, con=10)
    sb["hit_dice"] = "3d8"
    sb["actions"] = [{"name": "Morso", "attack_bonus": 4, "damage_dice": "1d6+2", "damage_type": "piercing"}]
    return sb


async def _master(client, level=3, **scores) -> int:
    return await _ranger(client, level, "beast_master", **scores)


async def _companion(client, cid, **kw):
    body = {"kind": "companion", "name": "Pantera", "feature_key": COMPANION, "max_hp": 13, "armor_class": 12,
            "statblock": _panther(), **kw}
    return await client.post(f"/characters/{cid}/companions", json=body)


async def _beast(client, level=3, **scores) -> tuple[int, int]:
    cid = await _master(client, level, **scores)
    r = await _companion(client, cid)
    assert r.status_code == 201, r.text
    return cid, r.json()["id"]


async def _order(client, cid, comp, command, **body):
    return await client.post(f"/characters/{cid}/companions/{comp}/command", json={"command": command, **body})


async def _bite(client, cid, comp, **body):
    return await client.post(f"/characters/{cid}/companions/{comp}/attack",
                             json={"action_index": 0, "mode": "normal", "dice": [10], "damage_rolls": [3], **body})


async def _read(client, cid, comp) -> dict:
    return next(c for c in (await client.get(f"/characters/{cid}/companions")).json() if c["id"] == comp)


# ---------------------------------------------------------------------------
# Compagno del Ranger: la bestia
# ---------------------------------------------------------------------------

async def test_the_companion_is_only_for_the_beast_master(client):
    for archetype in (None, "hunter"):
        cid = await _ranger(client, 3, archetype)
        r = await _companion(client, cid)
        assert r.status_code == 422 and r.json()["detail"] == "feature_unavailable"
    assert (await _companion(client, await _master(client))).status_code == 201


async def test_the_beast_takes_the_greater_of_its_hit_points_and_four_times_the_level(client):
    cid, comp = await _beast(client, 5)  # competenza +3
    read = await _read(client, cid, comp)
    assert (read["max_hp"], read["armor_class"], read["attack_bonus_extra"], read["damage_bonus_extra"]) == (20, 15, 3, 3)
    class_id = (await _full(client, cid))["classes"][0]["id"]
    await client.patch(f"/characters/{cid}/classes/{class_id}", json={"level": 20})
    assert (await _read(client, cid, comp))["max_hp"] == 80


async def test_a_new_beast_is_possible_only_when_the_old_one_is_dead(client):
    cid, comp = await _beast(client, 3)
    again = await _companion(client, cid)
    assert again.status_code == 422 and again.json()["detail"] == "companion_exists"
    assert (await client.patch(f"/characters/{cid}/companions/{comp}/hp", json={"op": "damage", "value": 100})).status_code == 200
    assert (await _companion(client, cid, name="Nuova")).status_code == 201


async def test_the_other_kinds_of_companion_are_not_limited(client):
    cid, _ = await _beast(client, 3)
    r = await client.post(f"/characters/{cid}/companions", json={"kind": "familiar", "name": "Gufo", "statblock": {}})
    assert r.status_code == 201


# ---------------------------------------------------------------------------
# Ordini
# ---------------------------------------------------------------------------

async def test_the_beast_does_not_attack_without_an_order(client):
    cid, comp = await _beast(client)
    r = await _bite(client, cid, comp)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_order"


async def test_ordering_the_attack_costs_the_action_and_allows_one_bite(client):
    cid, comp = await _beast(client)
    r = await _order(client, cid, comp, "attack")
    assert r.status_code == 200, r.text
    assert r.json()["attacks_left"] == 1 and (await _turn(client, cid))["action_used"] is True
    assert (await _turn(client, cid))["beast"]["attacks_left"] == 1  # il Turno lo mostra
    assert (await _bite(client, cid, comp)).status_code == 200
    assert (await _turn(client, cid))["beast"]["attacks_left"] == 0
    again = await _bite(client, cid, comp)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "no_order"
    await _new_turn(client, cid)
    assert (await _bite(client, cid, comp)).json()["detail"]["code"] == "no_order"


@pytest.mark.parametrize("command", ["help", "disengage", "dash", "dodge"])
async def test_the_other_orders_cost_the_action_and_do_not_open_the_attack(client, command):
    cid, comp = await _beast(client)
    r = await _order(client, cid, comp, command)
    assert r.status_code == 200 and r.json()["attacks_left"] == 0
    assert (await _turn(client, cid))["action_used"] is True
    assert (await _bite(client, cid, comp)).json()["detail"]["code"] == "no_order"


async def test_only_one_order_per_action(client):
    cid, comp = await _beast(client)
    await _order(client, cid, comp, "dash")
    r = await _order(client, cid, comp, "attack")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "turn_slot_used"


async def test_an_unknown_order_is_refused_without_cost(client):
    cid, comp = await _beast(client)
    assert (await _order(client, cid, comp, "fly")).status_code == 422
    assert (await _turn(client, cid))["action_used"] is False


async def test_the_reaction_attack_needs_no_order_and_no_action(client):
    cid, comp = await _beast(client)
    r = await _bite(client, cid, comp, reaction=True)
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["action_used"] is False


async def test_an_incapacitated_ranger_cannot_command_but_the_beast_acts_alone(client):
    cid, comp = await _beast(client)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"incapacitated": True}})
    refused = await _order(client, cid, comp, "attack")
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "incapacitated"
    assert (await _bite(client, cid, comp)).status_code == 200


async def test_a_dead_beast_takes_no_orders_and_does_not_attack(client):
    cid, comp = await _beast(client)
    await client.patch(f"/characters/{cid}/companions/{comp}/hp", json={"op": "damage", "value": 100})
    refused = await _order(client, cid, comp, "attack")
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "companion_down"
    assert (await _turn(client, cid))["action_used"] is False


async def test_orders_are_only_for_the_ranger_companion(client):
    cid = await _master(client)
    plain = (await client.post(f"/characters/{cid}/companions", json={"kind": "familiar", "name": "Gufo", "statblock": beast()})).json()
    r = await _order(client, cid, plain["id"], "attack")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "feature_unavailable"


async def test_extra_attack_lets_the_ranger_attack_while_the_beast_does(client):
    cid, comp = await _beast(client, 5)
    wid = await _item(client, cid, "Spada", damage_dice="1d8", weapon_type="melee", properties=[], equip="main_hand")
    assert (await _order(client, cid, comp, "attack")).status_code == 200
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10})  # senza conferma oltre il limite
    assert r.status_code == 200, r.text
    assert (await _bite(client, cid, comp)).status_code == 200


async def _weapon_attack(client, cid, wid):
    return await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10})


async def test_the_attack_order_is_the_attack_action_and_costs_one_of_its_attacks(client):
    cid, comp = await _beast(client, 3)  # senza Attacco Extra l'azione ha un solo attacco: è quello della bestia
    wid = await _item(client, cid, "Spada", damage_dice="1d8", weapon_type="melee", properties=[], equip="main_hand")
    assert (await _order(client, cid, comp, "attack")).status_code == 200
    assert (await _turn(client, cid))["action_attacks"] == 1
    refused = await _weapon_attack(client, cid, wid)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "attack_limit"
    assert (await _bite(client, cid, comp)).status_code == 200  # la bestia attacca comunque


async def test_with_extra_attack_the_ranger_has_one_weapon_attack_while_the_beast_attacks(client):
    cid, comp = await _beast(client, 5)
    wid = await _item(client, cid, "Spada", damage_dice="1d8", weapon_type="melee", properties=[], equip="main_hand")
    assert (await _order(client, cid, comp, "attack")).status_code == 200
    assert (await _weapon_attack(client, cid, wid)).status_code == 200
    second = await _weapon_attack(client, cid, wid)
    assert second.status_code == 409 and second.json()["detail"]["code"] == "attack_limit"


async def test_the_attack_order_after_the_weapon_attacks_needs_an_attack_left(client):
    cid, comp = await _beast(client, 5)
    wid = await _item(client, cid, "Spada", damage_dice="1d8", weapon_type="melee", properties=[], equip="main_hand")
    assert (await _weapon_attack(client, cid, wid)).status_code == 200
    assert (await _order(client, cid, comp, "attack")).status_code == 200  # il secondo attacco dell'azione è dell'ordine
    assert (await _weapon_attack(client, cid, wid)).status_code == 409
    again = await _beast(client, 5)
    wid2 = await _item(client, again[0], "Spada", damage_dice="1d8", weapon_type="melee", properties=[], equip="main_hand")
    for _ in range(2):
        assert (await _weapon_attack(client, again[0], wid2)).status_code == 200
    refused = await _order(client, *again, "attack")  # gli attacchi dell'azione sono già finiti
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "no_attack_left"
    assert (await _turn(client, again[0]))["action_used"] is False  # il rifiuto non costa l'azione


# ---------------------------------------------------------------------------
# Addestramento Straordinario e Furia Bestiale
# ---------------------------------------------------------------------------

async def test_exceptional_training_orders_help_disengage_dash_or_dodge_as_a_bonus_action(client):
    assert TRAINING not in await _keys_of(client, await _master(client, 6))
    cid, comp = await _beast(client, 7)
    assert TRAINING in await _keys_of(client, cid)
    r = await _order(client, cid, comp, "dodge", bonus=True)
    assert r.status_code == 200, r.text
    turn = await _turn(client, cid)
    assert turn["bonus_used"] is True and turn["action_used"] is False
    again = await _order(client, cid, comp, "dash", bonus=True)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"


async def test_the_bonus_order_is_not_for_the_attack_and_not_before_level_7(client):
    cid, comp = await _beast(client, 6)
    r = await _order(client, cid, comp, "dodge", bonus=True)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "feature_unavailable"
    cid, comp = await _beast(client, 7)
    assert (await _order(client, cid, comp, "attack", bonus=True)).status_code == 422


async def test_the_bonus_order_needs_a_turn_in_which_the_beast_does_not_attack(client):
    cid, comp = await _beast(client, 7)
    await _order(client, cid, comp, "attack")
    r = await _order(client, cid, comp, "dodge", bonus=True)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "beast_attacked"
    assert (await _turn(client, cid))["bonus_used"] is False
    await _new_turn(client, cid)
    assert (await _order(client, cid, comp, "dodge", bonus=True)).status_code == 200
    blocked = await _order(client, cid, comp, "attack")  # dopo l'ordine in azione bonus la bestia non attacca più in questo turno
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "beast_not_attacking"


async def test_bestial_fury_gives_two_attacks_for_one_attack_order_from_level_11(client):
    assert FURY not in await _keys_of(client, await _master(client, 10))
    cid, comp = await _beast(client, 11)
    assert FURY in await _keys_of(client, cid)
    assert (await _order(client, cid, comp, "attack")).json()["attacks_left"] == 2
    assert (await _bite(client, cid, comp)).status_code == 200
    assert (await _bite(client, cid, comp)).status_code == 200
    assert (await _bite(client, cid, comp)).json()["detail"]["code"] == "no_order"


async def test_bestial_fury_uses_the_multiattack_of_the_beast_when_it_has_one(client):
    cid = await _master(client, 11)
    sb = _panther()
    sb["multiattack"] = 3
    comp = (await _companion(client, cid, statblock=sb)).json()["id"]
    assert (await _order(client, cid, comp, "attack")).json()["attacks_left"] == 3


# ---------------------------------------------------------------------------
# Dadi Vita e riposi
# ---------------------------------------------------------------------------

async def _wound(client, cid, comp, value):
    assert (await client.patch(f"/characters/{cid}/companions/{comp}/hp", json={"op": "damage", "value": value})).status_code == 200


async def test_the_beast_spends_its_own_hit_dice_to_heal(client):
    cid, comp = await _beast(client)
    await _wound(client, cid, comp, 12)
    r = await client.post(f"/characters/{cid}/companions/{comp}/hit-dice", json={"count": 2})
    assert r.status_code == 200, r.text
    body = r.json()  # PF 13, scesi a 1; Dado Vita d8, Costituzione 10 della bestia
    assert len(body["rolls"]) == 2 and all(1 <= v <= 8 for v in body["rolls"]) and body["hit_dice_left"] == 1
    assert body["healed"] == min(12, sum(body["rolls"]))
    assert (await _read(client, cid, comp))["current_hp"] == 1 + body["healed"]


async def test_hit_dice_are_limited_to_the_dice_of_the_statblock(client):
    cid, comp = await _beast(client)
    await _wound(client, cid, comp, 8)
    assert (await client.post(f"/characters/{cid}/companions/{comp}/hit-dice", json={"count": 3})).status_code == 200
    await _wound(client, cid, comp, 12)
    r = await client.post(f"/characters/{cid}/companions/{comp}/hit-dice", json={"count": 1})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_hit_dice"


async def test_a_dead_beast_or_a_full_one_does_not_spend_hit_dice(client):
    cid, comp = await _beast(client)
    full = await client.post(f"/characters/{cid}/companions/{comp}/hit-dice", json={"count": 1})
    assert full.status_code == 409 and full.json()["detail"]["code"] == "hp_full"
    await _wound(client, cid, comp, 100)
    dead = await client.post(f"/characters/{cid}/companions/{comp}/hit-dice", json={"count": 1})
    assert dead.status_code == 409 and dead.json()["detail"]["code"] == "companion_down"


async def test_a_long_rest_heals_the_beast_and_gives_back_half_the_hit_dice(client):
    cid, comp = await _beast(client)
    await _wound(client, cid, comp, 8)
    await client.post(f"/characters/{cid}/companions/{comp}/hit-dice", json={"count": 3})
    await _wound(client, cid, comp, 5)
    await _rest(client, cid, "long")
    read = await _read(client, cid, comp)
    assert read["current_hp"] == read["max_hp"] and read["statblock"]["hit_dice_spent"] == 2  # 3d8: tornano metà, per difetto (1)


async def test_a_short_rest_does_not_heal_the_beast_by_itself(client):
    cid, comp = await _beast(client)
    await _wound(client, cid, comp, 5)
    before = (await _read(client, cid, comp))["current_hp"]
    await _rest(client, cid, "short")
    assert (await _read(client, cid, comp))["current_hp"] == before


async def test_a_dead_beast_stays_dead_after_a_long_rest(client):
    cid, comp = await _beast(client)
    await _wound(client, cid, comp, 100)
    await _rest(client, cid, "long")
    assert (await _read(client, cid, comp))["current_hp"] == 0


async def _patch_statblock(client, cid, comp, **fields):
    sb = {**_panther(), **fields}
    return await client.patch(f"/characters/{cid}/companions/{comp}", json={"statblock": sb})


@pytest.mark.parametrize("field,value", [
    ("multiattack", "tre"), ("multiattack", 40), ("multiattack", True), ("hit_dice", "molti"), ("hit_dice", "99d8"),
    ("hit_dice_spent", "x"), ("hit_dice_spent", -1), ("hit_dice_spent", 1.5)])
async def test_the_statblock_numbers_the_server_reads_are_validated_on_save(client, field, value):
    cid, comp = await _beast(client)
    r = await _patch_statblock(client, cid, comp, **{field: value})
    assert r.status_code == 422, r.text
    created = await _companion(client, cid, statblock={**_panther(), field: value})
    assert created.status_code == 422, created.text


async def test_a_patch_cannot_reset_the_hit_dice_the_beast_has_spent(client):
    cid, comp = await _beast(client)
    await _wound(client, cid, comp, 8)
    assert (await client.post(f"/characters/{cid}/companions/{comp}/hit-dice", json={"count": 2})).status_code == 200
    for sent in ({}, {"hit_dice_spent": 0}):  # senza il campo o con un valore del client: resta quello del server
        r = await _patch_statblock(client, cid, comp, **sent)
        assert r.status_code == 200, r.text
        assert r.json()["statblock"]["hit_dice_spent"] == 2


async def test_an_old_statblock_with_bad_numbers_does_not_break_orders_hit_dice_or_the_long_rest(client, test_session_factory):
    cid, comp = await _beast(client, 11)  # Furia Bestiale legge `multiattack`
    async with test_session_factory() as s:
        row = await s.get(Companion, comp)
        row.statblock = {**_panther(), "multiattack": "tre", "hit_dice_spent": "x"}
        await s.commit()
    await _wound(client, cid, comp, 8)
    assert (await _order(client, cid, comp, "attack")).json()["attacks_left"] == 2
    ok = await client.post(f"/characters/{cid}/companions/{comp}/hit-dice", json={"count": 1})
    assert ok.status_code == 200, ok.text
    await _rest(client, cid, "long")  # il riposo lungo del personaggio non va in 500
    assert (await _read(client, cid, comp))["current_hp"] == (await _read(client, cid, comp))["max_hp"]


async def test_a_long_rest_gives_back_at_least_one_hit_die(client):
    cid, comp = await _beast(client)
    await _patch_statblock(client, cid, comp, hit_dice="1d8")
    await _wound(client, cid, comp, 8)
    assert (await client.post(f"/characters/{cid}/companions/{comp}/hit-dice", json={"count": 1})).status_code == 200
    await _rest(client, cid, "long")
    assert (await _read(client, cid, comp))["statblock"]["hit_dice_spent"] == 0


# ---------------------------------------------------------------------------
# Condividere Incantesimi
# ---------------------------------------------------------------------------

async def _spell(client, cid, name, range_area, **extra) -> int:
    body = {"name": name, "level": 1, "range_area": range_area, "casting_time": "1 azione", "is_prepared": True, **extra}
    r = await client.post(f"/characters/{cid}/spells", json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_share_spells_is_asked_on_a_self_only_spell(client):
    assert SHARE not in await _keys_of(client, await _master(client, 14))
    cid, comp = await _beast(client, 15)
    assert SHARE in await _keys_of(client, cid)
    selfish = await _spell(client, cid, "Passo Veloce", "Personale")
    ranged = await _spell(client, cid, "Colpo", "18 m")
    assert SHARE_OPTION in await _roll_keys(client, cid, "cast", spell_id=selfish)
    assert SHARE_OPTION not in await _roll_keys(client, cid, "cast", spell_id=ranged)


async def test_share_spells_confirmation_says_the_beast_shares_the_effect(client):
    cid, comp = await _beast(client, 15)
    spell = await _spell(client, cid, "Passo Veloce", "Self")
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 1, "options": [SHARE_OPTION]})
    assert r.status_code == 200, r.text
    effect = r.json()["option_result"]["effects"][0]
    assert "9 m" in effect["it"] and "9 m" not in effect["en"] and "30 ft" in effect["en"]
