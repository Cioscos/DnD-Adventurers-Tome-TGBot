"""POST /characters/{id}/saving_throws/{ability}/roll (D20RollSubmission).

Deterministic via client-supplied ``die``. Bonus = ability modifier +
proficiency bonus when the character is proficient in that save. A starting
Guerriero is seeded proficient in STR and CON saves (PHB), so the proficiency
branch is exercised without any extra setup. nat 20 → is_critical, nat 1 →
is_fumble. ``with_inspiration`` requires a token (409 otherwise) and consumes it.

Contract: ``RollResult`` (api.stats.rollSavingThrow → die/bonus/total/
is_critical/is_fumble/description).
"""
from __future__ import annotations


async def _fighter(client) -> int:
    """Guerriero L1 → PB +2; STR & CON saves proficient, all ability mods 0."""
    r = await client.post(
        "/characters",
        json={"name": "Save", "initial_class": {"class_name": "Guerriero", "level": 1, "hit_die": 10}},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["saving_throws"]["strength"] is True   # class-seeded proficiency
    return body["id"]


async def _roll(client, cid: int, ability: str, **body):
    return await client.post(f"/characters/{cid}/saving_throws/{ability}/roll", json=body or None)


async def test_unknown_ability_is_400(client):
    cid = await _fighter(client)
    r = await _roll(client, cid, "luck", die=10)
    assert r.status_code == 400, r.text


async def test_proficient_save_adds_proficiency_bonus(client):
    cid = await _fighter(client)
    res = (await _roll(client, cid, "strength", die=10)).json()  # proficient, mod 0
    assert res["bonus"] == 2 and res["total"] == 12
    assert res["description"] == "strength"


async def test_non_proficient_save_has_no_bonus(client):
    cid = await _fighter(client)
    res = (await _roll(client, cid, "dexterity", die=10)).json()  # not proficient, mod 0
    assert res["bonus"] == 0 and res["total"] == 10


async def test_ability_modifier_applies_without_proficiency(client):
    cid = await _fighter(client)
    r = await client.patch(f"/characters/{cid}/ability_scores/dexterity", json={"value": 14})  # +2
    assert r.status_code == 200, r.text
    res = (await _roll(client, cid, "dexterity", die=10)).json()
    assert res["bonus"] == 2 and res["total"] == 12   # mod 2, no PB


async def test_critical_and_fumble_flags(client):
    cid = await _fighter(client)
    assert (await _roll(client, cid, "wisdom", die=20)).json()["is_critical"] is True
    assert (await _roll(client, cid, "wisdom", die=1)).json()["is_fumble"] is True


async def test_inspiration_required_when_absent(client):
    cid = await _fighter(client)
    r = await _roll(client, cid, "strength", with_inspiration=True)
    assert r.status_code == 409, r.text


async def test_inspiration_is_consumed(client):
    cid = await _fighter(client)
    r = await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    assert r.status_code == 200, r.text
    r = await _roll(client, cid, "strength", die=15, with_inspiration=True)
    assert r.status_code == 200, r.text
    after = (await client.get(f"/characters/{cid}")).json()
    assert after["heroic_inspiration"] is False
