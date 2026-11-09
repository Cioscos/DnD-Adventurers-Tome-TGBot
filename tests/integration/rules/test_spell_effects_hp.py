"""Effetti degli incantesimi sui PF: CA impostata, PF temporanei, Aiuto, Interdizione alla Morte, Legame di Protezione, cure nel tempo."""
from __future__ import annotations

import pytest

from core.rules.catalog.spells import spell_effect
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
from tests.integration.rules.test_spell_effects_cast import _full
from tests.integration.rules.test_spell_effects_defenses import _cast, _hit, _sheet, _table
from tests.integration.test_magic_items import _item

DEATH_WARD = "spell:death_ward:hold"


def _max_dice(monkeypatch) -> None:
    monkeypatch.setattr("core.rules.spell_effects.random.randint", lambda _a, b: b)


async def _hp(client, cid, current, maximum=None, user=GM_ID) -> None:
    as_user(user)
    if maximum is not None:
        assert (await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": maximum})).status_code == 200
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": current})).status_code == 200


async def _states(client, cid, key, user=PLAYER_ID) -> list[dict]:
    return [s for s in (await _sheet(client, cid, user))["active_states"] or [] if s["key"] == key]


async def _new_turn(client, cid, user=PLAYER_ID) -> None:
    as_user(user)
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200


# --- catalogo -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("srd", ["mage-armor", "barkskin", "armor-of-agathys", "false-life", "death-ward", "warding-bond",
                                 "regenerate", "aura-of-vitality"])
@pytest.mark.parametrize("edition", ["2014", "2024"])
def test_hit_point_spells_are_in_both_editions(edition, srd):
    assert spell_effect(edition, srd) is not None


def test_power_word_fortify_is_2024_only():
    assert spell_effect("2014", "power-word-fortify") is None and spell_effect("2024", "power-word-fortify") is not None


def test_aura_of_life_heals_one_hp_only_at_zero():
    _, variant = spell_effect("2014", "aura-of-life")
    zero, up = type("C", (), {"current_hit_points": 0, "is_dead": False}), type("C", (), {"current_hit_points": 5, "is_dead": False})
    assert variant.turn_heal({}, zero) == 1 and variant.turn_heal({}, up) == 0


# --- CA impostata ---------------------------------------------------------------------------------------------------

async def test_mage_armor_sets_base_ac_13_plus_dex_only_without_armor(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Mage Armor", "mage-armor", 1)
    assert (await _sheet(client, hero))["ac"] == 13  # DES 16 senza armatura: 10 + 3
    await _cast(client, caster, spell, [hero], level=1)
    assert (await _sheet(client, hero))["ac"] == 16  # 13 + 3


async def test_mage_armor_does_nothing_with_armor_on(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Mage Armor", "mage-armor", 1)
    as_user(PLAYER_ID)
    await _item(client, hero, "Cotta di maglia", item_type="armor", slot="body", base_ac=16)
    before = (await _sheet(client, hero))["ac"]
    await _cast(client, caster, spell, [hero], level=1)
    assert (await _sheet(client, hero))["ac"] == before


async def test_mage_armor_does_not_break_the_character_list_nor_the_live_session(client, test_session_factory):
    """C1: la CA con Armatura Magica si calcola anche in home e in serata, dove i dati non sono tutti caricati."""
    hero, caster, spell = await _table(client, test_session_factory, "Mage Armor", "mage-armor", 1)
    await _cast(client, caster, spell, [hero], level=1)
    as_user(PLAYER_ID)
    listed = await client.get("/characters")
    assert listed.status_code == 200, listed.text
    assert next(c for c in listed.json() if c["id"] == hero)["ac"] == 16
    as_user(GM_ID)
    live = await client.get("/sessions/1/live")
    assert live.status_code == 200, live.text
    assert next(c for c in live.json()["live_characters"] if c["id"] == hero)["ac"] == 16


async def test_mage_armor_is_not_listed_among_the_sources_of_other_rolls(client, test_session_factory):
    """M1: compare solo nella CA."""
    hero, caster, spell = await _table(client, test_session_factory, "Mage Armor", "mage-armor", 1)
    await _cast(client, caster, spell, [hero], level=1)
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from core.db.models import Character
    from core.rules.modifiers import modifiers_for
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == hero).options(
            selectinload(Character.items), selectinload(Character.classes), selectinload(Character.ability_scores)))).scalar_one()
        assert "spell:mage_armor" not in modifiers_for(char, "strength_check").notes


@pytest.mark.parametrize("edition,floor", [("2014", 16), ("2024", 17)])
async def test_barkskin_sets_a_minimum_ac(client, test_session_factory, edition, floor):
    hero, caster, spell = await _table(client, test_session_factory, "Barkskin", "barkskin", 2, hero_edition=edition, caster_edition=edition)
    await _cast(client, caster, spell, [hero], level=2)
    assert (await _sheet(client, hero))["ac"] == floor


@pytest.mark.parametrize("edition,floor", [("2014", 16), ("2024", 17)])
async def test_barkskin_floor_applies_to_the_final_ac_including_item_bonuses(client, test_session_factory, edition, floor):
    """I2: base 10 + DES 3 = 13 più un anello +1 = 14: il minimo porta il totale a ``floor``, non a ``floor`` + 1."""
    hero, caster, spell = await _table(client, test_session_factory, "Barkskin", "barkskin", 2, hero_edition=edition, caster_edition=edition)
    as_user(PLAYER_ID)
    await _item(client, hero, "Anello", slot="ring1", is_magic=True, bonuses=[{"target": "ac", "value": 1}])
    await _cast(client, caster, spell, [hero], level=2)
    sheet = await _sheet(client, hero)
    assert sheet["ac"] + sheet["ac_breakdown"]["items"] + sheet["ac_breakdown"]["homebrew"] == floor
    listed = next(c for c in (await client.get("/characters")).json() if c["id"] == hero)
    assert listed["ac"] + listed["ac_items_modifier"] + listed["ac_homebrew_modifier"] == floor


# --- PF temporanei -------------------------------------------------------------------------------------------------

async def test_false_life_2014_gives_1d4_plus_4_plus_5_per_slot_and_the_higher_temp_hp_wins(client, test_session_factory, monkeypatch):
    _max_dice(monkeypatch)
    hero, caster, spell = await _table(client, test_session_factory, "False Life", "false-life", 2)
    await _hp(client, caster, 20, 20)
    await _cast(client, caster, spell, [], level=2)
    assert (await _sheet(client, caster, GM_ID))["temp_hp"] == 13  # 4 + 4 + 5
    await client.patch(f"/characters/{caster}/hp", json={"op": "set_temp", "value": 30})
    await _cast(client, caster, spell, [], level=2)
    assert (await _sheet(client, caster, GM_ID))["temp_hp"] == 30  # non si sommano: resta il maggiore


async def test_false_life_2024_is_instant_2d4_plus_4_and_leaves_no_state(client, test_session_factory, monkeypatch):
    _max_dice(monkeypatch)
    hero, caster, spell = await _table(client, test_session_factory, "False Life", "false-life", 1, caster_edition="2024")
    await _cast(client, caster, spell, [], level=1)
    sheet = await _sheet(client, caster, GM_ID)
    assert sheet["temp_hp"] == 12 and not [s for s in sheet["active_states"] or [] if s["key"].startswith("spell")]


async def test_enhance_ability_2014_constitution_gives_2d6_temp_hp(client, test_session_factory, monkeypatch):
    _max_dice(monkeypatch)
    hero, caster, spell = await _table(client, test_session_factory, "Enhance Ability", "enhance-ability", 2)
    await _cast(client, caster, spell, [hero], level=2, choices={"ability": "constitution"})
    assert (await _sheet(client, hero))["temp_hp"] == 12


async def test_power_word_fortify_splits_120_temp_hp(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Power Word Fortify", "power-word-fortify", 7,
                                       hero_edition="2024", caster_edition="2024")
    await _cast(client, caster, spell, [hero, caster], level=7)
    assert (await _sheet(client, hero))["temp_hp"] == 60 and (await _sheet(client, caster, GM_ID))["temp_hp"] == 60


async def test_armor_of_agathys_2014_keeps_the_spell_and_reminds_the_retaliation(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Armor of Agathys", "armor-of-agathys", 2)
    await _hp(client, caster, 30, 30)
    await _cast(client, caster, spell, [], level=2)
    assert (await _sheet(client, caster, GM_ID))["temp_hp"] == 10
    r = await client.patch(f"/characters/{caster}/hp", json={"op": "damage", "value": 10, "damage_type": "slashing"})
    note = " ".join(n["message"] for n in r.json()["homebrew_notifications"])
    assert "10 danni da freddo" in note
    assert len(await _states(client, caster, "spell:armor_of_agathys", GM_ID)) == 1  # 2014: l'incantesimo non finisce
    r = await client.patch(f"/characters/{caster}/hp", json={"op": "damage", "value": 3, "damage_type": "slashing"})
    assert not r.json().get("homebrew_notifications")  # senza PF temporanei niente ritorsione


async def test_armor_of_agathys_2024_ends_when_the_temp_hp_are_gone(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Armor of Agathys", "armor-of-agathys", 1, caster_edition="2024")
    await _hp(client, caster, 30, 30)
    await _cast(client, caster, spell, [], level=1)
    as_user(GM_ID)
    await client.patch(f"/characters/{caster}/hp", json={"op": "damage", "value": 3, "damage_type": "slashing"})
    assert len(await _states(client, caster, "spell:armor_of_agathys", GM_ID)) == 1  # restano 2 PF temporanei
    await client.patch(f"/characters/{caster}/hp", json={"op": "damage", "value": 5, "damage_type": "slashing"})
    assert await _states(client, caster, "spell:armor_of_agathys", GM_ID) == []
    assert await _states(client, caster, "spell_cast:armor_of_agathys", GM_ID) == []


async def test_fire_shield_reminds_the_retaliation_on_every_damage(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Fire Shield", "fire-shield", 4)
    await _hp(client, caster, 30, 30)
    await _cast(client, caster, spell, [], level=4, choices={"shield": "warm"})
    r = await client.patch(f"/characters/{caster}/hp", json={"op": "damage", "value": 4, "damage_type": "slashing"})
    assert "2d8 danni da fuoco" in r.json()["homebrew_notifications"][0]["message"]


async def test_heroism_gives_temp_hp_equal_to_the_casters_modifier_at_the_start_of_each_turn(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Heroism", "heroism", 1)
    as_user(GM_ID)
    assert (await client.post(f"/characters/{caster}/classes", json={"class_name": "bard", "level": 3, "hit_die": 8})).status_code == 201
    assert (await client.patch(f"/characters/{caster}/ability_scores/charisma", json={"value": 16})).status_code == 200
    await _cast(client, caster, spell, [hero], level=1)
    assert (await _sheet(client, hero))["temp_hp"] == 0  # a inizio turno, non al lancio
    await _new_turn(client, hero)
    assert (await _sheet(client, hero))["temp_hp"] == 3
    await client.patch(f"/characters/{hero}/hp", json={"op": "set_temp", "value": 1})
    await _new_turn(client, hero)
    assert (await _sheet(client, hero))["temp_hp"] == 3  # non si sommano


async def test_undoing_the_turn_advance_takes_back_the_heroism_temp_hp(client, test_session_factory, monkeypatch):
    """I4: i PF temporanei dati a inizio turno si tolgono con l'annullo dell'avanzamento."""
    from sqlalchemy import select

    from core.db.models import Character
    from tests.integration._encounter_helpers import setup_full_encounter
    from tests.integration._telegram_stub import install_fake_telegram
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)
    assert (await client.post(f"/sessions/{sid}/encounter/start", json={})).status_code == 200
    async with test_session_factory() as s:
        hero = (await s.execute(select(Character).where(Character.name == "Eroe"))).scalar_one()
        hero.temp_hp = 0
        hero.active_states = [*(hero.active_states or []), {"key": "spell:heroism", "name": "Heroism", "ends_on": ["manual"], "rounds_left": None,
                                                           "data": {"spell_key": "heroism", "edition": "2014", "cast_mod": 3}}]
        await s.commit()
        hero_id = hero.id
    as_user(GM_ID)
    for _ in range(3):  # PG -> goblin -> goblin -> PG
        assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200
    assert (await _sheet(client, hero_id))["temp_hp"] == 3
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/prev-turn")).status_code == 200
    assert (await _sheet(client, hero_id))["temp_hp"] == 0


# --- Aiuto -----------------------------------------------------------------------------------------------------------

async def test_aid_raises_current_hp_too_and_the_end_caps_them_at_the_old_maximum(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Aid", "aid", 2)
    await _hp(client, caster, 30, 30)
    await _hp(client, hero, 150, user=PLAYER_ID)
    await _cast(client, caster, spell, [hero], level=2)
    sheet = await _sheet(client, hero)
    assert sheet["computed"]["hp_max_effective"] == 205 and sheet["current_hit_points"] == 155  # +5 al 2° livello
    await _hp(client, hero, 205, user=PLAYER_ID)
    as_user(GM_ID)
    assert (await client.post(f"/characters/{caster}/rest", json={"rest_type": "long"})).status_code == 200
    sheet = await _sheet(client, hero)
    assert sheet["computed"]["hp_max_effective"] == 200 and sheet["current_hit_points"] == 200


async def _homebrew_hp(client, cid, bonus, user=PLAYER_ID) -> None:
    as_user(user)
    rule = {"name": "PF extra", "enabled": True, "dsl": {"version": 1, "subject": {"type": "character"}, "triggers": [], "passive_modifiers": [{
        "when": {"path": "$character.id", "op": "gt", "value": 0}, "target": "character.hit_points_max", "value": bonus,
        "label_i18n": {"it": "PF extra", "en": "HP bonus"}}]}}
    assert (await client.post(f"/characters/{cid}/homebrew/rules", json=rule)).status_code in (200, 201)


async def _caster_long_rest(client, caster) -> None:
    as_user(GM_ID)
    assert (await client.post(f"/characters/{caster}/rest", json={"rest_type": "long"})).status_code == 200


async def test_ending_a_spell_without_hp_max_keeps_the_homebrew_hp_bonus(client, test_session_factory):
    """I3: la fine di Benedizione non tocca i PF attuali, nemmeno quelli oltre il massimo delle regole."""
    hero, caster, spell = await _table(client, test_session_factory, "Bless", "bless", 1)
    await _hp(client, caster, 30, 30)
    await _homebrew_hp(client, hero, 10)
    await _hp(client, hero, 210, user=PLAYER_ID)
    await _cast(client, caster, spell, [hero], level=1)
    await _caster_long_rest(client, caster)
    assert (await _sheet(client, hero))["current_hit_points"] == 210


async def test_ending_aid_caps_current_hp_at_the_maximum_including_the_homebrew_bonus(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Aid", "aid", 2)
    await _hp(client, caster, 30, 30)
    await _homebrew_hp(client, hero, 10)
    await _cast(client, caster, spell, [hero], level=2)
    await _hp(client, hero, 215, user=PLAYER_ID)
    await _caster_long_rest(client, caster)
    assert (await _sheet(client, hero))["current_hit_points"] == 210  # 200 + 10, non 200


async def test_heroes_feast_rolls_2d10_for_maximum_and_current(client, test_session_factory, monkeypatch):
    _max_dice(monkeypatch)
    hero, caster, spell = await _table(client, test_session_factory, "Heroes' Feast", "heroes-feast", 6)
    await _cast(client, caster, spell, [hero], level=6)
    sheet = await _sheet(client, hero)
    assert sheet["computed"]["hp_max_effective"] == 220 and sheet["current_hit_points"] == 220


# --- Interdizione alla Morte ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("edition", ["2014", "2024"])
async def test_death_ward_holds_at_one_hp_even_against_massive_damage_and_ends(client, test_session_factory, edition):
    hero, caster, spell = await _table(client, test_session_factory, "Death Ward", "death-ward", 4, hero_edition=edition, caster_edition=edition)
    await _hp(client, caster, 30, 30)
    await _cast(client, caster, spell, [hero], level=4)
    as_user(PLAYER_ID)
    assert await _hit(client, hero, 500, "slashing", options=[DEATH_WARD]) == 199
    sheet = await _sheet(client, hero)
    assert sheet["current_hit_points"] == 1 and not sheet["is_dead"]
    assert await _states(client, hero, "spell:death_ward") == []
    assert await _states(client, caster, "spell_cast:death_ward", GM_ID) == []  # l'incantesimo è finito


async def test_death_ward_is_kept_when_the_hit_does_not_reach_zero(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Death Ward", "death-ward", 4)
    await _hp(client, caster, 30, 30)
    await _cast(client, caster, spell, [hero], level=4)
    as_user(PLAYER_ID)
    assert await _hit(client, hero, 50, "slashing", options=[DEATH_WARD]) == 50
    assert len(await _states(client, hero, "spell:death_ward")) == 1
    assert len(await _states(client, caster, "spell_cast:death_ward", GM_ID)) == 1  # il rimborso toglie anche la fine in attesa
    assert await _hit(client, hero, 500, "slashing") == 150  # senza conferma il colpo uccide
    assert (await _sheet(client, hero))["is_dead"]


# --- Legame di Protezione ------------------------------------------------------------------------------------------

async def test_warding_bond_shares_damage_and_ends_when_the_caster_drops_to_zero(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Warding Bond", "warding-bond", 2)
    await _hp(client, caster, 30, 30)
    ac = (await _sheet(client, hero))["ac"]
    await _cast(client, caster, spell, [hero], level=2)
    assert (await _sheet(client, hero))["ac"] == ac + 1
    assert await _hit(client, hero, 10, "fire") == 5  # resistenza a tutti i danni
    assert (await _sheet(client, caster, GM_ID))["current_hit_points"] == 25  # il lanciatore subisce gli stessi 5
    as_user(GM_ID)
    history = (await client.get(f"/characters/{caster}/history")).json()
    assert any("condivisi con Eroe" in h["description"] for h in (history["items"] if isinstance(history, dict) else history))
    assert await _hit(client, hero, 100, "fire") == 50  # altri 50: il lanciatore va a 0
    caster_sheet = await _sheet(client, caster, GM_ID)
    assert caster_sheet["current_hit_points"] == 0 and caster_sheet["conditions"].get("unconscious")
    assert await _states(client, hero, "spell:warding_bond") == []
    assert (await _sheet(client, hero))["ac"] == ac


async def _history(client, cid, user=GM_ID) -> list[str]:
    as_user(user)
    data = (await client.get(f"/characters/{cid}/history")).json()
    return [h["description"] for h in (data["items"] if isinstance(data, dict) else data)]


async def _damage(client, cid, value, damage_type="fire", **extra) -> dict:
    as_user(PLAYER_ID)
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": value, "damage_type": damage_type, **extra})
    assert r.status_code == 200, r.text
    return r.json()


async def _undo(client, cid, op_id, user=PLAYER_ID) -> None:
    as_user(user)
    r = await client.post(f"/characters/{cid}/hp/undo", json={"op_id": op_id})
    assert r.status_code == 200, r.text


async def test_undoing_a_warding_bond_damage_restores_the_caster_hp_and_history(client, test_session_factory):
    """C2: l'annullo del bersaglio riporta anche il lanciatore com'era."""
    hero, caster, spell = await _table(client, test_session_factory, "Warding Bond", "warding-bond", 2)
    await _hp(client, caster, 30, 30)
    await _cast(client, caster, spell, [hero], level=2)
    dmg = await _damage(client, hero, 20)
    assert dmg["current_hit_points"] == 190 and (await _sheet(client, caster, GM_ID))["current_hit_points"] == 20
    await _undo(client, hero, dmg["hp_undo_id"])
    assert (await _sheet(client, hero))["current_hit_points"] == 200
    assert (await _sheet(client, caster, GM_ID))["current_hit_points"] == 30
    assert any("annullat" in h.lower() for h in await _history(client, caster))


async def test_undoing_a_damage_that_ended_warding_bond_brings_the_bond_back_on_both_sheets(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Warding Bond", "warding-bond", 2)
    await _hp(client, caster, 5, 30)
    await _cast(client, caster, spell, [hero], level=2)
    dmg = await _damage(client, hero, 100)
    assert (await _sheet(client, caster, GM_ID))["current_hit_points"] == 0 and await _states(client, hero, "spell:warding_bond") == []
    await _undo(client, hero, dmg["hp_undo_id"])
    caster_sheet = await _sheet(client, caster, GM_ID)
    assert caster_sheet["current_hit_points"] == 5 and not caster_sheet["conditions"].get("unconscious")
    assert len(await _states(client, caster, "spell_cast:warding_bond", GM_ID)) == 1
    assert len(await _states(client, hero, "spell:warding_bond")) == 1


async def test_warding_bond_shared_damage_makes_the_caster_roll_the_concentration_save(client, test_session_factory):
    """M2: è danno vero: segue il percorso del danno (TS di concentrazione, PF temporanei, morte)."""
    hero, caster, spell = await _table(client, test_session_factory, "Warding Bond", "warding-bond", 2)
    await _hp(client, caster, 30, 30)
    await _cast(client, caster, spell, [hero], level=2)
    as_user(GM_ID)
    assert (await client.patch(f"/characters/{caster}/concentration", json={"spell_id": spell})).status_code == 200
    await _damage(client, hero, 20)
    assert any("TS Concentrazione" in h for h in await _history(client, caster))


# --- Rigenerazione ---------------------------------------------------------------------------------------------------

async def test_regenerate_heals_4d8_plus_15_then_one_hp_each_turn(client, test_session_factory, monkeypatch):
    _max_dice(monkeypatch)
    hero, caster, spell = await _table(client, test_session_factory, "Regenerate", "regenerate", 7)
    await _hp(client, hero, 100, user=PLAYER_ID)
    await _cast(client, caster, spell, [hero], level=7)
    assert (await _sheet(client, hero))["current_hit_points"] == 147  # 32 + 15
    await _new_turn(client, hero)
    assert (await _sheet(client, hero))["current_hit_points"] == 148
