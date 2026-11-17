"""Log della serata (U42/U47): ingressi dei PG, una sola riga per dado vita, nomi delle opzioni al posto delle chiavi."""
from __future__ import annotations

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID
from tests.integration.test_campaigns_api import _char, _enrolled, act
from tests.integration.test_session_recap import P2_ID, _join, _no_flag  # noqa: F401 — fixture autouse

from core.rules.roll_options import option_names


async def _open(client, camp_id) -> str:
    act(GM_ID)
    r = await client.post("/sessions", json={"campaign_id": camp_id})
    assert r.status_code == 201, r.text
    return r.json()["code"]


async def _feed(client, uid: int, code: str) -> list[dict]:
    act(uid)
    r = await client.get(f"/sessions/{code}/feed")
    assert r.status_code == 200, r.text
    return [i for i in r.json()["items"] if i["type"] == "event"]


async def test_joins_and_a_single_hit_die_row_reach_the_feed(client, test_session_factory):
    f = test_session_factory
    camp, cid = await _enrolled(client, f)
    cid2 = await _char(f, P2_ID, name="Bardo")
    act(P2_ID)
    assert (await client.post("/campaigns/enroll", json={"code": camp["invite_code"], "character_id": cid2})).status_code == 200
    code = await _open(client, camp["id"])
    await _join(client, camp["id"], PLAYER_ID, cid)
    await _join(client, camp["id"], P2_ID, cid2)

    joins = [e for e in await _feed(client, GM_ID, code) if e["event_type"] == "session_join"]
    assert {e["character_name"] for e in joins} == {"Eroe", "Bardo"}
    assert len({e["event_id"] for e in joins}) == 2

    act(PLAYER_ID)
    for op, v in (("set_max", 20), ("set_current", 10)):
        assert (await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": v})).status_code == 200
    class_id = (await client.get(f"/characters/{cid}")).json()["classes"][0]["id"]
    r = await client.post(f"/characters/{cid}/hit_dice/spend", json={"class_id": class_id, "count": 1, "rolls": [4]})
    assert r.status_code == 200, r.text

    mine = await _feed(client, PLAYER_ID, code)
    assert [e["event_type"] for e in mine if e["event_type"] in ("hit_dice", "hp_change") and "Cura" in e["description"]] == []
    assert len([e for e in mine if e["event_type"] == "hit_dice"]) == 1
    other = [e["description"] for e in await _feed(client, P2_ID, code) if e["event_type"] == "hit_dice"]
    assert other == ["ha speso un dado vita"]

    act(PLAYER_ID)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 3, "damage_type": "slashing"})
    assert r.status_code == 200, r.text
    seen = [e["description"] for e in await _feed(client, P2_ID, code) if e["event_type"] == "hp_change"]
    assert "ha subito 3 danni da Taglio" in seen


def test_option_names_reads_the_label_and_keeps_unknown_keys(monkeypatch):
    from core.rules import roll_options
    from core.rules.catalog.y2014.rogue import SNEAK_ATTACK
    monkeypatch.setattr(roll_options, "_specs_by_key", lambda _char: {SNEAK_ATTACK.key: SNEAK_ATTACK})
    assert option_names(None, [SNEAK_ATTACK.key, "mystery.key"]) == "Attacco Furtivo, mystery.key"
