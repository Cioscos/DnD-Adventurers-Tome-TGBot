"""Competenze negli strumenti in Character.tool_proficiencies ({chiave: true | "expert"})."""
from __future__ import annotations

from types import SimpleNamespace

from core.rules.tools import add_tools, drop_tools, migrate_tools


def _c(tools=None, other=None, profs=None):
    return SimpleNamespace(general_proficiencies={"armor": [], "weapons": [], "tools": list(tools or []),
                                                  "other": list(other or [])},
                           tool_proficiencies=dict(profs or {}))


def test_migrate_moves_known_and_keeps_unknown():
    c = _c(tools=["Arnesi da scasso", "Strumenti musicali", "Lute"])
    migrate_tools(c)
    assert c.tool_proficiencies == {"thieves_tools": True, "lute": True}
    assert c.general_proficiencies["tools"] == [] and c.general_proficiencies["other"] == ["Strumenti musicali"]


def test_migrate_twice_does_not_duplicate_other():
    c = _c(tools=["Strumenti musicali"], other=["strumenti MUSICALI"])
    migrate_tools(c)
    migrate_tools(c)
    assert c.general_proficiencies["other"] == ["strumenti MUSICALI"]


def test_add_tools_keeps_expert():
    c = _c(profs={"thieves_tools": "expert"})
    add_tools(c, ["thieves_tools", "lute"])
    assert c.tool_proficiencies == {"thieves_tools": "expert", "lute": True}


def test_drop_tools_keeps_expert():
    c = _c(profs={"thieves_tools": "expert", "lute": True})
    drop_tools(c, ["thieves_tools", "lute"])
    assert c.tool_proficiencies == {"thieves_tools": "expert"}


async def _char(client) -> int:
    r = await client.post("/characters", json={"name": "Artigiana"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_patch_tool_proficiencies(client):
    cid = await _char(client)
    r = await client.patch(f"/characters/{cid}", json={"tool_proficiencies": {"lute": True, "thieves_tools": "expert"}})
    assert r.status_code == 200, r.text
    assert r.json()["tool_proficiencies"] == {"lute": True, "thieves_tools": "expert"}


async def test_patch_rejects_unknown_tool(client):
    cid = await _char(client)
    assert (await client.patch(f"/characters/{cid}", json={"tool_proficiencies": {"nope": True}})).status_code == 422
    assert (await client.patch(f"/characters/{cid}", json={"tool_proficiencies": {"lute": "master"}})).status_code == 422


async def test_patch_text_tools_are_converted(client):
    cid = await _char(client)
    r = await client.patch(f"/characters/{cid}", json={"general_proficiencies": {"tools": ["Liuto", "Pippo"]}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tool_proficiencies"].get("lute") is True
    assert body["general_proficiencies"]["tools"] == [] and "Pippo" in body["general_proficiencies"]["other"]
