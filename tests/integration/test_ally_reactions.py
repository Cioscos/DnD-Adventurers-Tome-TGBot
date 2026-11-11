"""Reazioni degli alleati a un danno (Task 1): richiesta, idoneità, presenza, risposta del donatore, chiusura."""
from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from api.services import ally_reactions as svc
from api.services.character_load import get_owned_full_with_resources
from core.db.models import Character, GameSession, SessionParticipant, SessionRole, SessionStatus
from tests.integration._encounter_helpers import NOW, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard import BI, LORE as LORE_2014, _ability, _bard, _use
from tests.integration.rules.test_2014_fighter_styles import _item
from tests.integration.rules.test_2024_bard import LORE as LORE_2024, _bard24, _set_uses, _turn
from tests.integration.rules.test_2024_fighter import _styled

INTERCEPTION, CUTTING = "fighter.style_interception", "bard.cutting_words"
FIGHTER_USER, BARD_USER, OUTSIDER_USER = 11, 12, 13


@pytest.fixture(autouse=True)
def _clean_presence():
    svc._SEEN.clear()
    yield
    svc._SEEN.clear()


@pytest.fixture
def clock(monkeypatch):
    now = [svc.utc_now()]
    monkeypatch.setattr(svc, "utc_now", lambda: now[0])
    return now


async def _seat(factory, sid, uid, cid, name) -> None:
    async with factory() as s:
        s.add(SessionParticipant(session_id=sid, user_id=uid, character_id=cid, role=SessionRole.PLAYER,
                                 display_name=name, joined_at=NOW))
        await s.commit()


async def _fighter(client, factory, sid, armed=True) -> int:
    as_user(FIGHTER_USER)
    cid = await _styled(client, "interception")
    if armed:
        await _item(client, cid, "Spada", damage_dice="1d8", weapon_type="melee", properties=[], equip="main_hand")
    await _seat(factory, sid, FIGHTER_USER, cid, "Guerriero")
    return cid


async def _lore_bard(client, factory, sid, edition="2024") -> int:
    as_user(BARD_USER)
    cid = await (_bard24(client, 3, LORE_2024, charisma=16) if edition == "2024" else _bard(client, 3, LORE_2014, charisma=16))
    await _seat(factory, sid, BARD_USER, cid, "Bardo")
    return cid


async def _poll(client, cid, uid) -> list[dict]:
    as_user(uid)
    r = await client.get(f"/characters/{cid}/reaction-prompts")
    assert r.status_code == 200, r.text
    return r.json()


async def _open(client, hero, damage=12) -> dict:
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{hero}/ally-reactions", json={"damage": damage, "damage_type": "slashing"})
    assert r.status_code == 200, r.text
    return r.json()


async def _answer(client, cid, uid, rid, use):
    as_user(uid)
    return await client.post(f"/characters/{cid}/reaction-prompts/{rid}", json={"use": use})


async def _read(client, hero, rid) -> dict:
    as_user(PLAYER_ID)
    r = await client.get(f"/characters/{hero}/ally-reactions/{rid}")
    assert r.status_code == 200, r.text
    return r.json()


async def _table(client, factory):
    """Serata con ricevente, guerriero armato (Intercettazione) e bardo della Sapienza 2024, tutti presenti."""
    sid, hero = await seed_session(factory)
    fighter = await _fighter(client, factory, sid)
    bard = await _lore_bard(client, factory, sid)
    await _poll(client, fighter, FIGHTER_USER)
    await _poll(client, bard, BARD_USER)
    return sid, hero, fighter, bard


async def test_open_lists_present_donors(client, test_session_factory):
    _, hero, fighter, bard = await _table(client, test_session_factory)
    out = await _open(client, hero)
    assert out["request_id"] is not None and out["expires_in"] == 30
    assert {(w["character_id"], w["feature_key"]) for w in out["waiting"]} == {(fighter, INTERCEPTION), (bard, CUTTING)}
    prompts = await _poll(client, fighter, FIGHTER_USER)
    assert prompts == [{"request_id": out["request_id"], "receiver_name": "Eroe", "damage": 12, "damage_type": "slashing",
                        "feature_key": INTERCEPTION, "dice": "1d10+2"}]


async def test_no_request_without_present_donors(client, test_session_factory):
    sid, hero = await seed_session(test_session_factory)
    await _fighter(client, test_session_factory, sid)
    await _lore_bard(client, test_session_factory, sid)
    assert (await _open(client, hero))["request_id"] is None


async def test_presence_expires_after_fifteen_seconds(client, test_session_factory, clock):
    _, hero, *_ = await _table(client, test_session_factory)
    clock[0] += timedelta(seconds=16)
    assert (await _open(client, hero))["request_id"] is None


async def test_no_request_outside_session(client, test_session_factory):
    sid, hero, fighter, bard = await _table(client, test_session_factory)
    as_user(OUTSIDER_USER)
    r = await client.post("/characters", json={"name": "Fuori", "initial_class": {"class_name": "fighter", "level": 1, "subclass": None}})
    outsider = r.json()["id"]
    assert (await client.post(f"/characters/{outsider}/ally-reactions", json={"damage": 10})).json()["request_id"] is None


async def test_interception_not_for_self(client, test_session_factory):
    _, hero, fighter, bard = await _table(client, test_session_factory)
    as_user(FIGHTER_USER)
    out = (await client.post(f"/characters/{fighter}/ally-reactions", json={"damage": 9})).json()
    assert [w["character_id"] for w in out["waiting"]] == [bard]  # il guerriero colpito non è nella sua lista
    as_user(BARD_USER)
    out = (await client.post(f"/characters/{bard}/ally-reactions", json={"damage": 9})).json()
    assert [w["character_id"] for w in out["waiting"]] == [fighter]  # nemmeno il bardo: per lui servirà un'altra strada


async def test_unarmed_fighter_not_eligible(client, test_session_factory):
    sid, hero = await seed_session(test_session_factory)
    fighter = await _fighter(client, test_session_factory, sid, armed=False)
    await _poll(client, fighter, FIGHTER_USER)
    assert (await _open(client, hero))["request_id"] is None


async def test_bard_without_inspiration_not_eligible(client, test_session_factory):
    sid, hero = await seed_session(test_session_factory)
    bard = await _lore_bard(client, test_session_factory, sid)
    await _set_uses(client, bard, BI, 0)
    await _poll(client, bard, BARD_USER)
    assert (await _open(client, hero))["request_id"] is None


async def test_reaction_already_used_not_eligible(client, test_session_factory):
    _, hero, fighter, bard = await _table(client, test_session_factory)
    as_user(FIGHTER_USER)
    assert (await _use(client, fighter, INTERCEPTION)).status_code == 200
    assert [w["character_id"] for w in (await _open(client, hero))["waiting"]] == [bard]


async def test_use_interception(client, test_session_factory, monkeypatch):
    monkeypatch.setattr("api.services.rules_states.random.randint", lambda a, b: 7)
    _, hero, fighter, bard = await _table(client, test_session_factory)
    rid = (await _open(client, hero))["request_id"]
    r = await _answer(client, fighter, FIGHTER_USER, rid, True)
    assert r.status_code == 200 and r.json() == {"reduction": 7 + 2, "rolls": [7]}
    assert (await _turn(client, fighter))["reaction_used"] is True
    history = (await client.get(f"/characters/{fighter}/history")).json()
    assert any("Intercettazione" in e["description"] and "Eroe" in e["description"] for e in history)
    assert (await _read(client, hero, rid))["total_reduction"] == 9


@pytest.mark.parametrize("edition", ["2014", "2024"])
async def test_use_cutting_words(client, test_session_factory, monkeypatch, edition):
    monkeypatch.setattr("api.services.rules_states.random.randint", lambda a, b: 4)
    sid, hero = await seed_session(test_session_factory)
    bard = await _lore_bard(client, test_session_factory, sid, edition)
    await _poll(client, bard, BARD_USER)
    before = (await _ability(client, bard, BI))["uses"]
    rid = (await _open(client, hero))["request_id"]
    r = await _answer(client, bard, BARD_USER, rid, True)
    assert r.status_code == 200 and r.json() == {"reduction": 4, "rolls": [4]}
    assert (await _ability(client, bard, BI))["uses"] == before - 1
    assert (await _turn(client, bard))["reaction_used"] is True


async def test_the_answer_keeps_what_was_spent_for_the_refund(client, test_session_factory):
    from core.db.models import AllyReactionRequest
    _, hero, fighter, bard = await _table(client, test_session_factory)
    rid = (await _open(client, hero))["request_id"]
    await _answer(client, bard, BARD_USER, rid, True)
    row_id = (await _ability(client, bard, BI))["id"]
    async with test_session_factory() as s:
        spent = {a["donor_id"]: a["spent"] for a in (await s.get(AllyReactionRequest, rid)).answers}
    assert spent[bard] == {"slot": "reaction", "ability_id": row_id, "uses": 1} and spent[fighter] is None


async def test_decline_spends_nothing(client, test_session_factory):
    _, hero, fighter, bard = await _table(client, test_session_factory)
    rid = (await _open(client, hero))["request_id"]
    as_user(BARD_USER)
    uses = (await _ability(client, bard, BI))["uses"]
    assert (await _answer(client, bard, BARD_USER, rid, False)).json() == {"reduction": 0, "rolls": []}
    assert (await _turn(client, bard))["reaction_used"] is False and (await _ability(client, bard, BI))["uses"] == uses
    body = await _read(client, hero, rid)
    assert [(a["name"], a["status"]) for a in body["answers"]] == [("Bardo", "declined")] and body["total_reduction"] == 0
    assert [w["character_id"] for w in body["waiting"]] == [fighter] and body["status"] == "open"


async def test_closes_when_all_answered(client, test_session_factory):
    _, hero, fighter, bard = await _table(client, test_session_factory)
    rid = (await _open(client, hero))["request_id"]
    await _answer(client, fighter, FIGHTER_USER, rid, True)
    assert (await _read(client, hero, rid))["status"] == "open"
    await _answer(client, bard, BARD_USER, rid, True)
    body = await _read(client, hero, rid)
    assert body["status"] == "closed" and body["waiting"] == [] and len(body["answers"]) == 2 and body["total_reduction"] >= 4


async def test_closes_after_30_seconds(client, test_session_factory, clock):
    _, hero, fighter, bard = await _table(client, test_session_factory)
    rid = (await _open(client, hero))["request_id"]
    clock[0] += timedelta(seconds=29)
    assert (await _read(client, hero, rid))["status"] == "open"
    clock[0] += timedelta(seconds=2)
    body = await _read(client, hero, rid)
    assert body["status"] == "closed" and body["waiting"] == []
    assert await _poll(client, bard, BARD_USER) == []  # il popup sparisce
    assert (await _answer(client, bard, BARD_USER, rid, True)).status_code == 409


async def test_close_by_receiver(client, test_session_factory):
    _, hero, fighter, bard = await _table(client, test_session_factory)
    rid = (await _open(client, hero))["request_id"]
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{hero}/ally-reactions/{rid}/close")
    assert r.status_code == 200 and r.json()["status"] == "closed"
    assert (await client.post(f"/characters/{hero}/ally-reactions/{rid}/close")).status_code == 200  # una volta sola, senza errori


async def test_answer_after_close_409(client, test_session_factory):
    _, hero, fighter, bard = await _table(client, test_session_factory)
    rid = (await _open(client, hero))["request_id"]
    as_user(PLAYER_ID)
    await client.post(f"/characters/{hero}/ally-reactions/{rid}/close")
    as_user(BARD_USER)
    uses = (await _ability(client, bard, BI))["uses"]
    r = await _answer(client, bard, BARD_USER, rid, True)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "request_closed"
    assert (await _turn(client, bard))["reaction_used"] is False and (await _ability(client, bard, BI))["uses"] == uses
    assert (await _read(client, hero, rid))["total_reduction"] == 0


async def test_reaction_spent_meanwhile_409(client, test_session_factory):
    _, hero, fighter, bard = await _table(client, test_session_factory)
    rid = (await _open(client, hero))["request_id"]
    as_user(FIGHTER_USER)
    assert (await _use(client, fighter, INTERCEPTION)).status_code == 200  # la reazione parte per un'altra strada
    r = await _answer(client, fighter, FIGHTER_USER, rid, True)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "turn_slot_used"
    body = await _read(client, hero, rid)
    assert [(a["name"], a["status"]) for a in body["answers"]] == [("Guerriero", "declined")]
    assert (await _answer(client, fighter, FIGHTER_USER, rid, True)).status_code == 409  # già risposto


@pytest.mark.parametrize("what", ["stunned", "dead"])
async def test_donor_down_after_opening_cannot_use(client, test_session_factory, what):
    _, hero, fighter, bard = await _table(client, test_session_factory)
    rid = (await _open(client, hero))["request_id"]
    async with test_session_factory() as s:
        ch = await s.get(Character, fighter)
        if what == "dead":
            ch.is_dead = True
        else:
            ch.conditions = {"stunned": True}
        await s.commit()
    r = await _answer(client, fighter, FIGHTER_USER, rid, True)
    assert r.status_code == 409
    assert (await _turn(client, fighter))["reaction_used"] is False
    body = await _read(client, hero, rid)
    assert [(a["name"], a["status"]) for a in body["answers"]] == [("Guerriero", "declined")] and body["total_reduction"] == 0


async def test_answer_after_session_closed_409(client, test_session_factory):
    sid, hero, fighter, bard = await _table(client, test_session_factory)
    rid = (await _open(client, hero))["request_id"]
    async with test_session_factory() as s:
        (await s.get(GameSession, sid)).status = SessionStatus.CLOSED
        await s.commit()
    r = await _answer(client, fighter, FIGHTER_USER, rid, True)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "request_closed"
    assert (await _turn(client, fighter))["reaction_used"] is False


async def test_answer_with_non_donor_character_404(client, test_session_factory):
    _, hero, fighter, bard = await _table(client, test_session_factory)
    rid = (await _open(client, hero))["request_id"]
    as_user(PLAYER_ID)  # possiede l'eroe, che non è donatore di questa richiesta
    r = await client.post(f"/characters/{hero}/reaction-prompts/{rid}", json={"use": True})
    assert r.status_code == 404 and r.json()["detail"]["code"] == "request_not_found"


async def test_other_players_cannot_read_or_answer(client, test_session_factory):
    _, hero, fighter, bard = await _table(client, test_session_factory)
    rid = (await _open(client, hero))["request_id"]
    as_user(BARD_USER)
    assert (await client.get(f"/characters/{hero}/ally-reactions/{rid}")).status_code == 403
    assert (await client.post(f"/characters/{fighter}/reaction-prompts/{rid}", json={"use": True})).status_code == 403
    as_user(PLAYER_ID)
    assert (await client.get(f"/characters/{fighter}/ally-reactions/{rid}")).status_code == 403


async def test_concurrent_answers_both_recorded(client, test_session_factory):
    _, hero, fighter, bard = await _table(client, test_session_factory)
    rid = (await _open(client, hero))["request_id"]

    async def one(cid, uid):
        async with test_session_factory() as s:
            donor = await get_owned_full_with_resources(cid, uid, s)
            out = await svc.answer(s, donor, rid, True)
            await s.commit()
            return out

    await asyncio.gather(one(fighter, FIGHTER_USER), one(bard, BARD_USER))
    body = await _read(client, hero, rid)
    assert sorted(a["status"] for a in body["answers"]) == ["used", "used"] and body["status"] == "closed"
