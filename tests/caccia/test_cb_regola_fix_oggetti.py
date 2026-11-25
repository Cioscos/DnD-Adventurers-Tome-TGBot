"""Controlli scritti dal correttore del gruppo oggetti per i dubbi risolti come difetti (Q-…)."""
import pytest

from tests.integration.rules.test_2014_fighter_battle_master import _damage, _hit, _key, _master
from tests.integration.rules.test_2014_fighter_styles import _choose, _greatsword
from tests.integration.rules.test_feats_2014_selection import _char14
from tests.integration.rules.test_feats_take_complete import _take


@pytest.mark.caccia(id="CB-4271", fonte="2014 · Talenti · Aggressore Selvaggio / Savage Attacker · pag. 165",
                    zona="regola:2014/talenti", voce="interazione",
                    copre=["carta:2014/feats.md#Aggressore Selvaggio / Savage Attacker (pag. 165)",
                           "POST /characters/{char_id}/items/{item_id}/attack"])
async def test_aggressore_selvaggio_ritira_anche_i_dadi_del_critico(client, dadi):
    cid = (await _char14(client, "fighter", strength=10))["id"]
    assert (await _take(client, cid, "savage_attacker")).status_code == 201
    r = await client.post(f"/characters/{cid}/items", json={"name": "Spada lunga", "item_type": "weapon", "item_metadata": {
        "damage_dice": "1d8", "weapon_type": "melee", "weapon_category": "martial", "properties": []}})
    spada = max(i["id"] for i in r.json()["items"])
    dadi(1, 1, 8, 8)  # primo tiro del critico: 1 + 1; secondo tiro: 8 + 8
    r = await client.post(f"/characters/{cid}/items/{spada}/attack", json={"die": 20})
    assert r.status_code == 200, r.text
    # al critico i dadi dei danni dell'arma sono due d8: Aggressore Selvaggio li ritira tutti e tiene il risultato migliore
    assert r.json()["damage_rolls"] == [8, 8]


@pytest.mark.caccia(id="CB-4272", fonte="2014 · Guerriero · Combattere con Armi Possenti / Great Weapon Fighting · pag. 72",
                    zona="regola:2014/fighter", voce="interazione",
                    copre=["carta:2014/classes/fighter.md#Combattere con Armi Possenti / Great Weapon Fighting (Stile di Combattimento, Guerriero 1, pag. 72)",
                           "carta:2014/classes/fighter.md#Attacco con Spinta / Pushing Attack (Manovra, Maestro di Battaglia 3, pag. 74)",
                           "POST /characters/{char_id}/attack/{attack_id}/damage"])
async def test_armi_possenti_ritira_anche_il_dado_di_superiorita(client, dadi):
    cid = await _master(client, 3, "pushing", strength=10)
    assert (await _choose(client, cid, "great_weapon")).status_code == 200
    spadone = await _greatsword(client, cid)
    dadi(6, 6)
    colpo = await _hit(client, cid, spadone)
    dadi(1, 5)  # il dado di superiorità esce 1 e si ritira: 5
    r = await _damage(client, cid, colpo, _key("pushing"))
    assert r.status_code == 200, r.text
    # «su un 1 o un 2 a un dado dei danni» dell'attacco in mischia a due mani: anche il dado che la manovra aggiunge
    assert r.json()["option_result"]["extra_rolls"] == [5]


@pytest.mark.caccia(id="CB-4275", fonte="2014 · Equipaggiamento · Tabella pag. 150, Strumenti pag. 154, Armature pag. 145",
                    zona="regola:2014/equipaggiamento", voce="regola",
                    copre=["carta:2014/equipment.md#Tabella (pag. 150)", "carta:2014/equipment.md#Strumenti (tabella, pag. 154)",
                           "carta:2014/equipment.md#Armature / Armor (pag. 145)", "POST /characters"])
@pytest.mark.parametrize("classe, scelte, nome, libbre", [
    ("wizard", [0, 0, 0, 0], "Libro degli incantesimi", 3),  # 1,5 kg
    ("wizard", [0, 0, 0, 0], "Borsa componenti", 2),  # 1 kg
    ("ranger", [0, 0, 1, 0], "Faretra", 1),  # 0,5 kg
    ("ranger", [0, 0, 1, 0], "Frecce", 1),  # 20 frecce, 0,5 kg in tutto
    ("cleric", [0, 0, 0, 0, 0], "Quadrelli", 1.5),  # 20 quadrelli, 0,75 kg in tutto
    ("rogue", [0, 0, 0, 0], "Arnesi da scasso", 1),  # 0,5 kg
    ("bard", [0, 0, 0, 0, 0], "Liuto", 2),  # 1 kg
    ("druid", [0, 0, 0], "Scudo di legno", 6),  # lo scudo, 3 kg, come quello dell'SRD
])
async def test_gli_oggetti_di_partenza_2014_pesano_come_la_tabella(client, classe, scelte, nome, libbre):
    r = await client.post("/characters", json={"name": "Peso", "rules_edition": "2014", "initial_class": {"class_name": classe},
                                               "starting_equipment": scelte})
    assert r.status_code == 201, r.text
    oggetto = next(i for i in r.json()["items"] if i["name"] == nome)
    assert oggetto["weight"] * oggetto["quantity"] == pytest.approx(libbre)
