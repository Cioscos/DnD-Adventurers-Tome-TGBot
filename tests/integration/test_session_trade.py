"""POST /sessions/{id}/trade: scambio PG -> PG con riga pubblica nel feed e notifica."""
from __future__ import annotations

import json

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from core.db.engine import _migrate_schema
from core.db.models import (
    AbilityScore, Base, Character, CharacterClass, Currency, EquipmentSlot, Item,
    SessionMessage, SessionParticipant, SessionRole,
)
from tests.integration._encounter_helpers import GM_ID, NOW, PLAYER_ID, as_user, seed_session
from tests.integration._telegram_stub import install_fake_telegram

PLAYER2_ID = 9999
CON_RING = {"ability_modifiers": [{"ability": "constitution", "kind": "relative", "value": 2}]}


async def _seed_trade(factory, *, equipped_con: bool = False):
    """Sessione di seed_session + Lyra (PLAYER2). Ritorna (sid, eroe_id, lyra_id, item_id)."""
    sid, hero = await seed_session(factory)
    async with factory() as s:
        lyra = Character(user_id=PLAYER2_ID, name="Lyra")
        s.add(lyra)
        await s.flush()
        s.add(SessionParticipant(
            session_id=sid, user_id=PLAYER2_ID, character_id=lyra.id,
            role=SessionRole.PLAYER, display_name="Lyra", joined_at=NOW,
        ))
        if equipped_con:
            s.add(AbilityScore(character_id=hero, name="constitution", value=10))
            s.add(CharacterClass(character_id=hero, class_name="fighter", level=2, hit_die=10))
            h = await s.get(Character, hero)
            h.hit_points, h.current_hit_points = 20, 20
            item = Item(character_id=hero, name="Anello del Vigore", item_type="accessory",
                        item_metadata=json.dumps(CON_RING), is_equipped=True,
                        equipment_slot=EquipmentSlot.RING1)
        else:
            item = Item(character_id=hero, name="Corda", item_type="generic", quantity=3)
        s.add(item)
        s.add(Currency(character_id=hero, gold=10))
        await s.commit()
        return sid, hero, lyra.id, item.id


async def _owner(factory, item_id: int) -> int:
    async with factory() as s:
        return (await s.get(Item, item_id)).character_id


async def _feed(client, uid: int) -> list[dict]:
    as_user(uid)
    r = await client.get("/sessions/ABC123/feed")
    assert r.status_code == 200, r.text
    return r.json()["items"]


async def test_trade_item_moves_and_posts_public_message(client, test_session_factory, monkeypatch):
    install_fake_telegram(monkeypatch)
    sid, hero, lyra, item_id = await _seed_trade(test_session_factory)
    as_user(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/trade", json={
        "from_character_id": hero, "to_user_id": PLAYER2_ID, "item_id": item_id})
    assert r.status_code == 200, r.text
    assert not any(i["id"] == item_id for i in r.json()["items"])
    assert await _owner(test_session_factory, item_id) == lyra
    async with test_session_factory() as s:
        msg = (await s.execute(select(SessionMessage))).scalar_one()
    assert msg.recipient_user_id is None and msg.user_id == PLAYER_ID
    assert msg.item_id is None and msg.item_name is None and msg.item_quantity is None
    payload = json.loads(msg.trade_payload)
    assert payload["from"] == {"character_id": hero, "name": "Eroe"}
    assert payload["to"] == {"character_id": lyra, "name": "Lyra"}
    assert payload["coins"] == {} and payload["items"][0]["name"] == "Corda"
    assert payload["items"][0]["quantity"] == 3
    trades = [i["trade"] for i in await _feed(client, GM_ID) if i.get("trade")]
    assert trades[0]["to"]["name"] == "Lyra"


async def test_trade_notifies_recipient(client, test_session_factory, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    sid, hero, lyra, item_id = await _seed_trade(test_session_factory)
    as_user(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/trade", json={
        "from_character_id": hero, "to_user_id": PLAYER2_ID, "item_id": item_id})
    assert r.status_code == 200, r.text
    msgs = [c["json"] for c in captured if c["json"]["chat_id"] == PLAYER2_ID]
    assert len(msgs) == 1 and "Corda" in msgs[0]["text"]
    url = msgs[0]["reply_markup"]["inline_keyboard"][0][0]["web_app"]["url"]
    assert url.endswith(f"#/char/{lyra}/inventory")


async def test_trade_opt_out_is_silent_but_trades(client, test_session_factory, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    sid, hero, lyra, item_id = await _seed_trade(test_session_factory)
    async with test_session_factory() as s:
        (await s.get(Character, lyra)).settings = {"notifications": {"gm_events": False}}
        await s.commit()
    as_user(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/trade", json={
        "from_character_id": hero, "to_user_id": PLAYER2_ID, "item_id": item_id})
    assert r.status_code == 200, r.text
    assert captured == [] and await _owner(test_session_factory, item_id) == lyra


async def test_trade_rejects(client, test_session_factory, monkeypatch):
    install_fake_telegram(monkeypatch)
    sid, hero, lyra, item_id = await _seed_trade(test_session_factory)
    async with test_session_factory() as s:  # un giocatore senza PG
        s.add(SessionParticipant(session_id=sid, user_id=4242, role=SessionRole.PLAYER, joined_at=NOW))
        await s.commit()

    async def attempt(caller, **over):
        as_user(caller)
        body = {"from_character_id": hero, "to_user_id": PLAYER2_ID, "item_id": item_id, **over}
        return (await client.post(f"/sessions/{sid}/trade", json=body)).status_code

    assert await attempt(31337) == 403                       # non partecipante
    assert await attempt(PLAYER_ID, from_character_id=lyra) == 403   # PG non suo
    assert await attempt(PLAYER2_ID) == 403                  # PG di Lyra != hero
    assert await attempt(PLAYER_ID, to_user_id=GM_ID) == 422
    assert await attempt(PLAYER_ID, to_user_id=777) == 422
    assert await attempt(PLAYER_ID, to_user_id=4242) == 422
    assert await attempt(PLAYER_ID, to_user_id=PLAYER_ID) == 422
    assert await attempt(PLAYER_ID, coins={"gold": 1}) == 422        # item e coins insieme
    assert await attempt(PLAYER_ID, item_id=None) == 422             # niente da dare
    assert await _owner(test_session_factory, item_id) == hero

    async with test_session_factory() as s:
        from core.db.models import GameSession, SessionStatus
        (await s.get(GameSession, sid)).status = SessionStatus.CLOSED
        await s.commit()
    assert await attempt(PLAYER_ID) == 410
    assert await _owner(test_session_factory, item_id) == hero


async def test_trade_coins(client, test_session_factory, monkeypatch):
    install_fake_telegram(monkeypatch)
    sid, hero, lyra, _ = await _seed_trade(test_session_factory)
    as_user(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/trade", json={
        "from_character_id": hero, "to_user_id": PLAYER2_ID, "coins": {"gold": 5}})
    assert r.status_code == 200, r.text
    assert r.json()["currency"]["gold"] == 5
    trade = next(i["trade"] for i in await _feed(client, GM_ID) if i.get("trade"))
    assert trade["coins"] == {"gold": 5} and trade["items"] == []
    async with test_session_factory() as s:
        assert (await s.execute(select(Currency.gold).where(Currency.character_id == lyra))).scalar_one() == 5
    as_user(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/trade", json={
        "from_character_id": hero, "to_user_id": PLAYER2_ID, "coins": {"gold": 50}})
    assert r.status_code == 409


async def test_trade_equipped_con_item_recomputes_hp_and_dispatches(
        client, test_session_factory, monkeypatch):
    install_fake_telegram(monkeypatch)
    sid, hero, lyra, item_id = await _seed_trade(test_session_factory, equipped_con=True)
    calls = []

    async def fake_dispatch(db, char, event, ctx):
        calls.append((event, ctx))
        return []

    import api.routers.sessions as sessions_router
    monkeypatch.setattr(sessions_router, "dispatch", fake_dispatch)
    as_user(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/trade", json={
        "from_character_id": hero, "to_user_id": PLAYER2_ID, "item_id": item_id})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["unequipped_item_names"] == ["Anello del Vigore"]
    assert body["hit_points"] == 20 - 1 * 2  # CON 12 -> 10: mod -1, x 2 livelli
    assert [c[0] for c in calls] == ["item_unequipped"]
    assert calls[0][1]["item_id"] == item_id and calls[0][1]["slot"] == "ring1"
    async with test_session_factory() as s:
        moved = await s.get(Item, item_id)
        assert moved.character_id == lyra and not moved.is_equipped


async def test_migration_adds_trade_payload():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE session_messages DROP COLUMN trade_payload"))
        await conn.run_sync(_migrate_schema)
        await conn.run_sync(_migrate_schema)  # idempotente
        cols = {r[1] for r in await conn.execute(text("PRAGMA table_info(session_messages)"))}
    assert "trade_payload" in cols
