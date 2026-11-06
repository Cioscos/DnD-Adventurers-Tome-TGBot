"""Chierico 2024 (Task 33, parte A): tabelle, Ordine Divino, Incanalare Divinità (Scintilla Divina, Scacciare Non Morti,
Bruciare Non Morti), Colpi Benedetti, Intervento Divino (anche Superiore) e passaggio da un'edizione all'altra. Valori dalla
scheda ``docs/superpowers/rules/2024/classes/cleric.md``."""
from __future__ import annotations

import pytest
from core.rules.catalog import features_for
from core.rules.proficiencies import class_proficiencies
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_barbarian import _turn, _weapon
from tests.integration.rules.test_2014_bard import _ability, _choice, _full, _keys_of, _resolve, _roll_keys, _states, _use
from tests.integration.rules.test_2014_bard_inspiration import _seat
from tests.integration.rules.test_2014_cleric_domains import _deferred

POOL, SPARK, TURN, DI = "cleric.channel_divinity", "cleric.divine_spark", "cleric.turn_undead", "cleric.divine_intervention"
PREPARED = (4, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16, 16, 17, 17, 18, 18, 19, 20, 21, 22)
CANTRIPS = (3, 3, 3, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5)
SLOTS = {1: (2,), 3: (4, 2), 5: (4, 3, 2), 9: (4, 3, 3, 3, 1), 17: (4, 3, 3, 3, 2, 1, 1, 1, 1), 20: (4, 3, 3, 3, 3, 2, 2, 1, 1)}


async def _cleric24(client, level=5, order=None, **scores) -> int:
    body = {"name": "Chierico", "initial_class": {"class_name": "cleric", "level": level, "subclass": None}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    if order:
        r = await _resolve(client, cid, "divine_order", [order])
        assert r.status_code == 200, r.text
    return cid


async def _table24(client, factory, level=5, **scores):
    sid, hero = await seed_session(factory)
    as_user(GM_ID)
    cleric = await _cleric24(client, level, wisdom=16, **scores)
    await _seat(factory, cleric)
    return sid, cleric, hero


# ---------------------------------------------------------------------------
# Tabelle e catalogo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", range(1, 21))
async def test_cantrips_and_prepared_spells_follow_the_2024_table(client, level):
    cid = await _cleric24(client, level)
    limits = (await _full(client, cid))["spellcasting"]["limits"][0]
    assert (limits["cantrips_limit"], limits["prepared_limit"]) == (CANTRIPS[level - 1], PREPARED[level - 1])


@pytest.mark.parametrize("level", sorted(SLOTS))
async def test_spell_slots_follow_the_full_caster_table(client, level):
    cid = await _cleric24(client, level)
    slots = tuple(s["total"] for s in sorted((await _full(client, cid))["spell_slots"], key=lambda s: s["level"]))
    assert slots == SLOTS[level]


async def test_hit_points_use_the_d8_and_follow_constitution(client):
    cid = await _cleric24(client, 3)
    full = await _full(client, cid)
    assert full["classes"][0]["hit_die"] == 8 and full["hit_points"] == 8 + 5 + 5


def test_class_and_multiclass_proficiencies_from_the_class_table():
    first = class_proficiencies("2024", "cleric", False)
    assert set(first.armor) == {"light", "medium", "shields"} and first.weapons == ("simple",)
    assert set(first.saves) == {"wisdom", "charisma"} and first.skills_count == 2
    multi = class_proficiencies("2024", "cleric", True)
    assert set(multi.armor) == {"light", "medium", "shields"} and not multi.weapons and not multi.saves and not multi.skills_count


@pytest.mark.parametrize("level,asi", [(4, [4]), (16, [4, 8, 12, 16]), (19, [4, 8, 12, 16])])
async def test_asi_choice_is_pending_at_each_asi_level_and_the_19th_is_an_epic_boon(client, level, asi):
    cid = await _cleric24(client, level)
    pending = (await _full(client, cid))["pending_choices"]
    assert sorted(c["level"] for c in pending if c["kind"] == "asi") == asi
    assert [c["level"] for c in pending if c["kind"] == "epic_boon"] == ([19] if level >= 19 else [])


async def test_every_mapping_title_has_its_row_and_rules_only_rows_stay_off_the_sheet(client):
    titles = {f.source_title for f in features_for("2024", "cleric")}
    assert "Ordine Divino: Taumaturgo / Divine Order: Thaumaturge (Chierico 1, pag. 70)" in titles
    cid = await _cleric24(client, 20)
    keys = await _keys_of(client, cid)
    assert not keys & {f"cleric.{k}" for k in ("core_traits", "spellcasting", "cleric_subclass", "ability_score_improvement",
                                                "epic_boon", "multiclassing")}
    assert {POOL, SPARK, TURN, DI} <= keys


# ---------------------------------------------------------------------------
# Ordine Divino
# ---------------------------------------------------------------------------

async def test_the_divine_order_is_a_single_choice_at_level_1(client):
    cid = await _cleric24(client, 1)
    choice = _choice(await _full(client, cid), "divine_order")
    assert choice is not None and choice["count"] == 1
    assert (await _resolve(client, cid, "divine_order", ["protector", "thaumaturge"])).status_code == 422


async def test_protector_adds_martial_weapons_and_heavy_armor(client):
    cid = await _cleric24(client, 1, "protector")
    got = (await _full(client, cid))["general_proficiencies"]
    assert "Armi da guerra" in got["weapons"] and "Armature pesanti" in got["armor"]
    assert _choice(await _full(client, cid), "thaumaturge_cantrip") is None


async def test_thaumaturge_gives_a_free_cantrip_and_wisdom_to_arcana_and_religion(client):
    cid = await _cleric24(client, 1, "thaumaturge", wisdom=16, intelligence=10)
    full = await _full(client, cid)
    assert _choice(full, "thaumaturge_cantrip")["spell_pick"] == {"free": True, "max_level": 0, "list": "cleric"}
    assert "Armature pesanti" not in full["general_proficiencies"]["armor"]
    arcana = (await client.post(f"/characters/{cid}/skills/arcana/roll", json={"die": 10})).json()
    history = (await client.post(f"/characters/{cid}/skills/history/roll", json={"die": 10})).json()
    assert (arcana["bonus"], history["bonus"]) == (3, 0)


async def test_thaumaturge_bonus_is_at_least_plus_one(client):
    cid = await _cleric24(client, 1, "thaumaturge", wisdom=8)
    assert (await client.post(f"/characters/{cid}/skills/religion/roll", json={"die": 10})).json()["bonus"] == 1


# ---------------------------------------------------------------------------
# Incanalare Divinità
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,uses", [(1, None), (2, 2), (5, 2), (6, 3), (17, 3), (18, 4), (20, 4)])
async def test_channel_divinity_uses_follow_the_level(client, level, uses):
    cid = await _cleric24(client, level)
    row = await _ability(client, cid, POOL)
    assert (row["max_uses"] if row else None) == uses
    if row:
        assert row["restoration_type"] == "long_rest"


async def test_a_short_rest_returns_one_use_and_a_long_rest_all_of_them(client):
    cid = await _cleric24(client, 6)
    for _ in range(3):
        await client.post(f"/characters/{cid}/turn/new")
        assert (await _use(client, cid, TURN)).status_code == 200
    assert (await _ability(client, cid, POOL))["uses"] == 0
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert (await _ability(client, cid, POOL))["uses"] == 1
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert (await _ability(client, cid, POOL))["uses"] == 3


@pytest.mark.parametrize("level,dice", [(2, 1), (6, 1), (7, 2), (12, 2), (13, 3), (17, 3), (18, 4)])
async def test_divine_spark_rolls_one_to_four_d8_by_level(client, level, dice):
    cid = await _cleric24(client, level, wisdom=16)
    r = await _use(client, cid, SPARK, params={"mode": "damage_radiant"})
    assert r.status_code == 200, r.text
    assert len(r.json()["rolls"]) == dice and all(1 <= v <= 8 for v in r.json()["rolls"])


async def test_divine_spark_damage_asks_a_constitution_save_with_the_spell_dc(client, monkeypatch):
    monkeypatch.setattr("api.services.rules_states.random.randint", lambda a, b: 5)
    cid = await _cleric24(client, 2, wisdom=16)  # competenza +2, Saggezza +3
    r = await _use(client, cid, SPARK, params={"mode": "damage_necrotic"})
    assert r.status_code == 200, r.text
    data = r.json()["state"]["data"]
    assert (data["dc"], data["save"], data["damage"], data["damage_type"]) == (8 + 2 + 3, "constitution", 8, "necrotic")
    assert "TS Costituzione (CD 13)" in r.json()["message"]["it"] and "8 danni necrotici" in r.json()["message"]["it"]
    assert (await _ability(client, cid, POOL))["uses"] == 1 and (await _turn(client, cid))["action_used"] is True


async def test_divine_spark_needs_a_listed_mode_and_a_free_action(client):
    cid = await _cleric24(client, 2)
    assert (await _use(client, cid, SPARK, params={"mode": "wish"})).status_code == 422
    assert (await _use(client, cid, SPARK)).status_code == 422
    assert (await _ability(client, cid, POOL))["uses"] == 2
    assert (await _use(client, cid, SPARK, params={"mode": "heal"})).status_code == 200
    again = await _use(client, cid, SPARK, params={"mode": "heal"})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"


async def test_divine_spark_heals_an_ally_of_the_evening_with_dice_plus_wisdom(client, test_session_factory, monkeypatch):
    monkeypatch.setattr("api.services.rules_states.random.randint", lambda a, b: 4)
    sid, cleric, hero = await _table24(client, test_session_factory, 2)  # Saggezza +3
    as_user(PLAYER_ID)
    assert (await client.patch(f"/characters/{hero}/hp", json={"op": "set_max", "value": 40})).status_code == 200
    assert (await client.patch(f"/characters/{hero}/hp", json={"op": "set_current", "value": 5})).status_code == 200
    as_user(GM_ID)
    r = await _use(client, cleric, SPARK, params={"mode": "heal", "target_character_id": hero})
    assert r.status_code == 200, r.text
    assert r.json()["received"]["healed"] == 4 + 3 and r.json()["healed"] == 0
    as_user(PLAYER_ID)
    assert (await _full(client, hero))["current_hit_points"] == 5 + 7


async def test_divine_spark_heal_outside_the_evening_is_reported_to_the_gm(client, monkeypatch):
    monkeypatch.setattr("api.services.rules_states.random.randint", lambda a, b: 4)
    cid = await _cleric24(client, 2, wisdom=16)
    r = await _use(client, cid, SPARK, params={"mode": "heal"})
    assert r.json()["given"] == 7 and r.json()["state"] is None


async def test_turn_undead_shows_the_save_and_applies_frightened_and_incapacitated_for_a_minute(client):
    cid = await _cleric24(client, 4, wisdom=16)
    r = await _use(client, cid, TURN)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["targets"] == [TURN] and body["rolls"] == []
    data = body["state"]["data"]
    assert (data["dc"], data["save"]) == (8 + 2 + 3, "wisdom") and "damage" not in data
    assert body["state"]["rounds_left"] == 10 and set(body["state"]["ends_on"]) == {"incapacitated", "manual"}
    effect = (await client.get(f"/characters/{cid}/target-effects/{TURN}")).json()["result"]
    assert effect["condition"] == "frightened" and effect["also"] == ["incapacitated"] and effect["rounds"] == 10
    assert (await _ability(client, cid, POOL))["uses"] == 1


@pytest.mark.parametrize("wisdom,dice", [(8, 1), (10, 1), (14, 2), (20, 5)])
async def test_sear_undead_rolls_wisdom_d8_at_level_5_with_a_minimum_of_one(client, wisdom, dice):
    cid = await _cleric24(client, 5, wisdom=wisdom)
    body = (await _use(client, cid, TURN)).json()
    assert len(body["rolls"]) == dice
    assert body["state"]["data"]["damage"] == sum(body["rolls"]) and body["state"]["data"]["damage_type"] == "radiant"
    assert "radiosi" in body["message"]["it"]


async def test_turn_undead_is_refused_without_uses_and_keeps_the_action(client):
    cid = await _cleric24(client, 2)
    assert (await _use(client, cid, TURN)).status_code == 200
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "action", "used": False})
    assert (await _use(client, cid, TURN)).status_code == 200
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "action", "used": False})
    r = await _use(client, cid, TURN)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_uses"
    assert (await _turn(client, cid))["action_used"] is False


# ---------------------------------------------------------------------------
# Riserva condivisa (la riuserà il Paladino 2024)
# ---------------------------------------------------------------------------

def _paladin_pool_spec(level):
    from core.rules.types import FeatureSpec, Uses
    return FeatureSpec(key="paladin.channel_divinity", class_key="paladin", edition="2024", level=level, source_title="prova",
                       name={"it": "x", "en": "x"}, summary={"it": "x", "en": "x"}, action_type="action",
                       uses=Uses(table={level: 1}), restoration="short_rest", shared_pool="channel_divinity")


@pytest.mark.parametrize("cleric_first", [True, False])
async def test_channel_divinity_is_one_pool_in_both_multiclass_orders(client, cleric_first):
    from core.rules.types import FeatureSpec  # noqa: F401  (il registro è quello vero: la riga di prova si aggiunge)
    from core.rules import catalog
    catalog._REGISTRY[("2024", "paladin")] = (_paladin_pool_spec(3),)
    try:
        first, second = ("cleric", "paladin") if cleric_first else ("paladin", "cleric")
        r = await client.post("/characters", json={"name": "Mix", "initial_class": {"class_name": first, "level": 5, "subclass": None}})
        cid = r.json()["id"]
        assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
        r = await client.post(f"/characters/{cid}/classes", json={"class_name": second, "level": 5, "hit_die": 8})
        assert r.status_code == 201, r.text
        rows = [a for a in (await _full(client, cid))["abilities"] if a["feature_key"] in (POOL, "paladin.channel_divinity")]
        assert len(rows) == 1 and rows[0]["feature_key"] == POOL and rows[0]["max_uses"] == 2  # la classe che ne dà di più
        assert (await _use(client, cid, TURN)).status_code == 200
        assert (await _ability(client, cid, POOL))["uses"] == 1
    finally:
        catalog._REGISTRY.pop(("2024", "paladin"), None)


# ---------------------------------------------------------------------------
# Colpi Benedetti
# ---------------------------------------------------------------------------

async def test_blessed_strikes_is_a_choice_at_level_7(client):
    assert _choice(await _full(client, await _cleric24(client, 6)), "blessed_strikes") is None
    cid = await _cleric24(client, 7)
    assert _choice(await _full(client, cid), "blessed_strikes")["count"] == 1
    assert {"cleric.blessed_strikes_divine_strike", "cleric.blessed_strikes_potent"}.isdisjoint(await _keys_of(client, cid))


async def test_divine_strike_offers_necrotic_or_radiant_once_per_turn(client):
    cid = await _cleric24(client, 7, strength=14)
    await _resolve(client, cid, "blessed_strikes", ["divine_strike"])
    sword = await _weapon(client, cid, "Mazza", damage_dice="1d6")
    keys = await _roll_keys(client, cid, "attack", item_id=sword)
    nec, rad = "cleric.divine_strike_blessed_necrotic", "cleric.divine_strike_blessed_radiant"
    assert {nec, rad} <= set(keys)
    hit = await _deferred(client, cid, sword, 15, rad)
    assert hit["option_result"] is not None
    after = await _roll_keys(client, cid, "attack", item_id=sword)
    assert nec not in after and rad not in after  # una sola volta per turno, qualunque sia il tipo


async def test_divine_strike_is_2d8_from_level_14_and_not_offered_with_the_other_choice(client):
    from core.rules.catalog.y2014.cleric import _strike_dice
    from core.rules.types import RuleContext
    assert _strike_dice(RuleContext(char=None, edition="2024", class_level=13), {}) == "1d8"
    assert _strike_dice(RuleContext(char=None, edition="2024", class_level=14), {}) == "2d8"
    cid = await _cleric24(client, 7, strength=14)
    await _resolve(client, cid, "blessed_strikes", ["potent_spellcasting"])
    sword = await _weapon(client, cid, "Mazza", damage_dice="1d6")
    assert not any(k.startswith("cleric.divine_strike") for k in await _roll_keys(client, cid, "attack", item_id=sword))


async def _cantrip(client, cid) -> int:
    row = (await _full(client, cid))["classes"][0]["id"]
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Fiamma sacra", "level": 0, "damage_dice": "1d8",
                                                             "damage_type": "radiant", "class_id": row})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_potent_spellcasting_adds_wisdom_to_a_cleric_cantrip(client):
    cid = await _cleric24(client, 7, wisdom=16)
    await _resolve(client, cid, "blessed_strikes", ["potent_spellcasting"])
    cantrip = await _cantrip(client, cid)
    r = await client.post(f"/characters/{cid}/spells/{cantrip}/roll_damage", json={"main_rolls": [4, 3]})  # 2 dadi dal 5°
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 4 + 3 + 3


async def test_a_divine_strike_cleric_gets_no_wisdom_on_cantrips(client):
    cid = await _cleric24(client, 7, wisdom=16)
    await _resolve(client, cid, "blessed_strikes", ["divine_strike"])
    cantrip = await _cantrip(client, cid)
    assert (await client.post(f"/characters/{cid}/spells/{cantrip}/roll_damage", json={"main_rolls": [4, 3]})).json()["total"] == 7


async def test_improved_potent_spellcasting_offers_twice_wisdom_as_temporary_hp_from_level_14(client):
    low = await _cleric24(client, 13, wisdom=16)
    await _resolve(client, low, "blessed_strikes", ["potent_spellcasting"])
    cid = await _cleric24(client, 14, wisdom=16)
    await _resolve(client, cid, "blessed_strikes", ["potent_spellcasting"])
    key = "cleric.improved_potent_spellcasting"
    spell = await _cantrip(client, cid)
    assert key in await _roll_keys(client, cid, "spell_damage", spell_id=spell)
    assert key not in await _roll_keys(client, low, "spell_damage", spell_id=await _cantrip(client, low))
    other = await _cleric24(client, 14, wisdom=16)
    await _resolve(client, other, "blessed_strikes", ["divine_strike"])
    assert key not in await _roll_keys(client, other, "spell_damage", spell_id=await _cantrip(client, other))


# ---------------------------------------------------------------------------
# Intervento Divino
# ---------------------------------------------------------------------------

async def test_divine_intervention_casts_a_cleric_spell_for_free_once_per_long_rest(client):
    cid = await _cleric24(client, 10, wisdom=16)
    r = await _use(client, cid, DI, params={"spell": "Cura ferite di massa", "spell_level": "5"})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, DI))["uses"] == 0 and (await _turn(client, cid))["action_used"] is False
    spell = next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["name"] == "Cura ferite di massa")
    assert spell["level"] == 5 and spell["always_prepared"] is True
    again = await _use(client, cid, DI, params={"spell": "X", "spell_level": "1"})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "no_uses"
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"free_cast": True})
    assert r.status_code == 200, r.text
    assert all(s["total"] - s["used"] == s["total"] for s in (await _full(client, cid))["spell_slots"])  # nessuno slot speso
    assert not any(s["name"] == "Cura ferite di massa" for s in (await client.get(f"/characters/{cid}/spells")).json())
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert (await _ability(client, cid, DI))["uses"] == 1


async def test_divine_intervention_needs_a_name_and_a_level_up_to_five_and_is_absent_before_level_10(client):
    cid = await _cleric24(client, 10)
    for params in ({}, {"spell": "Palla di fuoco"}, {"spell_level": "3"}, {"spell": "Parola del potere", "spell_level": "6"},
                   {"spell": " ", "spell_level": "3"}, {"wish": True}):
        r = await _use(client, cid, DI, params=params)
        assert r.status_code in (422,), (params, r.text)
    assert (await _ability(client, cid, DI))["uses"] == 1
    assert DI not in await _keys_of(client, await _cleric24(client, 9))


async def test_wish_blocks_divine_intervention_for_2d4_long_rests_and_counts_them_down(client, monkeypatch):
    monkeypatch.setattr("core.rules.catalog.y2024.cleric.random.randint", lambda a, b: 1)
    cid = await _cleric24(client, 20, wisdom=16)
    r = await _use(client, cid, DI, params={"wish": True})
    assert r.status_code == 200, r.text
    lock = next(s for s in await _states(client, cid) if s["key"] == "greater_divine_intervention")
    assert lock["data"] == {"roll": [1, 1], "rests_left": 2}
    spell = next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["level"] == 9)
    assert spell["name"] == "Desiderio"
    for expected_locked in (True, False):
        await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
        r = await _use(client, cid, DI, params={"spell": "Cura ferite", "spell_level": "1"})
        assert (r.status_code == 409) is expected_locked, r.text
        if expected_locked:
            assert r.json()["detail"]["code"] == "feature_unavailable"
            assert next(s for s in await _states(client, cid) if s["key"] == "greater_divine_intervention")["data"]["rests_left"] == 1


async def test_wish_is_not_available_before_level_20_and_a_normal_spell_does_not_lock(client):
    cid = await _cleric24(client, 19)
    assert (await _use(client, cid, DI, params={"wish": True})).status_code == 422
    assert (await _use(client, cid, DI, params={"spell": "Rianimare morti", "spell_level": "5"})).status_code == 200
    assert not any(s["key"] == "greater_divine_intervention" for s in await _states(client, cid))


# ---------------------------------------------------------------------------
# Passaggio dal 2014 al 2024
# ---------------------------------------------------------------------------

async def test_a_2014_cleric_that_becomes_2024_gets_the_2024_rows_and_keeps_its_spent_uses(client):
    body = {"name": "Chierico", "initial_class": {"class_name": "cleric", "level": 8, "subclass": None}}
    cid = (await client.post("/characters", json=body)).json()["id"]
    keys14 = await _keys_of(client, cid)
    assert {POOL, TURN, "cleric.destroy_undead"} <= keys14 and DI not in keys14 and SPARK not in keys14
    assert (await _ability(client, cid, POOL))["max_uses"] == 2
    assert (await _use(client, cid, TURN)).status_code == 200
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    keys24 = await _keys_of(client, cid)
    assert "cleric.destroy_undead" not in keys24 and {POOL, SPARK, TURN, "cleric.sear_undead", "cleric.divine_order"} <= keys24
    assert (await _ability(client, cid, POOL))["max_uses"] == 3 and (await _ability(client, cid, POOL))["uses"] == 2
    assert [c["group"] for c in (await _full(client, cid))["pending_choices"] if c["kind"] == "class_option"] == ["divine_order", "blessed_strikes"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2014"})).status_code == 200
    keys_back = await _keys_of(client, cid)
    assert "cleric.destroy_undead" in keys_back and SPARK not in keys_back
    assert (await _ability(client, cid, POOL))["max_uses"] == 2 and (await _ability(client, cid, POOL))["uses"] == 1


async def test_a_2014_domain_without_a_2024_twin_keeps_its_text_and_its_rows(client):
    body = {"name": "Chierico", "initial_class": {"class_name": "cleric", "level": 3, "subclass": "Dominio della Conoscenza"}}
    cid = (await client.post("/characters", json=body)).json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    full = await _full(client, cid)
    assert full["classes"][0]["subclass"] == "Dominio della Conoscenza"
    # sottoclasse non riconosciuta nel 2024: nessuna perdita, le righe restano (feature_sync) e il Conoscenza non si trasforma
    assert "cleric.knowledge_spells" in await _keys_of(client, cid)
