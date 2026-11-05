"""Difetti comuni chiusi prima dei cataloghi di classe (Task 18b)."""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.db.models import Character
from api.services.rules_states import start_state, state_name
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


# --- Giro 1: stato senza riga né nome, spesa di N usi -----------------------------------------------------------------

def test_start_state_without_a_name_stores_none_never_the_key():
    from types import SimpleNamespace
    char = SimpleNamespace(active_states=[], abilities=[])
    state = start_state(char, StateSpec("wild_shape"), "druid.wild_shape")
    assert state["name"] is None
    assert state_name(char, state) == "Effetto attivo"


async def test_state_without_row_or_name_is_never_named_by_its_key(client, test_session_factory):
    cid = await _fighter(client, test_session_factory)
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == cid))).scalar_one()
        char.active_states = [{"key": "wild_shape", "feature_key": "druid.wild_shape", "name": None,
                               "rounds_left": 1, "ends_on": ["manual"], "data": {}}]
        await s.commit()
    r = await client.post(f"/characters/{cid}/rounds/tick")
    assert r.json()["expired_effects"] == ["Effetto attivo"]


async def test_wild_shape_state_has_no_raw_key_name(client, test_session_factory):
    from api.services.wild_shape import start_form
    from core.db.models import Companion
    cid = await _fighter(client, test_session_factory)
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == cid).options(
            selectinload(Character.classes), selectinload(Character.abilities),
            selectinload(Character.ability_scores), selectinload(Character.items),
        ))).scalar_one()
        form = Companion(character_id=cid, name="Lupo", kind="wild_shape", max_hp=10, current_hp=10,
                        created_at="2026-01-01T00:00:00")
        s.add(form)
        await s.flush()
        start_form(char, form)
        assert char.active_states[0]["name"] is None
        await s.commit()


async def test_amount_over_the_remaining_uses_is_refused_and_spends_nothing(client, test_session_factory, rules_catalog):
    rules_catalog(_spec(OnUse(heal=lambda _c, _r: 1, state=StateSpec("aura"), grants_action=True, slot="bonus"),
                        uses=Uses(table={1: 2})))
    cid = await _fighter(client, test_session_factory, hp=(30, 10))
    r = await _use(client, cid, amount=3)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    char = await _char(client, cid)
    assert _uses_of(char) == 2 and char["current_hit_points"] == 10 and not char["active_states"]
    turn = (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]
    assert turn["bonus_used"] is False and turn["extra_actions"] == 0


async def test_grants_action_repeats_for_each_unit(client, test_session_factory, rules_catalog):
    rules_catalog(_spec(OnUse(grants_action=True), uses=Uses(table={1: 5})))
    cid = await _fighter(client, test_session_factory)
    assert (await _use(client, cid, amount=3)).status_code == 200
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]["extra_actions"] == 3


async def test_hp_undo_after_a_pool_heal_is_refused_and_never_restores_stale_hp(client, test_session_factory, rules_catalog):
    # La cura di un privilegio non scrive uno snapshot di annullamento PF: `/hp/undo` di un'operazione precedente
    # trova i PF cambiati e rifiuta (409), senza riportare i PF a prima della cura. Gli usi restano spesi.
    rules_catalog(_spec(OnUse(heal=lambda _c, _r: 1), uses=Uses(table={1: 10})))
    cid = await _fighter(client, test_session_factory, hp=(30, 10))
    dmg = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 2})).json()
    assert (await _use(client, cid, amount=4)).status_code == 200
    r = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": dmg["hp_undo_id"]})
    assert r.status_code == 409 and r.json()["detail"] == "hp_undo_not_applicable"
    char = await _char(client, cid)
    assert char["current_hit_points"] == 12 and _uses_of(char) == 6


async def test_pool_feature_declares_that_the_player_chooses_the_amount(client, test_session_factory, rules_catalog):
    rules_catalog(_spec(OnUse(heal=lambda _c, _r: 1, choose_amount=True, max_amount=5), uses=Uses(table={1: 10})))
    cid = await _fighter(client, test_session_factory, hp=(30, 10))
    ab = next(a for a in (await _char(client, cid))["abilities"] if a["feature_key"] == "fighter.prova")
    assert ab["has_on_use"] is True and ab["choose_amount"] is True and ab["max_amount"] == 5
    r = await _use(client, cid, amount=6)  # oltre il tetto del privilegio: rifiutato, nulla speso
    assert r.status_code == 409 and r.json()["detail"]["code"] == "amount_too_high"
    assert _uses_of(await _char(client, cid)) == 10
    assert (await _use(client, cid, amount=5)).json()["healed"] == 5


async def test_plain_feature_does_not_ask_for_an_amount(client, test_session_factory, rules_catalog):
    rules_catalog(_spec(OnUse(slot="bonus")))
    cid = await _fighter(client, test_session_factory)
    ab = next(a for a in (await _char(client, cid))["abilities"] if a["feature_key"] == "fighter.prova")
    assert ab["choose_amount"] is False and ab["max_amount"] is None


def test_max_amount_needs_choose_amount():
    with pytest.raises(ValueError):
        OnUse(max_amount=5)
    with pytest.raises(ValueError):
        OnUse(choose_amount=True, max_amount=0)
