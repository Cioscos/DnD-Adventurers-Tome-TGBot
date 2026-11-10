"""Minori rinviati, Task 5 (punto 25): i quindici difetti minori del Warlock 2024 (task-41-review.md, M1-M15)."""
from __future__ import annotations

from tests.integration.rules.test_2014_barbarian import _keys
from tests.integration.rules.test_2014_bard import _full, _use
from tests.integration.rules.test_2014_paladin import _new_turn
from tests.integration.rules.test_2024_warlock_patrons import ESCAPE, VENGEANCE, _effect, _hp, _make, _misty
from tests.integration.rules.test_2014_warlock_invocations import _cast


async def test_warlock_25_m4_thought_shield_says_how_much_to_reflect(client):
    cid = await _make(client, "great_old_one", 10)
    await _hp(client, cid, op="set_max", value=100)
    await _hp(client, cid, op="set_current", value=100)
    full = await _hp(client, cid, op="damage", value=10, damage_type="psychic", options=["warlock.thought_shield_reflection"])
    assert full["option_result"]["effects"][0]["it"].endswith(": 5."), full["option_result"]["effects"]


def test_warlock_25_m5_eldritch_hex_names_the_ability_not_its_raw_key():
    from core.rules.catalog.y2024.warlock_subclasses import ABILITIES, _hex
    for ability in ABILITIES:
        spec = _hex(ability)
        text = " ".join([*spec.label.values(), *spec.effect(None, {}).values()])
        assert ability not in text
    assert "Forza" in _hex("strength").label["it"] and "Strength" in _hex("strength").label["en"]


async def test_warlock_25_m7_psychic_spells_only_for_warlock_spells(client):
    from tests.integration.rules.test_2014_fighter_eldritch_knight import _spell
    from tests.integration.rules.test_2014_bard import _roll_keys
    cid = await _make(client, "great_old_one", 5)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 1, "hit_die": 6})
    assert r.status_code == 201, r.text
    classes = {c["class_name"]: c["id"] for c in (await _full(client, cid))["classes"]}
    mine = await _spell(client, cid, "Fiamma", 1, damage_dice="2d6", damage_type="fire", class_id=classes["warlock"], school="enchantment")
    other = await _spell(client, cid, "Palla", 1, damage_dice="2d6", damage_type="fire", class_id=classes["wizard"], school="enchantment")
    for spell, expected in ((mine, True), (other, False)):
        assert ("warlock.psychic_spells" in await _roll_keys(client, cid, "spell_damage", spell_id=spell)) is expected
        assert ("warlock.psychic_spells_silent" in await _roll_keys(client, cid, "cast", spell_id=spell)) is expected


async def test_warlock_25_m10_magical_cunning_says_how_many_slots_come_back(client):
    from tests.integration.rules.test_2024_warlock import CUNNING, _set_used, _warlock24
    from tests.integration.rules.test_2014_warlock import _pact_slots
    cid = await _warlock24(client, 11)
    [pact] = await _pact_slots(client, cid)
    await _set_used(client, cid, pact["id"], 3)
    r = await _use(client, cid, CUNNING)
    assert r.status_code == 200, r.text
    assert "2 slot di Patto" in r.json()["message"]["it"] and "2 Pact slots" in r.json()["message"]["en"]


async def test_warlock_25_m11_a_slot_cast_misty_step_still_warns_with_bewitching_magic_active(client):
    from tests.integration.rules.test_2014_fighter_eldritch_knight import _spell
    from tests.integration.rules.test_2024_warlock_patrons import BEWITCH, _level
    cid = await _make(client, "archfey", 14)
    charm = await _spell(client, cid, "Sonno", 1, school="enchantment")
    misty = await _misty(client, cid)
    level = await _level(client, cid)
    assert (await _cast(client, cid, charm, slot_level=level, options=[BEWITCH])).status_code == 200
    r = await _cast(client, cid, misty, slot_level=level)  # con uno slot: un secondo incantesimo con slot nello stesso turno
    assert r.status_code == 409 and "one_slot_per_turn" in r.json()["detail"]["warnings"], r.text
    assert (await _cast(client, cid, misty, free_cast=True)).status_code == 200  # il lancio gratuito no


async def test_warlock_25_m12_devils_sight_is_not_a_source_of_the_attack_result(client):
    from tests.integration.rules.test_2014_barbarian import _weapon
    from tests.integration.rules.test_2014_warlock import _resolve
    from tests.integration.rules.test_2024_warlock import _warlock24
    cid = await _warlock24(client, 5)
    assert (await _resolve(client, cid, "invocations", ["armor_of_shadows", "devils_sight", "eldritch_mind", "fiendish_vigor", "misty_visions"])).status_code == 200, "resolve"
    wid = await _weapon(client, cid)
    r = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 12})
    assert r.status_code == 200, r.text
    assert not [n for n in r.json()["notes"] if "devils_sight" in str(n)], r.json()["notes"]


def test_warlock_25_m13_lessons_of_the_first_ones_says_the_app_does_not_grant_the_feat():
    from core.rules.catalog import features_for
    spec = next(s for s in features_for("2024", "warlock") if s.key == "warlock.lessons_of_the_first_ones")
    assert "L'app non lo assegna" in spec.summary["it"] and "does not grant" in spec.summary["en"]
    assert len(spec.summary["it"]) <= 200 and len(spec.summary["en"]) <= 200


async def _d10s(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}/dice/stats")).json()["stats"].get("d10", {})


async def test_warlock_25_m14_the_refreshing_step_d10_goes_in_the_dice_history(client, monkeypatch):
    from tests.integration.rules.test_2014_paladin import _new_turn
    from tests.integration.rules.test_2024_warlock_patrons import STEPS
    cid = await _make(client, "archfey", 6, charisma=18)
    monkeypatch.setattr("random.randint", lambda _a, b: min(7, b))
    assert (await _use(client, cid, ESCAPE, params={"effect": "refreshing"})).status_code == 200
    assert await _d10s(client, cid) == {"7": 1}  # dall'uso della Fuga Velata
    await _new_turn(client, cid)
    r = await _cast(client, cid, await _misty(client, cid), free_cast=True, options=[STEPS + "_refreshing"])
    assert r.status_code == 200, r.text
    assert await _d10s(client, cid) == {"7": 2}  # e dall'opzione del lancio


async def test_warlock_25_m14_an_invocation_goes_dormant_when_the_level_drops_below_its_own(client):
    from tests.integration.rules.test_2014_warlock import _resolve
    from tests.integration.rules.test_2024_warlock import _warlock24
    cid = await _warlock24(client, 5)
    picks = ["armor_of_shadows", "devils_sight", "eldritch_mind", "fiendish_vigor", "misty_visions"]
    assert (await _resolve(client, cid, "invocations", picks)).status_code == 200
    full = await _full(client, cid)
    assert {"type": "devils_sight", "range_ft": 120} in full["computed"]["senses"]
    r = await client.patch(f"/characters/{cid}/classes/{full['classes'][0]['id']}", json={"level": 1})
    assert r.status_code == 200, r.text
    assert {"type": "devils_sight", "range_ft": 120} not in (await _full(client, cid))["computed"]["senses"]


async def test_warlock_25_m15_the_awakened_mind_link_ends_with_a_short_rest_by_its_duration(client):
    from tests.integration.rules.test_2014_paladin import _rest
    from tests.integration.rules.test_2024_warlock_patrons import MIND, _states
    cid = await _make(client, "great_old_one", 5)
    assert (await _use(client, cid, MIND)).status_code == 200
    assert "awakened_mind" in _states(await _full(client, cid))
    await _rest(client, cid, "short")  # 5 minuti: finisce prima di un'ora
    assert "awakened_mind" not in _states(await _full(client, cid))


async def test_warlock_25_m1_disappearing_step_ends_when_you_attack_and_when_you_cast(client):
    from tests.integration.rules.test_2014_barbarian import _weapon
    from tests.integration.rules.test_2014_fighter_eldritch_knight import _spell
    cid = await _make(client, "archfey", 6, charisma=18)
    misty, wid = await _misty(client, cid), await _weapon(client, cid)
    for ender in ("attack", "cast"):
        assert (await _cast(client, cid, misty, free_cast=True, options=[ESCAPE + "_disappearing"])).status_code == 200
        assert (await _full(client, cid))["conditions"]["invisible"] is True
        if ender == "attack":
            assert (await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 12})).status_code == 200
        else:
            dart = await _spell(client, cid, "Dardo", 0, damage_dice="1d10", damage_type="force")
            assert (await _cast(client, cid, dart)).status_code == 200
        assert not (await _full(client, cid))["conditions"].get("invisible")
        await _new_turn(client, cid)


async def test_warlock_25_m6_healing_light_and_awakened_mind_are_bonus_actions(client):
    from tests.integration.rules.test_2014_bard import _ability
    celestial = await _make(client, "celestial", 5)
    old_one = await _make(client, "great_old_one", 5)
    assert (await _ability(client, celestial, "warlock.healing_light"))["action_type"] == "bonus_action"
    assert (await _ability(client, old_one, "warlock.awakened_mind"))["action_type"] == "bonus_action"
