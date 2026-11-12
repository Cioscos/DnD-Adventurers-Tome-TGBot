"""GET /characters/{id}/turn-state (routers/sessions.py)."""
from __future__ import annotations

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration._encounter_helpers import setup_full_encounter


async def test_turn_state_not_in_session(client, test_session_factory):
    _, char_id = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    r = await client.get(f"/characters/{char_id}/turn-state")
    assert r.status_code == 200, r.text
    assert {k: v for k, v in r.json().items() if k not in ("turn", "attacks_allowed", "attacks_allowed_pact", "hide_min_total", "effects_sig")} == {"in_encounter": False, "is_my_turn": False, "round": None, "session_id": None, "pending_saves": []}


async def test_turn_state_my_turn_true(client, test_session_factory):
    sid, enc = await setup_full_encounter(client, test_session_factory)
    pc = next(c for c in enc["combatants"] if c["kind"] == "pc")
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter/start", json={})
    assert r.status_code == 200, r.text
    as_user(PLAYER_ID)
    r = await client.get(f"/characters/{pc['character_id']}/turn-state")
    assert {k: v for k, v in r.json().items() if k not in ("turn", "attacks_allowed", "attacks_allowed_pact", "hide_min_total", "effects_sig")} == {"in_encounter": True, "is_my_turn": True, "round": 1, "session_id": sid, "pending_saves": []}
    # Dopo next-turn tocca a un goblin.
    as_user(GM_ID)
    await client.post(f"/sessions/{sid}/encounter/next-turn")
    as_user(PLAYER_ID)
    r = await client.get(f"/characters/{pc['character_id']}/turn-state")
    assert r.json()["in_encounter"] is True and r.json()["is_my_turn"] is False


async def test_turn_state_other_user_forbidden(client, test_session_factory):
    _, char_id = await seed_session(test_session_factory)
    r = await client.get(f"/characters/{char_id}/turn-state")  # GM_ID non è il proprietario
    assert r.status_code == 403


async def test_turn_state_effects_sig_changes_with_states_and_is_stable(client, test_session_factory):
    from core.db.models import Character
    _, char_id = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    sig = lambda: client.get(f"/characters/{char_id}/turn-state")  # noqa: E731
    first = (await sig()).json()["effects_sig"]
    assert first and (await sig()).json()["effects_sig"] == first
    async with test_session_factory() as s:
        (await s.get(Character, char_id)).active_states = [{"key": "spell:shield_of_faith", "data": {}}]
        await s.commit()
    assert (await sig()).json()["effects_sig"] != first


async def test_turn_state_effects_sig_changes_with_hp_and_ability_uses(client, test_session_factory):
    from core.db.models import Ability, Character
    _, char_id = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    sig = lambda: client.get(f"/characters/{char_id}/turn-state")  # noqa: E731
    async with test_session_factory() as s:
        s.add(Ability(character_id=char_id, name="Ispirazione Bardica", max_uses=3, uses=3))
        await s.commit()
    first = (await sig()).json()["effects_sig"]
    async with test_session_factory() as s:
        (await s.get(Character, char_id)).current_hit_points += 5  # cura istantanea di un alleato
        await s.commit()
    second = (await sig()).json()["effects_sig"]
    assert second != first
    async with test_session_factory() as s:
        from sqlalchemy import select
        (await s.execute(select(Ability).where(Ability.character_id == char_id))).scalar_one().uses = 2
        await s.commit()
    assert (await sig()).json()["effects_sig"] != second
