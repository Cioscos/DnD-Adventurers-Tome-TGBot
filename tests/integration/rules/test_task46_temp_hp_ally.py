"""Task 46: PF temporanei dati a un altro PG della serata (estende R42): Incoraggiamento 2014 e 2024, Mantello di Ispirazione,
Forza Vivificante, Lampo di Interdizione Migliorato, Punizione Ispiratrice. Valore del server, riceventi della serata,
il maggiore vince, spesa unica, storico sul ricevente."""
from __future__ import annotations

import pytest

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard import _ability, _use
from tests.integration.rules.test_2014_bard_inspiration import _second_ally
from tests.integration.rules.test_2014_fighter_battle_master import _master
from tests.integration.rules.test_2014_paladin import _hurt  # noqa: F401  (parità di import con le altre prove del Paladino)
from tests.integration.rules.test_2014_bard_inspiration import _seat
from tests.integration.rules.test_2024_barbarian import _new_turn, _rage
from tests.integration.rules.test_2024_barbarian_paths import TREE
from tests.integration.rules.test_2024_bard import GLAMOUR, _bard24
from tests.integration.rules.test_2024_cleric_domains import _dom
from tests.integration.rules.test_2024_fighter_subclasses import _bm
from tests.integration.rules.test_2024_paladin_oaths import CD, FREE, _oath, _sword
from tests.integration.rules.test_2024_barbarian_paths import _barbarian
from tests.integration.rules.test_2014_paladin_combat import _damage, _deferred

RALLY14, RALLY24 = "fighter.maneuver_rally", "fighter.maneuver_rally"
MANTLE, LIFE, FLARE, SMITE = ("bard.mantle_of_inspiration", "barbarian.life_giving_force", "cleric.warding_flare",
                              "paladin.inspiring_smite")
BI, SD = "bard.bardic_inspiration", "fighter.superiority_dice"


@pytest.fixture(autouse=True)
def _dice_at_five(monkeypatch):
    monkeypatch.setattr("random.randint", lambda a, b: min(5, b))


# (id, costruttore -> cid, chiave, params, valore atteso con ogni dado a 5, riserva spesa o None se è lo stato/turno a limitare)
async def _rally14(client):
    return await _master(client, 7, "rally", charisma=14)


async def _rally24(client):
    return await _bm(client, 7, "rally", charisma=18)


async def _mantle(client):
    return await _bard24(client, 5, GLAMOUR, charisma=16)


async def _life(client):
    cid = await _barbarian(client, 3, TREE)
    assert (await _rage(client, cid)).status_code == 200
    await _new_turn(client, cid)
    return cid


async def _flare(client):
    return await _dom(client, 6, "light", wisdom=16)


async def _smite(client):
    cid = await _oath(client, 5, "glory", charisma=16)
    wid = await _sword(client, cid)
    assert (await _damage(client, cid, await _deferred(client, cid, wid), [FREE])).status_code == 200
    return cid


CASES = [
    pytest.param(_rally14, RALLY14, {}, 7, SD, id="rally-2014"),
    pytest.param(_rally24, RALLY24, {}, 8, SD, id="rally-2024"),
    pytest.param(_mantle, MANTLE, {}, 10, BI, id="mantle-of-inspiration"),
    pytest.param(_life, LIFE, {}, 10, None, id="life-giving-force"),
    pytest.param(_flare, FLARE, {}, 13, FLARE, id="improved-warding-flare"),
    pytest.param(_smite, SMITE, {"keep": "none"}, 15, CD, id="inspiring-smite"),
]


async def _table(client, test_session_factory, build):
    """Una serata con il personaggio del GM seduto e un eroe: `(sid, caster, hero)`."""
    sid, hero = await seed_session(test_session_factory)
    as_user(GM_ID)
    cid = await build(client)
    await _seat(test_session_factory, cid)
    return sid, cid, hero


async def _go(client, cid, key, params, target=None, **extra):
    as_user(GM_ID)
    body = {**params, **({"target_character_id": target} if target is not None else {}), **extra}
    return await client.post(f"/characters/{cid}/features/{key}/use", json={"params": body})


async def _temp(client, cid, user=PLAYER_ID) -> int:
    as_user(user)
    return (await client.get(f"/characters/{cid}")).json()["temp_hp"]


async def _left(client, cid, pool):
    as_user(GM_ID)
    return (await _ability(client, cid, pool))["uses"] if pool else None


async def _set_temp(client, cid, value):
    as_user(PLAYER_ID)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "set_temp", "value": value})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("build,key,params,value,pool", CASES)
async def test_the_value_is_delivered_to_the_seated_ally_and_logged_on_his_sheet(client, test_session_factory, build, key, params, value, pool):
    _sid, cid, hero = await _table(client, test_session_factory, build)
    before, mine = await _left(client, cid, pool), await _temp(client, cid, GM_ID)
    r = await _go(client, cid, key, params, hero)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["given"] is None  # consegnato: non resta un valore «da dare»
    assert body["temp_received"] == [{"name": "Eroe", "given": value, "temp_hp": value, "applied": True}]
    assert await _temp(client, hero) == value
    assert await _left(client, cid, pool) == (None if pool is None else before - 1)
    assert await _temp(client, cid, GM_ID) == mine  # nulla sulla scheda di chi lo usa (l'Ira dà i suoi, a prescindere)
    as_user(PLAYER_ID)
    history = (await client.get(f"/characters/{hero}/history")).json()
    assert any(e["event_type"] == "hp_change" and e["description"].startswith(f"PF temporanei: {value} (0") for e in history)


@pytest.mark.parametrize("build,key,params,value,pool", CASES)
async def test_an_ally_with_more_temporary_hp_keeps_them_and_the_use_is_spent(client, test_session_factory, build, key, params, value, pool):
    _sid, cid, hero = await _table(client, test_session_factory, build)
    await _set_temp(client, hero, value + 20)
    before = await _left(client, cid, pool)
    r = await _go(client, cid, key, params, hero)
    assert r.status_code == 200, r.text
    assert r.json()["temp_received"] == [{"name": "Eroe", "given": value, "temp_hp": value + 20, "applied": False}]
    assert await _temp(client, hero) == value + 20
    assert await _left(client, cid, pool) == (None if pool is None else before - 1)


async def test_temporary_hit_points_never_add_up_a_lower_value_is_replaced(client, test_session_factory):
    _sid, cid, hero = await _table(client, test_session_factory, _rally14)
    await _set_temp(client, hero, 3)
    r = await _go(client, cid, RALLY14, {}, hero)
    assert r.json()["temp_received"][0]["temp_hp"] == 7 and await _temp(client, hero) == 7  # 7, non 3 + 7


@pytest.mark.parametrize("build,key,params,value,pool", CASES)
async def test_without_a_target_the_outcome_stays_textual(client, test_session_factory, build, key, params, value, pool):
    _sid, cid, hero = await _table(client, test_session_factory, build)
    r = await _go(client, cid, key, params)
    assert r.status_code == 200, r.text
    assert r.json()["given"] == value and r.json()["temp_received"] == []
    assert await _temp(client, hero) == 0


@pytest.mark.parametrize("build,key,params,value,pool", CASES)
async def test_someone_not_at_the_table_is_refused_and_nothing_is_spent(client, test_session_factory, build, key, params, value, pool):
    _sid, cid, hero = await _table(client, test_session_factory, build)
    as_user(9999)
    outsider = (await client.post("/characters", json={"name": "Estraneo"})).json()["id"]
    before = await _left(client, cid, pool)
    for target in (outsider, cid, 987654):  # fuori serata, sé stessi, inesistente
        r = await _go(client, cid, key, params, target)
        assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_target", r.text
    assert await _left(client, cid, pool) == before and await _temp(client, outsider, 9999) == 0
    r = await _go(client, cid, key, params, str(hero))  # un testo non è un id
    assert r.status_code == 422


@pytest.mark.parametrize("build,key,params,value,pool", CASES)
async def test_a_second_use_cannot_spend_again_nor_deliver_twice(client, test_session_factory, build, key, params, value, pool):
    _sid, cid, hero = await _table(client, test_session_factory, build)
    assert (await _go(client, cid, key, params, hero)).status_code == 200
    await _set_temp(client, hero, 0)
    again = await _go(client, cid, key, params, hero)
    assert again.status_code == 409, again.text  # usi finiti, azione di turno o una volta per turno
    assert await _temp(client, hero) == 0


async def test_the_delivery_is_definitive_hp_undo_no_longer_applies(client, test_session_factory):
    _sid, cid, hero = await _table(client, test_session_factory, _rally14)
    op = (await _set_temp(client, hero, 2))["hp_undo_id"]
    assert (await _go(client, cid, RALLY14, {}, hero)).status_code == 200
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{hero}/hp/undo", json={"op_id": op})
    assert r.status_code == 409 and await _temp(client, hero) == 7


async def test_mantle_of_inspiration_reaches_up_to_charisma_modifier_creatures(client, test_session_factory):
    sid, cid, hero = await _table(client, test_session_factory, _mantle)
    second = await _second_ally(test_session_factory, sid)
    await _set_temp(client, hero, 30)
    r = await _go(client, cid, MANTLE, {}, None, target_character_ids=[hero, second])
    assert r.status_code == 200, r.text
    got = {e["name"]: e for e in r.json()["temp_received"]}
    assert got["Eroe"]["applied"] is False and got["Compagno"]["applied"] is True and got["Compagno"]["temp_hp"] == 10
    assert await _temp(client, second, 9001) == 10 and await _temp(client, hero) == 30
    as_user(GM_ID)
    assert (await _ability(client, cid, BI))["uses"] == (await _ability(client, cid, BI))["max_uses"] - 1  # una sola spesa


async def test_mantle_refuses_more_creatures_than_the_modifier_and_duplicates(client, test_session_factory):
    sid, cid, hero = await _table(client, test_session_factory, _mantle)
    second = await _second_ally(test_session_factory, sid)
    third = await _second_ally(test_session_factory, sid, user=9002)
    fourth = await _second_ally(test_session_factory, sid, user=9003)
    for ids in ([hero, second, third, fourth], [hero, hero]):  # Carisma 16: al massimo 3
        r = await _go(client, cid, MANTLE, {}, None, target_character_ids=ids)
        assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_target"
    assert (await _ability(client, cid, BI))["uses"] == (await _ability(client, cid, BI))["max_uses"]


async def test_only_one_target_is_allowed_where_the_privilege_names_one(client, test_session_factory):
    sid, cid, hero = await _table(client, test_session_factory, _rally14)
    second = await _second_ally(test_session_factory, sid)
    r = await _go(client, cid, RALLY14, {}, None, target_character_ids=[hero, second])
    assert r.status_code == 422


async def test_a_light_cleric_below_level_6_has_nothing_to_give_and_the_sheet_does_not_ask(client, test_session_factory):
    _sid, cid, hero = await _table(client, test_session_factory, lambda c: _dom(c, 5, "light", wisdom=16))
    as_user(GM_ID)
    row = next(a for a in (await client.get(f"/characters/{cid}")).json()["abilities"] if a["feature_key"] == FLARE)
    assert row["gives_to_ally"] is False
    r = await _go(client, cid, FLARE, {}, hero)
    assert r.status_code == 200 and r.json()["temp_received"] == [] and await _temp(client, hero) == 0  # valore 0: niente da consegnare


@pytest.mark.parametrize("build,key,params,value,pool", CASES)
async def test_the_sheet_tells_the_client_to_ask_for_the_ally(client, test_session_factory, build, key, params, value, pool):
    _sid, cid, _hero = await _table(client, test_session_factory, build)
    as_user(GM_ID)
    row = next(a for a in (await client.get(f"/characters/{cid}")).json()["abilities"] if a["feature_key"] == key)
    assert row["gives_to_ally"] is True and row["ally_max"] >= 1
