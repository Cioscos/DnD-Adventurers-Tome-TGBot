"""Privilegi usati dopo aver visto il d20: il server legge il tiro dal proprio stato, non dal client."""
from __future__ import annotations

import pytest
from dataclasses import replace

from sqlalchemy import select

from api.services.condition_effects import SaveSpec, upsert_effect
from core.db.models import Character, CharacterHistory, Combatant, Encounter, PendingSave
from core.rules.roll_options import refund_spent
from core.rules.types import Cost, RollOptionSpec, Uses
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.test_rules_roll_options_api import _LABEL, _char, _code, _deferred, _feature, _uses, _weapon

ROLLS = ("attack", "skill", "save", "initiative", "death_save")
ADD = RollOptionSpec(key="add", phase="after_roll", after="add", rolls=ROLLS, label=_LABEL, bonus=lambda _c, _i: 3)
ADD_DICE = RollOptionSpec(key="add_dice", phase="after_roll", after="add", rolls=ROLLS, label=_LABEL,
                          extra_dice=lambda _c, _i: "1d10")
REROLL = RollOptionSpec(key="again", phase="after_roll", after="reroll", rolls=ROLLS, label=_LABEL)
FANATIC = RollOptionSpec(key="fanatic", phase="after_roll", after="reroll", rolls=ROLLS, label=_LABEL,
                         bonus=lambda _c, _i: 4, mode="advantage")
LUCK = RollOptionSpec(key="luck", phase="after_roll", after="succeed", rolls=ROLLS, label=_LABEL)
PAID = RollOptionSpec(key="paid", phase="after_roll", after="add", rolls=ROLLS, label=_LABEL, bonus=lambda _c, _i: 5,
                      cost=Cost(feature_key="fighter.prova"), pay_if_success=True)
ONCE = RollOptionSpec(key="once", phase="after_roll", after="add", rolls=ROLLS, label=_LABEL, bonus=lambda _c, _i: 1,
                      once_per_turn=True, pay_if_success=True)
PORTENT = RollOptionSpec(key="portent", phase="before", rolls=ROLLS, label=_LABEL, replace_die=True,
                         once_per_turn=True)
HIT_ONLY = RollOptionSpec(key="hit_only", phase="after_hit", rolls=("attack",), label=_LABEL,
                          extra_dice=lambda _c, _i: "1d6")
_USES = Uses(table={1: 2})


async def _encounter(client, test_session_factory):
    """Un PG del giocatore in un incontro: (id personaggio, id sessione, id combattente)."""
    sid, cid = await seed_session(test_session_factory)
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    assert r.status_code == 201, r.text
    comb = next(c for c in r.json()["combatants"] if c["kind"] == "pc")["id"]
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})
    assert r.status_code == 201, r.text
    return cid, sid, comb


async def _skill(client, cid, die=5, **extra) -> dict:
    r = await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": die, **extra})
    assert r.status_code == 200, r.text
    return r.json()


async def _after(client, cid, *keys, **extra):
    return await client.post(f"/characters/{cid}/last-roll/options", json={"options": list(keys), **extra})


async def _failed_save(s, cid, dc=15):
    ch = await s.get(Character, cid)
    ch.conditions = {"poisoned": True}
    eff = await upsert_effect(s, ("character", cid), "poisoned", save=SaveSpec("constitution", dc, "end"))
    ps = PendingSave(effect_id=eff.id, character_id=cid, ability="constitution", dc=dc, status="pending",
                     created_at="2026-11-04T10:00:00")
    s.add(ps)
    await s.commit()
    return ps.id


async def _pending_save(client, test_session_factory, cid, die=2, dc=15) -> int:
    async with test_session_factory() as s:
        psid = await _failed_save(s, cid, dc)
    r = await client.post(f"/characters/{cid}/pending-saves/{psid}/roll", json={"die": die})
    assert r.status_code == 200 and r.json()["passed"] is False, r.text
    return psid


async def test_add_keeps_die_and_changes_total(client, rules_catalog):
    rules_catalog(_feature(ADD, ADD_DICE))
    cid = await _char(client)
    first = await _skill(client, cid)
    r = await _after(client, cid, "add")
    assert r.status_code == 200, r.text
    added = r.json()
    assert added["die"] == 5 and added["bonus"] == first["bonus"] + 3 and added["total"] == first["total"] + 3
    assert added["notes"] == ["feature:fighter.prova"]

    r = await _after(client, cid, "add_dice")
    dice = r.json()
    assert dice["die"] == 5 and len(dice["option_result"]["extra_rolls"]) == 1
    assert dice["total"] == added["total"] + dice["option_result"]["extra_total"]


async def test_reroll_uses_new_die_mandatorily(client, rules_catalog):
    rules_catalog(_feature(REROLL))
    cid = await _char(client)
    first = await _skill(client, cid, die=15)
    r = await _after(client, cid, "again", dice=[3])
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 3 and r.json()["total"] == first["total"] - 12  # peggiore, ma obbligatorio
    history = (await client.get(f"/characters/{cid}/history")).json()
    assert any("Dopo il tiro (again)" in h["description"] for h in history)


async def test_reroll_applies_bonus_and_mode(client, rules_catalog):
    rules_catalog(_feature(FANATIC))
    cid = await _char(client)
    first = await _skill(client, cid, die=5)
    r = await _after(client, cid, "fanatic", dice=[7, 16], mode="advantage")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["die"] == 16 and body["dice"] == [7, 16] and body["mode"] == "advantage"
    assert body["bonus"] == first["bonus"] + 4 and body["total"] == 16 + first["bonus"] + 4


async def test_reroll_on_attack_keeps_damage_until_crit_changes(client, rules_catalog):
    rules_catalog(_feature(REROLL, replace(REROLL, key="again2"), replace(REROLL, key="again3")))
    cid = await _char(client)
    item = await _weapon(client, cid)
    hit = await _deferred(client, cid, item, die=10)
    same = (await _after(client, cid, "again", dice=[12])).json()["attack"]
    assert same["to_hit_die"] == 12 and same["damage_total"] == hit["damage_total"]
    crit = (await _after(client, cid, "again2", dice=[20])).json()["attack"]
    assert crit["is_critical"] is True and len(crit["damage_rolls"]) == 2  # 1d8 raddoppiato
    fumble = (await _after(client, cid, "again3", dice=[1])).json()["attack"]
    assert fumble["is_fumble"] is True and fumble["damage_total"] == 0
    r = await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={})
    assert r.status_code == 409 and _code(r) == "attack_missed"


async def test_succeed_turns_skill_to_20_and_attack_to_hit_not_crit(client, rules_catalog):
    rules_catalog(_feature(LUCK))
    cid = await _char(client)
    first = await _skill(client, cid, die=4)
    body = (await _after(client, cid, "luck")).json()
    assert body["die"] == 20 and body["total"] == first["total"] + 16 and body["is_critical"] is False  # una prova di abilità non ha critico

    item = await _weapon(client, cid)
    hit = await _deferred(client, cid, item, die=4)
    attack = (await _after(client, cid, "luck")).json()["attack"]
    assert attack["forced_hit"] is True and attack["is_critical"] is False and attack["to_hit_die"] == 4
    assert attack["damage_total"] == hit["damage_total"]
    done = await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={})
    assert done.status_code == 200 and done.json()["forced_hit"] is True


async def test_succeed_after_natural_one_rolls_the_damage(client, rules_catalog):
    rules_catalog(_feature(LUCK))
    cid = await _char(client)
    item = await _weapon(client, cid)
    fumble = await _deferred(client, cid, item, die=1)
    assert fumble["is_fumble"] is True and fumble["damage_total"] == 0 and fumble["attack_id"]
    attack = (await _after(client, cid, "luck")).json()["attack"]
    assert attack["is_fumble"] is False and attack["forced_hit"] is True and attack["damage_rolls"] != [0]
    done = await client.post(f"/characters/{cid}/attack/{fumble['attack_id']}/damage", json={})
    assert done.status_code == 200 and done.json()["damage_total"] == attack["damage_total"]


async def test_spell_attack_row(client, rules_catalog):
    rules_catalog(_feature(ADD))
    cid = await _char(client)
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Dardo", "level": 0, "attack_save": "ATK"})
    assert r.status_code == 201, r.text
    spell = next(s["id"] for s in r.json()["spells"]) if "spells" in r.json() else r.json()["id"]
    r = await client.post(f"/characters/{cid}/spells/{spell}/attack", json={"die": 6})
    assert r.status_code == 200, r.text
    first = r.json()
    r = await _after(client, cid, "add")
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 6 and r.json()["total"] == first["to_hit_total"] + 3 and "attack" not in r.json()


async def test_pending_save_recomputes_outcome_and_frees(client, rules_catalog, test_session_factory):
    rules_catalog(_feature(LUCK))
    cid = await _char(client)
    psid = await _pending_save(client, test_session_factory, cid)
    r = await _after(client, cid, "luck")
    assert r.status_code == 200, r.text
    assert r.json()["passed"] is True and r.json()["condition_removed"] is True
    async with test_session_factory() as s:
        assert not (await s.get(Character, cid)).conditions.get("poisoned")
        assert (await s.execute(select(PendingSave).where(PendingSave.id == psid))).scalar_one_or_none() is None
    r = await _after(client, cid, "luck")
    assert r.status_code == 409  # il TS non c'è più: niente da ritoccare


async def test_pending_save_still_failed_stays_failed(client, rules_catalog, test_session_factory):
    rules_catalog(_feature(ADD))
    cid = await _char(client)
    psid = await _pending_save(client, test_session_factory, cid, die=2, dc=25)
    r = await _after(client, cid, "add")
    assert r.status_code == 200 and r.json()["passed"] is False and r.json()["condition_removed"] is False
    async with test_session_factory() as s:
        ps = await s.get(PendingSave, psid)
        assert ps.status == "failed" and ps.last_roll["total"] == r.json()["total"]


async def test_pay_if_success_refund(client, rules_catalog):
    rules_catalog(_feature(PAID, ONCE, uses=_USES))
    cid = await _char(client)
    await _skill(client, cid)
    start = await _uses(client, cid)
    r = await _after(client, cid, "paid")
    assert r.json()["refundable"] == ["paid"] and await _uses(client, cid) == start - 1
    r = await client.post(f"/characters/{cid}/last-roll/refund")
    assert r.status_code == 200, r.text
    assert await _uses(client, cid) == start
    r = await client.post(f"/characters/{cid}/last-roll/refund")
    assert r.status_code == 409 and _code(r) == "nothing_to_refund"  # non si rimborsa due volte

    await _after(client, cid, "once")
    listed = await client.get(f"/characters/{cid}/roll-options", params={"roll": "skill", "skill": "athletics"})
    assert "once" not in [o["key"] for o in listed.json()]
    assert (await client.post(f"/characters/{cid}/last-roll/refund")).status_code == 200
    listed = await client.get(f"/characters/{cid}/roll-options", params={"roll": "skill", "skill": "athletics"})
    assert "once" in [o["key"] for o in listed.json()]


async def test_refund_only_of_the_last_roll(client, rules_catalog):
    rules_catalog(_feature(PAID, uses=_USES))
    cid = await _char(client)
    await _skill(client, cid)
    await _after(client, cid, "paid")
    await _skill(client, cid)
    r = await client.post(f"/characters/{cid}/last-roll/refund")
    assert r.status_code == 409 and _code(r) == "nothing_to_refund"


async def test_pending_save_refund_automatic(client, rules_catalog, test_session_factory):
    rules_catalog(_feature(PAID, uses=_USES))
    cid = await _char(client)
    await _pending_save(client, test_session_factory, cid, die=2, dc=25)
    start = await _uses(client, cid)
    r = await _after(client, cid, "paid")
    assert r.json()["passed"] is False and "refundable" not in r.json()
    assert await _uses(client, cid) == start


async def test_pending_save_success_keeps_the_payment(client, rules_catalog, test_session_factory):
    rules_catalog(_feature(PAID, uses=_USES))
    cid = await _char(client)
    await _pending_save(client, test_session_factory, cid, die=8, dc=9 + 5)
    start = await _uses(client, cid)
    r = await _after(client, cid, "paid", )
    assert r.json()["passed"] is True and await _uses(client, cid) == start - 1


async def test_after_roll_refused_without_last_roll(client, rules_catalog):
    rules_catalog(_feature(ADD))
    cid = await _char(client)
    r = await _after(client, cid, "add")
    assert r.status_code == 409 and _code(r) == "no_last_roll"
    await _skill(client, cid)
    await client.post(f"/characters/{cid}/turn/new")
    r = await _after(client, cid, "add")
    assert r.status_code == 409 and _code(r) == "no_last_roll"


async def test_after_roll_refused_after_the_damage(client, rules_catalog):
    rules_catalog(_feature(ADD))
    cid = await _char(client)
    item = await _weapon(client, cid)
    hit = await _deferred(client, cid, item)
    assert (await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={})).status_code == 200
    r = await _after(client, cid, "add")
    assert r.status_code == 409 and _code(r) == "no_last_roll"


async def test_after_roll_option_of_another_phase_refused(client, rules_catalog):
    rules_catalog(_feature(ADD, HIT_ONLY))
    cid = await _char(client)
    await _skill(client, cid)
    r = await _after(client, cid, "hit_only")
    assert r.status_code == 409 and _code(r) == "option_unavailable"
    r = await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 5, "options": ["add"]})
    assert r.status_code == 409 and _code(r) == "option_unavailable"


async def test_auto_fail_cannot_be_changed(client, rules_catalog):
    rules_catalog(_feature(PAID, uses=_USES))
    cid = await _char(client)
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"blinded": True}})
    assert r.status_code == 200
    await _skill(client, cid, options=["condition:blinded"])
    start = await _uses(client, cid)
    r = await _after(client, cid, "paid")
    assert r.status_code == 409 and _code(r) == "option_unavailable" and await _uses(client, cid) == start


async def test_last_roll_replaced_by_new_roll(client, rules_catalog):
    rules_catalog(_feature(ADD))
    cid = await _char(client)
    await _skill(client, cid, die=5)
    second = await _skill(client, cid, die=9)
    r = await _after(client, cid, "add")
    assert r.json()["die"] == 9 and r.json()["total"] == second["total"] + 3 and r.json()["description"] == "athletics"
    # un tiro che non si ritocca cancella comunque il precedente
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Dardo", "level": 0, "damage_dice": "1d4"})
    assert r.status_code == 201, r.text
    spell = r.json()["id"]
    r = await client.post(f"/characters/{cid}/spells/{spell}/roll_damage", json={})
    assert r.status_code == 200, r.text
    r = await _after(client, cid, "add")
    assert r.status_code == 409 and _code(r) == "no_last_roll"


# --- Limite per tiro --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("key,dice", [("add", None), ("again", [3]), ("luck", None)])
async def test_same_option_only_once_on_a_roll(client, rules_catalog, key, dice):
    costly = [replace(o, cost=Cost(feature_key="fighter.prova")) for o in (ADD, REROLL, LUCK)]
    rules_catalog(_feature(*costly, uses=_USES))
    cid = await _char(client)
    first = await _skill(client, cid)
    assert (await _after(client, cid, key, dice=dice)).status_code == 200
    uses = await _uses(client, cid)
    state = (await _after(client, cid, key, dice=dice))
    assert state.status_code == 409 and _code(state) == "option_unavailable" and state.json()["detail"]["key"] == key
    assert await _uses(client, cid) == uses
    # un tiro nuovo la riapre
    assert first and (await _skill(client, cid)) and (await _after(client, cid, key, dice=dice)).status_code == 200


async def test_pay_if_success_cannot_sum_for_free_up_to_the_dc(client, rules_catalog, test_session_factory):
    rules_catalog(_feature(PAID, uses=_USES))
    cid = await _char(client)
    await _pending_save(client, test_session_factory, cid, die=2, dc=11)  # 2 + 3 (competenza), +5 fa 10: resta fallito
    start = await _uses(client, cid)
    assert (await _after(client, cid, "paid")).json()["passed"] is False
    assert await _uses(client, cid) == start  # rimborso automatico
    again = await _after(client, cid, "paid")
    assert again.status_code == 409 and _code(again) == "option_unavailable"


async def test_refunded_option_stays_counted_on_the_roll(client, rules_catalog):
    rules_catalog(_feature(PAID, uses=_USES))
    cid = await _char(client)
    await _skill(client, cid)
    await _after(client, cid, "paid")
    assert (await client.post(f"/characters/{cid}/last-roll/refund")).status_code == 200
    again = await _after(client, cid, "paid")
    assert again.status_code == 409 and _code(again) == "option_unavailable"


async def test_refundable_accumulates_between_options(client, rules_catalog):
    other = replace(PAID, key="paid2")
    rules_catalog(_feature(PAID, other, uses=_USES))
    cid = await _char(client)
    await _skill(client, cid)
    start = await _uses(client, cid)
    await _after(client, cid, "paid")
    r = await _after(client, cid, "paid2")
    assert r.json()["refundable"] == ["paid", "paid2"] and await _uses(client, cid) == start - 2
    assert (await client.post(f"/characters/{cid}/last-roll/refund")).status_code == 200
    assert await _uses(client, cid) == start


# --- La domanda sul rimborso resta finché il tiro è l'ultimo --------------------------------------------------------------

async def _refundable(client, cid) -> dict:
    state = (await client.get(f"/characters/{cid}/turn-state")).json()
    return (state["turn"].get("last_roll") or {}).get("refundable") or {}


async def test_unanswered_refund_stays_until_answered_or_replaced(client, rules_catalog):
    rules_catalog(_feature(PAID, uses=_USES))
    cid = await _char(client)
    await _skill(client, cid)
    await _after(client, cid, "paid")
    assert list(await _refundable(client, cid)) == ["paid"]
    await _skill(client, cid)
    assert await _refundable(client, cid) == {}


async def test_declaring_success_closes_the_question_and_keeps_the_payment(client, rules_catalog):
    rules_catalog(_feature(PAID, uses=_USES))
    cid = await _char(client)
    await _skill(client, cid)
    start = await _uses(client, cid)
    await _after(client, cid, "paid")
    r = await client.post(f"/characters/{cid}/last-roll/refund", json={"succeeded": True})
    assert r.status_code == 200, r.text
    assert await _refundable(client, cid) == {} and await _uses(client, cid) == start - 1
    r = await client.post(f"/characters/{cid}/last-roll/refund")
    assert r.status_code == 409 and _code(r) == "nothing_to_refund"


async def test_damage_rolled_means_the_attack_hit_no_refund_left(client, rules_catalog):
    rules_catalog(_feature(PAID, uses=_USES))
    cid = await _char(client)
    item = await _weapon(client, cid)
    hit = await _deferred(client, cid, item)
    await _after(client, cid, "paid")
    assert (await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={})).status_code == 200
    assert await _refundable(client, cid) == {}


# --- Iniziativa -----------------------------------------------------------------------------------------------------------

async def test_initiative_can_be_retouched(client, rules_catalog):
    rules_catalog(_feature(ADD, REROLL))
    cid = await _char(client)
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 9})
    assert r.status_code == 200, r.text
    first = r.json()
    added = (await _after(client, cid, "add")).json()
    assert added["die"] == 9 and added["total"] == first["total"] + 3 and added["description"] == "initiative"
    again = (await _after(client, cid, "again", dice=[2])).json()
    assert again["die"] == 2 and again["total"] == added["total"] - 7


async def test_encounter_initiative_updates_the_combatant(client, rules_catalog, test_session_factory):
    rules_catalog(_feature(ADD))
    cid, sid, comb = await _encounter(client, test_session_factory)
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{comb}/initiative", json={"die": 9})
    assert r.status_code == 200, r.text
    before = next(c for c in r.json()["combatants"] if c["id"] == comb)
    r = await _after(client, cid, "add")
    assert r.status_code == 200, r.text
    assert r.json()["total"] == before["initiative"] + 3
    async with test_session_factory() as s:
        row = await s.get(Combatant, comb)
        assert row.initiative == before["initiative"] + 3 and row.initiative_die == 9


async def test_ended_encounter_initiative_is_refused(client, rules_catalog, test_session_factory):
    rules_catalog(_feature(ADD))
    cid, sid, comb = await _encounter(client, test_session_factory)
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{comb}/initiative", json={"die": 9})
    assert r.status_code == 200, r.text
    async with test_session_factory() as s:
        (await s.get(Encounter, (await s.get(Combatant, comb)).encounter_id)).status = "ended"
        await s.commit()
    r = await _after(client, cid, "add")
    assert r.status_code == 409 and _code(r) == "no_last_roll"


# --- TS contro la morte ---------------------------------------------------------------------------------------------------

async def _dying(client, cid, failures=0, successes=0, test_session_factory=None) -> None:
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 0})
    assert r.status_code == 200, r.text
    if failures or successes:
        async with test_session_factory() as s:
            ch = await s.get(Character, cid)
            ch.death_saves = {"successes": successes, "failures": failures, "stable": False}
            await s.commit()


async def _death(client, cid, die) -> dict:
    r = await client.post(f"/characters/{cid}/death_saves/roll", json={"die": die})
    assert r.status_code == 200, r.text
    return r.json()


async def _sheet(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def test_death_reroll_turns_failure_into_success(client, rules_catalog):
    rules_catalog(_feature(REROLL))
    cid = await _char(client)
    await _dying(client, cid)
    first = await _death(client, cid, 5)
    assert first["failures"] == 1 and first["successes"] == 0
    r = await _after(client, cid, "again", dice=[15])
    assert r.status_code == 200, r.text
    death = r.json()["death"]
    assert death["outcome"] == "success" and death["failures"] == 0 and death["successes"] == 1
    sheet = await _sheet(client, cid)
    assert sheet["death_saves"]["failures"] == 0 and sheet["death_saves"]["successes"] == 1


async def test_death_natural_one_reroll_removes_both_failures(client, rules_catalog, test_session_factory):
    rules_catalog(_feature(REROLL))
    cid = await _char(client)
    await _dying(client, cid, failures=1, test_session_factory=test_session_factory)
    first = await _death(client, cid, 1)
    assert first["outcome"] == "nat1" and first["failures"] == 3
    assert (await _sheet(client, cid))["is_dead"] is True
    death = (await _after(client, cid, "again", dice=[12])).json()["death"]
    assert death["outcome"] == "success" and death["failures"] == 1 and death["successes"] == 1
    assert (await _sheet(client, cid))["is_dead"] is False


async def test_death_reroll_to_natural_twenty_revives_and_back(client, rules_catalog):
    rules_catalog(_feature(REROLL, replace(REROLL, key="again2")))
    cid = await _char(client)
    await _dying(client, cid)
    await _death(client, cid, 5)
    death = (await _after(client, cid, "again", dice=[20])).json()["death"]
    assert death["outcome"] == "nat20" and death["revived"] is True and death["current_hp"] == 1
    assert death["failures"] == 0
    death = (await _after(client, cid, "again2", dice=[1])).json()["death"]
    assert death["outcome"] == "nat1" and death["revived"] is False and death["current_hp"] == 0
    assert death["failures"] == 2  # dallo stato prima del tiro, non da quello del ritiro


async def test_death_reroll_to_natural_one_kills(client, rules_catalog, test_session_factory):
    rules_catalog(_feature(REROLL))
    cid = await _char(client)
    await _dying(client, cid, failures=2, test_session_factory=test_session_factory)
    await _death(client, cid, 12)
    death = (await _after(client, cid, "again", dice=[1])).json()["death"]
    assert death["failures"] == 3 and (await _sheet(client, cid))["is_dead"] is True


async def test_death_add_reaches_ten_and_stabilizes_on_third(client, rules_catalog, test_session_factory):
    rules_catalog(_feature(ADD))
    cid = await _char(client)
    await _dying(client, cid, successes=2, test_session_factory=test_session_factory)
    first = await _death(client, cid, 8)
    assert first["outcome"] == "failure" and first["failures"] == 1
    death = (await _after(client, cid, "add")).json()["death"]
    assert death["outcome"] == "success" and death["failures"] == 0 and death["successes"] == 3 and death["stable"]


async def test_death_add_cannot_change_natural_one(client, rules_catalog):
    rules_catalog(_feature(ADD))
    cid = await _char(client)
    await _dying(client, cid)
    await _death(client, cid, 1)
    death = (await _after(client, cid, "add")).json()["death"]
    assert death["outcome"] == "nat1" and death["failures"] == 2


async def test_death_succeed_is_a_natural_twenty(client, rules_catalog):
    rules_catalog(_feature(LUCK))
    cid = await _char(client)
    await _dying(client, cid)
    await _death(client, cid, 5)
    death = (await _after(client, cid, "luck")).json()["death"]
    assert death["outcome"] == "nat20" and death["revived"] is True


async def test_death_recap_counts_only_the_final_outcome(client, rules_catalog, test_session_factory):
    rules_catalog(_feature(REROLL))
    cid = await _char(client)
    await _dying(client, cid)
    await _death(client, cid, 5)
    await _after(client, cid, "again", dice=[15])
    async with test_session_factory() as s:
        rows = (await s.execute(select(CharacterHistory).where(
            CharacterHistory.character_id == cid, CharacterHistory.event_type == "death_save"))).scalars().all()
    counted = [r.meta["ds"] for r in rows if r.meta and r.meta.get("ds")]
    assert counted == ["success"]


async def test_death_pay_if_success_refunded_when_still_failed(client, rules_catalog):
    rules_catalog(_feature(PAID, uses=_USES))
    cid = await _char(client)
    await _dying(client, cid)
    await _death(client, cid, 2)
    start = await _uses(client, cid)
    r = await _after(client, cid, "paid")  # 2 + 5 = 7
    assert r.json()["death"]["outcome"] == "failure" and "refundable" not in r.json()
    assert await _uses(client, cid) == start


async def test_death_retouch_refused_if_the_state_moved_on(client, rules_catalog):
    rules_catalog(_feature(REROLL))
    cid = await _char(client)
    await _dying(client, cid)
    await _death(client, cid, 5)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "heal", "value": 5})
    assert r.status_code == 200, r.text
    r = await _after(client, cid, "again", dice=[15])
    assert r.status_code == 409 and _code(r) == "not_rerollable"
    assert (await _sheet(client, cid))["current_hit_points"] == 5


# --- TS di concentrazione -------------------------------------------------------------------------------------------------

async def _concentrating(client, test_session_factory, cid, rounds=7) -> int:
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Benedizione", "level": 1, "is_concentration": True})
    assert r.status_code == 201, r.text
    spell = r.json()["id"]
    r = await client.patch(f"/characters/{cid}/concentration", json={"spell_id": spell, "rounds": rounds})
    assert r.status_code == 200, r.text
    return spell


async def _conc_save(client, cid, die, damage=30) -> dict:
    r = await client.post(f"/characters/{cid}/concentration/save", json={"damage": damage, "dice": [die]})
    assert r.status_code == 200, r.text
    return r.json()


async def test_concentration_reroll_success_restores_it(client, rules_catalog, test_session_factory):
    rules_catalog(_feature(REROLL))
    cid = await _char(client)
    spell = await _concentrating(client, test_session_factory, cid)
    async with test_session_factory() as s:
        ch = await s.get(Character, cid)
        ch.active_states = [{"key": "aura", "ends_on": ["concentration_end"], "rounds_left": None}]
        target = await upsert_effect(s, ("character", cid), "poisoned", ends_with_concentration=True,
                                     source_character_id=cid, source_spell_id=spell)
        ch.conditions = {"poisoned": True}
        await s.commit()
        assert target.id
    first = await _conc_save(client, cid, 2)
    assert first["success"] is False and first["lost_concentration"] is True
    sheet = await _sheet(client, cid)
    assert sheet["concentrating_spell_id"] is None and not sheet["conditions"].get("poisoned")

    r = await _after(client, cid, "again", dice=[19])
    assert r.status_code == 200, r.text
    conc = r.json()["concentration"]
    assert conc["success"] is True and conc["lost_concentration"] is False and conc["die"] == 19
    sheet = await _sheet(client, cid)
    assert sheet["concentrating_spell_id"] == spell and sheet["conditions"].get("poisoned")
    async with test_session_factory() as s:
        ch = await s.get(Character, cid)
        assert ch.settings["concentration_rounds_left"] == 7
        assert [a["key"] for a in ch.active_states] == ["aura"]


async def test_concentration_reroll_failure_after_pass_loses_it(client, rules_catalog, test_session_factory):
    rules_catalog(_feature(REROLL))
    cid = await _char(client)
    spell = await _concentrating(client, test_session_factory, cid)
    assert (await _conc_save(client, cid, 19))["success"] is True
    assert (await _sheet(client, cid))["concentrating_spell_id"] == spell
    conc = (await _after(client, cid, "again", dice=[2])).json()["concentration"]
    assert conc["success"] is False and conc["lost_concentration"] is True
    assert (await _sheet(client, cid))["concentrating_spell_id"] is None


async def test_concentration_failed_after_add_stays_lost_and_refunds(client, rules_catalog, test_session_factory):
    rules_catalog(_feature(PAID, uses=_USES))
    cid = await _char(client)
    await _concentrating(client, test_session_factory, cid)
    await _conc_save(client, cid, 2, damage=60)  # CD 30
    start = await _uses(client, cid)
    r = await _after(client, cid, "paid")
    assert r.json()["concentration"]["lost_concentration"] is True and "refundable" not in r.json()
    assert await _uses(client, cid) == start


async def test_concentration_not_restored_over_a_new_one(client, rules_catalog, test_session_factory):
    rules_catalog(_feature(REROLL))
    cid = await _char(client)
    await _concentrating(client, test_session_factory, cid)
    await _conc_save(client, cid, 2)
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Altra", "level": 1, "is_concentration": True})
    other = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}/concentration", json={"spell_id": other})).status_code == 200
    r = await _after(client, cid, "again", dice=[19])
    assert r.status_code == 409 and _code(r) == "not_rerollable"
    assert (await _sheet(client, cid))["concentrating_spell_id"] == other


async def test_concentration_save_from_damage_can_be_retouched(client, rules_catalog, test_session_factory, monkeypatch):
    rules_catalog(_feature(REROLL))
    cid = await _char(client)
    spell = await _concentrating(client, test_session_factory, cid)
    with monkeypatch.context() as patch:  # undo() toglierebbe anche il catalogo di prova
        patch.setattr("api.services.d20.random.randint", lambda _a, _b: 1)
        r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 5})
    assert r.status_code == 200 and r.json()["concentration_save"]["lost_concentration"] is True
    conc = (await _after(client, cid, "again", dice=[19])).json()["concentration"]
    assert conc["success"] is True
    assert (await _sheet(client, cid))["concentrating_spell_id"] == spell


@pytest.mark.parametrize("die", [10, 1])
async def test_attack_defers_when_only_after_roll_exists(client, rules_catalog, die):
    rules_catalog(_feature(LUCK))
    cid = await _char(client)
    item = await _weapon(client, cid)
    listed = await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": item})
    assert [(o["key"], o["phase"], o["after"]) for o in listed.json()] == [("luck", "after_roll", "succeed")]
    hit = await _deferred(client, cid, item, die=die)
    assert hit["attack_id"]
    state = await client.get(f"/characters/{cid}/turn-state")
    assert state.json()["turn"]["pending_attack"]["attack_id"] == hit["attack_id"]


async def test_natural_one_without_after_roll_has_no_pending(client, rules_catalog):
    rules_catalog(_feature(HIT_ONLY))
    cid = await _char(client)
    item = await _weapon(client, cid)
    fumble = await _deferred(client, cid, item, die=1)
    assert "attack_id" not in fumble


async def _save_dice(test_session_factory, cid, values) -> None:
    async with test_session_factory() as s:
        ch = await s.get(Character, cid)
        ch.settings = {**(ch.settings or {}), "saved_dice": {"portent": values}}
        await s.commit()


async def test_replace_die_uses_saved_value_only(client, rules_catalog, test_session_factory):
    rules_catalog(_feature(PORTENT))
    cid = await _char(client)
    listed = await client.get(f"/characters/{cid}/roll-options", params={"roll": "skill", "skill": "athletics"})
    assert listed.json() == []  # nessun dado salvato: non si offre
    await _save_dice(test_session_factory, cid, [4, 17])
    listed = await client.get(f"/characters/{cid}/roll-options", params={"roll": "skill", "skill": "athletics"})
    assert listed.json()[0]["saved_dice"] == [4, 17]

    r = await client.post(f"/characters/{cid}/skills/athletics/roll",
                          json={"die": 2, "options": ["portent"], "option_inputs": {"portent": {"die": 9}}})
    assert r.status_code == 409 and _code(r) == "option_unavailable"  # non è fra i salvati

    r = await client.post(f"/characters/{cid}/skills/athletics/roll",
                          json={"die": 2, "mode": "normal", "options": ["portent"], "option_inputs": {"portent": {"die": 17}}})
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 17 and r.json()["total"] == 17 + r.json()["bonus"]
    async with test_session_factory() as s:
        assert (await s.get(Character, cid)).settings["saved_dice"]["portent"] == [4]  # si consuma


async def test_replace_die_token_is_refundable(client, test_session_factory):
    cid = await _char(client)
    await _save_dice(test_session_factory, cid, [])
    async with test_session_factory() as s:
        ch = await s.get(Character, cid)
        refund_spent(ch, ["die:portent:17"])
        assert ch.settings["saved_dice"]["portent"] == [17]


async def test_inspiration_reroll_unchanged(client):
    cid = await _char(client, edition="2024")
    r = await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    assert r.status_code == 200, r.text
    first = await _skill(client, cid, die=5)
    second = await _skill(client, cid, die=14, with_inspiration=True)
    assert second["die"] == 14 and second["total"] == first["total"] + 9
    assert set(second) == set(first) and "refundable" not in second and "option_result" not in second
    r = await client.post(f"/characters/{cid}/skills/athletics/roll", json={"die": 14, "with_inspiration": True})
    assert r.status_code == 409


async def test_inspiration_after_before_option_keeps_it_without_paying(client, rules_catalog):
    bless = RollOptionSpec(key="bless2", phase="before", rolls=("skill",), label=_LABEL, bonus=lambda _c, _i: 2,
                           cost=Cost(feature_key="fighter.prova"))
    rules_catalog(replace(_feature(bless, uses=_USES), edition="2024"))
    cid = await _char(client, edition="2024")
    await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    first = await _skill(client, cid, die=5, options=["bless2"])
    uses = await _uses(client, cid)
    second = await _skill(client, cid, die=6, with_inspiration=True)
    assert second["bonus"] == first["bonus"] and await _uses(client, cid) == uses
