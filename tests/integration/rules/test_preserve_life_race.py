"""Preservare Vita (C1 e I1 del Task 21): riserva spesa una volta sola con richieste concorrenti, tetto residuo senza PF."""
from __future__ import annotations

import asyncio

from fastapi import Request

from api.auth import get_current_user
from api.main import app
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
from tests.integration.rules.test_2014_bard import _ability, _full
from tests.integration.rules.test_2014_cleric import POOL, _cleric
from tests.integration.rules.test_preserve_life import _go, _hp, _scene

OTHER_ID = 4321


def _user_from_header() -> None:
    """Ogni richiesta porta il proprio utente: serve a lanciarne più insieme da giocatori diversi."""
    def user(request: Request) -> int:
        return int(request.headers["x-test-user"])

    app.dependency_overrides[get_current_user] = user


def _post(client, cleric, user, allocations):
    return client.post(f"/characters/{cleric}/preserve-life", headers={"x-test-user": str(user)}, json={
        "allocations": [{"character_id": c, "amount": a} for c, a in allocations], "confirm_living": True})


async def test_parallel_requests_spend_the_single_use_once(client, test_session_factory):
    sid, cleric, hero = await _scene(client, test_session_factory, hero_hp=1)  # il chierico 10/40: tetto 10; l'eroe 1/40: 19
    _user_from_header()
    rs = await asyncio.gather(*(_post(client, cleric, GM_ID, [(t, 10)]) for t in (hero, cleric, hero, hero)))
    assert sorted(r.status_code for r in rs) == [200, 409, 409, 409], [r.text for r in rs]
    as_user(GM_ID)
    assert (await _ability(client, cleric, POOL))["uses"] == 0
    total = 0
    for cid, user in ((cleric, GM_ID), (hero, PLAYER_ID)):
        as_user(user)
        total += (await _full(client, cid))["current_hit_points"]
    assert total == 10 + 1 + 10  # una sola cura da 10


async def test_two_clerics_on_the_same_receiver_never_pass_half(client, test_session_factory):
    sid, first, hero = await _scene(client, test_session_factory, hero_hp=5)  # l'eroe 5/40: restano 15
    as_user(OTHER_ID)
    second = await _cleric(client, 5, "life", wisdom=16)
    from core.db.models import SessionParticipant, SessionRole
    from tests.integration._encounter_helpers import NOW
    async with test_session_factory() as s:
        s.add(SessionParticipant(session_id=sid, user_id=OTHER_ID, character_id=second, role=SessionRole.PLAYER,
                                 display_name="Secondo", joined_at=NOW))
        await s.commit()
    _user_from_header()
    rs = await asyncio.gather(_post(client, first, GM_ID, [(hero, 15)]), _post(client, second, OTHER_ID, [(hero, 15)]))
    assert sorted(r.status_code for r in rs) == [200, 422], [r.text for r in rs]
    loser = first if rs[0].status_code == 422 else second
    as_user(PLAYER_ID)
    assert (await _full(client, hero))["current_hit_points"] == 20  # mai oltre la metà
    as_user(GM_ID if loser == first else OTHER_ID)
    assert (await _ability(client, loser, POOL))["uses"] == 1  # chi è stato rifiutato non perde l'uso


async def test_session_allies_do_not_reveal_the_hit_points(client, test_session_factory):
    sid, cleric, hero = await _scene(client, test_session_factory, hero_hp=7)
    as_user(PLAYER_ID)
    r = await client.get(f"/characters/{hero}/session-allies")
    assert r.status_code == 200
    for ally in r.json():
        assert "hp" not in ally and "hp_max" not in ally and "heal_cap" not in ally


async def test_the_targets_endpoint_gives_only_the_residual_cap_to_who_can_use_it(client, test_session_factory):
    sid, cleric, hero = await _scene(client, test_session_factory, hero_hp=7)
    as_user(GM_ID)
    r = await client.get(f"/characters/{cleric}/preserve-life")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pool"] == 25 and body["uses_left"] == 1
    assert {t["id"]: t["cap"] for t in body["targets"]} == {cleric: 10, hero: 13}  # 20 - 10; 20 - 7
    assert all(set(t) == {"id", "name", "cap", "self"} for t in body["targets"])
    # il tetto non va oltre la riserva: chi è molto ferito non lascia leggere quanto
    as_user(PLAYER_ID)
    await _hp(client, hero, 1, 40)
    as_user(GM_ID)
    assert {t["id"]: t["cap"] for t in (await client.get(f"/characters/{cleric}/preserve-life")).json()["targets"]}[hero] == 19
    # senza usi o senza il privilegio: nessun elenco
    as_user(GM_ID)
    assert (await _go(client, cleric, [(cleric, 1)])).status_code == 200
    r = await client.get(f"/characters/{cleric}/preserve-life")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    war = await _cleric(client, 5, "war")
    assert (await client.get(f"/characters/{war}/preserve-life")).status_code == 404
    as_user(9999)
    assert (await client.get(f"/characters/{cleric}/preserve-life")).status_code == 403


async def test_the_feature_row_tells_how_many_uses_the_pool_has_left(client, test_session_factory):
    sid, cleric, hero = await _scene(client, test_session_factory)
    as_user(GM_ID)
    assert (await _ability(client, cleric, "cleric.preserve_life"))["spends_left"] == 1
    assert (await _go(client, cleric, [(cleric, 1)])).status_code == 200
    assert (await _ability(client, cleric, "cleric.preserve_life"))["spends_left"] == 0
