"""Stati attivi e uso reale dei privilegi (Task 10)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from api.services import rules_states
from api.services.class_features import sync_class_feature_abilities
from api.services.durations import end_concentration
from core.db.models import Character, CharacterClass
from core.rules.types import FeatureSpec, OnUse, StateSpec, Uses
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, setup_full_encounter
from tests.integration._telegram_stub import install_fake_telegram


def _spec(on_use: OnUse, key="fighter.prova", uses=Uses(table={1: 2}), restoration="long_rest") -> FeatureSpec:
    return FeatureSpec(
        key=key, class_key="fighter", edition="2014", level=1, source_title="Prova",
        name={"it": "Prova", "en": "Test"}, summary={"it": "x", "en": "x"}, action_type="bonus_action",
        uses=uses, restoration=restoration, on_use=on_use,
    )


async def _add_fighter(factory, cid, level=5, hp=None) -> None:
    """Aggiunge la classe e fa girare il sync (crea le righe Ability dal catalogo di prova)."""
    async with factory() as s:
        char = (await s.execute(select(Character).where(Character.id == cid).options(
            selectinload(Character.classes), selectinload(Character.abilities),
            selectinload(Character.ability_scores), selectinload(Character.items),
        ))).scalar_one()
        if hp:
            char.hit_points, char.current_hit_points = hp
        cls = CharacterClass(character_id=cid, class_name="fighter", level=level)
        char.classes.append(cls)
        await s.flush()
        await sync_class_feature_abilities(s, char, cls)
        await s.commit()


async def _fighter(client, factory, level=5, hp=(30, 10)) -> int:
    cid = (await client.post("/characters", json={"name": "Stati"})).json()["id"]
    await _add_fighter(factory, cid, level, hp)
    return cid


async def _use(client, cid, key="fighter.prova", **body):
    return await client.post(f"/characters/{cid}/features/{key}/use", json=body)


async def _char(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def _turn(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]


def _uses_of(char: dict, key="fighter.prova") -> int:
    return next(a["uses"] for a in char["abilities"] if a["feature_key"] == key)


async def test_use_spends_uses_and_turn_slot(client, test_session_factory, rules_catalog):
    rules_catalog(_spec(OnUse(slot="bonus")))
    cid = await _fighter(client, test_session_factory)
    assert _uses_of(await _char(client, cid)) == 2
    r = await _use(client, cid)
    assert r.status_code == 200, r.text
    assert _uses_of(await _char(client, cid)) == 1
    assert (await _turn(client, cid))["bonus_used"] is True
    # lo slot è già speso: 409 e gli usi non scendono
    r = await _use(client, cid)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "turn_slot_used"
    assert _uses_of(await _char(client, cid)) == 1


async def test_state_ticks_and_expires_in_rounds(client, test_session_factory, rules_catalog):
    rules_catalog(_spec(OnUse(state=StateSpec("rage", rounds=2, data={"bonus": 2}))))
    cid = await _fighter(client, test_session_factory)
    body = (await _use(client, cid)).json()
    assert body["state"]["key"] == "rage" and body["state"]["rounds_left"] == 2
    assert body["state"]["feature_key"] == "fighter.prova" and body["state"]["data"] == {"bonus": 2}
    await client.post(f"/characters/{cid}/rounds/tick")
    assert [s["rounds_left"] for s in (await _char(client, cid))["active_states"]] == [1]
    await client.post(f"/characters/{cid}/rounds/tick")
    assert (await _char(client, cid))["active_states"] == []


@pytest.mark.parametrize("ends_on, rest, damage, ended", [
    (("rest_short",), "short", None, True),
    (("rest_short",), "long", None, True),
    (("rest_long",), "short", None, False),
    (("rest_long",), "long", None, True),
    (("unconscious",), None, 40, True),
    (("unconscious",), None, 5, False),
    (("manual",), "long", None, False),
])
async def test_state_ends_on_rest_and_unconscious(client, test_session_factory, rules_catalog, ends_on, rest, damage, ended):
    rules_catalog(_spec(OnUse(state=StateSpec("rage", ends_on=ends_on))))
    cid = await _fighter(client, test_session_factory, hp=(30, 30))
    await _use(client, cid)
    if damage:
        await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": damage})
    if rest:
        r = await client.post(f"/characters/{cid}/rest", json={"rest_type": rest, "confirm_early": True})
        assert r.status_code == 200, r.text
    assert ((await _char(client, cid))["active_states"] == []) is ended


@pytest.mark.parametrize("attacks, ended", [(0, True), (1, False)])
async def test_state_ends_when_turn_ends_without_attacking(client, test_session_factory, rules_catalog, monkeypatch, attacks, ended):
    install_fake_telegram(monkeypatch)
    rules_catalog(_spec(OnUse(state=StateSpec("rage", ends_on=("turn_end_no_attack",)))))
    sid, _ = await setup_full_encounter(client, test_session_factory)
    async with test_session_factory() as s:
        pc_id = (await s.execute(select(Character.id))).scalar_one()
    await _add_fighter(test_session_factory, pc_id)
    as_user(GM_ID)
    await client.post(f"/sessions/{sid}/encounter/start", json={})
    as_user(PLAYER_ID)
    assert (await _use(client, pc_id)).status_code == 200
    for _ in range(attacks):
        await client.post(f"/characters/{pc_id}/turn/use", json={"slot": "attack"})
    as_user(GM_ID)
    await client.post(f"/sessions/{sid}/encounter/next-turn")  # fine del turno del PG
    as_user(PLAYER_ID)
    assert ((await _char(client, pc_id))["active_states"] == []) is ended


def test_state_ends_on_concentration_end():
    char = SimpleNamespace(concentrating_spell_id=3, settings={}, active_states=[
        {"key": "a", "feature_key": "x", "rounds_left": None, "ends_on": ["concentration_end"], "data": {}},
        {"key": "b", "feature_key": "x", "rounds_left": None, "ends_on": ["manual"], "data": {}},
    ])
    end_concentration(char)
    assert [s["key"] for s in char.active_states] == ["b"]


async def test_heal_on_use_rolls_and_caps(client, test_session_factory, rules_catalog, monkeypatch):
    monkeypatch.setattr(rules_states.random, "randint", lambda a, b: b)
    rules_catalog(_spec(OnUse(rolls="1d10", heal=lambda ctx, rolled: rolled + ctx.class_level)))
    cid = await _fighter(client, test_session_factory, level=5, hp=(30, 10))
    body = (await _use(client, cid)).json()
    assert body["rolls"] == [10] and body["healed"] == 15  # 10 + livello 5
    assert (await _char(client, cid))["current_hit_points"] == 25
    body = (await _use(client, cid)).json()  # mancano solo 5 PF
    assert body["healed"] == 5 and (await _char(client, cid))["current_hit_points"] == 30


async def test_grants_action_increments_extra_actions(client, test_session_factory, rules_catalog):
    rules_catalog(_spec(OnUse(grants_action=True)))
    cid = await _fighter(client, test_session_factory)
    await _use(client, cid)
    assert (await _turn(client, cid))["extra_actions"] == 1


async def test_use_with_no_uses_returns_409(client, test_session_factory, rules_catalog):
    rules_catalog(_spec(OnUse(), uses=Uses(table={1: 1})),
                  _spec(OnUse(), key="fighter.futuro", uses=Uses(table={9: 1})))
    cid = await _fighter(client, test_session_factory)
    assert (await _use(client, cid)).status_code == 200
    r = await _use(client, cid)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    assert _uses_of(await _char(client, cid)) == 0
    # usi massimi 0: la riga non esiste ancora, ma è 409 esplicito, mai 500
    r = await _use(client, cid, key="fighter.futuro")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"


async def test_unknown_feature_and_manual_removal(client, test_session_factory, rules_catalog):
    rules_catalog(_spec(OnUse(state=StateSpec("rage"))))
    cid = await _fighter(client, test_session_factory)
    r = await _use(client, cid, key="fighter.nope")
    assert r.status_code == 404 and r.json()["detail"]["code"] == "feature_not_usable"
    await _use(client, cid)
    assert (await client.delete(f"/characters/{cid}/active-states/rage")).status_code == 200
    assert (await _char(client, cid))["active_states"] == []
    assert (await client.delete(f"/characters/{cid}/active-states/rage")).status_code == 404
