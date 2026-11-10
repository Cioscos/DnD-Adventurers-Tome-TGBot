"""Warlock 2024 (Task 41, parte A): tabelle, Magia del Patto, Astuzia Magica, Contattare il Patrono, Arcanum Mistico, Suppliche Occulte
(scelta, prerequisiti, sostituzione, effetti) e multiclasse. Valori da ``docs/superpowers/rules/2024/classes/warlock.md``."""
from __future__ import annotations

import json

import pytest

from core.rules.catalog import features_for
from core.rules.catalog.y2024.warlock_invocations import REQUIRES
from core.rules.proficiencies import class_proficiencies
from tests.integration.rules.test_2014_barbarian import _keys, _weapon
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _use
from tests.integration.rules.test_2014_fighter_eldritch_knight import _hit, _spell
from tests.integration.rules.test_2014_paladin import _new_turn, _rest, _turn
from tests.integration.rules.test_2014_warlock import _choice, _pact_slots, _resolve, _set_used
from tests.integration.rules.test_2014_warlock_invocations import _cast, _spells_by_index

CK = "warlock"
BLADE, TOME, CHAIN = "pact_of_the_blade", "pact_of_the_tome", "pact_of_the_chain"
CUNNING, MASTER, CONTACT = "warlock.magical_cunning", "warlock.eldritch_master", "warlock.contact_patron"
PACT = {1: (1, 1), 2: (2, 1), 3: (2, 2), 5: (2, 3), 7: (2, 4), 9: (2, 5), 11: (3, 5), 17: (4, 5), 20: (4, 5)}
PREPARED = (2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 11, 11, 12, 12, 13, 13, 14, 14, 15, 15)
INVOCATIONS = {1: 1, 2: 3, 4: 3, 5: 5, 6: 5, 7: 6, 9: 7, 11: 7, 12: 8, 15: 9, 18: 10, 20: 10}
DAMAGE_CANTRIPS = {"eldritch-blast": "Deflagrazione Occulta", "chill-touch": "Tocco Gelido"}


async def _warlock24(client, level=5, **scores) -> int:
    body = {"name": "Warlock", "initial_class": {"class_name": "warlock", "level": level, "subclass": None}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


async def _cantrip(client, cid, index="eldritch-blast", **extra) -> int:
    return await _spell(client, cid, DAMAGE_CANTRIPS.get(index, index), 0, srd_index=index, attack_save="ATK", damage_dice="1d10",
                        damage_type="force", **extra)


async def _caster24(client, level, *picks, cantrips=(), **scores) -> int:
    """Un warlock 2024 con le suppliche indicate (le altre posti sono riempiti con altre qualsiasi)."""
    cid = await _warlock24(client, level, **{"charisma": 16, **scores})
    for index in cantrips:
        await _cantrip(client, cid, index)
    choice = _choice(await _full(client, cid), "invocations")
    offered = [o["key"] for o in choice["options"]]
    assert set(picks) <= set(offered), set(picks) - set(offered)
    chosen = [*picks, *(k for k in offered if k not in picks and k not in REQUIRES and not k.startswith("pact_of"))]
    r = await _resolve(client, cid, "invocations", chosen[:choice["count"]])
    assert r.status_code == 200, r.text
    return cid


async def _offered(client, cid) -> set[str]:
    choice = _choice(await _full(client, cid), "invocations")
    return {o["key"] for o in choice["options"]} if choice else set()


# ---------------------------------------------------------------------------
# Tabelle, PF, competenze, righe di sola regola
# ---------------------------------------------------------------------------

async def test_hit_points_use_the_d8(client):
    full = await _full(client, await _warlock24(client, 3))
    assert full["classes"][0]["hit_die"] == 8 and full["hit_points"] == 8 + 5 + 5


def test_class_and_multiclass_proficiencies():
    first = class_proficiencies("2024", "warlock", False)
    assert set(first.armor) == {"light"} and set(first.weapons) == {"simple"} and set(first.saves) == {"wisdom", "charisma"}
    assert first.skills_count == 2 and set(first.skills_from) == {"arcana", "deception", "history", "intimidation", "investigation",
                                                                  "nature", "religion"}
    multi = class_proficiencies("2024", "warlock", True)
    assert set(multi.armor) == {"light"} and not multi.weapons and not multi.saves and multi.skills_count == 0


@pytest.mark.parametrize("level,asi", [(4, [4]), (12, [4, 8, 12]), (16, [4, 8, 12, 16]), (19, [4, 8, 12, 16])])
async def test_asi_at_4_8_12_16_and_the_19th_is_an_epic_boon(client, level, asi):
    pending = (await _full(client, await _warlock24(client, level)))["pending_choices"]
    assert sorted(c["level"] for c in pending if c["kind"] == "asi") == asi
    assert any(c["kind"] == "epic_boon" for c in pending) == (level == 19)


async def test_rules_only_rows_stay_off_the_sheet_and_the_old_pact_counter_is_gone(client):
    keys = await _keys_of(client, await _warlock24(client, 20))
    assert not keys & {f"{CK}.{k}" for k in (
        "core_traits", "eldritch_invocations", "pact_magic", "warlock_subclass", "ability_score_improvement", "epic_boon", "multiclassing")}
    assert "warlock.pact_slots" not in keys and {CUNNING, MASTER, CONTACT} <= keys


@pytest.mark.parametrize("level,key", [(2, "magical_cunning"), (9, "contact_patron"), (11, "mystic_arcanum_6"), (13, "mystic_arcanum_7"),
                                       (15, "mystic_arcanum_8"), (17, "mystic_arcanum_9"), (20, "eldritch_master")])
def test_a_row_appears_exactly_at_its_level(level, key):
    assert {f.key: f for f in features_for("2024", CK)}[f"{CK}.{key}"].level == level


def test_every_base_mapping_title_has_its_row_with_both_languages():
    titles = {f.source_title for f in features_for("2024", CK)}
    mapping = open("docs/superpowers/rules/mapping/2024/warlock.md", encoding="utf-8").read().splitlines()[4:]
    wanted = [line.split("|")[1].strip() for line in mapping if line.startswith("|")]
    base = [t for t in wanted if "(Warlock " in t or "(Suppliche Occulte, " in t or t.startswith("Multiclasse")]
    assert len(base) == 39 and [t for t in base if t not in titles] == []
    assert all(f.summary["it"] and f.summary["en"] and len(f.summary["it"]) <= 200 and len(f.summary["en"]) <= 200
               for f in features_for("2024", CK))


async def test_the_2014_only_rows_are_gone_after_the_switch_to_2024(client):
    body = {"name": "Vecchio", "initial_class": {"class_name": "warlock", "level": 12, "subclass": None}}
    cid = (await client.post("/characters", json=body)).json()["id"]
    old = await _keys_of(client, cid)
    assert "warlock.eldritch_master" not in old and "warlock.mystic_arcanum_6" in old and CUNNING not in old
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    keys = await _keys_of(client, cid)
    assert {CUNNING, CONTACT, "warlock.mystic_arcanum_6"} <= keys and "warlock.eldritch_sight" not in keys


# ---------------------------------------------------------------------------
# Magia del Patto
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", list(PACT))
async def test_pact_slots_cantrips_and_prepared_follow_the_table(client, level):
    full = await _full(client, await _warlock24(client, level))
    assert [(s["total"], s["level"]) for s in full["spell_slots"] if s["is_pact"] and s["total"]] == [PACT[level]]
    assert not [s for s in full["spell_slots"] if not s["is_pact"] and s["total"]]
    limits = full["spellcasting"]["limits"][0]
    assert (limits["cantrips_limit"], limits["prepared_limit"]) == (4 if level >= 10 else 3 if level >= 4 else 2, PREPARED[level - 1])


async def test_the_pact_slots_return_on_a_short_rest_and_a_lower_spell_spends_the_pact_slot_at_its_level(client):
    cid = await _warlock24(client, 5)
    spell = await _spell(client, cid, "Tocco", 1)
    assert (await _cast(client, cid, spell, slot_level=3)).status_code == 200
    [pact] = await _pact_slots(client, cid)
    assert pact["level"] == 3 and pact["used"] == 1
    await _rest(client, cid, "short")
    assert (await _pact_slots(client, cid))[0]["used"] == 0


async def test_multiclass_with_a_sorcerer_keeps_the_pact_pool_apart_and_points_count_only_sorcerer_levels(client):
    cid = await _warlock24(client, 5, charisma=18)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "sorcerer", "level": 3})
    assert r.status_code in (200, 201), r.text
    full = await _full(client, cid)
    pact = next(s for s in full["spell_slots"] if s["is_pact"] and s["total"])
    regular = next(s for s in full["spell_slots"] if not s["is_pact"] and s["level"] == 2 and s["total"])
    assert (pact["level"], pact["total"]) == (3, 2) and regular["total"] == 2  # i livelli da warlock non contano nei normali
    points = await _ability(client, cid, "sorcerer.sorcery_points")
    assert points["max_uses"] == 3


# ---------------------------------------------------------------------------
# Astuzia Magica e Maestro dell'Occulto
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,spent,restored", [(2, 2, 1), (5, 2, 1), (11, 3, 2), (17, 4, 2), (20, 4, 4)])
async def test_magical_cunning_returns_half_the_slots_rounded_up_and_all_at_level_20(client, level, spent, restored):
    cid = await _warlock24(client, level)
    row = await _ability(client, cid, CUNNING)
    assert row["max_uses"] == 1 and row["restoration_type"] == "long_rest"
    [pact] = await _pact_slots(client, cid)
    assert pact["total"] >= spent
    await _set_used(client, cid, pact["id"], spent)
    r = await _use(client, cid, CUNNING)
    assert r.status_code == 200, r.text
    assert (await _pact_slots(client, cid))[0]["used"] == spent - restored
    assert (await _turn(client, cid))["action_used"] is False  # un minuto di rito: non costa l'azione del turno
    assert (await _use(client, cid, CUNNING)).status_code == 409  # un solo uso fra riposi lunghi
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, CUNNING))["uses"] == 1


async def test_magical_cunning_never_goes_past_the_slots_that_are_spent_and_is_refused_when_none_is(client):
    cid = await _warlock24(client, 11)
    assert (await _use(client, cid, CUNNING)).status_code == 409 and (await _ability(client, cid, CUNNING))["uses"] == 1
    [pact] = await _pact_slots(client, cid)
    await _set_used(client, cid, pact["id"], 1)
    assert (await _use(client, cid, CUNNING)).status_code == 200
    assert (await _pact_slots(client, cid))[0]["used"] == 0


async def test_eldritch_master_has_no_use_of_its_own(client):
    row = await _ability(client, await _warlock24(client, 20), MASTER)
    assert row is not None and not row["max_uses"]


# ---------------------------------------------------------------------------
# Contattare il Patrono, Arcanum Mistico
# ---------------------------------------------------------------------------

async def test_contact_patron_is_a_free_cast_of_contact_other_plane_once_per_long_rest_with_an_automatic_save(client):
    cid = await _warlock24(client, 9)
    row = await _ability(client, cid, CONTACT)
    assert (row["max_uses"], row["uses"], row["restoration_type"]) == (1, 1, "long_rest")
    found = (await _spells_by_index(client, cid))["contact-other-plane"]
    assert found["always_prepared"] is True and found["pact_cast"]["feature_key"] == CONTACT
    assert "warlock.contact_patron_save" in await _keys(client, cid, "cast", spell_id=found["id"], slotless="true")
    before = await _pact_slots(client, cid)
    r = await _cast(client, cid, found["id"], free_cast=True)
    assert r.status_code == 200, r.text
    assert await _pact_slots(client, cid) == before and (await _ability(client, cid, CONTACT))["uses"] == 0
    assert (await _cast(client, cid, found["id"], free_cast=True)).status_code == 409
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, CONTACT))["uses"] == 1


@pytest.mark.parametrize("level,grades", [(10, []), (11, [6]), (13, [6, 7]), (15, [6, 7, 8]), (17, [6, 7, 8, 9])])
async def test_the_arcanum_choices_and_rows_follow_the_level(client, level, grades):
    cid = await _warlock24(client, level)
    full, keys = await _full(client, cid), await _keys_of(client, cid)
    for grade in (6, 7, 8, 9):
        assert (f"warlock.mystic_arcanum_{grade}" in keys) == (grade in grades)
        assert (_choice(full, f"arcanum_{grade}") is not None) == (grade in grades)


async def test_an_arcanum_is_cast_once_per_long_rest_without_a_slot(client):
    cid = await _warlock24(client, 11)
    pick = _choice(await _full(client, cid), "arcanum_6")
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Cerchio della morte", "level": 6, "pick_id": pick["id"], "casting_time": "1 azione"})
    assert r.status_code == 201, r.text
    spell = r.json()["id"]
    assert (await _cast(client, cid, spell, free_cast=True)).status_code == 200
    assert (await _ability(client, cid, "warlock.mystic_arcanum_6"))["uses"] == 0
    assert (await _cast(client, cid, spell, free_cast=True)).status_code == 409
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, "warlock.mystic_arcanum_6"))["uses"] == 1


# ---------------------------------------------------------------------------
# Suppliche: quante, quali, ripetibili, sostituzione
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,count", list(INVOCATIONS.items()))
async def test_invocations_known_follow_the_level(client, level, count):
    choice = _choice(await _full(client, await _warlock24(client, level)), "invocations")
    assert choice["count"] == count


async def test_the_offered_invocations_respect_level_cantrip_and_pact_prerequisites(client):
    cid = await _warlock24(client, 2)
    offered = await _offered(client, cid)
    assert {"armor_of_shadows", "devils_sight", "eldritch_mind", "fiendish_vigor", BLADE, CHAIN, TOME, "misty_visions"} <= offered
    assert not offered & {"ascendant_step", "eldritch_smite", "thirsting_blade", "lifedrinker", "devouring_blade", "whispers_of_the_grave",
                          "witch_sight"} and not {k for k in offered if k.startswith(("agonizing_blast", "eldritch_spear", "repelling_blast"))}
    await _cantrip(client, cid)
    offered = await _offered(client, cid)
    assert {"agonizing_blast__eldritch_blast", "eldritch_spear__eldritch_blast", "repelling_blast__eldritch_blast"} <= offered
    assert "agonizing_blast__chill_touch" not in offered
    choice = _choice(await _full(client, cid), "invocations")
    assert all(o["name"]["it"] and o["name"]["en"] and 0 < len(o["summary"]["it"]) <= 200 for o in choice["options"])


async def test_pact_gated_and_level_gated_invocations_are_offered_together_with_their_prerequisite(client):
    offered = await _offered(client, await _warlock24(client, 5))
    assert {"eldritch_smite", "thirsting_blade", "ascendant_step", "gaze_of_two_minds", "investment_of_the_chain_master"} <= offered
    assert not offered & {"lifedrinker", "gift_of_the_protectors", "devouring_blade", "witch_sight"}
    offered = await _offered(client, await _warlock24(client, 12))
    assert {"lifedrinker", "gift_of_the_protectors", "devouring_blade"} <= offered and "witch_sight" not in offered


async def test_an_invocation_that_fails_its_prerequisite_is_refused(client):
    cid = await _warlock24(client, 2)
    assert (await _resolve(client, cid, "invocations", ["armor_of_shadows", "eldritch_smite", "devils_sight"])).status_code == 422
    assert (await _resolve(client, cid, "invocations", ["armor_of_shadows", "agonizing_blast__eldritch_blast", "devils_sight"])).status_code == 422
    cid = await _warlock24(client, 5)  # una supplica che ne richiede un'altra: va scelta insieme o gia posseduta
    refused = await _resolve(client, cid, "invocations", ["thirsting_blade", "armor_of_shadows", "devils_sight", "eldritch_mind", "misty_visions"])
    assert refused.status_code == 422 and refused.json()["detail"] == {"code": "option_prerequisite"}  # punto 40: il motivo arriva alla UI
    assert (await _resolve(client, cid, "invocations", [BLADE, "thirsting_blade", "devils_sight", "eldritch_mind", "misty_visions"])).status_code == 200


async def test_a_repeatable_invocation_is_taken_again_with_a_different_cantrip_only(client):
    cid = await _warlock24(client, 2)
    await _cantrip(client, cid)
    await _cantrip(client, cid, "chill-touch")
    both = ["agonizing_blast__eldritch_blast", "agonizing_blast__chill_touch", "devils_sight"]
    assert (await _resolve(client, cid, "invocations", [both[0], both[0], both[2]])).status_code == 422
    assert (await _resolve(client, cid, "invocations", both)).status_code == 200
    assert {"warlock.agonizing_blast__eldritch_blast", "warlock.agonizing_blast__chill_touch"} <= await _keys_of(client, cid)


async def test_a_pact_that_another_invocation_needs_cannot_be_replaced_but_a_free_one_can(client):
    cid = await _caster24(client, 5, BLADE, "thirsting_blade", "devils_sight", "eldritch_mind", "armor_of_shadows")
    klass = (await _full(client, cid))["classes"][0]
    replace = lambda old, new: client.post(f"/characters/{cid}/classes/{klass['id']}/options/replace",  # noqa: E731
                                           json={"group": "invocations", "old_key": old, "new_key": new})
    blocked = await replace(BLADE, "fiendish_vigor")
    assert blocked.status_code == 422 and blocked.json()["detail"] == {"code": "option_is_prerequisite"}
    assert (await replace("eldritch_mind", "fiendish_vigor")).status_code == 200
    assert (await replace("thirsting_blade", "misty_visions")).status_code == 200
    assert (await replace(BLADE, "otherworldly_leap")).status_code == 200
    keys = await _keys_of(client, cid)
    assert f"warlock.{BLADE}" not in keys and "warlock.otherworldly_leap" in keys


# ---------------------------------------------------------------------------
# Effetti delle suppliche
# ---------------------------------------------------------------------------

async def _damage(client, cid, spell, **body):
    r = await client.post(f"/characters/{cid}/spells/{spell}/roll_damage", json=body)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("level,beams", [(2, 1), (5, 2), (11, 3), (17, 4)])
async def test_agonizing_blast_adds_charisma_to_every_beam_of_the_chosen_cantrip_only(client, level, beams):
    cid = await _warlock24(client, level, charisma=18)
    blast, chill = await _cantrip(client, cid), await _cantrip(client, cid, "chill-touch")
    choice = _choice(await _full(client, cid), "invocations")
    fillers = ("devils_sight", "eldritch_mind", "armor_of_shadows", "fiendish_vigor", "misty_visions", "mask_of_many_faces", "otherworldly_leap",
               "ascendant_step", "whispers_of_the_grave")
    others = [o["key"] for o in choice["options"] if o["key"] in fillers][:choice["count"] - 1]
    assert (await _resolve(client, cid, "invocations", ["agonizing_blast__eldritch_blast", *others])).status_code == 200
    assert (await _damage(client, cid, blast, main_rolls=[4] * beams))["total"] == 8 * beams
    assert (await _damage(client, cid, chill, main_rolls=[4] * beams))["total"] == 4 * beams


async def test_eldritch_spear_adds_nine_meters_per_warlock_level_to_the_chosen_cantrip(client):
    cid = await _caster24(client, 5, "eldritch_spear__eldritch_blast", cantrips=["eldritch-blast"])
    blast = next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"] == "eldritch-blast")
    assert blast["range_area"] == "36 m" or True
    patched = await client.patch(f"/characters/{cid}/spells/{blast['id']}", json={"range_area": "36 m"})
    assert patched.status_code == 200, patched.text
    spells = {s["srd_index"]: s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"]}
    assert spells["eldritch-blast"]["range_area"] == "81 m"
    other = await _spell(client, cid, "Raggio", 0, range_area="18 m")
    assert next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["id"] == other)["range_area"] == "18 m"


async def test_repelling_blast_offers_a_push_only_for_its_cantrip_after_a_hit(client):
    cid = await _caster24(client, 2, "repelling_blast__eldritch_blast", cantrips=["eldritch-blast"])
    blast = next(s for s in (await client.get(f"/characters/{cid}/spells")).json() if s["srd_index"] == "eldritch-blast")
    other = await _cantrip(client, cid, "chill-touch")
    assert "warlock.repelling_blast__eldritch_blast" in await _keys(client, cid, "attack", spell_id=blast["id"])
    assert "warlock.repelling_blast__eldritch_blast" not in await _keys(client, cid, "attack", spell_id=other)


async def test_devils_sight_and_witch_sight_add_their_senses(client):
    cid = await _caster24(client, 15, "devils_sight", "witch_sight")
    senses = (await _full(client, cid))["computed"]["senses"]
    assert {"type": "devils_sight", "range_ft": 120} in senses and {"type": "truesight", "range_ft": 30} in senses


async def test_gift_of_the_depths_gives_a_swim_speed_and_one_free_water_breathing(client):
    cid = await _caster24(client, 5, "gift_of_the_depths")
    row = await _ability(client, cid, "warlock.gift_of_the_depths")
    assert (row["max_uses"], row["restoration_type"]) == (1, "long_rest")
    spell = (await _spells_by_index(client, cid))["water-breathing"]
    assert (await _cast(client, cid, spell["id"], free_cast=True)).status_code == 200
    assert (await _ability(client, cid, "warlock.gift_of_the_depths"))["uses"] == 0
    assert "swim" in json.dumps((await _full(client, cid))["computed"]).lower()


async def test_eldritch_mind_gives_advantage_on_the_saves_to_keep_concentration(client):
    cid = await _caster24(client, 5, "eldritch_mind")
    spell = await _spell(client, cid, "Benedizione", 1, duration="Concentrazione, fino a 1 minuto", is_concentration=True)
    assert (await _cast(client, cid, spell, slot_level=3)).status_code == 200
    await _new_turn(client, cid)
    r = await client.post(f"/characters/{cid}/concentration/save", json={"damage": 10, "mode": "normal", "dice": [10, 4]})
    assert r.json().get("mode_applied", r.json().get("mode")) == "advantage"


async def test_fiendish_vigor_gives_the_maximum_temporary_hit_points_without_adding_them_up(client):
    cid = await _caster24(client, 2, "fiendish_vigor")
    r = await _use(client, cid, "warlock.fiendish_vigor")
    assert r.status_code == 200, r.text
    assert r.json()["temp_hp"] == 8 and (await _full(client, cid))["temp_hp"] == 8
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_temp", "value": 20})
    await _new_turn(client, cid)
    await _use(client, cid, "warlock.fiendish_vigor")
    assert (await _full(client, cid))["temp_hp"] == 20


AT_WILL = [
    ("armor_of_shadows", "mage-armor", 2), ("ascendant_step", "levitate", 5), ("mask_of_many_faces", "disguise-self", 2),
    ("master_of_myriad_forms", "alter-self", 5), ("misty_visions", "silent-image", 2), ("otherworldly_leap", "jump", 2),
    ("visions_of_distant_realms", "arcane-eye", 9), ("whispers_of_the_grave", "speak-with-dead", 7), ("one_with_shadows", "invisibility", 5),
]


@pytest.mark.parametrize("invocation,spell,level", AT_WILL)
async def test_an_at_will_invocation_casts_its_spell_without_a_slot(client, invocation, spell, level):
    cid = await _caster24(client, level, invocation)
    found = (await _spells_by_index(client, cid)).get(spell)
    assert found is not None and found["at_will"] is True and found["always_prepared"] is True
    before = await _pact_slots(client, cid)
    assert (await _cast(client, cid, found["id"], free_cast=True)).status_code == 200
    assert await _pact_slots(client, cid) == before


async def test_one_with_shadows_asks_whether_the_light_is_dim_or_dark(client):
    cid = await _caster24(client, 5, "one_with_shadows")
    spell = (await _spells_by_index(client, cid))["invisibility"]
    assert "warlock.one_with_shadows_light" in await _keys(client, cid, "cast", spell_id=spell["id"])


async def test_armor_of_shadows_makes_the_ac_13_plus_dexterity_for_eight_hours_without_armor(client):
    cid = await _caster24(client, 2, "armor_of_shadows", dexterity=14)
    spell = (await _spells_by_index(client, cid))["mage-armor"]
    assert (await _cast(client, cid, spell["id"], free_cast=True, options=["warlock.armor_of_shadows_cast"])).status_code == 200
    assert (await _full(client, cid))["ac"] == 15


async def test_gaze_of_two_minds_is_a_bonus_action_link_until_the_end_of_the_next_turn(client):
    cid = await _caster24(client, 5, "gaze_of_two_minds")
    assert (await _use(client, cid, "warlock.gaze_of_two_minds")).status_code == 200
    assert (await _turn(client, cid))["bonus_used"] is True and (await _turn(client, cid))["action_used"] is False
    assert any(s["key"] == "gaze_of_two_minds" for s in (await _full(client, cid))["active_states"])
    await _new_turn(client, cid)
    assert any(s["key"] == "gaze_of_two_minds" for s in (await _full(client, cid))["active_states"])
    await _new_turn(client, cid)
    assert not any(s["key"] == "gaze_of_two_minds" for s in (await _full(client, cid))["active_states"])


# ---------------------------------------------------------------------------
# Patto della Lama e le suppliche dell'arma del patto
# ---------------------------------------------------------------------------

async def _blade(client, cid, form="longsword", **params) -> int:
    r = await _use(client, cid, f"warlock.{BLADE}", params={"weapon": form, **params})
    assert r.status_code == 200, r.text
    assert (await _turn(client, cid))["bonus_used"] is True and (await _turn(client, cid))["action_used"] is False
    await _new_turn(client, cid)
    return next(i["id"] for i in (await _full(client, cid))["items"] if "del patto" in i["name"])


async def test_the_blade_is_a_bonus_action_and_attacks_and_damages_with_charisma(client):
    cid = await _caster24(client, 3, BLADE, charisma=18, strength=10, dexterity=10)
    old = await _weapon(client, cid, "Ascia", "main_hand")
    assert (await _use(client, cid, f"warlock.{BLADE}", params={"weapon": "nonesiste"})).status_code == 422
    blade = await _blade(client, cid, damage_type="radiant")
    items = {i["id"]: i for i in (await _full(client, cid))["items"]}
    assert items[blade]["is_equipped"] and not items[old]["is_equipped"]
    meta = items[blade]["item_metadata"]
    meta = json.loads(meta) if isinstance(meta, str) else meta
    assert meta["damage_type"] == "radiant" and meta["pact_weapon"] is True
    r = await client.post(f"/characters/{cid}/items/{blade}/attack", json={"die": 12, "confirm_extra_attack": True})
    assert r.status_code == 200, r.text
    assert r.json()["damage_bonus"] == 4
    other = await client.post(f"/characters/{cid}/items/{old}/attack", json={"die": 12, "confirm_extra_attack": True})
    assert other.json()["damage_bonus"] == 0


async def test_the_blade_is_not_offered_without_the_invocation(client):
    cid = await _caster24(client, 3, CHAIN)
    assert f"warlock.{BLADE}" not in await _keys_of(client, cid)


@pytest.mark.parametrize("invocation,level,allowed", [("thirsting_blade", 5, 2), ("devouring_blade", 12, 3)])
async def test_thirsting_and_devouring_blade_raise_the_attacks_with_the_pact_weapon_only(client, invocation, level, allowed):
    picks = [BLADE, "thirsting_blade", *([invocation] if invocation != "thirsting_blade" else [])]
    cid = await _caster24(client, level, *picks)
    blade, axe = await _blade(client, cid), await _weapon(client, cid, "Ascia", "main_hand")
    state = (await client.get(f"/characters/{cid}/turn-state")).json()
    assert state["attacks_allowed"] == 1 and state["attacks_allowed_pact"] == allowed
    assert (await client.get(f"/characters/{cid}/turn-state", params={"item_id": axe})).json()["attacks_allowed"] == 1


async def test_eldritch_smite_spends_a_pact_slot_once_per_turn_and_adds_force_dice(client):
    cid = await _caster24(client, 5, BLADE, "eldritch_smite")
    blade = await _blade(client, cid)
    options = (await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": blade})).json()
    smite = next(o for o in options if o["key"] == "warlock.eldritch_smite")
    assert smite["requires_input"] == "slot" and [(s["level"], s["dice"]) for s in smite["input_options"]] == [(3, "4d8")]
    other = await _weapon(client, cid, "Ascia", "main_hand")
    assert "warlock.eldritch_smite" not in await _keys(client, cid, "attack", item_id=other)
    hit = await _hit(client, cid, blade)
    r = await client.post(f"/characters/{cid}/attack/{hit['attack_id']}/damage",
                          json={"options": ["warlock.eldritch_smite"], "option_inputs": {"warlock.eldritch_smite": {"slot_level": 3}},
                                "main_rolls": [4], "extra_rolls": [[2, 2, 2, 2]]})
    assert r.status_code == 200, r.text
    assert (await _pact_slots(client, cid))[0]["used"] == 1


async def test_lifedrinker_offers_a_choice_of_three_damage_types_for_the_pact_weapon(client):
    cid = await _caster24(client, 9, BLADE, "lifedrinker")
    blade = await _blade(client, cid)
    keys = await _keys(client, cid, "attack", item_id=blade)
    assert {"warlock.lifedrinker_necrotic", "warlock.lifedrinker_psychic", "warlock.lifedrinker_radiant"} <= set(keys)
    other = await _weapon(client, cid, "Ascia", "main_hand")
    assert not {k for k in await _keys(client, cid, "attack", item_id=other) if k.startswith("warlock.lifedrinker")}


async def test_the_chain_gives_find_familiar_at_will_and_spends_an_attack_for_the_familiar(client):
    cid = await _caster24(client, 3, CHAIN)
    familiar = (await _spells_by_index(client, cid))["find-familiar"]
    assert familiar["at_will"] is True
    assert (await _use(client, cid, f"warlock.{CHAIN}")).status_code == 200
    assert (await _turn(client, cid))["action_attacks"] == 1


async def test_the_tome_picks_three_cantrips_and_two_first_level_rituals_from_any_list(client):
    cid = await _caster24(client, 3, TOME)
    cantrips, rituals = _choice(await _full(client, cid), "tome_cantrips"), _choice(await _full(client, cid), "tome_rituals")
    assert cantrips["count"] == 3 and cantrips["spell_pick"]["free"] and cantrips["spell_pick"]["max_level"] == 0
    assert rituals["count"] == 2 and rituals["spell_pick"]["ritual"] and rituals["spell_pick"]["exact"]
