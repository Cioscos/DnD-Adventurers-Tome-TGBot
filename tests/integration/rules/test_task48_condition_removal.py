"""Task 48: togliere condizioni con privilegi e incantesimi, anche a un altro PG della serata. Un solo meccanismo
(``core/rules/condition_removal.py``): ogni voce dell'inventario, le condizioni non ammesse, i non partecipanti, la spesa
unica, le differenze fra edizioni e le note per ciò che l'app non traccia."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from core.db.models import CharacterHistory
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard import _full
from tests.integration.rules.test_2014_bard_inspiration import _seat
from tests.integration.rules.test_2014_cleric import _cleric
from tests.integration.rules.test_2014_paladin_auras import _table as _table14
from tests.integration.rules.test_2014_bard import _use
from tests.integration.rules.test_2014_monk_ki import _ki
from tests.integration.rules.test_2014_paladin import LOH
from tests.integration.rules.test_2014_paladin_round1_loh import _hero_hp, _hero_state, _pool
from tests.integration.rules.test_2014_wizard import _wizard
from tests.integration.rules.test_2014_wizard_necromancy_transmutation import PANACEA, _master
from tests.integration.rules.test_2024_monk_subclasses import HEAL, _sub
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


async def _named_spell(client, cid, name: str, level: int, srd_index=None, concentration=False, duration=None) -> int:
    """Un incantesimo inserito a mano o importato: il nome, e se c'è lo `srd_index`."""
    r = await client.post(f"/characters/{cid}/spells", json={
        "name": name, "level": level, "srd_index": srd_index, "is_prepared": True, "is_concentration": concentration, "duration": duration,
        "class_id": (await _full(client, cid))["classes"][0]["id"]})
    assert r.status_code == 201, r.text
    return r.json()["id"]


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
# Privilegi: un solo corpo `removal` e lo stesso foglio degli incantesimi
# ---------------------------------------------------------------------------

def _rm(targets, conditions=None, **extra) -> dict:
    return {**extra, "removal": {"targets": targets, **({"conditions": conditions} if conditions is not None else {})}}


async def test_lay_on_hands_2014_cures_poison_on_a_seated_ally_and_notes_the_disease(client, test_session_factory):
    _, paladin, hero = await _table14(client, test_session_factory, level=5)
    await _hero_hp(test_session_factory, hero, 5, conditions={"poisoned": True, "blinded": True})
    as_user(GM_ID)
    r = await _use(client, paladin, LOH, amount=1, params=_rm([hero], ["poisoned", "disease"], mode="cure"))  # due voci: 5 punti ciascuna
    assert r.status_code == 200, r.text
    assert r.json()["notes"] == [] and "malattia" in " ".join(x["it"] for x in r.json()["removal"]).lower()
    assert await _pool(client, paladin) == 15
    assert await _hero(test_session_factory, hero) == {"blinded": True}
    assert "Condizione Avvelenato tolta da Paladino" in await _history(test_session_factory, hero)


async def test_lay_on_hands_2014_outside_the_evening_is_a_note_for_the_gm(client, test_session_factory):
    _, paladin, _h = await _table14(client, test_session_factory, level=5)
    as_user(GM_ID)
    r = await _use(client, paladin, LOH, amount=1, params=_rm(["other"], ["poisoned"], mode="cure"))
    assert r.status_code == 200 and "Da togliere alla creatura" in r.json()["removal"][0]["it"] and await _pool(client, paladin) == 20


async def test_lay_on_hands_2024_removes_the_chosen_conditions_from_a_seated_ally_only(client, test_session_factory):
    _, paladin, hero = await _table24(client, test_session_factory, level=14)
    await _hero_hp(test_session_factory, hero, 20, conditions={"poisoned": True, "blinded": True, "prone": True})
    as_user(GM_ID)
    before = await _pool(client, paladin)
    r = await _use(client, paladin, LOH, amount=99, params=_rm([hero], ["poisoned", "blinded"], mode="cure"))  # il costo non lo decide il client
    assert r.status_code == 200, r.text
    assert await _hero(test_session_factory, hero) == {"prone": True}  # Prono non è nell'elenco del Tocco Ristoratore
    assert await _pool(client, paladin) == before - 10
    bad = await _use(client, paladin, LOH, amount=1, params=_rm([hero], ["prone"], mode="cure"))
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "invalid_condition"
    assert await _pool(client, paladin) == before - 10


async def test_lay_on_hands_2024_below_level_14_only_poison_exists(client, test_session_factory):
    _, paladin, hero = await _table24(client, test_session_factory, level=5)
    await _hero_hp(test_session_factory, hero, 20, conditions={"poisoned": True, "blinded": True})
    as_user(GM_ID)
    bad = await _use(client, paladin, LOH, amount=1, params=_rm([hero], ["poisoned", "blinded"], mode="cure"))
    assert bad.status_code == 422 and await _hero(test_session_factory, hero) == {"poisoned": True, "blinded": True}
    r = await _use(client, paladin, LOH, amount=1, params=_rm([hero], ["poisoned"], mode="cure"))
    assert r.status_code == 200 and await _hero(test_session_factory, hero) == {"blinded": True}  # Accecato è del 14° livello


async def test_lay_on_hands_2024_refuses_a_non_participant_and_spends_nothing(client, test_session_factory):
    _, paladin, _hero_id = await _table24(client, test_session_factory, level=5)
    as_user(9999)
    outsider = (await client.post("/characters", json={"name": "Estraneo"})).json()["id"]
    as_user(GM_ID)
    before = await _pool(client, paladin)
    r = await _use(client, paladin, LOH, amount=1, params=_rm([outsider], ["poisoned"], mode="cure"))
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_target"
    assert await _pool(client, paladin) == before


async def test_lay_on_hands_2024_cure_on_yourself_still_removes(client, test_session_factory):
    _, paladin, _h = await _table24(client, test_session_factory, level=5)
    as_user(GM_ID)
    await client.patch(f"/characters/{paladin}/conditions", json={"conditions": {"poisoned": True}})
    r = await _use(client, paladin, LOH, amount=1, params=_rm(["self"], ["poisoned"], mode="cure"))
    assert r.status_code == 200 and not (await _full(client, paladin))["conditions"].get("poisoned")


async def test_a_double_tap_on_the_same_use_spends_and_removes_once(client, test_session_factory):
    _, paladin, hero = await _table24(client, test_session_factory, level=5)
    await _hero_hp(test_session_factory, hero, 20, conditions={"poisoned": True})
    as_user(GM_ID)
    first = await _use(client, paladin, LOH, amount=1, params=_rm([hero], ["poisoned"], mode="cure"))
    assert first.status_code == 200
    again = await _use(client, paladin, LOH, amount=1, params=_rm([hero], ["poisoned"], mode="cure"))
    assert again.status_code == 409 and again.json()["detail"]["code"] == "turn_slot_used"  # azione bonus già spesa
    assert await _pool(client, paladin) == 20


# --- I4: Mano della Guarigione / Tocco del Medico su un compagno ------------------------------------------------------

async def _mercy_table(client, factory, level):
    _sid, hero = await seed_session(factory)
    as_user(GM_ID)
    monk = await _sub(client, "mercy", level, wisdom=16)
    await _seat(factory, monk)
    return monk, hero


async def test_hand_of_healing_on_a_companion_heals_and_removes_the_chosen_condition(client, test_session_factory):
    monk, hero = await _mercy_table(client, test_session_factory, 6)
    await _hero_hp(test_session_factory, hero, 10, conditions={"poisoned": True, "stunned": True})
    ki = await _ki(client, monk)
    r = await _use(client, monk, HEAL, params=_rm([hero], ["poisoned"], mode="other"))
    assert r.status_code == 200, r.text
    assert r.json()["received"]["name"] == "Eroe" and r.json()["received"]["healed"] > 0
    assert r.json().get("message") is None  # niente «riferiscili al GM» accanto al toast di chi è curato
    assert await _hero(test_session_factory, hero) == {"stunned": True}
    assert await _ki(client, monk) == ki - 1  # una sola spesa
    assert "Condizione Avvelenato tolta da Monaco" in await _history(test_session_factory, hero)


async def test_hand_of_healing_on_a_companion_refuses_what_the_rules_do_not_allow(client, test_session_factory):
    monk, hero = await _mercy_table(client, test_session_factory, 6)
    await _hero_hp(test_session_factory, hero, 10, conditions={"charmed": True, "poisoned": True})
    ki = await _ki(client, monk)
    outsider = (await client.post("/characters", json={"name": "Estraneo"})).json()["id"]
    for params, code in ((_rm([hero], ["charmed"], mode="other"), "invalid_condition"),  # Affascinato non è nell'elenco
                         (_rm([outsider], ["poisoned"], mode="other"), "invalid_target"),  # non partecipante
                         (_rm(["self"], ["poisoned"], mode="other"), "invalid_choice"),  # il bersaglio segue la modalità
                         (_rm([hero], ["poisoned"], mode="self"), "invalid_choice")):
        r = await _use(client, monk, HEAL, params=params)
        assert r.status_code == 422 and r.json()["detail"]["code"] == code, (params, r.text)
    assert await _ki(client, monk) == ki and await _hero(test_session_factory, hero) == {"charmed": True, "poisoned": True}


async def test_hand_of_healing_below_level_6_cannot_remove_anything(client, test_session_factory):
    monk, hero = await _mercy_table(client, test_session_factory, 3)
    await _hero_hp(test_session_factory, hero, 10, conditions={"poisoned": True})
    r = await _use(client, monk, HEAL, params=_rm([hero], ["poisoned"], mode="other"))
    assert r.status_code == 422 and await _hero(test_session_factory, hero) == {"poisoned": True}


# --- Panacea e gli automatici sullo stesso meccanismo --------------------------------------------------------------------

async def test_panacea_on_a_seated_ally_removes_poison_and_notes_curses_and_diseases(client, test_session_factory):
    _sid, hero = await seed_session(test_session_factory)
    as_user(GM_ID)
    cid = await _wizard(client, 14, "transmutation")
    await _seat(test_session_factory, cid)
    await _hero_hp(test_session_factory, hero, 10, conditions={"poisoned": True, "blinded": True})
    await _master(client, cid)
    r = await _use(client, cid, PANACEA, params=_rm([hero], mode="other"))
    assert r.status_code == 200, r.text
    assert await _hero(test_session_factory, hero) == {"blinded": True}
    lines = " ".join(x["it"] for x in r.json()["removal"]).lower()
    assert "l'app non la traccia" not in lines  # punto 28: senza una scelta il promemoria sarebbe superfluo, il testo del privilegio lo dice già
    assert "Condizione Avvelenato tolta da" in " ".join(await _history(test_session_factory, hero))


async def test_panacea_28_notes_the_untracked_entries_only_when_chosen(client, test_session_factory):
    _sid, hero = await seed_session(test_session_factory)
    as_user(GM_ID)
    cid = await _wizard(client, 14, "transmutation")
    await _seat(test_session_factory, cid)
    await _master(client, cid)
    r = await _use(client, cid, PANACEA, params=_rm([hero], ["curse"], mode="other"))
    assert r.status_code == 200, r.text
    lines = " ".join(x["it"] for x in r.json()["removal"]).lower()
    assert "maledizione" in lines and "malattia" not in lines


async def test_there_is_no_second_path_clears_is_gone():
    from core.rules.types import OnUse
    assert not hasattr(OnUse(), "clears")


# ---------------------------------------------------------------------------
# I3: incantesimi inseriti a mano o importati, riconosciuti per nome
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,edition,have,chosen,kept", [
    ("Ristorare Inferiore", "2014", ["blinded", "charmed"], ["blinded"], ["charmed"]),
    ("Lesser Restoration", "2024", ["poisoned", "stunned"], ["poisoned"], ["stunned"]),
    ("Parola del Potere Guarire", "2014", ["charmed", "poisoned"], None, ["poisoned"]),
    ("Power Word Heal", "2024", ["charmed", "poisoned"], None, []),
    ("ristorare   superiore", "2014", ["charmed", "petrified"], ["charmed"], ["petrified"]),
])
async def test_a_spell_without_srd_index_is_recognized_by_its_name(client, test_session_factory, name, edition, have, chosen, kept):
    cid, hero = await _table(client, test_session_factory, edition)
    await _hero_hp(test_session_factory, hero, 20, conditions=_on(have))
    level = 9 if "Guarire" in name or "Heal" in name else 5 if "uperiore" in name else 2
    spell = await _named_spell(client, cid, name, level)
    sheet = next(s for s in (await _full(client, cid))["spells"] if s["id"] == spell)
    assert sheet["removal"] and sheet["removal"]["conditions"]
    r = await _cast(client, cid, spell, level, [hero], chosen)
    assert r.status_code == 200, r.text
    assert set(await _hero(test_session_factory, hero)) == set(kept)


async def test_a_removal_looking_spell_that_is_not_recognized_says_so(client, test_session_factory):
    cid, _hero_id = await _table(client, test_session_factory, "2014")
    spell = await _named_spell(client, cid, "Ristorare Minore Homebrew", 2)
    as_user(GM_ID)
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 2})
    assert r.status_code == 200, r.text
    assert "non lo riconosce" in r.json()["removal_result"][0]["it"] and "does not recognize" in r.json()["removal_result"][0]["en"]
    other = await _named_spell(client, cid, "Palla di Fuoco", 3)
    quiet = await client.post(f"/characters/{cid}/spells/{other}/use", json={"slot_level": 3})
    assert quiet.status_code == 200 and "removal_result" not in quiet.json()


# ---------------------------------------------------------------------------
# I5: Calmare Emozioni sospende; le condizioni tornano quando finisce la concentrazione
# ---------------------------------------------------------------------------

async def _calm(client, factory, edition="2014", have=("charmed", "frightened", "blinded")):
    cid, hero = await _table(client, factory, edition)
    await _hero_hp(factory, hero, 20, conditions=_on(list(have)))
    spell = await _named_spell(client, cid, "Calmare Emozioni", 2, srd_index="calm-emotions", concentration=True,
                               duration="Concentrazione, fino a 1 minuto")
    r = await _cast(client, cid, spell, 2, [hero])
    assert r.status_code == 200, r.text
    assert set(await _hero(factory, hero)) == {"blinded"} and (await _full(client, cid))["concentrating_spell_id"] == spell
    return cid, hero, spell


async def _back(factory, hero) -> set[str]:
    return set(await _hero(factory, hero))


async def test_calm_emotions_conditions_come_back_when_the_concentration_is_dropped(client, test_session_factory):
    cid, hero, _spell_id = await _calm(client, test_session_factory)
    as_user(GM_ID)
    assert (await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})).status_code == 200
    assert await _back(test_session_factory, hero) == {"blinded", "charmed", "frightened"}
    assert any("tornata" in d for d in await _history(test_session_factory, hero))
    as_user(GM_ID)
    assert not (await _full(client, cid)).get("active_states")  # lo stato di sospensione è chiuso


async def test_calm_emotions_conditions_come_back_when_the_caster_starts_another_concentration(client, test_session_factory):
    cid, hero, _spell_id = await _calm(client, test_session_factory, "2024")
    other = await _named_spell(client, cid, "Benedizione", 1, concentration=True, duration="Concentrazione, fino a 1 minuto")
    as_user(GM_ID)
    r = await client.post(f"/characters/{cid}/spells/{other}/use", json={"slot_level": 1, "confirm": ["one_slot_per_turn"]})
    assert r.status_code == 200, r.text
    assert await _back(test_session_factory, hero) == {"blinded", "charmed", "frightened"}


async def test_calm_emotions_conditions_come_back_when_the_caster_is_incapacitated(client, test_session_factory):
    cid, hero, _spell_id = await _calm(client, test_session_factory)
    as_user(GM_ID)
    assert (await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"incapacitated": True}})).status_code == 200
    assert await _back(test_session_factory, hero) == {"blinded", "charmed", "frightened"}


async def test_calm_emotions_conditions_come_back_when_the_duration_runs_out(client, test_session_factory):
    cid, hero, spell = await _calm(client, test_session_factory)
    as_user(GM_ID)
    assert (await client.patch(f"/characters/{cid}/concentration", json={"spell_id": spell, "rounds": 1})).status_code == 200
    assert (await client.post(f"/characters/{cid}/rounds/tick")).status_code == 200
    assert await _back(test_session_factory, hero) == {"blinded", "charmed", "frightened"}


async def test_a_condition_removed_another_way_in_the_meantime_does_not_come_back(client, test_session_factory):
    cid, hero, _spell_id = await _calm(client, test_session_factory)
    as_user(PLAYER_ID)
    # la tolgono davvero (per altra via): non è più sospesa
    assert (await client.patch(f"/characters/{hero}/conditions", json={"conditions": {"charmed": False}})).status_code == 200
    as_user(GM_ID)
    assert (await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})).status_code == 200
    assert await _back(test_session_factory, hero) == {"blinded", "frightened"}


async def test_calm_emotions_on_the_caster_comes_back_too(client, test_session_factory):
    cid, hero = await _table(client, test_session_factory, "2014")
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"frightened": True}})
    spell = await _named_spell(client, cid, "Calmare Emozioni", 2, srd_index="calm-emotions", concentration=True,
                               duration="Concentrazione, fino a 1 minuto")
    assert (await _cast(client, cid, spell, 2, ["self"])).status_code == 200
    assert not (await _full(client, cid))["conditions"].get("frightened")
    assert (await client.patch(f"/characters/{cid}/concentration", json={"spell_id": None})).status_code == 200
    assert (await _full(client, cid))["conditions"].get("frightened") is True


# ---------------------------------------------------------------------------
# Giro 2: N1 (testo su sé stessi) e N2 (Panacea porta i PF al massimo)
# ---------------------------------------------------------------------------

def test_outcome_lines_on_yourself_never_name_a_target():
    from core.rules.condition_removal import ConditionRemoval, outcome_lines
    lines = outcome_lines(ConditionRemoval(("poisoned",)), target=None, removed=["poisoned"], absent=["blinded"], untracked=["curse"],
                          wanted=["poisoned"])
    text = " ".join(t[lg] for t in lines for lg in ("it", "en"))
    assert "None" not in text and "Tolto: Avvelenato." in text and "Removed: Poisoned." in text


async def test_an_automatic_self_removal_toast_has_no_none(client):
    from tests.integration.rules.test_2024_barbarian import RAGE, _barbarian, _rage
    from tests.integration.rules.test_2024_barbarian_paths import BERSERKER
    cid = await _barbarian(client, 6, BERSERKER)
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"frightened": True}})
    r = await _rage(client, cid)
    assert r.status_code == 200, r.text
    lines = r.json()["removal"]
    assert lines and not any("None" in x[lg] for x in lines for lg in ("it", "en"))
    assert any(x["it"].startswith("Tolto: ") for x in lines)


async def test_panacea_on_a_seated_ally_restores_all_hit_points_with_history_on_the_receiver(client, test_session_factory):
    _sid, hero = await seed_session(test_session_factory)
    as_user(GM_ID)
    cid = await _wizard(client, 14, "transmutation")
    await _seat(test_session_factory, cid)
    await _hero_hp(test_session_factory, hero, 7, maximum=40, conditions={"poisoned": True})
    await _master(client, cid)
    r = await _use(client, cid, PANACEA, params=_rm([hero], mode="other"))
    assert r.status_code == 200, r.text
    assert (await _hero_state(test_session_factory, hero))[0] == 40
    assert r.json()["received"] == {"name": r.json()["received"]["name"], "healed": 33}
    assert any("Cura: +" in h for h in await _history(test_session_factory, hero))
    assert not any("Cura: +0" in h for h in await _history(test_session_factory, cid))  # chi usa la pietra non cura nulla


async def test_panacea_reaches_the_effective_maximum_with_a_bonus(client, test_session_factory, monkeypatch):
    import api.services.effects as effects
    async def _bonus(_s, _c, path):  # +10 ai PF massimi, come una regola homebrew passiva
        return 10 if path == "character.hit_points_max" else 0
    monkeypatch.setattr(effects, "get_passive_modifiers", _bonus)
    _sid, hero = await seed_session(test_session_factory)
    as_user(GM_ID)
    cid = await _wizard(client, 14, "transmutation")
    await _seat(test_session_factory, cid)
    await _hero_hp(test_session_factory, hero, 0, maximum=40, conditions={"poisoned": True})
    await _master(client, cid)
    r = await _use(client, cid, PANACEA, params=_rm([hero], mode="other"))
    assert r.status_code == 200, r.text
    assert (await _hero_state(test_session_factory, hero))[0] == 50
