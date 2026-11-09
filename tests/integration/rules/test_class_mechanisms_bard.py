"""Meccanismi comuni aggiunti per il Bardo (Task 20), provati con privilegi di prova."""
from __future__ import annotations

from core.rules.types import ChoiceSpec, FeatureSpec, OnUse, Uses

KEY, COUNTER = "bard.prova", "bard.contatore"


def _spec(key=KEY, level=1, **kw) -> FeatureSpec:
    return FeatureSpec(key=key, class_key="bard", edition="2014", level=level, source_title=key,
                       name={"it": "Prova", "en": "Test"}, summary={"it": "x", "en": "x"}, action_type=None, **kw)


async def _bard(client, level=5) -> int:
    r = await client.post("/characters", json={"name": "Prova", "initial_class": {"class_name": "bard", "level": level}})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _full(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def _use(client, cid, key=KEY):
    return await client.post(f"/characters/{cid}/features/{key}/use", json={})


def _uses_of(full, key) -> int:
    return next(a for a in full["abilities"] if a["feature_key"] == key)["uses"]


async def test_use_can_roll_a_die_that_depends_on_the_level(client, rules_catalog):
    rules_catalog(_spec(on_use=OnUse(rolls=lambda ctx: "1d4" if ctx.class_level < 5 else "1d12")))
    low, high = await _bard(client, 3), await _bard(client, 5)
    low_rolls = [(await _use(client, low)).json()["rolls"][0] for _ in range(10)]
    high_rolls = [(await _use(client, high)).json()["rolls"][0] for _ in range(40)]
    assert all(1 <= r <= 4 for r in low_rolls)
    assert all(1 <= r <= 12 for r in high_rolls) and max(high_rolls) > 4


def test_a_rolls_formula_is_validated_when_it_is_a_string():
    import pytest

    with pytest.raises(ValueError):
        OnUse(rolls="d6")


async def test_use_can_spend_the_uses_of_another_feature(client, rules_catalog):
    rules_catalog(_spec(COUNTER, uses=Uses(table={1: 2}), restoration="long_rest"),
                  _spec(on_use=OnUse(slot="reaction", spends=COUNTER)))
    cid = await _bard(client)
    assert (await _use(client, cid)).status_code == 200
    full = await _full(client, cid)
    assert _uses_of(full, COUNTER) == 1
    await client.post(f"/characters/{cid}/turn/new")
    assert (await _use(client, cid)).status_code == 200
    await client.post(f"/characters/{cid}/turn/new")
    refused = await _use(client, cid)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "no_uses"
    turn = (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]
    assert turn["reaction_used"] is False and _uses_of(await _full(client, cid), COUNTER) == 0


async def test_spending_a_missing_feature_is_refused_before_the_turn_slot(client, rules_catalog):
    rules_catalog(_spec(on_use=OnUse(slot="action", spends="bard.assente")))
    cid = await _bard(client)
    r = await _use(client, cid)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]["action_used"] is False


async def test_choice_grants_proficiency_or_expertise_on_resolution(client, rules_catalog):
    skills = ["arcana", "history", "stealth"]
    rules_catalog(
        _spec(choices=(ChoiceSpec("studio", {1: 1}, lambda ctx: [s for s in skills if not (ctx.char.skills or {}).get(s)],
                                  grants="proficient"),)),
        _spec("bard.maestria", choices=(ChoiceSpec("maestria", {1: 1}, lambda ctx: [s for s in skills if (ctx.char.skills or {}).get(s)],
                                                   grants="expert"),)))
    cid = await _bard(client, 1)
    await client.patch(f"/characters/{cid}/skills", json={"skills": {"history": True}})
    pending = {c["group"]: c for c in (await _full(client, cid))["pending_choices"]}

    async def resolve(group, key):
        return await client.post(f"/characters/{cid}/choices/{pending[group]['id']}/resolve",
                                 json={"kind": "class_option", "options": [key]})

    assert (await resolve("studio", "history")).status_code == 422  # già competente: non è fra le offerte
    assert (await resolve("studio", "arcana")).json()["skills"]["arcana"] is True
    assert (await resolve("maestria", "history")).json()["skills"]["history"] == "expert"


async def test_expertise_never_lowers_a_skill_that_is_already_expert(client, rules_catalog):
    rules_catalog(_spec(choices=(ChoiceSpec("studio", {1: 1}, lambda ctx: ["arcana"], grants="proficient"),)))
    cid = await _bard(client, 1)
    await client.patch(f"/characters/{cid}/skills", json={"skills": {"arcana": "expert"}})
    choice = next(c for c in (await _full(client, cid))["pending_choices"] if c["group"] == "studio")
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve", json={"kind": "class_option", "options": ["arcana"]})
    assert r.status_code == 200 and r.json()["skills"]["arcana"] == "expert"


def test_a_spell_pick_value_is_validated():
    import pytest

    with pytest.raises(ValueError):
        ChoiceSpec("x", {1: 1}, lambda ctx: [], spell_pick="altro")
