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
