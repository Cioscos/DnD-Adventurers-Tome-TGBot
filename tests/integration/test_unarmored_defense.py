"""POST /characters/{id}/ac/unarmored-defense (Barbarian/Monk Unarmored Defense).

D&D 5e: base AC = 10 + DEX mod + second-ability mod (CON for Barbarian, WIS for
Monk). Enabling clears the manual base override (mutually exclusive) and keeps
base AC in sync with later DEX / second-ability changes; disabling reverts base
to the equipped armor (or 10). ``ability`` must be 'wisdom' or 'constitution'
(else 400).

Contract: response is ``CharacterFull``; api.stats.setUnarmoredDefense reads
ac_breakdown.base / ac / unarmored_defense_ability / base_armor_class_override.
"""
from __future__ import annotations


async def _barbarian(client) -> int:
    r = await client.post(
        "/characters",
        json={"name": "Unarmored", "initial_class": {"class_name": "Barbaro", "level": 1, "hit_die": 12}},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _set_ability(client, cid: int, ability: str, value: int):
    r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
    assert r.status_code == 200, r.text
    return r.json()


async def test_enable_sets_base_ac_from_dex_and_second_ability(client):
    cid = await _barbarian(client)
    await _set_ability(client, cid, "dexterity", 16)     # +3
    await _set_ability(client, cid, "constitution", 14)  # +2

    r = await client.post(f"/characters/{cid}/ac/unarmored-defense", json={"ability": "constitution"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["unarmored_defense_ability"] == "constitution"
    assert body["ac_breakdown"]["base"] == 15            # 10 + 3 + 2
    assert body["ac"] == 15                               # no shield / magic


async def test_dex_change_resyncs_base_while_active(client):
    cid = await _barbarian(client)
    r = await client.post(f"/characters/{cid}/ac/unarmored-defense", json={"ability": "constitution"})
    assert r.status_code == 200, r.text
    assert r.json()["ac_breakdown"]["base"] == 10        # default DEX/CON mods 0

    body = await _set_ability(client, cid, "dexterity", 16)  # +3 → base resyncs
    assert body["ac_breakdown"]["base"] == 13            # 10 + 3 + 0


async def test_enable_clears_manual_base_override(client):
    cid = await _barbarian(client)
    # Manually pin base AC to 99 (sets the override flag).
    r = await client.patch(f"/characters/{cid}/ac", json={"base": 99})
    assert r.status_code == 200, r.text
    assert r.json()["ac_breakdown"]["base"] == 99
    assert r.json()["base_armor_class_override"] is True

    r = await client.post(f"/characters/{cid}/ac/unarmored-defense", json={"ability": "wisdom"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["base_armor_class_override"] is False
    assert body["ac_breakdown"]["base"] == 10            # recomputed, override discarded


async def test_disable_reverts_base_to_ten_when_unarmored(client):
    cid = await _barbarian(client)
    await _set_ability(client, cid, "dexterity", 16)
    await _set_ability(client, cid, "constitution", 14)
    r = await client.post(f"/characters/{cid}/ac/unarmored-defense", json={"ability": "constitution"})
    assert r.json()["ac_breakdown"]["base"] == 15

    r = await client.post(f"/characters/{cid}/ac/unarmored-defense", json={"ability": None})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["unarmored_defense_ability"] is None
    assert body["ac_breakdown"]["base"] == 10            # no armor → 10


async def test_invalid_second_ability_is_400(client):
    cid = await _barbarian(client)
    r = await client.post(f"/characters/{cid}/ac/unarmored-defense", json={"ability": "strength"})
    assert r.status_code == 400, r.text
