"""Notifiche al giocatore per azioni del GM: loot consegnato e condizioni
aggiornate sul suo combatant PC (categoria gm_events)."""
from __future__ import annotations

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration._telegram_stub import install_fake_telegram


async def _set_prefs(test_session_factory, char_id: int, prefs: dict) -> None:
    from core.db.models import Character
    async with test_session_factory() as s:
        char = await s.get(Character, char_id)
        char.settings = {"notifications": prefs}
        await s.commit()


async def test_grant_item_notifies_player_with_inventory_link(
        client, test_session_factory, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    sid, cid = await seed_session(test_session_factory)
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/gm/grant_item", json={
        "recipient_user_ids": [PLAYER_ID],
        "item": {"name": "Pozione di cura", "quantity": 2, "item_type": "generic"},
    })
    assert r.status_code == 201, r.text
    msgs = [c["json"] for c in captured if c["json"]["chat_id"] == PLAYER_ID]
    assert len(msgs) == 1
    assert "Pozione di cura" in msgs[0]["text"] and "🎁" in msgs[0]["text"]
    url = msgs[0]["reply_markup"]["inline_keyboard"][0][0]["web_app"]["url"]
    assert url.endswith(f"#/char/{cid}/inventory")


async def test_grant_item_opt_out_is_silent_but_grants(
        client, test_session_factory, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    sid, cid = await seed_session(test_session_factory)
    await _set_prefs(test_session_factory, cid, {"gm_events": False})
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/gm/grant_item", json={
        "recipient_user_ids": [PLAYER_ID],
        "item": {"name": "Corda", "quantity": 1, "item_type": "generic"},
    })
    assert r.status_code == 201, r.text
    assert r.json()["results"][0]["status"] == "ok"
    assert captured == []


async def _open_encounter_with_pc(client, sid: int) -> int:
    """Apre un incontro light (auto-aggiunge i PC) e ritorna l'id del combatant PC."""
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "light"})
    assert r.status_code == 201, r.text
    pc = next(c for c in r.json()["combatants"] if c["kind"] == "pc")
    return pc["id"]


async def test_patch_conditions_on_pc_notifies_owner(
        client, test_session_factory, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    sid, _cid = await seed_session(test_session_factory)
    as_user(GM_ID)
    comb_id = await _open_encounter_with_pc(client, sid)
    captured.clear()  # scarta l'eventuale notifica 'incontro iniziato'
    r = await client.patch(
        f"/sessions/{sid}/encounter/combatants/{comb_id}",
        json={"conditions": {"poisoned": True}})
    assert r.status_code == 200, r.text
    msgs = [c["json"] for c in captured if c["json"]["chat_id"] == PLAYER_ID]
    assert len(msgs) == 1
    assert "🌀" in msgs[0]["text"] and "poisoned" in msgs[0]["text"]


async def test_patch_same_conditions_is_silent(client, test_session_factory, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    sid, _cid = await seed_session(test_session_factory)
    as_user(GM_ID)
    comb_id = await _open_encounter_with_pc(client, sid)
    await client.patch(f"/sessions/{sid}/encounter/combatants/{comb_id}",
                       json={"conditions": {"poisoned": True}})
    captured.clear()
    await client.patch(f"/sessions/{sid}/encounter/combatants/{comb_id}",
                       json={"conditions": {"poisoned": True}})
    assert captured == []
