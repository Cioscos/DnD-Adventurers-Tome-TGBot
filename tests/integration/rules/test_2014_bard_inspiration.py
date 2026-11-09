"""Bardo 2014, giro 1: dado di Ispirazione dato a un alleato (I1, R38) e Canto di Riposo nel flusso del riposo (I6)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from core.db.models import AbilityScore, Character, GameSession, SessionParticipant, SessionRole, SessionStatus
from core.rules.roll_options import refund_spent
from tests.integration._encounter_helpers import GM_ID, NOW, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard import (
    BI, LORE, SONG, VALOR, _ability, _bard, _full, _hurt, _roll_keys, _spend, _states, _use,
)

STATE = "bardic_die"


async def _seat(test_session_factory, cid, user=GM_ID) -> None:
    async with test_session_factory() as s:
        part = (await s.execute(select(SessionParticipant).where(SessionParticipant.user_id == user))).scalar_one()
        part.character_id = cid
        await s.commit()


async def _table(client, test_session_factory, level=5, subclass=None):
    """Una serata con il bardo (GM) e un eroe: restituisce `(session_id, bard, hero)`."""
    sid, hero = await seed_session(test_session_factory)
    as_user(GM_ID)
    bard = await _bard(client, level, subclass, charisma=16)
    await _seat(test_session_factory, bard)
    return sid, bard, hero


async def _second_ally(test_session_factory, sid, user=9001) -> int:
    async with test_session_factory() as s:
        char = Character(user_id=user, name="Compagno")
        s.add(char)
        await s.flush()
        s.add(AbilityScore(character_id=char.id, name="dexterity", value=12))
        s.add(SessionParticipant(session_id=sid, user_id=user, character_id=char.id, role=SessionRole.PLAYER,
                                 display_name="Compagno", joined_at=NOW))
        await s.commit()
        return char.id


async def _give(client, bard, target, user=GM_ID):
    as_user(user)
    return await client.post(f"/characters/{bard}/features/{BI}/use", json={"params": {"target_character_id": target}})


def _states_of(full, key=STATE) -> list[dict]:
    return [s for s in full["active_states"] or [] if s["key"] == key]


async def test_inspiration_goes_to_the_chosen_ally_with_its_die(client, test_session_factory):
    sid, bard, hero = await _table(client, test_session_factory, level=5)
    r = await _give(client, bard, hero)
    assert r.status_code == 200, r.text
    assert (await _ability(client, bard, BI))["uses"] == (await _ability(client, bard, BI))["max_uses"] - 1
    assert await _states(client, bard) == []  # lo stato sta sul ricevente
    as_user(PLAYER_ID)
    [state] = _states_of(await _full(client, hero))
    assert state["data"]["die"] == 8 and state["rounds_left"] == 100 and not state["data"].get("combat")
    assert set(state["ends_on"]) == {"rest_short", "rest_long", "manual"} and state["name"] == "Ispirazione Bardica"


async def test_only_one_die_per_creature_and_one_each_for_two_allies(client, test_session_factory):
    sid, bard, hero = await _table(client, test_session_factory)
    friend = await _second_ally(test_session_factory, sid)
    await _give(client, bard, hero)
    as_user(GM_ID)
    await client.post(f"/characters/{bard}/turn/new")
    await _give(client, bard, hero)  # lo stesso alleato: il nuovo dado sostituisce il vecchio
    as_user(PLAYER_ID)
    assert len(_states_of(await _full(client, hero))) == 1
    as_user(GM_ID)
    await client.post(f"/characters/{bard}/turn/new")
    assert (await _give(client, bard, friend)).status_code == 200
    as_user(9001)
    assert len(_states_of(await _full(client, friend))) == 1  # un altro alleato ha il suo, senza togliere l'altro
    as_user(PLAYER_ID)
    assert len(_states_of(await _full(client, hero))) == 1


@pytest.mark.parametrize("who", ["self", "stranger", "other_session", "no_session"])
async def test_the_target_must_be_another_character_at_the_same_table(client, test_session_factory, who):
    sid, bard, hero = await _table(client, test_session_factory)
    as_user(GM_ID)
    if who == "self":
        target = bard
    elif who == "stranger":
        as_user(4242)
        target = await _bard(client, 3)
        as_user(GM_ID)
    elif who == "other_session":
        async with test_session_factory() as s:
            other = GameSession(code="ZZZ999", gm_user_id=4243, status=SessionStatus.ACTIVE, created_at=NOW, last_activity_at=NOW)
            s.add(other)
            await s.flush()
            char = Character(user_id=4244, name="Altrove")
            s.add(char)
            await s.flush()
            s.add(SessionParticipant(session_id=other.id, user_id=4244, character_id=char.id, role=SessionRole.PLAYER,
                                     display_name="Altrove", joined_at=NOW))
            await s.commit()
            target = char.id
    else:  # il bardo non siede a nessuna serata
        await _seat(test_session_factory, None)
        target = hero
    r = await _give(client, bard, target)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_target", r.text
    ability = await _ability(client, bard, BI)
    assert ability["uses"] == ability["max_uses"]  # nulla speso
    assert (await client.get(f"/characters/{bard}/turn-state")).json()["turn"]["bonus_used"] is False


async def test_the_table_lists_the_allies_to_pick_from(client, test_session_factory):
    sid, bard, hero = await _table(client, test_session_factory)
    friend = await _second_ally(test_session_factory, sid)
    as_user(GM_ID)
    allies = (await client.get(f"/characters/{bard}/session-allies")).json()
    assert {(a["id"], a["name"]) for a in allies} == {(hero, "Eroe"), (friend, "Compagno")}
    lone = await _bard(client, 3)
    assert (await client.get(f"/characters/{lone}/session-allies")).json() == []  # fuori serata: nessun elenco


async def _hero_roll(client, hero, skill="athletics", die=10):
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{hero}/skills/{skill}/roll", json={"die": die})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("roll,query", [("skill", {"skill": "athletics"}), ("save", {"ability": "wisdom"}),
                                        ("attack", {}), ("initiative", {}), ("ability", {"ability": "strength"})])
async def test_the_received_die_is_offered_after_every_kind_of_roll(client, test_session_factory, roll, query):
    sid, bard, hero = await _table(client, test_session_factory)
    as_user(PLAYER_ID)
    assert "bardic_die:add" not in await _roll_keys(client, hero, roll, **query)
    await _give(client, bard, hero)
    as_user(PLAYER_ID)
    assert "bardic_die:add" in await _roll_keys(client, hero, roll, **query)


async def test_the_received_die_adds_to_the_total_and_closes_the_state(client, test_session_factory):
    sid, bard, hero = await _table(client, test_session_factory, level=5)
    await _give(client, bard, hero)
    first = await _hero_roll(client, hero)
    r = await client.post(f"/characters/{hero}/last-roll/options", json={"options": ["bardic_die:add"]})
    assert r.status_code == 200, r.text
    extra = r.json()["option_result"]
    assert len(extra["extra_rolls"]) == 1 and 1 <= extra["extra_total"] <= 8
    assert r.json()["total"] == first["total"] + extra["extra_total"]
    assert _states_of(await _full(client, hero)) == []  # il dado è speso
    again = await client.post(f"/characters/{hero}/last-roll/options", json={"options": ["bardic_die:add"]})
    assert again.status_code == 409


async def test_the_die_works_for_a_creature_on_the_2024_rules(client, test_session_factory):
    sid, bard, hero = await _table(client, test_session_factory)
    as_user(PLAYER_ID)
    assert (await client.patch(f"/characters/{hero}", json={"rules_edition": "2024"})).status_code == 200
    await _give(client, bard, hero)
    await _hero_roll(client, hero)
    r = await client.post(f"/characters/{hero}/last-roll/options", json={"options": ["bardic_die:add"]})
    assert r.status_code == 200, r.text


async def test_a_refund_gives_the_closed_state_back():
    char = SimpleNamespace(
        active_states=[{"key": STATE, "data": {"die": 8}, "rounds_left": 90}], turn_state={}, abilities=[],
        spell_slots=[], settings={})
    from core.rules.roll_options import _spend_state_token  # il gettone che apply_options registra alla chiusura

    token = _spend_state_token(char, STATE)
    assert char.active_states == [] and token.startswith("state:bardic_die:")
    refund_spent(char, [token])
    assert [(s["key"], s["rounds_left"], s["data"]["die"]) for s in char.active_states] == [(STATE, 90, 8)]


async def test_the_die_spent_after_a_roll_comes_back_with_the_recorded_refund(client, test_session_factory):
    sid, bard, hero = await _table(client, test_session_factory)
    await _give(client, bard, hero)
    await _hero_roll(client, hero)
    r = await client.post(f"/characters/{hero}/last-roll/options", json={"options": ["bardic_die:add"]})
    spent = r.json()["option_result"]["spent"]
    assert any(t.startswith("state:bardic_die:") for t in spent)
    async with test_session_factory() as s:
        char = await s.get(Character, hero)
        assert not [st for st in char.active_states or [] if st["key"] == STATE]
        refund_spent(char, spent)
        assert [st["key"] for st in char.active_states] == [STATE]


# Ispirazione in Combattimento (Collegio del Valore)

async def _sword(client, cid) -> int:
    meta = {"damage_dice": "1d8", "weapon_type": "melee", "properties": []}
    r = await client.post(f"/characters/{cid}/items", json={"name": "Spada", "item_type": "weapon", "item_metadata": meta})
    wid = max(i["id"] for i in r.json()["items"] if i["name"] == "Spada")
    r = await client.patch(f"/characters/{cid}/items/{wid}", json={"is_equipped": True, "equipment_slot": "main_hand"})
    assert r.status_code == 200, r.text
    return wid


async def test_combat_inspiration_only_comes_from_a_valor_bard(client, test_session_factory):
    sid, bard, hero = await _table(client, test_session_factory, level=3, subclass=VALOR)
    await _give(client, bard, hero)
    as_user(PLAYER_ID)
    [state] = _states_of(await _full(client, hero))
    assert state["data"]["combat"] is True
    assert "bardic_die:damage" in await _roll_keys(client, hero, "attack")


async def test_a_lore_bard_die_has_no_combat_use(client, test_session_factory):
    sid, bard, hero = await _table(client, test_session_factory, level=3, subclass=LORE)
    await _give(client, bard, hero)
    as_user(PLAYER_ID)
    assert "bardic_die:damage" not in await _roll_keys(client, hero, "attack")
    assert (await client.post(f"/characters/{hero}/bardic-die/ac")).status_code == 409


@pytest.mark.parametrize("die,critical", [(10, False), (20, True)])
async def test_combat_inspiration_adds_one_die_to_the_damage_even_on_a_critical(client, test_session_factory, die, critical):
    sid, bard, hero = await _table(client, test_session_factory, level=3, subclass=VALOR)
    await _give(client, bard, hero)
    as_user(PLAYER_ID)
    wid = await _sword(client, hero)
    first = (await client.post(f"/characters/{hero}/items/{wid}/attack", json={"die": die, "defer_damage": True})).json()
    assert first["is_critical"] is critical
    r = await client.post(f"/characters/{hero}/attack/{first['attack_id']}/damage", json={"options": ["bardic_die:damage"]})
    assert r.status_code == 200, r.text
    block = r.json()["option_result"]
    assert len(block["extra_rolls"]) == 1 and 1 <= block["extra_total"] <= 6  # il dado non raddoppia col critico
    assert _states_of(await _full(client, hero)) == []


async def test_combat_inspiration_adds_the_die_to_the_armor_class_as_a_reaction(client, test_session_factory):
    sid, bard, hero = await _table(client, test_session_factory, level=3, subclass=VALOR)
    await _give(client, bard, hero)
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{hero}/bardic-die/ac")
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 6 and 1 <= r.json()["roll"] <= 6
    assert (await client.get(f"/characters/{hero}/turn-state")).json()["turn"]["reaction_used"] is True
    assert _states_of(await _full(client, hero)) == []
    assert (await client.post(f"/characters/{hero}/bardic-die/ac")).status_code == 409  # il dado è speso


async def test_the_armor_class_use_keeps_the_die_when_the_reaction_is_spent(client, test_session_factory):
    sid, bard, hero = await _table(client, test_session_factory, level=3, subclass=VALOR)
    await _give(client, bard, hero)
    as_user(PLAYER_ID)
    await client.post(f"/characters/{hero}/turn/use", json={"slot": "reaction"})
    r = await client.post(f"/characters/{hero}/bardic-die/ac")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "turn_slot_used"
    assert len(_states_of(await _full(client, hero))) == 1


# ---------------------------------------------------------------------------
# I6: Canto di Riposo nel flusso del riposo
# ---------------------------------------------------------------------------

async def _friend_at_the_table(client, test_session_factory):
    sid, hero = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    await client.post(f"/characters/{hero}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})
    await _hurt(test_session_factory, hero)
    as_user(GM_ID)
    bard = await _bard(client, 2)
    await _seat(test_session_factory, bard)
    return bard, hero


async def test_the_bard_rests_first_and_the_friend_who_spends_later_still_gets_the_die(client, test_session_factory):
    bard, hero = await _friend_at_the_table(client, test_session_factory)
    await _use(client, bard, SONG)
    assert (await client.post(f"/characters/{bard}/rest", json={"rest_type": "short"})).status_code == 200
    assert [s["key"] for s in await _states(client, bard)] == ["song_of_rest"]  # il riposo del bardo non lo chiude
    as_user(PLAYER_ID)
    spent = await _spend(client, hero)
    assert len(spent["song_rolls"]) == 1 and 1 <= spent["song_rolls"][0] <= 6


async def test_the_song_ends_with_a_long_rest_by_hand_or_at_the_next_new_turn(client):
    for how in ("long", "manual", "turn"):
        cid = await _bard(client, 2)
        await _use(client, cid, SONG)
        if how == "long":
            await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
        elif how == "manual":
            assert (await client.delete(f"/characters/{cid}/active-states/song_of_rest")).status_code == 200
        else:
            await client.post(f"/characters/{cid}/turn/new")
        assert await _states(client, cid) == [], how
