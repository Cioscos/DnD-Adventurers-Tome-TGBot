"""Turno indietro: annulla l'ultimo avanzamento (spec §2 "Turno indietro", "Conflitti")."""
from __future__ import annotations

from sqlalchemy import select

from api.services.condition_effects import ExpirySpec, SaveSpec
from core.db.models import Encounter, PendingSave
from tests.integration._encounter_helpers import GM_ID, as_user
from tests.integration.test_condition_time import _add_effect, _advance, _start, _state


async def _back(client, sid):
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter/prev-turn")
    assert r.status_code == 200, r.text
    return r.json()


async def test_back_restores_expired_condition(client, test_session_factory, monkeypatch):
    _, sid, enc_id, cid, _pc, _g1, g2 = await _start(client, test_session_factory, monkeypatch)
    await _add_effect(test_session_factory, cid, expiry=ExpirySpec("owner", "start", 1))
    await _advance(client, sid, 3)  # -> PG: scade
    assert (await _state(test_session_factory, cid))[1] == {}
    enc = await _back(client, sid)
    assert enc["active_combatant_id"] == g2
    conds, effects, _ = await _state(test_session_factory, cid)
    assert conds["poisoned"] is True and effects == {"poisoned": 1}
    async with test_session_factory() as s:
        assert (await s.get(Encounter, enc_id)).last_advance_undo is None


async def test_back_deletes_created_pending_save(client, test_session_factory, monkeypatch):
    _, sid, enc_id, cid, *_ = await _start(client, test_session_factory, monkeypatch)
    await _add_effect(test_session_factory, cid, save=SaveSpec("constitution", 13, "end"))
    await _advance(client, sid)  # fine turno PG: TS creato
    assert len((await _state(test_session_factory, cid))[2]) == 1
    await _back(client, sid)
    assert (await _state(test_session_factory, cid))[2] == []


async def test_back_skips_rolled_save(client, test_session_factory, monkeypatch):
    _, sid, enc_id, cid, *_ = await _start(client, test_session_factory, monkeypatch)
    await _add_effect(test_session_factory, cid, save=SaveSpec("constitution", 13, "end"))
    await _advance(client, sid)
    async with test_session_factory() as s:
        ps = (await s.execute(select(PendingSave))).scalar_one()
        ps.status = "failed"
        await s.commit()
    await _back(client, sid)
    _, _, saves = await _state(test_session_factory, cid)
    assert [p.status for p in saves] == ["failed"]


async def test_second_back_only_moves_pointer(client, test_session_factory, monkeypatch):
    _, sid, enc_id, cid, _pc, g1, g2 = await _start(client, test_session_factory, monkeypatch)
    await _add_effect(test_session_factory, cid, expiry=ExpirySpec("owner", "start", 2))
    await _advance(client, sid, 3)  # -> PG: 2 -> 1
    assert (await _state(test_session_factory, cid))[1] == {"poisoned": 1}
    assert (await _back(client, sid))["active_combatant_id"] == g2
    assert (await _state(test_session_factory, cid))[1] == {"poisoned": 2}
    assert (await _back(client, sid))["active_combatant_id"] == g1
    assert (await _state(test_session_factory, cid))[1] == {"poisoned": 2}


async def test_back_restores_pending_save_of_expired_effect(
    client, test_session_factory, monkeypatch,
):
    _, sid, enc_id, cid, *_ = await _start(client, test_session_factory, monkeypatch)
    await _add_effect(test_session_factory, cid, expiry=ExpirySpec("owner", "start", 1),
                      save=SaveSpec("constitution", 13, "end"))
    await _advance(client, sid)  # fine turno PG: TS creato
    save_id = (await _state(test_session_factory, cid))[2][0].id
    await _advance(client, sid, 2)  # -> PG: scade, il TS sparisce con l'effetto
    assert (await _state(test_session_factory, cid))[2] == []
    await _back(client, sid)
    conds, effects, saves = await _state(test_session_factory, cid)
    assert conds["poisoned"] is True and effects == {"poisoned": 1}
    assert [(p.id, p.status) for p in saves] == [(save_id, "pending")]


async def test_back_skips_reapplied_condition(client, test_session_factory, monkeypatch):
    _, sid, enc_id, cid, *_ = await _start(client, test_session_factory, monkeypatch)
    await _add_effect(test_session_factory, cid, expiry=ExpirySpec("owner", "start", 1))
    await _advance(client, sid, 3)
    await _add_effect(test_session_factory, cid, expiry=ExpirySpec("owner", "end", 5))
    await _back(client, sid)
    conds, effects, _ = await _state(test_session_factory, cid)
    assert conds["poisoned"] is True and effects == {"poisoned": 5}


async def test_back_restores_concentration_rounds(client, test_session_factory, monkeypatch):
    from core.db.models import Character
    _, sid, enc_id, cid, *_ = await _start(client, test_session_factory, monkeypatch)
    item_spell = {"item_id": 1, "name": "Luce"}
    async with test_session_factory() as s:
        ch = await s.get(Character, cid)
        ch.settings = {"concentration_rounds_left": 1, "concentration_item_spell": item_spell}
        await s.commit()
    await _advance(client, sid, 3)  # -> PG: concentrazione scade
    async with test_session_factory() as s:
        assert "concentration_item_spell" not in ((await s.get(Character, cid)).settings or {})
    await _back(client, sid)
    async with test_session_factory() as s:
        settings = (await s.get(Character, cid)).settings
    assert settings["concentration_rounds_left"] == 1
    assert settings["concentration_item_spell"] == item_spell
