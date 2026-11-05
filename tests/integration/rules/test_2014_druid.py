"""Druido 2014 (Task 22): progressione, Forma Selvatica (usi, limiti per livello e circolo, slot di turno, ritorno),
Incantesimi Bestiali, Arcidruido."""
from __future__ import annotations

import pytest

from core.rules.catalog import features_for
from core.rules.proficiencies import class_proficiencies
from core.rules.spellcasting import known_limits
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _spells

CIRCLES = {"land": "Circolo della Terra", "moon": "Circolo della Luna"}
WILD = "druid.wild_shape"


async def _druid(client, level=5, circle=None, **scores) -> int:
    body = {"name": "Druido", "initial_class": {"class_name": "druid", "level": level, "subclass": CIRCLES.get(circle)}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


def _beast(cr=0.25, swim=0, fly=0, kind="beast") -> dict:
    return {"size": "Medium", "type": kind, "challenge_rating": cr,
            "speed": {"walk_ft": 30, "swim_ft": swim, "fly_ft": fly}, "actions": []}


async def _form(client, cid, statblock=None, name="Bestia", hp=10) -> int:
    r = await client.post(f"/characters/{cid}/companions", json={
        "kind": "wild_shape", "name": name, "statblock": statblock or _beast(), "max_hp": hp, "armor_class": 12})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _activate(client, cid, comp, **body):
    return await client.post(f"/characters/{cid}/companions/{comp}/activate", json=body)


async def _turn(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]


# ---------------------------------------------------------------------------
# Progressione e catalogo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,cantrips", [(1, 2), (3, 2), (4, 3), (9, 3), (10, 4), (20, 4)])
def test_cantrips_follow_the_class_table(level, cantrips):
    assert known_limits("2014", "druid", level).cantrips == cantrips


async def test_slots_and_prepared_cap_follow_wisdom_plus_level(client):
    cid = await _druid(client, 5, wisdom=16)
    full = await _full(client, cid)
    assert {s["level"]: s["total"] for s in full["spell_slots"]} == {1: 4, 2: 3, 3: 2}
    assert full["spellcasting"]["prepared_cap"] == 3 + 5  # Saggezza 16 (+3) + livello


async def test_hit_points_use_the_d8_and_follow_constitution(client):
    cid = await _druid(client, 3)
    full = await _full(client, cid)
    assert full["classes"][0]["hit_die"] == 8
    assert full["hit_points"] == 8 + 5 + 5


def test_class_proficiencies_first_class_and_multiclass():
    first = class_proficiencies("2014", "druid", False)
    assert set(first.armor) == {"light", "medium", "shields"} and "scimitar" in first.weapons and len(first.weapons) == 10
    assert first.tools == ("herbalism_kit",) and set(first.saves) == {"intelligence", "wisdom"} and first.skills_count == 2
    assert set(first.skills_from) == {"arcana", "animal_handling", "insight", "medicine", "nature", "perception", "religion", "survival"}
    multi = class_proficiencies("2014", "druid", True)
    assert set(multi.armor) == {"light", "medium", "shields"} and not multi.weapons and not multi.tools and not multi.saves


async def test_druidic_is_among_the_languages(client):
    cid = await _druid(client, 1)
    assert "Druidico" in (await _full(client, cid))["languages"]


@pytest.mark.parametrize("level", [4, 8, 12, 16, 19])
async def test_asi_choice_is_pending_at_each_asi_level(client, level):
    cid = await _druid(client, level)
    levels = sorted(c["level"] for c in (await _full(client, cid))["pending_choices"] if c["kind"] == "asi")
    assert levels == [lv for lv in (4, 8, 12, 16, 19) if lv <= level]


async def test_rules_only_rows_do_not_clutter_the_sheet(client):
    cid = await _druid(client, 20, "land")
    keys = await _keys_of(client, cid)
    assert not keys & {f"druid.{k}" for k in ("hit_points", "proficiencies", "equipment", "druidic", "spellcasting",
                                              "druid_circle", "ability_score_improvement", "multiclassing")}


def test_every_catalog_row_belongs_to_the_2014_druid():
    rows = features_for("2014", "druid")
    assert rows and all(f.edition == "2014" and f.class_key == "druid" for f in rows)


# ---------------------------------------------------------------------------
# Forma Selvatica: usi, ricarica, Arcidruido
# ---------------------------------------------------------------------------

async def test_wild_shape_appears_at_level_2_with_two_uses_and_no_use_button(client):
    assert await _ability(client, await _druid(client, 1), WILD) is None
    row = await _ability(client, await _druid(client, 2), WILD)
    assert (row["max_uses"], row["uses"], row["restoration_type"]) == (2, 2, "short_rest")
    assert row["is_pool"] is True and row["has_on_use"] is False  # si attiva dalla forma, non da «Usa»


async def test_a_short_rest_returns_the_wild_shape_uses(client):
    cid = await _druid(client, 4)
    form = await _form(client, cid)
    assert (await _activate(client, cid, form)).status_code == 200
    assert (await _ability(client, cid, WILD))["uses"] == 1
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, WILD))["uses"] == 2


async def test_wild_shape_is_unlimited_at_level_20_and_never_spends(client):
    cid = await _druid(client, 20)
    row = await _ability(client, cid, WILD)
    assert row["max_uses"] is None and row["restoration_type"] == "short_rest"
    for _ in range(3):
        form = await _form(client, cid, _beast(1))
        assert (await _activate(client, cid, form)).status_code == 200
        await client.post(f"/characters/{cid}/turn/use", json={"slot": "action", "used": False})
    assert (await _ability(client, cid, WILD))["max_uses"] is None


async def test_the_catalog_lists_the_improved_forms_at_4_and_8(client):
    low = await _keys_of(client, await _druid(client, 3))
    mid = await _keys_of(client, await _druid(client, 4))
    high = await _keys_of(client, await _druid(client, 8))
    assert "druid.beast_shapes" in low and "druid.improved_wild_shape" not in low
    assert "druid.improved_wild_shape" in mid and "druid.improved_wild_shape_8" not in mid
    assert {"druid.improved_wild_shape", "druid.improved_wild_shape_8"} <= high


# ---------------------------------------------------------------------------
# Forme Bestiali: limiti per livello (Terra) e per Circolo della Luna
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,cr,swim,fly,reasons", [
    (2, 0.25, 0, 0, []), (2, 0.5, 0, 0, ["cr"]), (2, 0.25, 30, 0, ["swim"]), (3, 0.25, 0, 60, ["fly"]),
    (4, 0.5, 30, 0, []), (4, 1, 0, 0, ["cr"]), (4, 0.5, 0, 60, ["fly"]), (7, 0.5, 0, 60, ["fly"]),
    (8, 1, 0, 60, []), (8, 2, 0, 0, ["cr"]), (12, 1, 40, 40, []),
])
async def test_beast_shapes_are_limited_by_druid_level(client, level, cr, swim, fly, reasons):
    cid = await _druid(client, level, "land")
    form = await _form(client, cid, _beast(cr, swim, fly))
    r = await _activate(client, cid, form)
    if reasons:
        assert r.status_code == 409 and r.json()["detail"]["code"] == "form_not_allowed"
        assert r.json()["detail"]["reasons"] == reasons
        assert (await _ability(client, cid, WILD))["uses"] == 2  # rifiutata: nessun uso speso
        assert (await _activate(client, cid, form, force=True)).status_code == 200  # il giocatore può confermare
    else:
        assert r.status_code == 200, r.text
        assert (await _ability(client, cid, WILD))["uses"] == 1


async def test_only_beasts_and_only_with_a_druid_level(client):
    cid = await _druid(client, 8, "land")
    r = await _activate(client, cid, await _form(client, cid, _beast(0.25, kind="monstrosity")))
    assert r.status_code == 409 and r.json()["detail"]["reasons"] == ["not_beast"]
    low = await _druid(client, 1)
    r = await _activate(client, low, await _form(client, low))
    assert r.status_code == 409 and r.json()["detail"]["reasons"] == ["no_wild_shape"]


async def test_the_limits_use_the_druid_levels_not_the_total_level(client):
    cid = await _druid(client, 2, "land")
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 8, "hit_die": 10})
    assert r.status_code == 201, r.text
    r = await _activate(client, cid, await _form(client, cid, _beast(1)))
    assert r.status_code == 409 and r.json()["detail"]["reasons"] == ["cr"]


async def test_italian_class_names_get_the_same_limits(client):
    r = await client.post("/characters", json={"name": "Druido", "initial_class": {"class_name": "Druido", "level": 4}})
    cid = r.json()["id"]
    assert (await _activate(client, cid, await _form(client, cid, _beast(0.5, 30)))).status_code == 200


@pytest.mark.parametrize("level,max_cr", [(2, 1), (5, 1), (6, 2), (8, 2), (9, 3), (12, 4), (15, 5), (18, 6), (20, 6)])
async def test_circle_of_the_moon_allows_challenge_rating_of_level_over_three(client, level, max_cr):
    cid = await _druid(client, level, "moon")
    ok = await _activate(client, cid, await _form(client, cid, _beast(max_cr)))
    assert ok.status_code == 200, ok.text
    over = await _activate(client, cid, await _form(client, cid, _beast(max_cr + 1)))
    assert over.status_code == 409 and over.json()["detail"]["reasons"] == ["cr"]


async def test_the_moon_keeps_the_swim_and_fly_limits_of_the_level(client):
    cid = await _druid(client, 3, "moon")
    r = await _activate(client, cid, await _form(client, cid, _beast(1, swim=30)))
    assert r.json()["detail"]["reasons"] == ["swim"]
    r = await _activate(client, cid, await _form(client, cid, _beast(1, fly=60)))
    assert r.json()["detail"]["reasons"] == ["fly"]


async def test_wild_shape_takes_an_action_for_the_land_and_a_bonus_action_for_the_moon(client):
    land = await _druid(client, 4, "land")
    assert (await _activate(client, land, await _form(client, land))).status_code == 200
    assert (await _turn(client, land)).get("action_used") is True and not (await _turn(client, land)).get("bonus_used")
    moon = await _druid(client, 4, "moon")
    assert (await _activate(client, moon, await _form(client, moon))).status_code == 200
    assert (await _turn(client, moon)).get("bonus_used") is True and not (await _turn(client, moon)).get("action_used")


async def test_a_second_activation_in_the_same_turn_is_refused_before_spending_a_use(client):
    cid = await _druid(client, 4, "land")
    assert (await _activate(client, cid, await _form(client, cid))).status_code == 200
    r = await _activate(client, cid, await _form(client, cid, name="Altra"))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "turn_slot_used"
    assert (await _ability(client, cid, WILD))["uses"] == 1


# ---------------------------------------------------------------------------
# Durata e ritorno alla forma normale
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,hours", [(2, 1), (3, 1), (4, 2), (11, 5), (20, 10)])
async def test_the_form_lasts_half_the_druid_level_in_hours(client, level, hours):
    cid = await _druid(client, level, "land")
    assert (await _activate(client, cid, await _form(client, cid, _beast(0.25)))).status_code == 200
    state = next(s for s in (await _full(client, cid))["active_states"] if s["key"] == "wild_shape")
    assert state["rounds_left"] == hours * 600


async def test_ending_the_form_early_costs_the_bonus_action_but_never_blocks(client):
    cid = await _druid(client, 4, "land")
    form = await _form(client, cid)
    await _activate(client, cid, form)
    r = await client.post(f"/characters/{cid}/companions/{form}/deactivate")
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert (await _turn(client, cid)).get("bonus_used") is True
    await _activate(client, cid, form, force=True)
    r = await client.post(f"/characters/{cid}/companions/{form}/deactivate")  # azione bonus già spesa: torna lo stesso
    assert r.status_code == 200 and r.json()["is_active"] is False


async def test_a_short_rest_ends_the_form(client):
    cid = await _druid(client, 6, "land")
    await _activate(client, cid, await _form(client, cid, _beast(0.5)))
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert (await _full(client, cid))["active_form"] is None


# ---------------------------------------------------------------------------
# Incantesimi Bestiali (18°) e Arcidruido (20°)
# ---------------------------------------------------------------------------

async def _spell(client, cid, name="Parlare con le piante", components="V, S", level=0) -> int:
    r = await client.post(f"/characters/{cid}/spells", json={"name": name, "level": level, "components": components,
                                                              "is_prepared": True})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


async def _warnings(client, cid, spell) -> list[str]:
    return (await client.get(f"/characters/{cid}/spells/{spell}/cast-check")).json()


async def test_casting_in_beast_form_needs_confirmation_below_level_18(client):
    cid = await _druid(client, 17, "land")
    spell = await _spell(client, cid)
    await _activate(client, cid, await _form(client, cid, _beast(1, 30, 60)))
    assert "wild_shape" in await _warnings(client, cid, spell)


async def test_beast_spells_at_18_lift_the_block_but_not_the_material_components(client):
    cid = await _druid(client, 18, "land")
    plain = await _spell(client, cid, components="V, S")
    material = await _spell(client, cid, "Stoneskin", "V, S, M", level=4)
    await _activate(client, cid, await _form(client, cid, _beast(1, 30, 60)))
    assert await _warnings(client, cid, plain) == []
    assert await _warnings(client, cid, material) == ["form_materials"]
    out = await _full(client, cid)
    assert out["active_form"] is not None
    assert (await client.get(f"/characters/{cid}/spells/{material}/cast-check")).status_code == 200


async def test_the_archdruid_only_has_to_confirm_materials_with_a_cost_in_beast_form(client):
    cid = await _druid(client, 20, "land")
    material = await _spell(client, cid, "Stoneskin", "V, S, M", level=4)
    await _activate(client, cid, await _form(client, cid, _beast(1, 30, 60)))
    assert await _warnings(client, cid, material) == ["form_materials_cost"]


async def test_outside_beast_form_no_component_warning_ever(client):
    cid = await _druid(client, 20, "land")
    material = await _spell(client, cid, "Stoneskin", "V, S, M", level=4)
    assert await _warnings(client, cid, material) == []


async def test_text_only_rows_are_passive(client):
    cid = await _druid(client, 20, "land")
    for key in ("druid.timeless_body", "druid.archdruid", "druid.beast_spells"):
        row = await _ability(client, cid, key)
        assert row is not None and row["has_on_use"] is False


async def test_spells_listing_still_works_for_a_druid(client):
    cid = await _druid(client, 3, "land")
    assert isinstance(await _spells(client, cid), dict)
