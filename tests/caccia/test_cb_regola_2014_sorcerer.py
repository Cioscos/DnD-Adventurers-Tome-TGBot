"""Controlli della zona regola:2014/sorcerer."""
import asyncio
import json
from pathlib import Path

import pytest

from tests.integration.rules.test_2014_bard import _ability, _full, _roll_keys, _use
from tests.integration.rules.test_2014_fighter_eldritch_knight import _spell
from tests.integration.rules.test_2014_paladin import _new_turn, _rest
from tests.integration.rules.test_2014_sorcerer import SP, _points, _set_points, _slots, _sorcerer
from tests.integration.rules.test_2014_sorcerer_metamagic import _caster, _damage, _use_spell
from tests.integration.rules.test_2014_sorcerer_origins import _draconic

TIDES = "sorcerer.tides_of_chaos_advantage"
QUICKENED = "sorcerer.metamagic_quickened"
AFFINITY = "sorcerer.elemental_affinity"
EMPOWERED = "sorcerer.metamagic_empowered"
CREATE, CONVERT = "sorcerer.flexible_casting_create", "sorcerer.flexible_casting_convert"
PROGRESSION = Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "class-progression.json"


async def _surge(client, cid, **body) -> dict:
    r = await client.post(f"/characters/{cid}/wild-magic/surge", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2011", fonte="2014 · Stregone · Onde di Caos · pag. 111", zona="regola:2014/sorcerer", voce="regola",
                    copre=["carta:2014/classes/sorcerer.md#Onde di Caos / Tides of Chaos (Magia Selvaggia 1, pag. 111)",
                           "GET /characters/{char_id}/roll-options"])
@pytest.mark.parametrize("roll", ["initiative", "death_save"])
async def test_onde_di_caos_vale_anche_per_l_iniziativa_e_per_il_ts_contro_la_morte(client, roll):
    # L'iniziativa è una prova di Destrezza e il TS contro la morte è un tiro salvezza: Onde di Caos li copre come gli altri
    cid = await _sorcerer(client, 1, "wild_magic")
    assert TIDES in await _roll_keys(client, cid, "save", ability="dexterity")
    assert TIDES in await _roll_keys(client, cid, roll)


@pytest.mark.caccia(id="CB-2012",
                    fonte="2014 · Stregone · Incantesimo Rapido · pag. 110; Capitolo 10 · Tempo di Lancio, Azione Bonus · pag. 202",
                    zona="regola:2014/sorcerer", voce="interazione",
                    copre=["carta:2014/classes/sorcerer.md#Incantesimo Rapido / Quickened Spell (Stregone 3, pag. 110)",
                           "carta:2014/general.md#Tempo di Lancio / Casting Time (pag. 202)",
                           "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("quickened_level", [1, 0])
@pytest.mark.xfail(strict=True, reason="CB-2012: difforme dal manuale, confermato")
async def test_incantesimo_rapido_dopo_un_incantesimo_di_livello_lanciato_con_l_azione_chiede_conferma(client, quickened_level):
    # Un incantesimo lanciato con l'azione bonus lascia nel turno solo un trucchetto da 1 azione, in qualsiasi ordine
    cid = await _caster(client, 5, "quickened")
    first = await _spell(client, cid, "Primo", 1)
    second = await _spell(client, cid, "Secondo", quickened_level)
    assert (await _use_spell(client, cid, first, slot_level=1)).status_code == 200
    r = await _use_spell(client, cid, second, QUICKENED, slot_level=quickened_level or None)
    assert r.status_code == 409, r.text[:200]
    assert r.json()["detail"]["code"] == "cast_confirm" and "bonus_spell" in r.json()["detail"]["warnings"]
    assert await _points(client, cid) == 5


@pytest.mark.caccia(id="CB-2013", fonte="2014 · Stregone · Affinità Elementale · pag. 111", zona="regola:2014/sorcerer", voce="regola",
                    copre=["carta:2014/classes/sorcerer.md#Affinità Elementale / Elemental Affinity (Discendenza Draconica 6, pag. 111)",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_affinita_elementale_somma_il_carisma_a_un_solo_tiro_di_danno_per_lancio(client):
    cid = await _draconic(client, 6, "red", charisma=18)
    spell = await _spell(client, cid, "Raggio rovente", 2, attack_save="ATK", damage_dice="2d6", damage_type="fire", range_area="36 m")
    assert (await _use_spell(client, cid, spell, slot_level=2)).status_code == 200
    assert (await _damage(client, cid, spell, casting_level=2, main_rolls=[3, 3], options=[AFFINITY]))["total"] == 3 + 3 + 4
    # stesso lancio, secondo tiro di danno (il secondo raggio): il Carisma non si somma di nuovo
    r = await client.post(f"/characters/{cid}/spells/{spell}/roll_damage",
                          json={"casting_level": 2, "main_rolls": [3, 3], "options": [AFFINITY]})
    assert r.status_code == 409 or r.json()["total"] == 3 + 3, r.text[:200]


@pytest.mark.caccia(id="CB-2014", fonte="2014 · Stregone · Impulso di Magia Selvaggia, tabella 59-60 · pag. 112; Multiclasse · Magia del Patto · pag. 164",
                    zona="regola:2014/sorcerer", voce="interazione",
                    copre=["carta:2014/classes/sorcerer.md#Impulso di Magia Selvaggia / Wild Magic Surge (Magia Selvaggia 1, pag. 111)",
                           "POST /characters/{char_id}/wild-magic/surge"])
async def test_impulso_59_60_recupera_anche_lo_slot_del_patto_speso(client):
    cid = await _sorcerer(client, 1, "wild_magic")
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "warlock", "level": 1})).status_code == 201
    pact = next(s for s in (await _full(client, cid))["spell_slots"] if s["is_pact"])
    assert (await client.patch(f"/characters/{cid}/spell_slots/{pact['id']}", json={"used": 1})).status_code == 200
    body = await _surge(client, cid, die=1, percentile=[59])
    assert body["applied"]["slot_level"] == 1
    assert next(s for s in (await _full(client, cid))["spell_slots"] if s["is_pact"])["used"] == 0


@pytest.mark.caccia(id="CB-2015", fonte="2014 · Stregone · Metamagia e Incantesimo Potenziato · pag. 109-110", zona="regola:2014/sorcerer",
                    voce="regola",
                    copre=["carta:2014/classes/sorcerer.md#Incantesimo Potenziato / Empowered Spell (Stregone 3, pag. 110)",
                           "carta:2014/classes/sorcerer.md#Metamagia / Metamagic (Stregone 3, pag. 109)",
                           "POST /characters/{char_id}/last-damage/options"])
@pytest.mark.xfail(strict=True, reason="CB-2015: difforme dal manuale, confermato")
async def test_incantesimo_potenziato_si_usa_una_volta_sola_sullo_stesso_danno(client):
    # Potenziato si somma a un'altra opzione, non a sé stesso: due usi ritirerebbero più dadi del Carisma
    cid = await _caster(client, 5, "empowered", charisma=16)
    spell = await _spell(client, cid, "Palla di fuoco", 3, attack_save="DEX", damage_dice="8d6", damage_type="fire")
    assert (await _use_spell(client, cid, spell, slot_level=3)).status_code == 200
    await _damage(client, cid, spell, casting_level=3, main_rolls=[1] * 8)
    first = await client.post(f"/characters/{cid}/last-damage/options", json={"options": [EMPOWERED], "option_inputs": {}, "reroll": [0, 1, 2]})
    assert first.status_code == 200, first.text[:200]
    second = await client.post(f"/characters/{cid}/last-damage/options", json={"options": [EMPOWERED], "option_inputs": {}, "reroll": [3, 4, 5]})
    assert second.status_code == 409, second.text[:200]
    assert await _points(client, cid) == 4


@pytest.mark.caccia(id="CB-2016",
                    fonte="2014 · Stregone · Incantesimo Raddoppiato e Incantesimo Distante · pag. 110; Capitolo 10 · Gittata · pag. 202-203",
                    zona="regola:2014/sorcerer", voce="regola",
                    copre=["carta:2014/classes/sorcerer.md#Incantesimo Raddoppiato / Twinned Spell (Stregone 3, pag. 110)",
                           "carta:2014/classes/sorcerer.md#Incantesimo Distante / Distant Spell (Stregone 3, pag. 110)",
                           "carta:2014/general.md#Gittata / Range (pag. 202-203)",
                           "GET /characters/{char_id}/roll-options"])
@pytest.mark.parametrize("option", ["sorcerer.metamagic_twinned", "sorcerer.metamagic_distant"])
async def test_la_gittata_incantatore_del_manuale_esclude_raddoppiato_e_distante_come_personale(client, option):
    # Il manuale italiano chiama «Incantatore» la gittata personale: un cono che parte da chi lancia non ha una gittata da raddoppiare
    cid = await _caster(client, 10, "twinned", "distant")
    own = await _spell(client, cid, "Mani brucianti", 1, range_area="Personale (cono di 4,5 m)", attack_save="DEX")
    assert option not in await _roll_keys(client, cid, "cast", spell_id=own)
    spell = await _spell(client, cid, "Cono dal manuale", 1, range_area="Incantatore (cono di 4,5 m)", attack_save="DEX")
    assert option not in await _roll_keys(client, cid, "cast", spell_id=spell)


@pytest.mark.caccia(id="CB-2017", fonte="2014 · Stregone · Incantesimo Distante · pag. 110", zona="regola:2014/sorcerer", voce="regola",
                    copre=["carta:2014/classes/sorcerer.md#Incantesimo Distante / Distant Spell (Stregone 3, pag. 110)",
                           "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("range_area,shown", [("1,5 km", "3 km"), ("500 miglia", "1000 miglia")])
async def test_incantesimo_distante_raddoppia_la_gittata_in_chilometri_e_miglia_senza_cambiare_unita(client, range_area, shown):
    # Chiaroveggenza nel manuale italiano ha gittata 1,5 km: raddoppiata è 3 km, non 3 m
    cid = await _caster(client, 10, "distant")
    spell = await _spell(client, cid, "Lontano", 3, range_area=range_area)
    r = await _use_spell(client, cid, spell, "sorcerer.metamagic_distant", slot_level=3)
    assert r.status_code == 200, r.text[:200]
    assert shown in r.json()["option_result"]["effects"][0]["it"]


# ---------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2018", fonte="2014 · Stregone · Fonte di Magia · pag. 109", zona="regola:2014/sorcerer", voce="limiti",
                    copre=["carta:2014/classes/sorcerer.md#Fonte di Magia / Font of Magic (Stregone 2, pag. 109)", "POST /characters"])
@pytest.mark.parametrize("level,points", [(1, None), (2, 2), (20, 20)])
async def test_i_punti_stregoneria_arrivano_al_2_livello_e_valgono_il_livello_da_stregone(client, level, points):
    row = await _ability(client, await _sorcerer(client, level), SP)
    assert (row["max_uses"] if row else None) == points


@pytest.mark.caccia(id="CB-2019", fonte="2014 · Stregone · Incantesimi Flessibili: Creare Slot · pag. 109", zona="regola:2014/sorcerer",
                    voce="regola",
                    copre=["carta:2014/classes/sorcerer.md#Incantesimi Flessibili: Creare Slot Incantesimo / Flexible Casting: Creating Spell Slots (Stregone 2, pag. 109)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.parametrize("slot,cost", [(1, 2), (2, 3), (3, 5), (4, 6), (5, 7)])
async def test_creare_uno_slot_costa_i_punti_della_tabella(client, slot, cost):
    cid = await _sorcerer(client, 12)
    before = (await _slots(client, cid))[slot][0]
    r = await _use(client, cid, CREATE, params={"slot_level": str(slot)})
    assert r.status_code == 200, r.text
    assert await _points(client, cid) == 12 - cost and (await _slots(client, cid))[slot][0] == before + 1


@pytest.mark.caccia(id="CB-2020", fonte="2014 · Stregone · Ripristino Stregonesco · pag. 110", zona="regola:2014/sorcerer", voce="limiti",
                    copre=["carta:2014/classes/sorcerer.md#Ripristino Stregonesco / Sorcerous Restoration (Stregone 20, pag. 110)",
                           "POST /characters/{char_id}/rest"])
@pytest.mark.parametrize("level,back", [(19, 0), (20, 4)])
async def test_il_riposo_breve_ridà_4_punti_solo_dal_20_livello(client, level, back):
    cid = await _sorcerer(client, level)
    await _set_points(client, cid, level - 6)
    await _rest(client, cid, "short")
    assert await _points(client, cid) == level - 6 + back


@pytest.mark.caccia(id="CB-2021", fonte="2014 · Stregone · Impulso di Magia Selvaggia · pag. 111; 2024 · Stregone · Impulso di Magia Selvaggia · pag. 149",
                    zona="regola:2014/sorcerer", voce="edizioni",
                    copre=["carta:2014/classes/sorcerer.md#Impulso di Magia Selvaggia / Wild Magic Surge (Magia Selvaggia 1, pag. 111)",
                           "carta:2024/classes/sorcerer.md#Impulso di Magia Selvaggia / Wild Magic Surge (Magia Selvaggia 3, pag. 149)",
                           "POST /characters/{char_id}/wild-magic/surge"])
async def test_l_impulso_si_apre_con_1_nel_2014_e_con_20_nel_2024(client):
    old = await _sorcerer(client, 3, "wild_magic")
    new = await _sorcerer(client, 3, "wild_magic")
    assert (await client.patch(f"/characters/{new}", json={"rules_edition": "2024"})).status_code == 200
    assert (await _surge(client, old, die=20))["triggered"] is False
    await _new_turn(client, old)
    assert (await _surge(client, old, die=1, percentile=[97]))["triggered"] is True
    assert (await _surge(client, new, die=1))["triggered"] is False


@pytest.mark.caccia(id="CB-2022", fonte="2014 · Stregone · Resilienza Draconica e Fonte di Magia · pag. 109-110; Multiclasse · pag. 163",
                    zona="regola:2014/sorcerer", voce="interazione",
                    copre=["carta:2014/classes/sorcerer.md#Resilienza Draconica / Draconic Resilience (Discendenza Draconica 1, pag. 110)",
                           "carta:2014/classes/sorcerer.md#Multiclasse: Stregone / Multiclassing: Sorcerer (Multiclasse, pag. 163)",
                           "POST /characters/{char_id}/classes"])
async def test_in_multiclasse_pf_della_resilienza_e_punti_contano_solo_i_livelli_da_stregone(client):
    r = await client.post("/characters", json={"name": "Mago", "initial_class": {"class_name": "wizard", "level": 3}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "sorcerer", "level": 2, "subclass": "Discendenza Draconica"})
    assert r.status_code == 201, r.text
    full = await _full(client, cid)
    assert full["computed"]["hp_max_effective"] - full["hit_points"] == 2
    assert (await _ability(client, cid, SP))["max_uses"] == 2


@pytest.mark.caccia(id="CB-2023", fonte="2014 · Stregone · Incantesimi Flessibili: Creare Slot · pag. 109", zona="regola:2014/sorcerer",
                    voce="persistenza",
                    copre=["carta:2014/classes/sorcerer.md#Incantesimi Flessibili: Creare Slot Incantesimo / Flexible Casting: Creating Spell Slots (Stregone 2, pag. 109)",
                           "GET /characters/{char_id}/export", "POST /characters/import"])
async def test_lo_slot_creato_resta_dopo_export_e_import_e_svanisce_col_riposo_lungo(client):
    cid = await _sorcerer(client, 5)
    assert (await _use(client, cid, CREATE, params={"slot_level": "2"})).status_code == 200
    exported = await client.get(f"/characters/{cid}/export")
    r = await client.post("/characters/import", json=exported.json())
    assert r.status_code == 201, r.text
    copy = r.json()["id"]
    assert (await _slots(client, copy))[2] == (4, 0) and await _points(client, copy) == 2
    await _rest(client, copy, "long")
    assert (await _slots(client, copy))[2] == (3, 0)


@pytest.mark.caccia(id="CB-2024", fonte="2014 · Stregone · Incantesimi Flessibili: Convertire uno Slot · pag. 109", zona="regola:2014/sorcerer",
                    voce="ripetizione",
                    copre=["carta:2014/classes/sorcerer.md#Incantesimi Flessibili: Convertire uno Slot in Punti / Flexible Casting: Converting a Spell Slot to Sorcery Points (Stregone 2, pag. 109)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_due_conversioni_insieme_spendono_uno_slot_e_danno_i_punti_una_volta(client):
    cid = await _sorcerer(client, 9)
    await _set_points(client, cid, 0)
    first, second = await asyncio.gather(*(_use(client, cid, CONVERT, params={"slot_level": "3"}) for _ in range(2)))
    assert sorted((first.status_code, second.status_code)) == [200, 409], (first.text, second.text)
    assert await _points(client, cid) == 3 and (await _slots(client, cid))[3] == (3, 1)


# tabella di classe dello Stregone 2014: bonus di competenza e slot dal 1° al 9° livello
_TABLE = [
    (2, [2]), (2, [3]), (2, [4, 2]), (2, [4, 3]), (3, [4, 3, 2]), (3, [4, 3, 3]), (3, [4, 3, 3, 1]), (3, [4, 3, 3, 2]),
    (4, [4, 3, 3, 3, 1]), (4, [4, 3, 3, 3, 2]), (4, [4, 3, 3, 3, 2, 1]), (4, [4, 3, 3, 3, 2, 1]), (5, [4, 3, 3, 3, 2, 1, 1]),
    (5, [4, 3, 3, 3, 2, 1, 1]), (5, [4, 3, 3, 3, 2, 1, 1, 1]), (5, [4, 3, 3, 3, 2, 1, 1, 1]), (6, [4, 3, 3, 3, 2, 1, 1, 1, 1]),
    (6, [4, 3, 3, 3, 3, 1, 1, 1, 1]), (6, [4, 3, 3, 3, 3, 2, 1, 1, 1]), (6, [4, 3, 3, 3, 3, 2, 2, 1, 1]),
]


@pytest.mark.caccia(id="CB-2025", fonte="2014 · Stregone · Tabella di classe · pag. 108", zona="regola:2014/sorcerer", voce="regola",
                    copre=["carta:2014/classes/sorcerer.md#Incantesimi / Spellcasting (Stregone 1, pag. 109)"])
def test_la_progressione_del_frontend_ha_competenza_e_slot_della_tabella_dello_stregone():
    rows = json.loads(PROGRESSION.read_text(encoding="utf-8"))["Stregone"]
    got = [(r["proficiency_bonus"], [n for n in r["spell_slots"] if n]) for r in rows]
    assert got == _TABLE
