"""PATCH /hp DAMAGE con damage_type: resistenza/immunità/vulnerabilità applicate dal server."""
from __future__ import annotations

import pytest

from tests.integration.test_hp_damage_modifier import (
    _descriptions, _hp, _make_char, _start_concentration,
)


async def _set_mods(client, cid: int, **mods) -> None:
    r = await client.patch(f"/characters/{cid}", json={"damage_modifiers": mods})
    assert r.status_code == 200, r.text


async def test_damage_with_resistance_halves(client):
    cid = await _make_char(client, 20)
    await _set_mods(client, cid, resistances=["Fuoco"])
    body = await _hp(client, cid, "damage", 15, damage_type="fire")
    assert body["current_hit_points"] == 13  # 15 -> 7
    assert any("Danno 15" in d and "→ 7" in d and "resistenza" in d for d in await _descriptions(client, cid))


async def test_damage_with_immunity_zero_no_concentration_save(client):
    cid = await _make_char(client, 20)
    await _set_mods(client, cid, immunities=["fire"])
    await _start_concentration(client, cid)
    await _hp(client, cid, "set_temp", 4)
    body = await _hp(client, cid, "damage", 30, damage_type="fire")
    assert body["current_hit_points"] == 20
    assert body["temp_hp"] == 4
    assert body.get("concentration_save") is None
    assert body["concentrating_spell_id"] is not None


async def test_damage_with_vulnerability_doubles(client):
    cid = await _make_char(client, 20)
    await _set_mods(client, cid, vulnerabilities=["fire"])
    body = await _hp(client, cid, "damage", 6, damage_type="fire")
    assert body["current_hit_points"] == 8


async def test_concentration_dc_uses_applied_damage(client):
    cid = await _make_char(client, 100)
    await _set_mods(client, cid, resistances=["fire"])
    await _start_concentration(client, cid)
    body = await _hp(client, cid, "damage", 60, damage_type="fire")
    assert body["concentration_save"]["dc"] == 15  # applied 30 // 2, not raw 60 // 2


async def test_explicit_override_wins(client):
    cid = await _make_char(client, 20)
    await _set_mods(client, cid, resistances=["fire"])
    body = await _hp(client, cid, "damage", 15, damage_type="fire", damage_modifier="none")
    assert body["current_hit_points"] == 5


async def test_explicit_immune_applies_zero(client):
    cid = await _make_char(client, 20)
    body = await _hp(client, cid, "damage", 9, damage_type="fire", damage_modifier="immune", raw_value=9)
    assert body["current_hit_points"] == 20


@pytest.mark.parametrize("label", ["Fuoco", "Fire", "fire", "dmg_fire"])
async def test_resistance_matches_legacy_labels(client, label):
    cid = await _make_char(client, 20)
    await _set_mods(client, cid, resistances=[label])
    body = await _hp(client, cid, "damage", 10, damage_type="fire")
    assert body["current_hit_points"] == 15


async def test_no_damage_type_unchanged(client):
    cid = await _make_char(client, 20)
    await _set_mods(client, cid, resistances=["fire"], immunities=["cold"])
    body = await _hp(client, cid, "damage", 10)
    assert body["current_hit_points"] == 10


async def test_unknown_damage_type_unchanged(client):
    cid = await _make_char(client, 20)
    await _set_mods(client, cid, resistances=["fire"])
    body = await _hp(client, cid, "damage", 10, damage_type="banana")
    assert body["current_hit_points"] == 10
