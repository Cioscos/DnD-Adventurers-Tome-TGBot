"""Blocco `encounter` dentro GET /sessions/{id}/live — redazione per spettatore."""
from __future__ import annotations

from tests.integration._encounter_helpers import PLAYER_ID, as_user, seed_session
from tests.integration.test_encounters_turns import (
    install_fake_telegram,
    setup_full_encounter,
)


async def test_live_has_no_encounter_when_none_open(client, test_session_factory):
    sid, _ = await seed_session(test_session_factory)
    r = await client.get(f"/sessions/{sid}/live")
    assert r.status_code == 200, r.text
    assert r.json()["encounter"] is None


async def test_live_gm_sees_exact_monster_hp(client, test_session_factory, monkeypatch):
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)
    await client.post(f"/sessions/{sid}/encounter/start", json={})
    r = await client.get(f"/sessions/{sid}/live")
    enc = r.json()["encounter"]
    assert enc is not None and enc["status"] == "active"
    monster = next(c for c in enc["combatants"] if c["kind"] == "monster")
    assert monster["current_hp"] == 7 and monster["max_hp"] == 7 and monster["ac"] == 15
    assert monster["hp_bucket"] is None


async def test_live_player_sees_bucket_not_numbers(client, test_session_factory, monkeypatch):
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)
    await client.post(f"/sessions/{sid}/encounter/start", json={})
    g1 = next(
        c for c in (await client.get(f"/sessions/{sid}/live")).json()["encounter"]["combatants"]
        if c["name"] == "Goblin 1"
    )
    await client.patch(
        f"/sessions/{sid}/encounter/combatants/{g1['id']}", json={"current_hp": 3},
    )
    as_user(PLAYER_ID)
    r = await client.get(f"/sessions/{sid}/live")
    monster = next(c for c in r.json()["encounter"]["combatants"] if c["name"] == "Goblin 1")
    assert monster["current_hp"] is None and monster["max_hp"] is None and monster["ac"] is None
    assert monster["hp_bucket"] == "badly_wounded"   # 3/7 = 43%
    # iniziativa visibile a tutti
    assert monster["initiative"] is not None


async def test_live_pc_rows_never_carry_hp(client, test_session_factory, monkeypatch):
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)
    await client.post(f"/sessions/{sid}/encounter/start", json={})
    r = await client.get(f"/sessions/{sid}/live")
    pc = next(c for c in r.json()["encounter"]["combatants"] if c["kind"] == "pc")
    assert pc["current_hp"] is None and pc["max_hp"] is None and pc["hp_bucket"] is None
    assert pc["character_id"] is not None            # la FE joina live_characters


async def test_live_dead_monster_bucket_is_dead_for_players(
    client, test_session_factory, monkeypatch,
):
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)
    await client.post(f"/sessions/{sid}/encounter/start", json={})
    g1 = next(
        c for c in (await client.get(f"/sessions/{sid}/live")).json()["encounter"]["combatants"]
        if c["name"] == "Goblin 1"
    )
    await client.patch(
        f"/sessions/{sid}/encounter/combatants/{g1['id']}", json={"current_hp": 0},
    )
    as_user(PLAYER_ID)
    r = await client.get(f"/sessions/{sid}/live")
    monster = next(c for c in r.json()["encounter"]["combatants"] if c["name"] == "Goblin 1")
    assert monster["is_dead"] is True and monster["hp_bucket"] == "dead"
