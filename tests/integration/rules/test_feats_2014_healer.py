"""Guaritore 2014 (manuale p.167): la cura di un uso della borsa, 1d6 + 4 + i Dadi Vita massimi del bersaglio."""
from __future__ import annotations

from core.db.models import Character
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard import _full, _use
from tests.integration.rules.test_2014_bard_inspiration import _seat
from tests.integration.rules.test_2014_fighter_battle_master import _fixed

HEALER = "feat.healer"


async def _healer(client, level=5) -> int:
    r = await client.post("/characters", json={"name": "Medico", "rules_edition": "2014",
                                               "initial_class": {"class_name": "fighter", "level": level}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.post(f"/characters/{cid}/feats", json={"feat_key": "healer", "ability": None})
    assert r.status_code == 201, r.text
    return cid


async def _hp(factory, cid, current, maximum=100) -> None:
    async with factory() as s:
        char = await s.get(Character, cid)
        char.hit_points, char.current_hit_points = maximum, current
        await s.commit()


async def _current(factory, cid) -> int:
    async with factory() as s:
        return (await s.get(Character, cid)).current_hit_points


async def test_healer_heals_self(client, test_session_factory, monkeypatch):
    cid = await _healer(client, 5)
    await _hp(test_session_factory, cid, 1)
    _fixed(monkeypatch, 3)
    r = await _use(client, cid, HEALER, params={"mode": "self"})
    assert r.status_code == 200, r.text
    assert r.json()["healed"] == 3 + 4 + 5
    assert await _current(test_session_factory, cid) == 1 + 12


async def _table(client, factory, hero_level=8):
    _, hero = await seed_session(factory)
    as_user(PLAYER_ID)
    assert (await client.post(f"/characters/{hero}/classes", json={"class_name": "fighter", "level": hero_level, "hit_die": 10})).status_code == 201
    as_user(GM_ID)
    medic = await _healer(client, 5)
    await _seat(factory, medic, GM_ID)
    return medic, hero


async def test_healer_heals_seated_ally_with_target_level(client, test_session_factory, monkeypatch):
    medic, hero = await _table(client, test_session_factory, 8)
    await _hp(test_session_factory, hero, 1)
    _fixed(monkeypatch, 3)
    as_user(GM_ID)
    r = await _use(client, medic, HEALER, params={"mode": "other", "target_character_id": hero})
    assert r.status_code == 200, r.text
    assert r.json()["received"] == {"name": "Eroe", "healed": 3 + 4 + 8} and r.json()["healed"] == 0
    assert await _current(test_session_factory, hero) == 1 + 15


async def test_healer_outside_evening_is_text(client, test_session_factory, monkeypatch):
    cid = await _healer(client, 5)
    await _hp(test_session_factory, cid, 10)
    _fixed(monkeypatch, 3)
    r = await _use(client, cid, HEALER, params={"mode": "other"})
    assert r.status_code == 200, r.text
    # 3 + 4: i Dadi Vita del bersaglio li somma il giocatore, non il livello di chi cura
    assert r.json()["received"] is None and r.json()["given"] == 7 and r.json()["healed"] == 0
    assert "healer_other" in r.json()["notes"]
    assert await _current(test_session_factory, cid) == 10
