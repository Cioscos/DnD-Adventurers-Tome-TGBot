"""Circolo della Terra 2014 (Task 22): trucchetto bonus, territori e incantesimi del circolo, Andatura sul Territorio,
Interdizione della Natura, Rifugio della Natura."""
from __future__ import annotations

import pytest

from tests.integration.rules.test_2014_bard import _ability, _full, _roll_keys, _spells
from tests.integration.rules.test_2014_druid import _druid

# territorio -> incantesimi ai livelli 3, 5, 7, 9 (dalla scheda del Druido, ``srd_index``)
TERRITORIES = {
    "arctic": (("hold-person", "spike-growth"), ("slow", "sleet-storm"), ("freedom-of-movement", "ice-storm"),
               ("commune-with-nature", "cone-of-cold")),
    "coast": (("mirror-image", "misty-step"), ("water-walk", "water-breathing"), ("control-water", "freedom-of-movement"),
              ("conjure-elemental", "scrying")),
    "desert": (("blur", "silence"), ("create-food-and-water", "protection-from-energy"), ("blight", "hallucinatory-terrain"),
               ("wall-of-stone", "insect-plague")),
    "forest": (("spider-climb", "barkskin"), ("plant-growth", "call-lightning"), ("divination", "freedom-of-movement"),
               ("commune-with-nature", "tree-stride")),
    "grassland": (("invisibility", "pass-without-trace"), ("daylight", "haste"), ("divination", "freedom-of-movement"),
                  ("insect-plague", "dream")),
    "mountain": (("spike-growth", "spider-climb"), ("meld-into-stone", "lightning-bolt"), ("stoneskin", "stone-shape"),
                 ("wall-of-stone", "passwall")),
    "swamp": (("acid-arrow", "darkness"), ("water-walk", "stinking-cloud"), ("freedom-of-movement", "locate-creature"),
              ("insect-plague", "scrying")),
    "underdark": (("spider-climb", "web"), ("gaseous-form", "stinking-cloud"), ("greater-invisibility", "stone-shape"),
                  ("cloudkill", "insect-plague")),
}


def _choice(full, group):
    return next((c for c in full["pending_choices"] if c.get("group") == group), None)


async def _pick_territory(client, cid, territory):
    choice = _choice(await _full(client, cid), "territory")
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve",
                          json={"kind": "class_option", "options": [territory]})
    assert r.status_code == 200, r.text
    return r.json()


async def _always(client, cid) -> set[str]:
    return {s["srd_index"] for s in (await _spells(client, cid)).values() if s.get("always_prepared")}


# ---------------------------------------------------------------------------
# Trucchetto bonus e territorio
# ---------------------------------------------------------------------------

async def test_the_land_circle_offers_a_bonus_cantrip_beyond_the_limit(client):
    cid = await _druid(client, 2, "land")
    choice = _choice(await _full(client, cid), "bonus_cantrip")
    assert choice is not None and choice["count"] == 1 and choice["spell_pick"]["free"] is True
    assert choice["spell_pick"]["max_level"] == 0
    assert _choice(await _full(client, await _druid(client, 2, "moon")), "bonus_cantrip") is None
    assert _choice(await _full(client, await _druid(client, 1)), "bonus_cantrip") is None


async def test_the_territory_is_a_choice_of_eight_made_at_the_circle(client):
    cid = await _druid(client, 2, "land")
    choice = _choice(await _full(client, cid), "territory")
    assert choice["count"] == 1 and {o["key"] for o in choice["options"]} == set(TERRITORIES)
    assert all(o["name"]["it"] and o["name"]["en"] for o in choice["options"])
    assert _choice(await _full(client, await _druid(client, 2, "moon")), "territory") is None


@pytest.mark.parametrize("territory", sorted(TERRITORIES))
async def test_each_territory_grants_its_spells_at_levels_3_5_7_and_9(client, territory):
    cid = await _druid(client, 2, "land")
    await _pick_territory(client, cid, territory)
    assert await _always(client, cid) == set()  # il 2° livello non dà ancora incantesimi
    tiers = TERRITORIES[territory]
    for level, count in ((3, 1), (5, 2), (7, 3), (9, 4)):
        cls = (await _full(client, cid))["classes"][0]["id"]
        r = await client.patch(f"/characters/{cid}/classes/{cls}", json={"level": level})
        assert r.status_code == 200, r.text
        assert await _always(client, cid) == {name for tier in tiers[:count] for name in tier}, level


async def test_circle_spells_are_prepared_for_the_druid_and_outside_the_cap(client):
    cid = await _druid(client, 5, "land", wisdom=10)
    await _pick_territory(client, cid, "forest")
    spells = await _spells(client, cid)
    mine = [s for s in spells.values() if s["srd_index"] in {"spider-climb", "barkskin", "plant-growth", "call-lightning"}]
    assert len(mine) == 4 and all(s["is_prepared"] and s["always_prepared"] and s["class_id"] for s in mine)
    assert (await _full(client, cid))["spellcasting"]["prepared_count"] == 0


async def test_a_territory_row_names_the_chosen_territory_only(client):
    cid = await _druid(client, 3, "land")
    await _pick_territory(client, cid, "desert")
    keys = {a["feature_key"] for a in (await _full(client, cid))["abilities"]}
    assert "druid.territory_desert" in keys and not keys & {f"druid.territory_{t}" for t in TERRITORIES if t != "desert"}


# ---------------------------------------------------------------------------
# Andatura sul Territorio, Interdizione della Natura
# ---------------------------------------------------------------------------

async def test_lands_stride_is_a_confirmation_on_saves_from_level_6(client):
    low = await _druid(client, 5, "land")
    assert "druid.lands_stride" not in await _roll_keys(client, low, "save", ability="dexterity")
    cid = await _druid(client, 6, "land")
    options = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "save", "ability": "dexterity"})).json()
    stride = next(o for o in options if o["key"] == "druid.lands_stride")
    assert stride["mode"] == "advantage" and stride["phase"] == "before"
    moon = await _druid(client, 6, "moon")
    assert "druid.lands_stride" not in await _roll_keys(client, moon, "save", ability="dexterity")


async def _hp(client, cid, current, maximum):
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": maximum})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": current})


async def test_natures_ward_makes_the_druid_immune_to_poison_damage(client):
    cid = await _druid(client, 10, "land")
    await _hp(client, cid, 40, 40)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "poison"})
    assert r.json()["current_hit_points"] == 40
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "fire"})
    assert r.json()["current_hit_points"] == 30


async def test_natures_ward_blocks_the_poisoned_condition(client):
    cid = await _druid(client, 10, "land")
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"poisoned": True, "prone": True}})
    assert r.status_code == 200 and not r.json()["conditions"].get("poisoned") and r.json()["conditions"]["prone"] is True


async def test_before_level_10_and_in_other_circles_poison_still_works(client):
    for level, circle in ((9, "land"), (10, "moon")):
        cid = await _druid(client, level, circle)
        await _hp(client, cid, 40, 40)
        hit = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "poison"})
        assert hit.json()["current_hit_points"] == 30
        r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"poisoned": True}})
        assert r.json()["conditions"]["poisoned"] is True


# ---------------------------------------------------------------------------
# Rifugio della Natura
# ---------------------------------------------------------------------------

async def test_natures_sanctuary_shows_the_save_and_the_day_long_immunity(client):
    cid = await _druid(client, 14, "land", wisdom=16)  # competenza +5, Saggezza +3
    assert (await _ability(client, cid, "druid.natures_sanctuary"))["has_on_use"] is True
    r = await client.post(f"/characters/{cid}/features/druid.natures_sanctuary/use", json={})
    assert r.status_code == 200, r.text
    assert r.json()["targets"] == ["druid.natures_sanctuary"]
    effect = (await client.get(f"/characters/{cid}/target-effects/druid.natures_sanctuary")).json()["result"]
    assert (effect["condition"], effect["save_ability"], effect["save_dc"]) == ("custom:nature_ward", "wisdom", 8 + 5 + 3)
    assert effect["immune_on_success"] is True
    turn = (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]
    assert not turn.get("action_used") and not turn.get("reaction_used")  # passivo: nessuna azione


async def test_natures_sanctuary_needs_level_14_and_the_land(client):
    assert await _ability(client, await _druid(client, 13, "land"), "druid.natures_sanctuary") is None
    assert await _ability(client, await _druid(client, 14, "moon"), "druid.natures_sanctuary") is None


# ---------------------------------------------------------------------------
# La scelta del trucchetto bonus ammette solo trucchetti (e resta fuori dal limite)
# ---------------------------------------------------------------------------

async def _add(client, cid, name, level, **extra):
    return await client.post(f"/characters/{cid}/spells", json={"name": name, "level": level, **extra})


async def test_the_bonus_cantrip_pick_refuses_a_leveled_spell_and_stays_outside_the_limit(client):
    cid = await _druid(client, 3, "land")
    pick = _choice(await _full(client, cid), "bonus_cantrip")
    refused = await _add(client, cid, "Palla di fuoco", 1, pick_id=pick["id"])
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "spell_pick_level"
    assert (await _add(client, cid, "Bastone quercia", 0, pick_id=pick["id"])).status_code == 201
    assert _choice(await _full(client, cid), "bonus_cantrip") is None
    assert (await _full(client, cid))["spellcasting"]["limits"][0]["cantrips_count"] == 0  # non conta nei due trucchetti


async def test_the_acolyte_of_nature_cantrip_pick_is_also_a_cantrip_only_pick(client):
    from tests.integration.rules.test_2014_cleric import _cleric
    cid = await _cleric(client, 1, "nature")
    pick = _choice(await _full(client, cid), "nature_cantrip")
    assert pick["spell_pick"]["max_level"] == 0
    assert (await _add(client, cid, "Palla di fuoco", 1, pick_id=pick["id"])).status_code == 422


# ---------------------------------------------------------------------------
# Recupero Naturale: slot recuperati durante un riposo breve
# ---------------------------------------------------------------------------

async def _spend(client, cid, **used) -> None:
    """``used``: livello -> slot spesi (``l3=2``)."""
    for slot in (await _full(client, cid))["spell_slots"]:
        want = used.get(f"l{slot['level']}")
        if want is not None:
            r = await client.patch(f"/characters/{cid}/spell_slots/{slot['id']}", json={"used": want})
            assert r.status_code == 200, r.text


async def _used(client, cid) -> dict[int, int]:
    return {s["level"]: s["used"] for s in (await _full(client, cid))["spell_slots"]}


async def _short(client, cid, recovery=None):
    return await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "natural_recovery": recovery})


async def test_natural_recovery_is_a_single_use_pool_returning_on_a_long_rest(client):
    cid = await _druid(client, 2, "land")
    row = await _ability(client, cid, "druid.natural_recovery")
    assert (row["max_uses"], row["uses"], row["restoration_type"]) == (1, 1, "long_rest")
    assert row["is_pool"] is True and row["has_on_use"] is False
    assert await _ability(client, await _druid(client, 2, "moon"), "druid.natural_recovery") is None


async def _spend_all(client, cid) -> None:
    for slot in (await _full(client, cid))["spell_slots"]:
        r = await client.patch(f"/characters/{cid}/spell_slots/{slot['id']}", json={"used": slot["total"]})
        assert r.status_code == 200, r.text


@pytest.mark.parametrize("level,fits,over", [
    (2, {"1": 1}, {"1": 2}), (3, {"2": 1}, {"2": 1, "1": 1}), (4, {"1": 2}, {"2": 1, "1": 1}),
    (5, {"2": 1, "1": 1}, {"3": 1, "1": 1}), (9, {"5": 1}, {"5": 1, "1": 1}), (20, {"5": 2}, {"5": 2, "1": 1}),
])
async def test_natural_recovery_budget_is_half_the_druid_level_rounded_up(client, level, fits, over):
    cid = await _druid(client, level, "land")
    await _spend_all(client, cid)
    refused = await _short(client, cid, over)
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "natural_recovery_cap"
    assert (await _ability(client, cid, "druid.natural_recovery"))["uses"] == 1  # niente è stato speso
    assert (await _short(client, cid, fits)).status_code == 200
    spent = sum(int(lv) * n for lv, n in fits.items())
    assert sum(s["level"] * (s["total"] - s["used"]) for s in (await _full(client, cid))["spell_slots"]) == spent


async def test_natural_recovery_returns_exactly_the_chosen_slots_and_spends_the_use(client):
    cid = await _druid(client, 4, "land")
    await _spend(client, cid, l1=3, l2=2)
    r = await _short(client, cid, {"2": 1})
    assert r.status_code == 200, r.text
    assert await _used(client, cid) == {1: 3, 2: 1}
    assert (await _ability(client, cid, "druid.natural_recovery"))["uses"] == 0
    r = await _short(client, cid, {"1": 1})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    assert await _used(client, cid) == {1: 3, 2: 1}


async def test_natural_recovery_cannot_return_slots_that_were_not_spent(client):
    cid = await _druid(client, 6, "land")
    await _spend(client, cid, l1=1)
    r = await _short(client, cid, {"1": 2})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "natural_recovery_unspent"
    r = await _short(client, cid, {"3": 1})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "natural_recovery_unspent"
    assert (await _ability(client, cid, "druid.natural_recovery"))["uses"] == 1 and (await _used(client, cid))[1] == 1


async def test_natural_recovery_never_returns_slots_of_6th_level_or_higher(client):
    cid = await _druid(client, 20, "land")
    await _spend(client, cid, l6=1)
    r = await _short(client, cid, {"6": 1})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "natural_recovery_level"
    assert (await _used(client, cid))[6] == 1


async def test_natural_recovery_is_for_the_short_rest_only(client):
    cid = await _druid(client, 4, "land")
    await _spend(client, cid, l1=2)
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "natural_recovery": {"1": 1}})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "natural_recovery_short_only"
    assert (await _used(client, cid))[1] == 2 and (await _ability(client, cid, "druid.natural_recovery"))["uses"] == 1


async def test_natural_recovery_needs_the_land_circle(client):
    cid = await _druid(client, 4, "moon")
    await _spend(client, cid, l1=2)
    r = await _short(client, cid, {"1": 1})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "natural_recovery_unavailable"
    assert (await _used(client, cid))[1] == 2


async def test_a_refused_recovery_leaves_the_rest_undone(client):
    cid = await _druid(client, 4, "land")
    form = (await client.post(f"/characters/{cid}/companions", json={
        "kind": "wild_shape", "name": "Lupo", "statblock": {"type": "beast", "challenge_rating": 0.25, "speed": {}}, "max_hp": 9})).json()["id"]
    await client.post(f"/characters/{cid}/companions/{form}/activate", json={})
    r = await _short(client, cid, {"1": 1})  # nessuno slot speso
    assert r.status_code == 422
    assert (await _ability(client, cid, "druid.wild_shape"))["uses"] == 1  # il riposo non è avvenuto
    assert (await _full(client, cid))["active_form"] is not None


async def test_two_requests_at_once_recover_the_slots_only_once(client):
    import asyncio
    cid = await _druid(client, 4, "land")
    await _spend(client, cid, l1=4)
    first, second = await asyncio.gather(_short(client, cid, {"1": 2}), _short(client, cid, {"1": 2}))
    assert sorted([first.status_code, second.status_code]) == [200, 409]
    assert (await _used(client, cid))[1] == 2 and (await _ability(client, cid, "druid.natural_recovery"))["uses"] == 0


async def test_a_short_rest_without_recovery_leaves_the_slots_alone(client):
    cid = await _druid(client, 4, "land")
    await _spend(client, cid, l1=2)
    assert (await _short(client, cid)).status_code == 200
    assert (await _used(client, cid))[1] == 2 and (await _ability(client, cid, "druid.natural_recovery"))["uses"] == 1


def test_the_immunities_of_a_character_with_classes_come_from_states_and_features():
    from types import SimpleNamespace
    from core.rules.states import immune_conditions
    char = SimpleNamespace(active_states=[{"immune_conditions": ["frightened"]}], classes=[])
    assert immune_conditions(char) == {"frightened"}
