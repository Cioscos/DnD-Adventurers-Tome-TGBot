"""Warlock 2014 (Task 29): le suppliche occulte e il Dono del Patto."""
from __future__ import annotations

import json

import pytest

from tests.integration.rules.test_2014_barbarian import _armor, _keys, _weapon
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _use
from tests.integration.rules.test_2014_fighter_eldritch_knight import _hit, _spell
from tests.integration.rules.test_2014_paladin import _new_turn, _rest, _turn
from tests.integration.rules.test_2014_warlock import _choice, _pact_slots, _resolve, _set_used, _warlock, _with_blast

BLADE_USE = "warlock.pact_of_the_blade"


async def _caster(client, level, *picks, boon=None, blast=False, patron=None, **scores) -> int:
    """Un warlock con le suppliche indicate (le altre scelte sono riempite con altre qualsiasi)."""
    cid = await _warlock(client, level, patron, **{"charisma": 16, **scores})
    if boon:
        assert (await _resolve(client, cid, "pact_boon", [boon])).status_code == 200
    if blast:
        await _with_blast(client, cid)
    choice = _choice(await _full(client, cid), "invocations")
    offered = [o["key"] for o in choice["options"]]
    assert set(picks) <= set(offered), set(picks) - set(offered)
    chosen = [*picks, *(k for k in offered if k not in picks)][:choice["count"]]
    r = await _resolve(client, cid, "invocations", chosen)
    assert r.status_code == 200, r.text
    return cid


async def _spells_by_index(client, cid) -> dict[str, dict]:
    return {s["srd_index"]: s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"]}


async def _cast(client, cid, spell_id, **body):
    return await client.post(f"/characters/{cid}/spells/{spell_id}/use", json=body)


# ---------------------------------------------------------------------------
# A volontà: l'incantesimo è sulla scheda e si lancia senza slot
# ---------------------------------------------------------------------------

AT_WILL = [
    ("armor_of_shadows", "mage-armor", 2, None), ("beast_speech", "speak-with-animals", 2, None),
    ("eldritch_sight", "detect-magic", 2, None), ("misty_visions", "silent-image", 2, None),
    ("mask_of_many_faces", "disguise-self", 2, None), ("ascendant_step", "levitate", 9, None),
    ("otherworldly_leap", "jump", 9, None), ("whispers_of_the_grave", "speak-with-dead", 9, None),
    ("master_of_myriad_forms", "alter-self", 15, None), ("visions_of_distant_realms", "arcane-eye", 15, None),
    ("chains_of_carceri", "hold-monster", 15, "chain"),
]


@pytest.mark.parametrize("invocation,spell,level,boon", AT_WILL)
async def test_an_at_will_invocation_puts_the_spell_on_the_sheet_and_casts_it_without_a_slot(client, invocation, spell, level, boon):
    cid = await _caster(client, level, invocation, boon=boon)
    found = (await _spells_by_index(client, cid)).get(spell)
    assert found is not None and found["at_will"] is True and found["always_prepared"] is True
    before = await _pact_slots(client, cid)
    r = await _cast(client, cid, found["id"], free_cast=True)
    assert r.status_code == 200, r.text
    assert await _pact_slots(client, cid) == before and (await _turn(client, cid))["action_used"] is True


async def test_an_at_will_spell_is_absent_without_its_invocation(client):
    cid = await _caster(client, 2, "beast_speech", "misty_visions")
    assert "mage-armor" not in await _spells_by_index(client, cid)


async def test_armor_of_shadows_makes_the_ac_13_plus_dexterity_for_eight_hours_without_armor(client):
    cid = await _caster(client, 2, "armor_of_shadows", dexterity=14)
    assert (await _full(client, cid))["ac"] == 12
    spell = (await _spells_by_index(client, cid))["mage-armor"]
    assert (await _cast(client, cid, spell["id"], free_cast=True)).status_code == 200
    full = await _full(client, cid)
    assert full["ac"] == 15 and any(s["key"] == "mage_armor" and s["rounds_left"] == 4800 for s in full["active_states"])
    await _rest(client, cid, "long")
    assert (await _full(client, cid))["ac"] == 12


async def test_mage_armor_gives_nothing_to_someone_who_wears_armor(client):
    cid = await _caster(client, 2, "armor_of_shadows", dexterity=14)
    spell = (await _spells_by_index(client, cid))["mage-armor"]
    await _armor(client, cid, "heavy", 16)
    await _cast(client, cid, spell["id"], free_cast=True)
    assert (await _full(client, cid))["ac"] == 16


async def test_chains_of_carceri_asks_whether_the_target_is_allowed_and_new(client):
    cid = await _caster(client, 15, "chains_of_carceri", boon="chain")
    spell = (await _spells_by_index(client, cid))["hold-monster"]
    keys = await _keys(client, cid, "cast", spell_id=spell["id"])
    assert "warlock.chains_of_carceri_cast" in keys
    r = await _cast(client, cid, spell["id"], free_cast=True, options=["warlock.chains_of_carceri_cast"])
    assert r.status_code == 200, r.text
    assert "celestiali" in r.json()["option_result"]["effects"][0]["it"]


# ---------------------------------------------------------------------------
# Una volta per riposo lungo, con uno slot di Patto
# ---------------------------------------------------------------------------

ONCE = [
    ("mire_the_mind", "slow", 5), ("thief_of_five_fates", "bane", 2), ("sign_of_ill_omen", "bestow-curse", 5),
    ("dreadful_word", "confusion", 7), ("sculptor_of_flesh", "polymorph", 7), ("minions_of_chaos", "conjure-elemental", 9),
    ("bewitching_whispers", "compulsion", 7),
]


@pytest.mark.parametrize("invocation,spell,level", ONCE)
async def test_a_once_per_long_rest_invocation_spends_its_use_and_a_pact_slot(client, invocation, spell, level):
    cid = await _caster(client, level, invocation)
    row = await _ability(client, cid, f"warlock.{invocation}")
    assert row["max_uses"] == 1 and row["uses"] == 1 and row["restoration_type"] == "long_rest"
    found = (await _spells_by_index(client, cid))[spell]
    assert found["pact_cast"]["kind"] == "invocation" and found["pact_cast"]["pact_only"] is True and found["pact_cast"]["uses_left"] == 1
    [pact] = await _pact_slots(client, cid)
    r = await _cast(client, cid, found["id"], slot_id=pact["id"])
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, f"warlock.{invocation}"))["uses"] == 0
    assert (await _pact_slots(client, cid))[0]["used"] == 1
    await _set_used(client, cid, pact["id"], 0)
    assert (await _cast(client, cid, found["id"], slot_id=pact["id"])).status_code == 409  # l'uso è finito
    await _rest(client, cid, "long")
    assert (await _cast(client, cid, found["id"], slot_id=pact["id"])).status_code == 200


async def test_a_once_per_long_rest_invocation_needs_a_pact_slot_not_a_regular_one(client):
    cid = await _caster(client, 5, "mire_the_mind")
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 5})).status_code in (200, 201)
    slow = (await _spells_by_index(client, cid))["slow"]
    regular = next(s for s in (await _full(client, cid))["spell_slots"] if not s["is_pact"] and s["level"] == 3)
    r = await _cast(client, cid, slow["id"], slot_id=regular["id"])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "pact_slot_required"
    assert (await _ability(client, cid, "warlock.mire_the_mind"))["uses"] == 1  # nulla speso
    r = await _cast(client, cid, slow["id"], slot_level=3)  # col solo livello: solo il patto
    assert r.status_code == 200, r.text
    assert next(s for s in (await _full(client, cid))["spell_slots"] if s["id"] == regular["id"])["used"] == 0


async def test_a_refused_once_cast_costs_nothing(client):
    cid = await _caster(client, 5, "mire_the_mind")
    slow = (await _spells_by_index(client, cid))["slow"]
    [pact] = await _pact_slots(client, cid)
    await _set_used(client, cid, pact["id"], pact["total"])
    assert (await _cast(client, cid, slow["id"], slot_id=pact["id"])).status_code == 400
    assert (await _ability(client, cid, "warlock.mire_the_mind"))["uses"] == 1


# ---------------------------------------------------------------------------
# Deflagrazione occulta
# ---------------------------------------------------------------------------

async def _blast_damage(client, cid, spell, **body):
    r = await client.post(f"/characters/{cid}/spells/{spell}/roll_damage", json=body)
    assert r.status_code == 200, r.text
    return r.json()


async def _blast(client, cid) -> int:
    return await _spell(client, cid, "Deflagrazione occulta", 0, srd_index="eldritch-blast", attack_save="ATK", damage_dice="1d10", damage_type="force")


@pytest.mark.parametrize("level,beams", [(2, 1), (5, 2), (11, 3), (17, 4)])
async def test_agonizing_blast_adds_charisma_to_every_beam(client, level, beams):
    cid = await _caster(client, level, "agonizing_blast", blast=True, charisma=18)
    blast = next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"] == "eldritch-blast")
    other = await _spell(client, cid, "Raggio", 0, attack_save="ATK", damage_dice="1d10", damage_type="fire")
    assert (await _blast_damage(client, cid, other, main_rolls=[4] * beams))["total"] == 4 * beams
    assert (await _blast_damage(client, cid, blast["id"], main_rolls=[4] * beams))["total"] == 4 * beams + 4 * beams


async def test_agonizing_blast_needs_the_invocation(client):
    cid = await _caster(client, 5, "beast_speech", "misty_visions", "eldritch_sight", blast=True, charisma=18)
    blast = next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"] == "eldritch-blast")
    assert (await _blast_damage(client, cid, blast["id"], main_rolls=[4, 4]))["total"] == 8


async def test_agonizing_blast_is_found_from_the_italian_name_too(client):
    cid = await _caster(client, 2, "agonizing_blast", blast=True, charisma=18)
    manual = await _spell(client, cid, "Deflagrazione Occulta", 0, attack_save="ATK", damage_dice="1d10", damage_type="force")
    assert (await _blast_damage(client, cid, manual, main_rolls=[3]))["total"] == 3 + 4


async def test_eldritch_spear_shows_the_blast_range_as_90_meters(client):
    cid = await _caster(client, 2, "eldritch_spear", blast=True)
    spells = {s["srd_index"]: s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"]}
    assert spells["eldritch-blast"]["range_area"] == "90 m"
    other = await _spell(client, cid, "Raggio", 0, range_area="18 m")
    assert next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["id"] == other)["range_area"] == "18 m"


async def test_repelling_blast_offers_a_push_only_for_the_blast_after_a_hit(client):
    cid = await _caster(client, 2, "repelling_blast", blast=True)
    blast = next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"] == "eldritch-blast")
    other = await _spell(client, cid, "Raggio", 0, attack_save="ATK", damage_dice="1d10", damage_type="fire")
    assert "warlock.repelling_blast" in await _keys(client, cid, "attack", spell_id=blast["id"])
    assert "warlock.repelling_blast" not in await _keys(client, cid, "attack", spell_id=other)


# ---------------------------------------------------------------------------
# Competenze, sensi, rituali
# ---------------------------------------------------------------------------

async def test_beguiling_influence_gives_deception_and_persuasion_and_never_lowers_an_expertise(client):
    cid = await _warlock(client, 2)
    await client.patch(f"/characters/{cid}/skills", json={"skills": {"deception": "expert"}})
    choice = _choice(await _full(client, cid), "invocations")
    others = [o["key"] for o in choice["options"] if o["key"] != "beguiling_influence"]
    assert (await _resolve(client, cid, "invocations", ["beguiling_influence", others[0]])).status_code == 200
    skills = (await _full(client, cid))["skills"]
    assert skills["persuasion"] is True and skills["deception"] == "expert"


async def test_devils_sight_adds_a_36_meter_sense(client):
    cid = await _caster(client, 2, "devils_sight")
    senses = (await _full(client, cid))["computed"]["senses"]
    assert {"type": "devils_sight", "range_ft": 120} in senses


async def test_book_of_ancient_secrets_picks_two_first_level_rituals_outside_the_known_spells(client):
    cid = await _caster(client, 3, "book_of_ancient_secrets", boon="tome")
    pick = _choice(await _full(client, cid), "book_rituals")
    assert pick["count"] == 2 and pick["spell_pick"]["free"] is True and pick["spell_pick"]["exact"] and pick["spell_pick"]["ritual"]
    base = {"level": 1, "pick_id": pick["id"], "casting_time": "1 azione"}
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Dardo", **base})  # non è un rituale
    assert r.status_code == 422 and r.json()["detail"]["code"] == "spell_pick_ritual"
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Individuazione del magico", "is_ritual": True, **base})
    assert r.status_code == 201, r.text
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Trovare famiglio", "is_ritual": True, **{**base, "level": 2}})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "spell_pick_level"


async def test_book_of_ancient_secrets_lets_a_warlock_cast_a_known_ritual_as_a_ritual(client):
    cid = await _caster(client, 3, "book_of_ancient_secrets", boon="tome")
    info = (await _full(client, cid))["spellcasting"]
    assert info["has_ritual_caster"] is True
    ritual = await _spell(client, cid, "Individuazione del magico", 1, is_ritual=True)
    before = await _pact_slots(client, cid)
    r = await _cast(client, cid, ritual, as_ritual=True)
    assert r.status_code == 200, r.text
    assert await _pact_slots(client, cid) == before


async def test_a_warlock_without_the_book_does_not_cast_rituals(client):
    cid = await _caster(client, 3, "beast_speech", boon="tome")
    assert (await _full(client, cid))["spellcasting"]["has_ritual_caster"] is False
    ritual = await _spell(client, cid, "Individuazione del magico", 1, is_ritual=True)
    assert (await _cast(client, cid, ritual, as_ritual=True)).status_code == 400


async def test_the_tome_gives_three_free_cantrips_from_any_list(client):
    cid = await _warlock(client, 3)
    assert _choice(await _full(client, cid), "tome_cantrips") is None
    await _resolve(client, cid, "pact_boon", ["tome"])
    pick = _choice(await _full(client, cid), "tome_cantrips")
    assert pick["count"] == 3 and pick["spell_pick"]["free"] is True and pick["spell_pick"]["max_level"] == 0
    for name in ("Mano magica", "Luce", "Prestidigitazione"):
        r = await client.post(f"/characters/{cid}/spells", json={"name": name, "level": 0, "pick_id": pick["id"]})
        assert r.status_code == 201, r.text
    assert _choice(await _full(client, cid), "tome_cantrips") is None
    limits = (await _full(client, cid))["spellcasting"]["limits"][0]
    assert limits["cantrips_count"] == 0 or limits["cantrips_count"] <= limits["cantrips_limit"]


# ---------------------------------------------------------------------------
# Patto della Lama
# ---------------------------------------------------------------------------

async def test_the_blade_is_created_in_hand_as_a_magic_weapon_the_warlock_is_proficient_with(client):
    cid = await _warlock(client, 3)
    await _resolve(client, cid, "pact_boon", ["blade"])
    old = await _weapon(client, cid, "Ascia", "main_hand")
    assert (await _use(client, cid, BLADE_USE, params={"weapon": "nonesiste"})).status_code == 422
    assert (await _turn(client, cid))["action_used"] is False
    r = await _use(client, cid, BLADE_USE, params={"weapon": "longsword"})
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["action_used"] is True
    items = {i["id"]: i for i in (await _full(client, cid))["items"]}
    blade = next(i for i in items.values() if i["name"] == "Spada lunga del patto")
    assert blade["is_equipped"] and blade["equipment_slot"] == "main_hand"
    meta = json.loads(blade["item_metadata"]) if isinstance(blade["item_metadata"], str) else blade["item_metadata"]
    assert meta["damage_dice"] == "1d8" and meta["damage_type"] == "slashing" and meta["pact_weapon"] is True
    assert not items[old]["is_equipped"]
    attack = await client.post(f"/characters/{cid}/items/{blade['id']}/attack", json={"die": 12, "confirm_extra_attack": True})
    assert attack.status_code == 200 and attack.json()["is_magic"] is True


async def test_a_new_blade_replaces_the_old_one(client):
    cid = await _warlock(client, 3)
    await _resolve(client, cid, "pact_boon", ["blade"])
    await _use(client, cid, BLADE_USE, params={"weapon": "longsword"})
    await _new_turn(client, cid)
    await _use(client, cid, BLADE_USE, params={"weapon": "dagger"})
    names = [i["name"] for i in (await _full(client, cid))["items"] if "del patto" in i["name"]]
    assert names == ["Pugnale del patto"]


async def test_the_blade_is_not_offered_without_the_blade_boon(client):
    cid = await _warlock(client, 3)
    await _resolve(client, cid, "pact_boon", ["chain"])
    assert BLADE_USE not in await _keys_of(client, cid)


async def _blade(client, cid, form="longsword") -> int:
    assert (await _use(client, cid, BLADE_USE, params={"weapon": form})).status_code == 200
    await _new_turn(client, cid)
    return next(i["id"] for i in (await _full(client, cid))["items"] if "del patto" in i["name"])


@pytest.mark.parametrize("charisma,extra", [(18, 4), (10, 1), (6, 1)])
async def test_lifedrinker_adds_necrotic_damage_equal_to_charisma_with_a_minimum_of_one(client, charisma, extra):
    cid = await _caster(client, 12, "lifedrinker", boon="blade", charisma=charisma)
    blade = await _blade(client, cid)
    assert "warlock.lifedrinker" in await _keys(client, cid, "attack", item_id=blade)
    plain = await _hit(client, cid, blade)
    r = await client.post(f"/characters/{cid}/attack/{plain['attack_id']}/damage", json={"options": ["warlock.lifedrinker"], "main_rolls": [4]})
    assert r.status_code == 200, r.text
    base = await _hit(client, cid, blade)
    r0 = await client.post(f"/characters/{cid}/attack/{base['attack_id']}/damage", json={"main_rolls": [4]})
    assert r.json()["damage_bonus"] == r0.json()["damage_bonus"] + extra


async def test_lifedrinker_does_not_apply_to_other_weapons(client):
    cid = await _caster(client, 12, "lifedrinker", boon="blade")
    other = await _weapon(client, cid, "Ascia", "main_hand")
    assert "warlock.lifedrinker" not in await _keys(client, cid, "attack", item_id=other)


async def _swing(client, cid, item_id=None):
    """Un attacco senza la conferma dell'attacco extra: vale il limite dell'azione."""
    url = f"/characters/{cid}/attack/unarmed" if item_id is None else f"/characters/{cid}/items/{item_id}/attack"
    return await client.post(url, json={"die": 15})


async def test_thirsting_blade_gives_two_attacks_with_the_pact_weapon_only(client):
    cid = await _caster(client, 5, "thirsting_blade", boon="blade")
    blade, axe = await _blade(client, cid), await _weapon(client, cid, "Ascia", "main_hand")
    assert (await _swing(client, cid, blade)).status_code == 200
    assert (await _swing(client, cid, blade)).status_code == 200  # il secondo attacco, con l'arma del patto
    assert (await _swing(client, cid, blade)).status_code == 409
    await _new_turn(client, cid)
    assert (await _swing(client, cid, blade)).status_code == 200
    for other in (axe, None):  # un'altra arma o il colpo senz'armi non hanno il secondo attacco
        r = await _swing(client, cid, other)
        assert r.status_code == 409 and r.json()["detail"]["code"] == "attack_limit"


async def test_thirsting_blade_does_not_stack_with_extra_attack(client):
    cid = await _caster(client, 5, "thirsting_blade", boon="blade")
    blade = await _blade(client, cid)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 5})
    assert r.status_code in (200, 201), r.text
    for _ in range(2):
        assert (await _swing(client, cid, blade)).status_code == 200
    assert (await _swing(client, cid, blade)).status_code == 409


# ---------------------------------------------------------------------------
# Patto della Catena
# ---------------------------------------------------------------------------

async def test_the_chain_gives_find_familiar_as_a_free_ritual_and_spends_an_attack_for_the_familiar(client):
    cid = await _warlock(client, 3)
    await _resolve(client, cid, "pact_boon", ["chain"])
    familiar = (await _spells_by_index(client, cid))["find-familiar"]
    assert familiar["always_prepared"] is True
    limits = (await _full(client, cid))["spellcasting"]["limits"][0]
    assert limits["known_count"] == 0  # non conta fra i conosciuti
    assert (await _use(client, cid, "warlock.pact_of_the_chain")).status_code == 200
    assert (await _turn(client, cid))["action_attacks"] == 1
    assert (await _use(client, cid, "warlock.pact_of_the_chain")).status_code == 409  # un solo attacco: non ne restano


# ---------------------------------------------------------------------------
# Tutt'Uno con le Ombre, Sguardo delle Due Menti, Vigore Immondo
# ---------------------------------------------------------------------------

async def test_one_with_shadows_asks_for_the_light_and_ends_on_an_attack_or_a_cast(client):
    cid = await _caster(client, 5, "one_with_shadows")
    assert (await _use(client, cid, "warlock.one_with_shadows")).status_code == 422
    assert (await _use(client, cid, "warlock.one_with_shadows", params={"light": "bright"})).status_code == 422
    r = await _use(client, cid, "warlock.one_with_shadows", params={"light": "dim"})
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    assert full["conditions"]["invisible"] is True and any(s["key"] == "one_with_shadows" for s in full["active_states"])
    spell = await _spell(client, cid, "Tocco", 1)
    await _cast(client, cid, spell, slot_level=3)
    assert not (await _full(client, cid))["conditions"].get("invisible")


async def test_gaze_of_two_minds_blinds_and_deafens_until_the_end_of_the_next_turn_and_renews(client):
    cid = await _caster(client, 2, "gaze_of_two_minds")
    assert (await _use(client, cid, "warlock.gaze_of_two_minds")).status_code == 200
    full = await _full(client, cid)
    assert full["conditions"]["blinded"] is True and full["conditions"]["deafened"] is True
    await _new_turn(client, cid)  # comincia il turno dopo: la condizione c'è ancora
    assert (await _full(client, cid))["conditions"]["blinded"] is True
    assert (await _use(client, cid, "warlock.gaze_of_two_minds")).status_code == 200  # rinnovo con l'azione
    await _new_turn(client, cid)
    assert (await _full(client, cid))["conditions"]["blinded"] is True
    await _new_turn(client, cid)
    full = await _full(client, cid)
    assert not full["conditions"].get("blinded") and not full["conditions"].get("deafened")


async def test_gaze_of_two_minds_keeps_a_blindness_the_character_already_had(client):
    cid = await _caster(client, 2, "gaze_of_two_minds")
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"blinded": True}})
    await _use(client, cid, "warlock.gaze_of_two_minds")
    await _new_turn(client, cid)
    await _new_turn(client, cid)
    assert (await _full(client, cid))["conditions"]["blinded"] is True


async def test_fiendish_vigor_gives_1d4_plus_4_temporary_hit_points_without_adding_them_up(client):
    cid = await _caster(client, 2, "fiendish_vigor")
    r = await _use(client, cid, "warlock.fiendish_vigor")
    assert r.status_code == 200, r.text
    got = r.json()["temp_hp"]
    assert 5 <= got <= 8 and (await _full(client, cid))["temp_hp"] == got
    assert (await _turn(client, cid))["action_used"] is True
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_temp", "value": 20})
    await _new_turn(client, cid)
    await _use(client, cid, "warlock.fiendish_vigor")
    assert (await _full(client, cid))["temp_hp"] == 20
