"""Chi concede strumenti scrive Character.tool_proficiencies (classi, privilegi, talenti, import, export)."""
from __future__ import annotations

from tests.integration.rules.test_2014_rogue import _rogue
from tests.integration.rules.test_feats_take_complete import _complete, _feat_rows, _take


async def _full(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def test_new_rogue_gets_thieves_tools_key(client):
    full = await _full(client, await _rogue(client, 1))
    assert full["tool_proficiencies"].get("thieves_tools") is True
    assert full["general_proficiencies"]["tools"] == []


async def test_assassin_grants_kits(client):
    full = await _full(client, await _rogue(client, 3, "assassin"))
    assert full["tool_proficiencies"].get("disguise_kit") is True
    assert full["tool_proficiencies"].get("poisoners_kit") is True


async def test_expert_tool_survives_lost_grant(client):
    cid = await _rogue(client, 3, "assassin")
    profs = (await _full(client, cid))["tool_proficiencies"]
    r = await client.patch(f"/characters/{cid}", json={"tool_proficiencies": {**profs, "disguise_kit": "expert"}})
    assert r.status_code == 200, r.text
    row = (await _full(client, cid))["classes"][0]["id"]
    r = await client.patch(f"/characters/{cid}/classes/{row}", json={"subclass": "Furfante"})  # il Furfante non dà i kit
    assert r.status_code == 200, r.text
    after = (await _full(client, cid))["tool_proficiencies"]
    assert after.get("disguise_kit") == "expert" and "poisoners_kit" not in after


async def test_crafter_text_choice_goes_to_column(client):
    r = await client.post("/characters", json={"name": "Artigiana", "rules_edition": "2024"})
    cid = r.json()["id"]
    r = await _take(client, cid, "2024_crafter")
    assert r.status_code == 201, r.text
    row = _feat_rows(r.json(), "2024_crafter")[0]
    r = await _complete(client, cid, row["id"], {"tools": ["Strumenti da fabbro", "Pippo", "Strumenti da falegname"]})
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    assert {"smiths_tools", "carpenters_tools"} <= set(full["tool_proficiencies"])
    assert "Pippo" in full["general_proficiencies"]["other"] and full["general_proficiencies"]["tools"] == []


async def _reimport(client, data: dict) -> dict:
    r = await client.post("/characters/import", json=data)
    assert r.status_code == 201, r.text
    return r.json()


async def test_export_import_roundtrip_keeps_tools(client):
    cid = await _rogue(client, 1)
    await client.patch(f"/characters/{cid}", json={"tool_proficiencies": {"thieves_tools": "expert", "lute": True}})
    data = (await client.get(f"/characters/{cid}/export")).json()
    assert (await _reimport(client, data))["tool_proficiencies"] == {"thieves_tools": "expert", "lute": True}


async def test_import_legacy_text_tools_converts(client):
    cid = await _rogue(client, 1)
    data = (await client.get(f"/characters/{cid}/export")).json()
    data["character"].pop("tool_proficiencies", None)
    data["character"]["general_proficiencies"] = {"tools": ["Liuto", "Strumenti musicali"]}
    body = await _reimport(client, data)
    assert body["tool_proficiencies"].get("lute") is True
    assert "Strumenti musicali" in body["general_proficiencies"]["other"]


async def test_import_drops_unknown_tool_keys(client):
    cid = await _rogue(client, 1)
    data = (await client.get(f"/characters/{cid}/export")).json()
    data["character"]["tool_proficiencies"] = {"lute": True, "nope": True, "flute": "master"}
    assert (await _reimport(client, data))["tool_proficiencies"] == {"lute": True}


def test_ddb_tools_and_tool_expertise():
    from api.services import ddb_import

    class Ctx:
        data = {}
        def ok(self, *_a): pass
        def approx(self, *_a): pass
    mods = [
        {"type": "proficiency", "subType": "thieves-tools", "friendlySubtypeName": "Thieves' Tools"},
        {"type": "expertise", "subType": "thieves-tools", "friendlySubtypeName": "Thieves' Tools"},
        {"type": "proficiency", "subType": "lute", "friendlySubtypeName": "Lute"},
        {"type": "proficiency", "subType": "weird-kit", "friendlySubtypeName": "Weird Kit"},
    ]
    orig = ddb_import._modifiers
    ddb_import._modifiers = lambda _data: mods
    try:
        out = ddb_import._proficiencies(Ctx())
    finally:
        ddb_import._modifiers = orig
    assert out["tool_proficiencies"] == {"thieves_tools": "expert", "lute": True}
    assert "Weird Kit" in out["general_proficiencies"]["other"] and out["general_proficiencies"]["tools"] == []


async def test_session_identity_lists_tools(client, test_session_factory):
    from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
    _, cid = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    await client.patch(f"/characters/{cid}", json={"tool_proficiencies": {"lute": True}})
    as_user(GM_ID)
    r = await client.get(f"/sessions/ABC123/participants/{PLAYER_ID}/identity")
    assert r.status_code == 200, r.text
    assert "Liuto" in (r.json()["general_proficiencies"] or "")


async def test_lost_grant_keeps_a_tool_the_player_already_had(client):
    """Il kit da avvelenatore c'era già (es. dal background): perdere l'Assassino non lo toglie."""
    r = await client.post("/characters", json={"name": "Avvelenatrice", "initial_class": {"class_name": "rogue", "level": 2}})
    cid = r.json()["id"]
    await client.patch(f"/characters/{cid}", json={"tool_proficiencies": {"thieves_tools": True, "poisoners_kit": True}})
    row = (await _full(client, cid))["classes"][0]["id"]
    assert (await client.patch(f"/characters/{cid}/classes/{row}", json={"level": 3, "subclass": "Assassino"})).status_code == 200
    assert (await _full(client, cid))["tool_proficiencies"].get("disguise_kit") is True
    assert (await client.patch(f"/characters/{cid}/classes/{row}", json={"subclass": "Furfante"})).status_code == 200
    after = (await _full(client, cid))["tool_proficiencies"]
    assert after.get("poisoners_kit") is True and "disguise_kit" not in after
