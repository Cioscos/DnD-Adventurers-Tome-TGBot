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


async def test_import_restores_ability_action_type(client, test_session_factory):
    cid = await _make_valid(test_session_factory)
    data = await _export(client, cid)
    feat = next(a for a in data["abilities"] if a["name"] == "Arcane Recovery")
    assert feat["action_type"] == "special"
    r = await _import(client, data)
    assert r.status_code == 201, r.text
    imported = (await client.get(f"/characters/{r.json()['id']}/abilities")).json()
    assert next(a for a in imported if a["name"] == "Arcane Recovery")["action_type"] == "special"
    assert next(a for a in imported if a["name"] == "Manual")["action_type"] is None


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


async def test_export_and_duplicate_survive_out_of_range_legacy_data(client, test_session_factory):
    from core.db.models import CharacterClass, Spell
    cid = await _make_valid(test_session_factory)
    async with test_session_factory() as s:
        cls = (await s.execute(select(CharacterClass).where(CharacterClass.character_id == cid))).scalars().first()
        cls.level = 25
        item = (await s.execute(select(Item).where(Item.character_id == cid))).scalars().first()
        item.quantity = -1
        spell = (await s.execute(select(Spell).where(Spell.character_id == cid))).scalars().first()
        spell.level = 12
        await s.commit()
    r = await client.get(f"/characters/{cid}/export")
    assert r.status_code == 200 and {c["level"] for c in r.json()["classes"]} >= {25}
    d = await client.post(f"/characters/{cid}/duplicate")
    assert d.status_code == 201, d.text
    assert 25 in {c["level"] for c in d.json()["classes"]}
    # ...ma lo stesso file ricaricato dall'esterno resta rifiutato
    assert (await _import(client, r.json())).status_code == 422


async def test_import_rejects_duplicate_unique_keys(client):
    base = {"exported_at": "x", "character": {"name": "U"}}
    bad = [
        {"classes": [{"class_name": "wizard"}, {"class_name": "wizard"}]},
        {"ability_scores": [{"name": "strength"}, {"name": "strength"}]},
        {"spell_slots": [{"level": 1}, {"level": 1}]},
        {"homebrew_rules": [{"name": "r", "dsl": VALID_DSL}],
         "homebrew_resources": [{"rule_index": 0, "key": "k", "name": "a"}, {"rule_index": 0, "key": "k", "name": "b"}]},
    ]
    for extra in bad:
        assert (await _import(client, {**base, **extra})).status_code == 422, extra
    ok = {**base, "spell_slots": [{"level": 1}, {"level": 1, "is_pact": True}]}
    assert (await _import(client, ok)).status_code == 201


async def test_unequipped_item_does_not_claim_slot(client):
    d = {"exported_at": "x", "character": {"name": "S"}, "items": [
        {"name": "Old", "equipment_slot": "head"},
        {"name": "New", "is_equipped": True, "equipment_slot": "head"}]}
    items = {i["name"]: i for i in (await _import(client, d)).json()["items"]}
    assert items["New"]["is_equipped"] and items["New"]["equipment_slot"] == "head"


async def test_import_rejects_bad_item_metadata(client, test_session_factory):
    data = await _export(client, await _make_valid(test_session_factory))
    data["items"] = [{"name": "Spada", "item_type": "weapon", "item_metadata": {"magic_bonus": "abc"}}]
    assert (await _import(client, data)).status_code == 422
    data["items"] = [{"name": "Anello", "item_metadata": {"charges": {"max": "x"}}}]
    assert (await _import(client, data)).status_code == 422


async def test_import_enforces_attunement_limit(client, test_session_factory):
    data = await _export(client, await _make_valid(test_session_factory))
    meta = {"is_magic": True, "requires_attunement": True, "attuned": True}
    data["items"] = [{"name": f"Anello {i}", "item_metadata": meta} for i in range(4)]
    r = await _import(client, data)
    assert r.status_code == 422 and r.json()["detail"] == "attunement_limit"
    data["items"] = data["items"][:3]
    assert (await _import(client, data)).status_code == 201
