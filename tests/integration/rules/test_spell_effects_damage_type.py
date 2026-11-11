"""Effetti degli incantesimi, tipo di danno scelto al lancio: arriva al tiro di danno e ai privilegi che lo leggono."""
from __future__ import annotations

import pytest

from core.rules.catalog.spells import spell_effect
from tests.integration.rules.test_2014_bard import _roll_keys
from tests.integration.rules.test_2014_fighter_eldritch_knight import _spell
from tests.integration.rules.test_2024_sorcerer import OPTIONS, TRANSMUTED, _caster24, _damage, _pending
from tests.integration.rules.test_spell_effects_cast import _full
from tests.integration.rules.test_2024_sorcerer_subclasses import P, _affinity, _make
from tests.integration.rules.test_2014_sorcerer_origins import AFFINITY_CAST, _draconic as _draconic14

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
    ("2024", "conjure-elemental", {"lightning", "thunder", "fire", "cold"}),
    ("2014", "protection-from-energy", {"acid", "cold", "fire", "lightning", "thunder"}),
])
def test_the_spell_offers_its_damage_types_in_the_edition(edition, srd, options):
    _, variant = spell_effect(edition, srd)
    choice = next(c for c in variant.choices if c.key == "damage_type")
    assert set(choice.options(edition)) == options


@pytest.mark.parametrize("edition,srd", [("2014", "dragons-breath"), ("2014", "sorcerous-burst"), ("2014", "conjure-minor-elementals"), ("2014", "conjure-elemental")])
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


async def _roll(client, cid, spell, **body):
    return await client.post(f"/characters/{cid}/spells/{spell}/roll_damage", json={"casting_level": 1, **body})


async def test_the_roll_without_a_cast_does_not_fall_back_to_the_type_of_the_row(client):
    cid = (await client.post("/characters", json={"name": "Mago"})).json()["id"]
    spell = await _orb(client, cid)
    r = await _roll(client, cid, spell)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_choice"
    r = await _roll(client, cid, spell, damage_type="cold")  # nemmeno il tipo imposto dal client
    assert r.status_code == 422


async def test_the_roll_uses_the_type_of_the_cast_and_refuses_another(client):
    cid = (await client.post("/characters", json={"name": "Mago"})).json()["id"]
    await client.post(f"/characters/{cid}/spell_slots", json={"level": 1, "total": 3})
    spell = await _orb(client, cid)
    r0 = await _use(client, cid, spell, choices={"damage_type": "fire"}, confirm=["one_slot_per_turn"]); assert r0.status_code == 200, r0.text
    assert (await _roll(client, cid, spell, damage_type="poison")).status_code == 422
    assert (await _roll(client, cid, spell)).json()["damage_type"] == "fire"  # senza tipo: quello del lancio
    assert (await _roll(client, cid, spell, damage_type="fire")).json()["damage_type"] == "fire"


async def test_a_new_cast_replaces_the_type_and_another_spell_leaves_it(client):
    cid = (await client.post("/characters", json={"name": "Mago"})).json()["id"]
    await client.post(f"/characters/{cid}/spell_slots", json={"level": 1, "total": 4})
    spell = await _orb(client, cid)
    other = await _spell(client, cid, "Dardo", 1, srd_index="fire-bolt-x", damage_dice="1d10", damage_type="fire")
    await _use(client, cid, spell, choices={"damage_type": "fire"})
    await _use(client, cid, spell, choices={"damage_type": "cold"})
    assert (await _roll(client, cid, spell, damage_type="fire")).status_code == 422
    assert (await _roll(client, cid, spell)).json()["damage_type"] == "cold"
    assert (await _use(client, cid, other)).status_code == 200  # un altro lancio non tocca la voce della Sfera
    assert (await _roll(client, cid, spell)).json()["damage_type"] == "cold"


async def test_the_resisted_type_of_protection_from_energy_is_not_a_damage_type(client):
    cid = await _draconic14(client, 6, "red")
    spell = await _spell(client, cid, "Protezione dall'Energia", 3, srd_index="protection-from-energy")
    assert AFFINITY_CAST not in await _roll_keys(client, cid, "cast", spell_id=spell, damage_type="fire")  # nemmeno nell'elenco
    r = await _use(client, cid, spell, slot_level=3, choices={"damage_type": "fire"}, options=[AFFINITY_CAST])
    assert r.status_code == 409  # il tipo a cui si resiste non è un danno inflitto: l'Affinità non vale
    assert (await _use(client, cid, spell, slot_level=3, choices={"damage_type": "fire"})).status_code == 200


async def test_a_concentration_spell_remembers_the_type_chosen_at_the_cast(client):
    cid = (await client.post("/characters", json={"name": "Paladino"})).json()["id"]
    await client.post(f"/characters/{cid}/spell_slots", json={"level": 3, "total": 2})
    spell = await _spell(client, cid, "Arma Elementale", 3, srd_index="elemental-weapon", damage_dice="1d4", damage_type="fire",
                         is_concentration=True)
    sword = (await client.post(f"/characters/{cid}/items", json={"name": "Spada", "item_type": "weapon", "item_metadata": {"damage_dice": "1d8"}})).json()["items"][0]["id"]
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 3, "choices": {"damage_type": "thunder", "item_id": str(sword)}})
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
    assert (await _use(client, cid, spell, choices={"damage_type": "cold"})).status_code == 200
    plain = await _damage(client, cid, spell, casting_level=1, damage_type="cold", main_rolls=[1, 1, 1])
    boosted = await _damage(client, cid, spell, P + "elemental_affinity", casting_level=1, damage_type="cold", main_rolls=[1, 1, 1])
    assert boosted["total"] == plain["total"] + 4 and boosted["damage_type"] == "cold"
    r0 = await _use(client, cid, spell, choices={"damage_type": "fire"}, confirm=["one_slot_per_turn"]); assert r0.status_code == 200, r0.text
    r = await _roll(client, cid, spell, options=[P + "elemental_affinity"])
    assert r.status_code == 409  # sul fuoco l'Affinità non c'è


async def test_the_affinity_resistance_at_the_cast_follows_the_chosen_type_in_2014(client):
    cid = await _draconic14(client, 6, "red")  # antenato rosso: fuoco; la Sfera di base è acido
    spell = await _orb(client, cid)
    assert AFFINITY_CAST in await _roll_keys(client, cid, "cast", spell_id=spell, damage_type="fire")
    assert AFFINITY_CAST not in await _roll_keys(client, cid, "cast", spell_id=spell, damage_type="cold")
    r = await _use(client, cid, spell, slot_level=1, choices={"damage_type": "fire"}, options=[AFFINITY_CAST])
    assert r.status_code == 200, r.text


async def test_the_transmuted_affinity_is_listed_after_the_transmuted_option(client):
    cid = await _draconic_transmuter(client, "cold")
    spell = await _spell(client, cid, "Fiamma", 1, attack_save="DEX", damage_dice="2d6", damage_type="fire")
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": "spell_damage", "spell_id": spell})
    options = {o["key"]: o for o in r.json()}
    assert options[P + "elemental_affinity"]["needs"] == f"{TRANSMUTED}_cold"


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
    assert affinity in await _roll_keys(client, cid, "spell_damage", spell_id=spell)  # elencata solo dopo Trasmutato (needs): sul fuoco da sola non si applica
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


# 74: il Glifo di Interdizione chiede il tipo solo per le Rune Esplosive; il Glifo incantesimo non infligge danno
async def test_t10_74_a_spell_glyph_asks_for_no_damage_type_and_the_explosive_runes_do(client):
    cid = (await client.post("/characters", json={"name": "Chierico"})).json()["id"]
    await client.post(f"/characters/{cid}/spell_slots", json={"level": 3, "total": 3})
    glyph = await _spell(client, cid, "Glifo di Interdizione", 3, srd_index="glyph-of-warding")
    spells = {s["id"]: s for s in (await client.get(f"/characters/{cid}/spells")).json()}
    shown = {c["key"]: c["when"] for c in spells[glyph]["effect"]["choices"]}
    assert shown == {"glyph": None, "damage_type": ["glyph", "explosive"]}
    use = lambda **choices: client.post(f"/characters/{cid}/spells/{glyph}/use", json={"slot_level": 3, "choices": choices})  # noqa: E731
    assert (await use(glyph="spell")).status_code == 200
    assert (await use(glyph="spell", damage_type="fire")).status_code == 422  # il tipo non c'entra col glifo incantesimo
    assert (await use(glyph="explosive")).status_code == 422 and (await use(glyph="explosive", damage_type="force")).status_code == 422
    assert (await use(glyph="explosive", damage_type="fire")).status_code == 200
