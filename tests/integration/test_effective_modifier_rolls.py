"""Tiri di abilità, tiri salvezza, concentrazione e dadi vita usano gli stessi
numeri della scheda: modificatore effettivo (bonus degli oggetti equipaggiati),
competenza e modificatori passivi homebrew."""
from __future__ import annotations

import random


async def _setup(client) -> int:
    """Guerriero liv. 2 (PB +2, competente in TS FOR e COS), FOR 14 + guanti FOR +4, COS 12."""
    r = await client.post("/characters", json={"name": "Coerente"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.post(
        f"/characters/{cid}/classes",
        json={"class_name": "fighter", "level": 2, "hit_die": 10},
    )
    assert r.status_code == 201, r.text
    for ability, value in (("strength", 14), ("constitution", 12)):
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    meta = {"ability_modifiers": [{"ability": "strength", "kind": "relative", "value": 4}]}
    r = await client.post(
        f"/characters/{cid}/items",
        json={"name": "Guanti", "item_type": "accessory", "item_metadata": meta},
    )
    assert r.status_code == 201, r.text
    items = (await client.get(f"/characters/{cid}/items")).json()
    gid = next(i["id"] for i in items if i["name"] == "Guanti")
    r = await client.patch(f"/characters/{cid}/items/{gid}", json={"is_equipped": True})
    assert r.status_code == 200, r.text
    return cid


async def _add_passive_rule(client, cid: int, target: str, value: int) -> None:
    body = {
        "name": target,
        "enabled": True,
        "dsl": {
            "version": 1,
            "subject": {"type": "character"},
            "passive_modifiers": [{
                "when": {"path": "$character.id", "op": "gt", "value": 0},
                "target": target,
                "value": value,
                "label_i18n": {"it": target, "en": target},
            }],
            "triggers": [],
        },
    }
    r = await client.post(f"/characters/{cid}/homebrew/rules", json=body)
    assert r.status_code in (200, 201), r.text


async def test_skill_roll_uses_item_bonus_and_homebrew(client):
    cid = await _setup(client)
    await _add_passive_rule(client, cid, "character.skill.athletics", 1)
    r = await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 10})
    assert r.status_code == 200, r.text
    assert r.json()["bonus"] == 5  # FOR effettiva 18 (+4) + homebrew +1, non competente


async def test_saving_throw_roll_uses_item_bonus_and_homebrew(client):
    cid = await _setup(client)
    await _add_passive_rule(client, cid, "character.saving_throw.strength", 2)
    r = await client.post(f"/characters/{cid}/saving_throws/strength/roll", json={"die": 10})
    assert r.status_code == 200, r.text
    assert r.json()["bonus"] == 8  # +4 FOR effettiva, +2 competenza, +2 homebrew


async def test_concentration_adds_con_save_proficiency(client, monkeypatch):
    cid = await _setup(client)
    monkeypatch.setattr(random, "randint", lambda a, b: 8)
    r = await client.post(f"/characters/{cid}/concentration/save", json={"damage": 4})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["bonus"] == 3  # COS 12 (+1) + competenza TS COS +2
    assert body["total"] == 11
    assert body["success"] is True  # 11 >= CD 10


async def test_hit_dice_use_effective_con(client):
    cid = await _setup(client)
    meta = {"ability_modifiers": [{"ability": "constitution", "kind": "absolute", "value": 19}]}
    r = await client.post(
        f"/characters/{cid}/items",
        json={"name": "Amuleto della salute", "item_type": "accessory", "item_metadata": meta},
    )
    assert r.status_code == 201, r.text
    items = (await client.get(f"/characters/{cid}/items")).json()
    aid = next(i["id"] for i in items if i["name"] == "Amuleto della salute")
    r = await client.patch(f"/characters/{cid}/items/{aid}", json={"is_equipped": True})
    assert r.status_code == 200, r.text
    class_id = r.json()["classes"][0]["id"]

    r = await client.post(
        f"/characters/{cid}/hit_dice/spend",
        json={"class_id": class_id, "count": 1, "rolls": [3]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["con_bonus"] == 4  # COS effettiva 19, non la base 12
