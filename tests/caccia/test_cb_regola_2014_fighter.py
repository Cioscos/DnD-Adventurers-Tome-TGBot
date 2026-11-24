"""Controlli della zona regola:2014/fighter."""
import asyncio

import pytest

from core.db.models import Character

SOTTOCLASSI = {"champion": "Campione", "battle_master": "Maestro di Battaglia", "eldritch_knight": "Cavaliere Mistico"}
SW, AS, IND = "fighter.second_wind", "fighter.action_surge", "fighter.indomitable"


async def _guerriero(client, livello, sottoclasse=None, edizione="2014") -> int:
    corpo = {"name": "Guerriero", "initial_class": {"class_name": "fighter", "level": livello,
                                                    "subclass": SOTTOCLASSI.get(sottoclasse)}}
    r = await client.post("/characters", json=corpo)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.patch(f"/characters/{cid}", json={"rules_edition": edizione})
    assert r.status_code == 200, r.text
    return cid


async def _scheda(client, cid) -> dict:
    r = await client.get(f"/characters/{cid}")
    assert r.status_code == 200, r.text
    return r.json()


async def _riga(client, cid, chiave) -> dict | None:
    return next((a for a in (await _scheda(client, cid))["abilities"] if a["feature_key"] == chiave), None)


async def _classe(client, cid, nome, livello, dado) -> None:
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": nome, "level": livello, "hit_die": dado})
    assert r.status_code == 201, r.text


async def _id_classe(client, cid, *nomi) -> int:
    return next(c["id"] for c in (await _scheda(client, cid))["classes"] if c["class_name"].lower() in nomi)


async def _opzioni(client, cid, tiro, **query) -> list[str]:
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": tiro, **query})
    assert r.status_code == 200, r.text
    return [o["key"] for o in r.json()]


async def _spada(client, cid) -> int:
    meta = {"damage_dice": "1d8", "weapon_type": "melee", "properties": [], "damage_type": "slashing"}
    r = await client.post(f"/characters/{cid}/items", json={"name": "Spada", "item_type": "weapon", "item_metadata": meta})
    assert r.status_code == 201, r.text
    return max(i["id"] for i in r.json()["items"])


async def _trucchetto(client, cid, class_id) -> int:
    r = await client.post(f"/characters/{cid}/spells", json={"name": f"Raggio {class_id}", "level": 0,
                                                             "casting_time": "1 azione", "class_id": class_id})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _pf(factory, cid, valore) -> None:
    async with factory() as s:
        pg = await s.get(Character, cid)
        pg.current_hit_points = valore
        await s.commit()


async def _slot(client, cid) -> dict[int, int]:
    return {s["level"]: s["total"] for s in (await _scheda(client, cid))["spell_slots"] if s["total"]}


async def _manovre(client, cid, *scelte) -> None:
    scelta = next(c for c in (await _scheda(client, cid))["pending_choices"] if c.get("group") == "maneuvers")
    r = await client.post(f"/characters/{cid}/choices/{scelta['id']}/resolve",
                          json={"kind": "class_option", "options": list(scelte)[:scelta["count"]]})
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-1761", fonte="2014 · Guerriero · Incantesimi del Cavaliere Mistico · pag. 75; Multiclasse, Incantesimi · pag. 164; Paladino e Ranger · Incantesimi dal 2° livello · pag. 97, 104", zona="regola:2014/fighter", voce="interazione",
                    copre=["carta:2014/classes/fighter.md#Incantesimi / Eldritch Knight Spellcasting (Cavaliere Mistico 3, pag. 75)", "carta:2014/classes/fighter.md#Multiclasse: Guerriero / Multiclassing: Fighter (Regole opzionali, pag. 163)", "POST /characters/{char_id}/classes"])
@pytest.mark.parametrize("altra", ["paladin", "ranger"])
async def test_un_paladino_o_ranger_di_1_livello_non_cambia_gli_slot_del_cavaliere_mistico(client, altra):
    cid = await _guerriero(client, 7, "eldritch_knight")
    assert await _slot(client, cid) == {1: 4, 2: 2}
    await _classe(client, cid, altra, 1, 10)  # al 1° livello paladino e ranger 2014 non hanno ancora Incantesimi
    assert await _slot(client, cid) == {1: 4, 2: 2}


@pytest.mark.caccia(id="CB-1762", fonte="2014 · Guerriero · Magia da Guerra · pag. 75", zona="regola:2014/fighter", voce="interazione",
                    copre=["carta:2014/classes/fighter.md#Magia da Guerra / War Magic (Cavaliere Mistico 7, pag. 75)", "POST /characters/{char_id}/spells/{spell_id}/use", "GET /characters/{char_id}/roll-options"])
@pytest.mark.xfail(strict=True, reason="CB-1762: difforme dal manuale, confermato")
async def test_magia_da_guerra_vale_dopo_un_trucchetto_di_un_altra_classe(client):
    cid = await _guerriero(client, 7, "eldritch_knight")
    await _classe(client, cid, "wizard", 1, 6)
    guerriero, mago = await _id_classe(client, cid, "fighter", "guerriero"), await _id_classe(client, cid, "wizard", "mago")
    spada = await _spada(client, cid)
    assert (await client.post(f"/characters/{cid}/spells/{await _trucchetto(client, cid, guerriero)}/use", json={})).status_code == 200
    assert "fighter.war_magic" in await _opzioni(client, cid, "attack", item_id=spada)
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200
    assert (await client.post(f"/characters/{cid}/spells/{await _trucchetto(client, cid, mago)}/use", json={})).status_code == 200
    assert "fighter.war_magic" in await _opzioni(client, cid, "attack", item_id=spada)


@pytest.mark.caccia(id="CB-1763", fonte="2014 · Guerriero · Incantesimi del Cavaliere Mistico · pag. 75; Talenti · Incantatore da Guerra · pag. 168", zona="regola:2014/fighter", voce="interazione",
                    copre=["carta:2014/classes/fighter.md#Incantesimi / Eldritch Knight Spellcasting (Cavaliere Mistico 3, pag. 75)", "POST /characters/{char_id}/feats"])
@pytest.mark.xfail(strict=True, reason="CB-1763: difforme dal manuale, confermato")
async def test_il_cavaliere_mistico_puo_prendere_un_talento_che_chiede_di_lanciare_incantesimi(client):
    cid = await _guerriero(client, 4, "eldritch_knight")
    assert (await _scheda(client, cid))["spellcasting"]["casters"]  # lancia incantesimi (Intelligenza)
    r = await client.post(f"/characters/{cid}/feats", json={"feat_key": "war_caster", "ability": None})
    assert r.status_code == 201, r.text


@pytest.mark.caccia(id="CB-1764", fonte="2014 · Guerriero · Indomito · pag. 72; Tiri salvezza contro la morte · pag. 197", zona="regola:2014/fighter", voce="regola",
                    copre=["carta:2014/classes/fighter.md#Indomito / Indomitable (Guerriero 9, pag. 72)", "POST /characters/{char_id}/death_saves/roll", "POST /characters/{char_id}/last-roll/options"])
@pytest.mark.xfail(strict=True, reason="CB-1764: difforme dal manuale, confermato")
async def test_indomito_ripete_un_tiro_salvezza_contro_la_morte_fallito(client, test_session_factory):
    cid = await _guerriero(client, 9)
    await _pf(test_session_factory, cid, 0)
    tiro = await client.post(f"/characters/{cid}/death_saves/roll", json={"die": 5})
    assert tiro.status_code == 200 and tiro.json()["outcome"] == "failure", tiro.text
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [IND], "dice": [15]})
    assert r.status_code == 200, r.text
    assert (await _riga(client, cid, IND))["uses"] == 0


@pytest.mark.caccia(id="CB-1765", fonte="2014 · Guerriero · Superiorità in Combattimento · pag. 73", zona="regola:2014/fighter", voce="regola",
                    copre=["carta:2014/classes/fighter.md#Superiorità in Combattimento / Combat Superiority (Maestro di Battaglia 3, pag. 73)", "POST /characters/{char_id}/classes/{class_id}/options/replace"])
@pytest.mark.xfail(strict=True, reason="CB-1765: difforme dal manuale, confermato")
async def test_una_manovra_si_sostituisce_solo_quando_se_ne_imparano_di_nuove(client):
    cid = await _guerriero(client, 5, "battle_master")  # al 5° livello non si imparano manovre
    await _manovre(client, cid, "trip", "rally", "parry")
    classe = await _id_classe(client, cid, "fighter", "guerriero")
    r = await client.post(f"/characters/{cid}/classes/{classe}/options/replace",
                          json={"group": "maneuvers", "old_key": "trip", "new_key": "goading"})
    assert r.status_code >= 400, r.status_code
    scelte = (await client.get(f"/characters/{cid}/classes/{classe}/options/maneuvers")).json()["chosen"]
    assert {o["key"] for o in scelte} == {"trip", "rally", "parry"}


@pytest.mark.caccia(id="CB-1766", fonte="2014 · Guerriero · Manovre e Colpo Mistico · pag. 74-75; Attacchi in mischia (colpo senz'armi) · pag. 195", zona="regola:2014/fighter", voce="regola",
                    copre=["carta:2014/classes/fighter.md#Attacco Sbilanciante / Trip Attack (Manovra, Maestro di Battaglia 3, pag. 74)", "carta:2014/classes/fighter.md#Attacco Preciso / Precision Attack (Manovra, Maestro di Battaglia 3, pag. 74)", "carta:2014/classes/fighter.md#Attacco con Affondo / Lunging Attack (Manovra, Maestro di Battaglia 3, pag. 74)", "carta:2014/classes/fighter.md#Attacco con Spazzata / Sweeping Attack (Manovra, Maestro di Battaglia 3, pag. 74)", "carta:2014/classes/fighter.md#Colpo Mistico / Eldritch Strike (Cavaliere Mistico 10, pag. 75)", "GET /characters/{char_id}/roll-options"])
@pytest.mark.parametrize("sottoclasse,livello,opzione", [
    ("battle_master", 3, "fighter.maneuver_trip"), ("battle_master", 3, "fighter.maneuver_precision"),
    ("battle_master", 3, "fighter.maneuver_lunging"), ("battle_master", 3, "fighter.maneuver_sweeping"),
    ("eldritch_knight", 10, "fighter.eldritch_strike")])
@pytest.mark.xfail(strict=True, reason="CB-1766: difforme dal manuale, confermato")
async def test_le_opzioni_di_un_attacco_con_arma_valgono_anche_per_il_colpo_senz_armi(client, sottoclasse, livello, opzione):
    cid = await _guerriero(client, livello, sottoclasse)
    if sottoclasse == "battle_master":
        await _manovre(client, cid, opzione.removeprefix("fighter.maneuver_"), "rally", "parry")
    assert opzione in await _opzioni(client, cid, "attack", item_id=await _spada(client, cid))  # con l'arma sì
    assert opzione in await _opzioni(client, cid, "attack")  # colpo senz'armi: attacco con arma da mischia


# ---------------------------------------------------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-1767", fonte="2014 · Guerriero · Recuperare Energie · pag. 72", zona="regola:2014/fighter", voce="regola",
                    copre=["carta:2014/classes/fighter.md#Recuperare Energie / Second Wind (Guerriero 1, pag. 72)", "POST /characters/{char_id}/features/{feature_key}/use", "POST /characters/{char_id}/rest"])
async def test_recuperare_energie_cura_1d10_piu_il_livello_da_guerriero_e_torna_col_riposo_breve(client, test_session_factory, dadi):
    cid = await _guerriero(client, 5)
    await _classe(client, cid, "wizard", 2, 6)  # il livello da guerriero, non quello totale
    await _pf(test_session_factory, cid, 3)
    dadi(7)
    r = await client.post(f"/characters/{cid}/features/{SW}/use", json={})
    assert r.status_code == 200, r.text
    assert r.json()["healed"] == 7 + 5 and (await _scheda(client, cid))["current_hit_points"] == 3 + 12
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]["bonus_used"] is True
    assert (await _riga(client, cid, SW))["uses"] == 0
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "confirm_early": True})
    assert r.status_code == 200, r.text
    assert (await _riga(client, cid, SW))["uses"] == 1


@pytest.mark.caccia(id="CB-1768", fonte="2014 · Guerriero · Azione Impetuosa · pag. 72", zona="regola:2014/fighter", voce="limiti",
                    copre=["carta:2014/classes/fighter.md#Azione Impetuosa / Action Surge (Guerriero 2, pag. 72)", "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello,usi", [(1, None), (2, 1), (16, 1), (17, 2), (20, 2)])
async def test_usi_di_azione_impetuosa_per_livello(client, livello, usi):
    riga = await _riga(client, await _guerriero(client, livello), AS)
    assert (riga and (riga["max_uses"], riga["restoration_type"])) == (usi and (usi, "short_rest"))


@pytest.mark.caccia(id="CB-1769", fonte="2014 · Guerriero · Indomito · pag. 72", zona="regola:2014/fighter", voce="limiti",
                    copre=["carta:2014/classes/fighter.md#Indomito / Indomitable (Guerriero 9, pag. 72)", "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello,usi", [(8, None), (9, 1), (12, 1), (13, 2), (16, 2), (17, 3), (20, 3)])
async def test_usi_di_indomito_per_livello_e_solo_col_riposo_lungo(client, livello, usi):
    riga = await _riga(client, await _guerriero(client, livello), IND)
    assert (riga and (riga["max_uses"], riga["restoration_type"])) == (usi and (usi, "long_rest"))


@pytest.mark.caccia(id="CB-1770", fonte="2014 · Guerriero · Attacco Extra · pag. 72", zona="regola:2014/fighter", voce="limiti",
                    copre=["carta:2014/classes/fighter.md#Attacco Extra / Extra Attack (Guerriero 5, pag. 72)", "GET /characters/{character_id}/turn-state"])
@pytest.mark.parametrize("livello,attacchi", [(4, 1), (5, 2), (10, 2), (11, 3), (19, 3), (20, 4)])
async def test_attacchi_dell_azione_attacco_per_livello(client, livello, attacchi):
    cid = await _guerriero(client, livello)
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["attacks_allowed"] == attacchi


@pytest.mark.caccia(id="CB-1771", fonte="2014 · Guerriero · Critico Migliorato e Critico Superiore · pag. 72", zona="regola:2014/fighter", voce="limiti",
                    copre=["carta:2014/classes/fighter.md#Critico Migliorato / Improved Critical (Campione 3, pag. 72)", "carta:2014/classes/fighter.md#Critico Superiore / Superior Critical (Campione 15, pag. 72)", "POST /characters/{char_id}/items/{item_id}/attack"])
@pytest.mark.parametrize("livello,dado,critico", [(3, 18, False), (3, 19, True), (14, 18, False), (15, 18, True), (15, 17, False)])
async def test_soglia_del_critico_del_campione(client, livello, dado, critico):
    cid = await _guerriero(client, livello, "champion")
    r = await client.post(f"/characters/{cid}/items/{await _spada(client, cid)}/attack", json={"die": dado})
    assert r.status_code == 200, r.text
    assert r.json()["is_critical"] is critico


@pytest.mark.caccia(id="CB-1772", fonte="2014 · Guerriero · Tabella Incantesimi del Cavaliere Mistico · pag. 75", zona="regola:2014/fighter", voce="limiti",
                    copre=["carta:2014/classes/fighter.md#Incantesimi / Eldritch Knight Spellcasting (Cavaliere Mistico 3, pag. 75)", "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello,slot", [(3, {1: 2}), (6, {1: 3}), (7, {1: 4, 2: 2}), (13, {1: 4, 2: 3, 3: 2}),
                                          (19, {1: 4, 2: 3, 3: 3, 4: 1}), (20, {1: 4, 2: 3, 3: 3, 4: 1})])
async def test_slot_del_cavaliere_mistico_per_livello(client, livello, slot):
    assert await _slot(client, await _guerriero(client, livello, "eldritch_knight")) == slot


@pytest.mark.caccia(id="CB-1773", fonte="2014 · Guerriero · Recuperare Energie · pag. 72; 2024 · Guerriero · Recuperare Energie · pag. 91", zona="regola:2014/fighter", voce="edizioni",
                    copre=["carta:2014/classes/fighter.md#Recuperare Energie / Second Wind (Guerriero 1, pag. 72)", "GET /characters/{char_id}"])
@pytest.mark.parametrize("edizione,usi", [("2014", 1), ("2024", 3)])
async def test_usi_di_recuperare_energie_al_4_livello_per_edizione(client, edizione, usi):
    riga = await _riga(client, await _guerriero(client, 4, edizione=edizione), SW)
    assert riga["max_uses"] == usi


@pytest.mark.caccia(id="CB-1774", fonte="invariante: un doppio invio di Recuperare Energie spende l'unico uso una volta e cura una volta", zona="regola:2014/fighter", voce="ripetizione",
                    copre=["carta:2014/classes/fighter.md#Recuperare Energie / Second Wind (Guerriero 1, pag. 72)", "POST /characters/{char_id}/features/{feature_key}/use"])
async def test_due_invii_insieme_di_recuperare_energie_curano_una_volta(client, test_session_factory):
    cid = await _guerriero(client, 5)
    await _pf(test_session_factory, cid, 3)
    risposte = await asyncio.gather(*(client.post(f"/characters/{cid}/features/{SW}/use", json={}) for _ in range(2)))
    assert sorted(r.status_code for r in risposte) == [200, 409], [r.text for r in risposte]
    curati = next(r.json()["healed"] for r in risposte if r.status_code == 200)
    assert (await _scheda(client, cid))["current_hit_points"] == 3 + curati
    assert (await _riga(client, cid, SW))["uses"] == 0
