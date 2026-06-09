"""start / next-turn / prev-turn / end + notifica bot (routers/encounters.py)."""
from __future__ import annotations

import api.routers.encounters as enc_module
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session


class _FakeResponse:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code
        self.text = "stub"

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300


def install_fake_telegram(monkeypatch, *, status_code: int = 200) -> list[dict]:
    """Cattura le sendMessage del modulo encounters (pattern di test_dice_post_to_chat)."""
    captured: list[dict] = []

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            captured.append({"url": url, "json": json})
            return _FakeResponse(status_code)

    monkeypatch.setattr(enc_module, "_BOT_TOKEN", "fake-token")
    monkeypatch.setattr(enc_module.httpx, "AsyncClient", _FakeClient)
    return captured


async def setup_full_encounter(client, test_session_factory) -> tuple[int, dict]:
    """Sessione + incontro full con PG (DEX 16) e 2 goblin; iniziative note.

    PG: die 14 + 3 = 17 -> primo. Goblin 1: die 10 + 2 = 12. Goblin 2: die 4 + 2 = 6.
    Ritorna (session_id, encounter_json_dopo_le_iniziative).
    """
    sid, _ = await seed_session(test_session_factory)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    assert r.status_code == 201, r.text
    r = await client.post(
        f"/sessions/{sid}/encounter/combatants",
        json={"name": "Goblin", "count": 2, "initiative_mod": 2, "max_hp": 7, "ac": 15},
    )
    enc = r.json()
    pc = next(c for c in enc["combatants"] if c["kind"] == "pc")
    g1, g2 = [c for c in enc["combatants"] if c["kind"] == "monster"]
    as_user(PLAYER_ID)
    await client.post(
        f"/sessions/{sid}/encounter/combatants/{pc['id']}/initiative", json={"die": 14},
    )
    as_user(GM_ID)
    await client.post(
        f"/sessions/{sid}/encounter/combatants/{g1['id']}/initiative", json={"die": 10},
    )
    r = await client.post(
        f"/sessions/{sid}/encounter/combatants/{g2['id']}/initiative", json={"die": 4},
    )
    return sid, r.json()


# ---------------------------------------------------------------------------
# POST /sessions/{id}/encounter/start
# ---------------------------------------------------------------------------

async def test_start_with_missing_initiative_is_409_with_names(client, test_session_factory):
    sid, _ = await seed_session(test_session_factory)
    await client.post(f"/sessions/{sid}/encounter", json={"mode": "light"})
    await client.post(f"/sessions/{sid}/encounter/combatants", json={"name": "Goblin"})
    r = await client.post(f"/sessions/{sid}/encounter/start", json={})
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert detail["code"] == "missing_initiative"
    assert "Eroe" in detail["names"] and "Goblin" in detail["names"]


async def test_start_auto_roll_missing_fills_and_starts(client, test_session_factory, monkeypatch):
    install_fake_telegram(monkeypatch)
    sid, _ = await seed_session(test_session_factory)
    await client.post(f"/sessions/{sid}/encounter", json={"mode": "light"})
    await client.post(f"/sessions/{sid}/encounter/combatants", json={"name": "Goblin"})
    r = await client.post(
        f"/sessions/{sid}/encounter/start", json={"auto_roll_missing": True},
    )
    assert r.status_code == 200, r.text
    enc = r.json()
    assert enc["status"] == "active"
    assert all(c["initiative"] is not None for c in enc["combatants"])


async def test_start_orders_by_initiative_then_mod(client, test_session_factory, monkeypatch):
    captured = install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)
    r = await client.post(f"/sessions/{sid}/encounter/start", json={})
    assert r.status_code == 200, r.text
    enc = r.json()
    assert enc["status"] == "active" and enc["round"] == 1
    names = [c["name"] for c in enc["combatants"]]
    assert names == ["Eroe", "Goblin 1", "Goblin 2"]          # 17, 12, 6
    assert [c["sort_order"] for c in enc["combatants"]] == [10, 20, 30]
    assert enc["active_combatant_id"] == enc["combatants"][0]["id"]
    # primo turno = PG -> notifica al proprietario
    assert len(captured) == 1
    assert captured[0]["json"]["chat_id"] == PLAYER_ID
    assert "Round 1" in captured[0]["json"]["text"]


async def test_start_twice_is_409(client, test_session_factory, monkeypatch):
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)
    assert (await client.post(f"/sessions/{sid}/encounter/start", json={})).status_code == 200
    r = await client.post(f"/sessions/{sid}/encounter/start", json={})
    assert r.status_code == 409, r.text


async def test_start_requires_gm(client, test_session_factory):
    sid, _ = await setup_full_encounter(client, test_session_factory)
    as_user(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/encounter/start", json={})
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# next-turn / prev-turn
# ---------------------------------------------------------------------------

async def _started(client, test_session_factory, monkeypatch) -> tuple[int, dict, list[dict]]:
    captured = install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)
    r = await client.post(f"/sessions/{sid}/encounter/start", json={})
    assert r.status_code == 200, r.text
    captured.clear()   # scarta la notifica dello start
    return sid, r.json(), captured


async def test_next_turn_advances_and_wraps_round(client, test_session_factory, monkeypatch):
    sid, enc, captured = await _started(client, test_session_factory, monkeypatch)
    ids = [c["id"] for c in enc["combatants"]]    # [Eroe, Goblin 1, Goblin 2]

    r = await client.post(f"/sessions/{sid}/encounter/next-turn")
    assert r.json()["active_combatant_id"] == ids[1]
    assert r.json()["round"] == 1
    r = await client.post(f"/sessions/{sid}/encounter/next-turn")
    assert r.json()["active_combatant_id"] == ids[2]
    # wrap -> round 2, torna al PG -> notifica
    r = await client.post(f"/sessions/{sid}/encounter/next-turn")
    assert r.json()["active_combatant_id"] == ids[0]
    assert r.json()["round"] == 2
    assert len(captured) == 1 and captured[0]["json"]["chat_id"] == PLAYER_ID


async def test_next_turn_skips_dead_monsters(client, test_session_factory, monkeypatch):
    sid, enc, _ = await _started(client, test_session_factory, monkeypatch)
    g1 = enc["combatants"][1]
    r = await client.patch(
        f"/sessions/{sid}/encounter/combatants/{g1['id']}", json={"is_dead": True},
    )
    assert r.status_code == 200, r.text
    r = await client.post(f"/sessions/{sid}/encounter/next-turn")
    # Goblin 1 morto saltato -> Goblin 2
    assert r.json()["active_combatant_id"] == enc["combatants"][2]["id"]


async def test_prev_turn_is_noop_at_round1_start(client, test_session_factory, monkeypatch):
    sid, enc, _ = await _started(client, test_session_factory, monkeypatch)
    r = await client.post(f"/sessions/{sid}/encounter/prev-turn")
    assert r.status_code == 200, r.text
    assert r.json()["active_combatant_id"] == enc["combatants"][0]["id"]
    assert r.json()["round"] == 1


async def test_prev_turn_wraps_back_decrementing_round(client, test_session_factory, monkeypatch):
    sid, enc, _ = await _started(client, test_session_factory, monkeypatch)
    ids = [c["id"] for c in enc["combatants"]]
    for _ in range(3):                            # -> round 2, attivo Eroe
        await client.post(f"/sessions/{sid}/encounter/next-turn")
    r = await client.post(f"/sessions/{sid}/encounter/prev-turn")
    assert r.json()["active_combatant_id"] == ids[2]
    assert r.json()["round"] == 1


async def test_turns_require_gm(client, test_session_factory, monkeypatch):
    sid, _, _ = await _started(client, test_session_factory, monkeypatch)
    as_user(PLAYER_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 403
    assert (await client.post(f"/sessions/{sid}/encounter/prev-turn")).status_code == 403
