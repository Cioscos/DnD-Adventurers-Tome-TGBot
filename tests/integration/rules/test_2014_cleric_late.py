"""Chierico 2014 (Task 21): Intervento Divino, Collera Distruttiva, Colpo del Tuono e del Fulmine, Manto di Ombre,
Invocare Duplicato, Visioni del Passato e Nato dalla Tempesta."""
from __future__ import annotations

import pytest

from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _states, _use
from tests.integration.rules.test_2014_barbarian import _turn, _weapon
from tests.integration.rules.test_2014_cleric import POOL, _cleric

DI = "cleric.divine_intervention"


def _roll(monkeypatch, value: int) -> None:
    monkeypatch.setattr("api.services.rules_states.random.randint", lambda a, b: value)


# ---------------------------------------------------------------------------
# Intervento Divino
# ---------------------------------------------------------------------------

async def test_divine_intervention_success_blocks_the_feature_for_seven_days(client, monkeypatch):
    cid = await _cleric(client, 12)
    _roll(monkeypatch, 12)  # d100 <= livello da chierico
    r = await _use(client, cid, DI)
    assert r.status_code == 200, r.text
    assert r.json()["rolls"] == [12]
    state = r.json()["state"]
    assert state["data"] == {"roll": 12, "level": 12, "success": True} and state["ends_on"] == ["manual"]
    assert (await _turn(client, cid))["action_used"] is True
    await client.post(f"/characters/{cid}/turn/new")
    again = await _use(client, cid, DI)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "feature_unavailable"
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert (await _use(client, cid, DI)).status_code == 409  # il blocco di 7 giorni regge al riposo lungo
    await client.delete(f"/characters/{cid}/active-states/divine_intervention")
    assert (await _use(client, cid, DI)).status_code == 200


async def test_divine_intervention_failure_comes_back_after_a_long_rest(client, monkeypatch):
    cid = await _cleric(client, 12)
    _roll(monkeypatch, 13)  # un punto sopra il livello
    state = (await _use(client, cid, DI)).json()["state"]
    assert state["data"]["success"] is False and set(state["ends_on"]) == {"rest_long", "manual"}
    assert (await _ability(client, cid, DI))["uses"] == 0
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert await _states(client, cid) == [] and (await _ability(client, cid, DI))["uses"] == 1


@pytest.mark.parametrize("rolled,success", [(1, True), (10, True), (11, False), (100, False)])
async def test_divine_intervention_compares_the_d100_with_the_level(client, monkeypatch, rolled, success):
    cid = await _cleric(client, 10)
    _roll(monkeypatch, rolled)
    assert (await _use(client, cid, DI)).json()["state"]["data"]["success"] is success


async def test_divine_intervention_at_level_20_always_works_without_rolling(client):
    cid = await _cleric(client, 20)
    r = await _use(client, cid, DI)
    assert r.status_code == 200 and r.json()["rolls"] == [] and r.json()["state"]["data"]["success"] is True


async def test_divine_intervention_appears_at_level_10(client):
    assert DI not in await _keys_of(client, await _cleric(client, 9))
    assert DI in await _keys_of(client, await _cleric(client, 10))


# ---------------------------------------------------------------------------
# Dominio della Tempesta
# ---------------------------------------------------------------------------

async def _spell(client, cid, name, damage_type, level=3, dice="8d6") -> int:
    r = await client.post(f"/characters/{cid}/spells", json={
        "name": name, "level": level, "damage_dice": dice, "damage_type": damage_type, "is_prepared": True})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_destructive_wrath_maximises_lightning_and_thunder_dice(client):
    cid = await _cleric(client, 2, "tempest")
    bolt = await _spell(client, cid, "Fulmine", "lightning", 1, "3d6")
    fire = await _spell(client, cid, "Palla di fuoco", "fire", 1, "3d6")
    assert "cleric.destructive_wrath" in await _roll_keys(client, cid, "spell_damage", spell_id=bolt)
    assert "cleric.destructive_wrath" not in await _roll_keys(client, cid, "spell_damage", spell_id=fire)
    r = await client.post(f"/characters/{cid}/spells/{bolt}/roll_damage", json={
        "main_rolls": [1, 2, 3], "options": ["cleric.destructive_wrath"]})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 18 and r.json()["main_rolls"] == [6, 6, 6]
    assert (await _ability(client, cid, POOL))["uses"] == 0
    assert "cleric.destructive_wrath" not in await _roll_keys(client, cid, "spell_damage", spell_id=bolt)


async def test_destructive_wrath_does_not_touch_other_spells(client):
    cid = await _cleric(client, 2, "tempest")
    fire = await _spell(client, cid, "Palla di fuoco", "fire", 1, "3d6")
    r = await client.post(f"/characters/{cid}/spells/{fire}/roll_damage", json={
        "main_rolls": [1, 2, 3], "options": ["cleric.destructive_wrath"]})
    assert r.status_code == 409


async def test_thunderbolt_strike_shows_the_push_for_lightning_only(client):
    cid = await _cleric(client, 6, "tempest")
    bolt = await _spell(client, cid, "Fulmine", "lightning", 1, "3d6")
    thunder = await _spell(client, cid, "Frantumare", "thunder", 1, "3d6")
    assert "cleric.thunderbolt_strike" in await _roll_keys(client, cid, "spell_damage", spell_id=bolt)
    assert "cleric.thunderbolt_strike" not in await _roll_keys(client, cid, "spell_damage", spell_id=thunder)
    r = await client.post(f"/characters/{cid}/spells/{bolt}/roll_damage", json={
        "main_rolls": [1, 2, 3], "options": ["cleric.thunderbolt_strike"]})
    assert r.status_code == 200, r.text
    assert "3 m" in r.json()["option_result"]["effects"][0]["it"]
    low = await _cleric(client, 5, "tempest")
    assert "cleric.thunderbolt_strike" not in await _roll_keys(
        client, low, "spell_damage", spell_id=await _spell(client, low, "Fulmine", "lightning", 1, "3d6"))


async def test_stormborn_flies_unless_suspended_indoors(client):
    cid = await _cleric(client, 17, "tempest")
    full = await _full(client, cid)
    assert full["computed"]["fly_speed"] == full["computed"]["speed"]
    assert (await _cleric_fly(client, await _cleric(client, 16, "tempest"))) is None
    r = await _use(client, cid, "cleric.stormborn")
    assert r.status_code == 200 and r.json()["state"]["key"] == "stormborn_off"
    assert (await _full(client, cid))["computed"]["fly_speed"] is None
    assert (await _use(client, cid, "cleric.stormborn")).status_code == 409
    await client.delete(f"/characters/{cid}/active-states/stormborn_off")
    assert (await _full(client, cid))["computed"]["fly_speed"] is not None


async def _cleric_fly(client, cid):
    return (await _full(client, cid))["computed"]["fly_speed"]


# ---------------------------------------------------------------------------
# Dominio dell'Inganno
# ---------------------------------------------------------------------------

async def test_cloak_of_shadows_ends_when_you_attack(client):
    cid = await _cleric(client, 6, "trickery", strength=14)
    sword = await _weapon(client, cid, "Mazza", damage_dice="1d6")
    assert "cleric.cloak_attack" not in await _roll_keys(client, cid, "attack", item_id=sword)
    r = await _use(client, cid, "cleric.cloak_of_shadows")
    assert r.status_code == 200 and r.json()["state"]["rounds_left"] == 2
    assert (await _ability(client, cid, POOL))["uses"] == 1
    assert "cleric.cloak_attack" in await _roll_keys(client, cid, "attack", item_id=sword)
    hit = await client.post(f"/characters/{cid}/items/{sword}/attack", json={"die": 10, "options": ["cleric.cloak_attack"]})
    assert hit.status_code == 200, hit.text
    assert hit.json()["mode"] == "advantage"
    assert await _states(client, cid) == []


async def test_cloak_of_shadows_ends_when_you_cast(client):
    cid = await _cleric(client, 6, "trickery")
    await _use(client, cid, "cleric.cloak_of_shadows")
    spell = await _spell(client, cid, "Dardo", "force", 1, "1d4")
    assert "cleric.cloak_cast" in await _roll_keys(client, cid, "cast", spell_id=spell)
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 1, "options": ["cleric.cloak_cast"]})
    assert r.status_code == 200, r.text
    assert await _states(client, cid) == []


async def test_invoke_duplicity_needs_concentration_and_unlocks_the_bonus_move(client):
    cid = await _cleric(client, 2, "trickery")
    move = "cleric.invoke_duplicity_move"
    assert (await _use(client, cid, move)).status_code == 409
    r = await _use(client, cid, "cleric.invoke_duplicity")
    assert r.status_code == 200, r.text
    assert r.json()["state"]["rounds_left"] == 10 and r.json()["state"]["data"]["duplicates"] == 1
    full = await _full(client, cid)
    assert full["settings"]["concentration_item_spell"]["name"] == "Invocare Duplicato"
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid, move)).status_code == 200 and (await _turn(client, cid))["bonus_used"] is True
    assert "cleric.duplicity_advantage" in await _roll_keys(client, cid, "attack")


async def test_losing_concentration_ends_the_duplicate(client):
    cid = await _cleric(client, 2, "trickery")
    await _use(client, cid, "cleric.invoke_duplicity")
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})
    assert await _states(client, cid) == []
    assert "cleric.duplicity_advantage" not in await _roll_keys(client, cid, "attack")


async def test_invoke_duplicity_gives_four_duplicates_from_level_17(client):
    cid = await _cleric(client, 17, "trickery")
    assert (await _use(client, cid, "cleric.invoke_duplicity")).json()["state"]["data"]["duplicates"] == 4


async def test_starting_a_second_concentration_ends_the_duplicate(client):
    cid = await _cleric(client, 3, "trickery")
    await _use(client, cid, "cleric.invoke_duplicity")
    spell = (await client.post(f"/characters/{cid}/spells", json={
        "name": "Benedizione", "level": 1, "is_concentration": True, "duration": "Concentrazione, fino a 1 minuto"})).json()["id"]
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": spell, "rounds": 10})
    assert await _states(client, cid) == []


# ---------------------------------------------------------------------------
# Dominio della Conoscenza
# ---------------------------------------------------------------------------

async def test_visions_of_the_past_lasts_wisdom_minutes_in_concentration(client):
    cid = await _cleric(client, 17, "knowledge", wisdom=18)
    key = "cleric.visions_of_the_past"
    assert (await _ability(client, cid, key))["max_uses"] == 1
    r = await _use(client, cid, key)
    assert r.status_code == 200, r.text
    assert r.json()["state"]["rounds_left"] == 18 * 10 and "concentration_end" in r.json()["state"]["ends_on"]
    assert (await _use(client, cid, key)).status_code == 409  # un solo uso
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert (await _ability(client, cid, key))["uses"] == 1


async def test_visions_of_the_past_ends_with_the_concentration(client):
    cid = await _cleric(client, 17, "knowledge")
    await _use(client, cid, "cleric.visions_of_the_past")
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})
    assert await _states(client, cid) == []


async def test_object_and_area_reading_are_text_only_rows(client):
    cid = await _cleric(client, 17, "knowledge")
    for key in ("cleric.object_reading", "cleric.area_reading"):
        row = await _ability(client, cid, key)
        assert row["is_passive"] is True and row["max_uses"] is None


# ---------------------------------------------------------------------------
# Effetti dati a un alleato: Benedizione del Dio della Guerra e Benedizione dell'Ingannatore
# ---------------------------------------------------------------------------

async def _table(client, test_session_factory, level, domain):
    from tests.integration._encounter_helpers import GM_ID, as_user, seed_session
    from tests.integration.rules.test_2014_bard_inspiration import _seat
    sid, hero = await seed_session(test_session_factory)
    as_user(GM_ID)
    cleric = await _cleric(client, level, domain, wisdom=16)
    await _seat(test_session_factory, cleric)
    return sid, cleric, hero


async def _give(client, cleric, hero, key):
    return await client.post(f"/characters/{cleric}/features/{key}/use", json={"params": {"target_character_id": hero}})


async def test_war_gods_blessing_goes_to_the_ally_and_adds_ten_to_the_attack(client, test_session_factory):
    from tests.integration._encounter_helpers import PLAYER_ID, as_user
    sid, cleric, hero = await _table(client, test_session_factory, 6, "war")
    key = "cleric.war_gods_blessing"
    r = await _give(client, cleric, hero, key)
    assert r.status_code == 200, r.text
    assert (await _ability(client, cleric, POOL))["uses"] == 1 and (await _turn(client, cleric))["reaction_used"] is True
    assert await _states(client, cleric) == []  # lo stato sta sul ricevente
    as_user(PLAYER_ID)
    assert [s["key"] for s in await _states(client, hero)] == ["war_gods_blessing"]
    assert "war_blessing:add" in await _roll_keys(client, hero, "attack")
    assert "war_blessing:add" not in await _roll_keys(client, hero, "skill", skill="stealth")
    sword = await _weapon(client, hero, "Spada", damage_dice="1d8")
    first = (await client.post(f"/characters/{hero}/items/{sword}/attack", json={"die": 8, "defer_damage": True})).json()
    r = await client.post(f"/characters/{hero}/last-roll/options", json={"options": ["war_blessing:add"]})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == first["to_hit_total"] + 10
    assert await _states(client, hero) == []  # speso
    assert (await client.post(f"/characters/{hero}/last-roll/options", json={"options": ["war_blessing:add"]})).status_code == 409


async def test_war_gods_blessing_without_an_ally_stays_as_a_note_for_the_gm_creature(client):
    cid = await _cleric(client, 6, "war")
    r = await _use(client, cid, "cleric.war_gods_blessing")
    assert r.status_code == 200 and r.json()["state"]["key"] == "war_gods_blessing_note"
    assert "war_blessing:add" not in await _roll_keys(client, cid, "attack")  # non è un bonus per chi lo ha dato


async def test_war_gods_blessing_is_refused_for_someone_not_at_the_table(client, test_session_factory):
    sid, cleric, hero = await _table(client, test_session_factory, 6, "war")
    r = await _give(client, cleric, hero + 99, "cleric.war_gods_blessing")
    assert r.status_code == 422 and (await _ability(client, cleric, POOL))["uses"] == 2


async def test_trickster_blessing_gives_the_ally_advantage_on_stealth_only(client, test_session_factory):
    from tests.integration._encounter_helpers import PLAYER_ID, as_user
    sid, cleric, hero = await _table(client, test_session_factory, 1, "trickery")
    assert (await _give(client, cleric, hero, "cleric.blessing_of_the_trickster")).status_code == 200
    assert (await _turn(client, cleric))["action_used"] is True
    as_user(PLAYER_ID)
    [state] = await _states(client, hero)
    assert state["key"] == "trickster_blessing" and state["rounds_left"] == 600
    assert "trickster:advantage" in await _roll_keys(client, hero, "skill", skill="stealth")
    assert "trickster:advantage" not in await _roll_keys(client, hero, "skill", skill="perception")
    r = await client.post(f"/characters/{hero}/skills/stealth/roll", json={"options": ["trickster:advantage"], "die": 7})
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "advantage"
    assert len(await _states(client, hero)) == 1  # dura un'ora: non si spende


# ---------------------------------------------------------------------------
# Conoscenze Secolari
# ---------------------------------------------------------------------------

AGES = "cleric.knowledge_of_the_ages"


async def test_knowledge_of_the_ages_lists_the_skills_to_choose_from(client):
    cid = await _cleric(client, 2, "knowledge")
    row = await _ability(client, cid, AGES)
    [choice] = row["use_choices"]
    assert choice["key"] == "skill" and {o["key"] for o in choice["options"]} >= {"arcana", "stealth", "survival"}
    assert next(o for o in choice["options"] if o["key"] == "arcana")["label"] == {"it": "Arcana", "en": "Arcana"}


async def test_knowledge_of_the_ages_rejects_a_missing_or_unknown_skill_before_spending(client):
    cid = await _cleric(client, 2, "knowledge")
    for params in ({}, {"skill": "pottery"}):
        r = await client.post(f"/characters/{cid}/features/{AGES}/use", json={"params": params})
        assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice"
    assert (await _ability(client, cid, POOL))["uses"] == 1 and (await _turn(client, cid))["action_used"] is False


async def test_knowledge_of_the_ages_adds_proficiency_to_the_chosen_skill_only(client):
    cid = await _cleric(client, 2, "knowledge")  # competenza +2, Destrezza 10
    plain = (await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 10})).json()["total"]
    r = await client.post(f"/characters/{cid}/features/{AGES}/use", json={"params": {"skill": "stealth"}})
    assert r.status_code == 200, r.text
    assert r.json()["state"]["rounds_left"] == 100 and r.json()["state"]["data"] == {"skill": "stealth"}
    assert (await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 10})).json()["total"] == plain + 2
    assert (await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 10})).json()["total"] == 10


async def test_knowledge_of_the_ages_does_not_stack_on_a_skill_you_already_have(client):
    cid = await _cleric(client, 2, "knowledge")
    await client.patch(f"/characters/{cid}/skills", json={"skills": {"stealth": True}})
    before = (await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 10})).json()["total"]
    await client.post(f"/characters/{cid}/features/{AGES}/use", json={"params": {"skill": "stealth"}})
    assert (await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 10})).json()["total"] == before


# ---------------------------------------------------------------------------
# Benedizione dell'Ingannatore: un solo bersaglio alla volta
# ---------------------------------------------------------------------------

async def test_a_new_trickster_blessing_takes_the_state_off_the_previous_target(client, test_session_factory):
    from core.db.models import AbilityScore, Character, SessionParticipant, SessionRole
    from tests.integration._encounter_helpers import GM_ID, NOW, PLAYER_ID, as_user
    sid, cleric, hero = await _table(client, test_session_factory, 1, "trickery")
    async with test_session_factory() as s:
        other = Character(user_id=9002, name="Compagno")
        s.add(other)
        await s.flush()
        s.add(AbilityScore(character_id=other.id, name="dexterity", value=12))
        s.add(SessionParticipant(session_id=sid, user_id=9002, character_id=other.id, role=SessionRole.PLAYER,
                                 display_name="Compagno", joined_at=NOW))
        await s.commit()
        other_id = other.id
    key = "cleric.blessing_of_the_trickster"
    assert (await _give(client, cleric, hero, key)).status_code == 200
    await client.post(f"/characters/{cleric}/turn/new")
    assert (await _give(client, cleric, other_id, key)).status_code == 200
    as_user(PLAYER_ID)
    assert await _states(client, hero) == []  # tolto dal bersaglio precedente
    as_user(9002)
    assert [s["key"] for s in await _states(client, other_id)] == ["trickster_blessing"]
    as_user(GM_ID)
    assert (await _full(client, cleric))["settings"]["ally_exclusive"] == {key: other_id}
    await client.post(f"/characters/{cleric}/turn/new")
    assert (await _give(client, cleric, other_id, key)).status_code == 200  # lo stesso bersaglio: resta uno solo
    as_user(9002)
    assert len(await _states(client, other_id)) == 1


async def test_the_exclusive_target_is_server_owned_and_cleaned_on_import(client):
    cid = await _cleric(client, 1, "trickery")
    full = await _full(client, cid)
    await client.patch(f"/characters/{cid}", json={"settings": {**full["settings"], "ally_exclusive": {"cleric.blessing_of_the_trickster": 99}}})
    assert "ally_exclusive" not in (await _full(client, cid))["settings"]
    exported = (await client.get(f"/characters/{cid}/export")).json()
    exported["character"]["settings"]["ally_exclusive"] = {"cleric.blessing_of_the_trickster": 1}
    new = (await client.post("/characters/import", json=exported)).json()["id"]
    assert "ally_exclusive" not in (await _full(client, new))["settings"]


# ---------------------------------------------------------------------------
# Benedizioni della Conoscenza: i due linguaggi
# ---------------------------------------------------------------------------

def _choice_of(full, group):
    return next(c for c in full["pending_choices"] if c.get("group") == group)


async def test_blessings_of_knowledge_adds_two_languages_without_duplicates(client):
    cid = await _cleric(client, 1, "knowledge")
    await client.patch(f"/characters/{cid}", json={"languages": ["Elfico"]})
    choice = _choice_of(await _full(client, cid), "knowledge_languages")
    assert choice["count"] == 2 and len(choice["options"]) == 15  # quelli che hai già non si offrono
    assert next(o for o in choice["options"] if o["key"] == "dwarvish")["name"] == {"it": "Nanico", "en": "Dwarvish"}
    assert "elvish" not in {o["key"] for o in choice["options"]}
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve", json={"kind": "class_option", "options": ["sylvan", "dwarvish"]})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["languages"] == ["Elfico", "Silvano", "Nanico"]
    assert not any(c.get("group") == "knowledge_languages" for c in r.json()["pending_choices"])


async def test_blessings_of_knowledge_languages_need_two_valid_picks(client):
    cid = await _cleric(client, 1, "knowledge")
    choice = _choice_of(await _full(client, cid), "knowledge_languages")
    for picked in (["elvish"], ["elvish", "elvish"], ["elvish", "klingon"]):
        r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve", json={"kind": "class_option", "options": picked})
        assert r.status_code in (400, 422)
    assert (await _full(client, cid))["languages"] in ([], None)


async def test_an_imported_cleric_can_declare_the_languages_it_already_has(client):
    cid = await _cleric(client, 1, "knowledge")
    await client.patch(f"/characters/{cid}", json={"languages": ["Comune", "Elfico", "Nanico"]})
    exported = (await client.get(f"/characters/{cid}/export")).json()
    new = (await client.post("/characters/import", json=exported)).json()["id"]
    choice = _choice_of(await _full(client, new), "knowledge_languages")
    assert choice["retrofit"] is True
    assert {o["key"] for o in choice["options"] if o.get("owned")} == {"common", "elvish", "dwarvish"}
    r = await client.post(f"/characters/{new}/choices/{choice['id']}/resolve", json={"kind": "class_option", "options": ["elvish", "dwarvish"]})
    assert r.status_code == 200, r.text
    assert (await _full(client, new))["languages"] == ["Comune", "Elfico", "Nanico"]  # nessun duplicato
