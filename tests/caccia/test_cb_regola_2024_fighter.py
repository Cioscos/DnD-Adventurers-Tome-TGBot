"""Controlli della zona regola:2024/fighter."""
import pytest

from core.db.models import Character

SOTTOCLASSI = {"champion": "Campione", "battle_master": "Maestro di Battaglia", "eldritch_knight": "Cavaliere Mistico",
               "psi_warrior": "Guerriero Psionico"}
SW, AS, IND = "fighter.second_wind", "fighter.action_surge", "fighter.indomitable"
SD, PSI = "fighter.superiority_dice", "fighter.psionic_power"
MANOVRE = ("rally", "trip", "parry", "goading", "menacing", "pushing", "disarming", "precision", "riposte")


async def _guerriero(client, livello, sottoclasse=None, edizione="2024", **punteggi) -> int:
    corpo = {"name": "Guerriero", "initial_class": {"class_name": "fighter", "level": livello,
                                                    "subclass": SOTTOCLASSI.get(sottoclasse)}}
    r = await client.post("/characters", json=corpo)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.patch(f"/characters/{cid}", json={"rules_edition": edizione})
    assert r.status_code == 200, r.text
    for nome, valore in punteggi.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{nome}", json={"value": valore})
        assert r.status_code == 200, r.text
    return cid


async def _scheda(client, cid) -> dict:
    r = await client.get(f"/characters/{cid}")
    assert r.status_code == 200, r.text
    return r.json()


async def _riga(client, cid, chiave) -> dict | None:
    return next((a for a in (await _scheda(client, cid))["abilities"] if a["feature_key"] == chiave), None)


async def _usa(client, cid, chiave, **corpo):
    return await client.post(f"/characters/{cid}/features/{chiave}/use", json=corpo)


async def _turno(client, cid) -> dict:
    r = await client.get(f"/characters/{cid}/turn-state")
    assert r.status_code == 200, r.text
    return r.json()["turn"]


async def _nuovo_turno(client, cid) -> None:
    r = await client.post(f"/characters/{cid}/turn/new")
    assert r.status_code == 200, r.text


async def _riposo(client, cid, tipo) -> None:
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": tipo, "confirm_early": True})
    assert r.status_code == 200, r.text


async def _opzioni(client, cid, tiro, **query) -> list[str]:
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": tiro, **query})
    assert r.status_code == 200, r.text
    return [o["key"] for o in r.json()]


async def _spada(client, cid) -> int:
    meta = {"damage_dice": "1d8", "weapon_type": "melee", "properties": [], "damage_type": "slashing"}
    r = await client.post(f"/characters/{cid}/items", json={"name": "Spada", "item_type": "weapon", "item_metadata": meta})
    assert r.status_code == 201, r.text
    return max(i["id"] for i in r.json()["items"])


async def _pf(factory, cid, valore) -> None:
    async with factory() as s:
        pg = await s.get(Character, cid)
        pg.current_hit_points = valore
        await s.commit()


async def _manovre(client, cid, *scelte) -> None:
    scelta = next(c for c in (await _scheda(client, cid))["pending_choices"] if c.get("group") == "maneuvers")
    r = await client.post(f"/characters/{cid}/choices/{scelta['id']}/resolve",
                          json={"kind": "class_option", "options": list(scelte)[:scelta["count"]]})
    assert r.status_code == 200, r.text


async def _id_classe(client, cid) -> int:
    return next(c["id"] for c in (await _scheda(client, cid))["classes"] if c["class_name"].lower() in ("fighter", "guerriero"))


def _dado_massimo(monkeypatch) -> None:
    monkeypatch.setattr("random.randint", lambda _a, b: b)


# ---------------------------------------------------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2361", fonte="2024 · Guerriero · Indomito · pag. 92; Tiri Salvezza contro la Morte · pag. 28", zona="regola:2024/fighter", voce="regola",
                    copre=["carta:2024/classes/fighter.md#Indomito / Indomitable (Guerriero 9, pag. 92)", "POST /characters/{char_id}/death_saves/roll", "POST /characters/{char_id}/last-roll/options"])
@pytest.mark.xfail(strict=True, reason="CB-2361: difforme dal manuale, confermato")
async def test_indomito_2024_ripete_un_tiro_salvezza_contro_la_morte_fallito(client, test_session_factory):
    cid = await _guerriero(client, 9)
    await _pf(test_session_factory, cid, 0)
    tiro = await client.post(f"/characters/{cid}/death_saves/roll", json={"die": 5})
    assert tiro.status_code == 200 and tiro.json()["outcome"] == "failure", tiro.text
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [IND], "dice": [15]})
    assert r.status_code == 200, r.text
    assert (await _riga(client, cid, IND))["uses"] == 0


@pytest.mark.caccia(id="CB-2362", fonte="2024 · Guerriero · Azione Impetuosa · pag. 91; Movimento Telecinetico · pag. 98", zona="regola:2024/fighter", voce="interazione",
                    copre=["carta:2024/classes/fighter.md#Azione Impetuosa / Action Surge (Guerriero 2, pag. 91)", "carta:2024/classes/fighter.md#Movimento Telecinetico / Telekinetic Movement (Potere Psionico, Guerriero Psionico 3, pag. 98)", "POST /characters/{char_id}/features/{feature_key}/use", "POST /characters/{char_id}/turn/use"])
async def test_l_azione_in_piu_di_azione_impetuosa_non_paga_il_movimento_telecinetico(client):
    cid = await _guerriero(client, 3, "psi_warrior", intelligence=16)
    r = await client.post(f"/characters/{cid}/turn/use", json={"slot": "action"})  # l'azione del turno è già spesa
    assert r.status_code == 200, r.text
    assert (await _usa(client, cid, AS)).status_code == 200
    r = await _usa(client, cid, "fighter.telekinetic_movement")  # azione Magia: l'azione in più non la consente
    assert r.status_code == 409, r.text
    assert (await _turno(client, cid))["extra_actions"] == 1


@pytest.mark.caccia(id="CB-2363", fonte="2024 · Guerriero · Colpo Psionico · pag. 98; Maestro Telecinetico · pag. 99", zona="regola:2024/fighter", voce="regola",
                    copre=["carta:2024/classes/fighter.md#Colpo Psionico / Psionic Strike (Potere Psionico, Guerriero Psionico 3, pag. 98)", "carta:2024/classes/fighter.md#Maestro Telecinetico / Telekinetic Master (Guerriero Psionico 18, pag. 99)", "GET /characters/{char_id}/roll-options", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("livello,opzione", [(3, "fighter.psionic_strike"), (18, "fighter.telekinetic_master_attack")])
@pytest.mark.xfail(strict=True, reason="CB-2363: difforme dal manuale, confermato")
async def test_i_poteri_psionici_con_un_arma_non_valgono_per_il_colpo_senz_armi(client, livello, opzione):
    cid = await _guerriero(client, livello, "psi_warrior", intelligence=16)
    if livello >= 18:  # l'attacco come azione bonus vale mentre si mantiene la concentrazione su Telecinesi
        telecinesi = next(s for s in (await _scheda(client, cid))["spells"] if s["name"] == "Telecinesi")
        r = await client.post(f"/characters/{cid}/spells/{telecinesi['id']}/use", json={"free_cast": True})
        assert r.status_code == 200, r.text
    assert opzione in await _opzioni(client, cid, "attack", item_id=await _spada(client, cid))  # con l'arma sì
    assert opzione not in await _opzioni(client, cid, "attack")  # il Colpo Senz'Armi non è un'arma nel 2024


@pytest.mark.caccia(id="CB-2364", fonte="2024 · Guerriero · Superiorità in Combattimento · pag. 93", zona="regola:2024/fighter", voce="limiti",
                    copre=["carta:2024/classes/fighter.md#Superiorità in Combattimento / Combat Superiority (Maestro di Battaglia 3, pag. 93)", "POST /characters/{char_id}/classes/{class_id}/options/replace"])
@pytest.mark.xfail(strict=True, reason="CB-2364: difforme dal manuale, confermato")
async def test_al_5_livello_non_si_sostituiscono_due_manovre_di_fila(client):
    cid = await _guerriero(client, 5, "battle_master")  # nessuna manovra nuova al 4° e al 5°
    await _manovre(client, cid, "trip", "rally", "parry")
    classe = await _id_classe(client, cid)
    await client.post(f"/characters/{cid}/classes/{classe}/options/replace",
                      json={"group": "maneuvers", "old_key": "trip", "new_key": "goading"})
    r = await client.post(f"/characters/{cid}/classes/{classe}/options/replace",
                          json={"group": "maneuvers", "old_key": "rally", "new_key": "menacing"})
    assert r.status_code >= 400, r.status_code
    scelte = (await client.get(f"/characters/{cid}/classes/{classe}/options/maneuvers")).json()["chosen"]
    assert "rally" in {o["key"] for o in scelte}


# ---------------------------------------------------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-2365", fonte="2024 · Guerriero · Recuperare Energie · pag. 91", zona="regola:2024/fighter", voce="regola",
                    copre=["carta:2024/classes/fighter.md#Recuperare Energie / Second Wind (Guerriero 1, pag. 91)", "POST /characters/{char_id}/features/{feature_key}/use", "POST /characters/{char_id}/rest", "POST /characters/{char_id}/classes"])
async def test_recuperare_energie_cura_1d10_piu_il_livello_e_il_riposo_breve_ne_rende_uno(client, test_session_factory, dadi):
    cid = await _guerriero(client, 5)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 2, "hit_die": 6})
    assert r.status_code == 201, r.text  # il livello da guerriero, non quello totale
    await _pf(test_session_factory, cid, 3)
    dadi(7)
    r = await _usa(client, cid, SW)
    assert r.status_code == 200, r.text
    assert r.json()["healed"] == 7 + 5 and (await _turno(client, cid))["bonus_used"] is True
    await _nuovo_turno(client, cid)
    dadi(1)
    assert (await _usa(client, cid, SW)).status_code == 200
    riga = await _riga(client, cid, SW)
    assert (riga["max_uses"], riga["uses"]) == (3, 1)
    await _riposo(client, cid, "short")
    assert (await _riga(client, cid, SW))["uses"] == 2
    await _riposo(client, cid, "long")
    assert (await _riga(client, cid, SW))["uses"] == 3


@pytest.mark.caccia(id="CB-2366", fonte="2024 · Guerriero · Indomito · pag. 92; 2014 · Guerriero · Indomito · pag. 72", zona="regola:2024/fighter", voce="edizioni",
                    copre=["carta:2024/classes/fighter.md#Indomito / Indomitable (Guerriero 9, pag. 92)", "carta:2014/classes/fighter.md#Indomito / Indomitable (Guerriero 9, pag. 72)", "POST /characters/{char_id}/saving_throws/{ability}/roll", "POST /characters/{char_id}/last-roll/options"])
@pytest.mark.parametrize("edizione,bonus", [("2024", 9), ("2014", 0)])
async def test_indomito_aggiunge_il_livello_da_guerriero_solo_nel_2024(client, edizione, bonus):
    cid = await _guerriero(client, 9, edizione=edizione)
    primo = await client.post(f"/characters/{cid}/saving_throws/wisdom/roll", json={"die": 2})
    assert primo.status_code == 200, primo.text
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": [IND], "dice": [4]})
    assert r.status_code == 200, r.text
    assert r.json()["die"] == 4 and r.json()["total"] == primo.json()["total"] + 2 + bonus


@pytest.mark.caccia(id="CB-2367", fonte="2024 · Guerriero · Critico Migliorato e Critico Superiore · pag. 96", zona="regola:2024/fighter", voce="limiti",
                    copre=["carta:2024/classes/fighter.md#Critico Migliorato / Improved Critical (Campione 3, pag. 96)", "carta:2024/classes/fighter.md#Critico Superiore / Superior Critical (Campione 15, pag. 96)", "POST /characters/{char_id}/attack/unarmed"])
@pytest.mark.parametrize("livello,dado,critico", [(3, 18, False), (3, 19, True), (14, 18, False), (15, 18, True), (15, 17, False)])
async def test_soglia_del_critico_del_campione_anche_col_colpo_senz_armi(client, livello, dado, critico):
    cid = await _guerriero(client, livello, "champion")
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"die": dado})
    assert r.status_code == 200, r.text
    assert r.json()["is_critical"] is critico


@pytest.mark.caccia(id="CB-2368", fonte="2024 · Guerriero · Superiorità in Combattimento, Migliorata e Suprema · pag. 93-94", zona="regola:2024/fighter", voce="limiti",
                    copre=["carta:2024/classes/fighter.md#Superiorità in Combattimento / Combat Superiority (Maestro di Battaglia 3, pag. 93)", "carta:2024/classes/fighter.md#Superiorità in Combattimento Migliorata / Improved Combat Superiority (Maestro di Battaglia 10, pag. 94)", "carta:2024/classes/fighter.md#Superiorità in Combattimento Suprema / Ultimate Combat Superiority (Maestro di Battaglia 18, pag. 94)", "carta:2024/classes/fighter.md#Incoraggiamento / Rally (Manovra, Maestro di Battaglia 3, pag. 95)", "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.parametrize("livello,dadi_tot,facce", [(3, 4, 8), (6, 4, 8), (7, 5, 8), (9, 5, 8), (10, 5, 10), (15, 6, 10), (17, 6, 10), (18, 6, 12)])
async def test_numero_e_taglia_dei_dadi_di_superiorita_per_livello(client, monkeypatch, livello, dadi_tot, facce):
    cid = await _guerriero(client, livello, "battle_master")
    await _manovre(client, cid, *MANOVRE)
    riga = await _riga(client, cid, SD)
    assert (riga["max_uses"], riga["restoration_type"]) == (dadi_tot, "short_rest")
    _dado_massimo(monkeypatch)
    r = await _usa(client, cid, "fighter.maneuver_rally")
    assert r.status_code == 200, r.text
    assert r.json()["rolls"] == [facce] and (await _riga(client, cid, SD))["uses"] == dadi_tot - 1


@pytest.mark.caccia(id="CB-2369", fonte="2024 · Guerriero · Potere Psionico · pag. 98", zona="regola:2024/fighter", voce="limiti",
                    copre=["carta:2024/classes/fighter.md#Potere Psionico / Psionic Power (Guerriero Psionico 3, pag. 98)", "carta:2024/classes/fighter.md#Campo Protettivo / Protective Field (Potere Psionico, Guerriero Psionico 3, pag. 98)", "POST /characters/{char_id}/features/{feature_key}/use"])
@pytest.mark.parametrize("livello,dadi_tot,facce", [(3, 4, 6), (4, 4, 6), (5, 6, 8), (8, 6, 8), (9, 8, 8), (10, 8, 8), (11, 8, 10),
                                                    (12, 8, 10), (13, 10, 10), (16, 10, 10), (17, 12, 12), (20, 12, 12)])
async def test_dadi_di_energia_psionica_per_livello(client, monkeypatch, livello, dadi_tot, facce):
    cid = await _guerriero(client, livello, "psi_warrior", intelligence=16)
    riga = await _riga(client, cid, PSI)
    assert riga["max_uses"] == dadi_tot
    _dado_massimo(monkeypatch)
    r = await _usa(client, cid, "fighter.protective_field")
    assert r.status_code == 200, r.text
    assert r.json()["rolls"] == [facce] and r.json()["given"] == facce + 3


@pytest.mark.caccia(id="CB-2370", fonte="2024 · Guerriero · Incantesimi del Cavaliere Mistico · pag. 97", zona="regola:2024/fighter", voce="limiti",
                    copre=["carta:2024/classes/fighter.md#Incantesimi / Spellcasting (Cavaliere Mistico 3, pag. 97)", "GET /characters/{char_id}"])
@pytest.mark.parametrize("livello,slot,trucchetti,preparati", [
    (3, {1: 2}, 2, 3), (6, {1: 3}, 2, 4), (9, {1: 4, 2: 2}, 2, 6), (10, {1: 4, 2: 3}, 3, 7), (13, {1: 4, 2: 3, 3: 2}, 3, 9),
    (18, {1: 4, 2: 3, 3: 3}, 3, 11), (20, {1: 4, 2: 3, 3: 3, 4: 1}, 3, 13)])
async def test_slot_trucchetti_e_preparati_del_cavaliere_mistico(client, livello, slot, trucchetti, preparati):
    scheda = await _scheda(client, await _guerriero(client, livello, "eldritch_knight"))
    assert {s["level"]: s["total"] for s in scheda["spell_slots"] if s["total"]} == slot
    limiti = scheda["spellcasting"]["limits"][0]
    assert (limiti["cantrips_limit"], limiti["prepared_limit"]) == (trucchetti, preparati)
    assert scheda["spellcasting"]["casters"][0]["ability"] == "intelligence"


@pytest.mark.caccia(id="CB-2371", fonte="2024 · Guerriero · Baluardo di Forza · pag. 99", zona="regola:2024/fighter", voce="regola",
                    copre=["carta:2024/classes/fighter.md#Baluardo di Forza / Bulwark of Force (Guerriero Psionico 15, pag. 99)", "POST /characters/{char_id}/features/{feature_key}/use", "PATCH /characters/{char_id}/conditions"])
async def test_baluardo_di_forza_finisce_quando_il_guerriero_e_incapacitato(client):
    cid = await _guerriero(client, 15, "psi_warrior", intelligence=16)
    prima = (await _scheda(client, cid))["ac"]
    assert (await _usa(client, cid, "fighter.bulwark_of_force")).status_code == 200
    assert (await _scheda(client, cid))["ac"] == prima + 2  # Mezza Copertura
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"stunned": True}})
    assert r.status_code == 200, r.text
    scheda = await _scheda(client, cid)
    assert "bulwark_of_force" not in {s["key"] for s in scheda["active_states"] or []} and scheda["ac"] == prima


@pytest.mark.caccia(id="CB-2372", fonte="2024 · Guerriero · Rimonta Eroica · pag. 96; Sanguinante · pag. 362", zona="regola:2024/fighter", voce="limiti",
                    copre=["carta:2024/classes/fighter.md#Rimonta Eroica / Heroic Rally (Sopravvissuto, Campione 18, pag. 96)", "POST /characters/{char_id}/turn/new"])
@pytest.mark.parametrize("sopra_la_meta,cura", [(0, 5 + 2), (1, 0)])
async def test_rimonta_eroica_cura_solo_da_sanguinante(client, test_session_factory, sopra_la_meta, cura):
    cid = await _guerriero(client, 18, "champion", constitution=14)
    massimo = (await _scheda(client, cid))["hit_points"]
    pf = massimo // 2 + sopra_la_meta
    await _pf(test_session_factory, cid, pf)
    await _nuovo_turno(client, cid)
    assert (await _scheda(client, cid))["current_hit_points"] == pf + cura
