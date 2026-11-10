"""Preservare Vita (R42): cura di 5 × livello PF fra chi lo usa e gli altri partecipanti della serata."""
from __future__ import annotations

from sqlalchemy import select

from core.db.models import CharacterHistory, GameSession, SessionStatus
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
from tests.integration.rules.test_2014_bard import _ability, _full
from tests.integration.rules.test_2014_barbarian import _turn
from tests.integration.rules.test_2014_cleric import POOL, _cleric
from tests.integration.rules.test_2014_cleric_late import _table

KEY = "cleric.preserve_life"


async def _hp(client, cid, current, maximum=40) -> None:
    for body in ({"op": "set_max", "value": maximum}, {"op": "set_current", "value": current}):
        r = await client.patch(f"/characters/{cid}/hp", json=body)
        assert r.status_code == 200, r.text


async def _scene(client, factory, level=5, hero_hp=5):
    sid, cleric, hero = await _table(client, factory, level, "life")
    await _hp(client, cleric, 10, 40)  # il chierico: 10 su 40
    as_user(PLAYER_ID)
    await _hp(client, hero, hero_hp, 40)
    as_user(GM_ID)
    return sid, cleric, hero


async def _go(client, cleric, allocations, confirm=True):
    return await client.post(f"/characters/{cleric}/preserve-life", json={
        "allocations": [{"character_id": c, "amount": a} for c, a in allocations], "confirm_living": confirm})


async def _unspent(client, cleric, pool_uses) -> None:
    assert (await _ability(client, cleric, POOL))["uses"] == pool_uses
    assert (await _turn(client, cleric))["action_used"] is False


async def test_it_heals_the_caster_and_an_ally_and_spends_one_use_and_the_action(client, test_session_factory):
    sid, cleric, hero = await _scene(client, test_session_factory)
    r = await _go(client, cleric, [(cleric, 8), (hero, 12)])
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["pool"], body["spent"]) == (25, 20)
    assert {h["character_id"]: h["healed"] for h in body["healed"]} == {cleric: 8, hero: 12}
    assert (await _ability(client, cleric, POOL))["uses"] == 0 and (await _turn(client, cleric))["action_used"] is True
    as_user(PLAYER_ID)
    assert (await _full(client, hero))["current_hit_points"] == 17
    async with test_session_factory() as s:
        history = (await s.execute(select(CharacterHistory).where(CharacterHistory.character_id == hero))).scalars().all()
    assert any(h.event_type == "hp_change" for h in history)  # lo storico sta sulla scheda del ricevente


async def test_a_character_outside_the_session_is_refused_and_nothing_is_spent(client, test_session_factory):
    from core.db.models import Character
    sid, cleric, hero = await _scene(client, test_session_factory)
    async with test_session_factory() as s:
        stranger = Character(user_id=9001, name="Estraneo", hit_points=40, current_hit_points=1)
        s.add(stranger)
        await s.commit()
        stranger_id = stranger.id
    r = await _go(client, cleric, [(hero, 5), (stranger_id, 5)])
    assert r.status_code == 403 and r.json()["detail"]["code"] == "invalid_target"
    await _unspent(client, cleric, 1)
    async with test_session_factory() as s:
        assert (await s.get(Character, stranger_id)).current_hit_points == 1
    as_user(PLAYER_ID)
    assert (await _full(client, hero))["current_hit_points"] == 5  # nessuna cura parziale


async def test_a_closed_session_leaves_only_the_caster(client, test_session_factory):
    sid, cleric, hero = await _scene(client, test_session_factory)
    async with test_session_factory() as s:
        (await s.get(GameSession, sid)).status = SessionStatus.CLOSED
        await s.commit()
    r = await _go(client, cleric, [(hero, 5)])
    assert r.status_code == 403
    await _unspent(client, cleric, 1)
    assert (await _go(client, cleric, [(cleric, 5)])).status_code == 200  # su sé stessi si può sempre


async def test_a_sum_over_five_times_the_level_is_refused(client, test_session_factory):
    sid, cleric, hero = await _scene(client, test_session_factory, level=2)  # riserva 10
    as_user(PLAYER_ID)
    await _hp(client, hero, 1, 80)
    as_user(GM_ID)
    r = await _go(client, cleric, [(cleric, 6), (hero, 5)])
    assert r.status_code == 422 and r.json()["detail"]["code"] == "over_pool"
    await _unspent(client, cleric, 1)
    assert (await _go(client, cleric, [(cleric, 6), (hero, 4)])).status_code == 200


async def test_a_receiver_over_half_of_the_maximum_is_refused_as_a_whole(client, test_session_factory):
    sid, cleric, hero = await _scene(client, test_session_factory, hero_hp=25)  # 25 su 40: oltre la metà
    r = await _go(client, cleric, [(cleric, 5), (hero, 1)])
    assert r.status_code == 422 and r.json()["detail"]["code"] == "over_half"
    await _unspent(client, cleric, 1)
    assert (await _full(client, cleric))["current_hit_points"] == 10  # il chierico non è stato curato


async def test_the_half_cap_limits_each_receiver(client, test_session_factory):
    sid, cleric, hero = await _scene(client, test_session_factory, hero_hp=15)  # fino a 20: restano 5
    assert (await _go(client, cleric, [(hero, 6)])).status_code == 422
    r = await _go(client, cleric, [(hero, 5)])
    assert r.status_code == 200 and r.json()["healed"][0]["healed"] == 5 and "current_hit_points" not in r.json()["healed"][0]


async def test_a_receiver_at_zero_is_healed_and_the_death_saves_are_cleared(client, test_session_factory):
    sid, cleric, hero = await _scene(client, test_session_factory, hero_hp=0)
    as_user(PLAYER_ID)
    assert (await client.post(f"/characters/{hero}/death_saves/roll", json={"die": 5})).status_code == 200
    assert (await _full(client, hero))["death_saves"]["failures"] == 1
    as_user(GM_ID)
    assert (await _go(client, cleric, [(hero, 6)])).status_code == 200
    as_user(PLAYER_ID)
    full = await _full(client, hero)
    assert full["current_hit_points"] == 6 and full["death_saves"]["failures"] == 0


async def test_the_player_must_confirm_the_targets_are_living(client, test_session_factory):
    sid, cleric, hero = await _scene(client, test_session_factory)
    r = await _go(client, cleric, [(hero, 5)], confirm=False)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "confirm_required"
    await _unspent(client, cleric, 1)


async def test_bad_allocations_are_refused(client, test_session_factory):
    sid, cleric, hero = await _scene(client, test_session_factory)
    for allocations in ([(hero, 0)], [(hero, -3)], [(hero, 2), (hero, 3)]):
        r = await _go(client, cleric, allocations)
        assert r.status_code == 422 and r.json()["detail"]["code"] == "bad_allocation"
    await _unspent(client, cleric, 1)


async def test_the_generic_use_endpoint_refuses_the_panel_feature(client):
    cid = await _cleric(client, 5, "life")
    r = await client.post(f"/characters/{cid}/features/{KEY}/use", json={})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "needs_panel"
    await _unspent(client, cid, 1)
    assert (await _ability(client, cid, KEY))["use_panel"] == "preserve_life"


async def test_no_uses_and_a_spent_action_are_refused_without_touching_anything(client, test_session_factory):
    sid, cleric, hero = await _scene(client, test_session_factory)
    await client.post(f"/characters/{cleric}/turn/use", json={"slot": "action"})
    r = await _go(client, cleric, [(hero, 5)])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "turn_slot_used"
    assert (await _ability(client, cleric, POOL))["uses"] == 1
    as_user(PLAYER_ID)
    assert (await _full(client, hero))["current_hit_points"] == 5
    as_user(GM_ID)
    await client.post(f"/characters/{cleric}/turn/use", json={"slot": "action", "used": False})
    assert (await _go(client, cleric, [(cleric, 1)])).status_code == 200
    await client.post(f"/characters/{cleric}/turn/new")
    r = await _go(client, cleric, [(cleric, 1)])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"


async def test_the_caster_alone_outside_a_session_can_use_it(client):
    cid = await _cleric(client, 5, "life")
    await _hp(client, cid, 3, 40)
    r = await _go(client, cid, [(cid, 10)])
    assert r.status_code == 200 and (await _full(client, cid))["current_hit_points"] == 13


async def test_only_the_life_domain_has_it_and_only_the_owner_can_ask(client):
    war = await _cleric(client, 5, "war")
    assert (await _go(client, war, [(war, 1)])).status_code == 404
    life = await _cleric(client, 5, "life")
    as_user(9999)
    assert (await _go(client, life, [(life, 1)])).status_code == 403


async def test_preserve_life_2_the_half_cap_uses_the_effective_max(client, test_session_factory):
    from core.db.models import Character
    sid, cleric, hero = await _scene(client, test_session_factory, hero_hp=5)
    async with test_session_factory() as s:  # spossatezza 4 (2014): massimo effettivo 20, la metà è 10, ne restano 5
        h = await s.get(Character, hero)
        h.conditions = {**(h.conditions or {}), "exhaustion": 4}
        await s.commit()
    assert (await _go(client, cleric, [(hero, 6)])).status_code == 422
    assert (await _go(client, cleric, [(hero, 5)])).status_code == 200
