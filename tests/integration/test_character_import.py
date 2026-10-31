from __future__ import annotations

import json

from sqlalchemy import select

from core.db.models import Character, Item
from tests.integration.conftest import TEST_USER_ID
from tests.integration.test_character_export import _make_char
from core.db.models import HomebrewRule

VALID_DSL = {
    "version": 1,
    "subject": {"type": "character"},
    "passive_modifiers": [{
        "when": {"path": "$character.id", "op": "gt", "value": 0},
        "target": "character.ac", "value": 1, "label_i18n": {"it": "x", "en": "x"},
    }],
}


async def _make_valid(factory, user_id=TEST_USER_ID) -> int:
    """Come _make_char, ma con una DSL homebrew valida (l'import la rivalida)."""
    cid = await _make_char(factory, user_id)
    async with factory() as s:
        rule = (await s.execute(select(HomebrewRule).where(HomebrewRule.character_id == cid))).scalar_one()
        rule.dsl, rule.version = VALID_DSL, 2
        await s.commit()
    return cid


async def _export(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}/export")).json()


async def _import(client, payload: dict):
    return await client.post("/characters/import", json=payload)


def _norm(d: dict) -> dict:
    d = json.loads(json.dumps(d))
    d.pop("exported_at")
    d["character"].pop("name")
    return d


async def test_import_roundtrip_equals_export(client, test_session_factory):
    cid = await _make_valid(test_session_factory)
    first = await _export(client, cid)
    r = await _import(client, first)
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "Élan Test (importato)"
    second = await _export(client, r.json()["id"])
    assert _norm(first) == _norm(second)
    assert r.json()["id"] != cid


async def test_import_remaps_equipped_and_concentration(client, test_session_factory):
    cid = await _make_valid(test_session_factory)
    r = await _import(client, await _export(client, cid))
    new = r.json()
    assert new["concentrating_spell_id"] is not None
    spell = next(s for s in new["spells"] if s["id"] == new["concentrating_spell_id"])
    assert spell["name"] == "Bless"
    sword = next(i for i in new["items"] if i["name"] == "Sword")
    assert sword["is_equipped"] and sword["equipment_slot"] == "main_hand"
    feat = next(a for a in new["abilities"] if a["name"] == "Arcane Recovery")
    assert next(c for c in new["classes"] if c["id"] == feat["source_class_id"])["class_name"] == "warlock"


async def test_import_duplicate_slot_keeps_first(client, test_session_factory):
    cid = await _make_valid(test_session_factory)
    d = await _export(client, cid)
    d["items"].append({"name": "Axe", "is_equipped": True, "equipment_slot": "main_hand"})
    new = (await _import(client, d)).json()
    axe = next(i for i in new["items"] if i["name"] == "Axe")
    assert not axe["is_equipped"] and axe["equipment_slot"] is None


async def test_duplicate_creates_copy_with_suffix(client, test_session_factory):
    cid = await _make_valid(test_session_factory)
    r = await client.post(f"/characters/{cid}/duplicate")
    assert r.status_code == 201
    assert r.json()["name"] == "Élan Test (copia)"
    assert r.json()["id"] != cid
    other = await _make_valid(test_session_factory, user_id=999)
    assert (await client.post(f"/characters/{other}/duplicate")).status_code == 403


async def test_import_no_suffix_when_name_free(client):
    d = {"exported_at": "x", "character": {"name": "Solo"}}
    assert (await _import(client, d)).json()["name"] == "Solo"


async def test_import_multipart_file(client):
    d = {"exported_at": "x", "character": {"name": "Upl"}}
    r = await client.post("/characters/import", files={"file": ("c.json", json.dumps(d), "application/json")})
    assert r.status_code == 201 and r.json()["name"] == "Upl"


async def test_import_rejects_unknown_format_version(client, test_session_factory):
    d = await _export(client, await _make_valid(test_session_factory))
    d["format_version"] = 99
    assert (await _import(client, d)).status_code == 422


async def test_import_rejects_oversize(client):
    d = {"exported_at": "x", "character": {"name": "Big", "personality": {"a": "x" * 1_100_000}}}
    assert (await _import(client, d)).status_code == 413


async def test_import_rejects_too_many_items(client):
    d = {"exported_at": "x", "character": {"name": "M"}, "items": [{"name": "i"}] * 501}
    assert (await _import(client, d)).status_code == 422


async def test_import_rejects_invalid_dsl(client):
    d = {"exported_at": "x", "character": {"name": "D"}, "homebrew_rules": [{"name": "r", "dsl": {"a": 1}}]}
    assert (await _import(client, d)).status_code == 422


async def test_import_accepts_valid_dsl_and_version(client):
    d = {"exported_at": "x", "character": {"name": "D"},
         "homebrew_rules": [{"name": "r", "dsl": VALID_DSL, "version": 3}]}
    r = await _import(client, d)
    assert r.status_code == 201, r.text


async def test_import_rejects_negative_values(client):
    base = {"exported_at": "x", "character": {"name": "N"}}
    assert (await _import(client, {**base, "character": {"name": "N", "hit_points": -5}})).status_code == 422
    for v in (0, 31):
        d = {**base, "ability_scores": [{"name": "strength", "value": v}]}
        assert (await _import(client, d)).status_code == 422


async def test_import_ignores_foreign_ids(client, test_session_factory):
    other = await _make_valid(test_session_factory, user_id=999)
    d = await _export(client, await _make_valid(test_session_factory))
    d["character"].update(id=other, user_id=999)
    d["items"][0].update(id=1, character_id=other)
    new = (await _import(client, d)).json()
    async with test_session_factory() as s:
        assert (await s.get(Character, new["id"])).user_id == TEST_USER_ID
        assert (await s.get(Character, other)).user_id == 999
        rows = (await s.execute(select(Item).where(Item.character_id == other))).scalars().all()
        assert len(rows) == 2  # untouched
