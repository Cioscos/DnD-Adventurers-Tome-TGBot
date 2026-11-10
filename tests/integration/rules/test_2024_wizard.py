"""Mago 2024 (Task 42, parte A): tabelle, competenze, Libro degli Incantesimi, Adepto dei Rituali, Recupero Arcano, Studioso,
Memorizzare Incantesimo, Maestria negli Incantesimi, Dono Epico, Incantesimi Personali e multiclasse.
Valori da ``docs/superpowers/rules/2024/classes/wizard.md``. Nessun d20 casuale."""
from __future__ import annotations

import asyncio

import pytest

from core.rules.catalog import features_for
from core.rules.proficiencies import class_proficiencies
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _resolve, _skills
from tests.integration.rules.test_2014_fighter_eldritch_knight import _cast, _spell
from tests.integration.rules.test_2014_paladin import _rest
from tests.integration.rules.test_2014_wizard import _book, _choice, _gold, _prepare, _purse, _short, _spells, _spend, _used

ARCANE, MEMORIZE, SIG1, SIG2 = "wizard.arcane_recovery", "wizard.memorize_spell", "wizard.signature_spell_1", "wizard.signature_spell_2"
SLOTS = {1: (2,), 2: (3,), 3: (4, 2), 5: (4, 3, 2), 9: (4, 3, 3, 3, 1), 17: (4, 3, 3, 3, 2, 1, 1, 1, 1), 20: (4, 3, 3, 3, 3, 2, 2, 1, 1)}
PREPARED = (4, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16, 16, 17, 18, 19, 21, 22, 23, 24, 25)
SCHOLAR = {"arcana", "history", "investigation", "medicine", "nature", "religion"}
RITUAL = {"is_ritual": True, "casting_time": "1 azione"}


async def _wizard24(client, level=5, **scores) -> int:
    body = {"name": "Mago", "initial_class": {"class_name": "wizard", "level": level, "subclass": None}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


async def _rest_memorize(client, cid, out, into):
    return await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "memorize_spell": {"out": out, "into": into}})


# ---------------------------------------------------------------------------
# Tabelle, PF, competenze, righe di sola regola
# ---------------------------------------------------------------------------

async def test_hit_points_use_the_d6(client):
    full = await _full(client, await _wizard24(client, 3))
    assert full["classes"][0]["hit_die"] == 6 and full["hit_points"] == 6 + 4 + 4


def test_class_and_multiclass_proficiencies():
    first = class_proficiencies("2024", "wizard", False)
    assert not first.armor and not first.tools and set(first.weapons) == {"simple"} and set(first.saves) == {"intelligence", "wisdom"}
    assert first.skills_count == 2 and set(first.skills_from) == {"arcana", "history", "insight", "investigation", "medicine", "nature", "religion"}
    multi = class_proficiencies("2024", "wizard", True)
    assert not multi.armor and not multi.weapons and not multi.saves and multi.skills_count == 0


@pytest.mark.parametrize("level", list(SLOTS))
async def test_slots_cantrips_and_prepared_follow_the_table(client, level):
    full = await _full(client, await _wizard24(client, level))
    totals = tuple(s["total"] for s in sorted(full["spell_slots"], key=lambda s: s["level"]) if s["total"])
    assert totals == SLOTS[level]
    limits = full["spellcasting"]["limits"][0]
    assert (limits["cantrips_limit"], limits["prepared_limit"]) == (5 if level >= 10 else 4 if level >= 4 else 3, PREPARED[level - 1])


@pytest.mark.parametrize("level,asi", [(4, [4]), (12, [4, 8, 12]), (16, [4, 8, 12, 16]), (19, [4, 8, 12, 16])])
async def test_asi_at_4_8_12_16_and_the_19th_is_an_epic_boon(client, level, asi):
    pending = (await _full(client, await _wizard24(client, level)))["pending_choices"]
    assert sorted(c["level"] for c in pending if c["kind"] == "asi") == asi
    assert any(c["kind"] == "epic_boon" for c in pending) == (level == 19)


async def test_rules_only_rows_stay_off_the_sheet_and_the_real_ones_show(client):
    keys = await _keys_of(client, await _wizard24(client, 20))
    assert not keys & {f"wizard.{k}" for k in (
        "core_traits", "spellcasting", "spellbook", "expanding_spellbook", "ritual_adept", "scholar", "wizard_subclass",
        "ability_score_improvement", "spell_mastery", "epic_boon", "multiclassing")}
    assert {ARCANE, MEMORIZE, SIG1, SIG2} <= keys


@pytest.mark.parametrize("level,key", [(1, "arcane_recovery"), (2, "scholar"), (3, "wizard_subclass"), (5, "memorize_spell"),
                                       (18, "spell_mastery"), (19, "epic_boon"), (20, "signature_spell_1")])
def test_a_row_appears_exactly_at_its_level(level, key):
    assert {f.key: f for f in features_for("2024", "wizard")}[f"wizard.{key}"].level == level


def test_every_base_mapping_title_has_its_row_with_both_languages():
    titles = {f.source_title for f in features_for("2024", "wizard")}
    mapping = open("docs/superpowers/rules/mapping/2024/wizard.md", encoding="utf-8").read().splitlines()[4:]
    wanted = [line.split("|")[1].strip() for line in mapping if line.startswith("|")]
    base = [t for t in wanted if "(Mago " in t or t.startswith("Multiclasse")]
    assert len(base) == 14 and [t for t in base if t not in titles] == []
    assert all(f.summary["it"] and f.summary["en"] and len(f.summary["it"]) <= 200 and len(f.summary["en"]) <= 200
               for f in features_for("2024", "wizard"))


def test_the_subclass_module_is_hooked():
    from core.rules.catalog.y2024 import wizard, wizard_subclasses
    assert len(wizard_subclasses.SUBCLASS_ROWS) == 24 and len(wizard.FEATURES) == len(wizard.BASE_ROWS) + 24


# ---------------------------------------------------------------------------
# Libro degli Incantesimi
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,mode,hours,gold", [(1, "copy", 2, 50), (3, "copy", 6, 150), (1, "backup", 1, 10), (4, "backup", 4, 40),
                                                   (2, "retranscribe", 2, 20)])
async def test_the_copy_cost_is_per_spell_level(client, level, mode, hours, gold):
    cid = await _wizard24(client, 17)
    r = await client.get(f"/characters/{cid}/spellbook/cost", params={"level": level, "mode": mode})
    assert r.status_code == 200, r.text
    assert r.json() == {"hours": hours, "gold": gold, "halved": False}


async def test_a_2024_spell_is_outside_the_book_until_copied_and_the_gold_is_spent(client):
    cid = await _wizard24(client, 5)
    sid = await _spell(client, cid, "Palla di fuoco", 3)
    assert (await _spells(client, cid))["Palla di fuoco"]["in_spellbook"] is False
    assert (await _prepare(client, cid, sid)).status_code == 409  # fuori dal libro non si prepara
    await _gold(client, cid, 500)
    r = await client.post(f"/characters/{cid}/spells/{sid}/copy", json={"mode": "copy"})
    assert r.status_code == 200, r.text
    assert (await _spells(client, cid))["Palla di fuoco"]["in_spellbook"] is True and await _purse(client, cid) == 350
    assert (await _prepare(client, cid, sid)).status_code == 200


async def test_a_spell_above_the_slots_cannot_be_copied_and_a_cantrip_has_no_place_in_the_book(client):
    cid = await _wizard24(client, 3)
    await _gold(client, cid, 900)
    high = await _spell(client, cid, "Palla di fuoco", 3)
    r = await client.post(f"/characters/{cid}/spells/{high}/copy", json={"mode": "copy"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "spell_above_slots"
    cantrip = await _spell(client, cid, "Luce", 0)
    assert (await client.post(f"/characters/{cid}/spells/{cantrip}/copy", json={"mode": "copy"})).status_code == 422


async def test_a_lost_book_is_rewritten_only_for_prepared_spells(client):
    cid = await _wizard24(client, 5)
    await _gold(client, cid, 500)
    kept = await _book(client, cid, "Scudo", 1)
    lost = await _book(client, cid, "Sonno", 1)
    assert (await _prepare(client, cid, kept)).status_code == 200
    r = await client.post(f"/characters/{cid}/spellbook/lost")
    assert r.status_code == 200, r.text
    spells = await _spells(client, cid)
    assert not spells["Scudo"]["in_spellbook"] and not spells["Sonno"]["in_spellbook"]
    back = await client.post(f"/characters/{cid}/spells/{kept}/copy", json={"mode": "retranscribe"})
    assert back.status_code == 200, back.text
    refused = await client.post(f"/characters/{cid}/spells/{lost}/copy", json={"mode": "retranscribe"})
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "not_prepared"


@pytest.mark.parametrize("level,count", [(1, 6), (2, 8), (5, 14), (20, 44)])
async def test_the_book_choice_is_six_spells_then_two_per_level(client, level, count):
    assert _choice(await _full(client, await _wizard24(client, level)), "spellbook")["count"] == count


async def test_the_book_is_not_the_spellbook_of_another_class(client):
    cid = await _wizard24(client, 5)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "sorcerer", "level": 2})
    assert r.status_code in (200, 201), r.text
    klass = next(c["id"] for c in (await _full(client, cid))["classes"] if c["class_name"].lower() == "sorcerer")
    sid = await _spell(client, cid, "Raggio di gelo", 1, class_id=klass)
    refused = await client.post(f"/characters/{cid}/spells/{sid}/copy", json={"mode": "copy"})
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "not_a_wizard_spell"


# ---------------------------------------------------------------------------
# Adepto dei Rituali
# ---------------------------------------------------------------------------

async def test_a_book_ritual_is_cast_unprepared_but_one_outside_the_book_is_not(client):
    cid = await _wizard24(client, 5)
    await _gold(client, cid, 300)
    inside = await _book(client, cid, "Trova famiglio", 1, **RITUAL)
    outside = await _spell(client, cid, "Individuazione del magico", 1, **RITUAL)
    before = await _used(client, cid)
    ok = await _cast(client, cid, inside, as_ritual=True)
    assert ok.status_code == 200, ok.text
    assert await _used(client, cid) == before
    refused = await _cast(client, cid, outside, as_ritual=True)
    assert refused.status_code == 409 and refused.json()["detail"]["warnings"] == ["ritual_unprepared"]


# ---------------------------------------------------------------------------
# Recupero Arcano
# ---------------------------------------------------------------------------

async def test_arcane_recovery_is_a_single_use_pool_returning_on_a_long_rest(client):
    row = await _ability(client, await _wizard24(client, 1), ARCANE)
    assert (row["max_uses"], row["uses"], row["restoration_type"]) == (1, 1, "long_rest")


@pytest.mark.parametrize("level,fits,over", [(1, {"1": 1}, {"1": 2}), (4, {"1": 2}, {"2": 1, "1": 1}), (5, {"2": 1, "1": 1}, {"3": 1, "1": 1}),
                                             (20, {"5": 2}, {"5": 2, "1": 1})])
async def test_arcane_recovery_budget_is_half_the_wizard_level_rounded_up(client, level, fits, over):
    cid = await _wizard24(client, level)
    await _spend(client, cid, l1=4, l2=3, l3=3, l4=3, l5=2)
    refused = await _short(client, cid, over)
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "natural_recovery_cap"
    assert (await _short(client, cid, fits)).status_code == 200
    assert (await _ability(client, cid, ARCANE))["uses"] == 0
    again = await _short(client, cid, {"1": 1})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "no_uses"


async def test_arcane_recovery_never_returns_6th_level_slots_and_counts_wizard_levels_only(client):
    cid = await _wizard24(client, 20)
    await _spend(client, cid, l6=1)
    r = await _short(client, cid, {"6": 1})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "natural_recovery_level"
    multi = await _wizard24(client, 4)
    assert (await client.post(f"/characters/{multi}/classes", json={"class_name": "fighter", "level": 6})).status_code in (200, 201)
    await _spend(client, multi, l1=4)
    assert (await _short(client, multi, {"1": 3})).status_code == 422
    assert (await _short(client, multi, {"1": 2})).status_code == 200


async def test_two_arcane_recoveries_at_once_recover_once(client):
    cid = await _wizard24(client, 4)
    await _spend(client, cid, l1=4)
    first, second = await asyncio.gather(_short(client, cid, {"1": 2}), _short(client, cid, {"1": 2}))
    assert sorted([first.status_code, second.status_code]) == [200, 409] and (await _used(client, cid))[1] == 2


# ---------------------------------------------------------------------------
# Studioso
# ---------------------------------------------------------------------------

async def test_scholar_offers_only_the_six_skills_the_wizard_is_proficient_in_and_sets_expertise(client):
    cid = await _wizard24(client, 2)
    await _skills(client, cid, arcana=True, history="expert", insight=True, nature=True, stealth=True)
    pick = _choice(await _full(client, cid), "scholar")
    assert pick["count"] == 1 and {o["key"] for o in pick["options"]} == {"arcana", "nature"}  # niente Intuizione, Furtività, né già esperte
    for bad in (["insight"], ["stealth"], ["history"]):
        assert (await _resolve(client, cid, "scholar", bad)).status_code == 422
    r = await _resolve(client, cid, "scholar", ["nature"])
    assert r.status_code == 200, r.text
    assert r.json()["skills"]["nature"] == "expert" and _choice(await _full(client, cid), "scholar") is None


async def test_scholar_is_not_offered_before_level_2(client):
    assert _choice(await _full(client, await _wizard24(client, 1)), "scholar") is None


# ---------------------------------------------------------------------------
# Memorizzare Incantesimo
# ---------------------------------------------------------------------------

async def _memorize_setup(client, level=5):
    cid = await _wizard24(client, level)
    await _gold(client, cid, 500)
    ids = {"shield": await _book(client, cid, "Scudo", 1), "sleep": await _book(client, cid, "Sonno", 1)}
    if level >= 5:
        ids["fireball"] = await _book(client, cid, "Palla di fuoco", 3)
    assert (await _prepare(client, cid, ids["shield"])).status_code == 200
    return cid, ids


async def test_memorize_spell_swaps_one_prepared_spell_for_a_book_spell_at_a_short_rest(client):
    cid, ids = await _memorize_setup(client)
    r = await _rest_memorize(client, cid, ids["shield"], ids["sleep"])
    assert r.status_code == 200, r.text
    spells = await _spells(client, cid)
    assert spells["Scudo"]["is_prepared"] is False and spells["Sonno"]["is_prepared"] is True


@pytest.mark.parametrize("case", ["out_not_prepared", "into_already_prepared", "into_not_in_book", "into_above_slots", "always_prepared"])
async def test_memorize_spell_refuses_what_the_rules_do_not_allow_and_changes_nothing(client, test_session_factory, case):
    from core.db.models import Spell
    cid, ids = await _memorize_setup(client)
    high = await _spell(client, cid, "Metamorfosi", 4)
    async with test_session_factory() as s:  # nel libro, ma oltre gli slot (un livello perso dopo il calo di livello)
        (await s.get(Spell, high)).in_spellbook = True
        await s.commit()
    outside = await _spell(client, cid, "Dardo incantato", 1)
    extra = await _spell(client, cid, "Armatura magica", 1, always_prepared=True, is_prepared=True)
    out, into = {
        "out_not_prepared": (ids["sleep"], ids["sleep"]), "into_already_prepared": (ids["shield"], ids["shield"]),
        "into_not_in_book": (ids["shield"], outside), "into_above_slots": (ids["shield"], high),
        "always_prepared": (extra, ids["sleep"]),
    }[case]
    r = await _rest_memorize(client, cid, out, into)
    assert r.status_code == 422 and r.json()["detail"]["code"].startswith("memorize_"), r.text
    spells = await _spells(client, cid)
    assert spells["Scudo"]["is_prepared"] is True and spells["Sonno"]["is_prepared"] is False


async def test_memorize_spell_needs_level_5_the_feature_and_a_short_rest(client):
    low, ids = await _memorize_setup(client, 4)
    r = await _rest_memorize(client, low, ids["shield"], ids["sleep"])
    assert r.status_code == 422 and r.json()["detail"]["code"] == "memorize_unavailable"
    cid, ids = await _memorize_setup(client)
    long = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True,
                                                              "memorize_spell": {"out": ids["shield"], "into": ids["sleep"]}})
    assert long.status_code == 422 and long.json()["detail"]["code"] == "natural_recovery_short_only"
    assert (await _spells(client, cid))["Scudo"]["is_prepared"] is True


async def test_a_refused_memorize_does_not_spend_the_arcane_recovery_of_the_same_rest(client):
    cid, ids = await _memorize_setup(client)
    await _spend(client, cid, l1=2)
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "arcane_recovery": {"1": 1},
                                                           "memorize_spell": {"out": ids["sleep"], "into": ids["sleep"]}})
    assert r.status_code == 422
    assert (await _ability(client, cid, ARCANE))["uses"] == 1 and (await _used(client, cid))[1] == 2


# ---------------------------------------------------------------------------
# Maestria negli Incantesimi, Dono Epico, Incantesimi Personali
# ---------------------------------------------------------------------------

async def _master(client, level=18):
    cid = await _wizard24(client, level)
    await _gold(client, cid, 5000)
    ids = {"shield": await _book(client, cid, "Scudo", 1, srd_index="shield"),
           "ray": await _book(client, cid, "Raggio rovente", 2),
           "misty": await _book(client, cid, "Passo velato", 2, casting_time="1 azione bonus"),
           "fireball": await _book(client, cid, "Palla di fuoco", 3), "counter": await _book(client, cid, "Controincantesimo", 3)}
    return cid, ids


async def test_spell_mastery_offers_one_first_and_one_second_level_spell_cast_in_one_action(client):
    cid, _ = await _master(client)
    one, two = _choice(await _full(client, cid), "spell_mastery_1"), _choice(await _full(client, cid), "spell_mastery_2")
    assert [o["key"] for o in one["options"]] == ["Scudo"] and [o["key"] for o in two["options"]] == ["Raggio rovente"]  # niente azione bonus
    assert _choice(await _full(client, await _wizard24(client, 17)), "spell_mastery_1") is None


async def test_a_mastered_spell_is_always_prepared_outside_the_cap_and_cast_at_will_at_base_level(client):
    cid, ids = await _master(client)
    assert (await _resolve(client, cid, "spell_mastery_1", ["Scudo"])).status_code == 200
    spell = (await _spells(client, cid))["Scudo"]
    assert spell["always_prepared"] and spell["is_prepared"] and spell["at_will"] is True
    before = await _used(client, cid)
    for _ in range(3):
        cast = await _cast(client, cid, ids["shield"], free_cast=True)
        assert cast.status_code == 200, cast.text
        await client.post(f"/characters/{cid}/turn/new")
    assert await _used(client, cid) == before
    assert (await _cast(client, cid, ids["shield"], slot_level=2)).status_code == 200
    assert (await _used(client, cid))[2] == 1  # a livello superiore spende lo slot


async def test_spell_mastery_is_replaced_with_a_spell_of_the_same_level_and_the_old_one_is_no_longer_always_prepared(client):
    cid, ids = await _master(client)
    extra = await _book(client, cid, "Mani brucianti", 1, casting_time="1 azione")
    assert (await _resolve(client, cid, "spell_mastery_1", ["Scudo"])).status_code == 200
    klass = next(c["id"] for c in (await _full(client, cid))["classes"])
    url = f"/characters/{cid}/classes/{klass}/options/replace"
    assert (await client.post(url, json={"group": "spell_mastery_1", "old_key": "Scudo", "new_key": "Raggio rovente"})).status_code == 422
    r = await client.post(url, json={"group": "spell_mastery_1", "old_key": "Scudo", "new_key": "Mani brucianti"})
    assert r.status_code == 200, r.text
    spells = await _spells(client, cid)
    assert spells["Scudo"]["always_prepared"] is False and spells["Scudo"]["is_prepared"] is False
    assert spells["Mani brucianti"]["always_prepared"] is True and extra


async def test_the_19th_level_wizard_has_an_epic_boon_choice_and_no_asi_there(client):
    pending = (await _full(client, await _wizard24(client, 19)))["pending_choices"]
    assert [c["level"] for c in pending if c["kind"] == "epic_boon"] == [19] and 19 not in [c["level"] for c in pending if c["kind"] == "asi"]


async def test_signature_spells_are_two_third_level_book_spells_always_prepared_and_cast_once_free(client):
    cid, ids = await _master(client, 20)
    one = _choice(await _full(client, cid), "signature_1")
    assert {o["key"] for o in one["options"]} == {"Palla di fuoco", "Controincantesimo"}
    assert (await _resolve(client, cid, "signature_1", ["Palla di fuoco"])).status_code == 200
    assert [o["key"] for o in _choice(await _full(client, cid), "signature_2")["options"]] == ["Controincantesimo"]
    assert (await _resolve(client, cid, "signature_2", ["Controincantesimo"])).status_code == 200
    assert (await _spells(client, cid))["Palla di fuoco"]["always_prepared"]
    before = await _used(client, cid)
    assert (await _cast(client, cid, ids["fireball"], free_cast=True)).status_code == 200
    assert await _used(client, cid) == before
    assert (await _ability(client, cid, SIG1))["uses"] == 0 and (await _ability(client, cid, SIG2))["uses"] == 1
    await client.post(f"/characters/{cid}/turn/new")
    again = await _cast(client, cid, ids["fireball"], free_cast=True)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "no_uses"
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, SIG1))["uses"] == 1


# ---------------------------------------------------------------------------
# Multiclasse e cambio di edizione
# ---------------------------------------------------------------------------

async def test_multiclass_prepares_per_class_with_the_2024_table(client):
    cid = await _wizard24(client, 5)
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "cleric", "level": 4})).status_code in (200, 201)
    full = await _full(client, cid)
    assert tuple(s["total"] for s in sorted(full["spell_slots"], key=lambda s: s["level"]) if s["total"]) == (4, 3, 3, 3, 1)
    assert {c["class_name"]: c["prepared_limit"] for c in full["spellcasting"]["limits"]}["wizard"] == 9


async def test_a_2014_wizard_that_becomes_2024_keeps_its_book_and_gets_the_2024_rows(client):
    body = {"name": "Vecchio", "initial_class": {"class_name": "wizard", "level": 5, "subclass": None}}
    cid = (await client.post("/characters", json=body)).json()["id"]
    sid = await _spell(client, cid, "Scudo", 1)
    await _gold(client, cid, 100)
    assert (await client.post(f"/characters/{cid}/spells/{sid}/copy", json={"mode": "copy"})).status_code == 200
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    assert (await _spells(client, cid))["Scudo"]["in_spellbook"] is True
    assert {ARCANE, MEMORIZE} <= await _keys_of(client, cid)


async def test_minori_12_spell_mastery_is_replaced_once_per_long_rest(client):
    cid, _ids = await _master(client)
    await _book(client, cid, "Mani brucianti", 1, casting_time="1 azione")
    await _book(client, cid, "Dardo incantato", 1, casting_time="1 azione")
    assert (await _resolve(client, cid, "spell_mastery_1", ["Scudo"])).status_code == 200
    klass = next(c["id"] for c in (await _full(client, cid))["classes"])
    url = f"/characters/{cid}/classes/{klass}/options/replace"
    assert (await client.post(url, json={"group": "spell_mastery_1", "old_key": "Scudo", "new_key": "Mani brucianti"})).status_code == 200
    refused = await client.post(url, json={"group": "spell_mastery_1", "old_key": "Mani brucianti", "new_key": "Dardo incantato"})
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "replace_after_long_rest"
    await _rest(client, cid, "long")
    assert (await client.post(url, json={"group": "spell_mastery_1", "old_key": "Mani brucianti", "new_key": "Dardo incantato"})).status_code == 200
