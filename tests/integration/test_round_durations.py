"""Durate in round per condizioni e concentrazione + tick sui turni."""
from __future__ import annotations

from api.services.condition_effects import ExpirySpec, effects_for_character, upsert_effect
from core.db.models import Character
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
from tests.integration._telegram_stub import install_fake_telegram
from tests.integration._encounter_helpers import setup_full_encounter


async def _char(client) -> int:
    r = await client.post("/characters", json={"name": "Dur"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _counts(r) -> dict:
    return {e["slug"]: e["expiry_count"] for e in r.json()["condition_effects"]}


async def test_condition_duration_set_and_ticks_to_removal(client):
    cid = await _char(client)
    r = await client.patch(
        f"/characters/{cid}/conditions",
        json={"conditions": {"poisoned": True}, "durations": {"poisoned": 2}},
    )
    assert _counts(r) == {"poisoned": 2}
    r = await client.post(f"/characters/{cid}/rounds/tick")
    assert _counts(r) == {"poisoned": 1}
    assert r.json()["conditions"]["poisoned"] is True
    assert r.json()["expired_effects"] == []
    r = await client.post(f"/characters/{cid}/rounds/tick")
    body = r.json()
    assert body["conditions"]["poisoned"] is False
    assert len(body["expired_effects"]) == 1
    assert body["condition_effects"] == []
    hist = (await client.get(f"/characters/{cid}/history")).json()
    assert any("Durata scaduta" in h["description"] for h in hist)


async def test_concentration_duration_from_spell(client):
    cid = await _char(client)
    sp = (await client.post(f"/characters/{cid}/spells", json={
        "name": "Benedizione", "level": 1, "is_concentration": True,
        "duration": "Concentrazione, fino a 1 minuto",
    })).json()["id"]
    r = await client.patch(f"/characters/{cid}/concentration", json={"spell_id": sp, "rounds": 10})
    assert r.json()["settings"]["concentration_rounds_left"] == 10
    r = await client.post(f"/characters/{cid}/rounds/tick")
    assert r.json()["settings"]["concentration_rounds_left"] == 9


async def test_cast_sets_concentration_rounds(client):
    cid = await _char(client)
    await client.post(f"/characters/{cid}/spell_slots", json={"level": 1, "total": 1})
    sp = (await client.post(f"/characters/{cid}/spells", json={
        "name": "Benedizione", "level": 1, "is_concentration": True,
        "duration": "Concentrazione, fino a 1 minuto",
    })).json()["id"]
    r = await client.post(f"/characters/{cid}/spells/{sp}/use", json={"slot_level": 1})
    assert r.status_code == 200, r.text
    assert r.json()["settings"]["concentration_rounds_left"] == 10


async def test_concentration_expires_on_tick(client):
    cid = await _char(client)
    sp = (await client.post(f"/characters/{cid}/spells", json={
        "name": "B", "level": 1, "is_concentration": True,
    })).json()["id"]
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": sp, "rounds": 1})
    body = (await client.post(f"/characters/{cid}/rounds/tick")).json()
    assert body["concentrating_spell_id"] is None
    assert body["expired_effects"] == ["Concentrazione"]
    assert "concentration_rounds_left" not in body["settings"]


async def test_tick_preserves_other_settings(client):
    cid = await _char(client)
    await client.patch(f"/characters/{cid}", json={"settings": {"quick_actions": ["a"], "roll_notes": "x"}})
    await client.patch(
        f"/characters/{cid}/conditions",
        json={"conditions": {"poisoned": True}, "durations": {"poisoned": 1}},
    )
    s = (await client.post(f"/characters/{cid}/rounds/tick")).json()["settings"]
    assert s["quick_actions"] == ["a"] and s["roll_notes"] == "x"


async def test_clearing_condition_removes_duration(client):
    cid = await _char(client)
    await client.patch(
        f"/characters/{cid}/conditions",
        json={"conditions": {"poisoned": True}, "durations": {"poisoned": 5}},
    )
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"poisoned": False}})
    assert r.json()["condition_effects"] == []


async def test_rest_clears_concentration_duration(client):
    cid = await _char(client)
    sp = (await client.post(f"/characters/{cid}/spells", json={
        "name": "B", "level": 1, "is_concentration": True,
    })).json()["id"]
    for rest in ("short", "long"):
        await client.patch(f"/characters/{cid}/concentration", json={"spell_id": sp, "rounds": 10})
        r = await client.post(f"/characters/{cid}/rest", json={"rest_type": rest})
        assert r.status_code == 200, r.text
        assert r.json()["concentrating_spell_id"] is None
        assert "concentration_rounds_left" not in (r.json()["settings"] or {})


async def test_tick_other_user_403(client, test_session_factory):
    async with test_session_factory() as s:
        c = Character(user_id=999, name="Other")
        s.add(c)
        await s.commit()
        cid = c.id
    assert (await client.post(f"/characters/{cid}/rounds/tick")).status_code == 403
    assert (await client.post("/characters/9999/rounds/tick")).status_code == 404


async def _pc_setup(client, test_session_factory, monkeypatch):
    install_fake_telegram(monkeypatch)
    sid, enc = await setup_full_encounter(client, test_session_factory)
    r = await client.post(f"/sessions/{sid}/encounter/start", json={})
    assert r.status_code == 200, r.text
    pc = next(c for c in r.json()["combatants"] if c["kind"] == "pc")
    from core.db.models import Combatant
    async with test_session_factory() as s:
        comb = await s.get(Combatant, pc["id"])
        cid = comb.character_id
        ch = await s.get(Character, cid)
        ch.settings = {"quick_actions": ["a"]}
        await upsert_effect(s, ("character", cid), "poisoned",
                            expiry=ExpirySpec("owner", "start", 3))
        await s.commit()
    return sid, cid


async def _durs(test_session_factory, cid):
    async with test_session_factory() as s:
        return {e.slug: e.expiry_count for e in await effects_for_character(s, cid)}


async def test_next_turn_ticks_only_new_active_pc(client, test_session_factory, monkeypatch):
    sid, cid = await _pc_setup(client, test_session_factory, monkeypatch)
    as_user(GM_ID)
    # PG attivo; PG -> goblin 1: il nuovo attivo non e' il PG, niente tick
    await client.post(f"/sessions/{sid}/encounter/next-turn")
    assert await _durs(test_session_factory, cid) == {"poisoned": 3}
    await client.post(f"/sessions/{sid}/encounter/next-turn")
    await client.post(f"/sessions/{sid}/encounter/next-turn")  # torna al PG
    assert await _durs(test_session_factory, cid) == {"poisoned": 2}


async def test_prev_turn_does_not_tick(client, test_session_factory, monkeypatch):
    sid, cid = await _pc_setup(client, test_session_factory, monkeypatch)
    as_user(GM_ID)
    await client.post(f"/sessions/{sid}/encounter/next-turn")
    await client.post(f"/sessions/{sid}/encounter/prev-turn")  # torna al PG
    assert await _durs(test_session_factory, cid) == {"poisoned": 3}


async def test_malformed_durations_do_not_block_next_turn(client, test_session_factory, monkeypatch):
    sid, cid = await _pc_setup(client, test_session_factory, monkeypatch)
    async with test_session_factory() as s:
        ch = await s.get(Character, cid)
        ch.settings = {"concentration_rounds_left": "abc"}
        await upsert_effect(s, ("character", cid), "deafened",
                            expiry=ExpirySpec("owner", "start", 2))
        await s.commit()
    as_user(GM_ID)
    for _ in range(3):  # back to the PC -> tick runs on the malformed sheet
        r = await client.post(f"/sessions/{sid}/encounter/next-turn")
        assert r.status_code == 200, r.text
    async with test_session_factory() as s:
        settings = (await s.get(Character, cid)).settings
    assert await _durs(test_session_factory, cid) == {"poisoned": 2, "deafened": 1}
    assert "concentration_rounds_left" not in settings


async def test_patch_settings_keeps_server_owned_keys(client):
    cid = await _char(client)
    await client.patch(
        f"/characters/{cid}/conditions",
        json={"conditions": {"poisoned": True}, "durations": {"poisoned": 1}},
    )
    stale = (await client.get(f"/characters/{cid}")).json()["settings"]
    await client.post(f"/characters/{cid}/rounds/tick")  # duration expires server-side
    r = await client.patch(f"/characters/{cid}", json={"settings": {
        **stale, "roll_notes": "x", "hp_rolls": {"1": [9]}, "concentration_rounds_left": 5,
    }})
    s = r.json()["settings"]
    assert s["roll_notes"] == "x"
    assert "condition_durations" not in s
    assert "hp_rolls" not in s and "concentration_rounds_left" not in s
