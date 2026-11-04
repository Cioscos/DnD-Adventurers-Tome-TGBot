from sqlalchemy import select, text

from core.db.models import Character, CharacterClass
from core.db.engine import _migrate_schema
from core.rules.sample_characters import build_rules_character


async def _char(client, subclass, edition="2014"):
    r = await client.post("/characters", json={
        "name": "Sub", "initial_class": {"class_name": "Barbaro", "level": 3, "subclass": subclass}})
    cid = r.json()["id"]
    await client.patch(f"/characters/{cid}", json={"rules_edition": edition})
    return cid


async def test_catalog_endpoint(client):
    r = await client.get("/rules/subclasses", params={"edition": "2024", "class_key": "wizard"})
    assert r.status_code == 200
    assert [s["key"] for s in r.json()] == ["abjurer", "diviner", "evoker", "illusionist"]
    assert r.json()[0]["name"]["it"] == "Abiuratore" and r.json()[0]["choice_level"] == 3
    assert (await client.get("/rules/subclasses", params={"edition": "1999", "class_key": "wizard"})).status_code == 422


async def test_key_set_on_create_and_text_kept(client):
    cid = await _char(client, "Cammino del Berserker")
    cls = (await client.get(f"/characters/{cid}")).json()["classes"][0]
    assert cls["subclass_key"] == "berserker" and cls["subclass"] == "Cammino del Berserker"


async def test_unknown_subclass_text_is_preserved(client):
    cid = await _char(client, "Strano Cammino")
    cls = (await client.get(f"/characters/{cid}")).json()["classes"][0]
    assert cls["subclass"] == "Strano Cammino" and cls["subclass_key"] is None


async def test_edition_change_recomputes_key_and_keeps_text(client):
    cid = await _char(client, "Cammino del Combattente Totemico")
    chars = (await client.get(f"/characters/{cid}")).json()["classes"][0]
    assert chars["subclass_key"] == "totem_warrior"
    r = await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})
    cls = r.json()["classes"][0]
    assert cls["subclass_key"] is None and cls["subclass"] == "Cammino del Combattente Totemico"
    r = await client.patch(f"/characters/{cid}", json={"rules_edition": "2014"})
    assert r.json()["classes"][0]["subclass_key"] == "totem_warrior"


async def test_patch_class_subclass_updates_key(client):
    cid = await _char(client, None)
    cls_id = (await client.get(f"/characters/{cid}")).json()["classes"][0]["id"]
    r = await client.patch(f"/characters/{cid}/classes/{cls_id}", json={"subclass": "Path of the Berserker"})
    assert r.json()["classes"][0]["subclass_key"] == "berserker"


async def test_builder_computes_key(test_session_factory):
    async with test_session_factory() as s:
        spec = {"name": "x", "edition": "2024", "classes": [("Mago", 3, "Abiuratore", 6), ("Ladro", 1, "Ladro Acrobata", 8)]}
        char = await build_rules_character(s, spec, 1)
        rows = (await s.execute(select(CharacterClass).where(CharacterClass.character_id == char.id))).scalars()
        keys = {c.class_name: c.subclass_key for c in rows}
        assert keys == {"Mago": "abjurer", "Ladro": None}


async def test_migration_backfills_key_without_touching_text(test_session_factory):
    async with test_session_factory() as s:
        c = Character(user_id=1, name="Old", rules_edition="2014")
        s.add(c)
        await s.flush()
        s.add(CharacterClass(character_id=c.id, class_name="Mago", level=3, subclass="Scuola di Abiurazione"))
        s.add(CharacterClass(character_id=c.id, class_name="Ladro", level=3, subclass="Ladro Acrobata"))
        await s.commit()
        for _ in range(2):  # idempotente
            await s.run_sync(lambda sync: _migrate_schema(sync.connection()))
        rows = (await s.execute(text("SELECT class_name, subclass, subclass_key FROM character_classes"))).all()
        assert sorted(rows) == [("Ladro", "Ladro Acrobata", None), ("Mago", "Scuola di Abiurazione", "abjuration")]
