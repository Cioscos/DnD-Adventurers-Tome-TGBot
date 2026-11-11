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


async def test_undo_advance_does_not_reopen_wild_shape_ended_after_the_advance(client, test_session_factory, monkeypatch):
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
        ch.active_states = [{"key": "wild_shape", "name": "Forma selvatica", "ends_on": ["manual"], "rounds_left": 5,
                             "data": {"companion_id": form.id, "own_hp": True}}]
        await s.commit()
    await _advance(client, sid, 3)  # -> PG: 5 -> 4, la forma resta
    async with test_session_factory() as s:
        assert await get_active_form(s, cid) is not None
        ch = await s.get(Character, cid)
        ch.active_states = [x for x in ch.active_states if x.get("key") != "wild_shape"]  # finita a mano dopo l'avanzamento
        await s.commit()
    async with test_session_factory() as s:
        assert await get_active_form(s, cid) is None
    await _back(client, sid)
    async with test_session_factory() as s:
        assert await get_active_form(s, cid) is None


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


async def test_ability_based_checks_have_no_critical_on_a_natural_20(client):
    cid = await _fighter(client, 1)
    for url in (f"/characters/{cid}/skills/stealth/roll", f"/characters/{cid}/ability_checks/strength/roll", f"/characters/{cid}/dice/initiative"):
        r = await client.post(url, json={"die": 20})
        assert r.status_code == 200, r.text
        assert r.json()["die"] == 20 and r.json()["is_critical"] is False, url
    r = await client.post(f"/characters/{cid}/saving_throws/strength/roll", json={"die": 20})
    assert r.json()["is_critical"] is True  # i tiri salvezza non cambiano


async def test_feat_con_increase_keeps_hp_above_base_max_given_by_aid(client, test_session_factory, rules_catalog):
    from tests.integration.rules.test_class_mechanisms import _fighter as _fighter_con, _spec
    cid = await _fighter_con(client, 4, constitution=12)
    async with test_session_factory() as s:
        c = await s.get(Character, cid)
        c.active_states = [{"key": "spell:aid", "name": "Aid", "data": {"spell_key": "aid", "slot_level": 2, "edition": "2014"}}]
        c.current_hit_points = c.hit_points + 5
        base = c.hit_points
        await s.commit()
    rules_catalog(_spec(level=1, ability_bonus={"constitution": 2}, ability_cap=24))  # il talento arriva ora: COS 12 -> 14
    r = await client.patch(f"/characters/{cid}/ability_scores/strength", json={"value": 11})  # qualunque sync lo applica
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["hit_points"] == base + 4 and body["current_hit_points"] == base + 4 + 5  # il COS sale: Aiuto non si perde


async def test_hp_recalc_keeps_aid_hp_when_nothing_changed(client, test_session_factory):
    cid = await _fighter(client)
    async with test_session_factory() as s:
        c = await s.get(Character, cid)
        c.active_states = [{"key": "spell:aid", "name": "Aid", "data": {"spell_key": "aid", "slot_level": 2, "edition": "2014"}}]
        c.current_hit_points = c.hit_points + 5
        base = c.hit_points
        await s.commit()
    r = await client.post(f"/characters/{cid}/hp/recalc", json={})
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == base + 5


async def test_set_max_clamps_to_effective_max_including_aid(client, test_session_factory):
    cid = await _fighter(client)
    async with test_session_factory() as s:
        c = await s.get(Character, cid)
        c.active_states = [{"key": "spell:aid", "name": "Aid", "data": {"spell_key": "aid", "slot_level": 2, "edition": "2014"}}]
        c.hit_points, c.current_hit_points = 30, 35
        await s.commit()
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 28})
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == 33  # 28 + 5 di Aiuto, non 28


async def test_level_up_notification_does_not_wait_for_telegram(client, monkeypatch):
    import asyncio
    import api.services.telegram_notify as tn
    started = asyncio.Event()

    async def hung(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()  # Telegram che non risponde

    monkeypatch.setattr(tn, "send_telegram_message", hung)
    cid = await _fighter(client, 1)
    try:
        r = await asyncio.wait_for(client.patch(f"/characters/{cid}/xp", json={"set": 300}), timeout=3)
        assert r.status_code == 200, r.text
        await asyncio.wait_for(started.wait(), timeout=3)
    finally:
        for t in list(tn._BACKGROUND):
            t.cancel()
