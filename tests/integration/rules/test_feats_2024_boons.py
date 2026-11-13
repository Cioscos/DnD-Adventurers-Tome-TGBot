"""Doni Epici 2024 dal motore (PR 2 talenti, Task 5)."""
from __future__ import annotations

from tests.integration.rules.test_2014_bard import _full, _roll_keys
from tests.integration.rules.test_feats_2024_general import STATS
from tests.integration.rules.test_feats_2024_selection import _char
from tests.integration.rules.test_feats_take_complete import _complete, _feat_rows, _take


async def _boon(client, key: str, ability: str = "constitution", class_name: str = "fighter") -> dict:
    ch = await _char(client, class_name, 19, **STATS)
    r = await _take(client, ch["id"], f"2024_boon_{key}", ability)
    assert r.status_code == 201, r.text
    return {"before": ch, "after": r.json(), "id": ch["id"]}


async def test_fortitude_hp(client):
    b = await _boon(client, "fortitude")
    assert b["after"]["computed"]["hp_max_effective"] == b["before"]["computed"]["hp_max_effective"] + 40  # Costituzione 14 -> 15: modificatore invariato


async def test_speed_and_truesight(client):
    b = await _boon(client, "speed", "dexterity")
    assert b["after"]["computed"]["speed"] == b["before"]["computed"]["speed"] + 30
    t = await _boon(client, "truesight", "wisdom")
    assert {"type": "truesight", "range_ft": 60} in t["after"]["computed"]["senses"]


async def test_energy_resistance_choice(client):
    b = await _boon(client, "energy_resistance")
    row = _feat_rows(b["after"], "2024_boon_energy_resistance")[0]
    assert row["feat_status"] == "incomplete"
    assert (await _complete(client, b["id"], row["id"], {"damage_types": ["fire", "fire"]})).status_code == 422
    assert (await _complete(client, b["id"], row["id"], {"damage_types": ["fire", "slashing"]})).status_code == 422
    r = await _complete(client, b["id"], row["id"], {"damage_types": ["fire", "cold"]})
    assert r.status_code == 200, r.text
    assert {"fire", "cold"} <= set(r.json()["computed"]["resistances"])


async def test_fate_and_combat_prowess_options(client):
    fate = await _boon(client, "fate", "charisma")
    assert "feat.2024_boon_fate" in await _roll_keys(client, fate["id"], "save", ability="wisdom")
    row = _feat_rows(fate["after"], "2024_boon_fate")[0]
    assert (row["max_uses"], row["restoration_type"]) == (1, "short_rest")
    prowess = await _boon(client, "combat_prowess", "strength")
    assert "feat.2024_boon_combat_prowess" in await _roll_keys(client, prowess["id"], "attack")


async def test_recovery_pool(client):
    b = await _boon(client, "recovery")
    row = _feat_rows(b["after"], "2024_boon_recovery")[0]
    assert (row["max_uses"], row["restoration_type"]) == (10, "long_rest")
    await client.patch(f"/characters/{b['id']}/hp", json={"op": "set_current", "value": 10})
    r = await client.post(f"/characters/{b['id']}/features/feat.2024_boon_recovery/use", json={"amount": 3})
    assert r.status_code == 200, r.text
    assert len(r.json()["rolls"]) == 3
    assert _feat_rows(await _full(client, b["id"]), "2024_boon_recovery")[0]["uses"] == 7


async def test_skill_boon(client):
    b = await _boon(client, "skill", "wisdom")
    row = _feat_rows(b["after"], "2024_boon_skill")[0]
    r = await _complete(client, b["id"], row["id"], {"expertise": "stealth"})
    assert r.status_code == 200, r.text
    skills = r.json()["skills"]
    assert skills["stealth"] == "expert" and skills["arcana"] and skills["survival"]


async def test_night_spirit_state_resistances(client):
    b = await _boon(client, "night_spirit", "dexterity")
    r = await client.post(f"/characters/{b['id']}/features/feat.2024_boon_night_spirit/use", json={})
    assert r.status_code == 200, r.text
    res = set((await _full(client, b["id"]))["computed"]["resistances"])
    assert {"fire", "slashing", "necrotic"} <= res and "psychic" not in res and "radiant" not in res
