"""Controlli scritti dal correttore del gruppo classi-2024-a per i dubbi risolti come difetti."""
import pytest

from tests.integration.rules.test_2014_barbarian import _ability, _keys, _weapon
from tests.integration.rules.test_2024_barbarian import _barbarian, _new_turn, _rage
from tests.integration.rules.test_2024_barbarian_paths import _use
from tests.integration.rules.test_2024_barbarian_strike import _damage, _deferred
from tests.integration.rules.test_2024_bard import _bard24
from tests.integration.rules.test_2014_monk_ki import _ki, _states
from tests.integration.rules.test_2014_bard import _use as _use_feature
from tests.integration.rules.test_2014_fighter_styles import _item
from tests.integration.rules.test_2014_paladin_combat import _attack, _listed
from tests.integration.rules.test_2024_paladin import _paladin24
from tests.integration.rules.test_2024_paladin_oaths import _oath, _sword
from tests.integration.rules.test_2024_monk import _monk24
from tests.integration.rules.test_2014_paladin import _rest
from tests.integration.rules.test_2024_ranger import _spell_id
from tests.integration.rules.test_2024_ranger_subclasses import _sub as _ranger_sub
from tests.integration.rules.test_2014_bard import _roll_keys

RAGE = "barbarian.rage"
RECKLESS = "barbarian.reckless_attack"
FRENZY = "barbarian.frenzy"
TREE = "Cammino dell'Albero del Mondo"
BERSERKER = "Cammino del Berserker"


@pytest.mark.caccia(id="CB-4471", fonte="2024 · Barbaro, Cammino dell'Albero del Mondo · Viaggio lungo l'Albero · pag. 56",
                    zona="regola:2024/barbarian", voce="regola",
                    copre=["carta:2024/classes/barbarian.md#Viaggio lungo l'Albero / Travel along the Tree (Cammino dell'Albero del Mondo 14, pag. 56)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_viaggio_lungo_l_albero_a_150_piedi_gia_all_ingresso_in_ira(client):
    cid = await _barbarian(client, 15, TREE)  # dal 15° l'Ira non va prolungata: i turni passano senza attacchi
    assert "far" in {t["key"] for t in (await _ability(client, cid, RAGE))["use_toggles"]}
    entrata = await _rage(client, cid, far=True)
    assert entrata.status_code == 200, entrata.text
    assert "45 m" in entrata.json()["message"]["it"] and "150 ft" in entrata.json()["message"]["en"]
    await _new_turn(client, cid)
    r = await _use(client, cid, "travel_along_the_tree", params={"far": True})
    assert r.status_code == 409, "la versione a 150 piedi, una volta per Ira, è già stata usata entrando in Ira"


@pytest.mark.caccia(id="CB-4472", fonte="2024 · Barbaro, Cammino del Berserker · Frenesia · pag. 54; Barbaro · Attacco Irruento · pag. 52",
                    zona="regola:2024/barbarian", voce="interazione",
                    copre=["carta:2024/classes/barbarian.md#Frenesia / Frenzy (Cammino del Berserker 3, pag. 54)",
                           "carta:2024/classes/barbarian.md#Attacco Irruento / Reckless Attack (Barbaro 2, pag. 52)",
                           "POST /characters/{char_id}/items/{item_id}/attack", "POST /characters/{char_id}/attack/{attack_id}/damage"])
async def test_frenesia_solo_se_l_attacco_irruento_e_dichiarato_in_ira(client):
    cid = await _barbarian(client, 5, BERSERKER, strength=16)
    ascia = await _weapon(client, cid)
    await _new_turn(client, cid)
    await _deferred(client, cid, ascia, options=[RECKLESS], dice=[1, 1])  # Irruento senza Ira: mancato
    assert (await _rage(client, cid)).status_code == 200
    colpo = await _deferred(client, cid, ascia, dice=[15, 15])  # Attacco Extra, ora in Ira
    assert FRENZY not in await _keys(client, cid, "attack", item_id=ascia)
    r = await _damage(client, cid, colpo, [FRENZY])
    assert r.status_code == 409, "l'Attacco Irruento è stato usato prima che l'Ira fosse attiva: niente Frenesia"


@pytest.mark.caccia(id="CB-4473", fonte="2024 · Bardo · Segreti Magici · pag. 61", zona="regola:2024/bard", voce="regola",
                    copre=["carta:2024/classes/bard.md#Segreti Magici / Magical Secrets (Bardo 10, pag. 61)",
                           "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello", [10, 20])
async def test_segreti_magici_2024_e_un_permesso_non_una_scelta_da_fare(client, livello):
    cid = await _bard24(client, livello)
    full = (await client.get(f"/characters/{cid}")).json()
    assert "bard.magical_secrets" in {a["feature_key"] for a in full["abilities"]}
    assert not [c for c in full["pending_choices"] if c.get("group") == "magical_secrets"],         "i nuovi preparati possono venire dalle quattro liste: nessuna scelta obbligatoria"


@pytest.mark.caccia(id="CB-4474", fonte="2024 · Monaco · Difesa Superiore · pag. 103", zona="regola:2024/monk", voce="ripetizione",
                    copre=["carta:2024/classes/monk.md#Difesa Superiore / Superior Defense (Monaco 18, pag. 103)",
                           "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_difesa_superiore_una_volta_per_turno_e_si_rinnova_a_un_turno_successivo(client):
    cid = await _monk24(client, 18)
    assert (await _use_feature(client, cid, "monk.superior_defense")).status_code == 200
    assert (await _use_feature(client, cid, "monk.superior_defense")).status_code == 409, "un turno ha un solo inizio"
    await _new_turn(client, cid)
    r = await _use_feature(client, cid, "monk.superior_defense")
    assert r.status_code == 200, "a inizio di un turno successivo si può spendere di nuovo e il minuto riparte"
    assert await _ki(client, cid) == 18 - 6
    assert (await _states(client, cid))["superior_defense"]["rounds_left"] == 10


@pytest.mark.caccia(id="CB-4475", fonte="2024 · Paladino · Punizione del Paladino · pag. 110; Assalti Radianti · pag. 111; Equipaggiamento · Lancio · pag. 214",
                    zona="regola:2024/paladin", voce="regola",
                    copre=["carta:2024/classes/paladin.md#Punizione del Paladino / Paladin's Smite (Paladino 2, pag. 110)",
                           "carta:2024/classes/paladin.md#Assalti Radianti / Radiant Strikes (Paladino 11, pag. 111)",
                           "GET /characters/{char_id}/roll-options", "POST /characters/{char_id}/items/{item_id}/attack"])
async def test_punizione_e_assalti_radianti_valgono_con_un_arma_da_mischia_lanciata(client):
    cid = await _paladin24(client, 11)
    accetta = await _item(client, cid, "Accetta", damage_dice="1d6", weapon_type="melee", properties=["thrown"])
    dardo = await _item(client, cid, "Dardo", damage_dice="1d4", weapon_type="ranged", properties=["thrown"])
    lanciata = {o["key"] for o in await _listed(client, cid, accetta, attack_mode="thrown", grip="one")}
    assert {"paladin.divine_smite", "paladin.divine_smite_free"} <= lanciata, "lanciata, l'accetta resta un'arma da mischia"
    assert not {"paladin.divine_smite", "paladin.divine_smite_free"} & {
        o["key"] for o in await _listed(client, cid, dardo, attack_mode="thrown", grip="one")}, "il dardo è un'arma a distanza"
    colpo = await _attack(client, cid, accetta, attack_mode="thrown")
    assert colpo.status_code == 200, colpo.text
    assert "paladin.radiant_strikes" in (colpo.json().get("option_result") or {}).get("keys", [])


@pytest.mark.caccia(id="CB-4476", fonte="2024 · Ranger, Viandante Fatato · Rinforzi Fatati · pag. 125",
                    zona="regola:2024/ranger", voce="regola",
                    copre=["carta:2024/classes/ranger.md#Rinforzi Fatati / Fey Reinforcements (Viandante Fatato 11, pag. 125)",
                           "GET /characters/{char_id}/roll-options", "POST /characters/{char_id}/spells/{spell_id}/use"])
async def test_rinforzi_fatati_rinuncia_alla_concentrazione_anche_lanciando_con_uno_slot(client):
    cid = await _ranger_sub(client, 11, "fey_wanderer")
    evoca = await _spell_id(client, cid, "summon-fey")
    chiave = "ranger.fey_reinforcements_no_concentration"
    assert chiave in await _roll_keys(client, cid, "cast", spell_id=evoca), "«prima di lanciarlo»: ogni lancio di Summon Fey"
    r = await client.post(f"/characters/{cid}/spells/{evoca}/use", json={"slot_level": 3, "options": [chiave]})
    assert r.status_code == 200, r.text
    assert not (await client.get(f"/characters/{cid}")).json().get("concentrating_spell_id"), "lanciato con lo slot, dura 1 minuto senza Concentrazione"


@pytest.mark.caccia(id="CB-4477", fonte="2024 · Ranger · Nemico Prescelto · pag. 119; Viandante Fatato · Rinforzi Fatati · pag. 125",
                    zona="regola:2024/ranger", voce="annullamento",
                    copre=["carta:2024/classes/ranger.md#Nemico Prescelto / Favored Enemy (Ranger 1, pag. 119)",
                           "carta:2024/classes/ranger.md#Rinforzi Fatati / Fey Reinforcements (Viandante Fatato 11, pag. 125)",
                           "POST /characters/{char_id}/rest", "DELETE /characters/{char_id}/active-states/{key}"])
@pytest.mark.parametrize("chiave,stato,incantesimo", [("ranger.favored_enemy", "favored_enemy_free", "hunters-mark"),
                                                      ("ranger.fey_reinforcements", "fey_reinforcements_free", "summon-fey")])
async def test_il_lancio_gratuito_non_fatto_non_consuma_l_uso(client, chiave, stato, incantesimo):
    cid = await _ranger_sub(client, 11, "fey_wanderer")
    pieni = (await _ability(client, cid, chiave))["uses"]
    assert (await _use_feature(client, cid, chiave)).status_code == 200
    await _rest(client, cid, "short")  # l'autorizzazione finisce col riposo breve, senza lancio
    assert (await _ability(client, cid, chiave))["uses"] == pieni, "le carte contano i lanci: senza lancio l'uso resta"
    assert (await _use_feature(client, cid, chiave)).status_code == 200
    r = await client.delete(f"/characters/{cid}/active-states/{stato}")
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, chiave))["uses"] == pieni, "chiusa a mano senza lancio"
    assert (await _use_feature(client, cid, chiave)).status_code == 200
    r = await client.post(f"/characters/{cid}/spells/{await _spell_id(client, cid, incantesimo)}/use", json={"free_cast": True})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, chiave))["uses"] == pieni - 1, "il lancio fatto spende l'uso"


@pytest.mark.caccia(id="CB-4479", fonte="2024 · Paladino, Giuramento di Devozione · Arma Consacrata · pag. 113",
                    zona="regola:2024/paladin", voce="regola",
                    copre=["carta:2024/classes/paladin.md#Arma Consacrata / Sacred Weapon (Incanalare Divinità, Giuramento di Devozione, Paladino 3, pag. 113)",
                           "GET /characters/{char_id}/roll-options", "POST /characters/{char_id}/items/{item_id}/attack"])
async def test_arma_consacrata_sceglie_radioso_o_normale_a_ogni_colpo(client):
    cid = await _oath(client, 3, "devotion", charisma=16)
    spada = await _sword(client, cid, equip="main_hand")
    assert (await _use_feature(client, cid, "paladin.sacred_weapon", params={"weapon": str(spada)})).status_code == 200
    radioso = "paladin.sacred_weapon_radiant"
    assert radioso in {o["key"] for o in await _listed(client, cid, spada)}, "«each time you hit»: la scelta è del colpo"
    for scelte, atteso in (([radioso], True), ([], False)):  # lo stesso privilegio, un colpo radioso e uno normale
        colpo = await _attack(client, cid, spada, options=scelte)
        assert colpo.status_code == 200, colpo.text
        effetti = (colpo.json().get("option_result") or {}).get("effects", [])
        assert any("radios" in e["it"].lower() for e in effetti) is atteso, effetti
    assert (await _ability(client, cid, "paladin.channel_divinity"))["uses"] == 1, "cambiare tipo non costa un altro uso"
