"""Passivi (Percezione/Intuizione/Indagare), Tuttofare del Bardo e sensi."""
from __future__ import annotations

from tests.integration.conftest import TEST_USER_ID  # noqa: F401


async def _char(client, class_name="bard", level=2) -> int:
    r = await client.post("/characters", json={"name": "Menestrello"})
    cid = r.json()["id"]
    r = await client.post(f"/characters/{cid}/classes",
                          json={"class_name": class_name, "level": level, "hit_die": 8})
    assert r.status_code == 201, r.text
    for ab in ("wisdom", "intelligence"):
        await client.patch(f"/characters/{cid}/ability_scores/{ab}", json={"value": 14})  # +2
    return cid


async def _rule(client, cid, target, value):
    body = {"name": target, "enabled": True, "dsl": {
        "version": 1, "subject": {"type": "character"}, "triggers": [],
        "passive_modifiers": [{"when": {"path": "$character.id", "op": "gt", "value": 0},
                               "target": target, "value": value,
                               "label_i18n": {"it": target, "en": target}}]}}
    r = await client.post(f"/characters/{cid}/homebrew/rules", json=body)
    assert r.status_code in (200, 201), r.text


async def test_jack_of_all_trades_half_pb_on_unproficient(client):
    cid = await _char(client)
    r = await client.post(f"/characters/{cid}/skills/perception/roll", json={"die": 10})
    assert r.json()["bonus"] == 3  # SAG +2, Tuttofare floor(2/2)=1
    body = (await client.get(f"/characters/{cid}")).json()
    assert body["jack_of_all_trades"] is True
    assert body["skill_bonuses"]["perception"] == 3
    assert body["passives"]["perception"] == 13
    assert body["passives"]["insight"] == 13
    assert body["passives"]["investigation"] == 13


async def test_no_jack_below_level_2_or_other_class(client):
    for cn, lv in (("bard", 1), ("fighter", 5)):
        cid = await _char(client, cn, lv)
        r = await client.post(f"/characters/{cid}/skills/perception/roll", json={"die": 10})
        assert r.json()["bonus"] == 2


async def test_passives_include_homebrew_passive_target(client):
    cid = await _char(client, "fighter", 1)
    await _rule(client, cid, "character.passive.insight", 3)
    await _rule(client, cid, "character.skill.insight", 1)
    p = (await client.get(f"/characters/{cid}")).json()["passives"]
    assert p["insight"] == 10 + 2 + 1 + 3
    assert p["perception"] == 12


async def test_observant_feat_passives(client):
    cid = await _char(client, "fighter", 1)
    await client.patch(f"/characters/{cid}/xp", json={"set": 2700})
    body = (await client.get(f"/characters/{cid}")).json()
    base = body["passives"]
    ch = body["pending_choices"][0]["id"]
    r = await client.post(f"/characters/{cid}/choices/{ch}/resolve",
                          json={"kind": "feat", "feat_key": "observant", "ability": "wisdom"})
    assert r.status_code == 200, r.text
    p = r.json()["passives"]
    assert p["perception"] == base["perception"] + 5
    assert p["investigation"] == base["investigation"] + 5
    assert p["insight"] == base["insight"]


async def test_senses_saved_and_returned(client):
    cid = await _char(client)
    s = [{"type": "darkvision", "range_ft": 60}]
    r = await client.patch(f"/characters/{cid}", json={"settings": {"senses": s}})
    assert r.status_code == 200, r.text
    assert (await client.get(f"/characters/{cid}")).json()["settings"]["senses"] == s
    r = await client.patch(f"/characters/{cid}", json={"settings": {"senses": [{"type": "x", "range_ft": 1}]}})
    assert r.status_code == 422
