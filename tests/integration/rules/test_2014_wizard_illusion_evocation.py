"""Scuola di Illusione e di Invocazione 2014 (Task 30): Illusione Minore Migliorata, Illusioni Duttili, Sosia Illusorio, Realtà
Illusoria; Plasmare Incantesimi, Trucchetto Potente, Invocazione Potente, Saturazione Magica."""
from __future__ import annotations

import random

import pytest

from tests.integration.rules.test_2014_bard import _ability, _full, _roll_keys, _use
from tests.integration.rules.test_2014_fighter_eldritch_knight import _cast, _spell
from tests.integration.rules.test_2014_paladin import _rest
from tests.integration.rules.test_2014_wizard import _choice, _wizard

PICK, MALLEABLE, SELF, REALITY = "improved_minor_illusion", "wizard.malleable_illusions", "wizard.illusory_self", "wizard.illusory_reality"
SCULPT, EMPOWERED, OVERCHANNEL = "wizard.sculpt_spells", "wizard.empowered_evocation", "wizard.overchannel"


async def _turn(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]


async def _states(client, cid) -> dict[str, dict]:
    return {s["key"]: s for s in (await _full(client, cid))["active_states"] or []}


async def _illusion(client, cid, level=1, duration="Concentrazione, fino a 1 minuto", name="Immagine silenziosa", **extra) -> int:
    return await _spell(client, cid, name, level, school="illusion", casting_time="1 azione", duration=duration, **extra)


# ---------------------------------------------------------------------------
# Illusione Minore Migliorata
# ---------------------------------------------------------------------------

async def test_improved_minor_illusion_is_a_free_cantrip_pick_for_the_illusionist(client):
    cid = await _wizard(client, 2, "illusion")
    pick = _choice(await _full(client, cid), PICK)
    assert pick["count"] == 1 and pick["spell_pick"]["free"] is True and pick["spell_pick"]["max_level"] == 0
    assert _choice(await _full(client, await _wizard(client, 2, "evocation")), PICK) is None
    assert _choice(await _full(client, await _wizard(client, 1)), PICK) is None


async def test_the_picked_cantrip_stays_outside_the_cantrip_limit_and_must_be_a_cantrip(client):
    cid = await _wizard(client, 2, "illusion")
    pick = _choice(await _full(client, cid), PICK)
    wrong = await client.post(f"/characters/{cid}/spells", json={"name": "Scudo", "level": 1, "pick_id": pick["id"]})
    assert wrong.status_code == 422 and wrong.json()["detail"]["code"] == "spell_pick_level"
    ok = await client.post(f"/characters/{cid}/spells", json={"name": "Illusione minore", "level": 0, "pick_id": pick["id"]})
    assert ok.status_code == 201, ok.text
    full = await _full(client, cid)
    assert full["spellcasting"]["limits"][0]["cantrips_count"] == 0 and _choice(full, PICK) is None


# ---------------------------------------------------------------------------
# Illusioni Duttili
# ---------------------------------------------------------------------------

async def test_malleable_illusions_needs_an_illusion_that_lasts_a_minute(client):
    cid = await _wizard(client, 6, "illusion")
    refused = await _use(client, cid, MALLEABLE)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "feature_unavailable"
    short = await _illusion(client, cid, 1, "1 round", "Bagliore")
    assert (await _cast(client, cid, short, slot_level=1)).status_code == 200
    assert (await _use(client, cid, MALLEABLE)).status_code == 409
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _cast(client, cid, await _illusion(client, cid), slot_level=1)).status_code == 200
    r = await _use(client, cid, MALLEABLE)
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["action_used"] is True


async def test_a_cantrip_illusion_of_one_minute_also_opens_malleable_illusions(client):
    cid = await _wizard(client, 6, "illusion")
    minor = await _illusion(client, cid, 0, "1 minuto", "Illusione minore")
    assert (await _cast(client, cid, minor)).status_code == 200
    assert (await _use(client, cid, MALLEABLE)).status_code == 200


async def test_malleable_illusions_ends_with_the_duration_of_the_spell(client):
    cid = await _wizard(client, 6, "illusion")
    assert (await _cast(client, cid, await _illusion(client, cid, 1, "1 minuto"), slot_level=1)).status_code == 200
    assert (await _states(client, cid))["window_illusion"]["rounds_left"] == 10
    for _ in range(10):
        r = await client.post(f"/characters/{cid}/rounds/tick")
        assert r.status_code == 200, r.text
    assert "window_illusion" not in await _states(client, cid)


async def test_malleable_illusions_is_the_illusionists_from_level_6(client):
    assert await _ability(client, await _wizard(client, 5, "illusion"), MALLEABLE) is None
    assert await _ability(client, await _wizard(client, 6, "evocation"), MALLEABLE) is None


# ---------------------------------------------------------------------------
# Sosia Illusorio
# ---------------------------------------------------------------------------

async def test_illusory_self_is_a_reaction_with_one_use_back_on_a_short_rest(client):
    assert await _ability(client, await _wizard(client, 9, "illusion"), SELF) is None
    cid = await _wizard(client, 10, "illusion")
    row = await _ability(client, cid, SELF)
    assert (row["max_uses"], row["restoration_type"], row["has_on_use"]) == (1, "short_rest", True)
    assert (await _use(client, cid, SELF)).status_code == 200
    assert (await _turn(client, cid))["reaction_used"] is True and (await _ability(client, cid, SELF))["uses"] == 0
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid, SELF)).status_code == 409
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, SELF))["uses"] == 1


# ---------------------------------------------------------------------------
# Realtà Illusoria
# ---------------------------------------------------------------------------

async def test_illusory_reality_is_a_bonus_action_in_the_turn_of_an_illusion_of_first_level_or_more(client):
    cid = await _wizard(client, 14, "illusion")
    refused = await _use(client, cid, REALITY, params={"object": "Ponte"})
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "feature_unavailable"
    assert (await _cast(client, cid, await _illusion(client, cid), slot_level=1)).status_code == 200
    assert (await _use(client, cid, REALITY)).status_code == 422  # serve il nome dell'oggetto
    r = await _use(client, cid, REALITY, params={"object": "Ponte di corda"})
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["bonus_used"] is True
    state = (await _states(client, cid))["illusory_reality"]
    assert state["rounds_left"] == 10 and state["data"]["object"] == "Ponte di corda"


async def test_illusory_reality_does_not_survive_the_turn_or_a_cantrip(client):
    cid = await _wizard(client, 14, "illusion")
    assert (await _cast(client, cid, await _illusion(client, cid, 0, "1 minuto", "Illusione minore"))).status_code == 200
    assert (await _use(client, cid, REALITY, params={"object": "Ponte"})).status_code == 409  # un trucchetto non basta
    assert (await _cast(client, cid, await _illusion(client, cid), slot_level=1)).status_code == 200
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid, REALITY, params={"object": "Ponte"})).status_code == 409  # il turno è finito


async def test_illusory_reality_is_used_once_per_cast(client):
    cid = await _wizard(client, 14, "illusion")
    await _cast(client, cid, await _illusion(client, cid), slot_level=1)
    assert (await _use(client, cid, REALITY, params={"object": "Ponte"})).status_code == 200
    assert (await _use(client, cid, REALITY, params={"object": "Torre"})).status_code == 409


# ---------------------------------------------------------------------------
# Plasmare Incantesimi
# ---------------------------------------------------------------------------

async def _evocation(client, cid, name="Palla di fuoco", level=3, save="DEX", **extra) -> int:
    return await _spell(client, cid, name, level, school="evocation", casting_time="1 azione", attack_save=save,
                        damage_dice="8d6", damage_type="fire", **extra)


async def test_sculpt_spells_names_one_plus_the_spell_level_creatures(client):
    cid = await _wizard(client, 7, "evocation")
    ball = await _evocation(client, cid)
    assert SCULPT in await _roll_keys(client, cid, "cast", spell_id=ball, casting_level=3)
    r = await client.post(f"/characters/{cid}/spells/{ball}/use", json={"slot_level": 3, "options": [SCULPT]})
    assert r.status_code == 200, r.text
    effect = r.json()["option_result"]["effects"][0]
    assert " 4 " in effect["it"] and " 4 " in effect["en"]  # 1 + il livello 3
    higher = await client.post(f"/characters/{cid}/spells/{ball}/use", json={"slot_level": 4, "options": [SCULPT]})
    assert " 5 " in higher.json()["option_result"]["effects"][0]["it"]  # lo slot superiore alza il livello dell'incantesimo


async def test_sculpt_spells_needs_an_evocation_with_a_save(client):
    cid = await _wizard(client, 5, "evocation")
    attack = await _evocation(client, cid, "Raggio rovente", 2, "ATK")
    other = await _spell(client, cid, "Sonno", 1, school="enchantment", attack_save="WIS", casting_time="1 azione")
    assert SCULPT not in await _roll_keys(client, cid, "cast", spell_id=attack, casting_level=2)
    assert SCULPT not in await _roll_keys(client, cid, "cast", spell_id=other, casting_level=1)


# ---------------------------------------------------------------------------
# Trucchetto Potente
# ---------------------------------------------------------------------------

async def _damage(client, cid, spell, **body):
    r = await client.post(f"/characters/{cid}/spells/{spell}/roll_damage", json=body)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("level,half", [(5, None), (6, 8)])
async def test_potent_cantrip_gives_half_damage_to_a_creature_that_saves_from_level_6(client, level, half):
    cid = await _wizard(client, level, "evocation")
    cantrip = await _spell(client, cid, "Spruzzo velenoso", 0, school="conjuration", attack_save="CON", damage_dice="1d12",
                           damage_type="poison", casting_time="1 azione")
    result = await _damage(client, cid, cantrip, main_rolls=[8, 8])
    assert result.get("save_success_damage") == half


async def test_potent_cantrip_is_only_for_a_save_cantrip(client):
    cid = await _wizard(client, 6, "evocation")
    attack = await _spell(client, cid, "Raggio di fuoco", 0, school="evocation", attack_save="ATK", damage_dice="1d10", damage_type="fire")
    leveled = await _evocation(client, cid, "Mani brucianti", 1, "DEX")
    assert (await _damage(client, cid, attack)).get("save_success_damage") is None
    assert (await _damage(client, cid, leveled, casting_level=1)).get("save_success_damage") is None


async def test_potent_cantrip_belongs_to_the_evoker(client):
    cid = await _wizard(client, 6, "abjuration")
    cantrip = await _spell(client, cid, "Spruzzo velenoso", 0, school="conjuration", attack_save="CON", damage_dice="1d12", damage_type="poison")
    assert (await _damage(client, cid, cantrip)).get("save_success_damage") is None


# ---------------------------------------------------------------------------
# Invocazione Potente
# ---------------------------------------------------------------------------

async def test_empowered_evocation_adds_intelligence_to_the_damage_of_evocations_only(client):
    cid = await _wizard(client, 10, "evocation", intelligence=18)  # +4
    ball = await _evocation(client, cid)
    other = await _spell(client, cid, "Palla di fuoco malefica", 3, school="necromancy", attack_save="DEX", damage_dice="8d6",
                         damage_type="necrotic")
    assert (await _damage(client, cid, ball, casting_level=3, main_rolls=[1] * 8))["total"] == 8 + 4
    assert (await _damage(client, cid, other, casting_level=3, main_rolls=[1] * 8))["total"] == 8


async def test_empowered_evocation_needs_level_10_and_the_school(client):
    for level, school in ((9, "evocation"), (10, "abjuration")):
        cid = await _wizard(client, level, school, intelligence=18)
        assert (await _damage(client, cid, await _evocation(client, cid), casting_level=3, main_rolls=[1] * 8))["total"] == 8


# ---------------------------------------------------------------------------
# Saturazione Magica
# ---------------------------------------------------------------------------

async def _overchannel(client, cid, spell, level=None, monkeypatch=None):
    return await client.post(f"/characters/{cid}/spells/{spell}/roll_damage", json={
        "casting_level": level or 1, "options": [OVERCHANNEL]})


async def _hp(client, cid, value=200) -> None:
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": value})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": value})


async def test_overchannel_is_offered_for_a_damaging_spell_of_levels_1_to_5(client):
    cid = await _wizard(client, 14, "evocation")
    keys = {}
    for level in (0, 1, 5, 6):
        keys[level] = OVERCHANNEL in await _roll_keys(client, cid, "spell_damage", spell_id=await _evocation(client, cid, f"Prova {level}", level))
    assert keys == {0: False, 1: True, 5: True, 6: False}
    no_damage = await _spell(client, cid, "Scudo", 1, school="abjuration")
    assert OVERCHANNEL not in await _roll_keys(client, cid, "spell_damage", spell_id=no_damage)
    low = await _wizard(client, 13, "evocation")
    assert OVERCHANNEL not in await _roll_keys(client, low, "spell_damage", spell_id=await _evocation(client, low))


async def test_the_first_overchannel_deals_maximum_damage_and_hurts_nobody(client, monkeypatch):
    cid = await _wizard(client, 14, "evocation")
    await _hp(client, cid)
    ball = await _evocation(client, cid)
    monkeypatch.setattr(random, "randint", lambda a, b: 1)
    result = await _overchannel(client, cid, ball, 3)
    assert result.status_code == 200, result.text
    assert result.json()["total"] == 48  # 8d6 al massimo
    assert (await _full(client, cid))["current_hit_points"] == 200
    assert (await _states(client, cid))["overchannel"]["data"]["uses"] == 1


@pytest.mark.parametrize("uses,spell_level", [(2, 3), (3, 3), (2, 1), (4, 5)])
async def test_each_later_overchannel_deals_necrotic_damage_that_ignores_resistance(client, monkeypatch, uses, spell_level):
    cid = await _wizard(client, 14, "evocation")
    await _hp(client, cid, 1000)
    spell = await _evocation(client, cid, "Prova", spell_level)
    monkeypatch.setattr(random, "randint", lambda a, b: b)  # ogni dado al massimo: d12 = 12
    for n in range(1, uses + 1):
        result = await _overchannel(client, cid, spell, spell_level)
        assert result.status_code == 200, result.text
        effects = str(result.json()["option_result"]["effects"])
        assert ("necrotici" in effects) == (n >= 2)  # il primo uso non costa nulla
        assert (await _states(client, cid))["overchannel"]["data"]["uses"] == n
    # il secondo uso: 2d12 per livello, il terzo 3d12 per livello, e così via
    assert (await _full(client, cid))["current_hit_points"] == 1000 - 12 * spell_level * sum(range(2, uses + 1))


async def test_a_long_rest_resets_the_overchannel_count(client, monkeypatch):
    cid = await _wizard(client, 14, "evocation")
    await _hp(client, cid)
    spell = await _evocation(client, cid, "Prova", 1)
    monkeypatch.setattr(random, "randint", lambda a, b: b)
    await _overchannel(client, cid, spell, 1)
    await _overchannel(client, cid, spell, 1)
    await _rest(client, cid, "long")
    assert "overchannel" not in await _states(client, cid)
    hp = (await _full(client, cid))["current_hit_points"]
    await _overchannel(client, cid, spell, 1)
    assert (await _full(client, cid))["current_hit_points"] == hp  # di nuovo il primo uso


async def test_overchannel_self_damage_uses_the_slot_level_of_the_cast(client, monkeypatch):
    cid = await _wizard(client, 14, "evocation")
    await _hp(client, cid, 1000)
    ball = await _evocation(client, cid, "Palla di fuoco", 3)
    monkeypatch.setattr(random, "randint", lambda a, b: b)
    await _overchannel(client, cid, ball, 5)
    result = await _overchannel(client, cid, ball, 5)
    assert result.status_code == 200, result.text
    assert (await _full(client, cid))["current_hit_points"] == 1000 - 12 * 2 * 5  # 2d12 per livello di lancio (5), non del 3


async def test_overchannel_is_not_offered_when_the_cast_level_is_six_or_more(client):
    cid = await _wizard(client, 14, "evocation")
    spell = await _evocation(client, cid, "Palla di fuoco", 3)
    assert OVERCHANNEL in await _roll_keys(client, cid, "spell_damage", spell_id=spell, casting_level=5)
    assert OVERCHANNEL not in await _roll_keys(client, cid, "spell_damage", spell_id=spell, casting_level=6)


async def test_the_player_cannot_end_the_overchannel_count_by_hand(client, monkeypatch):
    cid = await _wizard(client, 14, "evocation")
    await _hp(client, cid, 1000)
    spell = await _evocation(client, cid, "Prova", 1)
    monkeypatch.setattr(random, "randint", lambda a, b: b)
    await _overchannel(client, cid, spell, 1)
    r = await client.delete(f"/characters/{cid}/active-states/overchannel")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "state_locked"
    assert (await _states(client, cid))["overchannel"]["data"]["uses"] == 1
