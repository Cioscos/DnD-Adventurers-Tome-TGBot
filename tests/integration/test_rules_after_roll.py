"""Privilegi usati dopo aver visto il d20: il server legge il tiro dal proprio stato, non dal client."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from api.services.condition_effects import SaveSpec, upsert_effect
from core.db.models import Character, PendingSave
from core.rules.roll_options import refund_spent
from core.rules.types import Cost, RollOptionSpec, Uses
from tests.integration.test_rules_roll_options_api import _LABEL, _char, _code, _deferred, _feature, _uses, _weapon

ROLLS = ("attack", "skill", "save")
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
    rules_catalog(_feature(REROLL))
    cid = await _char(client)
    item = await _weapon(client, cid)
    hit = await _deferred(client, cid, item, die=10)
    same = (await _after(client, cid, "again", dice=[12])).json()["attack"]
    assert same["to_hit_die"] == 12 and same["damage_total"] == hit["damage_total"]
    crit = (await _after(client, cid, "again", dice=[20])).json()["attack"]
    assert crit["is_critical"] is True and len(crit["damage_rolls"]) == 2  # 1d8 raddoppiato
    fumble = (await _after(client, cid, "again", dice=[1])).json()["attack"]
    assert fumble["is_fumble"] is True and fumble["damage_total"] == 0
    r = await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={})
    assert r.status_code == 409 and _code(r) == "attack_missed"


async def test_succeed_turns_skill_to_20_and_attack_to_hit_not_crit(client, rules_catalog):
    rules_catalog(_feature(LUCK))
    cid = await _char(client)
    first = await _skill(client, cid, die=4)
    body = (await _after(client, cid, "luck")).json()
    assert body["die"] == 20 and body["total"] == first["total"] + 16 and body["is_critical"] is True

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
    r = await client.post(f"/characters/{cid}/dice/initiative", json={"die": 9})
    assert r.status_code == 200, r.text
    r = await _after(client, cid, "add")
    assert r.status_code == 409 and _code(r) == "no_last_roll"


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
    cid = await _char(client)
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
    rules_catalog(_feature(bless, uses=_USES))
    cid = await _char(client)
    await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    first = await _skill(client, cid, die=5, options=["bless2"])
    uses = await _uses(client, cid)
    second = await _skill(client, cid, die=6, with_inspiration=True)
    assert second["bonus"] == first["bonus"] and await _uses(client, cid) == uses
