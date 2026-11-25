"""Talenti che scelgono strumenti dal catalogo: Artigiano, Musicista, Abile (chiavi, mai testo libero)."""
from __future__ import annotations

from core.rules.catalog.feats_2024 import options_ok
from tests.integration.rules.test_feats_take_complete import _complete, _feat_rows, _take


async def _with_feat(client, feat) -> tuple[int, int]:
    cid = (await client.post("/characters", json={"name": "Prova", "rules_edition": "2024"})).json()["id"]
    r = await _take(client, cid, feat)
    assert r.status_code == 201, r.text
    return cid, _feat_rows(r.json(), feat)[0]["id"]


async def test_crafter_saves_artisan_keys(client):
    cid, row = await _with_feat(client, "2024_crafter")
    tools = ["smiths_tools", "weavers_tools", "carpenters_tools"]  # 2024 Artigiano pag. 200: dalla tabella Creazione rapida
    r = await _complete(client, cid, row, {"tools": tools})
    assert r.status_code == 200, r.text
    full = (await client.get(f"/characters/{cid}")).json()
    assert set(tools) <= set(full["tool_proficiencies"])
    assert _feat_rows(full, "2024_crafter")[0]["options"]["tools"] == tools


async def test_crafter_rejects_an_instrument_or_duplicates(client):
    cid, row = await _with_feat(client, "2024_crafter")
    assert (await _complete(client, cid, row, {"tools": ["smiths_tools", "lute", "carpenters_tools"]})).status_code == 422
    assert (await _complete(client, cid, row, {"tools": ["smiths_tools", "smiths_tools", "carpenters_tools"]})).status_code == 422
    assert (await _complete(client, cid, row, {"tools": ["Strumenti da fabbro", "weavers_tools", "carpenters_tools"]})).status_code == 422


async def test_musician_rejects_artisan_tools(client):
    cid, row = await _with_feat(client, "2024_musician")
    assert (await _complete(client, cid, row, {"instruments": ["lute", "flute", "smiths_tools"]})).status_code == 422
    r = await _complete(client, cid, row, {"instruments": ["lute", "flute", "viol"]})
    assert r.status_code == 200, r.text


async def test_skilled_tool_pick_must_be_in_catalog(client):
    cid, row = await _with_feat(client, "2024_skilled")
    assert (await _complete(client, cid, row, {"picks": ["stealth", "arcana", "tool:Liuto"]})).status_code == 422
    r = await _complete(client, cid, row, {"picks": ["stealth", "arcana", "tool:lute"]})
    assert r.status_code == 200, r.text
    assert (await client.get(f"/characters/{cid}")).json()["tool_proficiencies"].get("lute") is True


def test_options_ok_accepts_old_recognised_names():
    old = ["Strumenti da fabbro", "Strumenti da falegname", "Strumenti da tessitore"]
    assert options_ok({"tools": old}, "feat.2024_crafter")
    assert not options_ok({"tools": [*old[:2], "Pippo"]}, "feat.2024_crafter")
    assert not options_ok({"tools": ["smiths_tools", "carpenters_tools", "lute"]}, "feat.2024_crafter")
    # 2024 Artigiano pag. 200: le scorte da alchimista non sono nella tabella Creazione rapida
    assert not options_ok({"tools": ["smiths_tools", "carpenters_tools", "Scorte da alchimista"]}, "feat.2024_crafter")
    assert options_ok({"instruments": ["lute", "Flauto", "viol"]}, "feat.2024_musician")
    assert options_ok({"picks": ["stealth", "tool:lute", "tool:Arnesi da scasso"]}, "feat.2024_skilled")
    assert not options_ok({"picks": ["stealth", "arcana", "tool:Pippo"]}, "feat.2024_skilled")
