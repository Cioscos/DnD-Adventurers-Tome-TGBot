"""Paladino 2014, giro di correzione 1 (I5, R46): Imposizione delle Mani su altri e cura di veleni."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from core.db.models import Character, CharacterHistory
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
from tests.integration.rules.test_2014_bard import _ability, _full, _use
from tests.integration.rules.test_2014_paladin import LOH, _hp, _hurt, _paladin, _turn
from tests.integration.rules.test_2014_paladin_auras import _table


async def _hero_hp(factory, hero, current, maximum=40, **fields) -> None:
    async with factory() as s:
        char = await s.get(Character, hero)
        char.hit_points, char.current_hit_points = maximum, current
        for name, value in fields.items():
            setattr(char, name, value)
        await s.commit()


async def _give(client, paladin, hero, amount, mode="other", **extra):
    params = {"mode": mode, **({"target_character_id": hero} if hero is not None else {}), **extra}
    return await client.post(f"/characters/{paladin}/features/{LOH}/use", json={"amount": amount, "params": params})


async def _pool(client, paladin) -> int:
    return (await _ability(client, paladin, LOH))["uses"]


async def _hero_state(factory, hero) -> tuple[int, dict]:
    async with factory() as s:
        char = await s.get(Character, hero)
        return char.current_hit_points, dict(char.conditions or {})


async def test_lay_on_hands_on_a_seated_ally_heals_them_and_spends_the_pool_and_the_action(client, test_session_factory):
    _, paladin, hero = await _table(client, test_session_factory, level=5)
    await _hero_hp(test_session_factory, hero, 5)
    as_user(GM_ID)
    r = await _give(client, paladin, hero, 8)
    assert r.status_code == 200, r.text
    assert r.json()["received"] == {"name": "Eroe", "healed": 8} and r.json()["healed"] == 0
    assert await _pool(client, paladin) == 25 - 8 and (await _turn(client, paladin))["action_used"] is True
    assert (await _hero_state(test_session_factory, hero))[0] == 13
    async with test_session_factory() as s:  # lo storico sta sulla scheda del ricevente
        events = (await s.execute(select(CharacterHistory).where(CharacterHistory.character_id == hero))).scalars().all()
    assert any(e.event_type == "hp_change" and "+8" in e.description for e in events)


async def test_the_heal_on_an_ally_never_goes_above_their_maximum_but_the_points_are_spent(client, test_session_factory):
    _, paladin, hero = await _table(client, test_session_factory, level=5)
    await _hero_hp(test_session_factory, hero, 38)
    as_user(GM_ID)
    r = await _give(client, paladin, hero, 10)
    assert r.json()["received"]["healed"] == 2 and (await _hero_state(test_session_factory, hero))[0] == 40
    assert await _pool(client, paladin) == 15


async def test_lay_on_hands_refuses_someone_who_is_not_at_the_table_and_changes_nothing(client, test_session_factory):
    _, paladin, hero = await _table(client, test_session_factory, level=5)
    async with test_session_factory() as s:
        stranger = Character(user_id=9001, name="Estraneo", hit_points=40, current_hit_points=1)
        s.add(stranger)
        await s.commit()
        stranger_id = stranger.id
    as_user(GM_ID)
    for target in (stranger_id, paladin, 99999):
        r = await _give(client, paladin, target, 5)
        assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_target"
    assert await _pool(client, paladin) == 25 and (await _turn(client, paladin))["action_used"] is False
    assert (await _hero_state(test_session_factory, stranger_id))[0] == 1


async def test_lay_on_hands_refuses_a_dead_ally_and_spends_nothing(client, test_session_factory):
    _, paladin, hero = await _table(client, test_session_factory, level=5)
    await _hero_hp(test_session_factory, hero, 0, is_dead=True)
    as_user(GM_ID)
    r = await _give(client, paladin, hero, 5)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "target_dead"
    assert await _pool(client, paladin) == 25 and (await _turn(client, paladin))["action_used"] is False


async def test_lay_on_hands_without_a_target_says_what_to_tell_the_gm_and_gives_the_points(client, test_session_factory):
    _, paladin, hero = await _table(client, test_session_factory, level=5)
    as_user(GM_ID)
    r = await _give(client, paladin, None, 7)
    assert r.status_code == 200, r.text
    assert r.json()["notes"] == ["lay_on_hands_other"] and r.json()["given"] == 7 and r.json()["received"] is None
    assert await _pool(client, paladin) == 25 - 7


async def test_a_target_sent_with_a_self_mode_is_ignored(client, test_session_factory):
    _, paladin, hero = await _table(client, test_session_factory, level=5)
    await _hero_hp(test_session_factory, hero, 5)
    as_user(GM_ID)
    await _hurt(test_session_factory, paladin, 10)
    r = await _give(client, paladin, hero, 4, mode="self")
    assert r.json()["healed"] == 4 and r.json()["received"] is None
    assert (await _hero_state(test_session_factory, hero))[0] == 5


async def test_two_requests_cannot_spend_the_same_points_twice(client, test_session_factory):
    import asyncio
    from tests.integration.rules.test_preserve_life_race import _user_from_header
    _, paladin, hero = await _table(client, test_session_factory, level=2)  # riserva 10
    await _hero_hp(test_session_factory, hero, 1)
    _user_from_header()
    body = {"amount": 8, "params": {"mode": "other", "target_character_id": hero}}
    rs = await asyncio.gather(*(client.post(f"/characters/{paladin}/features/{LOH}/use", json=body,
                                            headers={"x-test-user": str(GM_ID)}) for _ in range(3)))
    assert sorted(r.status_code for r in rs) == [200, 409, 409], [r.text for r in rs]
    as_user(GM_ID)
    assert await _pool(client, paladin) == 2
    assert (await _hero_state(test_session_factory, hero))[0] == 9  # una sola cura di 8


def _cure(targets, conditions) -> dict:
    """Task 48: stesso corpo `removal` degli incantesimi; il server calcola il costo (5 punti per voce)."""
    return {"mode": "cure", "removal": {"targets": targets, "conditions": conditions}}


async def test_cure_on_yourself_removes_poisoned_and_says_the_exceptions(client, test_session_factory):
    cid = await _paladin(client, 5)
    assert (await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"poisoned": True}})).status_code == 200
    r = await _use(client, cid, LOH, amount=1, params=_cure(["self"], ["poisoned", "disease"]))
    assert r.status_code == 200, r.text
    assert r.json()["notes"] == [] and r.json()["healed"] == 0
    assert "malattia" in " ".join(x["it"] for x in r.json()["removal"]).lower()  # la malattia resta una nota visibile
    assert not (await _full(client, cid))["conditions"].get("poisoned")
    assert await _pool(client, cid) == 15  # cinque punti per voce, deciso dal server


async def test_cure_on_yourself_only_costs_what_is_picked_and_leaves_other_conditions(client):
    cid = await _paladin(client, 5)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"blinded": True}})
    r = await _use(client, cid, LOH, amount=1, params=_cure(["self"], ["disease"]))
    assert r.status_code == 200 and r.json()["notes"] == [] and r.json()["removal"]
    assert (await _full(client, cid))["conditions"].get("blinded") is True and await _pool(client, cid) == 20


async def test_cure_on_an_ally_removes_the_poison_from_their_sheet_task48(client, test_session_factory):
    _, paladin, hero = await _table(client, test_session_factory, level=5)
    await _hero_hp(test_session_factory, hero, 5, conditions={"poisoned": True})
    as_user(GM_ID)
    r = await _use(client, paladin, LOH, amount=1, params=_cure([hero], ["poisoned"]))
    assert r.status_code == 200, r.text
    assert r.json()["notes"] == [] and r.json()["received"] is None
    assert await _pool(client, paladin) == 20
    assert await _hero_state(test_session_factory, hero) == (5, {"poisoned": False})


async def test_cure_refuses_a_missing_or_empty_removal_and_spends_nothing(client):
    cid = await _paladin(client, 5)
    for params in ({"mode": "cure"}, _cure(["self"], []), _cure(["self"], ["blinded"]), _cure([], ["poisoned"])):
        r = await _use(client, cid, LOH, amount=5, params=params)
        assert r.status_code == 422, (params, r.text)
    assert await _pool(client, cid) == 25


async def test_the_cure_mode_opens_the_common_sheet_and_heal_modes_do_not(client):
    cid = await _paladin(client, 5)
    row = await _ability(client, cid, LOH)
    assert row["ally_modes"] == ["other"] and row["removal"]["modes"] == ["cure"] and row["removal"]["cost_each"] == 5
    assert [c["key"] for c in row["removal"]["conditions"]] == ["poisoned"] and [u["key"] for u in row["removal"]["untracked"]] == ["disease"]
    [choice] = row["use_choices"]
    assert [o["key"] for o in choice["options"]] == ["self", "other", "cure"]
