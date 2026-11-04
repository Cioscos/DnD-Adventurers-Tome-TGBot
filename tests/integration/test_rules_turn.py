"""Stato del turno salvato sul server."""
from __future__ import annotations

from sqlalchemy import select

from core.db.models import Character
from core.rules.types import FeatureSpec
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session, setup_full_encounter
from tests.integration._telegram_stub import install_fake_telegram


async def _new_char(client, name="Turno") -> int:
    r = await client.post("/characters", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _turn(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}/turn-state")).json()


def _extra_attack(class_key: str, n: int = 2) -> FeatureSpec:
    return FeatureSpec(
        key=f"{class_key}.extra_attack", class_key=class_key, edition="2014", level=1, source_title="Prova",
        name={"it": "AE", "en": "EA"}, summary={"it": "x", "en": "x"}, action_type=None, passive=True,
        attacks_per_action=n,
    )


async def test_turn_state_persists_across_requests(client):
    cid = await _new_char(client)
    r = await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus"})
    assert r.status_code == 200 and r.json()["bonus_used"] is True
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "attack"})
    body = await _turn(client, cid)
    assert body["turn"]["bonus_used"] is True and body["turn"]["attacks_made"] == 1
    assert body["turn"]["action_used"] is False


async def test_slot_used_twice_returns_409(client):
    cid = await _new_char(client)
    assert (await client.post(f"/characters/{cid}/turn/use", json={"slot": "action"})).status_code == 200
    r = await client.post(f"/characters/{cid}/turn/use", json={"slot": "action"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "turn_slot_used"
    r = await client.post(f"/characters/{cid}/turn/use", json={"slot": "action", "used": False})
    assert r.json()["action_used"] is False


async def test_new_turn_resets(client):
    cid = await _new_char(client)
    for slot in ("action", "reaction", "attack"):
        await client.post(f"/characters/{cid}/turn/use", json={"slot": slot})
    r = await client.post(f"/characters/{cid}/turn/new")
    assert r.status_code == 200
    t = (await _turn(client, cid))["turn"]
    assert not t["action_used"] and not t["reaction_used"] and t["attacks_made"] == 0


async def test_encounter_advance_resets_only_that_character(client, test_session_factory, monkeypatch):
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)
    async with test_session_factory() as s:
        pc_id = (await s.execute(select(Character.id))).scalar_one()
        other = Character(user_id=PLAYER_ID, name="Altro", turn_state={"action_used": True})
        s.add(other)
        await s.commit()
        other_id = other.id
    as_user(PLAYER_ID)
    await client.post(f"/characters/{pc_id}/turn/use", json={"slot": "reaction"})
    as_user(GM_ID)
    await client.post(f"/sessions/{sid}/encounter/start", json={})
    # il PG (iniziativa più alta) apre il turno: reset anche al primo turno
    as_user(PLAYER_ID)
    assert (await _turn(client, pc_id))["turn"]["reaction_used"] is False
    await client.post(f"/characters/{pc_id}/turn/use", json={"slot": "action"})
    as_user(GM_ID)
    for _ in range(2):  # goblin 1, goblin 2: il PG non ricomincia
        await client.post(f"/sessions/{sid}/encounter/next-turn")
    as_user(PLAYER_ID)
    assert (await _turn(client, pc_id))["turn"]["action_used"] is True
    as_user(GM_ID)
    await client.post(f"/sessions/{sid}/encounter/next-turn")  # di nuovo il PG
    as_user(PLAYER_ID)
    assert (await _turn(client, pc_id))["turn"]["action_used"] is False
    async with test_session_factory() as s:
        assert (await s.get(Character, other_id)).turn_state == {"action_used": True}


async def test_attacks_allowed_uses_extra_attack(client):
    cid = await _new_char(client)
    assert (await _turn(client, cid))["attacks_allowed"] == 1
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 5})
    assert r.status_code == 201, r.text
    assert (await _turn(client, cid))["attacks_allowed"] == 2


async def test_multiclass_extra_attack_does_not_stack(client, rules_catalog):
    rules_catalog(_extra_attack("fighter"), _extra_attack("paladin"))
    cid = await _new_char(client)
    for cls in ("fighter", "paladin"):
        await client.post(f"/characters/{cid}/classes", json={"class_name": cls, "level": 5})
    assert (await _turn(client, cid))["attacks_allowed"] == 2


async def test_turn_without_encounter_and_foreign_character(client, test_session_factory):
    _, pc_id = await seed_session(test_session_factory)  # personaggio di un altro utente
    r = await client.post(f"/characters/{pc_id}/turn/use", json={"slot": "action"})
    assert r.status_code == 403
