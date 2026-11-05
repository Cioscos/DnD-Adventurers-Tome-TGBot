"""Difetti comuni chiusi prima dei cataloghi di classe (Task 18b)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from core.db.models import Character
from core.rules.types import Cost, OnUse, RollOptionSpec, StateSpec, Uses
from tests.integration.test_rules_states import _char, _fighter, _spec, _use, _uses_of

_LABEL = {"it": "x", "en": "x"}


# --- OnUse: rolls validati, pool, dadi in cronologia ------------------------------------------------------------------

@pytest.mark.parametrize("rolls", ["d10", "abc", "1d", "0d6", "2d1", "1d6+2", " 1d6"])
def test_onuse_rejects_an_invalid_dice_expression(rolls):
    with pytest.raises(ValueError):
        OnUse(rolls=rolls)


def test_onuse_accepts_a_dice_expression():
    assert OnUse(rolls="2d6").rolls == "2d6"


async def test_amount_multiplies_the_unit_effect_for_a_pool(client, test_session_factory, rules_catalog):
    # Imposizione delle Mani: ogni punto speso cura 1 PF
    rules_catalog(_spec(OnUse(heal=lambda _ctx, _rolled: 1), uses=Uses(table={1: 10})))
    cid = await _fighter(client, test_session_factory, hp=(30, 10))
    r = await _use(client, cid, amount=4)
    assert r.status_code == 200, r.text
    assert r.json()["healed"] == 4
    char = await _char(client, cid)
    assert _uses_of(char) == 6 and char["current_hit_points"] == 14


async def test_amount_rolls_the_dice_once_per_unit(client, test_session_factory, rules_catalog, monkeypatch):
    rules_catalog(_spec(OnUse(rolls="1d6", heal=lambda _ctx, rolled: rolled), uses=Uses(table={1: 10})))
    cid = await _fighter(client, test_session_factory, hp=(30, 10))
    monkeypatch.setattr("api.services.rules_states.random.randint", lambda _a, _b: 3)
    body = (await _use(client, cid, amount=3)).json()
    assert body["rolls"] == [3, 3, 3] and body["healed"] == 9


async def test_amount_keeps_a_single_state(client, test_session_factory, rules_catalog):
    rules_catalog(_spec(OnUse(state=StateSpec("rage")), uses=Uses(table={1: 10})))
    cid = await _fighter(client, test_session_factory)
    await _use(client, cid, amount=2)
    assert len((await _char(client, cid))["active_states"]) == 1


async def test_use_rolls_go_to_the_dice_history(client, test_session_factory, rules_catalog, monkeypatch):
    rules_catalog(_spec(OnUse(rolls="2d8")))
    cid = await _fighter(client, test_session_factory)
    monkeypatch.setattr("api.services.rules_states.random.randint", lambda _a, _b: 5)
    assert (await _use(client, cid)).status_code == 200
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == cid))).scalar_one()
        assert char.dice_stats["d8"] == {"5": 2}


# --- Nome dello stato: mai la chiave grezza --------------------------------------------------------------------------

async def test_expired_state_is_reported_by_its_name_not_its_key(client, test_session_factory, rules_catalog):
    rules_catalog(_spec(OnUse(state=StateSpec("rage", rounds=1))))
    cid = await _fighter(client, test_session_factory)
    await _use(client, cid)
    r = await client.post(f"/characters/{cid}/rounds/tick")
    assert r.status_code == 200, r.text
    assert r.json()["expired_effects"] == ["Prova"]


async def test_started_state_carries_the_name(client, test_session_factory, rules_catalog):
    rules_catalog(_spec(OnUse(state=StateSpec("rage"))))
    cid = await _fighter(client, test_session_factory)
    state = (await _use(client, cid)).json()["state"]
    assert state["key"] == "rage" and state["name"] == "Prova"
    assert (await _char(client, cid))["active_states"][0]["name"] == "Prova"


async def test_legacy_state_without_a_name_falls_back_to_the_ability(client, test_session_factory, rules_catalog):
    rules_catalog(_spec(OnUse(state=StateSpec("rage", rounds=1))))
    cid = await _fighter(client, test_session_factory)
    await _use(client, cid)
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == cid))).scalar_one()
        char.active_states = [{k: v for k, v in st.items() if k != "name"} for st in char.active_states]
        await s.commit()
    assert (await client.post(f"/characters/{cid}/rounds/tick")).json()["expired_effects"] == ["Prova"]


# --- Opzioni dopo il danno ----------------------------------------------------------------------------------------------

def test_after_damage_option_cannot_ask_for_input():
    with pytest.raises(ValueError):
        RollOptionSpec(key="r", phase="after_damage", rolls=("attack",), label=_LABEL, requires_input="slot",
                       cost=Cost(spell_slot_min=1), reroll_dice=lambda _c, i: i["slot_level"])


# --- Rilancio del danno con base fissa ----------------------------------------------------------------------------------

async def test_flat_damage_reroll_keeps_the_fixed_part_in_the_list(client, rules_catalog, monkeypatch):
    from dataclasses import replace

    from tests.integration.test_rules_general import _char as general_char
    from tests.integration.test_rules_roll_options_api import SNEAK, _deferred, _feature
    rules_catalog(replace(_feature(SNEAK), edition="2024"))
    cid = await general_char(client, edition="2024")
    await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Stocco", "item_type": "weapon",
        "item_metadata": {"damage_dice": "1", "weapon_type": "melee", "properties": ["finesse"]}})
    item = next(i["id"] for i in r.json()["items"] if i["name"] == "Stocco")
    hit = await _deferred(client, cid, item, die=10)
    resp = await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": ["sneak"]})
    body = resp.json()
    assert body["damage_rolls"] == [1] and body["reroll_dice"]
    monkeypatch.setattr("api.routers.spells.random.randint", lambda _a, _b: 6)
    r = await client.post(f"/characters/{cid}/last-damage/options",
                          json={"options": ["inspiration:reroll_damage"], "reroll": [0]})
    assert r.status_code == 200, r.text
    again = r.json()
    assert again["damage_rolls"] == [1]  # il fisso resta nell'elenco mostrato
    assert again["damage_total"] == body["damage_total"] - body["reroll_dice"][0][1] + 6
