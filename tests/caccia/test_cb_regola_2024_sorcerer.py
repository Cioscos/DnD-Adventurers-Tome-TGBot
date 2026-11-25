"""Controlli della zona regola:2024/sorcerer."""
import asyncio
import json
from pathlib import Path

import pytest

from tests.integration.rules.test_2014_bard import _ability, _full, _roll_keys, _use
from tests.integration.rules.test_2014_fighter_eldritch_knight import _spell
from tests.integration.rules.test_2014_paladin import _rest, _turn
from tests.integration.rules.test_2014_sorcerer import _points, _set_points, _slots
from tests.integration.rules.test_2014_sorcerer_metamagic import _caster as _caster14, _use_spell as _use_spell14
from tests.integration.rules.test_2024_sorcerer import (
    CONVERT, CREATE, EMPOWERED, HEIGHTENED, QUICKENED, RESTORATION, TWINNED, _cast, _caster24, _damage, _pending, _sorcerer24,
)
from tests.integration.rules.test_2024_sorcerer_subclasses import _affinity, _make, _spells

PROGRESSION = Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "class-progression.json"
AFFINITY = "sorcerer.elemental_affinity"
RESTORE_OWN = "sorcerer.restore_balance_own_roll"


async def _hidden(client, cid) -> None:
    """Azione Nascondersi 2024: Furtività di almeno 15, poi Invisibile."""
    r = await client.post(f"/characters/{cid}/skills/stealth/roll", json={"die": 20})
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/hide")
    assert r.status_code == 200, r.text
    assert (await _full(client, cid))["conditions"].get("invisible") is True


# ---------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2611", fonte="2024 · Stregone · Incantesimo Rapido · pag. 142", zona="regola:2024/sorcerer", voce="interazione",
                    copre=["carta:2024/classes/sorcerer.md#Incantesimo Rapido / Quickened Spell (Metamagia, pag. 142)",
                           "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.xfail(strict=True, reason="CB-2611: difforme dal manuale, confermato")
async def test_dopo_un_trucchetto_rapido_nessun_incantesimo_di_livello_nello_stesso_turno(client):
    # Incantesimo Rapido vieta di lanciare dopo, nello stesso turno, un incantesimo di livello 1 o più, anche se quello reso rapido era un trucchetto
    cid = await _caster24(client, 6, "quickened")
    cantrip = await _spell(client, cid, "Luce", 0)
    spell = await _spell(client, cid, "Charme", 1)
    assert (await _cast(client, cid, cantrip, QUICKENED)).status_code == 200
    before = (await _slots(client, cid))[1]
    r = await _cast(client, cid, spell, slot_level=1)
    assert r.status_code == 409, r.text[:200]
    assert (await _slots(client, cid))[1] == before


@pytest.mark.caccia(id="CB-2612", fonte="2024 · Stregone · Metamagia e Incantesimo Potenziato · pag. 141-142", zona="regola:2024/sorcerer",
                    voce="regola",
                    copre=["carta:2024/classes/sorcerer.md#Incantesimo Potenziato / Empowered Spell (Metamagia, pag. 142)",
                           "carta:2024/classes/sorcerer.md#Metamagia / Metamagic (Stregone 2, pag. 141)",
                           "POST /characters/{char_id}/last-damage/options"])
@pytest.mark.xfail(strict=True, reason="CB-2612: difforme dal manuale, confermato")
async def test_incantesimo_potenziato_2024_una_volta_sola_sullo_stesso_danno(client):
    # Potenziato si somma a un'altra opzione, non a sé stesso: due usi ritirerebbero più dadi del Carisma
    cid = await _caster24(client, 5, "empowered", charisma=16)
    spell = await _spell(client, cid, "Palla di fuoco", 3, attack_save="DEX", damage_dice="8d6", damage_type="fire")
    assert (await _cast(client, cid, spell, slot_level=3)).status_code == 200
    await _damage(client, cid, spell, casting_level=3, main_rolls=[1] * 8)
    first = await client.post(f"/characters/{cid}/last-damage/options", json={"options": [EMPOWERED], "option_inputs": {}, "reroll": [0, 1, 2]})
    assert first.status_code == 200, first.text[:200]
    second = await client.post(f"/characters/{cid}/last-damage/options", json={"options": [EMPOWERED], "option_inputs": {}, "reroll": [3, 4, 5]})
    assert second.status_code == 409, second.text[:200]
    assert await _points(client, cid) == 4


@pytest.mark.caccia(id="CB-2613", fonte="2024 · Stregone · Stregoneria Draconica · Affinità Elementale · pag. 148", zona="regola:2024/sorcerer",
                    voce="regola",
                    copre=["carta:2024/classes/sorcerer.md#Affinità Elementale / Elemental Affinity (Stregoneria Draconica 6, pag. 148)",
                           "POST /characters/{char_id}/spells/{spell_id}/roll_damage"])
async def test_affinita_elementale_2024_somma_il_carisma_a_un_solo_tiro_di_danno_per_lancio(client):
    cid = await _make(client, "draconic", 6, charisma=18)
    await _affinity(client, cid, "fire")
    spell = await _spell(client, cid, "Raggio rovente", 2, attack_save="ATK", damage_dice="2d6", damage_type="fire", range_area="36 m")
    assert (await _cast(client, cid, spell, slot_level=2)).status_code == 200
    first = await client.post(f"/characters/{cid}/spells/{spell}/roll_damage",
                              json={"casting_level": 2, "main_rolls": [3, 3], "options": [AFFINITY]})
    assert first.status_code == 200 and first.json()["total"] == 3 + 3 + 4, first.text[:200]
    # stesso lancio, secondo tiro di danno (il secondo raggio): il Carisma non si somma di nuovo
    second = await client.post(f"/characters/{cid}/spells/{spell}/roll_damage",
                               json={"casting_level": 2, "main_rolls": [3, 3], "options": [AFFINITY]})
    assert second.status_code == 409 or second.json()["total"] == 3 + 3, second.text[:200]


@pytest.mark.caccia(id="CB-2614", fonte="2024 · Stregone · Impulso di Magia Selvaggia, tabella 45-48 · pag. 149", zona="regola:2024/sorcerer",
                    voce="regola",
                    copre=["carta:2024/classes/sorcerer.md#Impulso di Magia Selvaggia / Wild Magic Surge (Magia Selvaggia 3, pag. 149)",
                           "carta:2024/general.md#Invisible [Condition] (Invisibile) (pag. 370)",
                           "POST /characters/{char_id}/wild-magic/surge"])
@pytest.mark.xfail(strict=True, reason="CB-2614: difforme dal manuale, confermato")
async def test_impulso_45_48_rende_invisibile_lo_stregone(client):
    cid = await _make(client, "wild_magic", 3)
    r = await client.post(f"/characters/{cid}/wild-magic/surge", json={"die": 20, "percentile": [45]})
    assert r.status_code == 200 and r.json()["applied"]["label"] == "45-48", r.text[:200]
    assert (await _full(client, cid))["conditions"].get("invisible") is True


@pytest.mark.caccia(id="CB-2615", fonte="2024 · Stregone · Stregoneria Aberrante · Stregoneria Psionica · pag. 146; Glossario · Nascondersi · pag. 368",
                    zona="regola:2024/sorcerer", voce="interazione",
                    copre=["carta:2024/classes/sorcerer.md#Stregoneria Psionica / Psionic Sorcery (Stregoneria Aberrante 6, pag. 146)",
                           "carta:2024/general.md#Hide [Action] (Nascondersi) (pag. 368)",
                           "POST /characters/{char_id}/hide", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.xfail(strict=True, reason="CB-2615: difforme dal manuale, confermato")
async def test_stregoneria_psionica_a_punti_non_toglie_il_nascondiglio(client):
    # Lanciato coi punti l'incantesimo psionico non ha componente verbale: chi è nascosto resta Invisibile
    cid = await _make(client, "aberrant", 7)
    spell = (await _spells(client, cid))["hunger-of-hadar"]
    assert "V" in spell["components"]
    await _hidden(client, cid)
    r = await client.post(f"/characters/{cid}/spells/{spell['id']}/use", json={"ki": True, "choices": {"upcast_type": "cold"}})
    assert r.status_code == 200, r.text[:200]
    assert await _points(client, cid) == 7 - 3
    assert (await _full(client, cid))["conditions"].get("invisible") is True


@pytest.mark.caccia(id="CB-2616", fonte="2024 · Stregone · Stregoneria Aberrante · Incantesimi Psionici e Stregoneria Psionica · pag. 145-146",
                    zona="regola:2024/sorcerer", voce="limiti",
                    copre=["carta:2024/classes/sorcerer.md#Stregoneria Psionica / Psionic Sorcery (Stregoneria Aberrante 6, pag. 146)",
                           "carta:2024/classes/sorcerer.md#Incantesimi Psionici / Psionic Spells (Stregoneria Aberrante 3, pag. 145)",
                           "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.xfail(strict=True, reason="CB-2616: difforme dal manuale, confermato")
async def test_stregoneria_psionica_non_lancia_un_incantesimo_psionico_non_ancora_ottenuto(client):
    # Telecinesi entra negli Incantesimi Psionici al 9° livello: al 6° non è un incantesimo di quel privilegio
    cid = await _make(client, "aberrant", 6)
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Telecinesi", "level": 5, "casting_time": "1 azione",
                                                            "srd_index": "telekinesis"})
    assert r.status_code == 201, r.text[:200]
    r = await client.post(f"/characters/{cid}/spells/{r.json()['id']}/use", json={"ki": True})
    assert r.status_code == 409, r.text[:200]
    assert await _points(client, cid) == 6


@pytest.mark.caccia(id="CB-2617", fonte="2024 · Stregone · Incantesimo Raddoppiato · pag. 142; Incantesimi · Arrampicarsi come un Ragno, Risata Incontenibile di Tasha",
                    zona="regola:2024/sorcerer", voce="regola",
                    copre=["carta:2024/classes/sorcerer.md#Incantesimo Raddoppiato / Twinned Spell (Metamagia, pag. 142)",
                           "carta:2024/spells.md#Arrampicarsi come un Ragno", "carta:2024/spells.md#Risata Incontenibile di Tasha",
                           "GET /characters/{char_id}/roll-options"])
@pytest.mark.parametrize("srd_index,level", [("spider-climb", 2), ("tashas-hideous-laughter", 1)])
async def test_incantesimo_raddoppiato_vale_per_gli_incantesimi_con_un_bersaglio_in_piu_per_slot(client, srd_index, level):
    cid = await _caster24(client, 6, "twinned")
    spell = await _spell(client, cid, "Prova", level, srd_index=srd_index)
    assert TWINNED in await _roll_keys(client, cid, "cast", spell_id=spell)


@pytest.mark.caccia(id="CB-2618", fonte="2024 · Stregone · Stregoneria Meccanica · Ripristinare l'Equilibrio · pag. 146", zona="regola:2024/sorcerer",
                    voce="regola",
                    copre=["carta:2024/classes/sorcerer.md#Ripristinare l'Equilibrio / Restore Balance (Stregoneria Meccanica 3, pag. 146)",
                           "POST /characters/{char_id}/skills/{skill_name}/roll"])
async def test_ripristinare_l_equilibrio_non_si_spende_su_un_tiro_senza_vantaggio_ne_svantaggio(client):
    cid = await _make(client, "clockwork", 5, charisma=18)
    r = await client.post(f"/characters/{cid}/skills/arcana/roll", json={"mode": "normal", "dice": [7], "options": [RESTORE_OWN]})
    assert r.status_code in (200, 409, 422), r.text[:200]
    assert (await _ability(client, cid, "sorcerer.restore_balance"))["uses"] == 4
    assert (await _turn(client, cid))["reaction_used"] is False


# ---------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2619", fonte="2024 · Stregone · Fonte di Magia · pag. 140", zona="regola:2024/sorcerer", voce="limiti",
                    copre=["carta:2024/classes/sorcerer.md#Fonte di Magia / Font of Magic (Stregone 2, pag. 140)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.parametrize("slot,cost,min_level", [(1, 2, 2), (2, 3, 3), (3, 5, 5), (4, 6, 7), (5, 7, 9)])
async def test_creare_uno_slot_costa_i_punti_della_tabella_dal_livello_minimo(client, slot, cost, min_level):
    cid = await _sorcerer24(client, min_level)
    total = (await _slots(client, cid)).get(slot, (0, 0))[0]
    assert (await _use(client, cid, CREATE, params={"slot_level": str(slot)})).status_code == 200
    assert await _points(client, cid) == min_level - cost and (await _slots(client, cid))[slot][0] == total + 1
    if min_level > 2:
        low = await _sorcerer24(client, min_level - 1)
        assert (await _use(client, low, CREATE, params={"slot_level": str(slot)})).status_code == 422
        assert await _points(client, low) == min_level - 1


@pytest.mark.caccia(id="CB-2620", fonte="2024 · Stregone · Ripristino Stregonesco · pag. 141", zona="regola:2024/sorcerer", voce="limiti",
                    copre=["carta:2024/classes/sorcerer.md#Ripristino Stregonesco / Sorcerous Restoration (Stregone 5, pag. 141)",
                           "POST /characters/{char_id}/rest"])
async def test_ripristino_stregonesco_rende_fino_a_meta_del_livello_una_volta_fra_riposi_lunghi(client):
    cid = await _sorcerer24(client, 11)
    await _set_points(client, cid, 0)
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "sorcerous_restoration": 6})
    assert r.status_code == 422 and await _points(client, cid) == 0
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "sorcerous_restoration": 5})).status_code == 200
    assert await _points(client, cid) == 5 and (await _ability(client, cid, RESTORATION))["uses"] == 0
    await _rest(client, cid, "long")
    assert (await _ability(client, cid, RESTORATION))["uses"] == 1


@pytest.mark.caccia(id="CB-2621", fonte="2024 · Stregone · Metamagia · pag. 141", zona="regola:2024/sorcerer", voce="limiti",
                    copre=["carta:2024/classes/sorcerer.md#Metamagia / Metamagic (Stregone 2, pag. 141)", "POST /characters"])
@pytest.mark.parametrize("level,count", [(1, None), (2, 2), (9, 2), (10, 4), (16, 4), (17, 6), (20, 6)])
async def test_le_opzioni_di_metamagia_sono_2_poi_4_al_10_e_6_al_17(client, level, count):
    pending = _pending(await _full(client, await _sorcerer24(client, level)))
    assert (pending["count"] if pending else None) == count


@pytest.mark.caccia(id="CB-2622", fonte="2024 · Stregone · Incantesimo Intensificato · pag. 142; 2014 · Stregone · Incantesimo Intensificato · pag. 110",
                    zona="regola:2024/sorcerer", voce="edizioni",
                    copre=["carta:2024/classes/sorcerer.md#Incantesimo Intensificato / Heightened Spell (Metamagia, pag. 142)",
                           "carta:2014/classes/sorcerer.md#Incantesimo Intensificato / Heightened Spell (Stregone 3, pag. 110)",
                           "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_incantesimo_intensificato_costa_2_punti_nel_2024_e_3_nel_2014(client):
    new = await _caster24(client, 10, "heightened")
    old = await _caster14(client, 10, "heightened")
    for cid, use, cost in ((new, _cast, 2), (old, _use_spell14, 3)):
        spell = await _spell(client, cid, "Ragnatela", 2, attack_save="DEX")
        r = await use(client, cid, spell, HEIGHTENED, slot_level=2)
        assert r.status_code == 200, r.text[:200]
        assert await _points(client, cid) == 10 - cost


@pytest.mark.caccia(id="CB-2623", fonte="2024 · Stregone · Incantesimo Raddoppiato · pag. 142", zona="regola:2024/sorcerer", voce="regola",
                    copre=["carta:2024/classes/sorcerer.md#Incantesimo Raddoppiato / Twinned Spell (Metamagia, pag. 142)",
                           "GET /characters/{char_id}/roll-options"])
@pytest.mark.parametrize("srd_index,level", [("heroism", 1), ("freedom-of-movement", 4), ("gaseous-form", 3), ("charm-person", 1)])
async def test_incantesimo_raddoppiato_offerto_per_eroismo_liberta_di_movimento_e_forma_gassosa(client, srd_index, level):
    cid = await _caster24(client, 10, "twinned")
    spell = await _spell(client, cid, "Prova", level, srd_index=srd_index)
    assert TWINNED in await _roll_keys(client, cid, "cast", spell_id=spell)


@pytest.mark.caccia(id="CB-2624", fonte="2024 · Stregone · Stregoneria Aberrante · Adattamento Acquatico · pag. 146", zona="regola:2024/sorcerer",
                    voce="regola",
                    copre=["carta:2024/classes/sorcerer.md#Adattamento Acquatico / Aquatic Adaptation (Stregoneria Aberrante 14, pag. 146)",
                           "carta:2024/classes/sorcerer.md#Rivelazione nella Carne / Revelation in Flesh (Stregoneria Aberrante 14, pag. 146)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_adattamento_acquatico_da_un_nuoto_pari_al_doppio_della_velocita(client):
    cid = await _make(client, "aberrant", 14)
    assert (await _use(client, cid, "sorcerer.revelation_in_flesh", params={"swim": True})).status_code == 200
    computed = (await _full(client, cid))["computed"]
    assert computed["swim_speed"] == 2 * computed["speed"] and await _points(client, cid) == 13


@pytest.mark.caccia(id="CB-2625", fonte="2024 · Stregone · Fonte di Magia: convertire uno slot · pag. 140", zona="regola:2024/sorcerer",
                    voce="ripetizione",
                    copre=["carta:2024/classes/sorcerer.md#Fonte di Magia / Font of Magic (Stregone 2, pag. 140)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_due_conversioni_dell_unico_slot_di_4_livello_insieme_ne_spendono_uno(client):
    # Nel 2024 la conversione non costa un'azione: niente azione bonus a serializzare due invii
    cid = await _sorcerer24(client, 7)
    await _set_points(client, cid, 0)
    first, second = await asyncio.gather(*(_use(client, cid, CONVERT, params={"slot_level": "4"}) for _ in range(2)))
    codes = sorted((first.status_code, second.status_code))
    assert codes[0] == 200 and codes[1] >= 400, (first.text[:200], second.text[:200])
    assert await _points(client, cid) == 4 and (await _slots(client, cid))[4] == (1, 1)


# tabella di classe dello Stregone 2024: bonus di competenza e slot dal 1° al 9° livello
_TABLE_2024 = [
    (2, [2]), (2, [3]), (2, [4, 2]), (2, [4, 3]), (3, [4, 3, 2]), (3, [4, 3, 3]), (3, [4, 3, 3, 1]), (3, [4, 3, 3, 2]),
    (4, [4, 3, 3, 3, 1]), (4, [4, 3, 3, 3, 2]), (4, [4, 3, 3, 3, 2, 1]), (4, [4, 3, 3, 3, 2, 1]), (5, [4, 3, 3, 3, 2, 1, 1]),
    (5, [4, 3, 3, 3, 2, 1, 1]), (5, [4, 3, 3, 3, 2, 1, 1, 1]), (5, [4, 3, 3, 3, 2, 1, 1, 1]), (6, [4, 3, 3, 3, 2, 1, 1, 1, 1]),
    (6, [4, 3, 3, 3, 3, 1, 1, 1, 1]), (6, [4, 3, 3, 3, 3, 2, 1, 1, 1]), (6, [4, 3, 3, 3, 3, 2, 2, 1, 1]),
]


@pytest.mark.caccia(id="CB-2626", fonte="2024 · Stregone · Tabella di classe · pag. 139", zona="regola:2024/sorcerer", voce="regola",
                    copre=["carta:2024/classes/sorcerer.md#Incantesimi / Spellcasting (Stregone 1, pag. 139)"])
def test_la_progressione_del_frontend_ha_competenza_e_slot_della_tabella_2024_dello_stregone():
    rows = json.loads(PROGRESSION.read_text(encoding="utf-8"))["Stregone"]
    assert [(r["proficiency_bonus"], [n for n in r["spell_slots"] if n]) for r in rows] == _TABLE_2024
