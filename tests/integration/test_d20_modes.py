"""Advantage/disadvantage on every d20 roll endpoint (api/services/d20.py)."""
from __future__ import annotations

import random

import pytest

from tests.integration._encounter_helpers import PLAYER_ID, as_user, seed_session


async def _char(client) -> int:
    r = await client.post(
        "/characters",
        json={
            "name": "Mago",
            "initial_class": {
                "class_name": "wizard", "level": 5, "hit_die": 6,
                "spellcasting_ability": "intelligence",
            },
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _sword(client, cid: int, dice: str = "1d8") -> int:
    meta = {"damage_dice": dice, "weapon_type": "melee", "properties": []}
    r = await client.post(
        f"/characters/{cid}/items",
        json={"name": "Spada", "item_type": "weapon", "item_metadata": meta},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _cantrip(client, cid: int) -> int:
    r = await client.post(
        f"/characters/{cid}/spells",
        json={"name": "Raggio di Gelo", "level": 0, "attack_save": "ATK"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _seq(monkeypatch, values: list[int]) -> None:
    it = iter(values)
    monkeypatch.setattr(random, "randint", lambda a, b: next(it))


async def test_skill_roll_advantage_keeps_max(client):
    cid = await _char(client)
    r = await client.post(
        f"/characters/{cid}/skills/athletics/roll", json={"mode": "advantage", "dice": [4, 17]},
    )
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["die"] == 17 and b["dice"] == [4, 17] and b["mode"] == "advantage"


async def test_save_disadvantage_keeps_min(client):
    cid = await _char(client)
    r = await client.post(
        f"/characters/{cid}/saving_throws/dexterity/roll",
        json={"mode": "disadvantage", "dice": [4, 17]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 4


async def test_attack_advantage_crit_on_kept_20(client):
    cid = await _char(client)
    wid = await _sword(client, cid)
    r = await client.post(
        f"/characters/{cid}/items/{wid}/attack", json={"mode": "advantage", "dice": [20, 3]},
    )
    b = r.json()
    assert b["to_hit_die"] == 20 and b["is_critical"] is True
    assert len(b["damage_rolls"]) == 2


async def test_attack_disadvantage_no_crit_when_other_die_20(client):
    cid = await _char(client)
    wid = await _sword(client, cid)
    r = await client.post(
        f"/characters/{cid}/items/{wid}/attack", json={"mode": "disadvantage", "dice": [20, 3]},
    )
    b = r.json()
    assert b["to_hit_die"] == 3 and b["is_critical"] is False
    assert len(b["damage_rolls"]) == 1


async def test_spell_attack_advantage(client):
    cid = await _char(client)
    sid = await _cantrip(client, cid)
    r = await client.post(
        f"/characters/{cid}/spells/{sid}/attack", json={"mode": "advantage", "dice": [9, 14]},
    )
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["to_hit_die"] == 14 and b["dice"] == [9, 14] and b["mode"] == "advantage"


async def test_death_save_advantage(client):
    cid = await _char(client)
    r = await client.post(
        f"/characters/{cid}/death_saves/roll", json={"mode": "advantage", "dice": [1, 12]},
    )
    b = r.json()
    assert b["die"] == 12 and b["outcome"] == "success"


async def test_encounter_initiative_advantage(client, test_session_factory):
    sid, _ = await seed_session(test_session_factory)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    pc = next(c for c in r.json()["combatants"] if c["kind"] == "pc")
    as_user(PLAYER_ID)
    r = await client.post(
        f"/sessions/{sid}/encounter/combatants/{pc['id']}/initiative",
        json={"mode": "advantage", "dice": [5, 15]},
    )
    assert r.status_code == 200, r.text
    got = next(c for c in r.json()["combatants"] if c["id"] == pc["id"])
    assert got["initiative"] == 15 + 3


async def test_dice_result_initiative_advantage_total_server_side(client):
    cid = await _char(client)
    r = await client.post(
        f"/characters/{cid}/dice/result",
        json={
            "rolls": [{"kind": "d20", "value": 6}, {"kind": "d20", "value": 13}],
            "mode": "advantage", "modifier": 2, "total": 999, "source": "init",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 15


async def test_dice_count_mismatch_422(client):
    cid = await _char(client)
    r = await client.post(
        f"/characters/{cid}/skills/athletics/roll", json={"mode": "advantage", "dice": [4]},
    )
    assert r.status_code == 422
    assert r.json()["detail"] == "dice_count_mismatch"


async def test_server_rolls_two_when_dice_missing(client, monkeypatch):
    cid = await _char(client)
    _seq(monkeypatch, [3, 18])
    r = await client.post(
        f"/characters/{cid}/saving_throws/wisdom/roll", json={"mode": "advantage"},
    )
    b = r.json()
    assert b["dice"] == [3, 18] and b["die"] == 18


async def test_history_mentions_both_dice(client):
    cid = await _char(client)
    await client.post(
        f"/characters/{cid}/skills/athletics/roll", json={"mode": "advantage", "dice": [4, 17]},
    )
    hist = (await client.get(f"/characters/{cid}/history")).json()
    assert any("2d20 vantaggio: 4, 17 → 17" in e["description"] for e in hist)


async def test_dice_stats_record_both(client):
    cid = await _char(client)
    await client.post(
        f"/characters/{cid}/skills/athletics/roll", json={"mode": "advantage", "dice": [4, 17]},
    )
    stats = (await client.get(f"/characters/{cid}/dice/stats")).json()["stats"]
    assert stats["d20"]["4"] == 1 and stats["d20"]["17"] == 1


async def test_war_caster_concentration_advantage(client, monkeypatch):
    cid = (await client.post("/characters", json={"name": "WC"})).json()["id"]
    for op, v in (("set_max", 30), ("set_current", 30)):
        await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": v})
    await client.patch(f"/characters/{cid}", json={"settings": {"war_caster": True}})
    await client.post(f"/characters/{cid}/spell_slots", json={"level": 1, "total": 1})
    spell = (await client.post(
        f"/characters/{cid}/spells",
        json={"name": "Bless", "level": 1, "is_concentration": True},
    )).json()["id"]
    await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 1})
    _seq(monkeypatch, [3, 18])
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 5})
    assert r.status_code == 200, r.text
    conc = r.json()["concentration_save"]
    assert conc["dice"] == [3, 18] and conc["success"] is True


@pytest.mark.parametrize("kind", ["skill", "save", "attack", "unarmed", "spell", "death", "init"])
async def test_legacy_die_field_still_accepted(client, test_session_factory, kind):
    cid = await _char(client)
    if kind == "init":
        sid, _ = await seed_session(test_session_factory)
        r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
        pc = next(c for c in r.json()["combatants"] if c["kind"] == "pc")
        as_user(PLAYER_ID)
        r = await client.post(
            f"/sessions/{sid}/encounter/combatants/{pc['id']}/initiative", json={"die": 11},
        )
        assert r.status_code == 200, r.text
        got = next(c for c in r.json()["combatants"] if c["id"] == pc["id"])
        assert got["initiative_die"] == 11
        return
    if kind == "skill":
        url = f"/characters/{cid}/skills/athletics/roll"
    elif kind == "save":
        url = f"/characters/{cid}/saving_throws/dexterity/roll"
    elif kind == "attack":
        url = f"/characters/{cid}/items/{await _sword(client, cid)}/attack"
    elif kind == "unarmed":
        url = f"/characters/{cid}/attack/unarmed"
    elif kind == "spell":
        url = f"/characters/{cid}/spells/{await _cantrip(client, cid)}/attack"
    else:
        url = f"/characters/{cid}/death_saves/roll"
    r = await client.post(url, json={"die": 11})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["die" if kind in ("skill", "save", "death") else "to_hit_die"] == 11
    assert b["mode"] == "normal" and b["dice"] == [11]
