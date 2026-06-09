"""GET /characters (list) + DELETE /characters/{id} — routers/characters.py.

These two endpoints were the only character-collection holes left in the
ledger (CRUD create/get/patch were already covered). The list returns the
lightweight ``CharacterSummary`` for the *authenticated* user only; delete is
ownership-guarded (404 missing / 403 foreign) and removes the row.

Ownership 403 can't be produced through the API (the auth override always
returns ``TEST_USER_ID``), so a foreign-owned character is inserted directly
through the test session factory — the same SQLite file the overridden
``get_db`` reads (mirrors ``test_history.py``).
"""
from __future__ import annotations

from core.db.models import Character

TEST_USER_ID = 1234  # mirrors tests/integration/conftest.py


async def _make_char(client, name: str = "Hero", initial_class: dict | None = None) -> int:
    body: dict = {"name": name}
    if initial_class is not None:
        body["initial_class"] = initial_class
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


# --- GET /characters (list) -------------------------------------------------

async def test_list_is_empty_initially(client):
    r = await client.get("/characters")
    assert r.status_code == 200, r.text
    assert r.json() == []


async def test_list_returns_owned_ordered_by_id(client):
    a = await _make_char(client, "Aaa")
    b = await _make_char(client, "Bbb")
    rows = (await client.get("/characters")).json()
    # ordered by id ascending (create order)
    assert [c["id"] for c in rows] == sorted([a, b])
    assert {c["name"] for c in rows} == {"Aaa", "Bbb"}


async def test_list_summary_shape(client):
    await _make_char(client, "Shape")
    row = (await client.get("/characters")).json()[0]
    # CharacterSummary fields the FE list reads.
    assert set(row) >= {
        "id", "name", "hit_points", "current_hit_points", "temp_hp",
        "ac", "total_level", "class_summary", "heroic_inspiration",
        "experience_points",
    }


async def test_list_excludes_other_owners_characters(client, test_session_factory):
    mine = await _make_char(client, "Mine")
    async with test_session_factory() as s:
        s.add(Character(user_id=TEST_USER_ID + 1, name="NotMine"))
        await s.commit()
    rows = (await client.get("/characters")).json()
    assert mine in [c["id"] for c in rows]
    assert all(c["name"] != "NotMine" for c in rows)


async def test_list_reflects_class_summary_and_total_level(client):
    cid = await _make_char(
        client, "Caster", initial_class={"class_name": "Mago", "level": 3, "hit_die": 6}
    )
    row = next(c for c in (await client.get("/characters")).json() if c["id"] == cid)
    assert row["total_level"] == 3
    assert row["class_summary"]  # non-empty once a class exists


# --- DELETE /characters/{id} ------------------------------------------------

async def test_delete_then_get_is_404(client):
    cid = await _make_char(client)
    d = await client.delete(f"/characters/{cid}")
    assert d.status_code == 204, d.text
    assert (await client.get(f"/characters/{cid}")).status_code == 404


async def test_delete_removes_only_the_target_from_list(client):
    keep = await _make_char(client, "Keep")
    drop = await _make_char(client, "Drop")
    assert (await client.delete(f"/characters/{drop}")).status_code == 204
    ids = [c["id"] for c in (await client.get("/characters")).json()]
    assert keep in ids and drop not in ids


async def test_delete_unknown_character_is_404(client):
    assert (await client.delete("/characters/999999")).status_code == 404


async def test_delete_other_owner_is_403(client, test_session_factory):
    async with test_session_factory() as s:
        other = Character(user_id=TEST_USER_ID + 1, name="NotMine")
        s.add(other)
        await s.commit()
        other_id = other.id
    assert (await client.delete(f"/characters/{other_id}")).status_code == 403
