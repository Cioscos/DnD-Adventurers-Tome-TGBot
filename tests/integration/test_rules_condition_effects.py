"""Effetti delle condizioni e modificatori di classe su ogni tiro e valore derivato (Task 11)."""
from __future__ import annotations

import random

import pytest
from sqlalchemy import select

from core.db.models import Character, CharacterHistory
from core.rules.types import FeatureSpec, Modifier
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session


async def _char(client, edition="2014", cls="fighter", level=1) -> int:
    r = await client.post("/characters", json={"name": "Prova"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": cls, "level": level, "hit_die": 10})
    assert r.status_code == 201, r.text
    if edition != "2014":
        r = await client.patch(f"/characters/{cid}", json={"rules_edition": edition})
        assert r.status_code == 200, r.text
    return cid


async def _cond(client, cid, **conditions) -> dict:
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": conditions})
    assert r.status_code == 200, r.text
    return r.json()


async def _set_hp(client, cid, maximum, current=None) -> None:
    for op, value in (("set_max", maximum), ("set_current", current if current is not None else maximum)):
        r = await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": value})
        assert r.status_code == 200, r.text


async def _weapon(client, cid) -> int:
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Spada", "item_type": "weapon",
        "item_metadata": {"damage_dice": "1d8", "weapon_type": "melee", "properties": []}})
    assert r.status_code == 201, r.text
    return next(i["id"] for i in r.json()["items"] if i["name"] == "Spada") if "items" in r.json() else r.json()["id"]


async def _passive_rule(client, cid, target, value) -> None:
    r = await client.post(f"/characters/{cid}/homebrew/rules", json={
        "name": target, "enabled": True,
        "dsl": {"version": 1, "subject": {"type": "character"}, "triggers": [], "passive_modifiers": [{
            "when": {"path": "$character.id", "op": "gt", "value": 0},
            "target": target, "value": value, "label_i18n": {"it": target, "en": target}}]},
    })
    assert r.status_code in (200, 201), r.text


def _spec(*modifiers, key="fighter.prova") -> FeatureSpec:
    return FeatureSpec(
        key=key, class_key="fighter", edition="2014", level=1, source_title="Prova",
        name={"it": "Prova", "en": "Test"}, summary={"it": "x", "en": "x"}, action_type=None, modifiers=modifiers,
    )


# --- Tiri ------------------------------------------------------------------------------------------------------------

async def test_skill_roll_gets_automatic_mode_and_explains_why(client):
    cid = await _char(client)
    await _cond(client, cid, poisoned=True)
    body = (await client.post(f"/characters/{cid}/skills/stealth/roll")).json()
    assert body["mode_applied"] == "disadvantage" and body["mode"] == "disadvantage"
    assert len(body["dice"]) == 2 and body["die"] == min(body["dice"])
    assert body["notes"] == ["condition:poisoned"]


async def test_client_single_die_gets_a_second_one_when_mode_is_forced(client, monkeypatch):
    cid = await _char(client)
    await _cond(client, cid, poisoned=True)
    monkeypatch.setattr(random, "randint", lambda a, b: 4)
    body = (await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 15})).json()
    assert body["dice"] == [15, 4] and body["die"] == 4


async def test_player_advantage_and_condition_cancel_on_the_first_die(client):
    cid = await _char(client)
    await _cond(client, cid, poisoned=True)
    body = (await client.post(f"/characters/{cid}/skills/stealth/roll",
                              json={"mode": "advantage", "dice": [3, 18]})).json()
    assert body["mode_applied"] == "normal" and body["dice"] == [3] and body["die"] == 3


async def test_without_conditions_the_dice_contract_is_unchanged(client):
    cid = await _char(client)
    body = (await client.post(f"/characters/{cid}/skills/stealth/roll",
                              json={"mode": "advantage", "dice": [3, 18]})).json()
    assert body["mode_applied"] == "advantage" and body["die"] == 18 and body["notes"] == []
    r = await client.post(f"/characters/{cid}/skills/stealth/roll", json={"mode": "advantage", "dice": [3]})
    assert r.status_code == 422


async def test_inspiration_reroll_stays_a_single_die_under_conditions(client, test_session_factory):
    cid = await _char(client, edition="2024")
    await _cond(client, cid, poisoned=True)
    async with test_session_factory() as s:
        (await s.get(Character, cid)).heroic_inspiration = True
        await s.commit()
    body = (await client.post(f"/characters/{cid}/skills/stealth/roll",
                              json={"with_inspiration": True, "die": 9})).json()
    assert body["dice"] == [9] and body["mode_applied"] == "normal" and body["notes"] == ["condition:poisoned"]


async def test_save_auto_fail_is_reported(client):
    cid = await _char(client)
    await _cond(client, cid, stunned=True)
    body = (await client.post(f"/characters/{cid}/saving_throws/dexterity/roll", json={"die": 20})).json()
    assert body["auto_fail"] is True and "condition:stunned" in body["notes"]
    body = (await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": 20})).json()
    assert body["auto_fail"] is False


async def test_pending_save_auto_fail_does_not_pass(client, test_session_factory):
    from api.services.condition_effects import SaveSpec, upsert_effect
    from core.db.models import PendingSave
    cid = await _char(client)
    await _cond(client, cid, stunned=True)
    async with test_session_factory() as s:
        eff = await upsert_effect(s, ("character", cid), "stunned", save=SaveSpec("dexterity", 10, "end"))
        ps = PendingSave(effect_id=eff.id, character_id=cid, ability="dexterity", dc=10, status="pending",
                         created_at="2026-11-04T00:00:00")
        s.add(ps)
        await s.commit()
        psid = ps.id
    r = await client.post(f"/characters/{cid}/pending-saves/{psid}/roll", json={"die": 20})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["passed"] is False and body["roll"]["auto_fail"] is True
    assert (await client.get(f"/characters/{cid}")).json()["conditions"]["stunned"]


async def test_weapon_and_unarmed_attack_modes(client):
    cid = await _char(client)
    weapon = await _weapon(client, cid)
    await _cond(client, cid, prone=True)
    for url in (f"/characters/{cid}/items/{weapon}/attack", f"/characters/{cid}/attack/unarmed"):
        body = (await client.post(url, json={"confirm_extra_attack": True})).json()
        assert body["mode_applied"] == "disadvantage" and len(body["dice"]) == 2
        assert body["notes"] == ["condition:prone"]
    await _cond(client, cid, prone=False, invisible=True)
    body = (await client.post(f"/characters/{cid}/attack/unarmed", json={"confirm_extra_attack": True})).json()
    assert body["mode_applied"] == "advantage"


async def test_spell_attack_mode(client):
    cid = await _char(client, cls="wizard")
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Dardo", "level": 0, "attack_save": "ATK"})
    assert r.status_code in (200, 201), r.text
    sid = r.json()["id"]
    await _cond(client, cid, blinded=True)
    r = await client.post(f"/characters/{cid}/spells/{sid}/attack", json={"slot_level": None})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode_applied"] == "disadvantage" and body["notes"] == ["condition:blinded"]


async def test_exhaustion_2024_reduces_every_d20_test_and_the_sheet(client):
    cid = await _char(client, edition="2024")
    weapon = await _weapon(client, cid)
    clean = (await client.get(f"/characters/{cid}")).json()
    base_attack = (await client.post(f"/characters/{cid}/items/{weapon}/attack", json={"die": 10})).json()
    base_skill = (await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 10})).json()
    base_save = (await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": 10})).json()

    full = await _cond(client, cid, exhaustion=2)
    assert full["computed"]["save_flat"]["wisdom"] == -4
    assert full["skill_bonuses"]["stealth"] == clean["skill_bonuses"]["stealth"] - 4
    assert full["initiative_bonus"] == clean["initiative_bonus"] - 4
    assert full["computed"]["speed"] == clean["computed"]["speed"] - 10
    attack = (await client.post(f"/characters/{cid}/items/{weapon}/attack",
                                json={"die": 10, "confirm_extra_attack": True})).json()
    assert attack["to_hit_bonus"] == base_attack["to_hit_bonus"] - 4
    assert attack["mode_applied"] == "normal" and attack["notes"] == ["condition:exhaustion"]
    skill = (await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 10})).json()
    assert skill["total"] == base_skill["total"] - 4
    save = (await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": 10})).json()
    assert save["total"] == base_save["total"] - 4


async def test_death_save_exhaustion_2024_uses_the_penalty_but_not_for_natural_results(client):
    cid = await _char(client, edition="2024")
    await _cond(client, cid, exhaustion=3)
    await _set_hp(client, cid, 20, 0)
    body = (await client.post(f"/characters/{cid}/death_saves/roll", json={"die": 12})).json()
    assert body["outcome"] == "failure" and body["notes"] == ["condition:exhaustion"]
    body = (await client.post(f"/characters/{cid}/death_saves/roll", json={"die": 16})).json()
    assert body["outcome"] == "success"
    body = (await client.post(f"/characters/{cid}/death_saves/roll", json={"die": 20})).json()
    assert body["outcome"] == "nat20"


async def test_death_save_exhaustion_2014_rolls_with_disadvantage(client):
    cid = await _char(client)
    await _cond(client, cid, exhaustion=3)
    await _set_hp(client, cid, 20, 0)
    body = (await client.post(f"/characters/{cid}/death_saves/roll")).json()
    assert body["mode_applied"] == "disadvantage" and len(body["dice"]) == 2


async def test_concentration_save_modes_cancel_with_war_caster(client, test_session_factory):
    cid = await _char(client)
    await _cond(client, cid, exhaustion=3)
    body = (await client.post(f"/characters/{cid}/concentration/save", json={"damage": 10})).json()
    assert body["mode_applied"] == "disadvantage" and body["notes"] == ["condition:exhaustion"]
    body = (await client.post(f"/characters/{cid}/concentration/save",
                              json={"damage": 10, "mode": "advantage", "dice": [2, 19]})).json()
    assert body["mode_applied"] == "normal" and body["die"] == 2


async def test_active_wild_shape_attack_keeps_the_character_conditions(client):
    cid = await _char(client)
    r = await client.post(f"/characters/{cid}/companions", json={
        "kind": "wild_shape", "name": "Lupo", "max_hp": 10, "armor_class": 13,
        "statblock": {"actions": [{"name": "Morso", "attack_bonus": 4, "damage_dice": "1d6"}]}})
    assert r.status_code in (200, 201), r.text
    comp = r.json()["id"]
    await _cond(client, cid, poisoned=True)
    # non attiva: è un altro combattente, le condizioni del personaggio non contano
    body = (await client.post(f"/characters/{cid}/companions/{comp}/attack", json={"action_index": 0})).json()
    assert body["mode"] == "normal" and body["notes"] == []
    r = await client.post(f"/characters/{cid}/companions/{comp}/activate")
    assert r.status_code == 200, r.text
    body = (await client.post(f"/characters/{cid}/companions/{comp}/attack", json={"action_index": 0})).json()
    assert body["mode"] == "disadvantage" and body["notes"] == ["condition:poisoned"]


# --- Iniziativa ------------------------------------------------------------------------------------------------------

async def _initiative_setup(client, factory, *, conditions, edition="2014"):
    sid, cid = await seed_session(factory)
    async with factory() as s:
        char = await s.get(Character, cid)
        char.conditions = conditions
        char.rules_edition = edition
        await s.commit()
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    assert r.status_code == 201, r.text
    pc = next(c for c in r.json()["combatants"] if c["kind"] == "pc")
    return sid, pc


@pytest.mark.parametrize("edition,die", [("2014", 3), ("2024", 17)])
async def test_invisible_initiative_uses_the_automatic_mode(client, test_session_factory, monkeypatch, edition, die):
    sid, pc = await _initiative_setup(client, test_session_factory, conditions={"invisible": True}, edition=edition)
    monkeypatch.setattr(random, "randint", lambda a, b: 17)
    as_user(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{pc['id']}/initiative", json={"die": 3})
    assert r.status_code == 200, r.text
    enc = r.json()
    row = next(c for c in enc["combatants"] if c["id"] == pc["id"])
    assert row["initiative_die"] == die
    assert enc["initiative_roll"]["mode_applied"] == ("advantage" if edition == "2024" else "normal")
    assert enc["initiative_roll"]["notes"] == (["condition:invisible"] if edition == "2024" else [])


async def test_exhaustion_2024_lowers_initiative_total(client, test_session_factory):
    sid, pc = await _initiative_setup(client, test_session_factory, conditions={"exhaustion": 2}, edition="2024")
    as_user(PLAYER_ID)
    enc = (await client.post(f"/sessions/{sid}/encounter/combatants/{pc['id']}/initiative", json={"die": 10})).json()
    row = next(c for c in enc["combatants"] if c["id"] == pc["id"])
    assert row["initiative"] == 10 + pc["initiative_mod"] - 4


async def test_auto_rolled_initiative_applies_conditions_to_pcs(client, test_session_factory, monkeypatch):
    sid, pc = await _initiative_setup(client, test_session_factory, conditions={"exhaustion": 2}, edition="2024")
    monkeypatch.setattr(random, "randint", lambda a, b: 10)
    r = await client.post(f"/sessions/{sid}/encounter/start", json={"auto_roll_missing": True})
    assert r.status_code == 200, r.text
    row = next(c for c in r.json()["combatants"] if c["id"] == pc["id"])
    assert row["initiative"] == 10 + pc["initiative_mod"] - 4


# --- Valori derivati -------------------------------------------------------------------------------------------------

async def test_passive_plus_minus_five(client):
    cid = await _char(client)
    clean = (await client.get(f"/characters/{cid}")).json()
    assert clean["computed"]["hp_max_effective"] == clean["hit_points"]
    poisoned = await _cond(client, cid, poisoned=True)
    assert poisoned["passives"]["perception"] == clean["passives"]["perception"] - 5
    assert poisoned["passives"]["insight"] == clean["passives"]["insight"] - 5
    # il bonus di abilità mostrato non cambia: il ±5 vale solo per la passiva
    assert poisoned["skill_bonuses"]["perception"] == clean["skill_bonuses"]["perception"]


async def test_homebrew_modifiers_sum_next_to_rule_modifiers(client):
    cid = await _char(client, edition="2024")
    clean = (await client.get(f"/characters/{cid}")).json()
    await _passive_rule(client, cid, "character.skill.stealth", 3)
    await _passive_rule(client, cid, "character.speed", 10)
    await _passive_rule(client, cid, "character.initiative", 2)
    await _passive_rule(client, cid, "character.saving_throw.wisdom", 1)
    await _passive_rule(client, cid, "character.passive.perception", 1)
    full = await _cond(client, cid, exhaustion=1)
    assert full["skill_bonuses"]["stealth"] == clean["skill_bonuses"]["stealth"] + 3 - 2
    assert full["computed"]["speed"] == clean["computed"]["speed"] + 10 - 5
    assert full["initiative_bonus"] == clean["initiative_bonus"] + 2 - 2
    assert full["passives"]["perception"] == clean["passives"]["perception"] + 1 - 2
    assert full["speed_homebrew_modifier"] == 10 and full["skills_homebrew_modifiers"]["stealth"] == 3
    roll = (await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 10})).json()
    assert roll["bonus"] == full["skill_bonuses"]["stealth"]
    save = (await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": 10})).json()
    assert save["bonus"] == 0 + 1 - 2  # SAG 10 senza competenza, homebrew +1, esaurimento -2
    assert full["saves_homebrew_modifiers"]["wisdom"] == 1 and full["computed"]["save_flat"]["wisdom"] == -2


async def test_homebrew_hp_bonus_is_halved_with_the_base_by_exhaustion_2014(client):
    cid = await _char(client)
    await _set_hp(client, cid, 40)
    await _passive_rule(client, cid, "character.hit_points_max", 10)
    full = (await client.get(f"/characters/{cid}")).json()
    assert full["computed"]["hp_max_effective"] == 50
    full = await _cond(client, cid, exhaustion=4)
    assert full["computed"]["hp_max_effective"] == 25
    assert full["hp_max_homebrew_modifier"] == 10 and full["hit_points"] == 40
    assert full["current_hit_points"] == 25


async def test_exhaustion_hp_max_caps_heal_and_long_rest_restores_after_reduction(client):
    cid = await _char(client)
    await _set_hp(client, cid, 40)
    full = await _cond(client, cid, exhaustion=4)
    assert full["computed"]["hp_max_effective"] == 20 and full["current_hit_points"] == 20
    assert full["hit_points"] == 40  # il valore salvato non si tocca
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "heal", "value": 50})
    assert r.json()["current_hit_points"] == 20
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 35})
    assert r.json()["current_hit_points"] == 20
    prev = (await client.get(f"/characters/{cid}/rest/preview", params={"rest_type": "long"})).json()
    assert prev["hp_gain"] == 20  # il riposo porta a 3 livelli: il massimo torna 40
    full = (await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})).json()
    assert full["conditions"]["exhaustion"] == 3 and full["current_hit_points"] == 40


async def test_massive_damage_uses_the_halved_maximum(client):
    cid = await _char(client)
    await _set_hp(client, cid, 40)
    await _cond(client, cid, exhaustion=4)  # massimo 20, PF 20
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 40})
    assert r.json()["is_dead"] is True


async def test_exhaustion_six_kills_and_revive_leaves_five(client):
    cid = await _char(client, edition="2024")
    full = await _cond(client, cid, exhaustion=6)
    assert full["is_dead"] is True
    r = await client.post(f"/characters/{cid}/revive")
    assert r.json()["is_dead"] is False and r.json()["conditions"]["exhaustion"] == 5


async def test_speed_zero_and_ac_in_computed_with_encumbrance_untouched(client):
    cid = await _char(client)
    clean = (await client.get(f"/characters/{cid}")).json()
    assert clean["computed"]["speed"] == clean["speed"] and clean["computed"]["incapacitated"] is False
    full = await _cond(client, cid, grappled=True)
    assert full["computed"]["speed"] == 0 and full["speed"] == clean["speed"]
    full = await _cond(client, cid, grappled=False, stunned=True)
    assert full["computed"]["incapacitated"] is True


async def test_petrified_halves_damage_without_writing_damage_modifiers(client):
    cid = await _char(client)
    await _set_hp(client, cid, 40)
    before = (await client.get(f"/characters/{cid}")).json()["damage_modifiers"]
    await _cond(client, cid, petrified=True)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "fire"})
    assert r.json()["current_hit_points"] == 35
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 11})
    assert r.json()["current_hit_points"] == 30  # senza tipo, per difetto
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 20, "damage_type": "poison"})
    assert r.json()["current_hit_points"] == 30  # 2014: immune al veleno
    body = r.json()
    assert body["damage_modifiers"] == before
    assert "all" in body["computed"]["resistances"] and "poison" in body["computed"]["immunities"]
    # la scelta esplicita dell'utente continua a vincere
    r = await client.patch(f"/characters/{cid}/hp", json={
        "op": "damage", "value": 4, "damage_modifier": "none", "raw_value": 4, "damage_type": "fire"})
    assert r.json()["current_hit_points"] == 26


# --- Concentrazione ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("edition", ["2014", "2024"])
@pytest.mark.parametrize("cond", ["incapacitated", "stunned", "paralyzed", "petrified", "unconscious"])
async def test_incapacitated_ends_concentration(client, edition, cond):
    cid = await _char(client, edition=edition, cls="wizard")
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Fiamma", "level": 0, "is_concentration": True})
    sid = r.json()["id"]
    r = await client.patch(f"/characters/{cid}/concentration", json={"spell_id": sid})
    assert r.json()["concentrating_spell_id"] == sid
    # una condizione che non incapacita non la rompe
    assert (await _cond(client, cid, poisoned=True))["concentrating_spell_id"] == sid
    assert (await _cond(client, cid, **{cond: True}))["concentrating_spell_id"] is None


async def test_conditions_already_on_do_not_end_a_later_concentration(client):
    cid = await _char(client, cls="wizard")
    await _cond(client, cid, stunned=True)
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Fiamma", "level": 0, "is_concentration": True})
    sid = r.json()["id"]
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": sid})
    # la webapp rimanda tutta la mappa delle condizioni a ogni modifica
    full = await _cond(client, cid, stunned=True, poisoned=True)
    assert full["concentrating_spell_id"] == sid


# --- Armatura e modificatori dei privilegi ----------------------------------------------------------------------------

async def test_untrained_armor_penalty_end_to_end(client):
    cid = await _char(client, cls="wizard")
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Piastre", "item_type": "armor", "is_equipped": True,
        "item_metadata": {"armor_type": "heavy", "ac_value": 18}})
    assert r.status_code == 201, r.text
    full = (await client.get(f"/characters/{cid}")).json()
    assert any(i["name"] == "Piastre" and i["is_equipped"] for i in full["items"])
    body = (await client.post(f"/characters/{cid}/saving_throws/dexterity/roll")).json()
    assert body["mode_applied"] == "disadvantage" and body["notes"] == ["armor:untrained"]
    body = (await client.post(f"/characters/{cid}/saving_throws/wisdom/roll")).json()
    assert body["mode_applied"] == "normal"


async def test_untrained_shield_2024_removes_ac_in_response(client, test_session_factory):
    cid = await _char(client, edition="2024", cls="wizard")
    clean = (await client.get(f"/characters/{cid}")).json()
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Scudo", "item_type": "shield", "is_equipped": True, "item_metadata": {"ac_bonus": 2}})
    assert r.status_code == 201, r.text
    async with test_session_factory() as s:
        (await s.get(Character, cid)).shield_armor_class = 2
        await s.commit()
    full = (await client.get(f"/characters/{cid}")).json()
    assert full["shield_armor_class"] == 2
    assert full["ac"] == clean["ac"]
    assert full["ac_breakdown"]["rules"] == -2


async def test_feature_modifiers_reach_rolls_and_derived_values(client, rules_catalog):
    rules_catalog(_spec(
        Modifier("attack", 1), Modifier("damage", 2),
        Modifier("speed", 10), Modifier("hp_max", 5), Modifier("save", 1), Modifier("ac", 1),
        Modifier("crit_min", 19), Modifier("advantage", 1, when=lambda ctx: ctx.skill == "stealth"),
        Modifier("min_d20", 10, when=lambda ctx: ctx.skill == "arcana"),
    ))
    cid = await _char(client)
    await _set_hp(client, cid, 20)
    weapon = await _weapon(client, cid)
    full = (await client.get(f"/characters/{cid}")).json()
    assert full["computed"]["speed"] == full["speed"] + 10
    assert full["computed"]["hp_max_effective"] == 25
    assert full["computed"]["save_flat"]["strength"] == 1
    assert full["ac_breakdown"]["rules"] == 1
    attack = (await client.post(f"/characters/{cid}/items/{weapon}/attack", json={"die": 19})).json()
    assert attack["is_critical"] is True and attack["notes"] == ["feature:fighter.prova"]
    assert len(attack["damage_rolls"]) == 2
    assert attack["damage_bonus"] == 2  # FOR 10: solo il modificatore del privilegio
    stealth = (await client.post(f"/characters/{cid}/skills/stealth/roll")).json()
    assert stealth["mode_applied"] == "advantage"
    arcana = (await client.post(f"/characters/{cid}/skills/arcana/roll", json={"die": 2})).json()
    assert arcana["die"] == 10


async def test_exhaustion_history_row_for_death(client, test_session_factory):
    cid = await _char(client)
    await _cond(client, cid, exhaustion=6)
    async with test_session_factory() as s:
        rows = (await s.execute(select(CharacterHistory.description).where(
            CharacterHistory.character_id == cid, CharacterHistory.event_type == "death_save"))).scalars().all()
    assert any("Morto" in r for r in rows)


async def test_homebrew_heal_on_a_character_without_relations_loaded_respects_the_halved_maximum(client):
    cid = await _char(client)
    await _set_hp(client, cid, 40, 5)
    r = await client.post(f"/characters/{cid}/homebrew/rules", json={
        "name": "Rigenera", "enabled": True,
        "dsl": {"version": 1, "subject": {"type": "character"}, "passive_modifiers": [], "triggers": [
            {"event": "turn_started", "effects": [{"action": "heal_character", "amount": 50}]}]},
    })
    assert r.status_code in (200, 201), r.text
    await _cond(client, cid, exhaustion=4)
    r = await client.post(f"/characters/{cid}/homebrew/turn-start")
    assert r.status_code == 200, r.text
    assert (await client.get(f"/characters/{cid}")).json()["current_hit_points"] == 20


# --- Rilievi di revisione: fallimento automatico ------------------------------------------------------------------------

async def test_auto_fail_is_never_critical(client):
    cid = await _char(client)
    await _cond(client, cid, stunned=True)
    body = (await client.post(f"/characters/{cid}/saving_throws/dexterity/roll", json={"die": 20})).json()
    assert body["auto_fail"] is True and body["is_critical"] is False
    body = (await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": 20})).json()
    assert body["is_critical"] is True


async def test_pending_save_keeps_the_reason_of_an_auto_fail(client, test_session_factory):
    from api.services.condition_effects import SaveSpec, upsert_effect
    from core.db.models import PendingSave
    cid = await _char(client)
    await _cond(client, cid, stunned=True)
    async with test_session_factory() as s:
        eff = await upsert_effect(s, ("character", cid), "stunned", save=SaveSpec("dexterity", 10, "end"))
        ps = PendingSave(effect_id=eff.id, character_id=cid, ability="dexterity", dc=10, status="pending",
                         created_at="2026-11-04T00:00:00")
        s.add(ps)
        await s.commit()
        psid = ps.id
    body = (await client.post(f"/characters/{cid}/pending-saves/{psid}/roll", json={"die": 20})).json()
    assert body["roll"]["is_critical"] is False
    async with test_session_factory() as s:
        last = (await s.get(PendingSave, psid)).last_roll
    assert last["auto_fail"] is True and "condition:stunned" in last["notes"]


# --- Rilievi di revisione: PF correnti e massimo dimezzato ----------------------------------------------------------------

async def _halved(client, cid) -> dict:
    await _set_hp(client, cid, 40)
    full = await _cond(client, cid, exhaustion=4)
    assert full["computed"]["hp_max_effective"] == 20 and full["current_hit_points"] == 20
    return full


async def _con_item(client, cid, value=8) -> int:
    meta = {"ability_modifiers": [{"ability": "constitution", "kind": "relative", "value": value}]}
    r = await client.post(f"/characters/{cid}/items", json={"name": "Amuleto", "item_type": "accessory", "item_metadata": meta})
    assert r.status_code == 201, r.text
    return next(i["id"] for i in r.json()["items"] if i["name"] == "Amuleto")


def _within_max(full: dict) -> None:
    assert full["current_hit_points"] <= full["computed"]["hp_max_effective"]


async def test_equipping_con_item_stays_within_the_halved_maximum_and_heal_never_lowers(client):
    cid = await _char(client, level=5)
    await _halved(client, cid)
    item = await _con_item(client, cid)
    r = await client.patch(f"/characters/{cid}/items/{item}", json={"is_equipped": True})
    assert r.status_code == 200, r.text
    full = r.json()
    assert full["hit_points"] == 60  # il massimo reale segue la COS: +4 per 5 livelli
    assert full["computed"]["hp_max_effective"] == 30
    _within_max(full)
    before = full["current_hit_points"]
    healed = (await client.patch(f"/characters/{cid}/hp", json={"op": "heal", "value": 1})).json()
    assert healed["current_hit_points"] >= before
    _within_max(healed)
    # tolta la spossatezza il massimo torna integro
    back = await _cond(client, cid, exhaustion=0)
    assert back["computed"]["hp_max_effective"] == 60 and back["hit_points"] == 60


async def test_constitution_change_stays_within_the_halved_maximum(client):
    cid = await _char(client, level=5)
    await _halved(client, cid)
    r = await client.patch(f"/characters/{cid}/ability_scores/constitution", json={"value": 20})
    assert r.status_code == 200, r.text
    full = (await client.get(f"/characters/{cid}")).json()
    assert full["hit_points"] == 65  # +5 per 5 livelli
    _within_max(full)


async def test_set_max_and_recalc_stay_within_the_halved_maximum(client):
    cid = await _char(client, level=3)
    await _halved(client, cid)
    full = (await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 24})).json()
    assert full["hit_points"] == 24 and full["current_hit_points"] == 12
    # il ricalcolo alza il massimo reale sommando il delta ai correnti
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 4})
    full = (await client.post(f"/characters/{cid}/hp/recalc")).json()
    assert full["hit_points"] > 4
    _within_max(full)


async def test_hp_undo_stays_within_the_halved_maximum(client):
    cid = await _char(client)
    await _set_hp(client, cid, 40)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 1})
    undo_id = r.json()["hp_undo_id"]
    await _cond(client, cid, exhaustion=4)
    # i PF sono scesi a 20: l'annullamento non si applica più, oppure resta nel massimo
    r = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": undo_id})
    assert r.status_code in (200, 409)
    _within_max((await client.get(f"/characters/{cid}")).json())


async def test_homebrew_max_hp_action_stays_within_the_halved_maximum(client, test_session_factory):
    from api.services.homebrew import actions
    from api.services.homebrew.actions import RuleFiringResult
    from sqlalchemy.orm import selectinload
    cid = await _char(client)
    await _halved(client, cid)
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).options(
            selectinload(Character.classes), selectinload(Character.items)).where(Character.id == cid))).scalar_one()
        char.current_hit_points = 25  # come dopo un altro percorso: l'azione riporta nel massimo
        await actions.execute_apply_modifier_once(
            {"action": "apply_modifier_once", "target": "character.hit_points_max", "delta": 2, "label": "x"},
            None, RuleFiringResult(rule_id=1, rule_name="x"), s, char)
        await s.commit()
    full = (await client.get(f"/characters/{cid}")).json()
    assert full["hit_points"] == 42 and full["computed"]["hp_max_effective"] == 21
    assert full["current_hit_points"] == 21


# --- Rilievi di revisione: iniziativa fuori dall'incontro -----------------------------------------------------------------

async def test_character_initiative_uses_mode_and_the_sheet_bonus(client):
    cid = await _char(client, edition="2024")
    await _passive_rule(client, cid, "character.initiative", 2)
    full = await _cond(client, cid, poisoned=True, exhaustion=1)
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 15})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["bonus"] == full["initiative_bonus"] == 0  # DES 10, homebrew +2, esaurimento -2
    assert body["mode_applied"] == "disadvantage" and len(body["dice"]) == 2 and body["dice"][0] == 15
    assert body["total"] == body["die"] + body["bonus"]
    assert set(body["notes"]) == {"condition:poisoned", "condition:exhaustion"}


async def test_character_initiative_player_mode_cancels_and_history_is_kept(client):
    cid = await _char(client)
    await _cond(client, cid, poisoned=True)
    body = (await client.post(f"/characters/{cid}/dice/initiative",
                              json={"mode": "advantage", "dice": [4, 18], "label": "Iniziativa"})).json()
    assert body["mode_applied"] == "normal" and body["die"] == 4
    history = (await client.get(f"/characters/{cid}/dice/history")).json()
    assert history[-1]["source"] == "init" and history[-1]["label"] == "Iniziativa"
    assert history[-1]["total"] == body["total"]


async def test_character_initiative_without_body_rolls_on_the_server(client):
    cid = await _char(client)
    body = (await client.post(f"/characters/{cid}/dice/initiative")).json()
    assert body["mode_applied"] == "normal" and len(body["dice"]) == 1


async def test_xp_level_up_stays_within_the_halved_maximum(client):
    cid = await _char(client)
    await _halved(client, cid)
    r = await client.patch(f"/characters/{cid}/xp", json={"add": 900})
    assert r.status_code == 200, r.text
    full = r.json()
    assert full["hit_points"] > 40
    _within_max(full)
