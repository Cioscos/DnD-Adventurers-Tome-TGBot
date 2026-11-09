"""Druido 2024 (Task 34, parte A): tabelle, Druidico, Ordine Primordiale, Forma Selvatica (usi, forma, ritorno), Compagno
Selvatico, Rigenerazione Selvatica, Furia Elementale, Incantesimi Bestiali, Arcidruido e multiclasse. Valori dalla scheda
``docs/superpowers/rules/2024/classes/druid.md``."""
from __future__ import annotations

import pytest

from core.rules.catalog import features_for
from core.rules.proficiencies import class_proficiencies
from tests.integration.rules.test_2014_barbarian import _turn, _weapon
from tests.integration.rules.test_2014_bard import _ability, _choice, _full, _keys_of, _resolve, _roll_keys, _states, _use
from tests.integration.rules.test_2014_cleric_domains import _deferred
from tests.integration.rules.test_2014_druid import _activate, _beast, _form

WILD = "druid.wild_shape"
COMPANION, RESURGENCE, RESURGENCE_SLOT = "druid.wild_companion", "druid.wild_resurgence", "druid.wild_resurgence_slot"
EVERGREEN, MAGICIAN = "druid.evergreen_wild_shape", "druid.nature_magician"
PREPARED = (4, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16, 16, 17, 17, 18, 18, 19, 20, 21, 22)
CANTRIPS = (2, 2, 2, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4)
SLOTS = {1: (2,), 3: (4, 2), 5: (4, 3, 2), 9: (4, 3, 3, 3, 1), 17: (4, 3, 3, 3, 2, 1, 1, 1, 1), 20: (4, 3, 3, 3, 3, 2, 2, 1, 1)}


async def _druid24(client, level=5, order=None, **scores) -> int:
    body = {"name": "Druido", "initial_class": {"class_name": "druid", "level": level, "subclass": None}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    if order:
        r = await _resolve(client, cid, "primal_order", [order])
        assert r.status_code == 200, r.text
    return cid


async def _new_turn(client, cid) -> None:
    for slot in ("action", "bonus"):
        await client.post(f"/characters/{cid}/turn/use", json={"slot": slot, "used": False})


async def _next_turn(client, cid) -> None:
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200


async def _shape(client, cid, cr=0.25, **kw) -> int:
    form = await _form(client, cid, _beast(cr, **kw))
    r = await _activate(client, cid, form)
    assert r.status_code == 200, r.text
    await _new_turn(client, cid)
    return form


# ---------------------------------------------------------------------------
# Tabelle e catalogo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", range(1, 21))
async def test_cantrips_and_prepared_spells_follow_the_2024_table(client, level):
    cid = await _druid24(client, level)
    limits = (await _full(client, cid))["spellcasting"]["limits"][0]
    assert (limits["cantrips_limit"], limits["prepared_limit"]) == (CANTRIPS[level - 1], PREPARED[level - 1])


@pytest.mark.parametrize("level", sorted(SLOTS))
async def test_spell_slots_follow_the_full_caster_table(client, level):
    cid = await _druid24(client, level)
    slots = tuple(s["total"] for s in sorted((await _full(client, cid))["spell_slots"], key=lambda s: s["level"]))
    assert slots == SLOTS[level]


async def test_hit_points_use_the_d8_and_follow_constitution(client):
    cid = await _druid24(client, 3)
    full = await _full(client, cid)
    assert full["classes"][0]["hit_die"] == 8 and full["hit_points"] == 8 + 5 + 5


def test_class_and_multiclass_proficiencies_from_the_class_table():
    first = class_proficiencies("2024", "druid", False)
    assert set(first.armor) == {"light", "shields"} and first.weapons == ("simple",) and first.tools == ("herbalism_kit",)
    assert set(first.saves) == {"intelligence", "wisdom"} and first.skills_count == 2
    multi = class_proficiencies("2024", "druid", True)
    assert set(multi.armor) == {"light", "shields"} and not multi.weapons and not multi.tools
    assert not multi.saves and not multi.skills_count


@pytest.mark.parametrize("level,asi", [(4, [4]), (16, [4, 8, 12, 16]), (19, [4, 8, 12, 16])])
async def test_asi_choice_is_pending_at_each_asi_level_and_the_19th_is_an_epic_boon(client, level, asi):
    cid = await _druid24(client, level)
    pending = (await _full(client, cid))["pending_choices"]
    assert sorted(c["level"] for c in pending if c["kind"] == "asi") == asi
    assert [c["level"] for c in pending if c["kind"] == "epic_boon"] == ([19] if level >= 19 else [])


async def test_every_mapping_title_has_its_row_and_rules_only_rows_stay_off_the_sheet(client):
    titles = {f.source_title for f in features_for("2024", "druid")}
    for title in ("Druidico / Druidic (Druido 1, pag. 80)", "Forma Selvatica / Wild Shape (Druido 2, pag. 80)",
                  "Compagno Selvatico / Wild Companion (Druido 2, pag. 81)", "Arcidruido / Archdruid (Druido 20, pag. 82)",
                  "Multiclasse: Druido / Multiclassing: Druid (Regole multiclasse, pag. 44)"):
        assert title in titles
    keys = await _keys_of(client, await _druid24(client, 20))
    assert not keys & {f"druid.{k}" for k in ("core_traits", "spellcasting", "druid_subclass", "ability_score_improvement",
                                               "epic_boon", "multiclassing", "wild_shape_rules")}
    assert {WILD, COMPANION, RESURGENCE, RESURGENCE_SLOT, MAGICIAN} <= keys


# ---------------------------------------------------------------------------
# Druidico e Ordine Primordiale
# ---------------------------------------------------------------------------

async def test_druidic_adds_the_language_and_speak_with_animals_always_prepared(client):
    cid = await _druid24(client, 1)
    full = await _full(client, cid)
    assert any(lang in ("Druidico", "Druidic") for lang in full["languages"])
    spell = next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"] == "speak-with-animals")
    assert spell["always_prepared"] is True and spell["is_prepared"] is True


async def test_the_primal_order_is_a_single_choice_at_level_1(client):
    cid = await _druid24(client, 1)
    choice = _choice(await _full(client, cid), "primal_order")
    assert choice is not None and choice["count"] == 1
    assert (await _resolve(client, cid, "primal_order", ["warden", "magician"])).status_code == 422


async def test_warden_adds_martial_weapons_and_medium_armor(client):
    cid = await _druid24(client, 1, "warden")
    full = await _full(client, cid)
    assert "Armi da guerra" in full["general_proficiencies"]["weapons"] and "Armature medie" in full["general_proficiencies"]["armor"]
    assert _choice(full, "magician_cantrip") is None


async def test_magician_gives_a_free_cantrip_and_wisdom_to_arcana_and_nature(client):
    cid = await _druid24(client, 1, "magician", wisdom=16, intelligence=10)
    full = await _full(client, cid)
    assert _choice(full, "magician_cantrip")["spell_pick"] == {"free": True, "max_level": 0, "list": "druid"}
    assert "Armi da guerra" not in full["general_proficiencies"]["weapons"]
    arcana = (await client.post(f"/characters/{cid}/skills/arcana/roll", json={"die": 10})).json()
    nature = (await client.post(f"/characters/{cid}/skills/nature/roll", json={"die": 10})).json()
    history = (await client.post(f"/characters/{cid}/skills/history/roll", json={"die": 10})).json()
    assert (arcana["bonus"], nature["bonus"], history["bonus"]) == (3, 3, 0)


async def test_magician_bonus_is_at_least_plus_one(client):
    cid = await _druid24(client, 1, "magician", wisdom=8)
    assert (await client.post(f"/characters/{cid}/skills/nature/roll", json={"die": 10})).json()["bonus"] == 1


# ---------------------------------------------------------------------------
# Forma Selvatica
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,uses", [(1, None), (2, 2), (5, 2), (6, 3), (16, 3), (17, 4), (20, 4)])
async def test_wild_shape_uses_follow_the_level_and_are_never_unlimited(client, level, uses):
    row = await _ability(client, await _druid24(client, level), WILD)
    if uses is None:
        assert row is None
        return
    assert (row["max_uses"], row["uses"], row["action_type"]) == (uses, uses, "bonus_action")
    assert row["is_pool"] is True and row["has_on_use"] is False


async def test_a_short_rest_returns_one_use_and_a_long_rest_all_of_them(client):
    cid = await _druid24(client, 6)
    await _shape(client, cid)
    await _shape(client, cid)
    await _shape(client, cid)
    assert (await _ability(client, cid, WILD))["uses"] == 0
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})).status_code == 200
    assert (await _ability(client, cid, WILD))["uses"] == 1
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})).status_code == 200
    assert (await _ability(client, cid, WILD))["uses"] == 3


async def test_wild_shape_is_a_bonus_action_gives_temporary_hp_equal_to_the_level_and_keeps_the_real_hp(client):
    cid = await _druid24(client, 5)
    before = (await _full(client, cid))["current_hit_points"]
    form = await _form(client, cid, _beast(0.25, swim=30))  # il 2024 non limita il nuoto
    assert (await _activate(client, cid, form)).status_code == 200
    turn = await _turn(client, cid)
    assert turn.get("bonus_used") is True and not turn.get("action_used")
    full = await _full(client, cid)
    assert full["temp_hp"] == 5 and full["current_hit_points"] == before and full["active_form"] is not None
    assert (await _ability(client, cid, WILD))["uses"] == 1


@pytest.mark.parametrize("level,known", [(2, 4), (3, 4), (4, 6), (7, 6), (8, 8), (20, 8)])
async def test_known_forms_follow_the_level(client, level, known):
    cid = await _druid24(client, level)
    for _ in range(known):
        await _form(client, cid)
    r = await client.post(f"/characters/{cid}/companions", json={
        "kind": "wild_shape", "name": "Una in più", "statblock": _beast(), "max_hp": 5, "armor_class": 10})
    assert r.status_code == 422 and r.json()["detail"] == "known_forms_limit"


@pytest.mark.parametrize("level,cr,fly,reasons", [
    (2, 0.25, 0, []), (2, 0.5, 0, ["cr"]), (4, 0.5, 0, []), (4, 1, 0, ["cr"]), (7, 1, 30, ["cr", "fly"]), (8, 1, 30, []), (8, 2, 0, ["cr"])])
async def test_forms_are_limited_by_challenge_rating_and_fly_not_by_swim(client, level, cr, fly, reasons):
    cid = await _druid24(client, level)
    form = await _form(client, cid, _beast(cr, swim=30, fly=fly))
    r = await _activate(client, cid, form)
    if reasons:
        assert r.status_code == 409 and r.json()["detail"]["reasons"] == reasons
    else:
        assert r.status_code == 200, r.text


async def test_the_form_lasts_half_the_druid_level_in_hours(client):
    cid = await _druid24(client, 11)
    await _shape(client, cid, 0.5)
    state = next(s for s in await _states(client, cid) if s["key"] == "wild_shape")
    assert state["rounds_left"] == 5 * 600


async def test_returning_to_normal_form_costs_the_bonus_action_and_is_refused_when_it_is_spent(client):
    cid = await _druid24(client, 5)
    form = await _shape(client, cid)
    r = await client.post(f"/characters/{cid}/companions/{form}/deactivate")
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert (await _turn(client, cid)).get("bonus_used") is True
    await _new_turn(client, cid)
    await _activate(client, cid, form)  # l'attivazione ha speso l'azione bonus: tornare normali non si può nello stesso turno
    r = await client.delete(f"/characters/{cid}/active-states/wild_shape")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "turn_slot_used"
    assert (await _full(client, cid))["active_form"] is not None
    await _new_turn(client, cid)
    assert (await client.delete(f"/characters/{cid}/active-states/wild_shape")).status_code == 200
    assert (await _full(client, cid))["active_form"] is None


async def test_the_higher_modifier_between_druid_and_beast_applies_to_checks(client):
    cid = await _druid24(client, 5, strength=8, dexterity=10)
    form = await _form(client, cid, {**_beast(), "abilities": {"str": 16, "dex": 10, "con": 10}})
    athletics = lambda: client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 10})  # noqa: E731
    assert (await athletics()).json()["bonus"] == -1
    assert (await _activate(client, cid, form)).status_code == 200
    assert (await athletics()).json()["bonus"] == 3


async def test_a_long_rest_does_not_end_a_form_lasting_hours_but_a_short_rest_ends_a_one_hour_one(client):
    cid = await _druid24(client, 4)
    await _shape(client, cid, 0.5)  # 2 ore
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert (await _full(client, cid))["active_form"] is not None
    short = await _druid24(client, 2)
    await _shape(client, short)  # 1 ora
    await client.post(f"/characters/{short}/rest", json={"rest_type": "short"})
    assert (await _full(client, short))["active_form"] is None


# ---------------------------------------------------------------------------
# Incantesimi Bestiali
# ---------------------------------------------------------------------------

async def _spell(client, cid, name="Parlare con le piante", components="V, S", level=0) -> int:
    r = await client.post(f"/characters/{cid}/spells", json={"name": name, "level": level, "components": components,
                                                              "is_prepared": True})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


async def _warnings(client, cid, spell) -> list[str]:
    return (await client.get(f"/characters/{cid}/spells/{spell}/cast-check")).json()


async def test_casting_in_beast_form_needs_confirmation_below_level_18(client):
    cid = await _druid24(client, 17)
    spell = await _spell(client, cid)
    await _shape(client, cid, 1, fly=30)
    assert "wild_shape" in await _warnings(client, cid, spell)


async def test_beast_spells_at_18_allow_casting_but_ask_about_materials_with_a_cost(client):
    cid = await _druid24(client, 18)
    plain = await _spell(client, cid)
    material = await _spell(client, cid, "Stoneskin", "V, S, M", level=4)
    await _shape(client, cid, 1, fly=30)
    assert await _warnings(client, cid, plain) == []
    assert await _warnings(client, cid, material) == ["form_materials_cost"]


# ---------------------------------------------------------------------------
# Compagno Selvatico
# ---------------------------------------------------------------------------

async def _companions(client, cid) -> list[dict]:
    return (await client.get(f"/characters/{cid}/companions")).json()


async def test_wild_companion_casts_find_familiar_paying_a_wild_shape_use(client):
    cid = await _druid24(client, 2)
    r = await _use(client, cid, COMPANION, params={"pay": "wild_shape"})
    assert r.status_code == 200, r.text
    familiar = next(c for c in await _companions(client, cid) if c["kind"] == "familiar")
    assert familiar["statblock"]["type"] == "fey"
    assert (await _ability(client, cid, WILD))["uses"] == 1
    assert all(s["used"] == 0 for s in (await _full(client, cid))["spell_slots"])
    assert (await _turn(client, cid)).get("action_used") is True  # azione Magia


async def test_wild_companion_casts_find_familiar_paying_a_slot(client):
    cid = await _druid24(client, 2)
    r = await _use(client, cid, COMPANION, params={"pay": "slot", "slot_level": "1"})
    assert r.status_code == 200, r.text
    slots = {s["level"]: s["used"] for s in (await _full(client, cid))["spell_slots"]}
    assert slots[1] == 1 and (await _ability(client, cid, WILD))["uses"] == 2


async def test_wild_companion_is_refused_without_the_chosen_payment_and_keeps_the_action(client):
    cid = await _druid24(client, 2)
    assert (await _use(client, cid, COMPANION, params={"pay": "gold"})).status_code == 422
    assert (await _use(client, cid, COMPANION, params={"pay": "slot"})).status_code == 422  # manca il livello dello slot
    await _shape(client, cid)
    await _shape(client, cid)
    r = await _use(client, cid, COMPANION, params={"pay": "wild_shape"})
    assert r.status_code == 409 and not any(c["kind"] == "familiar" for c in await _companions(client, cid))
    assert not (await _turn(client, cid)).get("action_used")


async def test_the_wild_companion_familiar_vanishes_at_the_next_long_rest(client):
    cid = await _druid24(client, 2)
    await _form(client, cid)
    assert (await _use(client, cid, COMPANION, params={"pay": "wild_shape"})).status_code == 200
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert any(c["kind"] == "familiar" for c in await _companions(client, cid))
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    kinds = [c["kind"] for c in await _companions(client, cid)]
    assert "familiar" not in kinds and "wild_shape" in kinds  # le forme conosciute restano


# ---------------------------------------------------------------------------
# Rigenerazione Selvatica
# ---------------------------------------------------------------------------

async def test_wild_resurgence_gives_a_use_for_a_slot_only_with_no_uses_left_and_once_per_turn(client):
    cid = await _druid24(client, 5)
    r = await _use(client, cid, RESURGENCE, params={"slot_level": "1"})
    assert r.status_code == 409  # restano usi
    await _shape(client, cid)
    await _shape(client, cid)
    assert (await _ability(client, cid, WILD))["uses"] == 0
    r = await _use(client, cid, RESURGENCE, params={"slot_level": "2"})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, WILD))["uses"] == 1
    assert {s["level"]: s["used"] for s in (await _full(client, cid))["spell_slots"]}[2] == 1
    assert not (await _turn(client, cid)).get("action_used") and not (await _turn(client, cid)).get("bonus_used")  # senza azione
    await _shape(client, cid)
    again = await _use(client, cid, RESURGENCE, params={"slot_level": "1"})
    assert again.status_code == 409  # una volta per turno


async def test_wild_resurgence_turns_a_use_into_a_first_level_slot_once_per_long_rest(client):
    cid = await _druid24(client, 5)
    await _shape(client, cid)
    await _shape(client, cid)
    assert (await _use(client, cid, RESURGENCE, params={"slot_level": "1"})).status_code == 200
    r = await _use(client, cid, RESURGENCE_SLOT)
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, WILD))["uses"] == 0
    first = next(s for s in (await _full(client, cid))["spell_slots"] if s["level"] == 1)
    assert (first["total"], first["used"]) == (5, 1)  # lo slot speso dalla Rigenerazione resta speso, ne arriva uno nuovo
    await _new_turn(client, cid)
    assert (await _use(client, cid, RESURGENCE_SLOT)).status_code == 409  # serve un riposo lungo
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    await _next_turn(client, cid)
    await _shape(client, cid)
    await _shape(client, cid)
    assert (await _use(client, cid, RESURGENCE, params={"slot_level": "1"})).status_code == 200
    assert (await _use(client, cid, RESURGENCE_SLOT)).status_code == 200  # dopo il riposo lungo il cambio torna possibile


# ---------------------------------------------------------------------------
# Furia Elementale
# ---------------------------------------------------------------------------

async def test_elemental_fury_is_a_choice_at_level_7(client):
    assert _choice(await _full(client, await _druid24(client, 6)), "elemental_fury") is None
    cid = await _druid24(client, 7)
    assert _choice(await _full(client, cid), "elemental_fury")["count"] == 1
    assert {"druid.elemental_fury_potent", "druid.elemental_fury_strike"}.isdisjoint(await _keys_of(client, cid))


async def _cantrip(client, cid, name="Fiamma") -> int:
    row = (await _full(client, cid))["classes"][0]["id"]
    r = await client.post(f"/characters/{cid}/spells", json={"name": name, "level": 0, "damage_dice": "1d8", "damage_type": "fire",
                                                             "class_id": row, "range_area": "18 m"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_potent_spellcasting_adds_wisdom_to_a_druid_cantrip_only(client):
    cid = await _druid24(client, 7, wisdom=16)
    await _resolve(client, cid, "elemental_fury", ["potent_spellcasting"])
    cantrip = await _cantrip(client, cid)
    r = await client.post(f"/characters/{cid}/spells/{cantrip}/roll_damage", json={"main_rolls": [4, 3]})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 4 + 3 + 3
    other = await _druid24(client, 7, wisdom=16)
    await _resolve(client, other, "elemental_fury", ["primal_strike"])
    assert (await client.post(f"/characters/{other}/spells/{await _cantrip(client, other)}/roll_damage",
                              json={"main_rolls": [4, 3]})).json()["total"] == 7


async def test_potent_spellcasting_adds_90_meters_to_cantrip_range_from_level_15(client):
    async def shown(level: int, chosen: str = "potent_spellcasting") -> list[str]:
        cid = await _druid24(client, level, wisdom=16)
        await _resolve(client, cid, "elemental_fury", [chosen])
        await _cantrip(client, cid)
        await client.post(f"/characters/{cid}/spells", json={"name": "Tocco", "level": 0, "range_area": "Contatto"})
        return [s["range_area"] for s in (await client.get(f"/characters/{cid}/spells")).json() if s["name"] in ("Fiamma", "Tocco")]
    assert sorted(await shown(14)) == ["18 m", "Contatto"]
    assert sorted(await shown(15)) == ["108 m", "Contatto"]
    assert sorted(await shown(15, "primal_strike")) == ["18 m", "Contatto"]


async def test_primal_strike_offers_four_energies_once_per_turn_with_a_weapon(client):
    cid = await _druid24(client, 7, strength=14)
    await _resolve(client, cid, "elemental_fury", ["primal_strike"])
    club = await _weapon(client, cid, "Randello", damage_dice="1d6")
    keys = await _roll_keys(client, cid, "attack", item_id=club)
    energies = {f"druid.primal_strike_{t}" for t in ("cold", "fire", "lightning", "thunder")}
    assert energies <= set(keys)
    assert (await _deferred(client, cid, club, 15, "druid.primal_strike_fire"))["option_result"] is not None
    assert energies.isdisjoint(await _roll_keys(client, cid, "attack", item_id=club))


async def test_primal_strike_is_2d8_from_level_15_and_not_offered_with_the_other_choice(client):
    from core.rules.catalog.y2024.druid import _strike_dice
    from core.rules.types import RuleContext
    assert _strike_dice(RuleContext(char=None, edition="2024", class_level=14), {}) == "1d8"
    assert _strike_dice(RuleContext(char=None, edition="2024", class_level=15), {}) == "2d8"
    cid = await _druid24(client, 7, strength=14)
    await _resolve(client, cid, "elemental_fury", ["potent_spellcasting"])
    club = await _weapon(client, cid, "Randello", damage_dice="1d6")
    assert not any(k.startswith("druid.primal_strike") for k in await _roll_keys(client, cid, "attack", item_id=club))


async def test_primal_strike_does_not_make_the_beast_attacks_magical(client):
    cid = await _druid24(client, 7)
    await _resolve(client, cid, "elemental_fury", ["primal_strike"])
    form = await _form(client, cid, {**_beast(0.5), "actions": [{"name": "Morso", "attack_bonus": 4, "damage_dice": "1d6", "damage_type": "piercing"}]})
    await _activate(client, cid, form)
    r = await client.post(f"/characters/{cid}/companions/{form}/attack", json={"action_index": 0, "die": 15})
    assert r.status_code == 200, r.text
    assert r.json()["is_magical"] is False


# ---------------------------------------------------------------------------
# Arcidruido
# ---------------------------------------------------------------------------

async def test_evergreen_wild_shape_gives_back_a_use_when_rolling_initiative_with_none_left(client):
    cid = await _druid24(client, 20)
    assert EVERGREEN not in await _roll_keys(client, cid, "initiative")  # restano usi
    for _ in range(4):
        await _shape(client, cid, 1, fly=30)
    assert (await _ability(client, cid, WILD))["uses"] == 0
    assert EVERGREEN in await _roll_keys(client, cid, "initiative")
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 9, "options": [EVERGREEN]})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, WILD))["uses"] == 1


async def test_evergreen_wild_shape_needs_level_20(client):
    cid = await _druid24(client, 19)
    for _ in range(4):
        await _shape(client, cid, 1, fly=30)
    assert EVERGREEN not in await _roll_keys(client, cid, "initiative")


@pytest.mark.parametrize("uses,slot", [(1, 2), (2, 4), (4, 8)])
async def test_nature_magician_turns_unused_uses_into_a_slot_of_two_levels_per_use(client, uses, slot):
    cid = await _druid24(client, 20)
    before = {s["level"]: s["total"] for s in (await _full(client, cid))["spell_slots"]}.get(slot, 0)
    r = await _use(client, cid, MAGICIAN, params={"uses": str(uses)})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, WILD))["uses"] == 4 - uses
    after = {s["level"]: s["total"] for s in (await _full(client, cid))["spell_slots"]}
    assert after[slot] == before + 1 and not (await _turn(client, cid)).get("action_used")
    assert (await _use(client, cid, MAGICIAN, params={"uses": "1"})).status_code == 409  # una volta fino al riposo lungo
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert {s["level"]: s["total"] for s in (await _full(client, cid))["spell_slots"]}.get(slot, 0) == before  # lo slot creato svanisce
    assert (await _use(client, cid, MAGICIAN, params={"uses": "1"})).status_code == 200


async def test_nature_magician_is_refused_above_the_unspent_uses(client):
    cid = await _druid24(client, 20)
    assert (await _use(client, cid, MAGICIAN, params={"uses": "5"})).status_code == 422
    for _ in range(3):
        await _shape(client, cid, 1, fly=30)
    assert (await _use(client, cid, MAGICIAN, params={"uses": "2"})).status_code == 422  # ne resta 1
    assert (await _use(client, cid, MAGICIAN, params={"uses": "1"})).status_code == 200


# ---------------------------------------------------------------------------
# Multiclasse e passaggio da un'edizione all'altra
# ---------------------------------------------------------------------------

async def test_a_druid_level_added_as_a_multiclass_gets_the_level_1_rows_and_the_primal_order_choice(client):
    body = {"name": "Mista", "initial_class": {"class_name": "fighter", "level": 3, "subclass": None}}
    cid = (await client.post("/characters", json=body)).json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    await client.patch(f"/characters/{cid}/ability_scores/wisdom", json={"value": 14})
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "druid", "level": 1})
    assert r.status_code in (200, 201), r.text
    full = await _full(client, cid)
    assert _choice(full, "primal_order") is not None
    assert "druid.druidic" in await _keys_of(client, cid)
    assert any(s["srd_index"] == "speak-with-animals" for s in (await client.get(f"/characters/{cid}/spells")).json())


async def test_a_2014_druid_that_becomes_2024_gets_the_2024_rows_and_keeps_its_spent_uses(client):
    body = {"name": "Druido", "initial_class": {"class_name": "druid", "level": 6, "subclass": None}}
    cid = (await client.post("/characters", json=body)).json()["id"]
    assert (await _ability(client, cid, WILD))["max_uses"] == 2 and (await _ability(client, cid, WILD))["action_type"] == "action"
    await _activate(client, cid, await _form(client, cid))
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    row = await _ability(client, cid, WILD)
    assert (row["max_uses"], row["uses"], row["action_type"]) == (3, 2, "bonus_action")
    assert {COMPANION, RESURGENCE} <= await _keys_of(client, cid)
    assert [c["group"] for c in (await _full(client, cid))["pending_choices"] if c["kind"] == "class_option"] == ["primal_order"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2014"})).status_code == 200
    assert COMPANION not in await _keys_of(client, cid)
    row = await _ability(client, cid, WILD)
    assert (row["max_uses"], row["uses"], row["action_type"]) == (2, 1, "action")
