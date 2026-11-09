"""Bardo 2024, Collegio dell'Incanto (Task 32): Magia Ammaliante, Mantello di Ispirazione, Mantello di Maestà, Maestà Infrangibile."""
from __future__ import annotations

import pytest

from tests.integration.rules.test_2014_bard import BI, _ability, _full, _roll_keys, _spells, _states, _use
from tests.integration.rules.test_2014_fighter_eldritch_knight import _cast, _spell
from tests.integration.rules.test_2014_rogue import _full_hp, _hurt
from tests.integration.rules.test_2024_bard import GLAMOUR, LORE, _bard24, _set_uses, _slot_used, _turn

BEGUILING = "bard.beguiling_magic"
CHARMED, FRIGHTENED = "bard.beguiling_magic_charmed", "bard.beguiling_magic_frightened"
MAJESTY = "bard.mantle_of_majesty"
UNBREAKABLE, MISS = "bard.unbreakable_majesty", "bard.unbreakable_majesty_miss"


async def _command(client, cid) -> dict:
    return next(s for s in (await _spells(client, cid)).values() if s["srd_index"] == "command")


# ---------------------------------------------------------------------------
# Magia Ammaliante
# ---------------------------------------------------------------------------

async def test_beguiling_magic_makes_charm_person_and_mirror_image_always_prepared(client):
    names = await _spells(client, await _bard24(client, 3, GLAMOUR))
    for name in ("Charme su persone", "Immagine speculare"):
        assert names[name]["always_prepared"] and names[name]["is_prepared"]
    assert "Comando" not in names  # arriva al 6°
    assert "Charme su persone" not in await _spells(client, await _bard24(client, 3, LORE))


async def test_beguiling_magic_is_one_use_per_long_rest(client):
    row = await _ability(client, await _bard24(client, 3, GLAMOUR), BEGUILING)
    assert (row["max_uses"], row["uses"], row["restoration_type"]) == (1, 1, "long_rest")


async def test_beguiling_magic_is_offered_after_an_enchantment_or_illusion_cast_with_a_slot(client):
    cid = await _bard24(client, 3, GLAMOUR)
    charm = await _spell(client, cid, "Charme su persone", 1, school="enchantment")
    image = await _spell(client, cid, "Immagine minore", 1, school="illusion")
    bolt = await _spell(client, cid, "Dardo di fuoco", 1, school="evocation")
    cantrip = await _spell(client, cid, "Beffa crudele", 0, school="enchantment")
    for spell in (charm, image):
        keys = await _roll_keys(client, cid, "cast", spell_id=spell)
        assert CHARMED in keys and FRIGHTENED in keys
    for spell in (bolt, cantrip):
        assert CHARMED not in await _roll_keys(client, cid, "cast", spell_id=spell)
    lore = await _bard24(client, 3, LORE)
    lore_charm = await _spell(client, lore, "Charme su persone", 1, school="enchantment")
    assert CHARMED not in await _roll_keys(client, lore, "cast", spell_id=lore_charm)


async def test_beguiling_magic_is_offered_on_the_real_granted_spells(client):
    cid = await _bard24(client, 6, GLAMOUR)
    names = await _spells(client, cid)
    for name in ("Charme su persone", "Immagine speculare", "Comando"):
        keys = await _roll_keys(client, cid, "cast", spell_id=names[name]["id"])
        assert CHARMED in keys and FRIGHTENED in keys, name


async def test_beguiling_magic_needs_a_slot_so_not_a_free_cast_or_a_ritual(client):
    cid = await _bard24(client, 6, GLAMOUR)
    spell = await _command(client, cid)
    assert CHARMED in await _roll_keys(client, cid, "cast", spell_id=spell["id"])
    assert CHARMED not in await _roll_keys(client, cid, "cast", spell_id=spell["id"], slotless="true")
    await _use(client, cid, MAJESTY)
    await client.post(f"/characters/{cid}/turn/new")
    r = await _cast(client, cid, spell["id"], free_cast=True, options=[FRIGHTENED])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"
    assert (await _ability(client, cid, BEGUILING))["uses"] == 1 and await _slot_used(client, cid, 1) == 0


async def test_beguiling_magic_asks_for_a_wisdom_save_against_the_spell_dc_and_spends_the_use(client):
    cid = await _bard24(client, 3, GLAMOUR, charisma=16)  # CD 8 + 2 + 3
    charm = await _spell(client, cid, "Charme su persone", 1, school="enchantment")
    r = await _cast(client, cid, charm, slot_level=1, options=[FRIGHTENED])
    assert r.status_code == 200, r.text
    block = r.json()["option_result"]
    assert block["targets"] == [FRIGHTENED]
    assert "CD 13" in block["effects"][0]["it"] and "DC 13" in block["effects"][0]["en"] and "Spaventat" in block["effects"][0]["it"]
    effect = (await client.get(f"/characters/{cid}/target-effects/{FRIGHTENED}")).json()["result"]
    assert (effect["condition"], effect["save_ability"], effect["save_dc"], effect["rounds"], effect["repeat_save"]) == (
        "frightened", "wisdom", 13, 10, "end")
    assert (await _ability(client, cid, BEGUILING))["uses"] == 0 and await _slot_used(client, cid, 1) == 1
    assert FRIGHTENED not in await _roll_keys(client, cid, "cast", spell_id=charm)  # una volta per riposo lungo


async def test_beguiling_magic_can_charm_instead(client):
    cid = await _bard24(client, 3, GLAMOUR)
    image = await _spell(client, cid, "Immagine minore", 1, school="illusion")
    assert (await _cast(client, cid, image, slot_level=1, options=[CHARMED])).status_code == 200
    effect = (await client.get(f"/characters/{cid}/target-effects/{CHARMED}")).json()["result"]
    assert effect["condition"] == "charmed"


async def test_beguiling_magic_can_be_restored_by_spending_an_inspiration_use_without_an_action(client):
    cid = await _bard24(client, 3, GLAMOUR, charisma=16)
    r = await _use(client, cid, BEGUILING)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "feature_unavailable"  # c'è già l'uso
    await _set_uses(client, cid, BEGUILING, 0)
    r = await _use(client, cid, BEGUILING)
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, BEGUILING))["uses"] == 1
    bi = await _ability(client, cid, BI)
    assert bi["uses"] == bi["max_uses"] - 1
    turn = await _turn(client, cid)
    assert not (turn["action_used"] or turn["bonus_used"] or turn["reaction_used"])


async def test_restoring_beguiling_magic_needs_an_inspiration_use(client):
    cid = await _bard24(client, 3, GLAMOUR, charisma=16)
    await _set_uses(client, cid, BEGUILING, 0)
    await _set_uses(client, cid, BI, 0)
    r = await _use(client, cid, BEGUILING)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    assert (await _ability(client, cid, BEGUILING))["uses"] == 0


# ---------------------------------------------------------------------------
# Mantello di Ispirazione
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,die", [(3, 6), (5, 8), (10, 10), (15, 12)])
async def test_mantle_of_inspiration_rolls_the_die_and_gives_double_as_temporary_hit_points(client, level, die):
    cid = await _bard24(client, level, GLAMOUR, charisma=16)
    r = await _use(client, cid, "bard.mantle_of_inspiration")
    assert r.status_code == 200, r.text
    [roll] = r.json()["rolls"]
    assert 1 <= roll <= die and r.json()["given"] == 2 * roll
    message = r.json()["message"]
    assert "3 creature" in message["it"] and "3 creatures" in message["en"] and "18 m" in message["it"]
    bi = await _ability(client, cid, BI)
    assert bi["uses"] == bi["max_uses"] - 1
    assert (await _turn(client, cid))["bonus_used"] is True


async def test_mantle_of_inspiration_targets_at_least_one_creature(client):
    cid = await _bard24(client, 3, GLAMOUR, charisma=8)
    assert "1 creatura" in (await _use(client, cid, "bard.mantle_of_inspiration")).json()["message"]["it"]


async def test_mantle_of_inspiration_without_inspiration_uses_keeps_the_bonus_action(client):
    cid = await _bard24(client, 3, GLAMOUR, charisma=8)
    await _set_uses(client, cid, BI, 0)
    r = await _use(client, cid, "bard.mantle_of_inspiration")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    assert (await _turn(client, cid))["bonus_used"] is False


# ---------------------------------------------------------------------------
# Mantello di Maestà
# ---------------------------------------------------------------------------

async def test_mantle_of_majesty_brings_command_always_prepared_and_one_use_per_long_rest(client):
    cid = await _bard24(client, 6, GLAMOUR)
    spell = await _command(client, cid)
    assert spell["always_prepared"] and spell["is_prepared"]
    row = await _ability(client, cid, MAJESTY)
    assert (row["max_uses"], row["restoration_type"]) == (1, "long_rest")
    assert MAJESTY not in {a["feature_key"] for a in (await _full(client, await _bard24(client, 5, GLAMOUR)))["abilities"]}


async def test_mantle_of_majesty_is_a_bonus_action_that_starts_concentration_for_a_minute(client):
    cid = await _bard24(client, 6, GLAMOUR)
    r = await _use(client, cid, MAJESTY)
    assert r.status_code == 200, r.text
    state = r.json()["state"]
    assert (state["key"], state["rounds_left"]) == ("mantle_of_majesty", 10)
    assert state["data"]["free_cast"] == "command" and MAJESTY in state["data"]["others"]
    assert "Comando" in r.json()["message"]["it"] and "senza slot" in r.json()["message"]["it"]
    assert (await _turn(client, cid))["bonus_used"] is True and "concentration_end" in state["ends_on"]
    assert (await _ability(client, cid, MAJESTY))["uses"] == 0
    again = await _use(client, cid, MAJESTY)
    assert again.status_code == 409


async def test_during_the_mantle_command_is_cast_as_a_bonus_action_without_a_slot_every_turn(client):
    cid = await _bard24(client, 6, GLAMOUR)
    spell = await _command(client, cid)
    await _use(client, cid, MAJESTY)
    await client.post(f"/characters/{cid}/turn/new")
    for _ in range(2):  # il Comando si ripete: lo stato non si chiude col lancio
        r = await _cast(client, cid, spell["id"], free_cast=True)
        assert r.status_code == 200, r.text
        turn = await _turn(client, cid)
        assert turn["bonus_used"] is True and turn["action_used"] is False
        again = await _cast(client, cid, spell["id"], free_cast=True)
        assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"
        await client.post(f"/characters/{cid}/turn/new")
    assert await _slot_used(client, cid, 1) == 0
    assert any(s["key"] == "mantle_of_majesty" for s in await _states(client, cid))


async def test_the_free_command_needs_the_mantle_and_ends_with_the_concentration(client):
    cid = await _bard24(client, 6, GLAMOUR)
    spell = await _command(client, cid)
    r = await _cast(client, cid, spell["id"], free_cast=True)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "free_cast_unavailable"
    await _use(client, cid, MAJESTY)
    assert (await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})).status_code == 200
    assert not any(s["key"] == "mantle_of_majesty" for s in await _states(client, cid))
    await client.post(f"/characters/{cid}/turn/new")
    r = await _cast(client, cid, spell["id"], free_cast=True)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "free_cast_unavailable"


async def test_mantle_of_majesty_is_restored_with_a_slot_of_third_level_or_higher(client):
    cid = await _bard24(client, 6, GLAMOUR)
    await _use(client, cid, MAJESTY)
    await client.post(f"/characters/{cid}/turn/new")
    low = await _use(client, cid, MAJESTY, params={"restore": True, "slot_level": "2"})
    assert low.status_code == 422 and low.json()["detail"]["code"] == "invalid_choice"
    missing = await _use(client, cid, MAJESTY, params={"restore": True})
    assert missing.status_code == 422
    assert (await _ability(client, cid, MAJESTY))["uses"] == 0 and await _slot_used(client, cid, 3) == 0
    r = await _use(client, cid, MAJESTY, params={"restore": True, "slot_level": "3"})
    assert r.status_code == 200, r.text
    assert await _slot_used(client, cid, 3) == 1
    assert (await _ability(client, cid, MAJESTY))["uses"] == 0  # ripristinato e subito speso per questo mantello
    assert (await _turn(client, cid))["bonus_used"] is True


# ---------------------------------------------------------------------------
# Maestà Infrangibile
# ---------------------------------------------------------------------------

async def test_unbreakable_majesty_is_a_bonus_action_for_a_minute_once_per_short_or_long_rest(client):
    cid = await _bard24(client, 14, GLAMOUR, charisma=16)
    row = await _ability(client, cid, UNBREAKABLE)
    assert (row["max_uses"], row["restoration_type"]) == (1, "short_rest")
    r = await _use(client, cid, UNBREAKABLE)
    assert r.status_code == 200, r.text
    assert (r.json()["state"]["key"], r.json()["state"]["rounds_left"]) == ("unbreakable_majesty", 10)
    assert (await _turn(client, cid))["bonus_used"] is True
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert (await _ability(client, cid, UNBREAKABLE))["uses"] == 1


async def test_unbreakable_majesty_turns_a_hit_into_a_miss_when_the_attacker_fails_the_save(client):
    cid = await _bard24(client, 14, GLAMOUR, charisma=16)  # CD 8 + 5 + 3
    await _full_hp(client, cid)
    r = await _hurt(client, cid, 20, MISS)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"
    await _use(client, cid, UNBREAKABLE)
    [state] = await _states(client, cid)
    assert (state["data"]["dc"], state["data"]["save"]) == (16, "charisma") and UNBREAKABLE in state["data"]["others"]
    hit = (await _hurt(client, cid, 20, MISS)).json()
    assert hit["current_hit_points"] == 60
    assert "CD 16" in hit["option_result"]["effects"][0]["it"] and "DC 16" in hit["option_result"]["effects"][0]["en"]
    assert (await _hurt(client, cid, 20)).json()["current_hit_points"] == 40  # un'altra creatura, o il tiro non è il primo
    assert MISS in await _roll_keys(client, cid, "damage_taken")  # vale per ogni creatura: lo stato resta


async def test_unbreakable_majesty_ends_when_the_bard_is_incapacitated(client):
    cid = await _bard24(client, 14, GLAMOUR)
    await _use(client, cid, UNBREAKABLE)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"stunned": True}})
    assert await _states(client, cid) == []
    assert MISS not in await _roll_keys(client, cid, "damage_taken")
