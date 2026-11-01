"""POST /characters/import/ddb: recupero (mockato), conversione, feature del motore, errori."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

import api.routers.transfer as transfer
from api.services import ddb_import
from api.services.ddb_import import DdbImportError, fetch_ddb, parse_ddb_id

_FIXTURE = Path(__file__).parents[1] / "fixtures" / "ddb" / "cleric19.json"
URL = "https://www.dndbeyond.com/characters/95893448"


def _fixture() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def ddb_ok(monkeypatch):
    seen = []

    async def fake(char_id: int) -> dict:
        seen.append(char_id)
        return _fixture()
    monkeypatch.setattr(transfer, "fetch_ddb", fake)
    return seen


async def _post(client, url=URL):
    return await client.post("/characters/import/ddb", json={"url": url})


async def test_import_ddb_creates_character(client, ddb_ok):
    r = await _post(client)
    assert r.status_code == 201, r.text
    body = r.json()
    ch = body["character"]
    assert ddb_ok == [95893448]
    assert ch["name"] == "Додрия" and ch["hit_points"] == 212 and ch["current_hit_points"] == 170
    ac = ch["ac_breakdown"]
    assert ac["base"] + ac["shield"] + ac["magic"] + ac["items"] + ac["homebrew"] == 22
    assert {"imported", "approximated", "skipped"} <= set(body["report"])
    assert body["report"]["imported"]


async def test_import_ddb_channel_divinity_not_duplicated(client, ddb_ok):
    ch = (await _post(client)).json()["character"]
    cd = [a for a in ch["abilities"] if a.get("feature_key") == "cleric.channel_divinity"]
    assert len(cd) == 1 and cd[0]["max_uses"] == 3 and cd[0]["uses"] == 2
    assert not any(a["name"] == "Channel Divinity" and not a.get("is_class_feature") for a in ch["abilities"])


async def test_import_ddb_spell_slots_used_survive(client, ddb_ok):
    ch = (await _post(client)).json()["character"]
    slots = {(s["level"], s["is_pact"]): s for s in ch["spell_slots"]}
    assert slots[(1, False)]["used"] == 1 and slots[(1, False)]["total"] == 4
    assert slots[(9, False)]["total"] >= 1


async def test_import_ddb_twice_gets_suffix(client, ddb_ok):
    await _post(client)
    r = await _post(client)
    assert r.json()["character"]["name"] == "Додрия (importato)"


@pytest.mark.parametrize("url,expected", [
    ("https://www.dndbeyond.com/characters/95893448", 95893448),
    ("dndbeyond.com/characters/95893448/builder?x=1", 95893448),
    ("  95893448 ", 95893448),
    ("https://ddb.ac/characters/95893448/AbCdEf", 95893448),
    ("https://www.dndbeyond.com/profile/x/characters/123", 123),
    ("ciao", None), ("", None), ("https://example.com/123abc", None),
])
def test_parse_ddb_id(url, expected):
    assert parse_ddb_id(url) == expected


async def test_invalid_link_422(client, ddb_ok):
    r = await _post(client, "ciao")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_link"
    assert ddb_ok == []


@pytest.mark.parametrize("code,status", [("ddb_private", 422), ("ddb_not_found", 422),
                                         ("ddb_unreachable", 502), ("ddb_invalid", 422)])
async def test_fetch_errors(client, monkeypatch, code, status):
    async def fail(char_id: int) -> dict:
        raise DdbImportError(code)
    monkeypatch.setattr(transfer, "fetch_ddb", fail)
    r = await _post(client)
    assert r.status_code == status and r.json()["detail"]["code"] == code


async def test_ddb_json_without_name_is_invalid(client, monkeypatch):
    async def bad(char_id: int) -> dict:
        return {"success": True, "data": {"id": 1}}
    monkeypatch.setattr(transfer, "fetch_ddb", bad)
    r = await _post(client)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "ddb_invalid"


@pytest.mark.parametrize("status,body,ctype,code", [
    (403, b"", "text/plain", "ddb_private"),
    (404, b"", "text/plain", "ddb_not_found"),
    (200, b"<html>blocked</html>", "text/html", "ddb_unreachable"),
    (200, b'{"success": false, "data": null}', "application/json", "ddb_unreachable"),
    (500, b"", "text/plain", "ddb_unreachable"),
])
async def test_fetch_ddb_maps_http(monkeypatch, status, body, ctype, code):
    transport = httpx.MockTransport(lambda req: httpx.Response(status, content=body, headers={"content-type": ctype}))
    monkeypatch.setattr(ddb_import, "_transport", transport)
    with pytest.raises(DdbImportError) as e:
        await fetch_ddb(1)
    assert e.value.code == code


async def test_fetch_ddb_ok_and_url(monkeypatch):
    seen = []

    def handler(req):
        seen.append(str(req.url))
        return httpx.Response(200, json={"success": True, "data": {"name": "X"}})
    monkeypatch.setattr(ddb_import, "_transport", httpx.MockTransport(handler))
    assert (await fetch_ddb(42))["data"]["name"] == "X"
    assert seen == ["https://character-service.dndbeyond.com/character/v5/character/42?includeCustomItems=true"]


async def test_fetch_ddb_network_error(monkeypatch):
    def boom(req):
        raise httpx.ConnectTimeout("t")
    monkeypatch.setattr(ddb_import, "_transport", httpx.MockTransport(boom))
    with pytest.raises(DdbImportError) as e:
        await fetch_ddb(1)
    assert e.value.code == "ddb_unreachable"


async def test_import_ddb_sorcery_points_not_duplicated(client, monkeypatch):
    sorc = Path(__file__).parents[1] / "fixtures" / "ddb" / "sorcerer5_2024.json"

    async def fake(char_id: int) -> dict:
        return json.loads(sorc.read_text(encoding="utf-8"))
    monkeypatch.setattr(transfer, "fetch_ddb", fake)
    ch = (await _post(client)).json()["character"]
    sp = [a for a in ch["abilities"] if a.get("feature_key") == "sorcerer.sorcery_points"]
    assert len(sp) == 1 and sp[0]["max_uses"] == 5 and sp[0]["uses"] == 5
    assert not any(a["name"] == "Font of Magic: Sorcery Points" for a in ch["abilities"])
    assert sum(ch["ac_breakdown"][k] for k in ("base", "shield", "magic", "items", "homebrew")) == 12


async def test_import_ddb_monk_focus_points_not_duplicated(client, monkeypatch):
    monk = Path(__file__).parents[1] / "fixtures" / "ddb" / "monk20_2024.json"

    async def fake(char_id: int) -> dict:
        return json.loads(monk.read_text(encoding="utf-8"))
    monkeypatch.setattr(transfer, "fetch_ddb", fake)
    ch = (await _post(client)).json()["character"]
    ki = [a for a in ch["abilities"] if a.get("feature_key") == "monk.ki"]
    assert len(ki) == 1 and ki[0]["max_uses"] == 20
    assert not any(a["name"] == "Focus Points" for a in ch["abilities"])


async def test_import_ddb_rage_uses_ddb_max_and_keeps_other_rage_actions(client, monkeypatch):
    barb = Path(__file__).parents[1] / "fixtures" / "ddb" / "barbarian20_2024.json"

    async def fake(char_id: int) -> dict:
        return json.loads(barb.read_text(encoding="utf-8"))
    monkeypatch.setattr(transfer, "fetch_ddb", fake)
    ch = (await _post(client)).json()["character"]
    rage = [a for a in ch["abilities"] if a.get("feature_key") == "barbarian.rage"]
    assert len(rage) == 1 and rage[0]["max_uses"] == 6 and rage[0]["uses"] == 6  # regole 2024, non "illimitata"
    names = {a["name"] for a in ch["abilities"]}
    assert "Rage (Enter)" not in names and "Rage: Regain Expended Uses" in names


def _char_with_subclass() -> dict:
    return {"success": True, "data": {"name": "X", "classes": [
        {"id": 5, "level": 20, "definition": {"id": 10}, "subclassDefinition": {"id": 20}}]}}


async def test_fetch_ddb_adds_always_prepared_spells(monkeypatch):
    seen = []

    def handler(req):
        seen.append(str(req.url))
        if "/character/v5/character/" in str(req.url):
            return httpx.Response(200, json=_char_with_subclass())
        if req.url.params.get("classId") == "20":
            return httpx.Response(200, json={"success": True, "data": [{"definition": {"name": "Bless", "level": 1}}]})
        return httpx.Response(200, json={"success": True, "data": []})
    monkeypatch.setattr(ddb_import, "_transport", httpx.MockTransport(handler))
    body = await fetch_ddb(42)
    assert [s["definition"]["name"] for s in body["data"]["_alwaysPrepared"]] == ["Bless"]
    assert any("always-prepared-spells?classId=20&classLevel=20" in u for u in seen)


async def test_fetch_ddb_always_prepared_failure_is_not_fatal(monkeypatch):
    def handler(req):
        if "/character/v5/character/" in str(req.url):
            return httpx.Response(200, json=_char_with_subclass())
        return httpx.Response(500)
    monkeypatch.setattr(ddb_import, "_transport", httpx.MockTransport(handler))
    body = await fetch_ddb(42)
    assert body["data"]["name"] == "X" and body["data"]["_alwaysPrepared"] == []


async def test_import_ddb_fighter_every_feature_deduplicated(client, monkeypatch):
    fighter = Path(__file__).parents[1] / "fixtures" / "ddb" / "fighter20_2024.json"

    async def fake(char_id: int) -> dict:
        return json.loads(fighter.read_text(encoding="utf-8"))
    monkeypatch.setattr(transfer, "fetch_ddb", fake)
    ch = (await _post(client)).json()["character"]
    by_key = {a["feature_key"]: a for a in ch["abilities"] if a.get("feature_key")}
    assert by_key["fighter.action_surge"]["max_uses"] == 2  # massimo DDB (2024)
    assert by_key["fighter.indomitable"]["max_uses"] == 3
    assert by_key["fighter.second_wind"]["max_uses"] == 4
    names = {a["name"] for a in ch["abilities"]}
    assert not names & {"Action Surge", "Indomitable", "Second Wind"}
    ac = ch["ac_breakdown"]
    assert ac["base"] + ac["shield"] == 18
