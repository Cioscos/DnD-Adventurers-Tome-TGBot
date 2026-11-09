"""Incantesimi concessi (D4), giro di correzione 1: dati coerenti (I5), due parti di danno (I9), gittata (M1)."""
from __future__ import annotations

import re

import pytest

from core.rules.catalog.granted_spells import GRANTED_SPELLS
from tests.integration.rules.test_2014_bard import _full, _spells
from tests.integration.rules.test_2014_cleric import _cleric

DICE = re.compile(r"^\d+d\d+([+-]\d+)?$")
WRATH = "cleric.destructive_wrath"


def test_every_granted_spell_has_damage_data_the_server_can_roll():
    for key, spell in GRANTED_SPELLS.items():
        assert spell.damage_dice is None or DICE.match(spell.damage_dice), (key, spell.damage_dice)
        assert spell.extra_damage_dice is None or DICE.match(spell.extra_damage_dice), (key, spell.extra_damage_dice)
        assert spell.higher_levels_dice is None or DICE.match(spell.higher_levels_dice), key
        assert spell.attack_save in (None, "ATK", "SAVE"), key
        if spell.damage_dice:  # un incantesimo che fa danno dice come: tiro per colpire o tiro salvezza
            assert spell.attack_save is not None and spell.damage_type, key
        else:  # senza danno non c'è altro da tirare
            assert spell.extra_damage_dice is None and spell.higher_levels_dice is None, key
        assert (spell.extra_damage_dice is None) == (spell.extra_damage_type is None), key


def test_buffs_and_utility_spells_do_not_roll_damage():
    for key in ("guardian-of-faith", "dimension-door", "divine-favor"):
        assert GRANTED_SPELLS[key].damage_dice is None, key
    assert GRANTED_SPELLS["scorching-ray"].attack_save == "ATK"


def test_the_two_part_spells_carry_both_parts_in_the_data():
    parts = {k: (s.damage_dice, s.damage_type, s.extra_damage_dice, s.extra_damage_type)
             for k, s in GRANTED_SPELLS.items() if s.extra_damage_dice}
    assert parts == {
        "flame-strike": ("4d6", "fire", "4d6", "radiant"),
        "ice-storm": ("2d8", "bludgeoning", "4d6", "cold"),
        "destructive-wave": ("5d6", "thunder", "5d6", "radiant|necrotic"),
    }


def test_grasping_vine_has_the_range_of_the_manual():
    assert GRANTED_SPELLS["grasping-vine"].range_area == "9 m"


async def _spell(client, cid, srd_index) -> dict:
    return next(s for s in (await _spells(client, cid)).values() if s["srd_index"] == srd_index)


async def test_a_two_part_spell_rolls_both_parts_without_the_player_adding_anything(client):
    cid = await _cleric(client, 9, "light", wisdom=16)
    spell = await _spell(client, cid, "flame-strike")
    assert (spell["extra_damage_dice"], spell["extra_damage_type"]) == ("4d6", "radiant")
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/roll_damage", json={
        "casting_level": 5, "main_rolls": [1, 2, 3, 4], "extra_rolls": [6, 6, 6, 6]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 10 + 24 and body["extra_kind"] == "d6" and body["extra_rolls"] == [6, 6, 6, 6]
    assert (body["damage_type"], body["extra_damage_type"]) == ("fire", "radiant")


async def test_destructive_wrath_maximises_only_the_thunder_part_of_the_destructive_wave(client):
    cid = await _cleric(client, 9, "tempest", wisdom=16)
    spell = await _spell(client, cid, "destructive-wave")
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/roll_damage", json={
        "casting_level": 5, "extra_rolls": [1, 1, 1, 1, 1], "options": [WRATH]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["main_rolls"] == [6] * 5 and body["extra_rolls"] == [1] * 5 and body["total"] == 30 + 5


async def test_destructive_wrath_does_not_maximise_dice_the_player_added_by_hand(client):
    cid = await _cleric(client, 9, "tempest", wisdom=16)
    spell = await _spell(client, cid, "call-lightning")
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/roll_damage", json={
        "casting_level": 3, "extra_dice": "2d4", "extra_rolls": [1, 1], "options": [WRATH]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["main_rolls"] == [10] * 3 and body["extra_rolls"] == [1, 1] and body["total"] == 30 + 2


async def test_a_spell_whose_damage_cannot_be_rolled_is_cast_anyway_and_says_so(client):
    cid = await _cleric(client, 5, wisdom=16)
    r = await client.post(f"/characters/{cid}/spells", json={
        "name": "Danno fisso", "level": 2, "damage_dice": "20", "damage_type": "radiant", "attack_save": "SAVE", "is_prepared": True})
    assert r.status_code == 201, r.text
    spell = r.json()["id"]
    before = {s["level"]: s["available"] for s in (await _full(client, cid))["spell_slots"]}
    use = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 2})
    assert use.status_code == 200, use.text
    assert use.json()["damage_unrollable"] is True  # il lancio c'è, il danno no: la UI lo dice
    assert {s["level"]: s["available"] for s in use.json()["spell_slots"]}[2] == before[2] - 1
    roll = await client.post(f"/characters/{cid}/spells/{spell}/roll_damage", json={"casting_level": 2})
    assert roll.status_code == 422 and roll.json()["detail"]["code"] == "bad_damage_dice"
    normal = await client.post(f"/characters/{cid}/spells", json={
        "name": "Dardo", "level": 1, "damage_dice": "1d4", "damage_type": "force", "is_prepared": True})
    use = await client.post(f"/characters/{cid}/spells/{normal.json()['id']}/use", json={"slot_level": 1})
    assert use.json()["damage_unrollable"] is False
