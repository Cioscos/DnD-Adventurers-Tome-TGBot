"""Effetti degli incantesimi, tipo di danno scelto al lancio: arriva al tiro di danno e ai privilegi che lo leggono."""
from __future__ import annotations

import pytest

from core.rules.catalog.spells import spell_effect
from tests.integration.rules.test_2014_bard import _roll_keys
from tests.integration.rules.test_2014_fighter_eldritch_knight import _spell
from tests.integration.rules.test_2024_sorcerer import OPTIONS, TRANSMUTED, _caster24, _damage, _pending
from tests.integration.rules.test_spell_effects_cast import _full
from tests.integration.rules.test_2024_sorcerer_subclasses import P, _affinity, _make

ORB = dict(name="Sfera Cromatica", srd_index="chromatic-orb", attack_save="DEX", damage_dice="3d8", damage_type="acid")
SIX = ["acid", "cold", "lightning", "fire", "thunder", "poison"]


async def _orb(client, cid, **extra) -> int:
    fields = {**ORB, **extra}
    return await _spell(client, cid, fields.pop("name"), 1, **fields)


async def _use(client, cid, spell, **body):
    return await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 1, **body})


# --- Catalogo ------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("edition,srd,options", [
    ("2014", "chromatic-orb", set(SIX)), ("2024", "chromatic-orb", set(SIX)),
    ("2024", "dragons-breath", {"acid", "cold", "fire", "lightning", "poison"}),
    ("2014", "elemental-weapon", {"acid", "cold", "fire", "lightning", "thunder"}),
    ("2024", "elemental-weapon", {"acid", "cold", "fire", "lightning", "thunder"}),
    ("2014", "glyph-of-warding", {"acid", "cold", "fire", "lightning", "thunder"}),
    ("2024", "glyph-of-warding", {"acid", "cold", "fire", "lightning", "thunder"}),
    ("2024", "sorcerous-burst", {"acid", "cold", "fire", "lightning", "poison", "psychic", "thunder"}),
    ("2024", "conjure-minor-elementals", {"acid", "cold", "fire", "lightning"}),
    ("2014", "protection-from-energy", {"acid", "cold", "fire", "lightning", "thunder"}),
])
def test_the_spell_offers_its_damage_types_in_the_edition(edition, srd, options):
    _, variant = spell_effect(edition, srd)
    choice = next(c for c in variant.choices if c.key == "damage_type")
    assert set(choice.options(edition)) == options


@pytest.mark.parametrize("edition,srd", [("2014", "dragons-breath"), ("2014", "sorcerous-burst"), ("2014", "conjure-minor-elementals")])
def test_a_spell_that_does_not_exist_in_the_edition_has_no_entry(edition, srd):
    assert spell_effect(edition, srd) is None


# --- Dal lancio al danno -------------------------------------------------------------------------------------------
async def test_chromatic_orb_cast_with_cold_rolls_cold_damage(client):
    cid = (await client.post("/characters", json={"name": "Mago"})).json()["id"]
    await client.post(f"/characters/{cid}/spell_slots", json={"level": 1, "total": 2})
    spell = await _orb(client, cid)
    assert (await _use(client, cid, spell, choices={"damage_type": "cold"})).status_code == 200
    result = await _damage(client, cid, spell, casting_level=1, damage_type="cold")
    assert result["damage_type"] == "cold" and result["parts"][0]["type"] == "cold"


async def test_a_damage_type_outside_the_list_is_refused_at_the_cast_and_at_the_roll(client):
    cid = (await client.post("/characters", json={"name": "Mago"})).json()["id"]
    await client.post(f"/characters/{cid}/spell_slots", json={"level": 1, "total": 2})
    spell = await _orb(client, cid)
    r = await _use(client, cid, spell, choices={"damage_type": "force"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice"
    r = await client.post(f"/characters/{cid}/spells/{spell}/roll_damage", json={"damage_type": "force", "casting_level": 1})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice"
    other = await _spell(client, cid, "Dardo", 1, srd_index="fire-bolt-x", damage_dice="1d10", damage_type="fire")
    r = await client.post(f"/characters/{cid}/spells/{other}/roll_damage", json={"damage_type": "cold", "casting_level": 1})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice"


async def test_a_spell_without_a_choice_is_unchanged(client):
    cid = (await client.post("/characters", json={"name": "Mago"})).json()["id"]
    spell = await _spell(client, cid, "Dardo", 1, damage_dice="2d6", damage_type="fire")
    result = await _damage(client, cid, spell, casting_level=1)
    assert result["damage_type"] == "fire"


async def test_the_roll_without_a_type_keeps_the_type_of_the_spell(client):
    cid = (await client.post("/characters", json={"name": "Mago"})).json()["id"]
    spell = await _orb(client, cid)
    assert (await _damage(client, cid, spell, casting_level=1))["damage_type"] == "acid"


async def test_a_concentration_spell_remembers_the_type_chosen_at_the_cast(client):
    cid = (await client.post("/characters", json={"name": "Paladino"})).json()["id"]
    await client.post(f"/characters/{cid}/spell_slots", json={"level": 3, "total": 2})
    spell = await _spell(client, cid, "Arma Elementale", 3, srd_index="elemental-weapon", damage_dice="1d4", damage_type="fire",
                         is_concentration=True)
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 3, "choices": {"damage_type": "thunder"}})
    assert r.status_code == 200, r.text
    assert (await _damage(client, cid, spell, casting_level=3))["damage_type"] == "thunder"


# --- Privilegi che leggono il tipo ---------------------------------------------------------------------------------
async def test_elemental_affinity_is_offered_on_the_orb_of_the_ancestors_type_only(client):
    cid = await _make(client, "draconic", 6)
    await _affinity(client, cid, "cold")
    spell = await _orb(client, cid)
    affinity = P + "elemental_affinity"
    assert affinity in await _roll_keys(client, cid, "spell_damage", spell_id=spell, damage_type="cold")
    assert affinity not in await _roll_keys(client, cid, "spell_damage", spell_id=spell, damage_type="fire")
    assert affinity not in await _roll_keys(client, cid, "spell_damage", spell_id=spell)  # il tipo di base è l'acido


async def test_the_affinity_bonus_applies_to_the_rolled_cold_orb(client):
    cid = await _make(client, "draconic", 6)
    await _affinity(client, cid, "cold")
    spell = await _orb(client, cid)
    plain = await _damage(client, cid, spell, casting_level=1, damage_type="cold", main_rolls=[1, 1, 1])
    boosted = await _damage(client, cid, spell, P + "elemental_affinity", casting_level=1, damage_type="cold", main_rolls=[1, 1, 1])
    assert boosted["total"] == plain["total"] + 4 and boosted["damage_type"] == "cold"
    r = await client.post(f"/characters/{cid}/spells/{spell}/roll_damage",
                          json={"options": [P + "elemental_affinity"], "casting_level": 1, "damage_type": "fire"})
    assert r.status_code == 409  # sul fuoco l'Affinità non c'è


async def _draconic_transmuter(client, ancestor):
    cid = await _make(client, "draconic", 6)
    await _affinity(client, cid, ancestor)
    choice = _pending(await _full(client, cid))
    picks = ["transmuted", *(k for k in OPTIONS if k != "transmuted")][:choice["count"]]
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve", json={"kind": "class_option", "options": picks})
    assert r.status_code == 200, r.text
    return cid


async def test_transmuted_spell_from_fire_to_cold_is_seen_by_the_affinity(client):
    cid = await _draconic_transmuter(client, "cold")
    spell = await _spell(client, cid, "Fiamma", 1, attack_save="DEX", damage_dice="2d6", damage_type="fire")
    affinity = P + "elemental_affinity"
    assert affinity not in await _roll_keys(client, cid, "spell_damage", spell_id=spell)  # sul fuoco non c'è
    plain = await _damage(client, cid, spell, f"{TRANSMUTED}_cold", casting_level=1, main_rolls=[1, 1])
    boosted = await _damage(client, cid, spell, f"{TRANSMUTED}_cold", affinity, casting_level=1, main_rolls=[1, 1])
    assert boosted["damage_type"] == "cold" and boosted["total"] == plain["total"] + 4


async def test_transmuting_away_from_the_ancestors_type_takes_the_affinity_away(client):
    cid = await _draconic_transmuter(client, "fire")
    spell = await _spell(client, cid, "Fiamma", 1, attack_save="DEX", damage_dice="2d6", damage_type="fire")
    r = await client.post(f"/characters/{cid}/spells/{spell}/roll_damage",
                          json={"options": [f"{TRANSMUTED}_cold", P + "elemental_affinity"], "casting_level": 1})
    assert r.status_code == 409


async def test_the_transmuted_spell_does_not_offer_the_type_the_orb_already_has(client):
    cid = await _caster24(client, 6, "transmuted")
    spell = await _orb(client, cid)
    keys = await _roll_keys(client, cid, "spell_damage", spell_id=spell, damage_type="cold")
    assert f"{TRANSMUTED}_cold" not in keys and f"{TRANSMUTED}_fire" in keys
