"""Controlli della zona regola:2014/paladin."""
import json
from pathlib import Path

import pytest

from core.rules.catalog import features_for

GIURAMENTI = {"devotion": "Giuramento di Devozione", "ancients": "Giuramento degli Antichi", "vengeance": "Giuramento di Vendetta"}
PUNIZIONE = "paladin.divine_smite"


async def _paladino(client, livello, giuramento=None, edizione="2014", **punteggi) -> int:
    corpo = {"name": "Paladino", "rules_edition": edizione,
             "initial_class": {"class_name": "paladin", "level": livello, "subclass": GIURAMENTI.get(giuramento)}}
    r = await client.post("/characters", json=corpo)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for nome, valore in punteggi.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{nome}", json={"value": valore})
        assert r.status_code == 200, r.text
    return cid


async def _scheda(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def _aggiungi(client, cid, classe, livello, dado, sottoclasse=None) -> None:
    r = await client.post(f"/characters/{cid}/classes",
                          json={"class_name": classe, "level": livello, "hit_die": dado, "subclass": sottoclasse})
    assert r.status_code == 201, r.text


async def _slot(client, cid) -> dict[int, int]:
    return {s["level"]: s["total"] for s in (await _scheda(client, cid))["spell_slots"]}


async def _spada(client, cid) -> int:
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Spada", "item_type": "weapon", "item_metadata": {"damage_dice": "1d8", "weapon_type": "melee", "properties": []}})
    assert r.status_code == 201, r.text
    iid = max(i["id"] for i in r.json()["items"])
    r = await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": "main_hand"})
    assert r.status_code == 200, r.text
    return iid


async def _colpo(client, cid, arma) -> dict:
    r = await client.post(f"/characters/{cid}/items/{arma}/attack", json={"die": 15, "confirm_extra_attack": True, "defer_damage": True})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Difformità
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-1861", fonte="2014 · Paladino · Incantesimi, multiclasse con una sola classe incantatrice · pag. 97, 164",
                    zona="regola:2014/paladin", voce="interazione",
                    copre=["carta:2014/classes/paladin.md#Incantesimi / Spellcasting (Paladino 2, pag. 97)",
                           "carta:2014/classes/paladin.md#Multiclasse: Paladino / Multiclassing: Paladin (Regole opzionali, pag. 163)",
                           "carta:2014/general.md#Incantesimi / Spellcasting (multiclasse) (pag. 164)",
                           "POST /characters/{char_id}/classes", "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello_paladino,altra,livello_altra,dado,sottoclasse", [
    (1, "ranger", 5, 10, None),  # il paladino di 1° livello non ha ancora Incantesimi: vale la tabella del ranger 5
    (1, "fighter", 7, 10, "Cavaliere Mistico"),  # idem: tabella del Cavaliere Mistico 7
    (5, "ranger", 1, 10, None),  # il ranger di 1° livello non ha Incantesimi: vale la tabella del paladino 5
])
async def test_slot_con_una_sola_classe_incantatrice_seguono_la_sua_tabella(
        client, livello_paladino, altra, livello_altra, dado, sottoclasse):
    cid = await _paladino(client, livello_paladino)
    await _aggiungi(client, cid, altra, livello_altra, dado, sottoclasse)
    assert await _slot(client, cid) == {1: 4, 2: 2}


@pytest.mark.caccia(id="CB-1862", fonte="2014 · Paladino · Incantesimi dal 2° livello (CD e attacco degli incantesimi) · pag. 97",
                    zona="regola:2014/paladin", voce="limiti",
                    copre=["carta:2014/classes/paladin.md#Incantesimi / Spellcasting (Paladino 2, pag. 97)", "GET /characters/{char_id}"])
async def test_paladino_di_primo_livello_non_ha_cd_degli_incantesimi(client):
    primo = (await _scheda(client, await _paladino(client, 1)))["spellcasting"]["casters"]
    secondo = (await _scheda(client, await _paladino(client, 2)))["spellcasting"]["casters"]
    assert [c["class_name"] for c in secondo] == ["paladin"]
    assert primo == []


@pytest.mark.caccia(id="CB-1863", fonte="2014 · Paladino · Incantesimi preparati solo di livelli per cui si hanno slot · pag. 97",
                    zona="regola:2014/paladin", voce="regola",
                    copre=["carta:2014/classes/paladin.md#Incantesimi / Spellcasting (Paladino 2, pag. 97)",
                           "POST /characters/{char_id}/spells", "GET /characters/{char_id}/spells"])
async def test_non_si_prepara_un_incantesimo_di_livello_senza_slot(client):
    cid = await _paladino(client, 2, charisma=16)  # slot solo di 1° livello, tetto dei preparati 3 + 1
    classe = (await _scheda(client, cid))["classes"][0]["id"]
    await client.post(f"/characters/{cid}/spells", json={"name": "Aiuto", "level": 2, "class_id": classe, "is_prepared": True})
    incantesimi = (await client.get(f"/characters/{cid}/spells")).json()
    assert not [s["name"] for s in incantesimi if s["level"] == 2 and s["is_prepared"]]


# ---------------------------------------------------------------------------
# Regole che restano giuste
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-1864", fonte="2014 · Paladino · livelli dei privilegi di classe e di giuramento · pag. 97-101",
                    zona="regola:2014/paladin", voce="regola",
                    copre=["carta:2014/classes/paladin.md#Percezione del Divino / Divine Sense (Paladino 1, pag. 97)",
                           "carta:2014/classes/paladin.md#Imposizione delle Mani / Lay on Hands (Paladino 1, pag. 97)",
                           "carta:2014/classes/paladin.md#Punizione Divina / Divine Smite (Paladino 2, pag. 98)",
                           "carta:2014/classes/paladin.md#Salute Divina / Divine Health (Paladino 3, pag. 98)",
                           "carta:2014/classes/paladin.md#Incanalare Divinità / Channel Divinity (Giuramento Sacro, Paladino 3, pag. 98)",
                           "carta:2014/classes/paladin.md#Attacco Extra / Extra Attack (Paladino 5, pag. 98)",
                           "carta:2014/classes/paladin.md#Aura di Protezione / Aura of Protection (Paladino 6, pag. 98)",
                           "carta:2014/classes/paladin.md#Aura di Coraggio / Aura of Courage (Paladino 10, pag. 98)",
                           "carta:2014/classes/paladin.md#Punizione Divina Migliorata / Improved Divine Smite (Paladino 11, pag. 98)",
                           "carta:2014/classes/paladin.md#Tocco Purificatore / Cleansing Touch (Paladino 14, pag. 98)",
                           "carta:2014/classes/paladin.md#Aure Migliorate / Aura Improvements (Paladino 18, pag. 98)",
                           "carta:2014/classes/paladin.md#Aura di Devozione / Aura of Devotion (Giuramento di Devozione, Paladino 7, pag. 99)",
                           "carta:2014/classes/paladin.md#Purezza di Spirito / Purity of Spirit (Giuramento di Devozione, Paladino 15, pag. 99)",
                           "carta:2014/classes/paladin.md#Nube Sacra / Holy Nimbus (Giuramento di Devozione, Paladino 20, pag. 99)",
                           "carta:2014/classes/paladin.md#Aura di Interdizione / Aura of Warding (Giuramento degli Antichi, Paladino 7, pag. 100)",
                           "carta:2014/classes/paladin.md#Sentinella Imperitura / Undying Sentinel (Giuramento degli Antichi, Paladino 15, pag. 100)",
                           "carta:2014/classes/paladin.md#Campione degli Antichi / Elder Champion (Giuramento degli Antichi, Paladino 20, pag. 100)",
                           "carta:2014/classes/paladin.md#Vendicatore Implacabile / Relentless Avenger (Giuramento di Vendetta, Paladino 7, pag. 101)",
                           "carta:2014/classes/paladin.md#Anima di Vendetta / Soul of Vengeance (Giuramento di Vendetta, Paladino 15, pag. 101)",
                           "carta:2014/classes/paladin.md#Angelo Vendicatore / Avenging Angel (Giuramento di Vendetta, Paladino 20, pag. 101)"])
def test_ogni_privilegio_arriva_al_livello_della_carta():
    attesi = {
        "divine_sense": 1, "lay_on_hands": 1, "fighting_style": 2, "spellcasting": 2, "divine_smite": 2, "divine_health": 3,
        "sacred_oath": 3, "channel_divinity": 3, "ability_score_improvement": 4, "extra_attack": 5, "aura_of_protection": 6,
        "aura_of_courage": 10, "improved_divine_smite": 11, "cleansing_touch": 14, "aura_improvements": 18,
        "sacred_weapon": 3, "turn_the_unholy": 3, "aura_of_devotion": 7, "purity_of_spirit": 15, "holy_nimbus": 20,
        "natures_wrath": 3, "turn_the_faithless": 3, "aura_of_warding": 7, "undying_sentinel": 15, "elder_champion": 20,
        "abjure_enemy": 3, "vow_of_enmity": 3, "relentless_avenger": 7, "soul_of_vengeance": 15, "avenging_angel": 20,
    }
    livelli = {f.key.removeprefix("paladin."): f.level for f in features_for("2014", "paladin")}
    assert {k: livelli.get(k) for k in attesi} == attesi


@pytest.mark.caccia(id="CB-1865", fonte="2014 · Paladino · ricarica di usi e riserve · pag. 97-101",
                    zona="regola:2014/paladin", voce="regola",
                    copre=["carta:2014/classes/paladin.md#Percezione del Divino / Divine Sense (Paladino 1, pag. 97)",
                           "carta:2014/classes/paladin.md#Imposizione delle Mani / Lay on Hands (Paladino 1, pag. 97)",
                           "carta:2014/classes/paladin.md#Incanalare Divinità / Channel Divinity (Giuramento Sacro, Paladino 3, pag. 98)",
                           "carta:2014/classes/paladin.md#Tocco Purificatore / Cleansing Touch (Paladino 14, pag. 98)",
                           "carta:2014/classes/paladin.md#Nube Sacra / Holy Nimbus (Giuramento di Devozione, Paladino 20, pag. 99)",
                           "carta:2014/classes/paladin.md#Sentinella Imperitura / Undying Sentinel (Giuramento degli Antichi, Paladino 15, pag. 100)",
                           "carta:2014/classes/paladin.md#Campione degli Antichi / Elder Champion (Giuramento degli Antichi, Paladino 20, pag. 100)",
                           "carta:2014/classes/paladin.md#Angelo Vendicatore / Avenging Angel (Giuramento di Vendetta, Paladino 20, pag. 101)"])
def test_ogni_uso_torna_col_riposo_della_carta():
    attesi = {"divine_sense": "long_rest", "lay_on_hands": "long_rest", "channel_divinity": "short_rest",
              "cleansing_touch": "long_rest", "holy_nimbus": "long_rest", "undying_sentinel": "long_rest",
              "elder_champion": "long_rest", "avenging_angel": "long_rest"}
    ricariche = {f.key.removeprefix("paladin."): f.restoration for f in features_for("2014", "paladin")}
    assert {k: ricariche.get(k) for k in attesi} == attesi


@pytest.mark.caccia(id="CB-1866", fonte="2014 · Paladino · tabella di classe (bonus di competenza e slot) · pag. 97",
                    zona="regola:2014/paladin", voce="regola",
                    copre=["carta:2014/classes/paladin.md#Incantesimi / Spellcasting (Paladino 2, pag. 97)"])
def test_la_progressione_del_frontend_segue_la_tabella_di_classe():
    tabella = [  # (competenza, slot dal 1° al 5°) per livello, dalla tabella della carta
        (2, 0, 0, 0, 0, 0), (2, 2, 0, 0, 0, 0), (2, 3, 0, 0, 0, 0), (2, 3, 0, 0, 0, 0), (3, 4, 2, 0, 0, 0),
        (3, 4, 2, 0, 0, 0), (3, 4, 3, 0, 0, 0), (3, 4, 3, 0, 0, 0), (4, 4, 3, 2, 0, 0), (4, 4, 3, 2, 0, 0),
        (4, 4, 3, 3, 0, 0), (4, 4, 3, 3, 0, 0), (5, 4, 3, 3, 1, 0), (5, 4, 3, 3, 1, 0), (5, 4, 3, 3, 2, 0),
        (5, 4, 3, 3, 2, 0), (6, 4, 3, 3, 3, 1), (6, 4, 3, 3, 3, 1), (6, 4, 3, 3, 3, 2), (6, 4, 3, 3, 3, 2),
    ]
    dati = json.loads(Path("webapp/src/data/class-progression.json").read_text(encoding="utf-8"))["Paladino"]
    letto = [(r["proficiency_bonus"], *r["spell_slots"][:5]) for r in dati]
    assert letto == tabella
    assert all(not any(r["spell_slots"][5:]) for r in dati)


@pytest.mark.caccia(id="CB-1867", fonte="2014 · Paladino · Imposizione delle Mani, riserva 5 x livello da paladino · pag. 97",
                    zona="regola:2014/paladin", voce="interazione",
                    copre=["carta:2014/classes/paladin.md#Imposizione delle Mani / Lay on Hands (Paladino 1, pag. 97)",
                           "POST /characters/{char_id}/classes"])
async def test_la_riserva_di_imposizione_conta_solo_i_livelli_da_paladino(client):
    cid = await _paladino(client, 3)
    await _aggiungi(client, cid, "fighter", 2, 10)
    riga = next(a for a in (await _scheda(client, cid))["abilities"] if a["feature_key"] == "paladin.lay_on_hands")
    assert (riga["max_uses"], riga["restoration_type"]) == (15, "long_rest")


@pytest.mark.caccia(id="CB-1868", fonte="2014 · Paladino · slot multiclasse con metà dei livelli per difetto · pag. 97 (2024 per eccesso, pag. 109)",
                    zona="regola:2014/paladin", voce="edizioni",
                    copre=["carta:2014/classes/paladin.md#Incantesimi / Spellcasting (Paladino 2, pag. 97)",
                           "carta:2024/classes/paladin.md#Incantesimi / Spellcasting (Paladino 1, pag. 109)",
                           "POST /characters/{char_id}/classes"])
async def test_meta_dei_livelli_da_paladino_per_difetto_nel_2014_e_per_eccesso_nel_2024(client):
    vecchio = await _paladino(client, 3)
    nuovo = await _paladino(client, 3, edizione="2024")
    for cid in (vecchio, nuovo):
        await _aggiungi(client, cid, "wizard", 1, 6)
    assert await _slot(client, vecchio) == {1: 3}  # 1 + 1 = livello da incantatore 2
    assert await _slot(client, nuovo) == {1: 4, 2: 2}  # 2 + 1 = livello da incantatore 3


@pytest.mark.caccia(id="CB-1869", fonte="2014 · Paladino · Punizione Divina, uno slot per colpo · pag. 98",
                    zona="regola:2014/paladin", voce="ripetizione",
                    copre=["carta:2014/classes/paladin.md#Punizione Divina / Divine Smite (Paladino 2, pag. 98)",
                           "POST /characters/{char_id}/attack/{attack_id}/damage"])
async def test_punizione_mandata_due_volte_sullo_stesso_colpo_spende_un_solo_slot(client):
    cid = await _paladino(client, 5)
    colpo = await _colpo(client, cid, await _spada(client, cid))
    corpo = {"options": [PUNIZIONE], "option_inputs": {PUNIZIONE: {"slot_level": 1}}}
    primo = await client.post(f"/characters/{cid}/attack/{colpo['attack_id']}/damage", json=corpo)
    secondo = await client.post(f"/characters/{cid}/attack/{colpo['attack_id']}/damage", json=corpo)
    assert primo.status_code == 200 and secondo.status_code >= 400
    assert {s["level"]: s["used"] for s in (await _scheda(client, cid))["spell_slots"]} == {1: 1, 2: 0}


@pytest.mark.caccia(id="CB-1870", fonte="2014 · Paladino · Punizione Divina senza azione · pag. 98",
                    zona="regola:2014/paladin", voce="regola",
                    copre=["carta:2014/classes/paladin.md#Punizione Divina / Divine Smite (Paladino 2, pag. 98)",
                           "GET /characters/{character_id}/turn-state"])
async def test_punizione_del_2014_non_spende_l_azione_bonus(client):
    cid = await _paladino(client, 5)
    colpo = await _colpo(client, cid, await _spada(client, cid))
    r = await client.post(f"/characters/{cid}/attack/{colpo['attack_id']}/damage",
                          json={"options": [PUNIZIONE], "option_inputs": {PUNIZIONE: {"slot_level": 2}}})
    assert r.status_code == 200, r.text
    turno = (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]
    assert (turno["bonus_used"], turno["reaction_used"]) == (False, False)
    assert len(r.json()["option_result"]["extra_rolls"]) == 3  # 3d8 con uno slot di 2° livello


@pytest.mark.caccia(id="CB-1871", fonte="2014 · Paladino · Percezione del Divino, 1 + Carisma usi senza minimo · pag. 97",
                    zona="regola:2014/paladin", voce="limiti",
                    copre=["carta:2014/classes/paladin.md#Percezione del Divino / Divine Sense (Paladino 1, pag. 97)",
                           "GET /characters/{char_id}"])
@pytest.mark.parametrize("carisma,usi", [(9, None), (11, 1), (12, 2)])
async def test_percezione_del_divino_ha_uno_piu_carisma_usi_anche_zero(client, carisma, usi):
    cid = await _paladino(client, 1, charisma=carisma)
    riga = next((a for a in (await _scheda(client, cid))["abilities"] if a["feature_key"] == "paladin.divine_sense"), None)
    assert (riga["max_uses"] if riga else None) == usi
