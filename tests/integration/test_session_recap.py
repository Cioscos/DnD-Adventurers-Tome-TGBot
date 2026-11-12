"""End-of-evening recap: computed at close (manual + sweep), Telegram, endpoints."""
from __future__ import annotations

import json

import pytest

from api.services import campaigns as svc
from api.services import recap as recap_svc
from api.tasks import session_cleanup
from core.db.models import (
    Combatant, Encounter, GameSession, SessionMessage, SessionParticipant, SessionRole, SessionStatus,
)
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID
from tests.integration._telegram_stub import install_fake_telegram
from tests.integration.test_campaigns_api import STRANGER_ID, _char, _enrolled, _session, act

P2_ID = 7777


@pytest.fixture(autouse=True)
def _no_flag(tmp_path, monkeypatch):
    monkeypatch.delenv("SEND_CAMPAIGN_MESSAGES", raising=False)
    monkeypatch.setattr(svc, "LORE_DIR", tmp_path / "lore")


async def _start(client, camp_id) -> int:
    act(GM_ID)
    r = await client.post("/sessions", json={"campaign_id": camp_id})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _join(client, camp_id, uid, cid):
    act(uid)
    r = await client.post(f"/campaigns/{camp_id}/session/join", json={"character_id": cid})
    assert r.status_code == 200, r.text


async def _close(client, sid):
    act(GM_ID)
    r = await client.post(f"/sessions/{sid}/close")
    assert r.status_code == 204, r.text


async def _gs(factory, sid) -> GameSession:
    async with factory() as s:
        return await s.get(GameSession, sid)


async def test_close_builds_recap_with_stats(client, test_session_factory):
    f = test_session_factory
    camp, cid = await _enrolled(client, f)
    cid2 = await _char(f, P2_ID, name="Bardo")
    act(P2_ID)
    r = await client.post("/campaigns/enroll", json={"code": camp["invite_code"], "character_id": cid2})
    assert r.status_code == 200, r.text

    sid = await _start(client, camp["id"])
    await _join(client, camp["id"], PLAYER_ID, cid)
    await _join(client, camp["id"], P2_ID, cid2)

    act(PLAYER_ID)
    for op, v in (("set_max", 20), ("set_current", 20), ("damage", 7), ("heal", 3)):
        assert (await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": v})).status_code == 200
    r = await client.post(f"/characters/{cid}/dice/result",
                          json={"rolls": [{"kind": "d20", "value": 20}], "modifier": 2})
    assert r.status_code == 200, r.text
    slot = (await client.post(f"/characters/{cid}/spell_slots", json={"level": 1, "total": 2})).json()
    assert (await client.patch(f"/characters/{cid}/spell_slots/{slot['id']}", json={"used": 1})).status_code == 200

    async with f() as s:
        enc = Encounter(session_id=sid, mode="light", status="ended", round=3,
                        created_at="2026-01-01T00:00:00", started_at="2026-01-01T00:00:00")
        s.add(enc)
        await s.flush()
        s.add(Combatant(encounter_id=enc.id, kind="monster", name="Goblin 1", created_at="x"))
        s.add(Combatant(encounter_id=enc.id, kind="monster", name="Goblin 2", created_at="x"))
        s.add(Combatant(encounter_id=enc.id, kind="pc", name="Eroe", character_id=cid, created_at="x"))
        await s.commit()

    act(GM_ID)
    r = await client.post(f"/sessions/{sid}/gm/grant_item", json={
        "recipient_user_ids": [PLAYER_ID], "item": {"name": "Pozione", "quantity": 2}})
    assert r.status_code == 201, r.text
    item_id = r.json()["results"][0]["item_id"]
    r = await client.post(f"/campaigns/{camp['id']}/lore", data={"title": "Il tempio", "body": "x"})
    lore_id = r.json()["id"]
    assert (await client.post(f"/campaigns/{camp['id']}/lore/{lore_id}/reveal")).status_code == 200

    act(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/trade", json={
        "from_character_id": cid, "to_user_id": P2_ID, "item_id": item_id, "quantity": 1})
    assert r.status_code == 200, r.text

    await _close(client, sid)
    rec = (await _gs(f, sid)).recap
    assert rec is not None
    assert rec["version"] == 1 and rec["session_id"] == sid and rec["campaign_id"] == camp["id"]
    assert rec["campaign_name"] == "Saga" and rec["number"] == 1
    assert rec["ended_at"] and rec["started_at"] and rec["duration_seconds"] >= 0
    eroe = next(c for c in rec["characters"] if c["character_id"] == cid)
    assert eroe["name"] == "Eroe" and eroe["level"] == 3 and eroe["class_summary"]
    assert eroe["dice"] == {"rolls": 1, "nat20": 1, "nat1": 0, "highest": 22}
    assert eroe["damage_taken"] == 7 and eroe["healed"] == 3 and eroe["downed"] == 0
    assert eroe["death_saves"] == {"successes": 0, "failures": 0}
    assert eroe["spells_cast"] == 0 and eroe["slots_used"] == {"1": 1}
    assert eroe["rests"] == {"short": 0, "long": 0} and eroe["conditions"] == []
    assert rec["combat"] == {"encounters": 1, "rounds": 3, "monsters": ["Goblin"]}
    assert rec["items"]["gm_grants"] == [{"to": "Eroe", "item": "Pozione", "quantity": 2}]
    assert rec["items"]["trades"] == [{"from": "Eroe", "to": "Bardo", "summary": "Pozione"}]
    assert rec["items"]["stash"] == []
    assert rec["lore"] == [{"id": lore_id, "title": "Il tempio"}]
    hl = {h["key"]: h for h in rec["highlights"]}
    assert set(hl) == {"luckiest", "most_damage", "top_healer"}
    assert hl["luckiest"] == {"key": "luckiest", "character_id": cid, "name": "Eroe", "value": 1}
    assert hl["most_damage"]["value"] == 7 and hl["top_healer"]["value"] == 3
    json.dumps(rec)  # JSON-serialisable snapshot


async def test_recap_number_counts_closed_campaign_sessions(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    s1 = await _start(client, camp["id"])
    await _close(client, s1)
    s2 = await _start(client, camp["id"])
    await _close(client, s2)
    assert (await _gs(test_session_factory, s1)).recap["number"] == 1
    assert (await _gs(test_session_factory, s2)).recap["number"] == 2
    act(GM_ID)
    loose = (await client.post("/sessions", json={"title": "Sola"})).json()["id"]
    await _close(client, loose)
    assert (await _gs(test_session_factory, loose)).recap["number"] is None
    d = (await client.get(f"/campaigns/{camp['id']}")).json()
    assert [(s["id"], s["number"], s["has_recap"]) for s in d["sessions"]] == [(s2, 2, True), (s1, 1, True)]


async def test_empty_session_recap_valid_no_highlights(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    sid = await _start(client, camp["id"])
    await _close(client, sid)
    rec = (await _gs(test_session_factory, sid)).recap
    assert rec["characters"] == [] and rec["highlights"] == [] and rec["lore"] == []
    assert rec["combat"] == {"encounters": 0, "rounds": 0, "monsters": []}
    assert rec["items"] == {"gm_grants": [], "trades": [], "stash": []}
    assert recap_svc.format_recap_text(rec, "it") and recap_svc.format_recap_text(rec, "en")


async def test_recap_failure_still_closes(client, test_session_factory, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(recap_svc, "build_recap", boom)
    camp, _ = await _enrolled(client, test_session_factory)
    sid = await _start(client, camp["id"])
    await _close(client, sid)
    gs = await _gs(test_session_factory, sid)
    assert gs.status == SessionStatus.CLOSED and gs.closed_at and gs.recap is None


async def test_sweep_close_builds_recap(client, test_session_factory, monkeypatch):
    camp, _ = await _enrolled(client, test_session_factory)
    sid = await _session(test_session_factory, camp["id"], status=SessionStatus.ACTIVE,
                         created="2000-01-01T00:00:00", last="2000-01-01T01:00:00")
    monkeypatch.setattr(session_cleanup, "AsyncSessionLocal", test_session_factory)
    assert await session_cleanup._sweep_once() == 1
    gs = await _gs(test_session_factory, sid)
    assert gs.status == SessionStatus.CLOSED
    assert gs.recap["session_id"] == sid and gs.recap["duration_seconds"] == 3600


async def _flag_session(test_session_factory, camp_id, cid, code="AAA111") -> int:
    sid = await _session(test_session_factory, camp_id, status=SessionStatus.ACTIVE,
                         created="2026-11-03T20:00:00", last="2026-11-03T21:00:00",
                         uid=PLAYER_ID, char_id=cid, code=code)
    async with test_session_factory() as s:  # stash owner must never be messaged
        s.add(SessionParticipant(session_id=sid, user_id=svc.STASH_USER_ID,
                                 role=SessionRole.PLAYER, joined_at="2026-11-03T20:00:00"))
        await s.commit()
    return sid


async def test_messages_only_with_flag(client, test_session_factory, monkeypatch):
    camp, cid = await _enrolled(client, test_session_factory)
    captured = install_fake_telegram(monkeypatch)
    sid = await _flag_session(test_session_factory, camp["id"], cid)
    await _close(client, sid)
    assert [c for c in captured if "sendMessage" in c["url"]] == []

    monkeypatch.setenv("SEND_CAMPAIGN_MESSAGES", "1")
    sid2 = await _flag_session(test_session_factory, camp["id"], cid, code="BBB222")
    await _close(client, sid2)
    sends = [c["json"] for c in captured if "sendMessage" in c["url"]]
    assert sorted(p["chat_id"] for p in sends) == sorted([GM_ID, PLAYER_ID])
    assert all(p["parse_mode"] == "MarkdownV2" for p in sends)
    url = sends[0]["reply_markup"]["inline_keyboard"][0][0]["web_app"]["url"]
    assert url.endswith(f"/campaign/{camp['id']}/recap/{sid2}")


async def test_send_failure_does_not_break_close(client, test_session_factory, monkeypatch):
    camp, cid = await _enrolled(client, test_session_factory)
    install_fake_telegram(monkeypatch, status_code=500)
    monkeypatch.setenv("SEND_CAMPAIGN_MESSAGES", "1")
    sid = await _flag_session(test_session_factory, camp["id"], cid)
    await _close(client, sid)
    gs = await _gs(test_session_factory, sid)
    assert gs.status == SessionStatus.CLOSED and gs.recap is not None


def _big_recap(n: int) -> dict:
    ch = {"character_id": 1, "name": "Nome_lungo*" * 3, "player_name": "Gio", "class_summary": "wizard 3",
          "level": 3, "dice": {"rolls": 5, "nat20": 1, "nat1": 1, "highest": 21},
          "damage_taken": 4, "healed": 2, "downed": 1, "death_saves": {"successes": 1, "failures": 2},
          "spells_cast": 2, "slots_used": {"1": 2}, "rests": {"short": 1, "long": 0},
          "conditions": ["poisoned"]}
    return {"version": 1, "session_id": 1, "campaign_id": 1, "campaign_name": "Saga (1).", "number": 3,
            "started_at": "2026-11-03T20:00:00", "ended_at": "2026-11-03T23:00:00",
            "duration_seconds": 10800, "characters": [ch] * n,
            "combat": {"encounters": 1, "rounds": 3, "monsters": ["Goblin"]},
            "items": {"gm_grants": [], "trades": [], "stash": []}, "lore": [], "highlights": []}


async def test_format_recap_text_truncates_to_4096():
    short = recap_svc.format_recap_text(_big_recap(1), "it")
    assert r"Saga \(1\)\." in short and r"Nome\_lungo\*" in short and not short.endswith("…")
    long = recap_svc.format_recap_text(_big_recap(200), "en")
    assert len(long) <= 4096 and long.endswith("…")


async def test_recap_endpoint_access(client, test_session_factory):
    f = test_session_factory
    camp, cid = await _enrolled(client, f)
    member2 = await _char(f, P2_ID, name="Bardo")
    act(P2_ID)
    await client.post("/campaigns/enroll", json={"code": camp["invite_code"], "character_id": member2})
    sid = await _start(client, camp["id"])
    await _join(client, camp["id"], PLAYER_ID, cid)
    act(GM_ID)
    assert (await client.get(f"/sessions/{sid}/recap")).status_code == 404  # still active
    await _close(client, sid)
    for uid in (GM_ID, PLAYER_ID, P2_ID):
        act(uid)
        r = await client.get(f"/sessions/{sid}/recap")
        assert r.status_code == 200 and r.json()["session_id"] == sid
    act(STRANGER_ID)
    assert (await client.get(f"/sessions/{sid}/recap")).status_code == 403
    act(GM_ID)
    assert (await client.get("/sessions/999999/recap")).status_code == 404


async def test_share_recap_gm_only(client, test_session_factory, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    camp, cid = await _enrolled(client, test_session_factory)
    sid = await _start(client, camp["id"])
    act(GM_ID)
    assert (await client.post(f"/share/recap/{sid}")).status_code == 404  # no recap yet
    await _close(client, sid)
    act(PLAYER_ID)
    assert (await client.post(f"/share/recap/{sid}")).status_code == 403
    act(GM_ID)
    r = await client.post(f"/share/recap/{sid}")
    assert r.status_code == 200 and r.json()["prepared_message_id"] == "prep-1"
    call = next(c for c in captured if "savePreparedInlineMessage" in c["url"])
    content = call["json"]["result"]["input_message_content"]
    assert content["parse_mode"] == "MarkdownV2" and "Saga" in content["message_text"]


async def _roll(client, uid, cid, value=20):
    act(uid)
    r = await client.post(f"/characters/{cid}/dice/result",
                          json={"rolls": [{"kind": "d20", "value": value}], "modifier": 0})
    assert r.status_code == 200, r.text


async def test_player_who_left_stays_in_recap_and_gets_message(client, test_session_factory, monkeypatch):
    f = test_session_factory
    camp, cid = await _enrolled(client, f)
    captured = install_fake_telegram(monkeypatch)
    monkeypatch.setenv("SEND_CAMPAIGN_MESSAGES", "1")
    sid = await _start(client, camp["id"])
    await _join(client, camp["id"], PLAYER_ID, cid)
    await _roll(client, PLAYER_ID, cid)
    act(PLAYER_ID)
    assert (await client.post(f"/sessions/{sid}/leave")).status_code == 204
    await _close(client, sid)
    rec = (await _gs(f, sid)).recap
    eroe = next(c for c in rec["characters"] if c["character_id"] == cid)
    assert eroe["dice"]["rolls"] == 1 and eroe["dice"]["nat20"] == 1
    sends = [c["json"]["chat_id"] for c in captured if "sendMessage" in c["url"]]
    assert sorted(sends) == sorted([GM_ID, PLAYER_ID])
    act(PLAYER_ID)
    assert (await client.get(f"/sessions/{sid}/recap")).status_code == 200


async def test_leave_and_rejoin_keeps_earlier_dice_baseline(client, test_session_factory):
    f = test_session_factory
    camp, cid = await _enrolled(client, f)
    sid = await _start(client, camp["id"])
    await _join(client, camp["id"], PLAYER_ID, cid)
    await _roll(client, PLAYER_ID, cid, 20)
    act(PLAYER_ID)
    assert (await client.post(f"/sessions/{sid}/leave")).status_code == 204
    await _join(client, camp["id"], PLAYER_ID, cid)
    await _roll(client, PLAYER_ID, cid, 1)
    act(PLAYER_ID)
    assert (await client.post(f"/sessions/{sid}/leave")).status_code == 204
    await _join(client, camp["id"], PLAYER_ID, cid)
    await _close(client, sid)
    rec = (await _gs(f, sid)).recap
    assert [c["character_id"] for c in rec["characters"]] == [cid]  # no duplicate
    assert rec["characters"][0]["dice"]["rolls"] == 2
    assert rec["characters"][0]["dice"]["nat20"] == 1 and rec["characters"][0]["dice"]["nat1"] == 1


async def test_null_dice_baseline_counts_no_rolls(client, test_session_factory):
    f = test_session_factory
    camp, cid = await _enrolled(client, f)
    await _roll(client, PLAYER_ID, cid, 20)  # lifetime stats before the evening
    sid = await _session(f, camp["id"], status=SessionStatus.ACTIVE, created="2026-11-03T20:00:00",
                         last="2026-11-03T21:00:00", uid=PLAYER_ID, char_id=cid)  # dice_stats_start NULL
    await _close(client, sid)
    eroe = (await _gs(f, sid)).recap["characters"][0]
    assert (eroe["dice"]["rolls"], eroe["dice"]["nat20"], eroe["dice"]["nat1"]) == (0, 0, 0)


async def test_recap_lore_deduped(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    sid = await _start(client, camp["id"])
    act(GM_ID)
    lore_id = (await client.post(f"/campaigns/{camp['id']}/lore", data={"title": "Il tempio"})).json()["id"]
    for path in ("reveal", "hide", "reveal"):  # hide + reveal again = two reveal messages
        assert (await client.post(f"/campaigns/{camp['id']}/lore/{lore_id}/{path}")).status_code == 200
    await _close(client, sid)
    assert (await _gs(test_session_factory, sid)).recap["lore"] == [{"id": lore_id, "title": "Il tempio"}]


async def test_recap_lists_places_once(client, test_session_factory):
    camp, _ = await _enrolled(client, test_session_factory)
    sid = await _start(client, camp["id"])
    rows = [("atlas_reveal", {"map_id": 1, "marker_id": 5, "title": "Tesoro"}),
            ("atlas_reveal", {"map_id": 1, "marker_id": None, "title": "Mondo"}),
            ("atlas_reveal", {"map_id": 1, "marker_id": 5, "title": "Tesoro"})]
    async with test_session_factory() as s:
        for _, pl in rows:
            s.add(SessionMessage(session_id=sid, user_id=GM_ID, role=SessionRole.GAME_MASTER,
                                 body="x", sent_at="2026-06-08T21:00:00", sender_display_name="__GM__",
                                 trade_payload=json.dumps({"kind": "atlas_reveal", **pl})))
        await s.commit()
    await _close(client, sid)
    rec = (await _gs(test_session_factory, sid)).recap
    assert rec["places"] == [{"map_id": 1, "marker_id": 5, "title": "Tesoro"},
                             {"map_id": 1, "marker_id": None, "title": "Mondo"}]
    assert "Luoghi scoperti" in recap_svc.format_recap_text(rec, "it")
    assert "Places discovered" in recap_svc.format_recap_text(rec, "en")


async def test_recap_text_labels_coins_and_conditions():
    rec = _big_recap(1)
    rec["characters"][0] = {**rec["characters"][0], "conditions": ["poisoned", "custom:fuoco_nero"]}
    rec["items"]["trades"] = [{"from": "A", "to": "B", "summary": recap_svc._summary([], {"gold": 15})}]
    it, en = recap_svc.format_recap_text(rec, "it"), recap_svc.format_recap_text(rec, "en")
    assert "15 GP" in it and "15 GP" in en
    assert "Avvelenato" in it and "custom" not in it and "Fuoco Nero" in it
    assert "Poisoned" in en and "Fuoco nero" in en and "custom" not in en


async def test_recap_exhaustion_level_spell_heal_and_real_heal_text(client, test_session_factory):
    f = test_session_factory
    act(GM_ID)
    from tests.integration.test_campaigns_api import _new_campaign
    camp = await _new_campaign(client)
    act(PLAYER_ID)
    r = await client.post("/characters", json={"name": "Chierico", "initial_class": {
        "class_name": "cleric", "level": 3, "subclass": "Dominio della Vita"}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    r = await client.post("/campaigns/enroll", json={"code": camp["invite_code"], "character_id": cid})
    assert r.status_code == 200, r.text
    sid = await _start(client, camp["id"])
    await _join(client, camp["id"], PLAYER_ID, cid)

    act(PLAYER_ID)
    for op, v in (("set_max", 20), ("set_current", 5)):
        assert (await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": v})).status_code == 200
    # cura oltre il massimo: 5 -> 20 sono 15 PF veri, non i 100 chiesti
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "heal", "value": 100})).status_code == 200
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 9})).status_code == 200
    spells = {s["srd_index"]: s for s in (await client.get(f"/characters/{cid}/spells")).json()}
    r = await client.post(f"/characters/{cid}/spells/{spells['cure-wounds']['id']}/roll_healing",
                          json={"casting_level": 1, "apply_to_self": True})
    assert r.status_code == 200, r.text
    healed_by_spell = r.json()["healed"]
    assert healed_by_spell > 0
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"exhaustion": 2}})
    assert r.status_code == 200, r.text

    hist = (await client.get(f"/characters/{cid}/history")).json()
    texts = [h["description"] for h in (hist["items"] if isinstance(hist, dict) else hist)]
    assert any(t.startswith("Cura: +15 HP (5 → 20)") for t in texts), texts

    await _close(client, sid)
    c = next(c for c in (await _gs(f, sid)).recap["characters"] if c["character_id"] == cid)
    assert c["healed"] == 15 + healed_by_spell  # la cura da incantesimo conta una volta sola
    assert c["conditions"] == ["exhaustion"] and c["condition_levels"] == {"exhaustion": 2}
    assert "Chi è stato curato di più" in recap_svc._T["it"]["top_healer"]
    assert "Esaurimento 2" in recap_svc.format_recap_text((await _gs(f, sid)).recap, "it").replace("\\", "")
