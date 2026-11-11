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


async def _end_spell(client, target, caster, key, how) -> None:
    """Chiude l'incantesimo ``key`` sul bersaglio: a mano (dal bersaglio) o con la fine della concentrazione (del lanciatore)."""
    if how == "manual":
        as_user(PLAYER_ID if target != caster else GM_ID)
        assert (await client.delete(f"/characters/{target}/active-states/spell:{key}")).status_code == 200
    else:
        as_user(GM_ID)
        assert (await client.patch(f"/characters/{caster}/concentration", json={"spell_id": None})).status_code == 200


# --- catalogo -----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("srd", ["mage-armor", "barkskin", "armor-of-agathys", "false-life", "death-ward", "warding-bond",
                                 "regenerate", "aura-of-vitality"])
@pytest.mark.parametrize("edition", ["2014", "2024"])
def test_hit_point_spells_are_in_both_editions(edition, srd):
    assert spell_effect(edition, srd) is not None


@pytest.mark.parametrize("srd,edition", [("heroism", "2014"), ("heroism", "2024"), ("enhance-ability", "2014")])
def test_temp_hp_spells_that_take_them_back_no_longer_warn_the_gm(srd, edition):
    """Giro 2: i PF temporanei svaniscono a fine incantesimo da soli, quindi niente nota per il GM."""
    _, variant = spell_effect(edition, srd)
    assert "toglili tu" not in variant.text["it"] and "remove them yourself" not in variant.text["en"]


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


async def test_mage_armor_ends_when_the_target_puts_on_armor(client, test_session_factory):
    """M3: per il manuale l'incantesimo termina, non resta sospeso."""
    hero, caster, spell = await _table(client, test_session_factory, "Mage Armor", "mage-armor", 1)
    await _cast(client, caster, spell, [hero], level=1)
    assert len(await _states(client, hero, "spell:mage_armor")) == 1
    as_user(PLAYER_ID)
    await _item(client, hero, "Cotta di maglia", item_type="armor", slot="body", base_ac=16)
    assert await _states(client, hero, "spell:mage_armor") == []
    assert await _states(client, caster, "spell_cast:mage_armor", GM_ID) == []


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


@pytest.mark.parametrize("how", ["manual", "concentration"])
async def test_heroism_temp_hp_vanish_when_the_spell_ends_unless_a_higher_source_took_over(client, test_session_factory, how):
    hero, caster, spell = await _table(client, test_session_factory, "Heroism", "heroism", 1)
    as_user(GM_ID)
    assert (await client.post(f"/characters/{caster}/classes", json={"class_name": "bard", "level": 3, "hit_die": 8})).status_code == 201
    assert (await client.patch(f"/characters/{caster}/ability_scores/charisma", json={"value": 16})).status_code == 200
    await _cast(client, caster, spell, [hero], level=1)
    await _new_turn(client, hero)
    assert (await _sheet(client, hero))["temp_hp"] == 3
    await _end_spell(client, hero, caster, "heroism", how)
    assert (await _sheet(client, hero))["temp_hp"] == 0
    # una fonte più alta nel frattempo: restano
    await _cast(client, caster, spell, [hero], level=1)
    await _new_turn(client, hero)
    await client.patch(f"/characters/{hero}/hp", json={"op": "set_temp", "value": 9})
    await _end_spell(client, hero, caster, "heroism", how)
    assert (await _sheet(client, hero))["temp_hp"] == 9


async def test_bears_endurance_temp_hp_vanish_when_the_spell_ends(client, test_session_factory, monkeypatch):
    _max_dice(monkeypatch)
    hero, caster, spell = await _table(client, test_session_factory, "Enhance Ability", "enhance-ability", 2)
    await _cast(client, caster, spell, [hero], level=2, choices={"ability": "constitution"})
    assert (await _sheet(client, hero))["temp_hp"] == 12
    await _end_spell(client, hero, caster, "enhance_ability", "concentration")
    assert (await _sheet(client, hero))["temp_hp"] == 0


async def test_false_life_temp_hp_have_no_state_to_end_so_they_stay(client, test_session_factory, monkeypatch):
    _max_dice(monkeypatch)
    hero, caster, spell = await _table(client, test_session_factory, "False Life", "false-life", 1)
    await _cast(client, caster, spell, [], level=1)
    sheet = await _sheet(client, caster, GM_ID)
    assert sheet["temp_hp"] == 8 and not [s for s in sheet["active_states"] or [] if s["key"].startswith("spell")]


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


async def test_undo_72_a_reopened_heroes_feast_gives_back_the_rolled_hit_points(client, test_session_factory, monkeypatch):
    from api.services.spell_effects import _drop_state, regrant_spells
    from api.services.session_allies import load_receiver
    from core.rules.states import SPELL_GIVEN
    _max_dice(monkeypatch)
    hero, caster, spell = await _table(client, test_session_factory, "Heroes' Feast", "heroes-feast", 6)
    await _cast(client, caster, spell, [hero], level=6)
    async with test_session_factory() as s:  # la chiusura dell'orologio toglie lo stato al bersaglio, l'annullo lo riapre
        c = await load_receiver(s, caster)
        given = dict((c.settings or {})[SPELL_GIVEN])
        await _drop_state(s, await load_receiver(s, hero), "spell:heroes_feast", caster)
        c.settings = {k: v for k, v in c.settings.items() if k != SPELL_GIVEN}
        await regrant_spells(s, c, given)
        await s.commit()
    sheet = await _sheet(client, hero)
    assert sheet["computed"]["hp_max_effective"] == 220


async def test_undo_83_the_vanished_temp_hp_line_is_written_even_if_a_new_cast_follows_in_the_same_save(test_session_factory):
    from sqlalchemy import select
    from core.db.models import Character, CharacterHistory
    from core.rules.states import drop_spell_temp_hp, forget_spell_temp_drop
    async with test_session_factory() as s:
        hero = Character(user_id=1, name="Eroe", hit_points=20, current_hit_points=20, temp_hp=3)
        s.add(hero)
        await s.flush()
        closed = [{"key": "spell:heroism", "name": "Eroismo", "data": {"temp_given": 3, "caster_id": 99}}]
        drop_spell_temp_hp(hero, closed)  # l'incantesimo finisce e toglie i PF temporanei
        forget_spell_temp_drop(hero, "spell:heroism")  # un nuovo lancio (o il riposo lungo) nello stesso salvataggio
        hero.temp_hp = 2  # forza il flush di una riga modificata
        await s.commit()
        rows = (await s.execute(select(CharacterHistory.description).where(CharacterHistory.character_id == hero.id))).scalars().all()
        assert any("PF temporanei svaniti" in r for r in rows)
        assert not (hero.settings or {}).get("spell_temp_dropped")


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
    assert await _hit(client, hero, 500, "slashing") == 149  # M4: senza conferma tiene a 1 PF lo stesso, il manuale non chiede nulla
    sheet = await _sheet(client, hero)
    assert sheet["current_hit_points"] == 1 and not sheet["is_dead"] and await _states(client, hero, "spell:death_ward") == []


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


async def test_undo_63_shared_damage_with_a_deleted_caster_undoes_only_the_targets_part(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Warding Bond", "warding-bond", 2)
    await _hp(client, caster, 30, 30)
    await _cast(client, caster, spell, [hero], level=2)
    dmg = await _damage(client, hero, 20)
    async with test_session_factory() as s:  # il lanciatore sparisce senza ripulire lo stato del bersaglio (cancellazione d'altro tipo)
        from sqlalchemy import delete as _delete
        from core.db.models import Character as _Character
        await s.execute(_delete(_Character).where(_Character.id == caster))
        await s.commit()
    await _undo(client, hero, dmg["hp_undo_id"])
    assert (await _sheet(client, hero))["current_hit_points"] == 200


async def test_undo_63_deleting_the_caster_after_the_bond_ended_leaves_no_orphan_state_for_the_next_damage(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Warding Bond", "warding-bond", 2)
    await _hp(client, caster, 5, 30)
    await _cast(client, caster, spell, [hero], level=2)
    dmg = await _damage(client, hero, 100)  # il lanciatore va a 0 e il legame finisce su entrambi
    as_user(GM_ID)
    assert (await client.delete(f"/characters/{caster}")).status_code in (200, 204)
    await _undo(client, hero, dmg["hp_undo_id"])
    assert await _states(client, hero, "spell:warding_bond") == []  # lo stato del lanciatore sparito non torna
    as_user(PLAYER_ID)
    assert (await client.patch(f"/characters/{hero}/hp", json={"op": "damage", "value": 10})).status_code == 200


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


async def test_warding_bond_damage_response_tells_the_target_about_the_shared_damage_and_the_casters_save(client, test_session_factory):
    """Giro 2: il bersaglio vede il danno condiviso e l'esito del TS del lanciatore; senza concentrazione, solo il danno."""
    hero, caster, spell = await _table(client, test_session_factory, "Warding Bond", "warding-bond", 2)
    await _hp(client, caster, 30, 30)
    await _cast(client, caster, spell, [hero], level=2)
    body = await _damage(client, hero, 20)
    # Legame di Protezione dà resistenza ai danni al bersaglio: 20 diventano 10, e 10 passano al lanciatore
    shared = body["shared_damage"]
    assert shared["amount"] == 10 and shared["caster_name"] == "Chierico"
    assert body["damage_taken"] == 10  # 73: il toast dice i danni subiti dopo la resistenza, non i 20 digitati
    assert shared["concentration_save"]["dc"] == 10 and isinstance(shared["concentration_save"]["success"], bool)
    assert body["concentration_save"] is None  # quello del bersaglio non c'è: il TS è del lanciatore
    as_user(GM_ID)
    assert (await client.patch(f"/characters/{caster}/concentration", json={"spell_id": None})).status_code == 200
    body = await _damage(client, hero, 20)
    assert body["shared_damage"]["amount"] == 10 and body["shared_damage"]["concentration_save"] is None


async def test_undoing_a_death_ward_hit_reopens_the_casters_clock_too(client, test_session_factory):
    """I1: l'annullo rimette lo stato sul bersaglio E l'orologio sul lanciatore, che poi lo fa scadere."""
    hero, caster, spell = await _table(client, test_session_factory, "Death Ward", "death-ward", 4)
    await _hp(client, caster, 30, 30)
    await _cast(client, caster, spell, [hero], level=4)
    dmg = await _damage(client, hero, 500, "slashing", options=[DEATH_WARD])
    assert await _states(client, hero, "spell:death_ward") == [] and await _states(client, caster, "spell_cast:death_ward", GM_ID) == []
    await _undo(client, hero, dmg["hp_undo_id"])
    assert len(await _states(client, hero, "spell:death_ward")) == 1
    assert len(await _states(client, caster, "spell_cast:death_ward", GM_ID)) == 1
    await _caster_long_rest(client, caster)  # la durata dell'incantesimo finisce: lo perde anche il bersaglio
    assert await _states(client, hero, "spell:death_ward") == []


async def _extra_spell(client, caster, name, srd, level) -> int:
    """Un secondo incantesimo del lanciatore, senza concentrazione, con il suo slot."""
    as_user(GM_ID)
    r = await client.post(f"/characters/{caster}/spells", json={"name": name, "srd_index": srd, "level": level, "is_concentration": False})
    assert r.status_code == 201, r.text
    assert (await client.post(f"/characters/{caster}/spell_slots", json={"level": level, "total": 2})).status_code == 201
    return r.json()["id"]


async def test_death_ward_triggering_keeps_the_casters_other_concentration(client, test_session_factory):
    """Giro 3, 1: Interdizione alla Morte scatta, ma Pelle Coriacea (concentrazione) resta sul bersaglio."""
    hero, caster, bark = await _table(client, test_session_factory, "Barkskin", "barkskin", 2)
    ward = await _extra_spell(client, caster, "Death Ward", "death-ward", 4)
    await _cast(client, caster, ward, [hero], level=4)
    await _cast(client, caster, bark, [hero], level=2)
    assert (await _sheet(client, caster, GM_ID))["concentrating_spell_id"] == bark
    await _damage(client, hero, 500, "slashing", options=[DEATH_WARD])
    assert await _states(client, hero, "spell:death_ward") == [] and await _states(client, caster, "spell_cast:death_ward", GM_ID) == []
    assert (await _sheet(client, caster, GM_ID))["concentrating_spell_id"] == bark
    assert len(await _states(client, hero, "spell:barkskin")) == 1


async def test_mage_armor_ending_keeps_the_casters_other_concentration(client, test_session_factory):
    hero, caster, bark = await _table(client, test_session_factory, "Barkskin", "barkskin", 2)
    armor = await _extra_spell(client, caster, "Mage Armor", "mage-armor", 1)
    await _cast(client, caster, armor, [hero], level=1)
    await _cast(client, caster, bark, [hero], level=2)
    as_user(PLAYER_ID)
    await _item(client, hero, "Cotta di maglia", item_type="armor", slot="body", base_ac=16)
    assert await _states(client, hero, "spell:mage_armor") == []
    assert (await _sheet(client, caster, GM_ID))["concentrating_spell_id"] == bark
    assert len(await _states(client, hero, "spell:barkskin")) == 1


async def _heroism_with_temp(client, test_session_factory):
    hero, caster, spell = await _table(client, test_session_factory, "Heroism", "heroism", 1)
    as_user(GM_ID)
    assert (await client.post(f"/characters/{caster}/classes", json={"class_name": "bard", "level": 3, "hit_die": 8})).status_code == 201
    assert (await client.patch(f"/characters/{caster}/ability_scores/charisma", json={"value": 16})).status_code == 200
    await _hp(client, caster, 200, 200)
    await _cast(client, caster, spell, [hero], level=1)
    await _new_turn(client, hero)
    assert (await _sheet(client, hero))["temp_hp"] == 3
    return hero, caster


async def test_undoing_the_damage_that_broke_concentration_gives_back_the_heroism_temp_hp(client, test_session_factory):
    """Giro 3, 2: l'annullo ridà al bersaglio anche i PF temporanei tolti dalla fine dell'incantesimo."""
    hero, caster = await _heroism_with_temp(client, test_session_factory)
    as_user(GM_ID)
    r = await client.patch(f"/characters/{caster}/hp", json={"op": "damage", "value": 100, "damage_type": "fire"})
    assert r.status_code == 200, r.text
    assert (await _sheet(client, hero))["temp_hp"] == 0 and await _states(client, hero, "spell:heroism") == []
    await _undo(client, caster, r.json()["hp_undo_id"], GM_ID)
    assert len(await _states(client, hero, "spell:heroism")) == 1
    sheet = await _sheet(client, hero)
    assert sheet["temp_hp"] == 3 and (await _states(client, hero, "spell:heroism"))[0]["data"]["temp_given"] == 3


async def test_heroism_temp_hp_are_not_given_back_if_the_target_got_others_meanwhile(client, test_session_factory):
    hero, caster = await _heroism_with_temp(client, test_session_factory)
    as_user(GM_ID)
    r = await client.patch(f"/characters/{caster}/hp", json={"op": "damage", "value": 100, "damage_type": "fire"})
    as_user(PLAYER_ID)
    assert (await client.patch(f"/characters/{hero}/hp", json={"op": "set_temp", "value": 5})).status_code == 200
    await _undo(client, caster, r.json()["hp_undo_id"], GM_ID)
    assert (await _sheet(client, hero))["temp_hp"] == 5


async def test_the_end_of_a_temp_hp_spell_leaves_a_history_row_on_the_receiver(client, test_session_factory):
    """Giro 3, 3."""
    hero, caster = await _heroism_with_temp(client, test_session_factory)
    await _end_spell(client, hero, caster, "heroism", "manual")
    assert any("PF temporanei svaniti" in h and "3 → 0" in h for h in await _history(client, hero, PLAYER_ID))


async def test_a_stale_heroism_drop_is_not_given_back_by_the_undo_of_a_later_cast(client, test_session_factory):
    """Giro 4, 1: la voce lasciata dalla fine del primo Eroismo non vale per l'annullo del danno che chiude il secondo."""
    hero, caster = await _heroism_with_temp(client, test_session_factory)
    as_user(GM_ID)
    assert (await client.patch(f"/characters/{caster}/hp", json={"op": "damage", "value": 100, "damage_type": "fire"})).status_code == 200
    spell = (await _sheet(client, caster, GM_ID))["spells"][0]["id"]
    await _cast(client, caster, spell, [hero], level=1)
    await _new_turn(client, hero)
    await _damage(client, hero, 3)  # il bersaglio assorbe i 3 PF temporanei del nuovo Eroismo
    assert (await _sheet(client, hero))["temp_hp"] == 0
    as_user(GM_ID)
    r = await client.patch(f"/characters/{caster}/hp", json={"op": "damage", "value": 60, "damage_type": "fire"})
    assert r.status_code == 200 and await _states(client, hero, "spell:heroism") == []
    await _undo(client, caster, r.json()["hp_undo_id"], GM_ID)
    assert len(await _states(client, hero, "spell:heroism")) == 1
    assert (await _sheet(client, hero))["temp_hp"] == 0


async def test_the_receivers_long_rest_forgets_the_dropped_temp_hp(client, test_session_factory):
    """Giro 4: nessuna voce resta per sempre; dopo il riposo lungo del bersaglio l'annullo non ridà i PF temporanei."""
    hero, caster = await _heroism_with_temp(client, test_session_factory)
    as_user(GM_ID)
    r = await client.patch(f"/characters/{caster}/hp", json={"op": "damage", "value": 100, "damage_type": "fire"})
    as_user(PLAYER_ID)
    assert (await client.post(f"/characters/{hero}/rest", json={"rest_type": "long"})).status_code == 200
    await _undo(client, caster, r.json()["hp_undo_id"], GM_ID)
    assert (await _sheet(client, hero))["temp_hp"] == 0


def test_a_new_temp_hp_drop_keeps_the_entries_not_yet_undone():
    """Giro 4, 2: la fine di un altro incantesimo non cancella la voce di quello prima."""
    from types import SimpleNamespace
    from core.rules.states import SPELL_TEMP_DROPPED, drop_spell_temp_hp
    char = SimpleNamespace(temp_hp=3, settings={})
    drop_spell_temp_hp(char, [{"key": "spell:heroism", "name": "Eroismo", "data": {"caster_id": 1, "temp_given": 3}}])
    char.temp_hp = 7
    drop_spell_temp_hp(char, [{"key": "spell:bears_endurance", "name": "Orso", "data": {"caster_id": 2, "temp_given": 7}}])
    assert set(char.settings[SPELL_TEMP_DROPPED]) == {"spell:heroism", "spell:bears_endurance"}


# --- Rigenerazione ---------------------------------------------------------------------------------------------------

async def test_regenerate_heals_4d8_plus_15_then_one_hp_each_turn(client, test_session_factory, monkeypatch):
    _max_dice(monkeypatch)
    hero, caster, spell = await _table(client, test_session_factory, "Regenerate", "regenerate", 7)
    await _hp(client, hero, 100, user=PLAYER_ID)
    await _cast(client, caster, spell, [hero], level=7)
    assert (await _sheet(client, hero))["current_hit_points"] == 147  # 32 + 15
    await _new_turn(client, hero)
    assert (await _sheet(client, hero))["current_hit_points"] == 148


async def test_death_ward_is_not_offered_to_the_client_because_the_server_applies_it(client, test_session_factory):
    """Giro 2: l'interruttore nel foglio «Prima del danno» è superfluo, ma il colpo resta tenuto a 1 PF."""
    hero, caster, spell = await _table(client, test_session_factory, "Death Ward", "death-ward", 4)
    await _cast(client, caster, spell, [hero], level=4)
    as_user(PLAYER_ID)
    r = await client.get(f"/characters/{hero}/roll-options", params={"roll": "damage_taken", "damage": 50, "damage_type": "slashing"})
    assert r.status_code == 200, r.text
    assert DEATH_WARD not in [o["key"] for o in r.json()]
    assert await _hit(client, hero, 500, "slashing") == 199  # senza opzioni inviate


async def test_89_the_ac_seen_in_the_evening_counts_items_like_the_sheet(client, test_session_factory):
    """Punto 89: in serata la CA include gli oggetti (e l'homebrew), come la scheda; prima li lasciava fuori."""
    hero, caster, spell = await _table(client, test_session_factory, "Mage Armor", "mage-armor", 1)
    as_user(PLAYER_ID)
    await _item(client, hero, "Anello", slot="ring1", is_magic=True, bonuses=[{"target": "ac", "value": 1}])
    await _cast(client, caster, spell, [hero], level=1)
    as_user(GM_ID)
    live = await client.get("/sessions/1/live")
    assert next(c for c in live.json()["live_characters"] if c["id"] == hero)["ac"] == 17  # 13 + 3 + anello +1


async def test_89_the_ac_seen_in_the_evening_counts_homebrew_like_the_sheet(client, test_session_factory):
    """Giro 1 (minor 4): in serata la CA somma anche i modificatori homebrew passivi, come la scheda."""
    hero, _caster, _spell = await _table(client, test_session_factory, "Mage Armor", "mage-armor", 1)
    as_user(GM_ID)
    before = next(c for c in (await client.get("/sessions/1/live")).json()["live_characters"] if c["id"] == hero)["ac"]
    as_user(PLAYER_ID)
    rule = {"name": "+2 AC", "enabled": True, "dsl": {"version": 1, "subject": {"type": "character"}, "triggers": [],
            "passive_modifiers": [{"when": {"path": "$character.id", "op": "gt", "value": 0}, "target": "character.ac",
                                   "value": 2, "label_i18n": {"it": "+2 CA", "en": "+2 AC"}}]}}
    r = await client.post(f"/characters/{hero}/homebrew/rules", json=rule)
    assert r.status_code in (200, 201), r.text
    as_user(GM_ID)
    live = await client.get("/sessions/1/live")
    assert next(c for c in live.json()["live_characters"] if c["id"] == hero)["ac"] == before + 2
