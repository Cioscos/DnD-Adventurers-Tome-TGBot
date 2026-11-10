"""Barbaro 2024, giro di correzione 1 (I2, R42/R46): Rivivificazione cura un personaggio della serata."""
from __future__ import annotations

from sqlalchemy import select

from core.db.models import Character, CharacterHistory, SessionParticipant
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_barbarian import _ability, _turn
from tests.integration.rules.test_2024_barbarian import _barbarian, _rage
from tests.integration.rules.test_2024_barbarian_paths import ZEALOT, _spent, _use


async def _table(client, factory, level=14):
    """Una serata con lo Zelota in forma divina (GM) e un eroe a 0 PF: `(barbarian, hero)`."""
    _, hero = await seed_session(factory)
    as_user(GM_ID)
    cid = await _barbarian(client, level, ZEALOT)
    async with factory() as s:
        part = (await s.execute(select(SessionParticipant).where(SessionParticipant.user_id == GM_ID))).scalar_one()
        part.character_id = cid
        char = await s.get(Character, hero)
        char.hit_points, char.current_hit_points = 40, 0
        await s.commit()
    assert (await _rage(client, cid, divine_form=True)).status_code == 200
    return cid, hero


async def _hero(factory, hero) -> Character:
    async with factory() as s:
        return await s.get(Character, hero)


def _revive(client, cid, hero):
    params = {"mode": "other", **({"target_character_id": hero} if hero is not None else {})}
    return _use(client, cid, "revivification", params=params)


async def test_revivification_brings_a_seated_ally_up_to_the_barbarian_level_and_spends_a_use_and_the_reaction(client, test_session_factory):
    cid, hero = await _table(client, test_session_factory)
    before = await _spent(client, cid)
    r = await _revive(client, cid, hero)
    assert r.status_code == 200, r.text
    assert r.json()["received"] == {"name": "Eroe", "healed": 14} and r.json()["healed"] == 0  # a chi usa non cura nulla
    assert (await _hero(test_session_factory, hero)).current_hit_points == 14
    assert await _spent(client, cid) == before - 1 and (await _turn(client, cid))["reaction_used"] is True
    async with test_session_factory() as s:  # lo storico sta sulla scheda del ricevente
        events = (await s.execute(select(CharacterHistory).where(CharacterHistory.character_id == hero))).scalars().all()
    assert any(e.event_type == "hp_change" and "+14" in e.description for e in events)


async def test_revivification_brings_the_hit_points_to_the_level_it_does_not_add_to_them(client, test_session_factory):
    cid, hero = await _table(client, test_session_factory)
    async with test_session_factory() as s:
        (await s.get(Character, hero)).current_hit_points = 7
        await s.commit()
    r = await _revive(client, cid, hero)
    assert r.json()["received"] == {"name": "Eroe", "healed": 7}  # 7 -> 14, non 21 (M1)
    assert (await _hero(test_session_factory, hero)).current_hit_points == 14


async def test_revivification_1_refuses_an_ally_already_at_or_above_the_level_and_spends_nothing(client, test_session_factory):
    cid, hero = await _table(client, test_session_factory)
    async with test_session_factory() as s:
        (await s.get(Character, hero)).current_hit_points = 30
        await s.commit()
    before = await _spent(client, cid)
    r = await _revive(client, cid, hero)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "target_not_down"
    assert (await _hero(test_session_factory, hero)).current_hit_points == 30
    assert await _spent(client, cid) == before and (await _turn(client, cid))["reaction_used"] is False


async def test_revivification_refuses_someone_not_at_the_table_and_spends_nothing(client, test_session_factory):
    cid, hero = await _table(client, test_session_factory)
    async with test_session_factory() as s:
        stranger = Character(user_id=9001, name="Estraneo", hit_points=40, current_hit_points=0)
        s.add(stranger)
        await s.commit()
        stranger_id = stranger.id
    before = await _spent(client, cid)
    for target in (stranger_id, cid, 99999):
        r = await _revive(client, cid, target)
        assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_target"
    assert await _spent(client, cid) == before and (await _turn(client, cid))["reaction_used"] is False
    assert (await _hero(test_session_factory, stranger_id)).current_hit_points == 0


async def test_revivification_refuses_a_dead_ally_and_spends_nothing(client, test_session_factory):
    cid, hero = await _table(client, test_session_factory)
    async with test_session_factory() as s:
        (await s.get(Character, hero)).is_dead = True
        await s.commit()
    before = await _spent(client, cid)
    r = await _revive(client, cid, hero)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "target_dead"
    assert await _spent(client, cid) == before and (await _turn(client, cid))["reaction_used"] is False


async def test_revivification_without_a_target_gives_the_level_and_says_what_to_tell_the_gm(client, test_session_factory):
    cid, _ = await _table(client, test_session_factory)
    r = await _revive(client, cid, None)
    assert r.status_code == 200, r.text
    assert r.json()["given"] == 14 and r.json()["received"] is None and r.json()["notes"] == ["revivification_other"]


async def test_revivification_is_aimed_at_another_creature_and_exposes_the_ally_mode(client, test_session_factory):
    cid, _ = await _table(client, test_session_factory)
    row = await _ability(client, cid, "barbarian.revivification")
    assert row["ally_modes"] == ["other"]
    assert [c["key"] for c in row["use_choices"]] == ["mode"]
    assert (await _use(client, cid, "revivification", params={"mode": "self"})).status_code == 422  # niente scelta valida
