"""Paladino 2014, giro di correzione 1 (I8): l'Aura di Protezione vale per ogni tiro salvezza, concentrazione compresa."""
from __future__ import annotations

from api.services.condition_effects import SaveSpec, upsert_effect
from core.db.models import Character, PendingSave
from tests.integration._encounter_helpers import PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard import _full, _roll_keys
from tests.integration.rules.test_2014_paladin_auras import PROTECTION, _table

AFTER = "aura:protection_after"


async def _concentrating(factory, cid, hp=30) -> None:
    async with factory() as s:
        char = await s.get(Character, cid)
        char.hit_points, char.current_hit_points = 40, hp
        char.settings = {**(char.settings or {}), "concentration_item_spell": {"feature_key": "x", "name": "x"}}
        await s.commit()


async def _after(client, cid, *keys):
    return await client.post(f"/characters/{cid}/last-roll/options", json={"options": list(keys)})


# ---------------------------------------------------------------------------
# Tiro contro la morte e TS in sospeso (la conferma prima del tiro)
# ---------------------------------------------------------------------------

async def test_a_death_save_takes_the_aura_bonus_from_a_paladin_at_the_table(client, test_session_factory):
    _, _, hero = await _table(client, test_session_factory, charisma=16)
    async with test_session_factory() as s:
        char = await s.get(Character, hero)
        char.hit_points, char.current_hit_points = 20, 0
        await s.commit()
    plain = await client.post(f"/characters/{hero}/death_saves/roll", json={"die": 9})
    assert plain.json()["outcome"] == "failure"
    r = await client.post(f"/characters/{hero}/death_saves/roll", json={"die": 9, "options": [PROTECTION]})
    assert r.status_code == 200, r.text
    assert r.json()["option_result"]["bonus"] == 3 and r.json()["outcome"] == "success"  # 9 + 3 = 12


async def test_a_pending_save_takes_the_aura_bonus_from_a_paladin_at_the_table(client, test_session_factory):
    _, _, hero = await _table(client, test_session_factory, charisma=16)
    async with test_session_factory() as s:
        char = await s.get(Character, hero)
        char.conditions = {"poisoned": True}
        eff = await upsert_effect(s, ("character", hero), "poisoned", save=SaveSpec("constitution", 12, "end"))
        ps = PendingSave(effect_id=eff.id, character_id=hero, ability="constitution", dc=12, status="pending",
                         created_at="2026-11-06T10:00:00")
        s.add(ps)
        await s.commit()
        psid = ps.id
    r = await client.post(f"/characters/{hero}/pending-saves/{psid}/roll", json={"die": 9, "options": [PROTECTION]})
    assert r.status_code == 200, r.text
    assert r.json()["roll"]["total"] == 9 + r.json()["roll"]["bonus"] and r.json()["passed"] is True


# ---------------------------------------------------------------------------
# Concentrazione: il bonus si somma dopo aver visto il dado
# ---------------------------------------------------------------------------

async def test_the_aura_is_offered_after_the_roll_on_a_save_and_not_before_it(client, test_session_factory):
    _, _, hero = await _table(client, test_session_factory, charisma=16)
    listed = (await client.get(f"/characters/{hero}/roll-options", params={"roll": "save", "ability": "constitution"})).json()
    by_key = {o["key"]: o for o in listed}
    assert by_key[PROTECTION]["phase"] == "before" and by_key[AFTER]["phase"] == "after_roll"


async def test_the_aura_saves_the_concentration_after_a_manual_roll(client, test_session_factory):
    _, _, hero = await _table(client, test_session_factory, charisma=16)
    await _concentrating(test_session_factory, hero)
    r = await client.post(f"/characters/{hero}/concentration/save", json={"damage": 20, "dice": [9]})
    assert r.status_code == 200, r.text
    assert r.json()["success"] is False and r.json()["lost_concentration"] is True  # 9 + 0 contro CD 10
    r = await _after(client, hero, AFTER)
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 9 + 3 and r.json()["concentration"]["success"] is True
    assert r.json()["concentration"]["lost_concentration"] is False
    assert (await _full(client, hero))["settings"].get("concentration_item_spell")  # la concentrazione è tornata


async def test_the_aura_also_covers_the_automatic_save_after_damage(client, test_session_factory):
    _, _, hero = await _table(client, test_session_factory, charisma=16)
    await _concentrating(test_session_factory, hero)
    r = await client.patch(f"/characters/{hero}/hp", json={"op": "damage", "value": 4})
    assert r.status_code == 200, r.text
    rolled = r.json()["concentration_save"]
    after = await _after(client, hero, AFTER)
    assert after.status_code == 200, after.text
    assert after.json()["total"] == rolled["total"] + 3


async def test_the_aura_after_the_roll_is_refused_without_a_paladin_at_the_table(client, test_session_factory):
    hero = (await seed_session(test_session_factory))[1]
    as_user(PLAYER_ID)
    await _concentrating(test_session_factory, hero)
    assert AFTER not in await _roll_keys(client, hero, "save", ability="constitution")
    await client.post(f"/characters/{hero}/concentration/save", json={"damage": 20, "dice": [9]})
    r = await _after(client, hero, AFTER)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "option_unavailable"
