"""Task 48: togliere condizioni con privilegi e incantesimi, anche a un altro PG della serata. Un solo meccanismo
(``core/rules/condition_removal.py``): ogni voce dell'inventario, le condizioni non ammesse, i non partecipanti, la spesa
unica, le differenze fra edizioni e le note per ciò che l'app non traccia."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from core.db.models import CharacterHistory
from tests.integration._encounter_helpers import GM_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard import _full
from tests.integration.rules.test_2014_bard_inspiration import _seat
from tests.integration.rules.test_2014_cleric import _cleric
from tests.integration.rules.test_2014_paladin_auras import _table as _table14
from tests.integration.rules.test_2014_paladin_round1_loh import _give, _hero_hp, _hero_state, _pool
from tests.integration.rules.test_2024_cleric import _cleric24
from tests.integration.rules.test_2024_paladin import _table24

# (edizione, srd_index, livello, condizioni sull'eroe, scelta, restano, parola nelle note o None)
CASES = [
    ("2014", "lesser-restoration", 2, ["blinded", "charmed"], ["blinded"], ["charmed"], None),
    ("2014", "lesser-restoration", 2, ["blinded"], ["disease"], ["blinded"], "malattia"),
    ("2024", "lesser-restoration", 2, ["poisoned", "stunned"], ["poisoned"], ["stunned"], None),
    ("2014", "greater-restoration", 5, ["charmed", "petrified"], ["charmed"], ["petrified"], None),
    ("2024", "greater-restoration", 5, ["petrified", "charmed"], ["petrified"], ["charmed"], None),
    ("2014", "greater-restoration", 5, [], ["curse"], [], "maledizione"),
    ("2014", "heal", 6, ["blinded", "deafened", "poisoned"], None, ["poisoned"], "malattia"),
    ("2024", "heal", 6, ["blinded", "deafened", "poisoned", "stunned"], None, ["stunned"], None),
    ("2014", "mass-heal", 9, ["blinded", "deafened", "poisoned"], None, ["poisoned"], "malattia"),
    ("2024", "mass-heal", 9, ["blinded", "poisoned", "charmed"], None, ["charmed"], None),
    ("2014", "power-word-heal", 9, ["charmed", "frightened", "paralyzed", "stunned", "poisoned"], None, ["poisoned"], None),
    ("2024", "power-word-heal", 9, ["charmed", "frightened", "paralyzed", "stunned", "poisoned", "blinded"], None, ["blinded"], None),
    ("2014", "protection-from-poison", 2, ["poisoned", "blinded"], None, ["blinded"], "veleno"),
    ("2024", "protection-from-poison", 2, ["poisoned", "blinded"], None, ["blinded"], None),
    ("2014", "remove-curse", 3, ["blinded"], None, ["blinded"], "maledizione"),
    ("2024", "remove-curse", 3, ["blinded"], None, ["blinded"], "maledizione"),
    ("2014", "calm-emotions", 2, ["charmed", "frightened", "blinded"], None, ["blinded"], "Sospeso"),
    ("2024", "calm-emotions", 2, ["charmed", "frightened", "blinded"], None, ["blinded"], "Sospeso"),
    ("2014", "heroes-feast", 6, ["poisoned", "blinded"], None, ["blinded"], "malattia"),
]


def _on(conditions: list[str]) -> dict:
    return {c: True for c in conditions}


async def _table(client, factory, edition: str):
    """Una serata con un chierico di 17° livello (GM, seduto) e un eroe: ``(chierico, eroe)``."""
    _sid, hero = await seed_session(factory)
    as_user(GM_ID)
    cid = await (_cleric(client, 17, wisdom=16) if edition == "2014" else _cleric24(client, 17, wisdom=16))
    await _seat(factory, cid)
    return cid, hero


async def _spell(client, cid, index: str, level: int) -> int:
    r = await client.post(f"/characters/{cid}/spells", json={
        "name": index, "level": level, "srd_index": index, "is_prepared": True,
        "class_id": (await _full(client, cid))["classes"][0]["id"]})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _cast(client, cid, spell: int, level: int, targets, conditions=None):
    as_user(GM_ID)
    return await client.post(f"/characters/{cid}/spells/{spell}/use", json={
        "slot_level": level, "removal": {"targets": targets, **({"conditions": conditions} if conditions is not None else {})}})


async def _slot_used(client, cid, level: int) -> int:
    as_user(GM_ID)
    return next(s["used"] for s in (await _full(client, cid))["spell_slots"] if s["level"] == level)


async def _hero(factory, hero) -> dict:
    return {c: v for c, v in (await _hero_state(factory, hero))[1].items() if v}


async def _history(factory, char) -> list[str]:
    async with factory() as s:
        return [e.description for e in (await s.execute(select(CharacterHistory).where(CharacterHistory.character_id == char))).scalars()]


@pytest.mark.parametrize("edition,index,level,have,chosen,kept,word", CASES, ids=[f"{c[0]}-{c[1]}" + ("-note" if c[4] and c[4][0] in ("disease", "curse") else "") for c in CASES])
async def test_each_inventory_entry_removes_what_the_edition_allows(client, test_session_factory, edition, index, level, have, chosen, kept, word):
    cid, hero = await _table(client, test_session_factory, edition)
    await _hero_hp(test_session_factory, hero, 20, conditions=_on(have))
    spell = await _spell(client, cid, index, level)
    r = await _cast(client, cid, spell, level, [hero], chosen)
    assert r.status_code == 200, r.text
    assert set(await _hero(test_session_factory, hero)) == set(kept)
    lines = " ".join(x["it"] for x in r.json()["removal_result"])
    if word:
        assert word.lower() in lines.lower(), lines
    assert await _slot_used(client, cid, level) == 1  # uno slot, una volta sola
    removed = [c for c in have if c not in kept]  # lo storico sul ricevente dice da chi
    assert sum("tolta da Chierico" in d for d in await _history(test_session_factory, hero)) == len(removed)


@pytest.mark.parametrize("edition,expect", [("2014", {"blinded", "deafened"}), ("2024", {"blinded", "deafened", "poisoned"})])
async def test_the_spell_sheet_exposes_the_list_of_the_casters_edition(client, test_session_factory, edition, expect):
    cid, _hero_id = await _table(client, test_session_factory, edition)
    await _spell(client, cid, "heal", 6)
    rule = next(s for s in (await _full(client, cid))["spells"] if s["srd_index"] == "heal")["removal"]
    assert {c["key"] for c in rule["conditions"]} == expect and rule["count"] is None
    assert bool(rule["untracked"]) == (edition == "2014")  # la malattia è nel manuale 2014, non nel 2024


async def test_a_condition_the_spell_does_not_allow_is_refused_and_nothing_is_spent(client, test_session_factory):
    cid, hero = await _table(client, test_session_factory, "2014")
    await _hero_hp(test_session_factory, hero, 20, conditions=_on(["charmed"]))
    spell = await _spell(client, cid, "lesser-restoration", 2)
    for chosen in (["charmed"], ["blinded", "deafened"], [], ["curse"]):  # non ammessa, due insieme, vuota, di un altro incantesimo
        r = await _cast(client, cid, spell, 2, [hero], chosen)
        assert r.status_code == 422, (chosen, r.text)
    assert (await _cast(client, cid, spell, 2, [hero])).status_code == 422  # un incantesimo «a scelta» non indovina
    assert await _slot_used(client, cid, 2) == 0 and (await _hero(test_session_factory, hero)) == {"charmed": True}


async def test_someone_not_at_the_table_is_refused_and_nothing_is_spent(client, test_session_factory):
    cid, hero = await _table(client, test_session_factory, "2014")
    spell = await _spell(client, cid, "heal", 6)
    as_user(9999)
    outsider = (await client.post("/characters", json={"name": "Estraneo"})).json()["id"]
    for target in (outsider, 987654, "ciao"):
        r = await _cast(client, cid, spell, 6, [target])
        assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_target", (target, r.text)
    assert (await _cast(client, cid, spell, 6, [hero, hero])).status_code == 422  # doppioni
    assert (await _cast(client, cid, spell, 6, [])).status_code == 422
    assert await _slot_used(client, cid, 6) == 0


async def test_one_creature_only_where_the_spell_names_one_and_many_for_the_mass_spells(client, test_session_factory):
    cid, hero = await _table(client, test_session_factory, "2014")
    one = await _spell(client, cid, "lesser-restoration", 2)
    assert (await _cast(client, cid, one, 2, ["self", hero], ["blinded"])).status_code == 422
    many = await _spell(client, cid, "mass-heal", 9)
    await _hero_hp(test_session_factory, hero, 20, conditions=_on(["blinded"]))
    as_user(GM_ID)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"deafened": True}})
    r = await _cast(client, cid, many, 9, ["self", hero])
    assert r.status_code == 200, r.text
    assert not await _hero(test_session_factory, hero)
    assert not (await _full(client, cid))["conditions"].get("deafened")


async def test_a_second_cast_cannot_spend_again_nor_remove_twice(client, test_session_factory):
    cid, hero = await _table(client, test_session_factory, "2014")
    spell = await _spell(client, cid, "power-word-heal", 9)
    await _hero_hp(test_session_factory, hero, 20, conditions=_on(["charmed"]))
    assert (await _cast(client, cid, spell, 9, [hero])).status_code == 200
    await _hero_hp(test_session_factory, hero, 20, conditions=_on(["charmed"]))
    assert (await _cast(client, cid, spell, 9, [hero])).status_code != 200  # un solo slot di 9° livello
    assert await _slot_used(client, cid, 9) == 1 and await _hero(test_session_factory, hero) == {"charmed": True}


async def test_a_creature_outside_the_evening_is_a_visible_note_and_the_slot_is_spent(client, test_session_factory):
    cid, _hero_id = await _table(client, test_session_factory, "2014")
    spell = await _spell(client, cid, "lesser-restoration", 2)
    r = await _cast(client, cid, spell, 2, ["other"], ["blinded"])
    assert r.status_code == 200 and "Da togliere alla creatura: Accecato" in r.json()["removal_result"][0]["it"]
    assert "To remove from the creature: Blinded" in r.json()["removal_result"][0]["en"]
    assert await _slot_used(client, cid, 2) == 1


async def test_on_yourself_it_is_always_allowed(client, test_session_factory):
    cid, _hero_id = await _table(client, test_session_factory, "2024")
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"poisoned": True}})
    spell = await _spell(client, cid, "protection-from-poison", 2)
    r = await _cast(client, cid, spell, 2, ["self"])
    assert r.status_code == 200 and not (await _full(client, cid))["conditions"].get("poisoned")


async def test_greater_restoration_lowers_exhaustion_by_one_level(client, test_session_factory):
    cid, hero = await _table(client, test_session_factory, "2024")
    await _hero_hp(test_session_factory, hero, 20, conditions={"exhaustion": 3})
    spell = await _spell(client, cid, "greater-restoration", 5)
    assert (await _cast(client, cid, spell, 5, [hero], ["exhaustion"])).status_code == 200
    assert (await _hero(test_session_factory, hero))["exhaustion"] == 2


async def test_a_spell_without_the_mechanism_refuses_a_removal_request(client, test_session_factory):
    cid, hero = await _table(client, test_session_factory, "2024")
    feast = await _spell(client, cid, "heroes-feast", 6)  # il manuale 2024 non toglie nulla
    assert (await _cast(client, cid, feast, 6, [hero])).status_code == 422
    assert await _slot_used(client, cid, 6) == 0


async def test_a_cast_without_removal_works_as_before(client, test_session_factory):
    cid, _hero_id = await _table(client, test_session_factory, "2014")
    spell = await _spell(client, cid, "lesser-restoration", 2)
    as_user(GM_ID)
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 2})
    assert r.status_code == 200 and "removal_result" not in r.json()


# ---------------------------------------------------------------------------
# Privilegi: Imposizione delle Mani e Tocco Ristoratore sul meccanismo comune
# ---------------------------------------------------------------------------

async def test_lay_on_hands_2014_cures_poison_on_a_seated_ally_and_notes_the_disease(client, test_session_factory):
    _, paladin, hero = await _table14(client, test_session_factory, level=5)
    await _hero_hp(test_session_factory, hero, 5, conditions={"poisoned": True, "blinded": True})
    as_user(GM_ID)
    r = await _give(client, paladin, hero, 10, mode="cure_other")  # un veleno e una malattia: 5 punti ciascuno
    assert r.status_code == 200, r.text
    assert r.json()["notes"] == [] and "malattia" in " ".join(x["it"] for x in r.json()["removal"]).lower()
    assert await _pool(client, paladin) == 15
    assert await _hero(test_session_factory, hero) == {"blinded": True}
    assert "Condizione Avvelenato tolta da Paladino" in await _history(test_session_factory, hero)


async def test_lay_on_hands_2014_outside_the_evening_is_a_note_for_the_gm(client, test_session_factory):
    _, paladin, _h = await _table14(client, test_session_factory, level=5)
    as_user(GM_ID)
    r = await _give(client, paladin, None, 5, mode="cure_other")
    assert r.status_code == 200 and "Da togliere alla creatura" in r.json()["removal"][0]["it"] and await _pool(client, paladin) == 20


async def test_lay_on_hands_2024_removes_the_chosen_conditions_from_a_seated_ally_only(client, test_session_factory):
    _, paladin, hero = await _table24(client, test_session_factory, level=14)
    await _hero_hp(test_session_factory, hero, 20, conditions={"poisoned": True, "blinded": True, "prone": True})
    as_user(GM_ID)
    before = await _pool(client, paladin)
    r = await _give(client, paladin, hero, 10, mode="cure_other", cure_poisoned=True, cure_blinded=True)
    assert r.status_code == 200, r.text
    assert await _hero(test_session_factory, hero) == {"prone": True}  # Prono non è nell'elenco del Tocco Ristoratore
    assert await _pool(client, paladin) == before - 10
    bad = await _give(client, paladin, hero, 5, mode="cure_other", cure_poisoned=True, cure_blinded=True)  # il costo è 5 per condizione
    assert bad.status_code == 409 and bad.json()["detail"]["code"] == "amount_invalid"


async def test_lay_on_hands_2024_below_level_14_only_poison_exists(client, test_session_factory):
    _, paladin, hero = await _table24(client, test_session_factory, level=5)
    await _hero_hp(test_session_factory, hero, 20, conditions={"poisoned": True, "blinded": True})
    as_user(GM_ID)
    r = await _give(client, paladin, hero, 5, mode="cure_other", cure_poisoned=True, cure_blinded=True)
    assert r.status_code == 200 and await _hero(test_session_factory, hero) == {"blinded": True}  # Accecato è del 14° livello


async def test_lay_on_hands_2024_refuses_a_non_participant_and_spends_nothing(client, test_session_factory):
    _, paladin, _hero_id = await _table24(client, test_session_factory, level=5)
    as_user(9999)
    outsider = (await client.post("/characters", json={"name": "Estraneo"})).json()["id"]
    as_user(GM_ID)
    before = await _pool(client, paladin)
    r = await _give(client, paladin, outsider, 5, mode="cure_other", cure_poisoned=True)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_target"
    assert await _pool(client, paladin) == before


async def test_lay_on_hands_2024_cure_on_yourself_still_removes(client, test_session_factory):
    _, paladin, _h = await _table24(client, test_session_factory, level=5)
    as_user(GM_ID)
    await client.patch(f"/characters/{paladin}/conditions", json={"conditions": {"poisoned": True}})
    r = await _give(client, paladin, None, 5, mode="cure_self", cure_poisoned=True)
    assert r.status_code == 200 and not (await _full(client, paladin))["conditions"].get("poisoned")
