"""Competenze per categoria (R6.6) e aspetto in personality (R6.7)."""
from __future__ import annotations

from sqlalchemy import select

from core.db.models import Character
from tests.integration.conftest import TEST_USER_ID
from tests.integration.test_character_export import _make_char
from tests.integration.test_weapon_options import _attack, _char, _weapon

EMPTY = {"armor": [], "weapons": [], "tools": [], "other": []}


async def test_legacy_proficiency_list_read_as_other(client, test_session_factory):
    cid = await _make_char(test_session_factory)
    async with test_session_factory() as s:
        c = (await s.execute(select(Character).where(Character.id == cid))).scalar_one()
        c.general_proficiencies = ["Liuto", "Armi semplici"]
        await s.commit()
    r = await client.get(f"/characters/{cid}")
    assert r.json()["general_proficiencies"] == {**EMPTY, "other": ["Liuto", "Armi semplici"]}


async def test_empty_proficiencies_read_as_empty_categories(client):
    cid = (await client.post("/characters", json={"name": "Vuoto"})).json()["id"]
    r = await client.get(f"/characters/{cid}")
    assert r.json()["general_proficiencies"] == EMPTY


async def test_categories_roundtrip(client):
    cid = (await client.post("/characters", json={"name": "Cat"})).json()["id"]
    body = {"armor": ["Scudi"], "weapons": ["Armi semplici"], "tools": ["Liuto"], "other": []}
    r = await client.patch(f"/characters/{cid}", json={"general_proficiencies": body})
    assert r.status_code == 200, r.text
    assert r.json()["general_proficiencies"] == body
    assert (await client.get(f"/characters/{cid}")).json()["general_proficiencies"] == body


async def test_patch_legacy_list_is_stored_as_categories(client):
    cid = (await client.post("/characters", json={"name": "Old"})).json()["id"]
    r = await client.patch(f"/characters/{cid}", json={"general_proficiencies": ["Liuto"]})
    assert r.json()["general_proficiencies"] == {**EMPTY, "other": ["Liuto"]}


async def test_unknown_category_rejected(client):
    cid = (await client.post("/characters", json={"name": "Bad"})).json()["id"]
    r = await client.patch(f"/characters/{cid}", json={"general_proficiencies": {"x": ["a"]}})
    assert r.status_code == 422


async def test_appearance_saved_in_personality_without_losing_traits(client):
    cid = (await client.post("/characters", json={"name": "Asp"})).json()["id"]
    traits = {"traits": "Coraggioso", "ideals": "Giustizia", "bonds": "Famiglia", "flaws": "Orgoglio"}
    await client.patch(f"/characters/{cid}", json={"personality": traits})
    full = (await client.get(f"/characters/{cid}")).json()["personality"]
    app = {"age": "27", "height": "180 cm", "weight": "80 kg", "eyes": "verdi", "hair": "neri", "skin": "olivastra"}
    r = await client.patch(f"/characters/{cid}", json={"personality": {**full, **app}})
    assert r.status_code == 200, r.text
    assert r.json()["personality"] == {**traits, **app}


async def test_weapon_warning_reads_weapons_category(client):
    cid = await _char(client)
    wid = await _weapon(client, cid, name="Spadone", weapon_category="martial")
    await client.patch(
        f"/characters/{cid}",
        json={"general_proficiencies": {"weapons": ["Armi semplici"]}},
    )
    warned = await _attack(client, cid, wid)
    await client.patch(
        f"/characters/{cid}",
        json={"general_proficiencies": {"weapons": ["Armi da guerra"]}},
    )
    ok = await _attack(client, cid, wid)
    assert warned.status_code == ok.status_code == 200
    assert warned.json() != ok.json() or "proficien" in str(warned.json()).lower()


def test_lacks_weapon_proficiency_accepts_categories_and_legacy_other():
    from api.routers.items import _lacks_weapon_proficiency as lacks

    class C:
        general_proficiencies = None

    c = C()
    c.general_proficiencies = {"weapons": ["Armi da guerra"]}
    assert not lacks(c, "Spadone", "martial")
    assert lacks(c, "Pugnale", "simple")
    c.general_proficiencies = {"other": ["Armi semplici"]}
    assert not lacks(c, "Pugnale", "simple")
    c.general_proficiencies = ["Armi semplici"]
    assert not lacks(c, "Pugnale", "simple")
    c.general_proficiencies = {}
    assert not lacks(c, "Pugnale", "simple")


async def test_import_accepts_legacy_list_and_object(client, test_session_factory):
    from tests.integration.test_character_import import _export, _import, _make_valid

    cid = await _make_valid(test_session_factory)
    data = await _export(client, cid)
    data["character"]["general_proficiencies"] = ["Liuto"]
    r = await _import(client, data)
    assert r.status_code == 201, r.text
    assert r.json()["general_proficiencies"] == {**EMPTY, "other": ["Liuto"]}
    obj = {**EMPTY, "tools": ["Liuto"]}
    data["character"]["general_proficiencies"] = obj
    r = await _import(client, data)
    assert r.status_code == 201, r.text
    assert r.json()["general_proficiencies"] == obj
