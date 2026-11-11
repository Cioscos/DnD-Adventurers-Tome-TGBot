"""Minori 3.1.1: COS con Aiuto, annullo + forma selvatica scaduta, lock e Telegram, import con riposo futuro, prove senza critico."""
from __future__ import annotations

from core.db.models import Character


async def _fighter(client, level: int = 3) -> int:
    r = await client.post("/characters", json={"name": "Min", "initial_class": {"class_name": "Guerriero", "level": level, "hit_die": 10}})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_con_drop_keeps_hp_above_base_max_given_by_aid(client, test_session_factory):
    cid = await _fighter(client)
    async with test_session_factory() as s:
        c = await s.get(Character, cid)
        c.active_states = [{"key": "spell:aid", "name": "Aid", "data": {"spell_key": "aid", "slot_level": 2, "edition": "2014"}}]
        c.current_hit_points = c.hit_points + 5
        base = c.hit_points
        await s.commit()
    r = await client.patch(f"/characters/{cid}/ability_scores/constitution", json={"value": 8})  # mod -1 x 3 livelli
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["hit_points"] == base - 3
    assert body["current_hit_points"] == base + 5 - 3  # 32/32 dell'esempio, non il massimo base


async def test_undo_advance_reopens_wild_shape_that_expired(client, test_session_factory, monkeypatch):
    from api.services.wild_shape import get_active_form
    from core.db.models import Companion
    from tests.integration.test_condition_time import _advance, _start
    from tests.integration.test_condition_undo import _back
    _, sid, _enc, cid, *_ = await _start(client, test_session_factory, monkeypatch)
    async with test_session_factory() as s:
        form = Companion(character_id=cid, kind="wild_shape", name="Orso", statblock={}, max_hp=10, current_hp=7, armor_class=11,
                         is_active=True, created_at="2026-01-01T00:00:00")
        s.add(form)
        await s.flush()
        ch = await s.get(Character, cid)
        ch.active_states = [{"key": "wild_shape", "name": "Forma selvatica", "ends_on": ["manual"], "rounds_left": 1,
                             "data": {"companion_id": form.id, "own_hp": True}}]
        fid = form.id
        await s.commit()
    await _advance(client, sid, 3)  # -> PG: la forma scade
    async with test_session_factory() as s:
        assert await get_active_form(s, cid) is None
    await _back(client, sid)
    async with test_session_factory() as s:
        form = await get_active_form(s, cid)
        assert form is not None and form.id == fid and form.current_hp == 7


async def test_party_emergency_does_not_wait_for_telegram(client, test_session_factory, monkeypatch):
    import asyncio
    import api.services.telegram_notify as tn
    from tests.integration._encounter_helpers import PLAYER_ID, as_user
    from tests.integration.test_notify_party_emergency import _seed
    started = asyncio.Event()

    async def hung(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()  # Telegram che non risponde

    monkeypatch.setattr(tn, "send_telegram_message", hung)
    cid = await _seed(test_session_factory)
    as_user(PLAYER_ID)
    try:
        r = await asyncio.wait_for(client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 99}), timeout=3)
        assert r.status_code == 200, r.text
        await asyncio.wait_for(started.wait(), timeout=3)  # l'invio parte comunque, staccato
    finally:
        for t in list(tn._BACKGROUND):
            t.cancel()


async def test_dice_post_and_export_send_skip_the_write_lock():
    import asyncio
    from starlette.requests import Request
    from api.locks import character_write_lock

    def req(path: str) -> Request:
        return Request({"type": "http", "method": "POST", "path": path, "path_params": {"char_id": "1"}, "headers": []})

    holder = character_write_lock(req("/characters/1/spells"))
    await holder.__anext__()  # tiene il lock del personaggio 1
    try:
        for path in ("/characters/1/dice/post-to-chat", "/characters/1/export/send"):
            gen = character_write_lock(req(path))
            await asyncio.wait_for(gen.__anext__(), timeout=1)  # non aspetta il lock tenuto
            await gen.aclose()
    finally:
        await holder.aclose()


async def test_import_drops_a_last_long_rest_in_the_future(client, test_session_factory):
    from datetime import datetime, timedelta
    from tests.integration.test_character_import import _export, _import, _make_valid
    cid = await _make_valid(test_session_factory)
    payload = await _export(client, cid)
    payload["character"]["last_long_rest_at"] = (datetime.utcnow() + timedelta(days=30)).isoformat(timespec="seconds")
    new = (await _import(client, payload)).json()["id"]
    async with test_session_factory() as s:
        assert (await s.get(Character, new)).last_long_rest_at is None
