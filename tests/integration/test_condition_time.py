"""Il tempo delle condizioni: bordi di turno, tick manuale, fine incontro (spec §2)."""
from __future__ import annotations

from sqlalchemy import select

from api.services.condition_effects import (
    ExpirySpec, SaveSpec, effects_for_character, upsert_effect,
)
from core.db.models import Character, Encounter, PendingSave
from tests.integration._encounter_helpers import (
    GM_ID, PLAYER_ID, as_user, setup_full_encounter,
)
from tests.integration._telegram_stub import install_fake_telegram


async def _start(client, test_session_factory, monkeypatch):
    """Incontro attivo, turno del PG. Ritorna (sid, enc_id, char_id, pc_id, g1_id, g2_id)."""
    captured = install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)
    r = await client.post(f"/sessions/{sid}/encounter/start", json={})
    assert r.status_code == 200, r.text
    enc = r.json()
    pc, g1, g2 = enc["combatants"]
    async with test_session_factory() as s:
        enc_id = (await s.execute(select(Encounter.id))).scalar_one()
        cid = (await s.execute(select(Character.id))).scalar_one()
    return captured, sid, enc_id, cid, pc["id"], g1["id"], g2["id"]


async def _add_effect(test_session_factory, cid, slug="poisoned", *, enc_id=None, **kw):
    async with test_session_factory() as s:
        ch = await s.get(Character, cid)
        ch.conditions = {**(ch.conditions or {}), slug: True}
        enc = await s.get(Encounter, enc_id) if enc_id else None
        await upsert_effect(s, ("character", cid), slug, encounter=enc, **kw)
        await s.commit()


async def _advance(client, sid, n=1):
    as_user(GM_ID)
    for _ in range(n):
        r = await client.post(f"/sessions/{sid}/encounter/next-turn")
        assert r.status_code == 200, r.text


async def _state(test_session_factory, cid):
    async with test_session_factory() as s:
        ch = await s.get(Character, cid)
        effects = {e.slug: e.expiry_count for e in await effects_for_character(s, cid)}
        saves = list((await s.execute(select(PendingSave).where(
            PendingSave.character_id == cid))).scalars())
        return ch.conditions or {}, effects, saves


async def test_owner_start_expires_on_own_turn(client, test_session_factory, monkeypatch):
    _, sid, enc_id, cid, *_ = await _start(client, test_session_factory, monkeypatch)
    await _add_effect(test_session_factory, cid, expiry=ExpirySpec("owner", "start", 1))
    await _advance(client, sid, 2)  # PG -> g1 -> g2: nessun bordo del PG di tipo start
    conds, effects, _ = await _state(test_session_factory, cid)
    assert conds["poisoned"] is True and effects == {"poisoned": 1}
    await _advance(client, sid)  # -> PG: inizio turno, scade
    conds, effects, _ = await _state(test_session_factory, cid)
    assert conds["poisoned"] is False and effects == {}
    as_user(PLAYER_ID)
    hist = (await client.get(f"/characters/{cid}/history")).json()
    assert any(h["description"] == "Durata scaduta: Avvelenato" for h in hist)
    async with test_session_factory() as s:
        undo = (await s.get(Encounter, enc_id)).last_advance_undo
    assert [e["slug"] for e in undo["expired"]] == ["poisoned"]


async def test_end_of_next_turn_applied_on_own_turn_skips_current(
    client, test_session_factory, monkeypatch,
):
    _, sid, enc_id, cid, *_ = await _start(client, test_session_factory, monkeypatch)
    await _add_effect(test_session_factory, cid, enc_id=enc_id,
                      expiry=ExpirySpec("owner", "end", 1))
    await _advance(client, sid)  # fine del turno in corso: non è "il prossimo"
    conds, effects, _ = await _state(test_session_factory, cid)
    assert conds["poisoned"] is True and effects == {"poisoned": 1}
    await _advance(client, sid, 3)  # g1 -> g2 -> PG -> fine turno PG
    conds, effects, _ = await _state(test_session_factory, cid)
    assert conds["poisoned"] is False and effects == {}


async def test_source_anchor_falls_back_when_source_removed(
    client, test_session_factory, monkeypatch,
):
    _, sid, enc_id, cid, _pc, g1, _g2 = await _start(client, test_session_factory, monkeypatch)
    await _add_effect(test_session_factory, cid, expiry=ExpirySpec("source", "start", 1),
                      source_combatant_id=g1)
    as_user(GM_ID)
    r = await client.delete(f"/sessions/{sid}/encounter/combatants/{g1}")
    assert r.status_code == 200, r.text
    await _advance(client, sid)  # PG -> g2
    assert (await _state(test_session_factory, cid))[1] == {"poisoned": 1}
    await _advance(client, sid)  # -> PG: la fonte non c'è più, ripiega su owner
    conds, effects, _ = await _state(test_session_factory, cid)
    assert conds["poisoned"] is False and effects == {}


async def test_source_anchor_ticks_on_source_turn(client, test_session_factory, monkeypatch):
    _, sid, enc_id, cid, _pc, g1, _g2 = await _start(client, test_session_factory, monkeypatch)
    await _add_effect(test_session_factory, cid, expiry=ExpirySpec("source", "start", 1),
                      source_combatant_id=g1)
    await _advance(client, sid)  # -> g1: inizio turno della fonte
    conds, effects, _ = await _state(test_session_factory, cid)
    assert conds["poisoned"] is False and effects == {}


async def test_save_created_once_per_effect(client, test_session_factory, monkeypatch):
    _, sid, enc_id, cid, *_ = await _start(client, test_session_factory, monkeypatch)
    await _add_effect(test_session_factory, cid, save=SaveSpec("constitution", 13, "end"))
    await _advance(client, sid, 6)  # due giri completi, due fini turno del PG
    _, _, saves = await _state(test_session_factory, cid)
    assert [(p.status, p.ability, p.dc) for p in saves] == [("pending", "constitution", 13)]


async def test_save_skip_once_when_applied_on_own_turn(client, test_session_factory, monkeypatch):
    _, sid, enc_id, cid, *_ = await _start(client, test_session_factory, monkeypatch)
    await _add_effect(test_session_factory, cid, enc_id=enc_id,
                      save=SaveSpec("constitution", 13, "end"))
    await _advance(client, sid)  # fine del turno in cui è stata applicata: niente TS
    assert (await _state(test_session_factory, cid))[2] == []
    await _advance(client, sid, 3)
    assert len((await _state(test_session_factory, cid))[2]) == 1


async def test_expiry_before_save_on_same_edge(client, test_session_factory, monkeypatch):
    _, sid, enc_id, cid, *_ = await _start(client, test_session_factory, monkeypatch)
    await _add_effect(test_session_factory, cid, expiry=ExpirySpec("owner", "end", 1),
                      save=SaveSpec("constitution", 13, "end"))
    await _advance(client, sid)
    conds, effects, saves = await _state(test_session_factory, cid)
    assert conds["poisoned"] is False and effects == {} and saves == []


async def test_manual_tick_rejected_in_encounter(client, test_session_factory, monkeypatch):
    _, sid, enc_id, cid, *_ = await _start(client, test_session_factory, monkeypatch)
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{cid}/rounds/tick")
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "in_encounter"


async def test_manual_tick_after_encounter_end(client, test_session_factory, monkeypatch):
    _, sid, enc_id, cid, *_ = await _start(client, test_session_factory, monkeypatch)
    await _add_effect(test_session_factory, cid, expiry=ExpirySpec("owner", "end", 2))
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/end")).status_code == 200
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{cid}/rounds/tick")
    assert r.status_code == 200, r.text
    assert r.json()["conditions"]["poisoned"] is True
    r = await client.post(f"/characters/{cid}/rounds/tick")
    assert r.json()["conditions"]["poisoned"] is False
    assert r.json()["expired_effects"] == ["Avvelenato"]


async def test_save_notification_sent(client, test_session_factory, monkeypatch):
    captured, sid, enc_id, cid, *_ = await _start(client, test_session_factory, monkeypatch)
    await _add_effect(test_session_factory, cid, save=SaveSpec("wisdom", 14, "end"))
    captured.clear()
    await _advance(client, sid)
    msgs = [c["json"] for c in captured if "Tiro salvezza" in c["json"]["text"]]
    assert len(msgs) == 1
    assert msgs[0]["chat_id"] == PLAYER_ID
    assert msgs[0]["text"] == "🎲 Tiro salvezza: Saggezza CD 14 per liberarti da Avvelenato"
