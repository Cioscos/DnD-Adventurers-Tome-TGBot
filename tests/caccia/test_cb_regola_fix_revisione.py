"""Controlli della revisione indipendente dei gruppi lancio-core, dati-incantesimi-fe e catalogo-incantesimi."""
import json
from pathlib import Path

import pytest

from sqlalchemy import select

from core.db.models import Character, SpellSlot
from core.rules.catalog.granted_spells import granted_spell
from tests.caccia.test_cb_regola_fix_lancio_core import _pg
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
from tests.integration.rules.test_spell_effects_defenses import _cast, _sheet, _table

SRD = Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "srd"


def _voce(edizione: str, indice: str) -> dict:
    file = "spells.json" if edizione == "2014" else "spells-2024.json"
    return next(s for s in json.loads((SRD / file).read_text(encoding="utf-8"))["items"] if s["index"] == indice)


def _ha(scheda: dict, chiave: str) -> bool:
    return any(s["key"] == chiave for s in scheda["active_states"] or [])


@pytest.mark.caccia(id="CB-4761", fonte="2014 · Incantesimi · Previsione · pag. 264; 2024 · Incantesimi · Preveggenza · pag. 276",
                    zona="regola:2014/incantesimi-M-R", voce="ripetizione",
                    copre=["carta:2014/spells.md#Previsione", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_previsione_rilanciata_su_un_png_finisce_sul_bersaglio_di_prima(client, test_session_factory, edizione):
    eroe, mago, previsione = await _table(client, test_session_factory, "Previsione", "foresight", 9, hero_edition=edizione, caster_edition=edizione)
    await _cast(client, mago, previsione, [eroe], level=9)
    assert _ha(await _sheet(client, eroe), "spell:foresight")
    async with test_session_factory() as s:  # un altro slot di 9° senza le 8 ore di un riposo, che la farebbero finire da sé
        for slot in (await s.execute(select(SpellSlot).where(SpellSlot.character_id == mago))).scalars():
            slot.used = 0
        await s.commit()
    as_user(GM_ID)
    r = await client.post(f"/characters/{mago}/spells/{previsione}/use", json={"slot_level": 9, "targets": [], "confirm": ["one_slot_per_turn"]})
    assert r.status_code == 200, r.text
    # «Termina se lanciato di nuovo»: anche se il nuovo bersaglio non ha una scheda
    assert not _ha(await _sheet(client, eroe), "spell:foresight")
    assert not _ha(await _sheet(client, mago, GM_ID), "spell_cast:foresight")


@pytest.mark.caccia(id="CB-4762", fonte="2014 · Incantesimi · Santuario · pag. 272", zona="regola:2014/incantesimi-S-Z", voce="regola",
                    copre=["carta:2014/spells.md#Santuario", "POST /characters/{char_id}/items/{item_id}/attack"])
async def test_santuario_2014_finisce_quando_il_protetto_attacca(client, test_session_factory):
    eroe, chierico, santuario = await _table(client, test_session_factory, "Santuario", "sanctuary", 1, hero_edition="2014", caster_edition="2014")
    await _cast(client, chierico, santuario, [eroe], level=1)
    assert _ha(await _sheet(client, eroe), "spell:sanctuary")
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{eroe}/items", json={"name": "Spada", "item_type": "weapon", "item_metadata": {
        "damage_dice": "1d8", "damage_type": "slashing", "weapon_type": "melee"}})
    arma = max(i["id"] for i in r.json()["items"])
    r = await client.post(f"/characters/{eroe}/items/{arma}/attack", json={})
    assert r.status_code == 200, r.text
    # «Termina se la creatura protetta attacca o lancia un incantesimo su un nemico»
    assert not _ha(await _sheet(client, eroe), "spell:sanctuary")


@pytest.mark.caccia(id="CB-4763", fonte="2014 · Incantesimi · Rigenerazione · pag. 270", zona="regola:2014/incantesimi-M-R", voce="regola",
                    copre=["carta:2014/spells.md#Rigenerazione", "POST /characters/{char_id}/items/{item_id}/cast",
                           "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("come", ["oggetto", "riga_senza_indice", "riga_del_catalogo"])
async def test_rigenerazione_senza_tiro_di_cura_da_comunque_i_4d8_piu_15(client, dadi, come):
    cid, classe = await _pg(client, "cleric", 13)
    for op, valore in (("set_max", 100), ("set_current", 10)):
        assert (await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": valore})).status_code == 200
    if come != "riga_del_catalogo":
        dadi(5, 5, 5, 5)
    if come == "oggetto":
        r = await client.post(f"/characters/{cid}/items", json={"name": "Verga", "item_type": "generic", "item_metadata": {
            "charges": {"max": 5, "current": 5}, "granted_spells": [{"name": "Rigenerazione", "srd_index": "regenerate", "level": 7, "charges_cost": 1}]}})
        assert r.status_code == 201, r.text
        r = await client.post(f"/characters/{cid}/items/{r.json()['items'][-1]['id']}/cast", json={"spell_index": 0})
    else:
        r = await client.post(f"/characters/{cid}/spells", json={"name": "Rigenerazione", "level": 7, "class_id": classe,
                                                                **({"srd_index": "regenerate"} if come == "riga_del_catalogo" else {})})
        assert r.status_code == 201, r.text
        r = await client.post(f"/characters/{cid}/spells/{r.json()['id']}/use", json={"slot_level": 7})
    assert r.status_code == 200, r.text
    # 4d8 + 15 subito; la riga del catalogo li tira dalla «Cura» dell'incantesimo, non anche dal lancio (CB-3363)
    attesi = 10 if come == "riga_del_catalogo" else 45
    assert (await client.get(f"/characters/{cid}")).json()["current_hit_points"] == attesi


@pytest.mark.caccia(id="CB-4764", fonte="2024 · Incantesimi · Ristorare Inferiore · pag. 291; Fame di Hadar · pag. 286; Presenza Regale di Yolande · pag. 343; "
                                        "Evoca Elementale · pag. 254; Muro di Pietra · pag. 339; Fonte di luce lunare · pag. 277; Parola del Potere · pag. 306; "
                                        "2014 · Muro di Pietra · pag. 254; Rampicante Afferrante · pag. 267",
                    zona="regola:2024/incantesimi-G-L", voce="edizioni",
                    copre=["carta:2024/spells.md#Ristorare Inferiore", "carta:2024/spells.md#Fame di Hadar", "carta:2014/spells.md#Muro di Pietra",
                           "GET /characters/{char_id}/spells"])
@pytest.mark.parametrize("edizione, chiave, campo, valore", [
    ("2024", "lesser-restoration", "casting_time", "1 azione bonus"), ("2014", "lesser-restoration", "casting_time", "1 azione"),
    ("2024", "hunger-of-hadar", "damage_dice", "2d6"), ("2024", "hunger-of-hadar", "higher_levels_dice", "1d6"),
    ("2024", "hunger-of-hadar", "damage_type", "cold"), ("2024", "hunger-of-hadar", "attack_save", "SAVE"),
    ("2024", "yolandes-regal-presence", "damage_dice", "4d6"), ("2024", "yolandes-regal-presence", "damage_type", "psychic"),
    ("2024", "conjure-elemental", "attack_save", "SAVE"), ("2024", "fount-of-moonlight", "attack_save", "SAVE"),
    ("2014", "wall-of-stone", "attack_save", "SAVE"), ("2024", "wall-of-stone", "attack_save", "SAVE"),
    ("2014", "grasping-vine", "attack_save", "SAVE"),
    ("2024", "power-word-heal", "components", "V"), ("2024", "power-word-kill", "components", "V"),
    ("2024", "power-word-kill", "damage_dice", "12d12"), ("2024", "power-word-kill", "damage_type", "psychic"),
])
def test_gli_incantesimi_concessi_hanno_i_dati_della_carta(edizione, chiave, campo, valore):
    assert getattr(granted_spell(chiave, edizione), campo) == valore


@pytest.mark.caccia(id="CB-4765", fonte="2014 · Incantesimi · Guarigione di Massa · pag. 240; Antipatia/Simpatia · pag. 214; Simbolo · pag. 277; "
                                        "Aura Sacra · pag. 216; Danza Irresistibile di Otto · pag. 228; Gabbia di Forza · pag. 238",
                    zona="regola:2014/incantesimi-G-L", voce="regola",
                    copre=["carta:2014/spells.md#Guarigione di Massa", "carta:2014/spells.md#Antipatia/Simpatia"])
@pytest.mark.parametrize("indice, campi", [
    ("mass-heal", {"school": "evocation"}),  # «Invocazione»: è evocation in inglese (come Cura Ferite di Massa, CB-4035)
    ("antipathy-sympathy", {"attack_type": "SAVE", "save_ability": "wis"}), ("symbol", {"attack_type": "SAVE", "save_ability": "con"}),
    ("holy-aura", {"attack_type": "SAVE", "save_ability": "con"}), ("irresistible-dance", {"attack_type": "SAVE", "save_ability": "wis"}),
    ("forcecage", {"attack_type": "SAVE", "save_ability": "cha"}),
])
def test_le_voci_2014_del_catalogo_hanno_scuola_e_ts_della_carta(indice, campi):
    voce = _voce("2014", indice)
    assert {k: voce[k] for k in campi} == campi


@pytest.mark.caccia(id="CB-4766", fonte="2024 · Incantesimi · Evoca Elementale · pag. 254; 2014 · Incantesimi · Fatale · pag. 235", zona="regola:2024/incantesimi-D-F",
                    voce="regola", copre=["carta:2024/spells.md#Evoca Elementale", "carta:2014/spells.md#Fatale"])
def test_evoca_elementale_2024_e_fatale_2014_hanno_i_dadi_della_carta():
    for voce in (_voce("2024", "conjure-elemental"), vars(granted_spell("conjure-elemental", "2024"))):  # 8d8 del tipo scelto, +2d8 per slot oltre il 5°
        assert (voce["damage_dice"], voce["damage_type"], voce["higher_levels_dice"]) == ("8d8", None, "2d8")
    assert granted_spell("conjure-elemental", "2014").damage_dice is None  # nel 2014 evoca una creatura, nessun danno
    fatale = _voce("2014", "weird")
    assert (fatale["damage_dice"], fatale["damage_type"], fatale["higher_levels_dice"]) == ("4d10", "psychic", None)


@pytest.mark.caccia(id="CB-4767", fonte="2014 · Chierico · Incantesimi · pag. 58; Paladino · Incantesimi · pag. 97 (dal 2° livello); Multiclasse · pag. 164",
                    zona="regola:2014/cleric", voce="interazione",
                    copre=["carta:2014/spells.md#Cura Ferite", "POST /characters/{char_id}/spells"])
async def test_un_paladino_2014_di_primo_livello_non_toglie_al_chierico_il_livello_massimo_dei_preparati(client):
    cid, _ = await _pg(client, "cleric", 3, wisdom=16, charisma=16)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "paladin", "level": 1, "hit_die": 10})
    assert r.status_code == 201, r.text
    # l'unica classe che incanta è il chierico (slot fino al 2°): un incantesimo non assegnato è suo
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Rianimare Morti", "level": 5, "is_prepared": True})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "spell_above_slots", r.text
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Aiuto", "level": 2, "is_prepared": True})
    assert r.status_code == 201, r.text
