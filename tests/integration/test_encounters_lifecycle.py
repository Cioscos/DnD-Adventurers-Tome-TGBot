"""POST /sessions/{id}/encounter — creazione incontro (routers/encounters.py)."""
from __future__ import annotations

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session


async def test_create_full_encounter_auto_adds_pcs(client, test_session_factory):
    sid, char_id = await seed_session(test_session_factory)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    assert r.status_code == 201, r.text
    enc = r.json()
    assert enc["mode"] == "full"
    assert enc["status"] == "setup"
    assert enc["round"] == 1
    pcs = [c for c in enc["combatants"] if c["kind"] == "pc"]
    assert len(pcs) == 1
    assert pcs[0]["character_id"] == char_id
    assert pcs[0]["owner_user_id"] == PLAYER_ID
    assert pcs[0]["name"] == "Eroe"
    assert pcs[0]["initiative_mod"] == 3     # DEX 16 -> +3
    assert pcs[0]["initiative"] is None


async def test_create_requires_gm(client, test_session_factory):
    sid, _ = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "light"})
    assert r.status_code == 403, r.text


async def test_double_open_encounter_is_409(client, test_session_factory):
    sid, _ = await seed_session(test_session_factory)
    r1 = await client.post(f"/sessions/{sid}/encounter", json={"mode": "light"})
    assert r1.status_code == 201, r1.text
    r2 = await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    assert r2.status_code == 409, r2.text


async def test_invalid_mode_is_422(client, test_session_factory):
    sid, _ = await seed_session(test_session_factory)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "epic"})
    assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# POST /sessions/{id}/encounter/combatants — aggiunta mostri
# ---------------------------------------------------------------------------

async def _create_encounter(client, sid: int, mode: str = "full") -> dict:
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": mode})
    assert r.status_code == 201, r.text
    return r.json()


async def test_add_monsters_with_count_suffixes_names(client, test_session_factory):
    sid, _ = await seed_session(test_session_factory)
    await _create_encounter(client, sid, "full")
    r = await client.post(
        f"/sessions/{sid}/encounter/combatants",
        json={"name": "Goblin", "count": 3, "initiative_mod": 2, "max_hp": 7, "ac": 15},
    )
    assert r.status_code == 201, r.text
    monsters = [c for c in r.json()["combatants"] if c["kind"] == "monster"]
    assert [m["name"] for m in monsters] == ["Goblin 1", "Goblin 2", "Goblin 3"]
    # GM view: HP esatti, current = max alla creazione
    assert all(m["max_hp"] == 7 and m["current_hp"] == 7 and m["ac"] == 15 for m in monsters)
    assert all(m["initiative_mod"] == 2 and m["initiative"] is None for m in monsters)
    assert all(m["sort_order"] is None for m in monsters)  # setup: niente ordine


async def test_add_single_monster_keeps_plain_name(client, test_session_factory):
    sid, _ = await seed_session(test_session_factory)
    await _create_encounter(client, sid, "light")
    r = await client.post(
        f"/sessions/{sid}/encounter/combatants", json={"name": "Drago"},
    )
    assert r.status_code == 201, r.text
    monsters = [c for c in r.json()["combatants"] if c["kind"] == "monster"]
    assert [m["name"] for m in monsters] == ["Drago"]


async def test_add_monster_hp_in_light_mode_is_422(client, test_session_factory):
    sid, _ = await seed_session(test_session_factory)
    await _create_encounter(client, sid, "light")
    r = await client.post(
        f"/sessions/{sid}/encounter/combatants",
        json={"name": "Goblin", "max_hp": 7},
    )
    assert r.status_code == 422, r.text


async def test_add_monster_requires_gm(client, test_session_factory):
    sid, _ = await seed_session(test_session_factory)
    await _create_encounter(client, sid, "full")
    as_user(PLAYER_ID)
    r = await client.post(
        f"/sessions/{sid}/encounter/combatants", json={"name": "Goblin"},
    )
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# POST /sessions/{id}/encounter/combatants/{cid}/initiative
# ---------------------------------------------------------------------------

def _pc(enc: dict) -> dict:
    return next(c for c in enc["combatants"] if c["kind"] == "pc")


async def test_player_rolls_own_initiative_with_die(client, test_session_factory):
    sid, _ = await seed_session(test_session_factory)   # DEX 16 -> mod +3
    enc = await _create_encounter(client, sid, "light")
    pc = _pc(enc)
    as_user(PLAYER_ID)
    r = await client.post(
        f"/sessions/{sid}/encounter/combatants/{pc['id']}/initiative",
        json={"die": 14},
    )
    assert r.status_code == 200, r.text
    rolled = _pc(r.json())
    assert rolled["initiative_die"] == 14
    assert rolled["initiative"] == 17        # 14 + 3


async def test_double_roll_is_409(client, test_session_factory):
    sid, _ = await seed_session(test_session_factory)
    enc = await _create_encounter(client, sid, "light")
    pc = _pc(enc)
    as_user(PLAYER_ID)
    url = f"/sessions/{sid}/encounter/combatants/{pc['id']}/initiative"
    assert (await client.post(url, json={"die": 14})).status_code == 200
    r = await client.post(url, json={"die": 20})
    assert r.status_code == 409, r.text


async def test_player_cannot_roll_for_monster(client, test_session_factory):
    sid, _ = await seed_session(test_session_factory)
    await _create_encounter(client, sid, "light")
    r = await client.post(
        f"/sessions/{sid}/encounter/combatants", json={"name": "Goblin", "initiative_mod": 2},
    )
    monster = next(c for c in r.json()["combatants"] if c["kind"] == "monster")
    as_user(PLAYER_ID)
    r2 = await client.post(
        f"/sessions/{sid}/encounter/combatants/{monster['id']}/initiative",
        json={"die": 10},
    )
    assert r2.status_code == 403, r2.text


async def test_gm_rolls_monster_without_die_gets_server_roll(client, test_session_factory):
    sid, _ = await seed_session(test_session_factory)
    await _create_encounter(client, sid, "light")
    r = await client.post(
        f"/sessions/{sid}/encounter/combatants", json={"name": "Goblin", "initiative_mod": 2},
    )
    monster = next(c for c in r.json()["combatants"] if c["kind"] == "monster")
    r2 = await client.post(
        f"/sessions/{sid}/encounter/combatants/{monster['id']}/initiative",
        json={},
    )
    assert r2.status_code == 200, r2.text
    rolled = next(c for c in r2.json()["combatants"] if c["id"] == monster["id"])
    assert 1 <= rolled["initiative_die"] <= 20
    assert rolled["initiative"] == rolled["initiative_die"] + 2
