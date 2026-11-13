"""Competenze per classe ed edizione: concessione alla creazione, migrazione una tantum, bonus sull'attacco."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.db.engine import _seed_proficiencies
from core.db.models import Character, CharacterClass
from core.rules.proficiencies import is_weapon_proficient
from core.rules.types import FeatureSpec
from tests.integration.test_weapon_options import _attack, _weapon

MARTIAL = type("I", (), {"name": "Spadone", "item_metadata": {"weapon_category": "martial"}})()


async def _new(client, class_name: str, **extra) -> dict:
    r = await client.post("/characters", json={"name": "Prova", "initial_class": {"class_name": class_name, **extra}})
    assert r.status_code == 201, r.text
    return r.json()


async def _add(client, cid: int, class_name: str, **extra):
    return await client.post(f"/characters/{cid}/classes", json={"class_name": class_name, **extra})


async def _run_seed(factory) -> None:
    async with factory() as s:
        await (await s.connection()).run_sync(_seed_proficiencies)
        await s.commit()


async def test_first_class_grants_saves_armor_weapons(client):
    body = await _new(client, "fighter")
    prof = body["general_proficiencies"]
    assert prof["armor"] == ["Armature leggere", "Armature medie", "Armature pesanti", "Scudi"]
    assert prof["weapons"] == ["Armi semplici", "Armi da guerra"]
    assert body["saving_throws"]["strength"] and body["saving_throws"]["constitution"]


async def test_second_class_grants_only_multiclass(client):
    cid = (await _new(client, "wizard"))["id"]
    r = await _add(client, cid, "rogue", skill_choices=["stealth"])
    assert r.status_code == 201, r.text
    body = r.json()
    prof = body["general_proficiencies"]
    assert prof["armor"] == ["Armature leggere"]
    assert body["tool_proficiencies"] == {"thieves_tools": True}
    assert "Stocco" not in prof["weapons"]  # le armi del ladro non si ottengono da seconda classe
    assert not body["saving_throws"].get("dexterity")  # i TS solo dalla prima classe
    assert body["saving_throws"]["intelligence"] is True
    assert body["skills"]["stealth"] is True


async def test_skill_choice_outside_list_or_too_many_is_rejected(client):
    cid = (await _new(client, "wizard"))["id"]
    assert (await _add(client, cid, "rogue", skill_choices=["arcana"])).status_code == 422
    assert (await _add(client, cid, "rogue", skill_choices=["stealth", "athletics"])).status_code == 422
    assert len((await client.get(f"/characters/{cid}")).json()["classes"]) == 1


async def test_domain_bonus_when_cleric_is_second_class(client, rules_catalog):  # D5
    rules_catalog(FeatureSpec(
        key="cleric.prova_dominio", class_key="cleric", edition="2014", level=1, source_title="Prova",
        name={"it": "Prova", "en": "Test"}, summary={"it": "p", "en": "t"}, action_type=None, subclass="war",
        proficiency_grants={"armor": ("heavy",), "weapons": ("martial",)},
    ))
    cid = (await _new(client, "wizard"))["id"]
    body = (await _add(client, cid, "cleric", subclass="Dominio della Guerra")).json()
    assert "Armature pesanti" in body["general_proficiencies"]["armor"]
    assert "Armi da guerra" in body["general_proficiencies"]["weapons"]
    # concessa una volta sola: se l'utente la toglie non torna a ogni sincronizzazione
    cls_id = next(c["id"] for c in body["classes"] if c["class_name"] == "cleric")
    prof = {**body["general_proficiencies"], "armor": ["Armature leggere"]}
    await client.patch(f"/characters/{cid}", json={"general_proficiencies": prof})
    r = await client.patch(f"/characters/{cid}/classes/{cls_id}", json={"level": 2})
    assert "Armature pesanti" not in r.json()["general_proficiencies"]["armor"]


async def test_existing_character_with_empty_list_keeps_pb(client, test_session_factory):
    fighter = (await _new(client, "fighter"))["id"]
    legacy = (await client.post("/characters", json={"name": "Vecchio"})).json()["id"]
    custom = (await _new(client, "Cacciatore di Taglie"))["id"]
    async with test_session_factory() as s:
        for char_id, old in ((fighter, []), (legacy, ["Liuto"]), (custom, None)):
            c = (await s.execute(select(Character).where(Character.id == char_id))).scalar_one()
            c.general_proficiencies = old  # come i personaggi creati prima delle tabelle
            c.settings = {}
        s.add(CharacterClass(character_id=legacy, class_name="Mago", level=1))
        await s.commit()
    await _run_seed(test_session_factory)
    async with test_session_factory() as s:
        chars = {c.id: c for c in (await s.execute(select(Character).options(selectinload(Character.classes)))).scalars()}
    assert is_weapon_proficient(chars[fighter], MARTIAL)
    assert chars[fighter].general_proficiencies["weapons"] == ["Armi semplici", "Armi da guerra"]
    assert chars[custom].general_proficiencies["weapons"] == ["Armi semplici", "Armi da guerra"]  # classe custom: come prima
    assert chars[legacy].general_proficiencies["other"] == ["Liuto"]  # il vecchio elenco resta
    assert not is_weapon_proficient(chars[legacy], MARTIAL)  # mago: solo le sue armi


async def test_seed_is_not_repeated(client, test_session_factory):
    cid = (await _new(client, "fighter"))["id"]
    async with test_session_factory() as s:
        c = (await s.execute(select(Character).where(Character.id == cid))).scalar_one()
        c.general_proficiencies = {"armor": [], "weapons": ["Armi semplici"], "tools": [], "other": []}
        c.settings = {**c.settings, "proficiencies_seeded": True}
        await s.commit()
    await _run_seed(test_session_factory)
    async with test_session_factory() as s:
        c = (await s.execute(select(Character).where(Character.id == cid))).scalar_one()
        assert c.general_proficiencies["weapons"] == ["Armi semplici"]


async def test_attack_without_proficiency_loses_pb(client):
    cid = (await _new(client, "wizard"))["id"]
    wid = await _weapon(client, cid, name="Spadone", weapon_category="martial")
    lacking = (await _attack(client, cid, wid)).json()
    assert lacking["proficiency_warning"] is True
    assert lacking["to_hit_bonus"] == 0  # FOR 10, il mago non ha le armi da guerra
    await client.patch(f"/characters/{cid}", json={"general_proficiencies": {"weapons": ["Armi da guerra"]}})
    ok = (await _attack(client, cid, wid)).json()
    assert ok["proficiency_warning"] is False and ok["to_hit_bonus"] == 2


async def test_item_without_category_counts_as_proficient(client):
    cid = (await _new(client, "wizard"))["id"]
    wid = await _weapon(client, cid, name="Strana")
    body = (await _attack(client, cid, wid)).json()
    assert body["proficiency_warning"] is False and body["to_hit_bonus"] == 2


async def test_rules_endpoint_returns_grant(client):
    r = await client.get("/rules/proficiencies", params={"edition": "2024", "class_key": "Ladro", "as_multiclass": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["armor"] == ["Armature leggere"] and body["skills_count"] == 1 and body["saves"] == []


async def test_custom_class_created_after_migration_keeps_pb(client):
    cid = (await _new(client, "Cacciatore di Taglie"))["id"]
    await client.patch(f"/characters/{cid}", json={"general_proficiencies": {}})
    wid = await _weapon(client, cid, name="Spadone", weapon_category="martial")
    body = (await _attack(client, cid, wid)).json()
    assert body["proficiency_warning"] is False and body["to_hit_bonus"] == 2


async def test_custom_plus_wizard_keeps_pb_on_martial_weapon(client):
    cid = (await _new(client, "wizard"))["id"]
    assert (await _add(client, cid, "Cacciatore di Taglie")).status_code == 201
    wid = await _weapon(client, cid, name="Spadone", weapon_category="martial")
    body = (await _attack(client, cid, wid)).json()
    assert body["proficiency_warning"] is False and body["to_hit_bonus"] == 2
