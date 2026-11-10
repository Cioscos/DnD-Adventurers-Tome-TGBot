"""Minori 57, 94-99: test mancanti (Aiuto della Terra su un alleato della serata; lancio degli effetti degli incantesimi: bersagli, rilanci, scelte, annullo del turno, istantanei)."""
from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import select

from api.services.effects import raises_hp_max
from api.services.spell_effects import _NO_SHEET_TEXT, _OUTSIDE_TEXT
from core.db.models import Character
from core.rules.catalog.spells import SPELL_EFFECTS
from core.rules.spell_effects import SpellEffect, SpellTarget, SpellVariant
from core.rules.states import SPELL_CAST_TYPE
from core.rules.types import Modifier
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
from tests.integration.rules.test_2014_bard import _ability
from tests.integration.rules.test_spell_effects_cast import SOF, STATE, _ac, _caster, _cast, _full, _slots_used, _states, _table
from tests.integration.rules.test_2014_fighter_eldritch_knight import _spell
from tests.integration.rules.test_spell_effects_defenses import _cast as _cast_at
from tests.integration.rules.test_spell_effects_defenses import _table as _defense_table


def _code(r) -> str:
    return r.json()["detail"]["code"]


# 94: Aiuto e Passo Lungo con i bersagli veri del tavolo

async def test_94_longstrider_takes_one_target_per_slot_level(client, test_session_factory):
    hero, caster, spell = await _defense_table(client, test_session_factory, "Longstrider", "longstrider", 1)
    as_user(GM_ID)
    assert (await client.post(f"/characters/{caster}/spell_slots", json={"level": 2, "total": 1})).status_code == 201
    assert _code(await client.post(f"/characters/{caster}/spells/{spell}/use", json={"slot_level": 1, "targets": [hero, caster]})) == "invalid_target"
    assert await _slots_used(client, caster) == 0  # rifiutato prima di spendere
    r = await client.post(f"/characters/{caster}/spells/{spell}/use", json={"slot_level": 2, "targets": [hero, caster]})
    assert r.status_code == 200, r.text
    assert {a["id"] for a in r.json()["spell_effects"]["applied"]} == {hero, caster}


async def test_94_aid_never_takes_more_than_three_targets(client, test_session_factory):
    hero, caster, aid = await _defense_table(client, test_session_factory, "Aid", "aid", 2)
    as_user(GM_ID)
    r = await client.post(f"/characters/{caster}/spells/{aid}/use", json={"slot_level": 2, "targets": [hero, caster, 9991, 9992]})
    assert r.status_code == 422 and _code(r) == "invalid_target"
    assert await _slots_used(client, caster) == 0
    spells = {s["srd_index"]: s for s in (await client.get(f"/characters/{caster}/spells")).json()}
    assert spells["aid"]["effect"]["max_targets_by_slot"]["2"] == 3 and spells["aid"]["effect"]["max_targets_by_slot"]["5"] == 3


# 95: bersagli assenti, rilancio su un altro bersaglio, scelta non valida

async def test_95_targets_left_out_are_the_same_as_casting_on_yourself(client, test_session_factory):
    _, _, caster, spell = await _table(client, test_session_factory)
    base = await _ac(client, caster, GM_ID)
    r = await _cast(client, caster, spell, None)
    assert r.status_code == 200, r.text
    assert r.json()["spell_effects"]["applied"] == [{"id": caster, "name": "Chierico"}]
    assert await _ac(client, caster, GM_ID) == base + 2
    [state] = await _states(client, caster, GM_ID)
    assert state["data"]["caster_id"] == caster


async def test_95_recasting_on_another_target_takes_the_effect_from_the_old_one(client, test_session_factory):
    hero, caster, _ = await _defense_table(client, test_session_factory, "Longstrider", "longstrider", 1)
    as_user(GM_ID)  # senza concentrazione: solo il rilancio toglie lo stato al vecchio bersaglio
    spell = (await client.post(f"/characters/{caster}/spells", json={"name": "Passo Veloce", "srd_index": "longstrider", "level": 1})).json()["id"]
    key = "spell:longstrider"
    await _cast_at(client, caster, spell, [hero], level=1)
    assert len(await _states(client, hero, PLAYER_ID, key)) == 1
    await _cast_at(client, caster, spell, [caster], level=1)
    assert await _states(client, hero, PLAYER_ID, key) == []
    assert len(await _states(client, caster, GM_ID, key)) == 1
    [clock] = await _states(client, caster, GM_ID, "spell_cast:longstrider")  # un solo orologio, quello dell'ultimo lancio
    assert clock["data"]["state_data"]["targets"] == 1


async def test_95_an_invalid_choice_is_refused_before_spending_the_slot(client, test_session_factory):
    _, hero, caster, spell = await _table(client, test_session_factory)
    r = await _cast(client, caster, spell, [hero], choices={"damage_type": "fire"})  # Scudo della Fede non ha scelte
    assert r.status_code == 422 and _code(r) == "invalid_choice", r.text
    assert await _states(client, hero, PLAYER_ID) == []
    as_user(GM_ID)
    assert await _slots_used(client, caster) == 0 and (await _full(client, caster))["concentrating_spell_id"] is None


# 96: un lancio senza la scelta toglie la voce del tipo di quell'incantesimo e non tocca le altre

async def test_96_a_cast_without_the_choice_drops_only_the_type_of_that_spell(client, test_session_factory):
    cid = (await client.post("/characters", json={"name": "Chierico"})).json()["id"]
    await client.post(f"/characters/{cid}/spell_slots", json={"level": 3, "total": 4})
    glyph = await _spell(client, cid, "Glifo di Interdizione", 3, srd_index="glyph-of-warding")
    orb = await _spell(client, cid, "Sfera Cromatica", 1, srd_index="chromatic-orb", damage_dice="3d8", damage_type="acid", attack_save="DEX")

    async def stored() -> dict:
        async with test_session_factory() as s:
            return dict(((await s.get(Character, cid)).settings or {}).get(SPELL_CAST_TYPE) or {})

    use = lambda spell, **choices: client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 3, "choices": choices})  # noqa: E731
    assert (await use(orb, damage_type="cold")).status_code == 200
    assert (await use(glyph, glyph="explosive", damage_type="fire")).status_code == 200
    assert await stored() == {"chromatic_orb": "cold", "glyph_of_warding": "fire"}
    assert (await use(glyph, glyph="spell")).status_code == 200  # stesso incantesimo, questa volta senza tipo
    assert await stored() == {"chromatic_orb": "cold"}


# 98: l'annullo del turno riapre la concentrazione scaduta per round e con lei l'effetto sull'alleato

async def test_98_undoing_the_turn_after_the_concentration_ran_out_gives_the_effect_back(client, test_session_factory, monkeypatch):
    from tests.integration._encounter_helpers import setup_full_encounter
    from tests.integration._telegram_stub import install_fake_telegram
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)
    assert (await client.post(f"/sessions/{sid}/encounter/start", json={})).status_code == 200
    async with test_session_factory() as s:
        hero = (await s.execute(select(Character).where(Character.name == "Eroe"))).scalar_one().id
    as_user(PLAYER_ID)
    spell = (await client.post(f"/characters/{hero}/spells", json={"name": "Shield of Faith", "srd_index": SOF, "level": 1, "is_concentration": True})).json()["id"]
    assert (await client.post(f"/characters/{hero}/spell_slots", json={"level": 1, "total": 2})).status_code == 201
    base = await _ac(client, hero, PLAYER_ID)
    assert (await _cast(client, hero, spell, None, user=PLAYER_ID)).status_code == 200
    async with test_session_factory() as s:  # ultimo round di concentrazione: finisce all'inizio del prossimo turno del PG
        ch = await s.get(Character, hero)
        assert ch.concentrating_spell_id == spell
        ch.settings = {**(ch.settings or {}), "concentration_rounds_left": 1}
        await s.commit()
    as_user(GM_ID)
    for _ in range(3):  # PG -> goblin -> goblin -> PG
        assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200
    as_user(PLAYER_ID)
    full = await _full(client, hero)
    assert full["concentrating_spell_id"] is None and await _ac(client, hero, PLAYER_ID) == base and not await _states(client, hero, PLAYER_ID, STATE)
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/prev-turn")).status_code == 200
    as_user(PLAYER_ID)
    full = await _full(client, hero)
    assert full["concentrating_spell_id"] == spell and await _ac(client, hero, PLAYER_ID) == base + 2
    assert len(await _states(client, hero, PLAYER_ID, STATE)) == 1


# 99: una voce istantanea (``track=False``) non lascia stato né orologio, solo il testo per il GM

async def test_99_an_instant_text_spell_leaves_no_state_and_no_clock(client, test_session_factory):
    _, caster, spell = await _defense_table(client, test_session_factory, "Wish", "wish", 9)
    r = await _cast_at(client, caster, spell, None, level=9)
    fx = r.json()["spell_effects"]
    assert fx["applied"] == [] and fx["text"]["it"] and fx["text"]["en"]
    as_user(GM_ID)
    assert not (await _full(client, caster))["active_states"]


# 97: un effetto senza testo proprio, lanciato dentro la serata, non dice mai «fuori da una serata»

async def test_97_an_effect_without_its_own_text_in_the_evening_says_nothing_or_that_no_sheet_has_it(client, test_session_factory):
    _, hero, caster, spell = await _table(client, test_session_factory)
    r = await _cast(client, caster, spell, [hero])  # sulla scheda di un alleato seduto: l'effetto c'è, nessun testo da dare al GM
    assert r.json()["spell_effects"]["text"] is None
    r = await _cast(client, caster, spell, [])  # su una creatura senza scheda: lo riferisce al GM, ma non con il testo «fuori serata»
    text = r.json()["spell_effects"]["text"]
    assert text == _NO_SHEET_TEXT and text != _OUTSIDE_TEXT


# 101 (dal Task 11): lo stato chiuso senza edizione salvata usa quella del bersaglio, non il 2014 fisso

def test_101_a_closed_state_without_a_saved_edition_reads_the_variant_of_the_target(monkeypatch):
    only_2024 = SpellEffect("zz_hp", ("zz-hp",), ("Zz",), SpellTarget("ally"), {"2024": SpellVariant(modifiers=lambda d: (Modifier("hp_max", 10),))})
    monkeypatch.setitem(SPELL_EFFECTS, "zz_hp", only_2024)
    state = {"key": "spell:zz_hp", "data": {"spell_key": "zz_hp"}}
    assert raises_hp_max([state], SimpleNamespace(rules_edition="2024")) is True
    assert raises_hp_max([state], SimpleNamespace(rules_edition="2014")) is False  # nel 2014 l'incantesimo non esiste
    assert raises_hp_max([{**state, "data": {**state["data"], "edition": "2024"}}], SimpleNamespace(rules_edition="2014")) is True  # quella salvata vince


# 57: Aiuto della Terra su un alleato seduto alla serata, dall'inizio alla fine (finora solo il testo era provato da un test unitario)

async def test_57_lands_aid_on_a_seated_ally_heals_them_spends_wild_shape_and_tells_it_without_the_gm_hint(client, test_session_factory, monkeypatch):
    from tests.integration.rules.test_2014_bard_inspiration import _seat
    from tests.integration.rules.test_2024_druid_circles import _circle
    from tests.integration._encounter_helpers import seed_session
    monkeypatch.setattr("core.rules.catalog.y2024.druid.random.randint", lambda a, b: 3)
    _, hero = await seed_session(test_session_factory)
    as_user(GM_ID)
    druid = await _circle(client, "land", 3, wisdom=16)
    await _seat(test_session_factory, druid, GM_ID)
    async with test_session_factory() as s:
        ally = await s.get(Character, hero)
        ally.hit_points, ally.current_hit_points = 40, 5
        await s.commit()
    uses = lambda: _ability(client, druid, "druid.wild_shape")  # noqa: E731
    before = (await uses())["uses"]
    r = await client.post(f"/characters/{druid}/features/druid.lands_aid/use", json={"params": {"mode": "other", "target_character_id": hero}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["received"] == {"name": "Eroe", "healed": 6} and body["healed"] == 0  # 2d6 con i dadi a 3: va all'alleato, non al druido
    assert "GM" not in body["message"]["it"] + body["message"]["en"] and all(t == t.rstrip() for t in body["message"].values())
    assert (await uses())["uses"] == before - 1  # un uso di Forma Selvatica
    async with test_session_factory() as s:
        assert (await s.get(Character, hero)).current_hit_points == 11


# I2 (giro 1): una punizione lanciata da elenco non tira il danno; nel 2024 costa l'azione bonus

async def test_i2_a_smite_in_the_list_says_its_damage_comes_from_the_hit_in_both_editions(client):
    for edition in ("2014", "2024"):
        cid = (await client.post("/characters", json={"name": "Paladina"})).json()["id"]
        await client.patch(f"/characters/{cid}", json={"rules_edition": edition})
        for srd, name in (("searing-smite", "Searing Smite"), ("fireball", "Fireball")):
            assert (await client.post(f"/characters/{cid}/spells", json={"name": name, "srd_index": srd, "level": 1 if srd != "fireball" else 3})).status_code == 201
        spells = {s["srd_index"]: s for s in (await client.get(f"/characters/{cid}/spells")).json()}
        assert spells["searing-smite"]["effect"]["hit_damage"] is True, edition
        assert spells["fireball"]["effect"] is None or spells["fireball"]["effect"]["hit_damage"] is False


async def test_i2_a_2024_smite_cast_from_the_list_needs_the_bonus_action(client):
    cid = (await client.post("/characters", json={"name": "Paladina"})).json()["id"]
    await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})
    spell = (await client.post(f"/characters/{cid}/spells", json={"name": "Searing Smite", "srd_index": "searing-smite", "level": 1})).json()["id"]
    await client.post(f"/characters/{cid}/spell_slots", json={"level": 1, "total": 2})
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus", "used": True})
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 1})
    assert r.status_code == 409 and _code(r) == "turn_slot_used"
    assert await _slots_used(client, cid) == 0  # rifiutato prima di spendere
    await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus", "used": False})
    assert (await client.post(f"/characters/{cid}/spells/{spell}/use", json={"slot_level": 1})).status_code == 200
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]["bonus_used"] is True
