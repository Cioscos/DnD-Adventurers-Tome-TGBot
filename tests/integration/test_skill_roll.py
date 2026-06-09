"""POST /characters/{id}/skills/{skill_name}/roll (D20RollSubmission).

A client-supplied ``die`` makes every branch deterministic (no RNG). Bonus rule:
- not proficient → ability modifier only;
- proficient (true/1) → ability modifier + proficiency bonus;
- expertise ("expert") → ability modifier + 2 x proficiency bonus.
nat 20 → is_critical, nat 1 → is_fumble. ``with_inspiration`` requires an
available token (else 409) and consumes it.

Contract: ``RollResult`` (api.stats.rollSkill → die/bonus/total/is_critical/
is_fumble/description).
"""
from __future__ import annotations


async def _fighter(client) -> int:
    """Guerriero L1 → proficiency bonus +2, ability scores all 10 (mod 0)."""
    r = await client.post(
        "/characters",
        json={"name": "Roll", "initial_class": {"class_name": "Guerriero", "level": 1, "hit_die": 10}},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _set_skill(client, cid: int, skill: str, level) -> None:
    r = await client.patch(f"/characters/{cid}/skills", json={"skills": {skill: level}})
    assert r.status_code == 200, r.text


async def _roll(client, cid: int, skill: str, **body):
    return await client.post(f"/characters/{cid}/skills/{skill}/roll", json=body or None)


async def test_unknown_skill_is_400(client):
    cid = await _fighter(client)
    r = await _roll(client, cid, "vibes", die=10)
    assert r.status_code == 400, r.text


async def test_basic_roll_without_proficiency(client):
    cid = await _fighter(client)
    r = await _roll(client, cid, "athletics", die=10)   # STR mod 0, not proficient
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["die"] == 10 and res["bonus"] == 0 and res["total"] == 10
    assert res["is_critical"] is False and res["is_fumble"] is False
    assert res["description"] == "athletics"


async def test_proficiency_adds_proficiency_bonus(client):
    cid = await _fighter(client)
    await _set_skill(client, cid, "athletics", True)
    res = (await _roll(client, cid, "athletics", die=10)).json()
    assert res["bonus"] == 2 and res["total"] == 12     # 0 + PB(2)


async def test_expertise_doubles_proficiency_bonus(client):
    cid = await _fighter(client)
    await _set_skill(client, cid, "athletics", "expert")
    res = (await _roll(client, cid, "athletics", die=10)).json()
    assert res["bonus"] == 4 and res["total"] == 14     # 0 + 2*PB


async def test_ability_modifier_is_included(client):
    cid = await _fighter(client)
    r = await client.patch(f"/characters/{cid}/ability_scores/strength", json={"value": 16})  # +3
    assert r.status_code == 200, r.text
    await _set_skill(client, cid, "athletics", True)
    res = (await _roll(client, cid, "athletics", die=10)).json()
    assert res["bonus"] == 5 and res["total"] == 15     # 3 + PB(2)


async def test_critical_and_fumble_flags(client):
    cid = await _fighter(client)
    assert (await _roll(client, cid, "stealth", die=20)).json()["is_critical"] is True
    assert (await _roll(client, cid, "stealth", die=1)).json()["is_fumble"] is True


async def test_inspiration_required_when_absent(client):
    cid = await _fighter(client)
    r = await _roll(client, cid, "athletics", with_inspiration=True)
    assert r.status_code == 409, r.text


async def test_inspiration_is_consumed(client):
    cid = await _fighter(client)
    r = await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    assert r.status_code == 200, r.text
    r = await _roll(client, cid, "athletics", die=15, with_inspiration=True)
    assert r.status_code == 200, r.text
    after = (await client.get(f"/characters/{cid}")).json()
    assert after["heroic_inspiration"] is False
