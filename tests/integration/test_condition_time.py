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
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/end")).status_code == 200
    await _add_effect(test_session_factory, cid, expiry=ExpirySpec("owner", "end", 2))  # fuori scontro: la fine lo toglierebbe
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


async def test_encounter_end_drops_round_durations(client, test_session_factory, monkeypatch):
    """B12 + L5: a fine scontro cadono le condizioni a round e quelle col TS ripetuto (fuori scontro nessuno lo chiede più);
    quelle senza durata né TS restano."""
    _, sid, enc_id, cid, *_ = await _start(client, test_session_factory, monkeypatch)
    await _add_effect(test_session_factory, cid, "frightened", enc_id=enc_id, expiry=ExpirySpec("owner", "end", 3),
                      save=SaveSpec("wisdom", 13, "end"))
    await _add_effect(test_session_factory, cid, "poisoned", save=SaveSpec("constitution", 13, "end"))
    async with test_session_factory() as s:
        ch = await s.get(Character, cid)
        ch.conditions = {**ch.conditions, "blinded": True}
        await s.commit()
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/end")).status_code == 200
    conds, effects, _ = await _state(test_session_factory, cid)
    assert conds["frightened"] is False and conds["poisoned"] is False and conds["blinded"] is True
    assert effects == {}


async def test_encounter_end_closes_states_of_a_minute_or_less(client, test_session_factory, monkeypatch):
    """L5: gli stati a round di un minuto o meno (Arma Consacrata, Benedizione) e la concentrazione che sta per finire
    chiudono con lo scontro; quelli più lunghi (Scudo della Fede, 10 minuti) e quelli senza durata restano."""
    _, sid, enc_id, cid, *_ = await _start(client, test_session_factory, monkeypatch)

    def st(key, rounds):
        return {"key": key, "feature_key": key, "rounds_left": rounds, "ends_on": ["manual"], "data": {}, "name": key}
    async with test_session_factory() as s:
        ch = await s.get(Character, cid)
        ch.active_states = [st("sacred_weapon", 9), st("long", 90), st("forever", None)]
        ch.settings = {**(ch.settings or {}), "concentration_rounds_left": 8}
        await s.commit()
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/end")).status_code == 200
    async with test_session_factory() as s:
        ch = await s.get(Character, cid)
        assert [x["key"] for x in ch.active_states] == ["long", "forever"]
        assert ch.active_states[0]["rounds_left"] == 90
        assert "concentration_rounds_left" not in (ch.settings or {})


async def test_gm_removes_a_condition_outside_combat(client, test_session_factory, monkeypatch):
    """L5: fuori combattimento il GM toglie una condizione a un PG seduto; un giocatore no."""
    _, sid, enc_id, cid, *_ = await _start(client, test_session_factory, monkeypatch)
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/end")).status_code == 200
    await _add_effect(test_session_factory, cid, "frightened")
    as_user(PLAYER_ID)
    assert (await client.delete(f"/sessions/{sid}/characters/{cid}/conditions/frightened")).status_code == 403
    as_user(GM_ID)
    r = await client.delete(f"/sessions/{sid}/characters/{cid}/conditions/frightened")
    assert r.status_code == 204, r.text
    conds, effects, _ = await _state(test_session_factory, cid)
    assert conds["frightened"] is False and effects == {}


async def test_escape_restrained_with_an_athletics_check(client, test_session_factory, monkeypatch):
    """U36: liberarsi da Trattenuto è un'azione con una prova contro la CD dell'effetto; riuscita, la condizione cade."""
    _, sid, enc_id, cid, *_ = await _start(client, test_session_factory, monkeypatch)
    await _add_effect(test_session_factory, cid, "restrained", save=SaveSpec("strength", 15, "end"))
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{cid}/conditions/restrained/escape?skill=athletics", json={"die": 2})
    assert r.status_code == 200, r.text
    assert r.json()["escaped"] is False and r.json()["dc"] == 15
    assert (await _state(test_session_factory, cid))[0]["restrained"] is True
    turn = (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]
    assert turn["action_used"] is True
    r = await client.post(f"/characters/{cid}/conditions/restrained/escape?skill=athletics", json={"die": 20})
    assert r.status_code == 409, r.text  # l'azione è già usata
    assert r.json()["detail"]["code"] == "turn_slot_used"
    await _advance(client, sid, 3)  # di nuovo il turno del PG
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{cid}/conditions/restrained/escape?skill=acrobatics", json={"die": 20})
    assert r.status_code == 200, r.text
    assert r.json()["escaped"] is True
    conds, effects, _ = await _state(test_session_factory, cid)
    assert conds["restrained"] is False and "restrained" not in effects


async def test_escape_needs_a_dc(client, test_session_factory, monkeypatch):
    _, sid, enc_id, cid, *_ = await _start(client, test_session_factory, monkeypatch)
    await _add_effect(test_session_factory, cid, "restrained")
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{cid}/conditions/restrained/escape?skill=athletics", json={"die": 20})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_escape_dc"


async def test_death_save_marks_the_turn(client, test_session_factory, monkeypatch):
    """Il banner «tira il TS contro la morte» sparisce dopo il tiro: il turno ricorda che è stato fatto."""
    _, sid, enc_id, cid, *_ = await _start(client, test_session_factory, monkeypatch)
    async with test_session_factory() as s:
        ch = await s.get(Character, cid)
        ch.hit_points, ch.current_hit_points = 10, 0
        await s.commit()
    as_user(PLAYER_ID)
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["turn"].get("death_save_rolled") in (None, False)
    assert (await client.post(f"/characters/{cid}/death_saves/roll", json={"die": 12})).status_code == 200
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]["death_save_rolled"] is True


async def test_encounter_end_summary_has_damage_dealt(client, test_session_factory, monkeypatch):
    """M2: il riepilogo di fine scontro dice i danni inflitti ai nemici, non solo quanti ne sono caduti."""
    _, sid, enc_id, cid, pc_id, g1_id, g2_id = await _start(client, test_session_factory, monkeypatch)
    as_user(GM_ID)
    assert (await client.patch(f"/sessions/{sid}/encounter/combatants/{g1_id}", json={"current_hp": 0})).status_code == 200
    assert (await client.patch(f"/sessions/{sid}/encounter/combatants/{g2_id}", json={"current_hp": 4})).status_code == 200
    assert (await client.post(f"/sessions/{sid}/encounter/end")).status_code == 200
    async with test_session_factory() as s:
        from core.db.models import SessionMessage
        bodies = [m.body for m in (await s.execute(select(SessionMessage))).scalars()]
    assert any("Nemici sconfitti: 1/2" in b and "Danni inflitti: 10" in b for b in bodies), bodies
