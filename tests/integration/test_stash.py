"""Party stash inside a live campaign session: players put/take, the GM adds/removes."""
from __future__ import annotations

import json

from sqlalchemy import select

from core.db.models import Campaign, Currency, Item, SessionMessage
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID
from tests.integration.test_campaigns_api import STRANGER_ID, _enrolled, act


async def _setup(client, factory):
    """Campaign + live session, PLAYER joined with a PG holding items and gold.

    Returns (sid, pg_id, stash_id, ids) with ids = rope/sword/bag/coin item ids.
    """
    camp, pg = await _enrolled(client, factory)
    act(GM_ID)
    sid = (await client.post("/sessions", json={"campaign_id": camp["id"]})).json()["id"]
    act(PLAYER_ID)
    r = await client.post(f"/campaigns/{camp['id']}/session/join", json={"character_id": pg})
    assert r.status_code == 200, r.text
    async with factory() as s:
        stash_id = (await s.get(Campaign, camp["id"])).stash_character_id
        rope = Item(character_id=pg, name="Corda", item_type="generic", quantity=5)
        sword = Item(character_id=pg, name="Spada", item_type="weapon")
        bag = Item(character_id=pg, name="Zaino", item_type="generic", weight=1.0,
                   item_metadata=json.dumps({"container": {"capacity_lb": 50, "coins": {"gold": 7}}}))
        s.add_all([rope, sword, bag])
        await s.flush()
        gem = Item(character_id=pg, name="Gemma", item_type="generic", container_id=bag.id)
        s.add(gem)
        s.add(Currency(character_id=pg, gold=10))
        await s.commit()
        ids = {"rope": rope.id, "sword": sword.id, "bag": bag.id, "gem": gem.id}
    return sid, pg, stash_id, ids


async def _stash_state(factory, stash_id):
    async with factory() as s:
        items = (await s.execute(select(Item).where(Item.character_id == stash_id).order_by(Item.id))).scalars().all()
        cur = (await s.execute(select(Currency).where(Currency.character_id == stash_id))).scalar_one()
        return [(i.id, i.name, i.quantity, i.container_id) for i in items], cur.gold


async def _kinds(factory):
    async with factory() as s:
        rows = (await s.execute(select(SessionMessage).order_by(SessionMessage.id))).scalars().all()
    return rows


async def test_get_stash_and_access(client, test_session_factory):
    sid, pg, stash_id, ids = await _setup(client, test_session_factory)
    for uid in (GM_ID, PLAYER_ID):
        act(uid)
        r = await client.get(f"/sessions/{sid}/stash")
        assert r.status_code == 200 and r.json()["items"] == []
        assert r.json()["currency"]["gold"] == 0
    act(STRANGER_ID)
    assert (await client.get(f"/sessions/{sid}/stash")).status_code == 403


async def test_no_campaign(client, test_session_factory):
    act(GM_ID)
    s = (await client.post("/sessions", json={"title": "x"})).json()
    r = await client.get(f"/sessions/{s['id']}/stash")
    assert r.status_code == 422 and r.json()["detail"] == "no_campaign"
    r = await client.post(f"/sessions/{s['id']}/stash/gm-add", json={"coins": {"gold": 1}})
    assert r.status_code == 422 and r.json()["detail"] == "no_campaign"


async def test_put_take_item_and_feed(client, test_session_factory):
    f = test_session_factory
    sid, pg, stash_id, ids = await _setup(client, f)
    act(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/stash/put", json={
        "from_character_id": pg, "item_id": ids["rope"], "quantity": 2})
    assert r.status_code == 200, r.text
    assert next(i for i in r.json()["items"] if i["id"] == ids["rope"])["quantity"] == 3
    st, _ = await _stash_state(f, stash_id)
    assert [(n, q) for _i, n, q, _c in st] == [("Corda", 2)]
    # stash row, then take it back: merges into the PG's generic stack
    stash_rope = st[0][0]
    r = await client.post(f"/sessions/{sid}/stash/take", json={"to_character_id": pg, "item_id": stash_rope})
    assert r.status_code == 200, r.text
    assert next(i for i in r.json()["items"] if i["id"] == ids["rope"])["quantity"] == 5
    assert (await _stash_state(f, stash_id))[0] == []
    msgs = await _kinds(f)
    assert [json.loads(m.trade_payload)["kind"] for m in msgs] == ["stash_put", "stash_take"]
    p = json.loads(msgs[0].trade_payload)
    assert p["from"] == {"character_id": pg, "name": "Eroe"}
    assert p["to"] == {"character_id": None, "name": "stash"}
    assert msgs[0].body == "Eroe ha messo nel deposito: Corda (×2)"
    assert msgs[1].body == "Eroe ha preso dal deposito: Corda (×2)"
    assert msgs[0].item_id is None and msgs[0].recipient_user_id is None
    assert json.loads(msgs[1].trade_payload)["to"]["character_id"] == pg


async def test_put_take_full_container(client, test_session_factory):
    f = test_session_factory
    sid, pg, stash_id, ids = await _setup(client, f)
    act(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/stash/put", json={"from_character_id": pg, "item_id": ids["bag"]})
    assert r.status_code == 200, r.text
    st, _ = await _stash_state(f, stash_id)
    assert {(i, c) for i, _n, _q, c in st} == {(ids["bag"], None), (ids["gem"], ids["bag"])}
    r = await client.post(f"/sessions/{sid}/stash/take", json={"to_character_id": pg, "item_id": ids["bag"]})
    assert r.status_code == 200, r.text
    assert (await _stash_state(f, stash_id))[0] == []
    async with f() as s:
        bag = await s.get(Item, ids["bag"])
        gem = await s.get(Item, ids["gem"])
        assert bag.character_id == pg and gem.character_id == pg and gem.container_id == bag.id
        assert json.loads(bag.item_metadata)["container"]["coins"]["gold"] == 7


async def test_put_take_coins(client, test_session_factory):
    f = test_session_factory
    sid, pg, stash_id, ids = await _setup(client, f)
    act(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/stash/put", json={"from_character_id": pg, "coins": {"gold": 12}})
    assert r.status_code == 200, r.text  # 10 purse + 2 from the bag
    assert (await _stash_state(f, stash_id))[1] == 12
    r = await client.post(f"/sessions/{sid}/stash/take", json={"to_character_id": pg, "coins": {"gold": 13}})
    assert r.status_code == 409 and r.json()["detail"] == "insufficient_funds"
    assert (await _stash_state(f, stash_id))[1] == 12
    r = await client.post(f"/sessions/{sid}/stash/take", json={"to_character_id": pg, "coins": {"gold": 5}})
    assert r.status_code == 200 and r.json()["currency"]["gold"] == 5
    assert (await _stash_state(f, stash_id))[1] == 7
    assert (await _kinds(f))[0].body == "Eroe ha messo nel deposito: 12 oro"


async def test_take_already_taken_404(client, test_session_factory):
    f = test_session_factory
    sid, pg, stash_id, ids = await _setup(client, f)
    act(PLAYER_ID)
    await client.post(f"/sessions/{sid}/stash/put", json={"from_character_id": pg, "item_id": ids["sword"]})
    body = {"to_character_id": pg, "item_id": ids["sword"]}
    assert (await client.post(f"/sessions/{sid}/stash/take", json=body)).status_code == 200
    r = await client.post(f"/sessions/{sid}/stash/take", json=body)
    assert r.status_code == 404
    assert len(await _kinds(f)) == 2


async def test_forbidden_paths(client, test_session_factory):
    f = test_session_factory
    sid, pg, stash_id, ids = await _setup(client, f)
    put = {"from_character_id": pg, "item_id": ids["sword"]}
    act(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/stash/put", json={**put, "from_character_id": pg + 99})
    assert r.status_code == 403 and r.json()["detail"] == "not_your_character"
    r = await client.post(f"/sessions/{sid}/stash/take", json={"to_character_id": pg + 99, "coins": {"gold": 1}})
    assert r.status_code == 403
    r = await client.post(f"/sessions/{sid}/stash/put", json={"from_character_id": pg})
    assert r.status_code == 422 and r.json()["detail"] == "nothing_to_give"
    for path, body in (("gm-add", {"coins": {"gold": 1}}), ("gm-remove", {"coins": {"gold": 1}})):
        r = await client.post(f"/sessions/{sid}/stash/{path}", json=body)
        assert r.status_code == 403 and r.json()["detail"] == "gm_only"
    act(GM_ID)
    r = await client.post(f"/sessions/{sid}/stash/put", json=put)
    assert r.status_code == 403 and r.json()["detail"] == "not_your_character"
    r = await client.post(f"/sessions/{sid}/stash/take", json={"to_character_id": pg, "coins": {"gold": 1}})
    assert r.status_code == 403
    act(STRANGER_ID)
    assert (await client.post(f"/sessions/{sid}/stash/put", json=put)).status_code == 403
    assert (await client.post(f"/sessions/{sid}/stash/gm-add", json={"coins": {"gold": 1}})).status_code == 403
    assert (await _stash_state(f, stash_id)) == ([], 0)
    assert await _kinds(f) == []


async def test_gm_add_and_remove(client, test_session_factory):
    f = test_session_factory
    sid, pg, stash_id, ids = await _setup(client, f)
    act(GM_ID)
    url = f"/sessions/{sid}/stash"
    r = await client.post(f"{url}/gm-add", json={"item": {"name": "Torcia", "quantity": 3}})
    assert r.status_code == 200, r.text
    assert [(i["name"], i["quantity"]) for i in r.json()["items"]] == [("Torcia", 3)]
    r = await client.post(f"{url}/gm-add", json={"item": {"name": "Torcia", "quantity": 2}, "coins": {"gold": 20}})
    assert r.status_code == 422 and r.json()["detail"] == "nothing_to_give"  # item xor coins
    r = await client.post(f"{url}/gm-add", json={"item": {"name": "Torcia", "quantity": 2}})
    assert [(i["name"], i["quantity"]) for i in r.json()["items"]] == [("Torcia", 5)]
    r = await client.post(f"{url}/gm-add", json={"item": {
        "name": "Cassa", "quantity": 2, "item_metadata": {"container": {"capacity_lb": 10}}}})
    assert r.status_code == 422 and r.json()["detail"] == "container_quantity"
    r = await client.post(f"{url}/gm-add", json={"coins": {"gold": 20}})
    assert r.json()["currency"]["gold"] == 20
    st, gold = await _stash_state(f, stash_id)
    assert gold == 20 and st[0][1:3] == ("Torcia", 5)
    r = await client.post(f"{url}/gm-remove", json={"item_id": st[0][0], "quantity": 2})
    assert r.json()["items"][0]["quantity"] == 3
    r = await client.post(f"{url}/gm-remove", json={"coins": {"gold": 21}})
    assert r.status_code == 409
    assert (await _stash_state(f, stash_id))[1] == 20
    r = await client.post(f"{url}/gm-remove", json={"coins": {"gold": 20}})
    assert r.json()["currency"]["gold"] == 0
    r = await client.post(f"{url}/gm-remove", json={"item_id": st[0][0]})
    assert r.json()["items"] == []
    msgs = await _kinds(f)
    kinds = [json.loads(m.trade_payload)["kind"] for m in msgs]
    assert kinds[0] == "gm_stash_add" and kinds[-1] == "gm_stash_remove"
    assert msgs[0].body == "Il master ha messo nel deposito: Torcia (×3)"
    assert msgs[-1].body == "Il master ha tolto dal deposito: Torcia (×3)"
    p = json.loads(msgs[0].trade_payload)
    assert p["from"] == {"character_id": None, "name": "gm"}
    assert p["to"] == {"character_id": None, "name": "stash"}


async def test_gm_remove_container_whole_tree(client, test_session_factory):
    f = test_session_factory
    sid, pg, stash_id, ids = await _setup(client, f)
    act(PLAYER_ID)
    await client.post(f"/sessions/{sid}/stash/put", json={"from_character_id": pg, "item_id": ids["bag"]})
    act(GM_ID)
    url = f"/sessions/{sid}/stash/gm-remove"
    r = await client.post(url, json={"item_id": ids["bag"]})
    assert r.status_code == 200 and r.json()["items"] == []
    async with f() as s:
        assert await s.get(Item, ids["gem"]) is None


async def test_gm_remove_errors_leave_stash(client, test_session_factory):
    f = test_session_factory
    sid, pg, stash_id, ids = await _setup(client, f)
    act(PLAYER_ID)
    await client.post(f"/sessions/{sid}/stash/put", json={"from_character_id": pg, "item_id": ids["rope"]})
    before = await _stash_state(f, stash_id)
    act(GM_ID)
    url = f"/sessions/{sid}/stash/gm-remove"
    assert (await client.post(url, json={"item_id": ids["rope"], "quantity": 9})).status_code == 422
    assert (await client.post(url, json={"item_id": 999999})).status_code == 404
    assert (await client.post(url, json={})).status_code == 422
    assert await _stash_state(f, stash_id) == before
