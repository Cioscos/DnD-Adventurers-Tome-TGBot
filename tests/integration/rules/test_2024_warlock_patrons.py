"""Warlock 2024 (Task 41, parte B): Patrono Fatato, Celestiale, Immondo e Grande Antico. Valori da
``docs/superpowers/rules/2024/classes/warlock.md``; nessun d20 casuale (``random.randint`` fissato dove un dado conta)."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from core.rules.catalog import features_for
from core.rules.catalog.granted_spells import GRANTED_SPELLS
from tests.integration.rules.test_2014_barbarian import _keys, _turn, _weapon
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _use
from tests.integration.rules.test_2014_fighter_eldritch_knight import _spell
from tests.integration.rules.test_2014_paladin import _new_turn, _rest
from tests.integration.rules.test_2014_warlock import _pact_slots
from tests.integration.rules.test_2014_warlock_invocations import _cast, _spells_by_index

NAMES = {"archfey": "Patrono Fatato", "celestial": "Patrono Celestiale", "fiend": "Patrono Immondo", "great_old_one": "Patrono Grande Antico"}
P = "warlock."
ROWS = {
    "archfey": {3: ["archfey_spells", "steps_of_the_fey"], 6: ["misty_escape"], 10: ["beguiling_defenses"], 14: ["bewitching_magic"]},
    "celestial": {3: ["celestial_spells", "healing_light"], 6: ["radiant_soul"], 10: ["celestial_resilience"], 14: ["searing_vengeance"]},
    "fiend": {3: ["dark_ones_blessing", "fiend_spells"], 6: ["dark_ones_own_luck"], 10: ["fiendish_resilience"], 14: ["hurl_through_hell"]},
    "great_old_one": {3: ["awakened_mind", "great_old_one_spells", "psychic_spells"], 6: ["clairvoyant_combatant"],
                      10: ["eldritch_hex", "thought_shield"], 14: ["create_thrall"]},
}
FLAT = [(sub, lv, key) for sub, levels in ROWS.items() for lv, keys in levels.items() for key in keys]
TIERS = {
    "archfey": {3: {"calm-emotions", "faerie-fire", "misty-step", "phantasmal-force", "sleep"}, 5: {"blink", "plant-growth"},
                7: {"dominate-beast", "greater-invisibility"}, 9: {"dominate-person", "seeming"}},
    "celestial": {3: {"aid", "cure-wounds", "guiding-bolt", "lesser-restoration", "light", "sacred-flame"}, 5: {"daylight", "revivify"},
                  7: {"guardian-of-faith", "wall-of-fire"}, 9: {"greater-restoration", "summon-celestial"}},
    "fiend": {3: {"burning-hands", "command", "scorching-ray", "suggestion"}, 5: {"fireball", "stinking-cloud"},
              7: {"fire-shield", "wall-of-fire"}, 9: {"geas", "insect-plague"}},
    "great_old_one": {3: {"detect-thoughts", "dissonant-whispers", "phantasmal-force", "tashas-hideous-laughter"},
                      5: {"clairvoyance", "hunger-of-hadar"}, 7: {"confusion", "summon-aberration"}, 9: {"modify-memory", "telekinesis"}},
}


async def _make(client, sub, level=14, **scores) -> int:
    body = {"name": "Warlock", "initial_class": {"class_name": "warlock", "level": level, "subclass": NAMES[sub]}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    for ability, value in {"charisma": 16, **scores}.items():
        assert (await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})).status_code == 200
    return cid


def _states(full: dict) -> dict[str, dict]:
    return {s["key"]: s for s in full["active_states"] or []}


async def _effect(client, cid, key) -> dict:
    return (await client.get(f"/characters/{cid}/target-effects/{key}")).json()["result"]


async def _level(client, cid) -> int:
    return (await _pact_slots(client, cid))[0]["level"]


async def _hp(client, cid, **body):
    r = await client.patch(f"/characters/{cid}/hp", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Catalogo: titoli, livelli, solo il proprio patrono
# ---------------------------------------------------------------------------

def test_every_patron_mapping_title_has_its_row_with_both_languages():
    rows = features_for("2024", "warlock")
    titles = {f.source_title for f in rows}
    mapping = open("docs/superpowers/rules/mapping/2024/warlock.md", encoding="utf-8").read().splitlines()[4:]
    wanted = [l.split("|")[1].strip() for l in mapping if l.startswith("|") and "(Patrono " in l.split("|")[1]]
    assert len(wanted) == 22 and [t for t in wanted if t not in titles] == []
    assert all(f.summary["it"] and f.summary["en"] and len(f.summary["it"]) <= 200 and len(f.summary["en"]) <= 200 for f in rows)


@pytest.mark.parametrize("sub,level,key", FLAT)
def test_a_patron_row_appears_at_its_level_and_only_for_its_subclass(sub, level, key):
    spec = {f.key: f for f in features_for("2024", "warlock")}[P + key]
    assert spec.level == level and spec.subclass == sub


@pytest.mark.parametrize("sub", list(ROWS))
async def test_a_patron_gives_only_its_own_rows(client, sub):
    keys = await _keys_of(client, await _make(client, sub))
    mine = {P + k for levels in ROWS[sub].values() for k in levels}
    others = {P + k for s, levels in ROWS.items() if s != sub for ks in levels.values() for k in ks}
    assert mine <= keys and not others & keys
    low = await _keys_of(client, await _make(client, sub, 5))
    assert {P + k for lv, ks in ROWS[sub].items() if lv > 5 for k in ks}.isdisjoint(low)


@pytest.mark.parametrize("sub", list(TIERS))
@pytest.mark.parametrize("level,expected", [(2, 0), (3, 1), (5, 2), (7, 3), (9, 4)])
async def test_patron_spells_are_always_prepared_from_their_level(client, sub, level, expected):
    have = set(await _spells_by_index(client, await _make(client, sub, level)))
    tiers = TIERS[sub]
    wanted = set().union(*(tiers[t] for t in sorted(tiers)[:expected])) if expected else set()
    assert wanted <= have
    assert not set().union(*(tiers[t] for t in sorted(tiers)[expected:])) & have


def test_every_patron_spell_has_its_granted_data():
    for tiers in TIERS.values():
        for spells in tiers.values():
            assert spells <= set(GRANTED_SPELLS)


# ---------------------------------------------------------------------------
# Patrono Fatato
# ---------------------------------------------------------------------------

STEPS, ESCAPE, DEFENSES, BEWITCH = P + "steps_of_the_fey", P + "misty_escape", P + "beguiling_defenses", P + "bewitching_magic"


@pytest.mark.parametrize("charisma,uses", [(18, 4), (16, 3), (8, 1)])
async def test_steps_of_the_fey_uses_are_charisma_with_a_minimum_of_one(client, charisma, uses):
    row = await _ability(client, await _make(client, "archfey", 3, charisma=charisma), STEPS)
    assert row["max_uses"] == uses and row["restoration_type"] == "long_rest"


async def _misty(client, cid) -> int:
    return (await _spells_by_index(client, cid))["misty-step"]["id"]


async def test_steps_of_the_fey_casts_misty_step_free_and_refreshing_gives_the_d10_as_temporary_points(client, monkeypatch):
    cid = await _make(client, "archfey", 5)
    spell = await _misty(client, cid)
    assert STEPS + "_refreshing" in await _keys(client, cid, "cast", spell_id=spell)
    monkeypatch.setattr("random.randint", lambda _a, b: min(7, b))
    before = sum(s["available"] for s in (await _full(client, cid))["spell_slots"])
    r = await _cast(client, cid, spell, free_cast=True, options=[STEPS + "_refreshing"])
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    assert full["temp_hp"] == 7 and sum(s["available"] for s in full["spell_slots"]) == before
    assert (await _ability(client, cid, STEPS))["uses"] == 2  # Carisma 16: 3 usi
    assert "7" in r.json()["option_result"]["effects"][0]["it"]


async def test_steps_of_the_fey_to_another_creature_reports_the_value_and_keeps_my_points(client, monkeypatch):
    cid = await _make(client, "archfey", 5)
    monkeypatch.setattr("random.randint", lambda _a, b: min(6, b))
    r = await _cast(client, cid, await _misty(client, cid), free_cast=True, options=[STEPS + "_refreshing_other"])
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["temp_hp"] == 0 and "6" in r.json()["option_result"]["effects"][0]["it"]


async def test_taunting_step_asks_a_wisdom_save_against_my_dc_until_the_start_of_my_next_turn(client):
    cid = await _make(client, "archfey", 5, charisma=18)
    r = await _cast(client, cid, await _misty(client, cid), free_cast=True, options=[STEPS + "_taunting"])
    assert r.status_code == 200, r.text
    effect = await _effect(client, cid, STEPS + "_taunting")
    assert effect["save_ability"] == "wisdom" and effect["save_dc"] == 8 + 3 + 4 and effect["note"] == "taunting_step"
    assert effect["ends_at"] == {"anchor": "source", "edge": "start", "count": 1}


async def test_only_one_step_effect_per_cast_and_the_level_6_ones_wait_for_misty_escape(client):
    low, cid = await _make(client, "archfey", 5), await _make(client, "archfey", 6)
    assert {STEPS + "_refreshing", STEPS + "_taunting"} <= set(await _keys(client, low, "cast", spell_id=await _misty(client, low)))
    assert not {ESCAPE + "_disappearing", ESCAPE + "_terrifying"} & set(await _keys(client, low, "cast", spell_id=await _misty(client, low)))
    assert {ESCAPE + "_disappearing", ESCAPE + "_terrifying"} <= set(await _keys(client, cid, "cast", spell_id=await _misty(client, cid)))
    r = await _cast(client, cid, await _misty(client, cid), free_cast=True, options=[STEPS + "_taunting", ESCAPE + "_terrifying"])
    assert r.status_code == 409


async def test_disappearing_and_terrifying_step_on_a_free_cast(client):
    cid = await _make(client, "archfey", 6, charisma=18)
    spell = await _misty(client, cid)
    assert (await _cast(client, cid, spell, free_cast=True, options=[ESCAPE + "_disappearing"])).status_code == 200
    assert (await _full(client, cid))["conditions"]["invisible"] is True
    await _new_turn(client, cid)
    assert not (await _full(client, cid))["conditions"].get("invisible")
    assert (await _cast(client, cid, spell, free_cast=True, options=[ESCAPE + "_terrifying"])).status_code == 200
    effect = await _effect(client, cid, ESCAPE + "_terrifying")
    assert effect["save_ability"] == "wisdom" and effect["save_dc"] == 8 + 3 + 4 and effect["damage_dice"] == "2d10"


async def test_misty_escape_is_a_reaction_that_spends_a_steps_use_and_can_add_an_effect(client, monkeypatch):
    cid = await _make(client, "archfey", 6, charisma=18)
    assert (await _use(client, cid, ESCAPE, params={"effect": "plain"})).status_code == 200  # nessun effetto sugli altri
    assert (await _turn(client, cid))["reaction_used"] is True and (await _ability(client, cid, STEPS))["uses"] == 3
    await _new_turn(client, cid)
    r = await _use(client, cid, ESCAPE, params={"effect": "disappearing"})
    assert r.status_code == 200 and (await _full(client, cid))["conditions"]["invisible"] is True
    assert r.json()["targets"] == []
    await _new_turn(client, cid)
    monkeypatch.setattr("random.randint", lambda _a, b: min(9, b))
    r = await _use(client, cid, ESCAPE, params={"effect": "refreshing"})
    assert r.status_code == 200 and (await _full(client, cid))["temp_hp"] == 9 and "9" in r.json()["message"]["it"]
    await _new_turn(client, cid)
    r = await _use(client, cid, ESCAPE, params={"effect": "terrifying"})
    assert r.status_code == 200 and r.json()["targets"] == [ESCAPE]
    assert (await _effect(client, cid, ESCAPE))["damage_dice"] == "2d10"
    assert (await _ability(client, cid, STEPS))["uses"] == 0
    await _new_turn(client, cid)
    assert (await _use(client, cid, ESCAPE, params={"effect": "plain"})).status_code == 409  # niente usi di Passi del Fatato


async def test_beguiling_defenses_make_me_immune_to_charm(client):
    low, cid = await _make(client, "archfey", 9), await _make(client, "archfey", 10)
    r = await client.patch(f"/characters/{low}/conditions", json={"conditions": {"charmed": True}})
    assert r.json()["conditions"].get("charmed") is True
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"charmed": True, "prone": True}})
    assert r.json()["conditions"].get("charmed") is None and r.json()["conditions"]["prone"] is True


async def test_beguiling_defenses_halve_the_hit_and_turn_the_damage_back_once_per_long_rest(client):
    cid = await _make(client, "archfey", 10, charisma=18)
    await _hp(client, cid, op="set_max", value=100)
    await _hp(client, cid, op="set_current", value=100)
    assert DEFENSES in await _keys(client, cid, "damage_taken", damage_type="slashing")
    full = await _hp(client, cid, op="damage", value=11, damage_type="slashing", options=[DEFENSES])
    assert full["current_hit_points"] == 95  # 11 dimezzato per difetto: 5
    assert (await _turn(client, cid))["reaction_used"] is True and (await _ability(client, cid, DEFENSES))["uses"] == 0
    await _new_turn(client, cid)
    assert DEFENSES not in await _keys(client, cid, "damage_taken", damage_type="slashing")
    assert DEFENSES + "_slot" in await _keys(client, cid, "damage_taken", damage_type="slashing")
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, DEFENSES))["uses"] == 1


async def test_beguiling_defenses_can_be_restored_with_a_pact_slot_and_never_a_normal_one(client):
    cid = await _make(client, "archfey", 10, charisma=18)
    await _hp(client, cid, op="set_max", value=100)
    await _hp(client, cid, op="set_current", value=100)
    await _hp(client, cid, op="damage", value=10, damage_type="slashing", options=[DEFENSES])
    await _new_turn(client, cid)
    pact = (await _pact_slots(client, cid))[0]
    full = await _hp(client, cid, op="damage", value=10, damage_type="slashing", options=[DEFENSES + "_slot"],
                     option_inputs={DEFENSES + "_slot": {"slot_level": pact["level"]}})
    assert full["current_hit_points"] == 90  # 100 - 5 - 5: due colpi dimezzati
    assert (await _pact_slots(client, cid))[0]["used"] == 1 and (await _ability(client, cid, DEFENSES))["uses"] == 0


# Magia Stregata

async def test_bewitching_magic_offers_a_free_misty_step_after_a_charm_or_illusion_spell_with_a_slot(client):
    cid = await _make(client, "archfey", 14)
    charm = await _spell(client, cid, "Sonno", 1, school="enchantment")
    evoc = await _spell(client, cid, "Dardo", 1, school="evocation")
    free = await _spell(client, cid, "Trucchetto", 0, school="enchantment")
    assert BEWITCH in await _keys(client, cid, "cast", spell_id=charm)
    assert BEWITCH not in await _keys(client, cid, "cast", spell_id=evoc)
    assert BEWITCH not in await _keys(client, cid, "cast", spell_id=free)  # il trucchetto non usa slot


async def test_bewitching_magic_authorises_one_misty_step_without_a_slot_or_a_bonus_action(client):
    cid = await _make(client, "archfey", 14)
    charm = await _spell(client, cid, "Sonno", 1, school="enchantment")
    misty = await _misty(client, cid)
    uses = (await _ability(client, cid, STEPS))["uses"]
    assert (await _cast(client, cid, charm, slot_level=await _level(client, cid), options=[BEWITCH])).status_code == 200
    assert "bewitching_magic" in _states(await _full(client, cid))
    before = sum(s["available"] for s in (await _full(client, cid))["spell_slots"])
    r = await _cast(client, cid, misty, free_cast=True)
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    assert sum(s["available"] for s in full["spell_slots"]) == before and "bewitching_magic" not in _states(full)
    assert (await _turn(client, cid))["bonus_used"] is False and (await _ability(client, cid, STEPS))["uses"] == uses


# ---------------------------------------------------------------------------
# Patrono Celestiale
# ---------------------------------------------------------------------------

LIGHT, SOUL, RESILIENCE_C, VENGEANCE = P + "healing_light", P + "radiant_soul", P + "celestial_resilience", P + "searing_vengeance"


@pytest.mark.parametrize("level", [3, 5, 12])
async def test_healing_light_pool_is_one_plus_the_warlock_level(client, level):
    row = await _ability(client, await _make(client, "celestial", level), LIGHT)
    assert row["max_uses"] == 1 + level and row["restoration_type"] == "long_rest"


async def test_healing_light_spends_up_to_charisma_dice_and_heals_the_rolled_total(client, monkeypatch):
    cid = await _make(client, "celestial", 5, charisma=16)  # +3
    await _hp(client, cid, op="set_max", value=60)
    await _hp(client, cid, op="set_current", value=10)
    monkeypatch.setattr("random.randint", lambda _a, b: min(4, b))
    assert (await _use(client, cid, LIGHT, amount=4, params={"mode": "self"})).status_code == 409  # oltre il Carisma
    r = await _use(client, cid, LIGHT, amount=3, params={"mode": "self"})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["current_hit_points"] == 10 + 12 and (await _ability(client, cid, LIGHT))["uses"] == 6 - 3
    assert (await _turn(client, cid))["bonus_used"] is True
    await _new_turn(client, cid)
    assert (await _use(client, cid, LIGHT, amount=1, params={"mode": "self"})).status_code == 200


async def test_healing_light_dice_minimum_is_one_with_a_low_charisma(client, monkeypatch):
    cid = await _make(client, "celestial", 4, charisma=8)
    await _hp(client, cid, op="set_max", value=60)
    await _hp(client, cid, op="set_current", value=10)
    monkeypatch.setattr("random.randint", lambda _a, b: min(5, b))
    assert (await _use(client, cid, LIGHT, amount=2, params={"mode": "self"})).status_code == 409
    assert (await _use(client, cid, LIGHT, amount=1, params={"mode": "self"})).status_code == 200
    assert (await _full(client, cid))["current_hit_points"] == 15


async def test_radiant_soul_resists_radiant_and_adds_charisma_to_radiant_or_fire_spell_damage_once_per_turn(client):
    cid = await _make(client, "celestial", 6, charisma=16)
    await _hp(client, cid, op="set_max", value=100)
    await _hp(client, cid, op="set_current", value=100)
    assert (await _hp(client, cid, op="damage", value=10, damage_type="radiant"))["current_hit_points"] == 95
    assert (await _hp(client, cid, op="damage", value=10, damage_type="cold"))["current_hit_points"] == 85
    fire = await _spell(client, cid, "Dardo", 1, attack_save="DEX", damage_dice="2d6", damage_type="fire")
    rad = await _spell(client, cid, "Raggio", 1, attack_save="DEX", damage_dice="2d6", damage_type="radiant")
    cold = await _spell(client, cid, "Gelo", 1, attack_save="DEX", damage_dice="2d6", damage_type="cold")
    for sid, expected in ((fire, True), (rad, True), (cold, False)):
        assert (SOUL in await _keys(client, cid, "spell_damage", spell_id=sid)) is expected
    low = await _make(client, "celestial", 5)
    assert SOUL not in await _keys(client, low, "spell_damage", spell_id=await _spell(client, low, "Dardo", 1, attack_save="DEX", damage_dice="2d6", damage_type="fire"))


async def test_celestial_resilience_gives_level_plus_charisma_temporary_points_at_each_rest(client):
    cid = await _make(client, "celestial", 10, charisma=16)
    assert (await _full(client, cid))["temp_hp"] == 0
    await _rest(client, cid, "short")
    assert (await _full(client, cid))["temp_hp"] == 10 + 3
    await _hp(client, cid, op="set_temp", value=20)
    await _rest(client, cid, "short")
    assert (await _full(client, cid))["temp_hp"] == 20  # i PF temporanei non si sommano
    await _rest(client, cid, "long")
    assert (await _full(client, cid))["temp_hp"] == 13
    low = await _make(client, "celestial", 9, charisma=16)
    await _rest(client, low, "short")
    assert (await _full(client, low))["temp_hp"] == 0


async def test_celestial_resilience_also_triggers_with_magical_cunning_and_tells_the_ally_value(client):
    cid = await _make(client, "celestial", 10, charisma=16)
    slot = (await _pact_slots(client, cid))[0]
    await client.patch(f"/characters/{cid}/spell_slots/{slot['id']}", json={"used": 1})
    r = await _use(client, cid, P + "magical_cunning")
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["temp_hp"] == 13
    assert "8" in r.json()["message"]["it"]  # fino a cinque creature: metà livello (5) + Carisma (3)


async def test_searing_vengeance_raises_a_dying_warlock_to_half_hp_and_blinds_the_chosen_creatures(client):
    cid = await _make(client, "celestial", 14, charisma=16)
    await _hp(client, cid, op="set_max", value=80)
    assert (await _use(client, cid, VENGEANCE, params={"mode": "self"})).status_code == 409  # non è a 0 PF
    await _hp(client, cid, op="set_current", value=0)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"prone": True}})
    r = await _use(client, cid, VENGEANCE, params={"mode": "self"})
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    assert full["current_hit_points"] == 40 and not full["conditions"].get("prone")
    effect = await _effect(client, cid, VENGEANCE)
    assert effect["condition"] == "blinded" and effect["damage_dice"] == "2d8+3" and effect["rounds"] == 1
    assert (await _ability(client, cid, VENGEANCE))["uses"] == 0
    assert (await _use(client, cid, VENGEANCE, params={"mode": "self"})).status_code == 409


async def test_searing_vengeance_for_an_ally_reports_the_outcome_without_touching_my_points(client):
    cid = await _make(client, "celestial", 14)
    await _hp(client, cid, op="set_max", value=80)
    before = (await _full(client, cid))["current_hit_points"]
    r = await _use(client, cid, VENGEANCE, params={"mode": "ally"})
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["current_hit_points"] == before and "metà" in r.json()["message"]["it"]


async def test_searing_vengeance_2_ally_heals_half_the_effective_max_not_the_base(client, test_session_factory):
    from sqlalchemy import select
    from core.db.models import Character, SessionParticipant
    from tests.integration._encounter_helpers import GM_ID, as_user, seed_session
    _, hero = await seed_session(test_session_factory)
    as_user(GM_ID)
    cid = await _make(client, "celestial", 14)
    await _hp(client, cid, op="set_max", value=80)
    async with test_session_factory() as s:
        part = (await s.execute(select(SessionParticipant).where(SessionParticipant.user_id == GM_ID))).scalar_one()
        part.character_id = cid
        char = await s.get(Character, hero)
        char.hit_points, char.current_hit_points, char.conditions = 80, 0, {"exhaustion": 4}  # 2014: il massimo effettivo si dimezza a 40, la metà è 20
        await s.commit()
    r = await _use(client, cid, VENGEANCE, params={"mode": "ally", "target_character_id": hero})
    assert r.status_code == 200, r.text
    assert r.json()["received"] == {"name": "Eroe", "healed": 20}  # metà del massimo effettivo (20), non di quello di base (40)


# ---------------------------------------------------------------------------
# Patrono Immondo
# ---------------------------------------------------------------------------

BLESSING, LUCK, RESILIENCE_F, HURL = P + "dark_ones_blessing", P + "dark_ones_own_luck", P + "fiendish_resilience", P + "hurl_through_hell"


@pytest.mark.parametrize("level,charisma,expected", [(3, 16, 6), (10, 16, 13), (4, 1, 1)])
async def test_dark_ones_blessing_gives_charisma_plus_level_temporary_points_and_at_least_one(client, level, charisma, expected):
    cid = await _make(client, "fiend", level, charisma=charisma)
    r = await _use(client, cid, BLESSING)
    assert r.status_code == 200, r.text
    assert r.json()["temp_hp"] == expected and (await _full(client, cid))["temp_hp"] == expected
    assert (await _turn(client, cid))["action_used"] is False


@pytest.mark.parametrize("charisma,uses", [(18, 4), (8, 1)])
async def test_dark_ones_own_luck_uses_are_charisma_with_a_minimum_of_one(client, charisma, uses):
    row = await _ability(client, await _make(client, "fiend", 6, charisma=charisma), LUCK)
    assert row["max_uses"] == uses and row["restoration_type"] == "long_rest"


def test_dark_ones_own_luck_covers_every_d20_test_that_is_a_check_or_a_save():
    spec = {f.key: f for f in features_for("2024", "warlock")}[LUCK]
    option = spec.roll_options[0]
    assert option.phase == "after_roll" and option.after == "add" and "attack" not in option.rolls
    assert {"skill", "ability", "save", "death_save", "initiative"} <= set(option.rolls)


async def test_dark_ones_own_luck_adds_1d10_after_the_roll_and_spends_a_use(client):
    cid = await _make(client, "fiend", 6, charisma=16)
    first = (await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": 5})).json()
    options = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "save", "ability": "wisdom"})).json()
    assert next(o for o in options if o["key"] == LUCK)["phase"] == "after_roll"
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [LUCK]})
    assert r.status_code == 200, r.text
    extra = r.json()["option_result"]
    assert len(extra["extra_rolls"]) == 1 and 1 <= extra["extra_total"] <= 10 and r.json()["total"] == first["total"] + extra["extra_total"]
    assert (await _ability(client, cid, LUCK))["uses"] == 2


async def test_fiendish_resilience_is_a_resistance_to_any_type_but_force_with_no_magical_weapon_exception(client):
    cid = await _make(client, "fiend", 10)
    await _hp(client, cid, op="set_max", value=100)
    await _hp(client, cid, op="set_current", value=100)
    assert (await _use(client, cid, RESILIENCE_F, params={"damage_type": "force"})).status_code == 422
    assert (await _use(client, cid, RESILIENCE_F, params={"damage_type": "slashing"})).status_code == 200
    assert (await _hp(client, cid, op="damage", value=10, damage_type="slashing"))["current_hit_points"] == 95
    assert (await _hp(client, cid, op="damage", value=10, damage_type="acid"))["current_hit_points"] == 85
    assert (await _use(client, cid, RESILIENCE_F, params={"damage_type": "cold"})).status_code == 409  # una scelta per riposo
    await _rest(client, cid, "short")
    assert (await _use(client, cid, RESILIENCE_F, params={"damage_type": "cold"})).status_code == 200
    assert (await _hp(client, cid, op="damage", value=10, damage_type="slashing"))["current_hit_points"] == 75
    assert (await _hp(client, cid, op="damage", value=10, damage_type="cold"))["current_hit_points"] == 70
    assert (await _turn(client, cid))["action_used"] is False


async def _hit(client, cid, sword, *options, **inputs) -> dict:
    r = await client.post(f"/characters/{cid}/items/{sword}/attack", json={"die": 15, "defer_damage": True, "confirm_extra_attack": True})
    assert r.status_code == 200, r.text
    hit = r.json()
    r = await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage", json={"options": list(options), "option_inputs": inputs})
    return r


async def test_hurl_through_hell_asks_a_charisma_save_and_adds_8d10_psychic_unless_a_fiend(client):
    cid = await _make(client, "fiend", 14, charisma=18)
    sword = await _weapon(client, cid, "Spada", "main_hand", damage_dice="1d8")
    keys = await _keys(client, cid, "attack", item_id=sword)
    assert {HURL, HURL + "_fiend", HURL + "_slot", HURL + "_fiend_slot"} <= set(keys)
    r = await _hit(client, cid, sword, HURL)
    assert r.status_code == 200, r.text
    block = r.json()["option_result"]
    assert "8d10" in block["effects"][0]["it"] and block["targets"] == [HURL]
    effect = await _effect(client, cid, HURL)
    assert effect["condition"] == "incapacitated" and effect["save_ability"] == "charisma" and effect["save_dc"] == 8 + 5 + 4
    assert effect["ends_at"] == {"anchor": "source", "edge": "end", "count": 1} and effect["note"] == "hurl_through_hell_2024"
    assert (await _ability(client, cid, HURL))["uses"] == 0
    assert HURL not in await _keys(client, cid, "attack", item_id=sword)


async def test_hurl_through_hell_on_a_fiend_does_no_damage_and_is_once_per_turn(client):
    cid = await _make(client, "fiend", 14)
    sword = await _weapon(client, cid, "Spada", "main_hand", damage_dice="1d8")
    assert (await _hit(client, cid, sword, HURL, HURL + "_fiend")).status_code in (409, 422)  # una sola scelta per colpo
    r = await _hit(client, cid, sword, HURL + "_fiend")
    assert r.status_code == 200, r.text
    assert "Nessun danno" in r.json()["option_result"]["effects"][0]["it"]
    assert not {HURL, HURL + "_slot"} & set(await _keys(client, cid, "attack", item_id=sword))  # una volta per turno


async def test_hurl_through_hell_can_be_restored_with_a_pact_slot_instead_of_the_use(client):
    cid = await _make(client, "fiend", 14)
    sword = await _weapon(client, cid, "Spada", "main_hand", damage_dice="1d8")
    pact = (await _pact_slots(client, cid))[0]
    r = await _hit(client, cid, sword, HURL + "_slot", **{HURL + "_slot": {"slot_level": pact["level"]}})
    assert r.status_code == 200, r.text
    assert (await _pact_slots(client, cid))[0]["used"] == 1 and (await _ability(client, cid, HURL))["uses"] == 1


# ---------------------------------------------------------------------------
# Patrono Grande Antico
# ---------------------------------------------------------------------------

MIND, PSYCHIC, CLAIR, HEX, SHIELD, THRALL = (P + k for k in ("awakened_mind", "psychic_spells", "clairvoyant_combatant", "eldritch_hex", "thought_shield", "create_thrall"))


@pytest.mark.parametrize("level,charisma", [(3, 16), (12, 8)])
async def test_awakened_mind_is_a_bonus_action_lasting_one_minute_per_level(client, level, charisma):
    cid = await _make(client, "great_old_one", level, charisma=charisma)
    r = await _use(client, cid, MIND)
    assert r.status_code == 200, r.text
    assert _states(await _full(client, cid))["awakened_mind"]["rounds_left"] == level * 10 and (await _turn(client, cid))["bonus_used"] is True
    assert str(max(1, (charisma - 10) // 2)) in r.json()["message"]["it"]  # miglia di distanza
    await _new_turn(client, cid)
    assert (await _use(client, cid, MIND)).status_code == 200  # un nuovo legame sostituisce il precedente


async def test_psychic_spells_offer_the_psychic_type_for_a_damaging_spell_that_is_not_psychic(client):
    cid = await _make(client, "great_old_one", 3)
    fire = await _spell(client, cid, "Dardo", 1, attack_save="DEX", damage_dice="2d6", damage_type="fire")
    mind = await _spell(client, cid, "Mente", 1, attack_save="WIS", damage_dice="2d6", damage_type="psychic")
    utility = await _spell(client, cid, "Luce", 1)
    assert PSYCHIC in await _keys(client, cid, "spell_damage", spell_id=fire)
    assert PSYCHIC not in await _keys(client, cid, "spell_damage", spell_id=mind)
    assert PSYCHIC not in await _keys(client, cid, "spell_damage", spell_id=utility)
    low = await _make(client, "archfey", 3)
    assert PSYCHIC not in await _keys(client, low, "spell_damage", spell_id=await _spell(client, low, "Dardo", 1, attack_save="DEX", damage_dice="2d6", damage_type="fire"))


async def test_clairvoyant_combatant_needs_the_awakened_mind_link_and_asks_a_wisdom_save(client):
    cid = await _make(client, "great_old_one", 6, charisma=18)
    assert (await _use(client, cid, CLAIR)).status_code == 409  # nessun legame
    await _use(client, cid, MIND)
    r = await _use(client, cid, CLAIR)
    assert r.status_code == 200, r.text
    effect = await _effect(client, cid, CLAIR)
    assert effect["save_ability"] == "wisdom" and effect["save_dc"] == 8 + 3 + 4 and effect["note"] == "clairvoyant_combatant"
    assert effect["rounds"] == 6 * 10 and (await _ability(client, cid, CLAIR))["uses"] == 0
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, CLAIR))["uses"] == 1


async def test_clairvoyant_combatant_can_be_restored_with_a_pact_slot(client):
    cid = await _make(client, "great_old_one", 6)
    await _use(client, cid, MIND)
    await _use(client, cid, CLAIR)
    pact = (await _pact_slots(client, cid))[0]
    r = await _use(client, cid, CLAIR, params={"restore": True, "slot_level": str(pact["level"])})
    assert r.status_code == 200, r.text
    assert (await _pact_slots(client, cid))[0]["used"] == 1 and (await _ability(client, cid, CLAIR))["uses"] == 0
    assert (await _use(client, cid, CLAIR, params={"restore": True})).status_code == 422  # lo slot va scelto


async def test_eldritch_hex_adds_a_disadvantage_on_the_saves_of_the_chosen_ability(client):
    cid = await _make(client, "great_old_one", 10)
    hex_id = (await _spells_by_index(client, cid))["hex"]["id"]
    keys = await _keys(client, cid, "cast", spell_id=hex_id)
    abilities = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
    assert {f"{HEX}_{a}" for a in abilities} <= set(keys)
    assert not any(k.startswith(HEX) for k in await _keys(client, cid, "cast", spell_id=await _spell(client, cid, "Altro", 1)))
    r = await _cast(client, cid, hex_id, slot_level=await _level(client, cid), options=[f"{HEX}_wisdom"], choices={"ability": "wisdom"})
    assert r.status_code == 200, r.text
    assert (await _effect(client, cid, f"{HEX}_wisdom"))["note"] == "eldritch_hex_wisdom"
    assert (await _cast(client, cid, hex_id, slot_level=await _level(client, cid), options=[f"{HEX}_wisdom", f"{HEX}_strength"], choices={"ability": "wisdom"})).status_code == 409
    low = await _make(client, "great_old_one", 9)
    assert "hex" not in await _spells_by_index(client, low)


async def test_thought_shield_resists_psychic_damage_and_tells_what_to_reflect(client):
    cid = await _make(client, "great_old_one", 10)
    await _hp(client, cid, op="set_max", value=100)
    await _hp(client, cid, op="set_current", value=100)
    assert "warlock.thought_shield_reflection" in await _keys(client, cid, "damage_taken", damage_type="psychic")
    full = await _hp(client, cid, op="damage", value=10, damage_type="psychic", options=["warlock.thought_shield_reflection"])
    assert full["current_hit_points"] == 95
    assert "psichici" in full["option_result"]["effects"][0]["it"]
    low = await _make(client, "great_old_one", 9)
    await _hp(client, low, op="set_max", value=100)
    await _hp(client, low, op="set_current", value=100)
    assert (await _hp(client, low, op="damage", value=10, damage_type="psychic"))["current_hit_points"] == 90


async def test_create_thrall_casts_summon_aberration_without_concentration_and_reports_the_points(client):
    cid = await _make(client, "great_old_one", 14, charisma=16)
    spell = (await _spells_by_index(client, cid))["summon-aberration"]["id"]
    assert THRALL + "_cast" in await _keys(client, cid, "cast", spell_id=spell)
    plain = await _make(client, "great_old_one", 13)
    assert THRALL + "_cast" not in await _keys(client, plain, "cast", spell_id=(await _spells_by_index(client, plain))["summon-aberration"]["id"])
    r = await _cast(client, cid, spell, slot_level=await _level(client, cid), options=[THRALL + "_cast"])
    assert r.status_code == 200, r.text
    effect = r.json()["option_result"]["effects"][0]["it"]
    assert str(14 + 3) in effect and "psichici" in effect
    assert (await _full(client, cid))["concentrating_spell_id"] is None
    await _new_turn(client, cid)
    r = await _cast(client, cid, spell, slot_level=await _level(client, cid))
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["concentrating_spell_id"] == spell


# ---------------------------------------------------------------------------
# Modulo comune toccato
# ---------------------------------------------------------------------------

async def test_spending_a_slot_for_a_pact_only_feature_never_takes_a_normal_slot():
    from api.services.rules_states import _spend_slot

    taken: list[int] = []

    class Session:
        async def execute(self, stmt):
            taken.append(stmt.compile().params["id_1"])
            return SimpleNamespace(rowcount=1)

        async def refresh(self, _row):
            return None

    normal = SimpleNamespace(id=1, level=3, used=0, total=2, is_pact=False)
    pact = SimpleNamespace(id=2, level=3, used=0, total=2, is_pact=True)
    await _spend_slot(Session(), SimpleNamespace(spell_slots=[normal, pact]), 3, pact_only=True)
    await _spend_slot(Session(), SimpleNamespace(spell_slots=[normal, pact]), 3)
    assert taken == [2, 1]  # solo Patto; senza il vincolo prima i normali


def test_every_note_a_patron_uses_has_its_two_translations():
    notes = {"taunting_step", "terrifying_step", "beguiling_defenses", "clairvoyant_combatant", "hurl_through_hell_2024",
             *(f"eldritch_hex_{a}" for a in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"))}
    for lang in ("it", "en"):
        data = json.load(open(f"webapp/src/locales/{lang}.json", encoding="utf-8"))
        have = data["character"]["target_effect"]["notes"]
        assert not notes - set(have), (lang, notes - set(have))
