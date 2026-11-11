"""Mago 2014 (Task 30): progressione, Libro degli Incantesimi, preparazione, rituali, scelte di incantesimi, Recupero Arcano,
Maestria negli Incantesimi, Incantesimi Personali, multiclasse."""
from __future__ import annotations

import pytest

from core.rules.catalog import features_for
from core.rules.proficiencies import class_proficiencies
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _spells
from tests.integration.rules.test_2014_fighter_eldritch_knight import _cast, _spell
from tests.integration.rules.test_2014_paladin import _rest

SCHOOLS = {"abjuration": "Scuola di Abiurazione", "enchantment": "Scuola di Ammaliamento", "divination": "Scuola di Divinazione",
           "conjuration": "Scuola di Evocazione", "illusion": "Scuola di Illusione", "evocation": "Scuola di Invocazione",
           "necromancy": "Scuola di Necromanzia", "transmutation": "Scuola di Trasmutazione"}
SLOTS = {1: (2,), 2: (3,), 3: (4, 2), 4: (4, 3), 5: (4, 3, 2), 9: (4, 3, 3, 3, 1), 11: (4, 3, 3, 3, 2, 1), 17: (4, 3, 3, 3, 2, 1, 1, 1, 1),
         20: (4, 3, 3, 3, 3, 2, 2, 1, 1)}
CANTRIPS = {1: 3, 3: 3, 4: 4, 9: 4, 10: 5, 20: 5}


async def _wizard(client, level=5, school=None, **scores) -> int:
    body = {"name": "Mago", "initial_class": {"class_name": "wizard", "level": level, "subclass": SCHOOLS.get(school)}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


def _choice(full: dict, group: str) -> dict | None:
    return next((c for c in full["pending_choices"] if c.get("group") == group), None)


async def _wizard_id(client, cid) -> int:
    return next(c["id"] for c in (await _full(client, cid))["classes"] if c["class_name"].lower() in ("wizard", "mago"))


async def _book(client, cid, name, level, **extra) -> int:
    """Un incantesimo di livello 1+ dell'elenco del mago, già nel libro (copiato), non preparato."""
    sid = await _spell(client, cid, name, level, **extra)
    r = await client.post(f"/characters/{cid}/spells/{sid}/copy", json={"mode": "copy"})
    assert r.status_code == 200, r.text
    return sid


async def _gold(client, cid, amount) -> None:
    r = await client.patch(f"/characters/{cid}/currency", json={"gold": amount})
    assert r.status_code == 200, r.text


async def _purse(client, cid) -> int:
    return (await _full(client, cid))["currency"]["gold"]


async def _prepare(client, cid, sid, value=True):
    return await client.patch(f"/characters/{cid}/spells/{sid}", json={"is_prepared": value})


# ---------------------------------------------------------------------------
# Progressione, PF, competenze
# ---------------------------------------------------------------------------

async def test_hit_points_use_the_d6_and_follow_constitution(client):
    full = await _full(client, await _wizard(client, 3))
    assert full["classes"][0]["hit_die"] == 6 and full["hit_points"] == 6 + 4 + 4


def test_class_proficiencies_first_class_and_multiclass():
    first = class_proficiencies("2014", "wizard", False)
    assert not first.armor and not first.tools and set(first.saves) == {"intelligence", "wisdom"}
    assert first.skills_count == 2 and set(first.skills_from) == {"arcana", "history", "insight", "investigation", "medicine", "religion"}
    multi = class_proficiencies("2014", "wizard", True)
    assert not multi.armor and not multi.tools and not multi.weapons and not multi.saves and multi.skills_count == 0


async def test_rules_only_rows_do_not_clutter_the_sheet(client):
    keys = await _keys_of(client, await _wizard(client, 20, "abjuration"))
    assert not keys & {f"wizard.{k}" for k in (
        "hit_points", "spellcasting", "cantrips", "spellbook", "preparing_spells", "spellcasting_ability", "ritual_casting",
        "learning_spells", "arcane_tradition", "ability_score_improvement", "multiclassing")}


@pytest.mark.parametrize("level", list(SLOTS))
async def test_slots_and_cantrips_follow_the_table(client, level):
    full = await _full(client, await _wizard(client, level))
    totals = tuple(s["total"] for s in sorted(full["spell_slots"], key=lambda s: s["level"]) if s["total"])
    assert totals == SLOTS[level]
    limits = full["spellcasting"]["limits"][0]
    assert limits["cantrips_limit"] == max(c for lv, c in CANTRIPS.items() if lv <= level) and limits["known_limit"] is None


@pytest.mark.parametrize("level,pending", [(3, 0), (4, 1), (8, 2), (12, 3), (16, 4), (19, 5), (20, 5)])
async def test_asi_choices_are_pending_at_levels_4_8_12_16_and_19(client, level, pending):
    full = await _full(client, await _wizard(client, level))
    assert len([c for c in full["pending_choices"] if c.get("kind") == "asi"]) == pending


async def test_every_row_with_a_title_has_a_summary_in_both_languages():
    for spec in features_for("2014", "wizard"):
        assert spec.summary["it"] and spec.summary["en"] and len(spec.summary["it"]) <= 200 and len(spec.summary["en"]) <= 200


# ---------------------------------------------------------------------------
# Libro degli Incantesimi: costo di copia, copia di riserva, ritrascrizione
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,mode,hours,gold", [
    (1, "copy", 2, 50), (3, "copy", 6, 150), (9, "copy", 18, 450), (1, "backup", 1, 10), (4, "backup", 4, 40), (2, "retranscribe", 2, 20)])
async def test_the_copy_cost_is_per_spell_level(client, level, mode, hours, gold):
    cid = await _wizard(client, 17)
    r = await client.get(f"/characters/{cid}/spellbook/cost", params={"level": level, "mode": mode})
    assert r.status_code == 200, r.text
    assert r.json() == {"hours": hours, "gold": gold, "halved": False}


async def test_a_new_spell_is_outside_the_book_until_it_is_copied(client):
    cid = await _wizard(client, 5)
    sid = await _spell(client, cid, "Palla di fuoco", 3, school="evocation")
    assert (await _spells(client, cid))["Palla di fuoco"]["in_spellbook"] is False
    await _gold(client, cid, 500)
    r = await client.post(f"/characters/{cid}/spells/{sid}/copy", json={"mode": "copy"})
    assert r.status_code == 200, r.text
    assert (await _spells(client, cid))["Palla di fuoco"]["in_spellbook"] is True
    assert await _purse(client, cid) == 500 - 150


async def test_copying_without_enough_gold_is_refused_and_changes_nothing(client):
    cid = await _wizard(client, 5)
    sid = await _spell(client, cid, "Palla di fuoco", 3)
    await _gold(client, cid, 149)
    r = await client.post(f"/characters/{cid}/spells/{sid}/copy", json={"mode": "copy"})
    assert r.status_code == 409 and r.json()["detail"] == "insufficient_funds"
    assert (await _spells(client, cid))["Palla di fuoco"]["in_spellbook"] is False and await _purse(client, cid) == 149


async def test_a_cantrip_does_not_go_in_the_book(client):
    cid = await _wizard(client, 5)
    sid = await _spell(client, cid, "Luce", 0)
    r = await client.post(f"/characters/{cid}/spells/{sid}/copy", json={"mode": "copy"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "not_a_wizard_spell"


async def test_a_spell_above_the_slots_cannot_be_copied(client):
    cid = await _wizard(client, 5)  # 3° livello al massimo
    sid = await _spell(client, cid, "Dito della morte", 7)
    await _gold(client, cid, 5000)
    r = await client.post(f"/characters/{cid}/spells/{sid}/copy", json={"mode": "copy"})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "spell_above_slots" and await _purse(client, cid) == 5000


async def test_a_spell_already_in_the_book_is_not_copied_twice(client):
    cid = await _wizard(client, 5)
    await _gold(client, cid, 1000)
    sid = await _book(client, cid, "Scudo", 1)
    r = await client.post(f"/characters/{cid}/spells/{sid}/copy", json={"mode": "copy"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "already_in_spellbook"
    assert await _purse(client, cid) == 950


async def test_a_backup_copy_needs_the_spell_in_the_book_and_costs_one_tenth_of_the_gold(client):
    cid = await _wizard(client, 5)
    await _gold(client, cid, 1000)
    outside = await _spell(client, cid, "Scudo", 1)
    r = await client.post(f"/characters/{cid}/spells/{outside}/copy", json={"mode": "backup"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_in_spellbook"
    inside = await _book(client, cid, "Dardo incantato", 1)
    r = await client.post(f"/characters/{cid}/spells/{inside}/copy", json={"mode": "backup"})
    assert r.status_code == 200, r.text
    assert (await _spells(client, cid))["Dardo incantato"]["in_backup"] is True and await _purse(client, cid) == 1000 - 50 - 10
    again = await client.post(f"/characters/{cid}/spells/{inside}/copy", json={"mode": "backup"})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "already_in_backup"


async def test_a_lost_book_is_rewritten_only_for_prepared_spells(client):
    cid = await _wizard(client, 5)
    await _gold(client, cid, 1000)
    prepared = await _book(client, cid, "Scudo", 1)
    other = await _book(client, cid, "Dardo incantato", 1)
    assert (await _prepare(client, cid, prepared)).status_code == 200
    r = await client.post(f"/characters/{cid}/spellbook/lost")
    assert r.status_code == 200, r.text
    spells = await _spells(client, cid)
    assert not spells["Scudo"]["in_spellbook"] and not spells["Dardo incantato"]["in_spellbook"]
    refused = await client.post(f"/characters/{cid}/spells/{other}/copy", json={"mode": "retranscribe"})
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "not_prepared"
    money = await _purse(client, cid)
    done = await client.post(f"/characters/{cid}/spells/{prepared}/copy", json={"mode": "retranscribe"})
    assert done.status_code == 200, done.text
    assert (await _spells(client, cid))["Scudo"]["in_spellbook"] is True and await _purse(client, cid) == money - 10


async def test_a_lost_book_comes_back_from_the_backup_copy(client):
    cid = await _wizard(client, 5)
    await _gold(client, cid, 1000)
    safe = await _book(client, cid, "Scudo", 1)
    await _book(client, cid, "Dardo incantato", 1)
    assert (await client.post(f"/characters/{cid}/spells/{safe}/copy", json={"mode": "backup"})).status_code == 200
    assert (await client.post(f"/characters/{cid}/spellbook/lost")).status_code == 200
    spells = await _spells(client, cid)
    assert spells["Scudo"]["in_spellbook"] is True and spells["Scudo"]["in_backup"] is False
    assert spells["Dardo incantato"]["in_spellbook"] is False


async def test_only_a_wizard_has_a_spellbook(client):
    r = await client.post("/characters", json={"name": "Bardo", "initial_class": {"class_name": "bard", "level": 5}})
    cid = r.json()["id"]
    sid = await _spell(client, cid, "Scudo", 1)
    refused = await client.post(f"/characters/{cid}/spells/{sid}/copy", json={"mode": "copy"})
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "not_a_wizard_spell"
    assert (await client.post(f"/characters/{cid}/spellbook/lost")).status_code == 422


# ---------------------------------------------------------------------------
# Preparare incantesimi
# ---------------------------------------------------------------------------

async def test_only_spells_in_the_book_can_be_prepared(client):
    cid = await _wizard(client, 5)
    await _gold(client, cid, 500)
    outside = await _spell(client, cid, "Scudo", 1)
    refused = await _prepare(client, cid, outside)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "not_in_spellbook"
    inside = await _book(client, cid, "Dardo incantato", 1)
    assert (await _prepare(client, cid, inside)).status_code == 200




async def _force_into_book(factory, spell_id) -> None:
    from core.db.models import Spell
    async with factory() as session:
        (await session.get(Spell, spell_id)).in_spellbook = True
        await session.commit()


async def test_a_spell_above_the_slots_cannot_be_prepared(client, test_session_factory):
    cid = await _wizard(client, 3)  # 2° livello al massimo
    sid = await _spell(client, cid, "Palla di fuoco", 3)
    await _force_into_book(test_session_factory, sid)  # nel libro (trovata in gioco), ma troppo alta per ora
    refused = await _prepare(client, cid, sid)
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "spell_above_slots"


async def test_the_prepared_cap_still_applies_to_book_spells(client):
    cid = await _wizard(client, 1, intelligence=10)  # 0 + 1 = 1 preparato
    await _gold(client, cid, 500)
    first = await _book(client, cid, "Scudo", 1)
    second = await _book(client, cid, "Dardo incantato", 1)
    assert (await _prepare(client, cid, first)).status_code == 200
    refused = await _prepare(client, cid, second)
    assert refused.status_code == 400 and refused.json()["detail"]["code"] == "prepared_cap"


async def test_a_granted_always_prepared_spell_needs_no_book(client):
    cid = await _wizard(client, 5)
    await _spell(client, cid, "Scudo", 1, always_prepared=True)
    assert (await _spells(client, cid))["Scudo"]["is_prepared"] is True


# ---------------------------------------------------------------------------
# Imparare incantesimi: due al libro per livello
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level,count", [(1, 6), (2, 8), (3, 10), (9, 22), (20, 44)])
async def test_the_book_grows_by_two_spells_per_wizard_level(client, level, count):
    choice = _choice(await _full(client, await _wizard(client, level)), "spellbook")
    assert choice is not None and choice["count"] == count
    assert choice["spell_pick"]["free"] is False and choice["spell_pick"]["max_level"] == {1: 1, 2: 1, 3: 2, 9: 5, 20: 9}[level]


async def test_a_picked_spell_goes_into_the_book_for_free(client):
    cid = await _wizard(client, 1)
    choice = _choice(await _full(client, cid), "spellbook")
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Dardo incantato", "level": 1, "pick_id": choice["id"]})
    assert r.status_code == 201, r.text
    assert r.json()["in_spellbook"] is True and r.json()["class_id"] == await _wizard_id(client, cid)
    assert _choice(await _full(client, cid), "spellbook")["count"] == 5
    too_high = await client.post(f"/characters/{cid}/spells", json={"name": "Palla di fuoco", "level": 3, "pick_id": choice["id"]})
    assert too_high.status_code == 422 and too_high.json()["detail"]["code"] == "spell_pick_level"


async def test_the_book_choice_does_not_count_as_known_spells(client):
    cid = await _wizard(client, 1)
    choice = _choice(await _full(client, cid), "spellbook")
    await client.post(f"/characters/{cid}/spells", json={"name": "Scudo", "level": 1, "pick_id": choice["id"]})
    limits = (await _full(client, cid))["spellcasting"]["limits"][0]
    assert limits["known_limit"] is None


async def test_leveling_up_adds_a_new_pick_of_two(client):
    cid = await _wizard(client, 1)
    choice = _choice(await _full(client, cid), "spellbook")
    for name in ("Scudo", "Dardo incantato", "Sonno", "Mani brucianti", "Armatura magica", "Charme su persone"):
        r = await client.post(f"/characters/{cid}/spells", json={"name": name, "level": 1, "pick_id": choice["id"]})
        assert r.status_code == 201, r.text
    assert _choice(await _full(client, cid), "spellbook") is None
    await client.patch(f"/characters/{cid}/classes/{await _wizard_id(client, cid)}", json={"level": 2})
    assert _choice(await _full(client, cid), "spellbook")["count"] == 2


async def test_an_existing_wizard_declares_the_spells_already_on_the_sheet(client, test_session_factory):
    from core.db.models import Character
    cid = await _wizard(client, 2)
    first = await _spell(client, cid, "Scudo", 1)
    second = await _spell(client, cid, "Sonno", 1)
    async with test_session_factory() as s:  # nato prima del catalogo
        char = await s.get(Character, cid)
        char.pending_choices = [{**c, "retrofit": True} for c in char.pending_choices]
        await s.commit()
    choice = _choice(await _full(client, cid), "spellbook")
    assert choice["retrofit"] is True
    r = await client.post(f"/characters/{cid}/choices/{choice['id']}/resolve",
                          json={"kind": "class_option", "options": [str(first), str(second)]})
    assert r.status_code == 200, r.text
    spells = await _spells(client, cid)
    assert spells["Scudo"]["in_spellbook"] and spells["Sonno"]["in_spellbook"]
    assert _choice(await _full(client, cid), "spellbook")["count"] == 6


# ---------------------------------------------------------------------------
# Celebrare rituali
# ---------------------------------------------------------------------------

RITUAL = {"is_ritual": True, "casting_time": "1 azione"}


async def test_a_book_ritual_is_cast_without_preparing_it(client):
    cid = await _wizard(client, 5)
    await _gold(client, cid, 500)
    sid = await _book(client, cid, "Identificare", 1, **RITUAL)
    r = await _cast(client, cid, sid, as_ritual=True)
    assert r.status_code == 200, r.text


async def test_a_ritual_outside_the_book_is_not_cast_as_a_wizard_ritual(client):
    cid = await _wizard(client, 5)
    sid = await _spell(client, cid, "Identificare", 1, **RITUAL)
    r = await _cast(client, cid, sid, as_ritual=True)
    assert r.status_code == 409 and r.json()["detail"]["warnings"] == ["ritual_unprepared"]
    assert (await _cast(client, cid, sid, as_ritual=True, confirm=["ritual_unprepared"])).status_code == 200


async def test_the_wizard_ritual_does_not_reach_the_spells_of_another_class(client):
    cid = await _wizard(client, 5)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 3, "subclass": "Cavaliere Mistico"})
    assert r.status_code in (200, 201), r.text
    knight = next(c["id"] for c in (await _full(client, cid))["classes"] if c["class_name"].lower() in ("fighter", "guerriero"))
    sid = await _spell(client, cid, "Identificare", 1, class_id=knight, **RITUAL)
    refused = await _cast(client, cid, sid, as_ritual=True)
    assert refused.status_code == 400 and refused.json()["detail"] == "No class with Ritual Casting"


# ---------------------------------------------------------------------------
# Recupero Arcano
# ---------------------------------------------------------------------------

ARCANE = "wizard.arcane_recovery"


async def _spend(client, cid, **used) -> None:
    """``used``: livello -> slot spesi (``l3=2``)."""
    for slot in (await _full(client, cid))["spell_slots"]:
        want = used.get(f"l{slot['level']}")
        if want is not None:
            r = await client.patch(f"/characters/{cid}/spell_slots/{slot['id']}", json={"used": want})
            assert r.status_code == 200, r.text


async def _used(client, cid) -> dict[int, int]:
    return {s["level"]: s["used"] for s in (await _full(client, cid))["spell_slots"]}


async def _short(client, cid, recovery=None):
    return await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "arcane_recovery": recovery})


async def test_arcane_recovery_is_a_single_use_pool_returning_on_a_long_rest(client):
    row = await _ability(client, await _wizard(client, 1), ARCANE)
    assert (row["max_uses"], row["uses"], row["restoration_type"]) == (1, 1, "long_rest")
    assert row["is_pool"] is True and row["has_on_use"] is False


@pytest.mark.parametrize("level,fits,over", [
    (1, {"1": 1}, {"1": 2}), (3, {"2": 1}, {"2": 1, "1": 1}), (4, {"1": 2}, {"2": 1, "1": 1}),
    (5, {"2": 1, "1": 1}, {"3": 1, "1": 1}), (9, {"5": 1}, {"5": 1, "1": 1}), (20, {"5": 2}, {"5": 2, "1": 1})])
async def test_arcane_recovery_budget_is_half_the_wizard_level_rounded_up(client, level, fits, over):
    cid = await _wizard(client, level)
    await _spend(client, cid, l1=4, l2=3, l3=3, l4=3, l5=2)
    refused = await _short(client, cid, over)
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "natural_recovery_cap"
    assert (await _ability(client, cid, ARCANE))["uses"] == 1  # niente è stato speso
    assert (await _short(client, cid, fits)).status_code == 200
    assert (await _ability(client, cid, ARCANE))["uses"] == 0


async def test_arcane_recovery_returns_exactly_the_chosen_slots_and_spends_the_use(client):
    cid = await _wizard(client, 4)
    await _spend(client, cid, l1=3, l2=2)
    assert (await _short(client, cid, {"2": 1})).status_code == 200
    used = await _used(client, cid)
    assert (used[1], used[2]) == (3, 1)
    again = await _short(client, cid, {"1": 1})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "no_uses"
    used = await _used(client, cid)
    assert (used[1], used[2]) == (3, 1)


async def test_arcane_recovery_cannot_return_slots_that_were_not_spent(client):
    cid = await _wizard(client, 6)
    await _spend(client, cid, l1=1)
    r = await _short(client, cid, {"1": 2})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "natural_recovery_unspent"
    assert (await _ability(client, cid, ARCANE))["uses"] == 1 and (await _used(client, cid))[1] == 1


async def test_arcane_recovery_never_returns_slots_of_6th_level_or_higher(client):
    cid = await _wizard(client, 20)
    await _spend(client, cid, l6=1)
    r = await _short(client, cid, {"6": 1})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "natural_recovery_level"
    assert (await _used(client, cid))[6] == 1


async def test_arcane_recovery_is_for_the_short_rest_only(client):
    cid = await _wizard(client, 4)
    await _spend(client, cid, l1=2)
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "arcane_recovery": {"1": 1}})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "natural_recovery_short_only"
    assert (await _used(client, cid))[1] == 2 and (await _ability(client, cid, ARCANE))["uses"] == 1


async def test_a_character_without_the_wizard_has_no_arcane_recovery(client):
    r = await client.post("/characters", json={"name": "Bardo", "initial_class": {"class_name": "bard", "level": 4}})
    cid = r.json()["id"]
    refused = await _short(client, cid, {"1": 1})
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "natural_recovery_unavailable"


async def test_two_requests_at_once_recover_the_slots_only_once(client):
    import asyncio
    cid = await _wizard(client, 4)
    await _spend(client, cid, l1=4)
    first, second = await asyncio.gather(_short(client, cid, {"1": 2}), _short(client, cid, {"1": 2}))
    assert sorted([first.status_code, second.status_code]) == [200, 409]
    assert (await _used(client, cid))[1] == 2 and (await _ability(client, cid, ARCANE))["uses"] == 0


async def test_two_stale_snapshots_recover_the_slots_only_once(client, test_session_factory):
    """La gara vera: due richieste leggono lo stesso personaggio (uso ancora 1) e superano entrambe i controlli; solo l'UPDATE condizionato
    sull'uso ne ferma una. Il test con ``gather`` sopra non morde: SQLite le serializza e il controllo in memoria basta."""
    from fastapi import HTTPException
    from api.services.character_load import get_owned_full
    from api.services.natural_recovery import ARCANE_FEATURE, recover
    cid = await _wizard(client, 4)
    await _spend(client, cid, l1=4)
    async with test_session_factory() as one, test_session_factory() as two:
        first, second = await get_owned_full(cid, 1234, one), await get_owned_full(cid, 1234, two)  # entrambe vedono uso = 1
        await recover(one, first, {1: 2}, ARCANE_FEATURE)
        await one.commit()
        with pytest.raises(HTTPException) as refused:
            await recover(two, second, {1: 2}, ARCANE_FEATURE)
        assert refused.value.detail["code"] == "no_uses"
    assert (await _used(client, cid))[1] == 2 and (await _ability(client, cid, ARCANE))["uses"] == 0


async def test_arcane_recovery_uses_the_wizard_level_not_the_total_level(client):
    cid = await _wizard(client, 4)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 6})
    assert r.status_code in (200, 201), r.text
    await _spend(client, cid, l1=4)
    refused = await _short(client, cid, {"1": 3})  # 5 livelli di totale non cambiano i due del mago 4
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "natural_recovery_cap"
    assert (await _short(client, cid, {"1": 2})).status_code == 200


# ---------------------------------------------------------------------------
# Maestria negli Incantesimi e Incantesimi Personali
# ---------------------------------------------------------------------------

async def _mastered(client, test_session_factory, level=18):
    """Un mago con due incantesimi di 1° e 2° nel libro, preparati, e uno di 3°."""
    cid = await _wizard(client, level)
    await _gold(client, cid, 5000)
    ids = {"shield": await _book(client, cid, "Scudo", 1, srd_index="shield"),
           "misty": await _book(client, cid, "Passo velato", 2, srd_index="misty-step", casting_time="1 azione bonus"),
           "fireball": await _book(client, cid, "Palla di fuoco", 3, srd_index="fireball"),
           "counter": await _book(client, cid, "Controincantesimo", 3, srd_index="counterspell")}
    return cid, ids


async def test_spell_mastery_offers_one_first_and_one_second_level_spell_from_the_book(client, test_session_factory):
    cid, ids = await _mastered(client, test_session_factory)
    one, two = _choice(await _full(client, cid), "spell_mastery_1"), _choice(await _full(client, cid), "spell_mastery_2")
    assert one["count"] == two["count"] == 1
    assert [o["key"] for o in one["options"]] == ["Scudo"] and [o["key"] for o in two["options"]] == ["Passo velato"]
    assert _choice(await _full(client, await _wizard(client, 17)), "spell_mastery_1") is None


async def test_a_mastered_prepared_spell_is_cast_at_will_at_its_base_level(client, test_session_factory):
    cid, ids = await _mastered(client, test_session_factory)
    await _prepare(client, cid, ids["shield"])
    pick = _choice(await _full(client, cid), "spell_mastery_1")
    r = await client.post(f"/characters/{cid}/choices/{pick['id']}/resolve", json={"kind": "class_option", "options": ["Scudo"]})
    assert r.status_code == 200, r.text
    spell = (await _spells(client, cid))["Scudo"]
    assert spell["at_will"] is True
    before = await _used(client, cid)
    for _ in range(3):
        cast = await _cast(client, cid, ids["shield"], free_cast=True)
        assert cast.status_code == 200, cast.text
        await client.post(f"/characters/{cid}/turn/new")
    assert await _used(client, cid) == before


async def test_a_mastered_spell_that_is_not_prepared_needs_a_slot(client, test_session_factory):
    cid, ids = await _mastered(client, test_session_factory)
    pick = _choice(await _full(client, cid), "spell_mastery_1")
    await client.post(f"/characters/{cid}/choices/{pick['id']}/resolve", json={"kind": "class_option", "options": ["Scudo"]})
    assert (await _spells(client, cid))["Scudo"]["at_will"] is False
    refused = await _cast(client, cid, ids["shield"], free_cast=True)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "free_cast_unavailable"


async def test_a_mastered_spell_cast_with_a_higher_slot_spends_the_slot(client, test_session_factory):
    cid, ids = await _mastered(client, test_session_factory)
    await _prepare(client, cid, ids["shield"])
    pick = _choice(await _full(client, cid), "spell_mastery_1")
    await client.post(f"/characters/{cid}/choices/{pick['id']}/resolve", json={"kind": "class_option", "options": ["Scudo"]})
    r = await _cast(client, cid, ids["shield"], slot_level=2)
    assert r.status_code == 200, r.text
    assert (await _used(client, cid))[2] == 1


async def test_spell_mastery_can_be_replaced_with_another_spell_of_the_same_level(client, test_session_factory):
    cid, ids = await _mastered(client, test_session_factory)
    await _book(client, cid, "Mani brucianti", 1)
    pick = _choice(await _full(client, cid), "spell_mastery_1")
    await client.post(f"/characters/{cid}/choices/{pick['id']}/resolve", json={"kind": "class_option", "options": ["Scudo"]})
    klass = await _wizard_id(client, cid)
    url = f"/characters/{cid}/classes/{klass}/options/replace"
    r = await client.post(url, json={"group": "spell_mastery_1", "old_key": "Scudo", "new_key": "Mani brucianti"})
    assert r.status_code == 200, r.text
    wrong = await client.post(url, json={"group": "spell_mastery_1", "old_key": "Mani brucianti", "new_key": "Passo velato"})
    assert wrong.status_code == 422


async def test_signature_spells_are_two_third_level_book_spells_always_prepared(client, test_session_factory):
    cid, ids = await _mastered(client, test_session_factory, 20)
    one, two = _choice(await _full(client, cid), "signature_1"), _choice(await _full(client, cid), "signature_2")
    assert {o["key"] for o in one["options"]} == {"Palla di fuoco", "Controincantesimo"}
    assert (await client.post(f"/characters/{cid}/choices/{one['id']}/resolve",
                              json={"kind": "class_option", "options": ["Palla di fuoco"]})).status_code == 200
    again = _choice(await _full(client, cid), "signature_2")
    assert [o["key"] for o in again["options"]] == ["Controincantesimo"]  # il primo non si sceglie due volte
    assert (await client.post(f"/characters/{cid}/choices/{again['id']}/resolve",
                              json={"kind": "class_option", "options": ["Controincantesimo"]})).status_code == 200
    spells = await _spells(client, cid)
    assert spells["Palla di fuoco"]["always_prepared"] and spells["Controincantesimo"]["is_prepared"]
    assert (await _full(client, cid))["spellcasting"]["prepared_count"] == 0  # fuori dal limite
    assert two["count"] == 1


async def test_each_signature_spell_is_cast_once_without_a_slot_then_a_rest_returns_it(client, test_session_factory):
    cid, ids = await _mastered(client, test_session_factory, 20)
    for n, name in ((1, "Palla di fuoco"), (2, "Controincantesimo")):
        pick = _choice(await _full(client, cid), f"signature_{n}")
        await client.post(f"/characters/{cid}/choices/{pick['id']}/resolve", json={"kind": "class_option", "options": [name]})
    before = await _used(client, cid)
    first = await _cast(client, cid, ids["fireball"], free_cast=True)
    assert first.status_code == 200, first.text
    assert await _used(client, cid) == before
    assert (await _ability(client, cid, "wizard.signature_spell_1"))["uses"] == 0
    assert (await _ability(client, cid, "wizard.signature_spell_2"))["uses"] == 1  # l'altro è intatto
    await client.post(f"/characters/{cid}/turn/new")
    again = await _cast(client, cid, ids["fireball"], free_cast=True)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "no_uses"
    await client.post(f"/characters/{cid}/turn/new")
    with_slot = await _cast(client, cid, ids["fireball"], slot_level=4)  # con uno slot si lancia anche senza uso
    assert with_slot.status_code == 200 and (await _used(client, cid))[4] == 1
    await _rest(client, cid, "short")
    assert (await _ability(client, cid, "wizard.signature_spell_1"))["uses"] == 1


async def test_two_signature_casts_at_once_spend_the_use_once(client, test_session_factory):
    import asyncio
    cid, ids = await _mastered(client, test_session_factory, 20)
    pick = _choice(await _full(client, cid), "signature_1")
    await client.post(f"/characters/{cid}/choices/{pick['id']}/resolve", json={"kind": "class_option", "options": ["Palla di fuoco"]})
    results = await asyncio.gather(*(_cast(client, cid, ids["fireball"], free_cast=True) for _ in range(2)))
    assert sorted(r.status_code for r in results) == [200, 409]
    assert (await _ability(client, cid, "wizard.signature_spell_1"))["uses"] == 0


async def test_two_stale_signature_snapshots_spend_the_use_only_once(client, test_session_factory):
    """Come il Recupero Arcano: il ``gather`` sopra non morde (SQLite serializza e il controllo in memoria basta). Qui due richieste vedono
    l'uso ancora disponibile e solo l'UPDATE condizionato ne ferma una."""
    from fastapi import HTTPException
    from api.routers.spells import _charge_pact_use
    from api.services.character_load import get_owned_full
    cid, _ids = await _mastered(client, test_session_factory, 20)
    pick = _choice(await _full(client, cid), "signature_1")
    await client.post(f"/characters/{cid}/choices/{pick['id']}/resolve", json={"kind": "class_option", "options": ["Palla di fuoco"]})
    async with test_session_factory() as one, test_session_factory() as two:
        rows = []
        for session in (one, two):
            char = await get_owned_full(cid, 1234, session)
            rows.append(next(a for a in char.abilities if a.feature_key == "wizard.signature_spell_1"))  # entrambe: uso = 1
        await _charge_pact_use(one, rows[0])
        await one.commit()
        with pytest.raises(HTTPException) as refused:
            await _charge_pact_use(two, rows[1])
        assert refused.value.detail["code"] == "no_uses"
    assert (await _ability(client, cid, "wizard.signature_spell_1"))["uses"] == 0
