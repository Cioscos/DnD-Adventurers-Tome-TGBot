"""Prova con strumento: d20 + caratteristica + competenza (doppia con la Maestria); 2024: vantaggio con l'abilità."""
from __future__ import annotations


async def _char(client, edition="2014", tools=None, dex=14, skills=None) -> int:
    r = await client.post("/characters", json={"name": "Scassinatrice", "rules_edition": edition,
                                               "ability_scores": {"dexterity": dex}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.patch(f"/characters/{cid}", json={"tool_proficiencies": tools or {"thieves_tools": True}})
    assert r.status_code == 200, r.text
    if skills:
        r = await client.patch(f"/characters/{cid}/skills", json={"skills": skills})
        assert r.status_code == 200, r.text
    return cid


async def _roll(client, cid, tool="thieves_tools", **body):
    return await client.post(f"/characters/{cid}/tool_checks/{tool}/roll", json={"ability": "dexterity", **body})


async def test_tool_check_adds_proficiency(client):
    cid = await _char(client)
    r = await _roll(client, cid, die=10)
    assert r.status_code == 200, r.text
    assert (r.json()["total"], r.json()["description"]) == (14, "thieves_tools")  # 10 + DES 2 + competenza 2


async def test_tool_check_expert_doubles(client):
    cid = await _char(client, tools={"thieves_tools": "expert"})
    assert (await _roll(client, cid, die=10)).json()["total"] == 16


async def test_tool_check_not_proficient_409(client):
    cid = await _char(client)
    r = await _roll(client, cid, tool="lute", die=10)
    assert r.status_code == 409 and "tool_not_proficient" in r.text
    history = (await client.get(f"/characters/{cid}/history")).json()
    assert not any("Liuto" in h["description"] for h in history)


async def test_2024_skill_proficient_gives_advantage(client):
    cid = await _char(client, edition="2024", skills={"sleight_of_hand": True})
    r = await _roll(client, cid, die=3, skill="sleight_of_hand")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode_applied"] == "advantage" and len(body["dice"]) == 2
    assert "tool_skill_advantage" in body["notes"]


async def test_2024_skill_not_proficient_no_advantage(client):
    cid = await _char(client, edition="2024")
    body = (await _roll(client, cid, die=3, skill="sleight_of_hand")).json()
    assert body["mode_applied"] == "normal"


async def test_2014_skill_refused(client):
    cid = await _char(client)
    r = await _roll(client, cid, die=10, skill="sleight_of_hand")
    assert r.status_code == 422 and "skill_needs_2024" in r.text


async def test_unknown_tool_404(client):
    cid = await _char(client)
    assert (await _roll(client, cid, tool="nope", die=10)).status_code == 404


async def test_history_names_the_tool(client):
    cid = await _char(client)
    await _roll(client, cid, die=10)
    history = (await client.get(f"/characters/{cid}/history")).json()
    assert any(h["description"].startswith("Prova con Arnesi da scasso (Destrezza)") for h in history)
