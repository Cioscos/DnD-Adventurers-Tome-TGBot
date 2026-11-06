"""Scuola di Abiurazione 2014 (Task 30): il Sapiente delle otto scuole, Interdizione Arcana e Proiettata, Abiurazione
Migliorata, Resistenza agli Incantesimi."""
from __future__ import annotations

import pytest

from tests.integration.rules.test_2014_bard import _full, _roll_keys, _use
from tests.integration.rules.test_2014_fighter_eldritch_knight import _cast, _spell
from tests.integration.rules.test_2014_paladin import _rest
from tests.integration.rules.test_2014_wizard import SCHOOLS, _book, _gold, _purse, _wizard

WARD, PROJECTED = "wizard.arcane_ward", "wizard.projected_ward"
IMPROVED, RESISTANCE = "wizard.improved_abjuration", "wizard.spell_resistance"
RESISTANCE_DAMAGE = "wizard.spell_resistance_damage"


async def _hp(client, cid, maximum=100, current=None) -> None:
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": maximum})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": current or maximum})


async def _damage(client, cid, value, **extra):
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": value, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def _ward(full: dict) -> dict | None:
    return next((s for s in full["active_states"] or [] if s["key"] == "arcane_ward"), None)


async def _abjuration(client, cid, name="Scudo", level=1, school="abjuration", **extra) -> int:
    return await _spell(client, cid, name, level, school=school, casting_time="1 azione", **extra)


async def _cast_at(client, cid, sid, level=None):
    r = await _cast(client, cid, sid, slot_level=level or 1)
    assert r.status_code == 200, r.text
    await client.post(f"/characters/{cid}/turn/new")
    return r


# ---------------------------------------------------------------------------
# I Sapienti: tempo e costo della copia dimezzati per la propria scuola
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("own", sorted(SCHOOLS))
async def test_each_savant_halves_the_copy_only_for_its_own_school(client, own):
    cid = await _wizard(client, 5, own)
    for school in SCHOOLS:
        r = await client.get(f"/characters/{cid}/spellbook/cost", params={"level": 2, "school": school})
        assert r.json() == ({"hours": 2, "gold": 50, "halved": True} if school == own else {"hours": 4, "gold": 100, "halved": False})
    back = await client.get(f"/characters/{cid}/spellbook/cost", params={"level": 3, "school": own, "mode": "backup"})
    assert back.json() == {"hours": 1.5, "gold": 15, "halved": True}


async def test_the_savant_also_understands_the_italian_school_names(client):
    cid = await _wizard(client, 5, "abjuration")
    r = await client.get(f"/characters/{cid}/spellbook/cost", params={"level": 1, "school": "abiurazione"})
    assert r.json()["halved"] is True


async def test_the_savant_halves_what_a_copy_costs_in_gold(client):
    cid = await _wizard(client, 5, "abjuration")
    await _gold(client, cid, 200)
    sid = await _abjuration(client, cid, level=2)
    assert (await client.post(f"/characters/{cid}/spells/{sid}/copy", json={"mode": "copy"})).status_code == 200
    assert await _purse(client, cid) == 200 - 50
    other = await _spell(client, cid, "Raggio rovente", 2, school="evocation")
    assert (await client.post(f"/characters/{cid}/spells/{other}/copy", json={"mode": "copy"})).status_code == 200
    assert await _purse(client, cid) == 200 - 50 - 100


async def test_without_a_school_nothing_is_halved(client):
    cid = await _wizard(client, 5)
    r = await client.get(f"/characters/{cid}/spellbook/cost", params={"level": 2, "school": "abjuration"})
    assert r.json()["halved"] is False


# ---------------------------------------------------------------------------
# Interdizione Arcana
# ---------------------------------------------------------------------------

async def test_casting_an_abjuration_creates_a_ward_with_twice_the_level_plus_intelligence(client):
    cid = await _wizard(client, 6, "abjuration", intelligence=16)  # 2 x 6 + 3
    assert _ward(await _full(client, cid)) is None
    await _cast_at(client, cid, await _abjuration(client, cid))
    ward = _ward(await _full(client, cid))
    assert ward["data"]["hp"] == ward["data"]["max"] == 15


@pytest.mark.parametrize("kwargs", [
    {"level": 0, "school": "abjuration"}, {"level": 1, "school": "evocation"}, {"level": 1, "school": None}])
async def test_a_cantrip_or_another_school_creates_no_ward(client, kwargs):
    cid = await _wizard(client, 6, "abjuration")
    sid = await _spell(client, cid, "Prova", kwargs["level"], school=kwargs["school"], casting_time="1 azione")
    r = await _cast(client, cid, sid, slot_level=1)
    assert r.status_code == 200, r.text
    assert _ward(await _full(client, cid)) is None


async def test_only_the_abjurer_has_a_ward(client):
    cid = await _wizard(client, 6, "evocation")
    await _cast_at(client, cid, await _abjuration(client, cid))
    assert _ward(await _full(client, cid)) is None


async def test_the_ward_takes_the_damage_before_the_wizard_and_the_rest_goes_through(client):
    cid = await _wizard(client, 6, "abjuration", intelligence=16)
    await _hp(client, cid)
    await _cast_at(client, cid, await _abjuration(client, cid))  # 15 PF di interdizione
    after = await _damage(client, cid, 10)
    assert after["current_hit_points"] == 100 and _ward(after)["data"]["hp"] == 5
    after = await _damage(client, cid, 12)
    assert after["current_hit_points"] == 93 and _ward(after)["data"]["hp"] == 0  # 7 residui
    after = await _damage(client, cid, 4)
    assert after["current_hit_points"] == 89 and _ward(after) is not None  # a 0 PF non assorbe più, ma c'è ancora


async def test_the_ward_comes_before_temporary_hit_points(client):
    cid = await _wizard(client, 6, "abjuration", intelligence=16)
    await _hp(client, cid)
    await _cast_at(client, cid, await _abjuration(client, cid))
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_temp", "value": 8})
    after = await _damage(client, cid, 20)  # 15 alla interdizione, 5 ai PF temporanei
    assert _ward(after)["data"]["hp"] == 0 and after["temp_hp"] == 3 and after["current_hit_points"] == 100


async def test_the_ward_takes_the_damage_after_resistance(client):
    cid = await _wizard(client, 6, "abjuration", intelligence=16)
    await _hp(client, cid)
    await _cast_at(client, cid, await _abjuration(client, cid))
    await _damage(client, cid, 8, raw_value=16, damage_modifier="half")
    assert _ward(await _full(client, cid))["data"]["hp"] == 7


async def test_every_abjuration_recharges_the_ward_by_twice_the_spell_level_up_to_the_maximum(client):
    cid = await _wizard(client, 6, "abjuration", intelligence=16)
    await _hp(client, cid)
    first = await _abjuration(client, cid)
    await _cast_at(client, cid, first)
    await _damage(client, cid, 15)
    await _cast_at(client, cid, await _abjuration(client, cid, "Protezione dal bene e dal male", level=2), 2)
    assert _ward(await _full(client, cid))["data"]["hp"] == 4  # 2 x 2
    await _cast_at(client, cid, first, 3)
    assert _ward(await _full(client, cid))["data"]["hp"] == 6  # il livello è quello dell'incantesimo, non dello slot
    for n in range(2):
        await _cast_at(client, cid, await _abjuration(client, cid, f"Prova {n}", level=3), 3)
    assert _ward(await _full(client, cid))["data"]["hp"] == 15  # mai oltre il massimo


async def test_a_ward_at_zero_is_recharged_and_no_second_ward_is_made_before_a_long_rest(client):
    cid = await _wizard(client, 6, "abjuration", intelligence=16)
    await _hp(client, cid)
    sid = await _abjuration(client, cid)
    await _cast_at(client, cid, sid)
    await _damage(client, cid, 40)
    await _cast_at(client, cid, sid)
    full = await _full(client, cid)
    assert len([s for s in full["active_states"] if s["key"] == "arcane_ward"]) == 1 and _ward(full)["data"]["hp"] == 2


async def test_a_long_rest_ends_the_ward_and_the_next_abjuration_makes_a_new_one(client):
    cid = await _wizard(client, 6, "abjuration", intelligence=16)
    sid = await _abjuration(client, cid)
    await _cast_at(client, cid, sid)
    await _rest(client, cid, "short")
    assert _ward(await _full(client, cid)) is not None
    await _rest(client, cid, "long")
    assert _ward(await _full(client, cid)) is None
    await _cast_at(client, cid, sid)
    assert _ward(await _full(client, cid))["data"]["hp"] == 15


async def test_damage_the_ward_took_comes_back_with_the_hp_undo(client):
    cid = await _wizard(client, 6, "abjuration", intelligence=16)
    await _hp(client, cid)
    await _cast_at(client, cid, await _abjuration(client, cid))
    done = await _damage(client, cid, 20)
    undo = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": done["hp_undo_id"]})
    assert undo.status_code == 200, undo.text
    assert undo.json()["current_hit_points"] == 100 and _ward(undo.json())["data"]["hp"] == 15


async def test_damage_fully_absorbed_by_the_ward_asks_no_concentration_save(client):
    cid = await _wizard(client, 6, "abjuration", intelligence=16)
    await _hp(client, cid)
    conc = await _spell(client, cid, "Benedizione", 1, school="enchantment", is_concentration=True, duration="Concentrazione, fino a 1 minuto")
    await _cast_at(client, cid, await _abjuration(client, cid))
    assert (await _cast(client, cid, conc, slot_level=1)).status_code == 200
    taken = await _damage(client, cid, 10)
    assert taken.get("concentration_save") is None  # il danno è andato alla interdizione


# ---------------------------------------------------------------------------
# Interdizione Proiettata
# ---------------------------------------------------------------------------

async def _warded(client, level=6, **scores) -> int:
    cid = await _wizard(client, level, "abjuration", intelligence=16, **scores)
    await _hp(client, cid)
    await _cast_at(client, cid, await _abjuration(client, cid))
    return cid


async def test_projected_ward_is_a_reaction_from_level_6_with_an_active_ward(client):
    assert PROJECTED not in {a["feature_key"] for a in (await _full(client, await _wizard(client, 5, "abjuration")))["abilities"]}
    cid = await _warded(client)
    refused = await _use(client, await _wizard(client, 6, "abjuration"), PROJECTED, params={"damage": "6"})
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "feature_unavailable"  # nessuna interdizione
    r = await _use(client, cid, PROJECTED, params={"damage": "6"})
    assert r.status_code == 200, r.text
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]["reaction_used"] is True


async def test_projected_ward_absorbs_what_it_can_and_names_the_rest(client):
    cid = await _warded(client)
    r = await _use(client, cid, PROJECTED, params={"damage": "10"})
    assert _ward(await _full(client, cid))["data"]["hp"] == 5
    assert "0" in r.json()["message"]["it"] and "0" in r.json()["message"]["en"]
    await client.post(f"/characters/{cid}/turn/new")
    r = await _use(client, cid, PROJECTED, params={"damage": "9"})
    assert _ward(await _full(client, cid))["data"]["hp"] == 0
    assert "4" in r.json()["message"]["it"]  # 9 - 5 restano alla creatura


@pytest.mark.parametrize("damage", ["", "abc", "0", "-3", "1.5"])
async def test_projected_ward_needs_a_positive_whole_damage(client, damage):
    cid = await _warded(client)
    r = await _use(client, cid, PROJECTED, params={"damage": damage})
    assert r.status_code == 422
    assert _ward(await _full(client, cid))["data"]["hp"] == 15
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]["reaction_used"] is False


async def test_projected_ward_cannot_absorb_at_zero(client):
    cid = await _warded(client)
    await _damage(client, cid, 15)
    r = await _use(client, cid, PROJECTED, params={"damage": "5"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "feature_unavailable"


# ---------------------------------------------------------------------------
# Abiurazione Migliorata
# ---------------------------------------------------------------------------

async def _check_options(client, cid, ability="intelligence") -> list[str]:
    return await _roll_keys(client, cid, "ability", ability=ability)


async def test_improved_abjuration_adds_proficiency_to_the_check_of_a_counterspell(client):
    cid = await _wizard(client, 10, "abjuration")
    counter = await _spell(client, cid, "Controincantesimo", 3, school="abjuration", srd_index="counterspell", casting_time="1 reazione")
    assert IMPROVED not in await _check_options(client, cid)
    assert (await _cast(client, cid, counter, slot_level=3)).status_code == 200
    assert IMPROVED in await _check_options(client, cid)
    assert IMPROVED not in await _check_options(client, cid, "strength")
    plain = (await client.post(f"/characters/{cid}/ability_checks/intelligence/roll", json={"die": 10})).json()
    boosted = (await client.post(f"/characters/{cid}/ability_checks/intelligence/roll", json={"die": 10, "options": [IMPROVED]})).json()
    assert boosted["total"] == plain["total"] + 4  # competenza del 10° livello


async def test_improved_abjuration_also_covers_dispel_magic_and_stops_with_another_spell(client):
    cid = await _wizard(client, 10, "abjuration")
    dispel = await _spell(client, cid, "Dissolvi magie", 3, school="abjuration", srd_index="dispel-magic", casting_time="1 azione")
    other = await _spell(client, cid, "Scudo", 1, school="abjuration", srd_index="shield", casting_time="1 azione")
    await _cast(client, cid, dispel, slot_level=3)
    assert IMPROVED in await _check_options(client, cid)
    await client.post(f"/characters/{cid}/turn/new")
    await _cast(client, cid, other, slot_level=1)
    assert IMPROVED not in await _check_options(client, cid)


async def test_improved_abjuration_needs_level_10_and_the_school(client):
    for level, school in ((9, "abjuration"), (10, "divination")):
        cid = await _wizard(client, level, school)
        counter = await _spell(client, cid, "Controincantesimo", 3, school="abjuration", srd_index="counterspell", casting_time="1 reazione")
        await _cast(client, cid, counter, slot_level=3)
        assert IMPROVED not in await _check_options(client, cid)


# ---------------------------------------------------------------------------
# Resistenza agli Incantesimi
# ---------------------------------------------------------------------------

async def test_spell_resistance_is_advantage_on_saves_against_spells_from_level_14(client):
    low = await _wizard(client, 13, "abjuration")
    assert RESISTANCE not in await _roll_keys(client, low, "save", ability="dexterity")
    cid = await _wizard(client, 14, "abjuration")
    options = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "save", "ability": "dexterity"})).json()
    found = next(o for o in options if o["key"] == RESISTANCE)
    assert found["mode"] == "advantage" and found["phase"] == "before"
    assert RESISTANCE not in await _roll_keys(client, await _wizard(client, 14, "evocation"), "save", ability="dexterity")


async def test_spell_resistance_halves_the_damage_of_a_spell_once(client):
    cid = await _wizard(client, 14, "abjuration")
    await _hp(client, cid)
    assert RESISTANCE_DAMAGE in await _roll_keys(client, cid, "damage_taken", damage_type="fire")
    plain = await _damage(client, cid, 20, damage_type="fire")
    assert plain["current_hit_points"] == 80
    halved = await _damage(client, cid, 20, damage_type="fire", options=[RESISTANCE_DAMAGE])
    assert halved["current_hit_points"] == 70
    await _hp(client, cid)
    resisted = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20, "damage_type": "fire", "damage_modifier": "half",
                                                                  "raw_value": 40, "options": [RESISTANCE_DAMAGE]})
    assert resisted.json()["current_hit_points"] == 80  # già resistente: la resistenza conta una volta
