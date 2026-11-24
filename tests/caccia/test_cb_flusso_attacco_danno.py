"""Controlli della zona flusso:attacco-danno."""
import asyncio

import pytest

ATT = "POST /characters/{char_id}/items/{item_id}/attack"
UNA = "POST /characters/{char_id}/attack/unarmed"
DMG = "POST /characters/{char_id}/attack/{attack_id}/damage"
REC = "POST /characters/{char_id}/items/{item_id}/recover-ammo"
LAST = "POST /characters/{char_id}/last-damage/options"
ROUTE = "route:/char/:id/inventory"


async def _pg(client, classe="fighter", livello=1, edizione="2014", sottoclasse=None, **punteggi):
    body = {"name": "Prova", "rules_edition": edizione,
            "initial_class": {"class_name": classe, "level": livello, "subclass": sottoclasse}}
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    for ab, v in punteggi.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ab}", json={"value": v})
        assert r.status_code == 200, r.text
    return cid


async def _oggetto(client, cid, nome, tipo, **extra):
    r = await client.post(f"/characters/{cid}/items", json={"name": nome, "item_type": tipo, **extra})
    assert r.status_code == 201, r.text
    return max(i["id"] for i in r.json()["items"])


async def _arma(client, cid, nome="Spada", dadi="1d8", proprieta=(), tipo="melee", equip=False, **meta):
    m = {"damage_dice": dadi, "weapon_type": tipo, "properties": list(proprieta), **meta}
    iid = await _oggetto(client, cid, nome, "weapon", item_metadata=m)
    if equip:
        r = await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True})
        assert r.status_code == 200, r.text
    return iid


async def _att(client, cid, iid, die=10, **body):
    return await client.post(f"/characters/{cid}/items/{iid}/attack", json={"die": die, **body})


async def _turno(client, cid):
    return (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]


async def _pila(client, cid, iid):
    items = (await client.get(f"/characters/{cid}/items")).json()
    return next(i for i in items if i["id"] == iid)


# --- Rossi -------------------------------------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-037", fonte="2014 · Combattere con Due Armi · pag. 195: serve l'azione di Attacco", zona="flusso:attacco-danno",
                    voce="regola", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_attacco_dell_altra_mano_solo_dopo_l_azione_attacco(client, dadi):
    cid = await _pg(client, dexterity=16)
    a = await _arma(client, cid, "Pugnale", "1d4", ["finesse", "light"], equip=True)
    b = await _arma(client, cid, "Pugnale secondo", "1d4", ["finesse", "light"], equip=True)
    dadi(2)
    r = await _att(client, cid, b, attack_mode="offhand")  # nessun attacco dell'azione prima
    assert r.status_code >= 400, r.text
    assert (await _turno(client, cid))["bonus_used"] is False


@pytest.mark.caccia(id="CB-038", fonte="2014 · Combattere con Due Armi · pag. 195: arma da mischia leggera", zona="flusso:attacco-danno",
                    voce="edizioni", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_2014_attacco_dell_altra_mano_non_con_un_arma_a_distanza(client, dadi):
    cid = await _pg(client, dexterity=16)
    a = await _arma(client, cid, "Pugnale", "1d4", ["finesse", "light"], equip=True)
    h = await _arma(client, cid, "Balestra a mano", "1d6", ["ammunition", "light", "loading"], tipo="ranged", equip=True)
    q = await _oggetto(client, cid, "Quadrelli", "ammunition", quantity=5)
    dadi(3)
    assert (await _att(client, cid, a)).status_code == 200
    dadi(2)
    r = await _att(client, cid, h, attack_mode="offhand")
    assert r.status_code >= 400, r.text
    assert (await _pila(client, cid, q))["quantity"] == 5


@pytest.mark.caccia(id="CB-040", fonte="2014 · Equipaggiamento · Munizioni · pag. 146: una munizione per attacco", zona="flusso:attacco-danno",
                    voce="limiti", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_faretra_veloce_vuota_si_passa_alle_frecce_sciolte(client, dadi):
    cid = await _pg(client, dexterity=16)
    arco = await _arma(client, cid, "Arco corto", "1d6", ["ammunition", "two-handed"], tipo="ranged", equip=True)
    far = await _oggetto(client, cid, "Faretra", "gear", item_metadata={"container": {"quick_access": True}})
    await _oggetto(client, cid, "Frecce", "ammunition", quantity=0, container_id=far)
    sciolte = await _oggetto(client, cid, "Frecce", "ammunition", quantity=10)
    dadi(3)
    j = (await _att(client, cid, arco)).json()
    assert j["ammo_missing"] is False
    assert (await _pila(client, cid, sciolte))["quantity"] == 9


@pytest.mark.caccia(id="CB-041", fonte="2014 · Equipaggiamento · Ricarica · pag. 147: una sola munizione per azione a prescindere dagli attacchi", zona="flusso:attacco-danno",
                    voce="regola", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_ricarica_non_blocca_l_attacco_con_un_altra_arma(client, dadi):
    cid = await _pg(client, "fighter", 5, strength=16, dexterity=16)
    spada = await _arma(client, cid, "Spada", "1d8", [])
    bal = await _arma(client, cid, "Balestra a mano", "1d6", ["ammunition", "light", "loading"], tipo="ranged")
    await _oggetto(client, cid, "Quadrelli", "ammunition", quantity=5)
    dadi(3)
    assert (await _att(client, cid, spada)).status_code == 200
    dadi(3)
    r = await _att(client, cid, bal)  # secondo attacco dell'azione, con l'arma a Ricarica mai sparata nel turno
    assert r.status_code == 200, r.text


# --- Verdi: percorso comune, limiti, regole -------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-042", fonte="2014 · Tiri per colpire e danni · pag. 194-196: dado + modificatore, competenza", zona="flusso:attacco-danno",
                    voce="normale", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_attacco_normale_con_i_numeri_giusti(client, dadi):
    cid = await _pg(client, strength=16)
    w = await _arma(client, cid, "Spada lunga", "1d8")
    dadi(5)
    j = (await _att(client, cid, w)).json()
    assert (j["to_hit_total"], j["damage_rolls"], j["damage_bonus"], j["damage_total"]) == (15, [5], 3, 8)
    assert (await _turno(client, cid))["action_attacks"] == 1


@pytest.mark.caccia(id="CB-043", fonte="2014 · Colpi critici · pag. 196: dadi doppi, modificatori una volta", zona="flusso:attacco-danno",
                    voce="limiti", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_critico_raddoppia_i_dadi_e_il_fumble_non_fa_danno(client, dadi):
    cid = await _pg(client, strength=16)
    w = await _arma(client, cid, "Spada lunga", "2d6+1", magic_bonus=1)
    dadi(2, 3, 4, 5)
    j = (await _att(client, cid, w, die=20)).json()
    assert j["is_critical"] and j["damage_rolls"] == [2, 3, 4, 5]
    assert j["damage_bonus"] == 5 and j["damage_total"] == 19  # +1 del dado, +1 magico, +3 Forza: una volta sola
    r = await _att(client, cid, w, die=1, confirm_extra_attack=True)
    j = r.json()
    assert j["is_fumble"] and (j["damage_total"], j["damage_bonus"]) == (0, 0)


@pytest.mark.caccia(id="CB-044", fonte="2014 · Tiri per i danni · pag. 196: mai danni negativi", zona="flusso:attacco-danno",
                    voce="limiti", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_il_danno_con_modificatore_negativo_non_scende_sotto_zero(client, dadi):
    cid = await _pg(client, strength=6)
    w = await _arma(client, cid, "Randello", "1d4")
    dadi(1)
    j = (await _att(client, cid, w)).json()
    assert (j["damage_bonus"], j["damage_total"]) == (-2, 0)


@pytest.mark.caccia(id="CB-045", fonte="2014 · Guerriero · Attacco Extra: 2, 3 e 4 attacchi a 5, 11 e 20", zona="flusso:attacco-danno",
                    voce="limiti", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
@pytest.mark.parametrize("livello,attacchi", [(4, 1), (5, 2), (11, 3), (20, 4)])
async def test_attacchi_per_azione_del_guerriero(client, dadi, livello, attacchi):
    cid = await _pg(client, "fighter", livello, strength=16)
    w = await _arma(client, cid, "Spada", "1d8")
    esiti = []
    for _ in range(attacchi + 1):
        dadi(3)
        esiti.append((await _att(client, cid, w)).status_code)
    assert esiti == [200] * attacchi + [409]


@pytest.mark.caccia(id="CB-046", fonte="2014 · Monaco · Arti Marziali: d4, d6, d8, d10 a 1, 5, 11, 17; 2024 · Monaco · Arti Marziali: d6, d8, d10, d12", zona="flusso:attacco-danno",
                    voce="edizioni", copre=["POST /characters/{char_id}/attack/unarmed", "route:/char/:id/inventory"])
@pytest.mark.parametrize("edizione,livello,dado", [
    ("2014", 1, "1d4"), ("2014", 5, "1d6"), ("2014", 11, "1d8"), ("2014", 17, "1d10"),
    ("2024", 1, "1d6"), ("2024", 5, "1d8"), ("2024", 11, "1d10"), ("2024", 17, "1d12")])
async def test_dado_arti_marziali_per_livello_ed_edizione(client, dadi, edizione, livello, dado):
    cid = await _pg(client, "monk", livello, edizione, dexterity=16)
    dadi(1)
    j = (await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10})).json()
    assert j["damage_dice"] == dado and j["damage_bonus"] == 3


@pytest.mark.caccia(id="CB-047", fonte="2014 · Barbaro · Critico Brutale: un dado in più a 9, due a 13, tre a 17, solo in mischia", zona="flusso:attacco-danno",
                    voce="regola", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
@pytest.mark.parametrize("livello,dadi_critico", [(8, 2), (9, 3), (13, 4), (17, 5)])
async def test_critico_brutale_dadi_in_piu(client, dadi, livello, dadi_critico):
    cid = await _pg(client, "barbarian", livello, strength=16)
    w = await _arma(client, cid, "Ascia bipenne", "1d12", ["heavy", "two-handed"])
    dadi(*([4] * dadi_critico))
    j = (await _att(client, cid, w, die=20)).json()
    assert j["damage_rolls"] == [4] * dadi_critico


@pytest.mark.caccia(id="CB-048", fonte="2014 · Guerriero · Campione: critico a 19-20 dal 3, a 18-20 dal 15", zona="flusso:attacco-danno",
                    voce="regola", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
@pytest.mark.parametrize("sottoclasse,livello,critici", [("Campione", 3, [19, 20]), ("Campione", 15, [18, 19, 20]), (None, 15, [20])])
async def test_intervallo_del_critico_del_campione(client, dadi, sottoclasse, livello, critici):
    cid = await _pg(client, "fighter", livello, sottoclasse=sottoclasse, strength=16)
    w = await _arma(client, cid, "Spada", "1d8")
    trovati = []
    for die in (17, 18, 19, 20):
        dadi(4, 4)
        r = await _att(client, cid, w, die=die, confirm_extra_attack=True)
        if r.json()["is_critical"]:
            trovati.append(die)
    assert trovati == critici


@pytest.mark.caccia(id="CB-049", fonte="2014 · Armi · Pesante: svantaggio se Piccola; 2024 · Armi · Pesante: Forza o Destrezza sotto 13", zona="flusso:attacco-danno",
                    voce="edizioni", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
@pytest.mark.parametrize("edizione,razza,forza,svantaggio", [
    ("2014", "Halfling", 16, True), ("2014", "Umano", 8, False),
    ("2024", "Umano", 12, True), ("2024", "Umano", 13, False)])
async def test_arma_pesante_per_edizione(client, dadi, edizione, razza, forza, svantaggio):
    cid = await _pg(client, edizione=edizione, strength=forza)
    await client.patch(f"/characters/{cid}", json={"race": razza})
    w = await _arma(client, cid, "Spadone", "2d6", ["heavy", "two-handed"])
    dadi(3, 3)
    j = (await _att(client, cid, w, mode="normal", dice=[10, 15])).json()
    assert (j["mode"] == "disadvantage") is svantaggio


@pytest.mark.caccia(id="CB-050", fonte="2014 · Competenze con le armi · pag. 146: bonus di competenza solo se competente", zona="flusso:attacco-danno",
                    voce="regola", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_senza_competenza_niente_bonus_e_avviso(client, dadi):
    cid = await _pg(client, "wizard", 1, strength=16)
    w = await _arma(client, cid, "Spada lunga", "1d8", weapon_category="martial")
    dadi(3)
    j = (await _att(client, cid, w)).json()
    assert (j["to_hit_bonus"], j["proficiency_warning"]) == (3, True)


# --- Verdi: ripetizione, annullamento, persistenza, permessi --------------------------------------------------------

@pytest.mark.caccia(id="CB-051", fonte="invariante: una richiesta ripetuta non spende due volte", zona="flusso:attacco-danno",
                    voce="ripetizione", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_due_attacchi_insieme_con_limite_uno_ne_passa_uno(client, dadi):
    cid = await _pg(client, "fighter", 1, dexterity=16)
    arco = await _arma(client, cid, "Arco corto", "1d6", ["ammunition", "two-handed"], tipo="ranged", equip=True)
    fr = await _oggetto(client, cid, "Frecce", "ammunition", quantity=5)
    dadi(*([3] * 10))
    rs = await asyncio.gather(_att(client, cid, arco), _att(client, cid, arco))
    assert sorted(r.status_code for r in rs) == [200, 409]
    assert (await _pila(client, cid, fr))["quantity"] == 4
    assert (await _turno(client, cid))["action_attacks"] == 1


@pytest.mark.caccia(id="CB-052", fonte="invariante: il danno di un attacco in sospeso si applica una volta sola", zona="flusso:attacco-danno",
                    voce="ripetizione", copre=["POST /characters/{char_id}/items/{item_id}/attack", "POST /characters/{char_id}/attack/{attack_id}/damage", "route:/char/:id/inventory"])
async def test_il_danno_in_sospeso_si_chiude_una_volta(client, dadi):
    cid = await _pg(client, strength=16)
    w = await _arma(client, cid, "Spada", "1d8")
    dadi(5)
    j = (await _att(client, cid, w, defer_damage=True)).json()
    aid = j["attack_id"]
    assert aid and j["damage_total"] == 8
    assert (await client.post(f"/characters/{cid}/attack/{aid}/damage", json={})).status_code == 200
    assert (await client.post(f"/characters/{cid}/attack/{aid}/damage", json={})).status_code == 404


@pytest.mark.caccia(id="CB-053", fonte="invariante: un attacco in sospeso non sopravvive all'arma, al turno, al riposo", zona="flusso:attacco-danno",
                    voce="annullamento", copre=["POST /characters/{char_id}/attack/{attack_id}/damage", "DELETE /characters/{char_id}/items/{item_id}", "route:/char/:id/inventory"])
async def test_attacco_in_sospeso_cade_con_arma_turno_e_riposo(client, dadi):
    cid = await _pg(client, strength=16)
    w = await _arma(client, cid, "Spada", "1d8")
    for evento in ("elimina", "turno", "riposo"):
        dadi(5)
        aid = (await _att(client, cid, w, defer_damage=True, confirm_extra_attack=True)).json()["attack_id"]
        if evento == "elimina":
            assert (await client.delete(f"/characters/{cid}/items/{w}")).status_code == 200
        elif evento == "turno":
            await client.post(f"/characters/{cid}/turn/new")
        else:
            await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
        assert (await client.post(f"/characters/{cid}/attack/{aid}/damage", json={})).status_code == 404
        if evento == "elimina":
            w = await _arma(client, cid, "Spada", "1d8")


@pytest.mark.caccia(id="CB-054", fonte="invariante: eliminare la pila di munizioni non rompe l'attacco, che segnala le munizioni mancanti", zona="flusso:attacco-danno",
                    voce="annullamento", copre=["POST /characters/{char_id}/items/{item_id}/attack", "DELETE /characters/{char_id}/items/{item_id}", "route:/char/:id/inventory"])
async def test_senza_la_pila_di_munizioni_l_attacco_le_segnala_mancanti(client, dadi):
    cid = await _pg(client, dexterity=16)
    arco = await _arma(client, cid, "Arco corto", "1d6", ["ammunition", "two-handed"], tipo="ranged", equip=True)
    fr = await _oggetto(client, cid, "Frecce", "ammunition", quantity=3)
    assert (await client.delete(f"/characters/{cid}/items/{fr}")).status_code == 200
    dadi(3)
    r = await _att(client, cid, arco)
    assert r.status_code == 200 and r.json()["ammo_missing"] is True and r.json()["ammo"] is None


@pytest.mark.caccia(id="CB-055", fonte="2014 · Equipaggiamento · Munizioni · pag. 146: a fine battaglia metà delle munizioni spese, per difetto", zona="flusso:attacco-danno",
                    voce="persistenza", copre=["POST /characters/{char_id}/items/{item_id}/recover-ammo", "GET /characters/{char_id}/export", "POST /characters/import", "route:/char/:id/inventory"])
async def test_recupero_munizioni_metà_per_difetto_una_volta_e_export(client, dadi):
    cid = await _pg(client, dexterity=16)
    arco = await _arma(client, cid, "Arco corto", "1d6", ["ammunition", "two-handed"], tipo="ranged", equip=True)
    fr = await _oggetto(client, cid, "Frecce", "ammunition", quantity=7)
    for _ in range(7):
        dadi(2)
        assert (await _att(client, cid, arco, confirm_extra_attack=True)).status_code == 200
    pila = await _pila(client, cid, fr)
    assert (pila["quantity"], pila["ammo_spent"]) == (0, 7)
    ex = (await client.get(f"/characters/{cid}/export")).json()
    imp = (await client.post("/characters/import", json=ex)).json()
    assert [(i["quantity"], i["ammo_spent"]) for i in imp["items"] if i["item_type"] == "ammunition"] == [(0, 7)]
    r = await client.post(f"/characters/{cid}/items/{fr}/recover-ammo")
    pila = next(i for i in r.json()["items"] if i["id"] == fr)
    assert (pila["quantity"], pila["ammo_spent"]) == (3, 0)
    r = await client.post(f"/characters/{cid}/items/{fr}/recover-ammo")
    assert next(i for i in r.json()["items"] if i["id"] == fr)["quantity"] == 3


@pytest.mark.caccia(id="CB-056", fonte="invariante: una munizione per attacco, anche mancato, mai sul rilancio con Ispirazione", zona="flusso:attacco-danno",
                    voce="edizioni", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_munizione_per_attacco_mancato_e_non_sul_rilancio_2024(client, dadi):
    cid = await _pg(client, "fighter", 5, "2024", dexterity=16)
    arco = await _arma(client, cid, "Arco corto", "1d6", ["ammunition", "two-handed"], tipo="ranged", equip=True)
    fr = await _oggetto(client, cid, "Frecce", "ammunition", quantity=5)
    await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    dadi(3)
    assert (await _att(client, cid, arco, die=1)).json()["ammo"]["remaining"] == 4
    dadi(3)
    r = await _att(client, cid, arco, die=12, with_inspiration=True)
    assert r.status_code == 200 and r.json()["ammo"]["remaining"] == 4
    assert (await _pila(client, cid, fr))["quantity"] == 4
    assert (await _turno(client, cid))["action_attacks"] == 1


@pytest.mark.caccia(id="CB-057", fonte="2014 · Ispirazione · pag. 125: si spende prima del tiro (il rilancio è del 2024)", zona="flusso:attacco-danno",
                    voce="edizioni", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_2014_il_rilancio_con_ispirazione_dopo_il_tiro_e_rifiutato(client, dadi):
    cid = await _pg(client, strength=16)
    w = await _arma(client, cid, "Spada", "1d8")
    dadi(3)
    r = await _att(client, cid, w, with_inspiration=True)
    assert r.status_code == 409 and r.json()["detail"] == "inspiration_before_roll"
    assert (await _turno(client, cid))["action_attacks"] == 0


@pytest.mark.caccia(id="CB-058", fonte="invariante: i dati di un altro giocatore non si leggono né si cambiano", zona="flusso:attacco-danno",
                    voce="permessi", copre=["POST /characters/{char_id}/items/{item_id}/attack", "POST /characters/{char_id}/attack/unarmed", "POST /characters/{char_id}/attack/{attack_id}/damage", "POST /characters/{char_id}/items/{item_id}/recover-ammo", "POST /characters/{char_id}/items/{item_id}/bond", "POST /characters/{char_id}/items/{item_id}/summon"])
async def test_un_altro_utente_non_attacca_con_il_mio_personaggio(client, dadi, come_utente):
    cid = await _pg(client, strength=16)
    w = await _arma(client, cid, "Spada", "1d8")
    dadi(5)
    aid = (await _att(client, cid, w, defer_damage=True)).json()["attack_id"]
    come_utente(9999)
    assert (await _att(client, cid, w)).status_code == 403
    assert (await client.post(f"/characters/{cid}/attack/unarmed", json={})).status_code == 403
    assert (await client.post(f"/characters/{cid}/attack/{aid}/damage", json={})).status_code == 403
    assert (await client.post(f"/characters/{cid}/items/{w}/recover-ammo")).status_code == 403
    assert (await client.post(f"/characters/{cid}/items/{w}/bond", json={})).status_code == 403
    assert (await client.post(f"/characters/{cid}/items/{w}/summon")).status_code == 403


@pytest.mark.caccia(id="CB-059", fonte="invariante: un oggetto di un altro personaggio non si usa per attaccare", zona="flusso:attacco-danno",
                    voce="permessi", copre=["POST /characters/{char_id}/items/{item_id}/attack"])
async def test_l_arma_di_un_altro_personaggio_non_si_usa(client, dadi):
    mio = await _pg(client, strength=16)
    altro = await _pg(client, strength=16)
    w = await _arma(client, altro, "Spada", "1d8")
    dadi(3)
    assert (await _att(client, mio, w)).status_code == 404
    assert (await _turno(client, mio))["action_attacks"] == 0


@pytest.mark.caccia(id="CB-060", fonte="invariante: i campi che il modale legge ci sono nella risposta", zona="flusso:attacco-danno",
                    voce="contratto", copre=["POST /characters/{char_id}/items/{item_id}/attack", "POST /characters/{char_id}/attack/unarmed", "route:/char/:id/inventory"])
async def test_la_risposta_ha_i_campi_che_il_modale_legge(client, dadi):
    cid = await _pg(client, dexterity=16)
    arco = await _arma(client, cid, "Arco corto", "1d6", ["ammunition", "two-handed"], tipo="ranged", equip=True)
    await _oggetto(client, cid, "Frecce", "ammunition", quantity=2)
    dadi(3)
    j = (await _att(client, cid, arco)).json()
    for k in ("weapon_name", "to_hit_die", "dice", "mode", "magic_bonus", "proficiency_warning", "to_hit_bonus", "to_hit_total",
              "is_critical", "is_fumble", "damage_dice", "damage_rolls", "damage_bonus", "damage_total", "ammo", "ammo_missing", "notes"):
        assert k in j, k
    assert j["ammo"] == {"item_id": j["ammo"]["item_id"], "name": "Frecce", "remaining": 1}
    assert (await _att(client, cid, arco, die=21)).status_code == 422
    assert (await _att(client, cid, arco, die=0)).status_code == 422
    cid2 = await _pg(client, strength=14)
    u = (await client.post(f"/characters/{cid2}/attack/unarmed", json={"die": 8})).json()
    assert (u["weapon_name"], u["damage_dice"], u["damage_type"]) == ("Attacco a mano libera", "1", "bludgeoning")


@pytest.mark.caccia(id="CB-061", fonte="2014 · Colpo senz'armi · pag. 195: 1 + Forza contundente, il fisso non si raddoppia", zona="flusso:attacco-danno",
                    voce="regola", copre=["POST /characters/{char_id}/attack/unarmed", "route:/char/:id/inventory"])
async def test_colpo_senz_armi_del_non_monaco_anche_critico(client):
    cid = await _pg(client, strength=16)
    j = (await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 20})).json()
    assert j["is_critical"] and (j["damage_rolls"], j["damage_bonus"], j["damage_total"]) == ([1], 3, 4)


@pytest.mark.caccia(id="CB-062", fonte="2014 · Monaco · Arti Marziali: solo senza armatura né scudo", zona="flusso:attacco-danno",
                    voce="interazione", copre=["POST /characters/{char_id}/attack/unarmed", "PATCH /characters/{char_id}/items/{item_id}", "route:/char/:id/inventory"])
async def test_il_monaco_con_l_armatura_perde_il_dado_e_la_destrezza(client, dadi):
    cid = await _pg(client, "monk", 5, dexterity=16, strength=10)
    ar = await _oggetto(client, cid, "Cuoio", "armor", item_metadata={"armor_type": "light", "base_ac": 11})
    r = await client.patch(f"/characters/{cid}/items/{ar}", json={"is_equipped": True, "equipment_slot": "body"})
    assert r.status_code == 200
    j = (await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10})).json()
    assert (j["damage_dice"], j["damage_bonus"]) == ("1", 0)
    await client.patch(f"/characters/{cid}/items/{ar}", json={"is_equipped": False})
    dadi(1)
    j = (await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10, "confirm_extra_attack": True})).json()
    assert (j["damage_dice"], j["damage_bonus"]) == ("1d6", 3)


@pytest.mark.caccia(id="CB-063", fonte="2024 · Ispirazione Eroica · pag. 368: rilanciare un dado di danno appena tirato", zona="flusso:attacco-danno",
                    voce="interazione", copre=["POST /characters/{char_id}/items/{item_id}/attack", "POST /characters/{char_id}/last-damage/options", "route:/char/:id/inventory"])
@pytest.mark.parametrize("forza,dado,tiri,die,rilancio,nuovo,totale", [
    (16, "1d8", [5], 10, 0, 2, 5), (16, "1d8", [5, 6], 20, 1, 1, 9), (6, "1d4", [1], 10, 0, 4, 2)])
async def test_rilancio_del_danno_con_ispirazione_aggiorna_il_totale(client, dadi, forza, dado, tiri, die, rilancio, nuovo, totale):
    cid = await _pg(client, "fighter", 1, "2024", strength=forza)
    w = await _arma(client, cid, "Spada", dado)
    await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    dadi(*tiri)
    assert (await _att(client, cid, w, die=die)).status_code == 200
    dadi(nuovo)
    r = await client.post(f"/characters/{cid}/last-damage/options", json={"options": ["inspiration:reroll_damage"], "reroll": [rilancio]})
    assert r.status_code == 200, r.text
    assert r.json()["damage_total"] == totale


@pytest.mark.caccia(id="CB-064", fonte="2014 · Combattere con Due Armi · pag. 195: niente modificatore al danno, salvo se negativo", zona="flusso:attacco-danno",
                    voce="regola", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
@pytest.mark.parametrize("destrezza,bonus", [(16, 0), (6, -2)])
async def test_attacco_dell_altra_mano_senza_modificatore_salvo_negativo(client, dadi, destrezza, bonus):
    cid = await _pg(client, dexterity=destrezza, strength=destrezza)
    a = await _arma(client, cid, "Pugnale", "1d4", ["finesse", "light"], equip=True)
    b = await _arma(client, cid, "Pugnale secondo", "1d4", ["finesse", "light"], equip=True)
    dadi(3, 2, 2)
    assert (await _att(client, cid, a)).status_code == 200
    j = (await _att(client, cid, b, attack_mode="offhand")).json()
    assert j["damage_bonus"] == bonus
    assert (await _att(client, cid, b, attack_mode="offhand")).status_code == 409  # un'azione bonus sola


@pytest.mark.caccia(id="CB-065", fonte="2024 · Armi · Leggera · pag. 213: l'attacco extra con un'altra arma Leggera", zona="flusso:attacco-danno",
                    voce="edizioni", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_2024_l_attacco_extra_con_la_balestra_a_mano_leggera_e_ammesso(client, dadi):
    cid = await _pg(client, "fighter", 1, "2024", dexterity=16)
    a = await _arma(client, cid, "Pugnale", "1d4", ["finesse", "light"], equip=True)
    h = await _arma(client, cid, "Balestra a mano", "1d6", ["ammunition", "light", "loading"], tipo="ranged", equip=True)
    await _oggetto(client, cid, "Quadrelli", "ammunition", quantity=5)
    dadi(3)
    assert (await _att(client, cid, a)).status_code == 200
    dadi(2)
    assert (await _att(client, cid, h, attack_mode="offhand")).status_code == 200


@pytest.mark.caccia(id="CB-066", fonte="2014 · Armi · Versatile e Lancio · pag. 147", zona="flusso:attacco-danno",
                    voce="regola", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_versatile_a_due_mani_lancio_e_scelta_della_caratteristica(client, dadi):
    cid = await _pg(client, strength=10, dexterity=18)
    sp = await _arma(client, cid, "Spada lunga", "1d8", ["versatile"], versatile_dice="1d10")
    dadi(5)
    assert (await _att(client, cid, sp, grip="two")).json()["damage_dice"] == "1d10"
    sc = await _oggetto(client, cid, "Scudo", "shield")
    await client.patch(f"/characters/{cid}/items/{sc}", json={"is_equipped": True, "equipment_slot": "off_hand"})
    r = await _att(client, cid, sp, grip="two", confirm_extra_attack=True)
    assert r.status_code == 422
    jav = await _arma(client, cid, "Giavellotto", "1d6", ["thrown"])
    pug = await _arma(client, cid, "Pugnale", "1d4", ["finesse", "light", "thrown"])
    dadi(3, 2)
    assert (await _att(client, cid, jav, attack_mode="thrown", confirm_extra_attack=True)).json()["to_hit_bonus"] == 2  # Forza
    assert (await _att(client, cid, pug, attack_mode="thrown", confirm_extra_attack=True)).json()["to_hit_bonus"] == 6  # Destrezza
    assert (await _att(client, cid, sp, attack_mode="thrown", confirm_extra_attack=True)).status_code == 422


@pytest.mark.caccia(id="CB-067", fonte="2024 · Oggetti magici · pag. 232: senza sintonia valgono solo i benefici non magici", zona="flusso:attacco-danno",
                    voce="regola", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_il_bonus_dell_arma_magica_vale_solo_con_la_sintonia(client, dadi):
    cid = await _pg(client, strength=16)
    w = await _arma(client, cid, "Spada +2", "1d8", magic_bonus=2, requires_attunement=True, attuned=False)
    dadi(4)
    j = (await _att(client, cid, w)).json()
    assert (j["magic_bonus"], j["to_hit_bonus"], j["damage_bonus"]) == (0, 5, 3)
    w2 = await _arma(client, cid, "Spada +2 sintonizzata", "1d8", magic_bonus=2, requires_attunement=True, attuned=True)
    dadi(4)
    j = (await _att(client, cid, w2, confirm_extra_attack=True)).json()
    assert (j["magic_bonus"], j["to_hit_bonus"], j["damage_bonus"]) == (2, 7, 5)


@pytest.mark.caccia(id="CB-068", fonte="2014 · Guerriero · Cavaliere Mistico · Arma Vincolata: due armi, azione bonus", zona="flusso:attacco-danno",
                    voce="regola", copre=["POST /characters/{char_id}/items/{item_id}/bond", "POST /characters/{char_id}/items/{item_id}/summon", "route:/char/:id/inventory"])
async def test_arma_vincolata_limite_sostituzione_ed_evocazione(client):
    cid = await _pg(client, "fighter", 3, sottoclasse="Cavaliere Mistico")
    w1, w2, w3 = [await _arma(client, cid, f"Spada {n}", "1d8") for n in (1, 2, 3)]
    assert (await client.post(f"/characters/{cid}/items/{w1}/bond", json={})).status_code == 200
    assert (await client.post(f"/characters/{cid}/items/{w2}/bond", json={})).status_code == 200
    r = await client.post(f"/characters/{cid}/items/{w3}/bond", json={})
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "bond_limit")
    assert (await client.post(f"/characters/{cid}/items/{w3}/bond", json={"replace_item_id": w1})).status_code == 200
    r = await client.post(f"/characters/{cid}/items/{w1}/summon")
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "not_bonded")
    assert (await _turno(client, cid))["bonus_used"] is False
    assert (await client.post(f"/characters/{cid}/items/{w2}/summon")).status_code == 200
    assert (await _turno(client, cid))["bonus_used"] is True
    await client.post(f"/characters/{cid}/turn/new")
    r = await client.post(f"/characters/{cid}/items/{w2}/summon")
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "already_in_hand")


@pytest.mark.caccia(id="CB-069", fonte="2014 · Monaco · Arti Marziali: colpo extra solo dopo l'Attacco con arma da monaco o senz'armi", zona="flusso:attacco-danno",
                    voce="interazione", copre=["POST /characters/{char_id}/attack/unarmed", "POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_il_colpo_extra_del_monaco_solo_dopo_un_attacco_da_monaco(client, dadi):
    chiave = "monk.martial_arts_bonus"
    cid = await _pg(client, "monk", 1, dexterity=16)
    lunga = await _arma(client, cid, "Spada lunga", "1d8", weapon_category="martial")
    corta = await _arma(client, cid, "Spada corta", "1d6", ["finesse", "light"], weapon_category="martial")
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10, "options": [chiave]})
    assert r.status_code == 409
    dadi(3)
    assert (await _att(client, cid, lunga)).status_code == 200
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10, "options": [chiave]})
    assert r.status_code == 409
    await client.post(f"/characters/{cid}/turn/new")
    dadi(3)
    assert (await _att(client, cid, corta)).status_code == 200
    dadi(3)
    r = await client.post(f"/characters/{cid}/attack/unarmed", json={"die": 10, "options": [chiave]})
    assert r.status_code == 200 and (await _turno(client, cid))["bonus_used"] is True


@pytest.mark.caccia(id="CB-072", fonte="invariante: l'etichetta «colpo magico» del modale vale per un'arma magica", zona="flusso:attacco-danno",
                    voce="contratto", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_arma_con_bonus_magico_e_un_colpo_magico(client, dadi):
    cid = await _pg(client, strength=16)
    w = await _arma(client, cid, "Spada +1", "1d8", magic_bonus=1)
    dadi(4)
    j = (await _att(client, cid, w)).json()
    assert j["magic_bonus"] == 1
    assert j.get("is_magic") is True


@pytest.mark.xfail(strict=True, reason="CB-073 il rilancio con Ispirazione come primo attacco è gratuito")
@pytest.mark.caccia(id="CB-073", fonte="2024 · Ispirazione Eroica · pag. 368: rilancio di un d20 già tirato", zona="flusso:attacco-danno",
                    voce="ripetizione", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_2024_rilancio_senza_attacco_precedente_non_e_gratuito(client, dadi):
    cid = await _pg(client, "fighter", 1, "2024", dexterity=16)
    arco = await _arma(client, cid, "Arco corto", "1d6", ["ammunition", "two-handed"], tipo="ranged", equip=True)
    fr = await _oggetto(client, cid, "Frecce", "ammunition", quantity=5)
    await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    dadi(3)
    r = await _att(client, cid, arco, with_inspiration=True)
    if r.status_code == 409:
        return
    assert r.status_code == 200
    assert (await _turno(client, cid))["action_attacks"] == 1
    assert (await _pila(client, cid, fr))["quantity"] == 4


@pytest.mark.xfail(strict=True, reason="CB-074 damage_dice non canonico accettato e danno 0 senza errore")
@pytest.mark.caccia(id="CB-074", fonte="invariante: un'arma accettata infligge danno, o la notazione è rifiutata alla creazione", zona="flusso:attacco-danno",
                    voce="limiti", copre=["POST /characters/{char_id}/items", "POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
@pytest.mark.parametrize("notazione", ["d8", "2d6 + 2", "1d8+1d4"])
async def test_notazione_dei_dadi_non_valida_rifiutata_o_con_danno(client, dadi, notazione):
    cid = await _pg(client, strength=10)
    r = await client.post(f"/characters/{cid}/items", json={"name": "X", "item_type": "weapon", "item_metadata": {
        "damage_dice": notazione, "weapon_type": "melee", "properties": []}})
    if r.status_code == 422:
        return
    w = max(i["id"] for i in r.json()["items"])
    dadi(*([3] * 12))
    assert (await _att(client, cid, w)).json()["damage_total"] > 0
