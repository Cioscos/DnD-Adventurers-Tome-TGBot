from __future__ import annotations

import json

import pytest

from core.db.models import (
    Ability, AbilityScore, Character, CharacterClass, Currency, EquipmentSlot,
    HomebrewResource, HomebrewRule, Item, Spell, SpellSlot,
)
from tests.integration.conftest import TEST_USER_ID


async def _make_char(factory, user_id=TEST_USER_ID) -> int:
    async with factory() as s:
        c = Character(
            user_id=user_id, name="Élan Test", race="elf", hit_points=20,
            current_hit_points=15, silhouette_path="data/silhouettes/1/x.png",
            rolls_history=[{"secret": 1}], settings={"theme": "x"},
            notes={
                "Plain": {"body": "hello", "created_at": "2026-01-01", "tags": ["a"]},
                "Legacy": "old text",
                "Voice": {"body": "[VOICE:data/voice_notes/1/abc.webm]", "tags": []},
            },
        )
        c.classes = [
            CharacterClass(class_name="wizard", level=3, hit_die=6),
            CharacterClass(class_name="warlock", level=2, hit_die=8),
        ]
        c.ability_scores = [AbilityScore(name="strength", value=12)]
        c.items = [
            Item(name="Sword", item_type="weapon", is_equipped=True,
                 equipment_slot=EquipmentSlot.MAIN_HAND, item_metadata='{"damage_dice": "1d8"}'),
            Item(name="Rope", item_metadata="not json"),
        ]
        spells = [Spell(name="Bless", level=1, is_concentration=True), Spell(name="Light", level=0)]
        c.spells = spells
        c.spell_slots = [SpellSlot(level=1, total=3, used=1), SpellSlot(level=1, total=2, is_pact=True)]
        c.currency = Currency(gold=50)
        s.add(c)
        await s.flush()
        s.add_all([
            Ability(character_id=c.id, name="Arcane Recovery", is_class_feature=True,
                    source_class_id=c.classes[1].id, feature_key="wizard.arcane_recovery"),
            Ability(character_id=c.id, name="Manual"),
        ])
        c.concentrating_spell_id = spells[0].id
        rule = HomebrewRule(character_id=c.id, name="R", enabled=True, dsl={"a": 1},
                            template_id="t", created_at="x", updated_at="x")
        s.add(rule)
        await s.flush()
        s.add(HomebrewResource(rule_id=rule.id, character_id=c.id, key="luck", name="Luck", current=1, max=3))
        await s.commit()
        return c.id


async def test_export_contains_all_sections(client, test_session_factory):
    cid = await _make_char(test_session_factory)
    r = await client.get(f"/characters/{cid}/export")
    assert r.status_code == 200
    assert 'attachment; filename="elan-test-' in r.headers["content-disposition"]
    d = r.json()
    assert d["format_version"] == 1 and d["exported_at"]
    assert d["character"]["name"] == "Élan Test"
    assert d["character"]["settings"] == {"theme": "x"}
    assert len(d["classes"]) == 2 and d["ability_scores"][0]["value"] == 12
    sword = next(i for i in d["items"] if i["name"] == "Sword")
    assert sword["equipment_slot"] == "main_hand" and sword["item_metadata"] == {"damage_dice": "1d8"}
    assert next(i for i in d["items"] if i["name"] == "Rope")["item_metadata"] == {}
    keys = {sp["export_key"]: sp["name"] for sp in d["spells"]}
    assert keys[d["concentrating_spell_key"]] == "Bless"
    assert sorted(sl["is_pact"] for sl in d["spell_slots"]) == [False, True]
    feat = next(a for a in d["abilities"] if a["name"] == "Arcane Recovery")
    assert feat["source_class_key"] == "c1"
    assert next(a for a in d["abilities"] if a["name"] == "Manual")["source_class_key"] is None
    assert d["currency"]["gold"] == 50
    notes = d["character"]["notes"]
    assert notes["Plain"]["body"] == "hello" and notes["Legacy"]["body"] == "old text"
    assert notes["Voice"]["body"] == "" and notes["Voice"]["was_voice"] is True
    assert d["homebrew_rules"][0]["dsl"] == {"a": 1}
    assert d["homebrew_resources"][0]["rule_index"] == 0
    assert d["companions"] == []


async def test_export_excludes_private_fields(client, test_session_factory):
    cid = await _make_char(test_session_factory)
    text = (await client.get(f"/characters/{cid}/export")).text
    for forbidden in ("user_id", "rolls_history", "silhouette_path", "data/voice_notes", "secret"):
        assert forbidden not in text
    assert str(TEST_USER_ID) not in json.loads(text)["character"].values()


async def test_export_other_user_403(client, test_session_factory):
    cid = await _make_char(test_session_factory, user_id=999)
    assert (await client.get(f"/characters/{cid}/export")).status_code == 403
    assert (await client.get("/characters/9999/export")).status_code == 404


async def test_export_send_503_without_token(client, test_session_factory, monkeypatch):
    cid = await _make_char(test_session_factory)
    monkeypatch.setattr("api.routers.transfer.bot_token_configured", lambda: False)
    assert (await client.post(f"/characters/{cid}/export/send")).status_code == 503


async def test_export_send_calls_send_document(client, test_session_factory, monkeypatch):
    cid = await _make_char(test_session_factory)
    calls = []

    async def fake(chat_id, filename, content, caption=None):
        calls.append((chat_id, filename, content))
        return True

    monkeypatch.setattr("api.routers.transfer.bot_token_configured", lambda: True)
    monkeypatch.setattr("api.routers.transfer.send_telegram_document", fake)
    r = await client.post(f"/characters/{cid}/export/send")
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert calls[0][0] == TEST_USER_ID and calls[0][1].endswith(".json")
    assert json.loads(calls[0][2])["format_version"] == 1

    async def fail(*a, **k):
        return False

    monkeypatch.setattr("api.routers.transfer.send_telegram_document", fail)
    assert (await client.post(f"/characters/{cid}/export/send")).status_code == 502
