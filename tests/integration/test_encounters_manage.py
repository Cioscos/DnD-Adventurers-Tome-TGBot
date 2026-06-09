"""PATCH / DELETE / reorder dei combattenti (routers/encounters.py)."""
from __future__ import annotations

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.test_encounters_turns import (
    install_fake_telegram,
    setup_full_encounter,
)


async def _full_setup(client, test_session_factory) -> tuple[int, dict]:
    sid, enc = await setup_full_encounter(client, test_session_factory)
    return sid, enc


def _monster(enc: dict, name: str = "Goblin 1") -> dict:
    return next(c for c in enc["combatants"] if c["name"] == name)


async def test_patch_damage_clamps_and_autokills(client, test_session_factory):
    sid, enc = await _full_setup(client, test_session_factory)
    g1 = _monster(enc)                               # 7/7 PF
    url = f"/sessions/{sid}/encounter/combatants/{g1['id']}"
    r = await client.patch(url, json={"current_hp": 3})
    assert r.status_code == 200, r.text
    assert _monster(r.json())["current_hp"] == 3
    r = await client.patch(url, json={"current_hp": 0})
    out = _monster(r.json())
    assert out["current_hp"] == 0
    assert out["is_dead"] is True                    # 0 PF -> morto automatico


async def test_patch_revive_clears_dead_flag(client, test_session_factory):
    sid, enc = await _full_setup(client, test_session_factory)
    g1 = _monster(enc)
    url = f"/sessions/{sid}/encounter/combatants/{g1['id']}"
    await client.patch(url, json={"current_hp": 0})
    r = await client.patch(url, json={"is_dead": False, "current_hp": 1})
    out = _monster(r.json())
    assert out["is_dead"] is False and out["current_hp"] == 1


async def test_patch_current_hp_clamped_to_max(client, test_session_factory):
    sid, enc = await _full_setup(client, test_session_factory)
    g1 = _monster(enc)
    r = await client.patch(
        f"/sessions/{sid}/encounter/combatants/{g1['id']}", json={"current_hp": 99},
    )
    assert _monster(r.json())["current_hp"] == 7     # clamp a max_hp


async def test_patch_conditions_and_initiative(client, test_session_factory):
    sid, enc = await _full_setup(client, test_session_factory)
    g1 = _monster(enc)
    r = await client.patch(
        f"/sessions/{sid}/encounter/combatants/{g1['id']}",
        json={"conditions": {"prone": True}, "initiative": 19},
    )
    out = _monster(r.json())
    assert out["conditions"] == {"prone": True}
    assert out["initiative"] == 19
    assert out["initiative_die"] is None             # inserimento manuale


async def test_patch_hp_on_light_mode_is_422(client, test_session_factory):
    sid, _ = await seed_session(test_session_factory)
    await client.post(f"/sessions/{sid}/encounter", json={"mode": "light"})
    r = await client.post(f"/sessions/{sid}/encounter/combatants", json={"name": "Goblin"})
    g = _monster(r.json(), "Goblin")
    r2 = await client.patch(
        f"/sessions/{sid}/encounter/combatants/{g['id']}", json={"current_hp": 3},
    )
    assert r2.status_code == 422, r2.text


async def test_patch_hp_on_pc_is_422(client, test_session_factory):
    sid, enc = await _full_setup(client, test_session_factory)
    pc = next(c for c in enc["combatants"] if c["kind"] == "pc")
    r = await client.patch(
        f"/sessions/{sid}/encounter/combatants/{pc['id']}", json={"current_hp": 3},
    )
    assert r.status_code == 422, r.text


async def test_patch_requires_gm(client, test_session_factory):
    sid, enc = await _full_setup(client, test_session_factory)
    g1 = _monster(enc)
    as_user(PLAYER_ID)
    r = await client.patch(
        f"/sessions/{sid}/encounter/combatants/{g1['id']}", json={"name": "Boss"},
    )
    assert r.status_code == 403, r.text
