"""Bardo 2024 (Task 32): tabelle, Ispirazione Bardica, Fonte di Ispirazione, Maestria, Factotum, Controfascino, Segreti
Magici, Ispirazione Superiore, Parole della Creazione e passaggio da un'edizione all'altra. Valori dalla scheda
``docs/superpowers/rules/2024/classes/bard.md``."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from core.db.models import SessionParticipant
from core.rules.catalog import features_for
from core.rules.proficiencies import class_proficiencies
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard import (
    BI, _ability, _add_spell, _choice, _full, _keys_of, _resolve, _roll_keys, _skills, _states, _use,
)

PREPARED = (4, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16, 16, 17, 17, 18, 18, 19, 20, 21, 22)
CANTRIPS = (2, 2, 2, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4)
SLOTS = {1: (2,), 3: (4, 2), 5: (4, 3, 2), 9: (4, 3, 3, 3, 1), 13: (4, 3, 3, 3, 2, 1, 1), 17: (4, 3, 3, 3, 2, 1, 1, 1, 1),
         20: (4, 3, 3, 3, 3, 2, 2, 1, 1)}
DANCE, GLAMOUR, LORE, VALOR = "Collegio della Danza", "Collegio dell'Incanto", "Collegio della Sapienza", "Collegio del Valore"


async def _bard24(client, level=5, subclass=None, **scores) -> int:
    body = {"name": "Bardo", "initial_class": {"class_name": "bard", "level": level, "subclass": subclass}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


async def _turn(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]


async def _slot_used(client, cid, level) -> int:
    return next(s["used"] for s in (await _full(client, cid))["spell_slots"] if s["level"] == level and not s["is_pact"])


async def _set_uses(client, cid, key, uses) -> None:
    row = await _ability(client, cid, key)
    assert (await client.patch(f"/characters/{cid}/abilities/{row['id']}", json={"uses": uses})).status_code == 200


# ---------------------------------------------------------------------------
# Tabelle e catalogo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", range(1, 21))
async def test_cantrips_and_prepared_spells_follow_the_2024_table(client, level):
    cid = await _bard24(client, level)
    limits = (await _full(client, cid))["spellcasting"]["limits"][0]
    assert (limits["cantrips_limit"], limits["prepared_limit"], limits["known_limit"]) == (
        CANTRIPS[level - 1], PREPARED[level - 1], None)


@pytest.mark.parametrize("level", sorted(SLOTS))
async def test_spell_slots_follow_the_full_caster_table(client, level):
    cid = await _bard24(client, level)
    slots = tuple(s["total"] for s in sorted((await _full(client, cid))["spell_slots"], key=lambda s: s["level"]))
    assert slots == SLOTS[level]


async def test_the_prepared_cap_blocks_the_fifth_spell_of_a_level_1_bard(client):
    cid = await _bard24(client, 1)
    for i in range(4):
        r = await _add_spell(client, cid, f"Incantesimo {i}", 1, is_prepared=True)
        assert r.status_code == 201, r.text
    r = await _add_spell(client, cid, "Incantesimo 4", 1, is_prepared=True)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "prepared_cap"


async def test_hit_points_use_the_d8_and_follow_constitution(client):
    cid = await _bard24(client, 3)
    full = await _full(client, cid)
    assert full["classes"][0]["hit_die"] == 8
    assert full["hit_points"] == 8 + 5 + 5
    await client.patch(f"/characters/{cid}/ability_scores/constitution", json={"value": 14})
    assert (await _full(client, cid))["hit_points"] == 8 + 5 + 5 + 2 * 3


def test_class_and_multiclass_proficiencies_from_the_class_table():
    first = class_proficiencies("2024", "bard", False)
    assert first.armor == ("light",) and first.weapons == ("simple",)
    assert set(first.saves) == {"dexterity", "charisma"} and first.skills_count == 3
    multi = class_proficiencies("2024", "bard", True)
    assert multi.armor == ("light",) and not multi.weapons and not multi.saves and multi.skills_count == 1


@pytest.mark.parametrize("level,present", [
    (1, {"bardic_inspiration"}), (2, {"expertise", "jack_of_all_trades"}), (5, {"font_of_inspiration"}),
    (7, {"countercharm"}), (10, {"magical_secrets"}), (18, {"superior_inspiration"}), (20, {"words_of_creation"}),
])
async def test_features_appear_at_their_level(client, level, present):
    cid = await _bard24(client, level)
    assert {f"bard.{k}" for k in present} <= await _keys_of(client, cid)
    low = await _keys_of(client, await _bard24(client, level - 1)) if level > 1 else set()
    assert not {f"bard.{k}" for k in present} & low


async def test_the_2024_bard_has_no_song_of_rest_and_rules_only_rows_stay_off_the_sheet(client):
    cid = await _bard24(client, 20, LORE)
    keys = await _keys_of(client, cid)
    assert "bard.song_of_rest" not in keys
    assert not keys & {f"bard.{k}" for k in (
        "core_traits", "spellcasting", "bard_subclass", "ability_score_improvement", "epic_boon", "multiclassing")}
    titles = {s.source_title for s in features_for("2024", "bard")}
    assert "Tratti Base del Bardo / Core Bard Traits (Bardo 1, pag. 59)" in titles


@pytest.mark.parametrize("level,asi", [(4, [4]), (8, [4, 8]), (16, [4, 8, 12, 16]), (19, [4, 8, 12, 16])])
async def test_asi_choice_is_pending_at_each_asi_level_and_the_19th_is_an_epic_boon(client, level, asi):
    cid = await _bard24(client, level)
    pending = (await _full(client, cid))["pending_choices"]
    assert sorted(c["level"] for c in pending if c["kind"] == "asi") == asi
    assert [c["level"] for c in pending if c["kind"] == "epic_boon"] == ([19] if level >= 19 else [])


# ---------------------------------------------------------------------------
# Ispirazione Bardica
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,cha,uses,rest", [
    (1, 16, 3, "long_rest"), (1, 8, 1, "long_rest"), (4, 18, 4, "long_rest"),
    (5, 14, 2, "short_rest"), (5, 8, 1, "short_rest"), (15, 20, 5, "short_rest")])
async def test_inspiration_uses_follow_charisma_and_recharge_by_level(client, level, cha, uses, rest):
    cid = await _bard24(client, level, charisma=cha)
    bi = await _ability(client, cid, BI)
    assert (bi["name"], bi["max_uses"], bi["uses"], bi["restoration_type"]) == ("Ispirazione Bardica", uses, uses, rest)


@pytest.mark.parametrize("level,die", [(1, 6), (4, 6), (5, 8), (9, 8), (10, 10), (14, 10), (15, 12), (20, 12)])
async def test_inspiration_die_follows_the_level_and_lasts_one_hour(client, level, die):
    cid = await _bard24(client, level, charisma=16)
    r = await _use(client, cid, BI)
    assert r.status_code == 200, r.text
    state = r.json()["state"]
    assert (state["key"], state["data"]["die"], state["rounds_left"]) == ("bardic_inspiration", die, 600)
    assert state["data"]["others"] == [BI]


async def test_inspiration_spends_a_use_and_the_bonus_action(client):
    cid = await _bard24(client, 5, charisma=16)
    assert (await _use(client, cid, BI)).status_code == 200
    assert (await _ability(client, cid, BI))["uses"] == 2
    again = await _use(client, cid, BI)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"


async def test_inspiration_recharges_on_a_short_rest_only_from_level_5(client):
    low, high = await _bard24(client, 4, charisma=16), await _bard24(client, 5, charisma=16)
    for cid in (low, high):
        assert (await _use(client, cid, BI)).status_code == 200
        assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})).status_code == 200
    assert (await _ability(client, low, BI))["uses"] == 2
    assert (await _ability(client, high, BI))["uses"] == 3


async def test_the_2024_inspiration_replaces_the_2014_ten_minutes(client):
    cid = await _bard24(client, 5, charisma=16)
    ability = await _ability(client, cid, BI)
    assert "1 ora" in ability["description"] or "un'ora" in ability["description"].lower()


async def _table(client, test_session_factory, level=5, subclass=None):
    sid, hero = await seed_session(test_session_factory)
    as_user(GM_ID)
    bard = await _bard24(client, level, subclass, charisma=16)
    async with test_session_factory() as s:
        part = (await s.execute(select(SessionParticipant).where(SessionParticipant.user_id == GM_ID))).scalar_one()
        part.character_id = bard
        await s.commit()
    return sid, bard, hero


async def test_the_die_given_to_an_ally_lasts_one_hour_and_is_independent_of_the_ally_edition(client, test_session_factory):
    sid, bard, hero = await _table(client, test_session_factory, level=10)
    r = await client.post(f"/characters/{bard}/features/{BI}/use", json={"params": {"target_character_id": hero}})
    assert r.status_code == 200, r.text
    as_user(PLAYER_ID)
    [state] = [s for s in (await _full(client, hero))["active_states"] if s["key"] == "bardic_die"]
    assert (state["data"]["die"], state["rounds_left"]) == (10, 600) and not state["data"].get("combat")


# ---------------------------------------------------------------------------
# Fonte di Ispirazione
# ---------------------------------------------------------------------------

async def test_font_of_inspiration_turns_a_slot_into_a_use_without_an_action(client):
    cid = await _bard24(client, 5, charisma=16)
    await _set_uses(client, cid, BI, 1)
    r = await _use(client, cid, "bard.font_of_inspiration", params={"slot_level": "2"})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, BI))["uses"] == 2
    assert await _slot_used(client, cid, 2) == 1
    turn = await _turn(client, cid)
    assert not (turn["action_used"] or turn["bonus_used"] or turn["reaction_used"])


async def test_font_of_inspiration_never_goes_over_the_maximum_and_keeps_the_slot(client):
    cid = await _bard24(client, 5, charisma=16)
    r = await _use(client, cid, "bard.font_of_inspiration", params={"slot_level": "1"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "feature_unavailable"
    assert await _slot_used(client, cid, 1) == 0


async def test_font_of_inspiration_needs_a_free_slot_of_that_level(client):
    cid = await _bard24(client, 5, charisma=16)
    await _set_uses(client, cid, BI, 0)
    r = await _use(client, cid, "bard.font_of_inspiration", params={"slot_level": "4"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice"
    assert (await _ability(client, cid, BI))["uses"] == 0


async def test_font_of_inspiration_is_not_there_below_level_5(client):
    assert "bard.font_of_inspiration" not in await _keys_of(client, await _bard24(client, 4))


# ---------------------------------------------------------------------------
# Maestria e Factotum
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,count", [(2, 2), (8, 2), (9, 4)])
async def test_expertise_comes_at_levels_2_and_9(client, level, count):
    cid = await _bard24(client, level)
    assert _choice(await _full(client, cid), "expertise")["count"] == count


async def test_expertise_only_on_skills_the_bard_is_proficient_in(client):
    cid = await _bard24(client, 2)
    await _skills(client, cid, acrobatics=True, arcana="expert", history=True)
    assert (await _resolve(client, cid, "expertise", ["acrobatics", "insight"])).status_code == 422
    r = await _resolve(client, cid, "expertise", ["acrobatics", "history"])
    assert r.status_code == 200, r.text
    assert r.json()["skills"]["acrobatics"] == "expert" and r.json()["skills"]["history"] == "expert"


async def test_jack_of_all_trades_adds_half_proficiency_to_skills_without_it_but_not_to_pure_checks(client):
    cid = await _bard24(client, 5, dexterity=10)  # competenza +3: metà 1
    await _skills(client, cid, stealth=True, acrobatics="expert")
    stealth = (await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 10})).json()
    expert = (await client.post(f"/characters/{cid}/skills/acrobatics/roll", json={"die": 10})).json()
    other = (await client.post(f"/characters/{cid}/skills/sleight_of_hand/roll", json={"die": 10})).json()
    assert (stealth["bonus"], expert["bonus"], other["bonus"]) == (3, 6, 1)
    pure = (await client.post(f"/characters/{cid}/ability_checks/dexterity/roll", json={"die": 10})).json()
    assert pure["bonus"] == 0  # il 2024 parla di prove con un'abilità: una prova pura non ha competenza da sommare


async def test_jack_of_all_trades_is_not_added_to_the_2024_initiative(client):
    cid = await _bard24(client, 5, dexterity=14)
    roll = (await client.post(f"/characters/{cid}/dice/initiative", json={"die": 10})).json()
    assert roll["bonus"] == 2 and "feature:bard.jack_of_all_trades" not in roll["notes"]
    assert (await _full(client, cid))["initiative_bonus"] == 2


async def test_the_2014_bard_still_adds_half_proficiency_to_pure_checks_and_initiative(client):
    body = {"name": "Bardo", "initial_class": {"class_name": "bard", "level": 5, "subclass": None}}
    cid = (await client.post("/characters", json=body)).json()["id"]
    await client.patch(f"/characters/{cid}/ability_scores/dexterity", json={"value": 14})
    pure = (await client.post(f"/characters/{cid}/ability_checks/dexterity/roll", json={"die": 10})).json()
    assert pure["bonus"] == 3
    assert (await client.post(f"/characters/{cid}/dice/initiative", json={"die": 10})).json()["bonus"] == 3


# ---------------------------------------------------------------------------
# Controfascino
# ---------------------------------------------------------------------------

async def test_countercharm_offers_the_reroll_with_advantage_for_a_reaction(client):
    cid = await _bard24(client, 7)
    r = await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": 4})
    assert r.status_code == 200, r.text
    options = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "save", "ability": "wisdom"})).json()
    cc = next(o for o in options if o["key"] == "bard.countercharm")
    assert (cc["phase"], cc["slot"]) == ("after_roll", "reaction")
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": ["bard.countercharm"]})
    assert r.status_code == 200, r.text
    assert r.json()["mode_applied"] == "advantage"
    assert (await _turn(client, cid))["reaction_used"] is True
    assert "bard.countercharm" not in [o["key"] for o in (await client.get(
        f"/characters/{cid}/roll-options", params={"roll": "save", "ability": "wisdom"})).json()]  # la reazione è spesa


async def test_countercharm_is_a_reaction_for_a_creature_within_9_m(client):
    cid = await _bard24(client, 7)
    r = await _use(client, cid, "bard.countercharm")
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["reaction_used"] is True
    assert r.json()["message"]["it"] and r.json()["message"]["en"]
    again = await _use(client, cid, "bard.countercharm")
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"


async def test_countercharm_is_refused_while_incapacitated(client):
    cid = await _bard24(client, 7)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"stunned": True}})
    assert "bard.countercharm" not in await _roll_keys(client, cid, "save", ability="wisdom")


# ---------------------------------------------------------------------------
# Segreti Magici
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,count", [(10, 1), (11, 2), (12, 2), (13, 3), (14, 3), (15, 4), (16, 4), (17, 5), (18, 6),
                                         (19, 7), (20, 8)])
async def test_magical_secrets_count_follows_the_growth_of_the_prepared_spells_from_level_10(client, level, count):
    cid = await _bard24(client, level)
    assert _choice(await _full(client, cid), "magical_secrets")["count"] == count
    assert PREPARED[level - 1] - PREPARED[8] == count  # i preparati cresciuti dopo il 9°


async def test_magical_secrets_is_absent_below_level_10(client):
    assert _choice(await _full(client, await _bard24(client, 9)), "magical_secrets") is None


async def test_magical_secrets_pick_a_spell_of_another_list_as_a_bard_spell(client):
    cid = await _bard24(client, 10)
    choice = _choice(await _full(client, cid), "magical_secrets")
    assert choice["spell_pick"]["max_level"] == 5 and choice["spell_pick"]["free"] is False
    assert (await _add_spell(client, cid, "Disintegrazione", 6, pick_id=choice["id"])).status_code == 422
    r = await _add_spell(client, cid, "Palla di fuoco", 3, pick_id=choice["id"])
    assert r.status_code == 201, r.text
    assert r.json()["class_id"] == (await _full(client, cid))["classes"][0]["id"]
    assert _choice(await _full(client, cid), "magical_secrets") is None


# ---------------------------------------------------------------------------
# Ispirazione Superiore
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("start,expected", [(0, 2), (1, 2), (2, 2), (3, 3)])
async def test_superior_inspiration_brings_the_uses_up_to_two_at_initiative(client, start, expected):
    cid = await _bard24(client, 18, charisma=16)  # 3 usi
    await _set_uses(client, cid, BI, start)
    assert "bard.superior_inspiration" not in await _roll_keys(client, cid, "initiative")  # nessuna scelta: è automatica
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 8})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, BI))["uses"] == expected


async def test_superior_inspiration_never_gives_more_than_the_maximum(client):
    cid = await _bard24(client, 18, charisma=10)  # 1 uso
    await _set_uses(client, cid, BI, 0)
    await client.post(f"/characters/{cid}/dice/initiative", json={"die": 8})
    assert (await _ability(client, cid, BI))["uses"] == 1


async def test_superior_inspiration_in_the_encounter_initiative(client, test_session_factory):
    sid, hero = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{hero}/classes", json={"class_name": "bard", "level": 18, "hit_die": 8})
    assert r.status_code == 201, r.text
    await client.patch(f"/characters/{hero}", json={"rules_edition": "2024"})
    await _set_uses(client, hero, BI, 0)
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    comb = next(c for c in r.json()["combatants"] if c["kind"] == "pc")
    as_user(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{comb['id']}/initiative", json={"die": 8})
    assert r.status_code == 200, r.text
    assert (await _ability(client, hero, BI))["uses"] == min(2, (await _ability(client, hero, BI))["max_uses"])


# ---------------------------------------------------------------------------
# Parole della Creazione
# ---------------------------------------------------------------------------

async def test_words_of_creation_gives_the_two_power_words_always_prepared_outside_the_cap(client):
    cid = await _bard24(client, 20)
    spells = {s["name"]: s for s in (await client.get(f"/characters/{cid}/spells")).json()}
    heal, kill = spells["Parola del Potere: Guarigione"], spells["Parola del Potere: Uccisione"]
    for spell in (heal, kill):
        assert spell["always_prepared"] and spell["is_prepared"] and spell["level"] == 9
    limits = (await _full(client, cid))["spellcasting"]["limits"][0]
    assert limits["prepared_count"] == 0  # sempre preparate, fuori dal limite
    assert (await _full(client, cid))["spellcasting"]["prepared_count"] == 0


async def test_words_of_creation_offers_the_second_target_only_for_the_two_spells(client):
    for name in ("Parola del Potere: Guarigione", "Parola del Potere: Uccisione"):
        cid = await _bard24(client, 20)  # un solo slot di 9° livello: un bardo per ogni lancio
        spells = {s["name"]: s for s in (await client.get(f"/characters/{cid}/spells")).json()}
        r = await client.post(f"/characters/{cid}/spells/{spells[name]['id']}/use", json={"slot_level": 9})
        assert r.status_code == 200, r.text
        [effect] = r.json()["option_result"]["effects"]
        assert "3 m" in effect["it"] and "10 ft" in effect["en"]
    other = (await _add_spell(client, cid, "Dardo incantato", 1)).json()
    await client.post(f"/characters/{cid}/turn/new")
    r = await client.post(f"/characters/{cid}/spells/{other['id']}/use", json={"slot_level": 1})
    assert r.status_code == 200, r.text
    assert not (r.json().get("option_result") or {}).get("effects")


async def test_the_power_words_go_away_from_the_always_prepared_when_the_feature_goes(client):
    cid = await _bard24(client, 20)
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2014"})).status_code == 200
    spells = {s["name"]: s for s in (await client.get(f"/characters/{cid}/spells")).json()}
    assert not spells["Parola del Potere: Guarigione"]["always_prepared"]


# ---------------------------------------------------------------------------
# Cambio di edizione
# ---------------------------------------------------------------------------

async def test_a_2014_bard_that_becomes_2024_gets_the_2024_rows_and_keeps_its_spent_uses(client):
    body = {"name": "Bardo", "initial_class": {"class_name": "bard", "level": 7, "subclass": None}}
    cid = (await client.post("/characters", json=body)).json()["id"]
    await client.patch(f"/characters/{cid}/ability_scores/charisma", json={"value": 16})
    assert (await _use(client, cid, BI)).status_code == 200
    keys14 = await _keys_of(client, cid)
    assert {"bard.song_of_rest", "bard.countercharm"} <= keys14
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    keys24 = await _keys_of(client, cid)
    assert "bard.song_of_rest" not in keys24 and "bard.countercharm" in keys24
    assert (await _ability(client, cid, BI))["uses"] == 2
    assert (await _use(client, cid, "bard.countercharm")).status_code == 200  # la riga del 2014 ora fa ciò che dice il 2024
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2014"})).status_code == 200
    assert (await _ability(client, cid, BI))["uses"] == 2 and "bard.song_of_rest" in await _keys_of(client, cid)


async def test_an_existing_2024_bard_without_the_catalog_receives_no_new_choice_but_the_rules(client):
    cid = await _bard24(client, 3)
    pending = (await _full(client, cid))["pending_choices"]
    assert [c["group"] for c in pending if c["kind"] == "class_option"] == ["expertise"]


async def test_a_2014_valor_bard_that_becomes_2024_gets_martial_training_and_the_2024_battle_magic(client):
    body = {"name": "Bardo", "initial_class": {"class_name": "bard", "level": 14, "subclass": VALOR}}
    cid = (await client.post("/characters", json=body)).json()["id"]
    keys14 = await _keys_of(client, cid)
    assert {"bard.valor_bonus_proficiencies", "bard.battle_magic"} <= keys14
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    keys24 = await _keys_of(client, cid)
    assert "bard.valor_bonus_proficiencies" not in keys24 and {"bard.martial_training", "bard.battle_magic"} <= keys24
    got = (await _full(client, cid))["general_proficiencies"]
    assert "Armi da guerra" in got["weapons"]  # le competenze già concesse restano
    assert "bard.song_of_rest" not in keys24


# ---------------------------------------------------------------------------
# Importazione da Beyond
# ---------------------------------------------------------------------------

async def test_the_beyond_2024_bard_imports_with_the_2024_catalog(client, monkeypatch):
    from tests.integration.rules.test_2014_monk import _import_fixture
    _import_fixture(monkeypatch, "bard20_2024.json")
    r = await client.post("/characters/import/ddb", json={"url": "https://www.dndbeyond.com/characters/1", "rules_edition": "2024"})
    assert r.status_code == 201, r.text
    full = r.json()["character"]
    rows = {a["feature_key"]: a for a in full["abilities"]}
    assert rows[BI]["restoration_type"] == "short_rest" and rows[BI]["max_uses"] >= 1
    assert {"bard.font_of_inspiration", "bard.countercharm", "bard.superior_inspiration", "bard.words_of_creation",
            "bard.cutting_words", "bard.peerless_skill", "bard.magical_discoveries"} <= set(rows)
    assert "bard.song_of_rest" not in rows
    spells = {s["srd_index"] for s in full["spells"]}
    assert {"power-word-heal", "power-word-kill"} <= spells
    kinds = [c["kind"] for c in full["pending_choices"]]
    assert kinds.count("asi") == 0  # il 19° di un 2024 è un Dono Epico
