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


@pytest.mark.caccia(id="CB-761", fonte="2024 · Ispirazione Eroica · pag. 368 (si ritira un dado appena tirato)", zona="flusso:attacco-danno", voce="regola",
                    copre=["POST /characters/{char_id}/attack/unarmed", "POST /characters/{char_id}/spells/{spell_id}/attack"])
@pytest.mark.parametrize("tipo", ["senz_armi", "incantesimo"])
async def test_ritiro_con_ispirazione_senza_tiro_rifiutato_anche_senza_arma(client, test_session_factory, tipo):
    from core.db.models import Character

    cid = (await client.post("/characters", json={"name": "P"})).json()["id"]
    await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 3, "hit_die": 6})
    await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})
    sid = (await client.post(f"/characters/{cid}/spells", json={"name": "Dardo X", "level": 0, "attack_save": "ATK"})).json()["id"]
    url = {"senz_armi": f"/characters/{cid}/attack/unarmed", "incantesimo": f"/characters/{cid}/spells/{sid}/attack"}
    await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    altro = url["incantesimo" if tipo == "senz_armi" else "senz_armi"]
    if tipo == "senz_armi":  # l'attacco di una bestia non ha né arma né incantesimo: non vale come colpo senz'armi
        async with test_session_factory() as s:
            char = await s.get(Character, cid)
            char.turn_state = {**(char.turn_state or {}), "last_roll": {"roll": "attack", "item_id": None, "spell_id": None}}
            await s.commit()
        assert (await client.post(url[tipo], json={"die": 12, "with_inspiration": True})).status_code == 409
    extra = {"confirm_extra_attack": True} if tipo == "senz_armi" else {}
    for prima in (None, altro):  # nessun tiro, oppure un tiro diverso
        if prima:
            assert (await client.post(prima, json={"die": 5})).status_code == 200
        r = await client.post(url[tipo], json={"die": 12, "with_inspiration": True})
        assert (r.status_code, r.json()["detail"]) == (409, {"code": "no_roll_to_reroll"})
    assert (await client.get(f"/characters/{cid}")).json()["heroic_inspiration"] is True
    assert (await client.post(url[tipo], json={"die": 5, **extra})).status_code == 200
    assert (await client.post(url[tipo], json={"die": 12, "with_inspiration": True})).status_code == 200



# --- Giro 2: attacco senz'armi, stili di combattimento, maestrie 2024, munizioni ----------------------------------

def _j(r):
    assert r.status_code == 200, r.text
    return r.json()


async def _scegli(client, cid, gruppo, scelte):
    from tests.integration.rules.test_2014_bard import _resolve

    r = await _resolve(client, cid, gruppo, scelte)
    assert r.status_code == 200, r.text


async def _slot(client, cid, iid, slot):
    r = await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True, "equipment_slot": slot})
    assert r.status_code == 200, r.text


async def _pg24(client, livello=3, stile=None, maestrie=(), **punteggi):
    cid = await _pg(client, "fighter", livello, "2024", **punteggi)
    if stile:
        await _scegli(client, cid, "fighting_style", [stile])
    if maestrie:
        await _scegli(client, cid, "weapon_mastery", list(maestrie))
    return cid


async def _chiavi(client, cid, **query):
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", **query})
    assert r.status_code == 200, r.text
    return [o["key"] for o in r.json()]


async def _senz_armi(client, cid, die=10, **body):
    return await client.post(f"/characters/{cid}/attack/unarmed", json={"die": die, **body})


@pytest.mark.caccia(id="CB-773", fonte="2014 · Colpo senz'armi · pag. 195: 1 + Forza, i danni non scendono sotto zero", zona="flusso:attacco-danno",
                    voce="limiti", copre=["POST /characters/{char_id}/attack/unarmed", "route:/char/:id/inventory"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_colpo_senz_armi_con_forza_molto_bassa_non_cura_ne_va_sotto_zero(client, edizione):
    cid = await _pg(client, "wizard", 1, edizione, strength=1)
    j = _j(await _senz_armi(client, cid))
    assert j["damage_bonus"] == -5 and j["damage_total"] == 0


@pytest.mark.caccia(id="CB-774", fonte="2024 · Colpo senz'armi · pag. 362: 1 + modificatore di Forza di danni contundenti", zona="flusso:attacco-danno",
                    voce="edizioni", copre=["POST /characters/{char_id}/attack/unarmed", "route:/char/:id/inventory"])
async def test_2024_colpo_senz_armi_del_non_monaco_e_uno_piu_forza(client):
    cid = await _pg(client, "fighter", 1, "2024", strength=16, dexterity=10)
    j = _j(await _senz_armi(client, cid))
    assert (j["damage_bonus"], j["damage_total"], j["to_hit_bonus"]) == (3, 4, 5)


@pytest.mark.caccia(id="CB-775", fonte="2014 · Colpo senz'armi · pag. 195: il non monaco usa Forza anche con Destrezza più alta", zona="flusso:attacco-danno",
                    voce="regola", copre=["POST /characters/{char_id}/attack/unarmed", "route:/char/:id/inventory"])
async def test_colpo_senz_armi_del_non_monaco_usa_sempre_la_forza(client):
    cid = await _pg(client, "fighter", 1, strength=8, dexterity=18)
    j = _j(await _senz_armi(client, cid))
    assert (j["to_hit_bonus"], j["damage_bonus"], j["damage_total"]) == (1, -1, 0)


@pytest.mark.caccia(id="CB-776", fonte="2024 · Stili di Combattimento · Tiro con l'Arco · pag. 209: +2 con armi a distanza, non con un'arma da mischia lanciata", zona="flusso:attacco-danno",
                    voce="regola", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_tiro_con_l_arco_non_vale_per_l_arma_da_mischia_lanciata(client, dadi):
    cid = await _pg24(client, 3, "archery", strength=16, dexterity=16)
    arco = await _arma(client, cid, "Arco corto", "1d6", ["ammunition", "two-handed"], tipo="ranged")
    await _oggetto(client, cid, "Frecce", "ammunition", quantity=5)
    ascia = await _arma(client, cid, "Accetta", "1d6", ["thrown", "light"], tipo="melee")
    dadi(3)
    assert _j(await _att(client, cid, arco))["to_hit_bonus"] == 7
    dadi(3)
    r = await _att(client, cid, ascia, attack_mode="thrown", confirm_extra_attack=True)
    assert r.json()["to_hit_bonus"] == 5


@pytest.mark.caccia(id="CB-777", fonte="2024 · Stili di Combattimento · Duello · pag. 209: arma da mischia in una mano e nessun'altra arma; lo scudo va bene", zona="flusso:attacco-danno",
                    voce="regola", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_duello_si_perde_con_una_seconda_arma_ma_non_con_lo_scudo(client, dadi):
    cid = await _pg24(client, 3, "dueling", strength=16)
    spada = await _arma(client, cid, "Spada", "1d8", [])
    await _slot(client, cid, spada, "main_hand")
    dadi(3)
    assert _j(await _att(client, cid, spada))["damage_bonus"] == 5
    pugnale = await _arma(client, cid, "Pugnale", "1d4", ["finesse", "light"])
    await _slot(client, cid, pugnale, "off_hand")
    dadi(3)
    assert _j(await _att(client, cid, spada, confirm_extra_attack=True))["damage_bonus"] == 3
    await client.patch(f"/characters/{cid}/items/{pugnale}", json={"is_equipped": False, "equipment_slot": None})
    scudo = await _oggetto(client, cid, "Scudo", "shield")
    await _slot(client, cid, scudo, "off_hand")
    dadi(3)
    assert _j(await _att(client, cid, spada, confirm_extra_attack=True))["damage_bonus"] == 5


@pytest.mark.caccia(id="CB-778", fonte="2024 · Stili di Combattimento · Combattere con Armi a Due Mani · pag. 209: un dado di danno 1 o 2 conta 3", zona="flusso:attacco-danno",
                    voce="limiti", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_armi_a_due_mani_su_un_critico_alza_anche_i_dadi_del_critico(client, dadi):
    cid = await _pg24(client, 3, "great_weapon", strength=16)
    w = await _arma(client, cid, "Spadone", "2d6", ["heavy", "two-handed"])
    await _slot(client, cid, w, "main_hand")
    dadi(1, 1, 2, 6)
    j = _j(await _att(client, cid, w, die=20))
    assert j["damage_rolls"] == [3, 3, 3, 6] and j["damage_total"] == 18


@pytest.mark.caccia(id="CB-779", fonte="2024 · Stili di Combattimento · Combattere con Due Armi · pag. 209: si aggiunge il modificatore al danno dell'attacco extra", zona="flusso:attacco-danno",
                    voce="regola", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_stile_due_armi_aggiunge_il_modificatore_all_attacco_dell_altra_mano(client, dadi):
    cid = await _pg24(client, 3, "two_weapon", strength=16)
    a = await _arma(client, cid, "Pugnale", "1d4", ["finesse", "light"])
    b = await _arma(client, cid, "Pugnale secondo", "1d4", ["finesse", "light"])
    await _slot(client, cid, a, "main_hand")
    await _slot(client, cid, b, "off_hand")
    dadi(2)
    assert (await _att(client, cid, a)).status_code == 200
    dadi(2)
    j = _j(await _att(client, cid, b, attack_mode="offhand"))
    assert (j["damage_bonus"], j["damage_total"]) == (3, 5)


@pytest.mark.caccia(id="CB-780", fonte="2024 · Maestria · Colpo di striscio · pag. 214: danni pari al modificatore, cresce solo aumentando il modificatore", zona="flusso:attacco-danno",
                    voce="regola", copre=["POST /characters/{char_id}/items/{item_id}/attack", "POST /characters/{char_id}/last-roll/options", "route:/char/:id/inventory"])
async def test_colpo_di_striscio_non_somma_il_bonus_magico_dell_arma(client):
    cid = await _pg24(client, 1, None, ("greatsword", "dagger", "handaxe"), strength=16)
    w = await _arma(client, cid, "Spadone +2", "2d6", ["heavy", "two-handed"], magic_bonus=2)
    await _slot(client, cid, w, "main_hand")
    a = _j(await _att(client, cid, w, die=5, defer_damage=True))
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": ["mastery_graze"]})
    assert r.status_code == 200, r.text
    assert r.json()["attack"]["damage_total"] == 3 and a["attack_id"]


@pytest.mark.caccia(id="CB-781", fonte="2024 · Maestria · Colpo di striscio · pag. 214: danni pari al modificatore usato; con modificatore negativo nessun danno", zona="flusso:attacco-danno",
                    voce="limiti", copre=["GET /characters/{char_id}/roll-options", "route:/char/:id/inventory"])
@pytest.mark.parametrize("forza,offerto", [(8, False), (10, False), (12, True)])
async def test_colpo_di_striscio_solo_con_modificatore_positivo(client, forza, offerto):
    cid = await _pg24(client, 1, None, ("greatsword", "dagger", "handaxe"), strength=forza)
    w = await _arma(client, cid, "Spadone", "2d6", ["heavy", "two-handed"])
    await _slot(client, cid, w, "main_hand")
    _j(await _att(client, cid, w, die=5, defer_damage=True))
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": ["mastery_graze"]})
    assert (r.status_code == 200) is offerto, r.text
    if offerto:
        assert r.json()["attack"]["damage_total"] == 1


@pytest.mark.caccia(id="CB-782", fonte="2024 · Maestria · Vessazione · pag. 214: vantaggio al prossimo attacco, finché non finisce il tuo prossimo turno", zona="flusso:attacco-danno",
                    voce="regola", copre=["POST /characters/{char_id}/attack/{attack_id}/damage", "GET /characters/{char_id}/roll-options", "route:/char/:id/inventory"])
async def test_vessazione_vale_per_un_attacco_e_scade_dopo_il_turno_seguente(client):
    cid = await _pg24(client, 1, None, ("greatsword", "dagger", "handaxe"), strength=16)
    w = await _arma(client, cid, "Accetta", "1d6", ["light", "thrown"])
    await _slot(client, cid, w, "main_hand")

    async def arma_vex():
        a = _j(await _att(client, cid, w, die=10, defer_damage=True, confirm_extra_attack=True))
        r = await client.post(f"/characters/{cid}/attack/{a['attack_id']}/damage", json={"options": ["mastery_vex"]})
        assert r.status_code == 200, r.text

    await arma_vex()
    assert "mastery_vex_advantage" in await _chiavi(client, cid, item_id=w)
    j = _j(await _att(client, cid, w, die=10, confirm_extra_attack=True, options=["mastery_vex_advantage"]))
    assert j["mode"] == "advantage"
    assert "mastery_vex_advantage" not in await _chiavi(client, cid, item_id=w)
    await arma_vex()
    await client.post(f"/characters/{cid}/turn/new")
    assert "mastery_vex_advantage" in await _chiavi(client, cid, item_id=w)
    await client.post(f"/characters/{cid}/turn/new")
    assert "mastery_vex_advantage" not in await _chiavi(client, cid, item_id=w)


@pytest.mark.caccia(id="CB-783", fonte="2024 · Maestria · Graffio · pag. 214: l'attacco extra della proprietà Leggera senza azione bonus, una volta per turno", zona="flusso:attacco-danno",
                    voce="regola", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_graffio_non_spende_l_azione_bonus_e_una_volta_per_turno(client):
    cid = await _pg24(client, 1, None, ("greatsword", "dagger", "handaxe"), strength=16, dexterity=16)
    a = await _arma(client, cid, "Pugnale", "1d4", ["finesse", "light"])
    b = await _arma(client, cid, "Pugnale secondo", "1d4", ["finesse", "light"])
    await _slot(client, cid, a, "main_hand")
    await _slot(client, cid, b, "off_hand")
    _j(await _att(client, cid, a))
    _j(await _att(client, cid, b, attack_mode="offhand", options=["mastery_nick"]))
    assert (await _turno(client, cid))["bonus_used"] is False
    r = await _att(client, cid, b, attack_mode="offhand", options=["mastery_nick"])
    assert r.status_code >= 400, r.text


@pytest.mark.caccia(id="CB-784", fonte="2024 · Maestria · Rovesciamento · pag. 214: CD 8 + modificatore usato per l'attacco + competenza", zona="flusso:attacco-danno",
                    voce="limiti", copre=["POST /characters/{char_id}/attack/{attack_id}/damage", "route:/char/:id/inventory"])
@pytest.mark.parametrize("livello,forza,destrezza,cd", [(1, 16, 10, 13), (5, 10, 18, 15), (9, 20, 10, 17)])
async def test_rovesciamento_usa_il_modificatore_dell_attacco(client, livello, forza, destrezza, cd):
    cid = await _pg24(client, livello, None, ("quarterstaff", "dagger", "handaxe", "mace")[:3 if livello == 1 else 4], strength=forza, dexterity=destrezza)
    w = await _arma(client, cid, "Bastone ferrato", "1d6", ["finesse"] if destrezza > forza else [])
    await _slot(client, cid, w, "main_hand")
    a = _j(await _att(client, cid, w, die=10, defer_damage=True))
    r = await client.post(f"/characters/{cid}/attack/{a['attack_id']}/damage", json={"options": ["mastery_topple"]})
    assert r.status_code == 200, r.text
    assert f"CD {cd}" in r.json()["option_result"]["effects"][0]["it"]


@pytest.mark.caccia(id="CB-785", fonte="2024 · Maestria · Doppio fendente · pag. 214: danno dell'arma senza modificatore, una volta per turno", zona="flusso:attacco-danno",
                    voce="ripetizione", copre=["POST /characters/{char_id}/attack/{attack_id}/damage", "route:/char/:id/inventory"])
async def test_doppio_fendente_senza_modificatore_e_una_volta_per_turno(client, dadi):
    cid = await _pg24(client, 1, None, ("greataxe", "dagger", "handaxe"), strength=16)
    w = await _arma(client, cid, "Ascia bipenne", "1d12", ["heavy", "two-handed"])
    await _slot(client, cid, w, "main_hand")
    dadi(*([12] * 8))
    a = _j(await _att(client, cid, w, die=10, defer_damage=True))
    r = await client.post(f"/characters/{cid}/attack/{a['attack_id']}/damage", json={"options": ["mastery_cleave"]})
    assert r.status_code == 200, r.text
    assert r.json()["option_result"]["separate_total"] == 12
    a = _j(await _att(client, cid, w, die=10, defer_damage=True, confirm_extra_attack=True))
    r = await client.post(f"/characters/{cid}/attack/{a['attack_id']}/damage", json={"options": ["mastery_cleave"]})
    assert r.status_code >= 400, r.text


@pytest.mark.caccia(id="CB-786", fonte="2024 · Maestria · pag. 214: la maestria è solo del 2024; tornando al 2014 le proprietà non valgono", zona="flusso:attacco-danno",
                    voce="edizioni", copre=["GET /characters/{char_id}/roll-options", "PATCH /characters/{char_id}", "route:/char/:id/inventory"])
async def test_le_maestrie_scelte_non_valgono_tornando_al_2014(client):
    cid = await _pg24(client, 1, None, ("greatsword", "dagger", "handaxe"), strength=16)
    w = await _arma(client, cid, "Spadone", "2d6", ["heavy", "two-handed"])
    await _slot(client, cid, w, "main_hand")
    assert "mastery_graze" in await _chiavi(client, cid, item_id=w)
    r = await client.patch(f"/characters/{cid}", json={"rules_edition": "2014"})
    assert r.status_code == 200, r.text
    assert not [k for k in await _chiavi(client, cid, item_id=w) if k.startswith("mastery_")]
    j = (await client.get(f"/characters/{cid}")).json()["items"]
    assert not next(i for i in j if i["id"] == w).get("mastery")


@pytest.mark.caccia(id="CB-787", fonte="2024 · Barbaro · Padronanza delle Armi · pag. 52: solo armi da mischia", zona="flusso:attacco-danno",
                    voce="limiti", copre=["POST /characters/{char_id}/choices/{choice_id}/resolve", "route:/char/:id/inventory"])
async def test_il_barbaro_non_sceglie_una_maestria_per_un_arma_a_distanza(client):
    from tests.integration.rules.test_2014_bard import _resolve

    cid = await _pg(client, "barbarian", 1, "2024")
    r = await _resolve(client, cid, "weapon_mastery", ["greataxe", "longbow"])
    assert r.status_code == 422, r.text


@pytest.mark.caccia(id="CB-788", fonte="2024 · Ladro · Padronanza delle Armi · pag. 129: solo armi con Accurata o Leggera", zona="flusso:attacco-danno",
                    voce="limiti", copre=["POST /characters/{char_id}/choices/{choice_id}/resolve", "route:/char/:id/inventory"])
async def test_il_ladro_sceglie_solo_armi_accurate_o_leggere(client):
    from tests.integration.rules.test_2014_bard import _resolve

    cid = await _pg(client, "rogue", 1, "2024")
    r = await _resolve(client, cid, "weapon_mastery", ["greatsword", "dagger"])
    assert r.status_code == 422, r.text
    r = await _resolve(client, cid, "weapon_mastery", ["rapier", "dagger"])
    assert r.status_code == 200, r.text


@pytest.mark.caccia(id="CB-789", fonte="invariante: due richieste insieme non recuperano due volte le stesse munizioni", zona="flusso:attacco-danno",
                    voce="ripetizione", copre=["POST /characters/{char_id}/items/{item_id}/recover-ammo", "route:/char/:id/inventory"])
async def test_due_recuperi_insieme_restituiscono_le_munizioni_una_volta(client, dadi):
    cid = await _pg(client, dexterity=16)
    arco = await _arma(client, cid, "Arco corto", "1d6", ["ammunition", "two-handed"], tipo="ranged", equip=True)
    fr = await _oggetto(client, cid, "Frecce", "ammunition", quantity=10)
    for _ in range(8):
        dadi(2)
        _j(await _att(client, cid, arco, confirm_extra_attack=True))
    await asyncio.gather(client.post(f"/characters/{cid}/items/{fr}/recover-ammo"),
                         client.post(f"/characters/{cid}/items/{fr}/recover-ammo"))
    pila = await _pila(client, cid, fr)
    assert (pila["quantity"], pila["ammo_spent"]) == (6, 0)


@pytest.mark.caccia(id="CB-790", fonte="2014 · Equipaggiamento · Munizioni · pag. 146: le munizioni si usano per attacchi a distanza con l'arma che le richiede", zona="flusso:attacco-danno",
                    voce="interazione", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_un_arma_lanciata_senza_munizioni_non_ne_consuma(client, dadi):
    cid = await _pg(client, strength=16)
    ascia = await _arma(client, cid, "Accetta", "1d6", ["thrown", "light"])
    fr = await _oggetto(client, cid, "Frecce", "ammunition", quantity=5)
    dadi(3)
    j = _j(await _att(client, cid, ascia, attack_mode="thrown"))
    assert j["ammo"] is None and j["ammo_missing"] is False
    assert (await _pila(client, cid, fr))["quantity"] == 5


@pytest.mark.caccia(id="CB-791", fonte="2014 · Equipaggiamento · Munizioni · pag. 146: a fine battaglia metà delle munizioni spese; fine dello scontro in sessione", zona="flusso:attacco-danno",
                    voce="persistenza", copre=["POST /sessions/{session_id}/encounter/end", "POST /characters/{char_id}/items/{item_id}/recover-ammo", "route:/char/:id/inventory"])
async def test_la_fine_dello_scontro_recupera_meta_delle_munizioni_una_volta(client, test_session_factory, dadi):
    from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session

    as_user(GM_ID)
    sid, cid = await seed_session(test_session_factory, player_dex=14)
    await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    await client.post(f"/sessions/{sid}/encounter/combatants", json={"name": "G", "count": 1, "initiative_mod": 0, "max_hp": 7, "ac": 10})
    as_user(PLAYER_ID)
    arco = await _arma(client, cid, "Arco corto", "1d6", ["ammunition", "two-handed"], tipo="ranged", equip=True)
    fr = await _oggetto(client, cid, "Frecce", "ammunition", quantity=10)
    for _ in range(5):
        dadi(2)
        _j(await _att(client, cid, arco, confirm_extra_attack=True))
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter/end")
    assert r.status_code == 200, r.text
    as_user(PLAYER_ID)
    pila = await _pila(client, cid, fr)
    assert (pila["quantity"], pila["ammo_spent"]) == (7, 0)
    r = await client.post(f"/characters/{cid}/items/{fr}/recover-ammo")
    assert next(i for i in r.json()["items"] if i["id"] == fr)["quantity"] == 7


async def _condizioni(client, cid, **cond):
    r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": cond})
    assert r.status_code == 200, r.text


@pytest.mark.caccia(id="CB-792", fonte="2014 · Tiri per colpire · pag. 194: Forza per la mischia e le armi lanciate, Destrezza per le armi a distanza", zona="flusso:attacco-danno",
                    voce="regola", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
@pytest.mark.parametrize("nome,tipo,proprieta,modo,forza,destrezza,atteso", [
    ("Mazza", "melee", [], "melee", 10, 18, 2), ("Accetta", "melee", ["thrown", "light"], "thrown", 10, 18, 2),
    ("Arco", "ranged", ["ammunition", "two-handed"], "melee", 18, 10, 2), ("Balestra a mano", "ranged", ["ammunition", "light", "loading"], "melee", 18, 8, 1)])
async def test_caratteristica_del_tiro_per_colpire_secondo_il_tipo_di_arma(client, dadi, nome, tipo, proprieta, modo, forza, destrezza, atteso):
    cid = await _pg(client, strength=forza, dexterity=destrezza)
    w = await _arma(client, cid, nome, "1d6", proprieta, tipo=tipo)
    await _oggetto(client, cid, "Munizioni", "ammunition", quantity=3)
    dadi(3)
    assert _j(await _att(client, cid, w, attack_mode=modo))["to_hit_bonus"] == atteso


@pytest.mark.caccia(id="CB-793", fonte="2014 · Multiclasse · Attacco Extra · pag. 164: i privilegi non si sommano fra classi", zona="flusso:attacco-danno",
                    voce="interazione", copre=["POST /characters/{char_id}/classes", "POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
@pytest.mark.parametrize("livello_guerriero,attacchi", [(5, 2), (11, 3)])
async def test_attacco_extra_non_si_somma_fra_guerriero_e_barbaro(client, dadi, livello_guerriero, attacchi):
    cid = await _pg(client, "fighter", livello_guerriero, strength=16)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "barbarian", "level": 5, "hit_die": 12})
    assert r.status_code in (200, 201), r.text
    w = await _arma(client, cid, "Spada", "1d8")
    esiti = []
    for _ in range(attacchi + 1):
        dadi(3)
        esiti.append((await _att(client, cid, w)).status_code)
    assert esiti == [200] * attacchi + [409]


@pytest.mark.caccia(id="CB-794", fonte="2014 · Vantaggio e svantaggio · pag. 173: più fonti dello stesso tipo non si sommano, vantaggio e svantaggio si annullano", zona="flusso:attacco-danno",
                    voce="interazione", copre=["PATCH /characters/{char_id}/conditions", "POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
@pytest.mark.parametrize("condizioni,modo", [({"poisoned": True}, "disadvantage"), ({"poisoned": True, "prone": True}, "disadvantage"),
                                              ({"poisoned": True, "invisible": True}, "normal"), ({"invisible": True}, "advantage")])
async def test_condizioni_sul_tiro_per_colpire_si_combinano_come_da_regola(client, dadi, condizioni, modo):
    cid = await _pg(client, strength=16)
    w = await _arma(client, cid, "Spada", "1d8")
    await _condizioni(client, cid, **condizioni)
    dadi(3)
    assert _j(await _att(client, cid, w, dice=[10, 15]))["mode"] == modo


@pytest.mark.caccia(id="CB-795", fonte="2014 · Condizioni · Spossatezza · pag. 291: svantaggio ai tiri per colpire dal 3° livello", zona="flusso:attacco-danno",
                    voce="edizioni", copre=["PATCH /characters/{char_id}/conditions", "POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
@pytest.mark.parametrize("livello,modo", [(2, "normal"), (3, "disadvantage")])
async def test_2014_spossatezza_dal_terzo_livello_svantaggio_ai_tiri_per_colpire(client, dadi, livello, modo):
    cid = await _pg(client, strength=16)
    w = await _arma(client, cid, "Spada", "1d8")
    await _condizioni(client, cid, exhaustion=livello)
    dadi(3)
    assert _j(await _att(client, cid, w, dice=[10, 15]))["mode"] == modo


@pytest.mark.caccia(id="CB-796", fonte="2024 · Condizioni · Spossatezza · pag. 367: -2 per livello ai Test del d20, nessuno svantaggio", zona="flusso:attacco-danno",
                    voce="edizioni", copre=["PATCH /characters/{char_id}/conditions", "POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_2024_spossatezza_toglie_due_per_livello_al_tiro_per_colpire(client, dadi):
    cid = await _pg(client, "fighter", 1, "2024", strength=16)
    w = await _arma(client, cid, "Spada", "1d8")
    await _condizioni(client, cid, exhaustion=3)
    dadi(3)
    j = _j(await _att(client, cid, w, dice=[10, 15]))
    assert (j["mode"], j["to_hit_bonus"], j["to_hit_total"]) == ("normal", -1, 9)


@pytest.mark.caccia(id="CB-797", fonte="2024 · Stili di Combattimento · Combattere Senz'Armi · pag. 209: d8 senz'armi, i dadi si raddoppiano al critico", zona="flusso:attacco-danno",
                    voce="limiti", copre=["POST /characters/{char_id}/attack/unarmed", "route:/char/:id/inventory"])
async def test_stile_senz_armi_al_critico_raddoppia_il_dado(client, dadi):
    cid = await _pg24(client, 3, "unarmed", strength=16)
    dadi(2, 3)
    j = _j(await _senz_armi(client, cid, die=20))
    assert (j["is_critical"], j["damage_rolls"], j["damage_total"]) == (True, [2, 3], 8)


async def _ira(client, cid):
    r = await client.post(f"/characters/{cid}/features/barbarian.rage/use", json={})
    assert r.status_code == 200, r.text


@pytest.mark.caccia(id="CB-798", fonte="2014 · Barbaro · Ira · pag. 46: solo attacchi in mischia con Forza; 2024 · Barbaro · Ira · pag. 51: ogni attacco con Forza, anche lanciato", zona="flusso:attacco-danno",
                    voce="edizioni", copre=["POST /characters/{char_id}/items/{item_id}/attack", "POST /characters/{char_id}/features/{feature_key}/use", "route:/char/:id/inventory"])
@pytest.mark.parametrize("edizione,bonus_lanciata", [("2014", 3), ("2024", 5)])
async def test_ira_sull_arma_lanciata_per_edizione(client, edizione, bonus_lanciata):
    cid = await _pg(client, "barbarian", 1, edizione, strength=16)
    ascia = await _arma(client, cid, "Accetta", "1d6", ["thrown", "light"])
    await _ira(client, cid)
    assert _j(await _att(client, cid, ascia))["damage_bonus"] == 5
    assert _j(await _att(client, cid, ascia, attack_mode="thrown", confirm_extra_attack=True))["damage_bonus"] == bonus_lanciata


@pytest.mark.caccia(id="CB-799", fonte="2024 · Barbaro · Ira · pag. 51: il bonus vale con un'arma o con un Colpo senz'Armi", zona="flusso:attacco-danno",
                    voce="regola", copre=["POST /characters/{char_id}/attack/unarmed", "POST /characters/{char_id}/features/{feature_key}/use", "route:/char/:id/inventory"])
async def test_2024_ira_vale_anche_per_il_colpo_senz_armi(client):
    cid = await _pg(client, "barbarian", 1, "2024", strength=16)
    await _ira(client, cid)
    j = _j(await _senz_armi(client, cid))
    assert (j["damage_bonus"], j["damage_total"]) == (5, 6)


@pytest.mark.caccia(id="CB-800", fonte="2014 · Combattere con Due Armi · pag. 195: seconda arma leggera impugnata nell'altra mano; 2024 · Armi · Leggera · pag. 213: un'altra arma Leggera", zona="flusso:attacco-danno",
                    voce="edizioni", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_l_attacco_con_l_altra_mano_non_si_fa_con_la_stessa_arma_dell_azione(client, dadi, edizione):
    cid = await _pg(client, "fighter", 1, edizione, dexterity=16)
    a = await _arma(client, cid, "Spada corta", "1d6", ["finesse", "light"])
    b = await _arma(client, cid, "Pugnale", "1d4", ["finesse", "light"])
    await _slot(client, cid, a, "main_hand")
    await _slot(client, cid, b, "off_hand")
    dadi(3)
    _j(await _att(client, cid, a))
    dadi(3)
    r = await _att(client, cid, a, attack_mode="offhand")
    assert r.status_code >= 400, r.text
    assert (await _turno(client, cid))["bonus_used"] is False


@pytest.mark.caccia(id="CB-801", fonte="2024 · Monaco · Arti Marziali · pag. 100: Destrezza anche per la CD di Afferrare e Spingere, solo senza armatura né scudo", zona="flusso:attacco-danno",
                    voce="edizioni", copre=["POST /characters/{char_id}/attack/unarmed", "route:/char/:id/inventory"])
@pytest.mark.parametrize("classe,scudo,cd", [("monk", False, 13), ("monk", True, 10), ("fighter", False, 10)])
async def test_2024_cd_di_afferrare_e_spingere_senz_armi(client, classe, scudo, cd):
    cid = await _pg(client, classe, 1, "2024", strength=10, dexterity=16)
    if scudo:
        await _slot(client, cid, await _oggetto(client, cid, "Scudo", "shield"), "off_hand")
    for effetto in ("grapple", "shove"):
        j = _j(await _senz_armi(client, cid, effect=effetto, confirm_extra_attack=True))
        assert j["save_dc"] == cd and j["effect"] == effetto


@pytest.mark.caccia(id="CB-802", fonte="2024 · Colpo senz'armi · pag. 377: Afferrare e Spingere sostituiscono un attacco; solo in 2024", zona="flusso:attacco-danno",
                    voce="ripetizione", copre=["POST /characters/{char_id}/attack/unarmed", "route:/char/:id/inventory"])
async def test_afferrare_spende_un_attacco_e_nel_2014_e_rifiutato(client, dadi):
    cid = await _pg(client, "fighter", 1, "2024", strength=16)
    _j(await _senz_armi(client, cid, effect="grapple"))
    assert (await _turno(client, cid))["action_attacks"] == 1
    assert (await _senz_armi(client, cid, effect="shove")).status_code == 409
    vecchio = await _pg(client, "fighter", 1, "2014", strength=16)
    assert (await _senz_armi(client, vecchio, effect="grapple")).status_code >= 400
    assert (await _turno(client, vecchio))["action_attacks"] == 0


@pytest.mark.caccia(id="CB-803", fonte="2014 · Armi · Accurata · pag. 147: la scelta fra Forza e Destrezza vale solo per le armi con Accurata", zona="flusso:attacco-danno",
                    voce="contratto", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
@pytest.mark.parametrize("nome,tipo,proprieta,scelta,atteso", [
    ("Mazza", "melee", [], "dexterity", 2), ("Arco", "ranged", ["ammunition", "two-handed"], "strength", 2),
    ("Stocco", "melee", ["finesse"], "dexterity", 6)])
async def test_la_caratteristica_scelta_dal_client_vale_solo_per_le_armi_accurate(client, dadi, nome, tipo, proprieta, scelta, atteso):
    cid = await _pg(client, strength=10 if tipo == "melee" else 18, dexterity=18 if tipo == "melee" else 10)
    w = await _arma(client, cid, nome, "1d6", proprieta, tipo=tipo)
    await _oggetto(client, cid, "Frecce", "ammunition", quantity=3)
    dadi(3)
    assert _j(await _att(client, cid, w, ability=scelta))["to_hit_bonus"] == atteso


@pytest.mark.caccia(id="CB-804", fonte="2014 · Cavaliere Mistico · Arma Vincolata: evocarla in una mano libera; un'arma a due mani le vuole entrambe", zona="flusso:attacco-danno",
                    voce="limiti", copre=["POST /characters/{char_id}/items/{item_id}/summon", "route:/char/:id/inventory"])
async def test_evocare_un_arma_a_due_mani_con_lo_scudo_in_mano_e_rifiutato_senza_spendere(client):
    cid = await _pg(client, "fighter", 3, sottoclasse="Cavaliere Mistico")
    spadone = await _arma(client, cid, "Spadone", "2d6", ["heavy", "two-handed"])
    assert (await client.post(f"/characters/{cid}/items/{spadone}/bond", json={})).status_code == 200
    await _slot(client, cid, await _oggetto(client, cid, "Scudo", "shield"), "off_hand")
    r = await client.post(f"/characters/{cid}/items/{spadone}/summon")
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "no_free_hand")
    assert (await _turno(client, cid))["bonus_used"] is False


@pytest.mark.caccia(id="CB-805", fonte="invariante: un'arma accettata infligge danno anche impugnata a due mani, o la notazione è rifiutata", zona="flusso:attacco-danno",
                    voce="limiti", copre=["POST /characters/{char_id}/items", "PATCH /characters/{char_id}/items/{item_id}", "POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
@pytest.mark.parametrize("come", ["crea", "modifica"])
async def test_dado_versatile_non_valido_rifiutato_o_con_danno(client, dadi, come):
    cid = await _pg(client, strength=10)
    meta = {"damage_dice": "1d8", "versatile_dice": "d10", "weapon_type": "melee", "properties": ["versatile"]}
    if come == "crea":
        r = await client.post(f"/characters/{cid}/items", json={"name": "X", "item_type": "weapon", "item_metadata": meta})
        if r.status_code == 422:
            return
        w = max(i["id"] for i in r.json()["items"])
    else:
        w = await _arma(client, cid, "X", "1d8", ["versatile"])
        r = await client.patch(f"/characters/{cid}/items/{w}", json={"item_metadata": meta})
        if r.status_code == 422:
            return
    dadi(*([4] * 4))
    assert _j(await _att(client, cid, w, grip="two"))["damage_total"] > 0


@pytest.mark.caccia(id="CB-807", fonte="2014 · Condizioni · pag. 290-292: incapacitato, paralizzato, stordito, privo di sensi e pietrificato non compiono azioni", zona="flusso:attacco-danno",
                    voce="interazione", copre=["PATCH /characters/{char_id}/conditions", "POST /characters/{char_id}/items/{item_id}/attack", "POST /characters/{char_id}/attack/unarmed", "route:/char/:id/inventory"])
@pytest.mark.parametrize("condizione", ["incapacitated", "paralyzed", "stunned", "unconscious", "petrified"])
async def test_un_incapace_non_attacca_e_non_spende_munizioni(client, dadi, condizione):
    cid = await _pg(client, dexterity=16)
    arco = await _arma(client, cid, "Arco corto", "1d6", ["ammunition", "two-handed"], tipo="ranged")
    fr = await _oggetto(client, cid, "Frecce", "ammunition", quantity=5)
    await _condizioni(client, cid, **{condizione: True})
    dadi(3)
    assert (await _att(client, cid, arco)).status_code == 409
    assert (await _senz_armi(client, cid)).status_code == 409
    assert (await _pila(client, cid, fr))["quantity"] == 5
    assert (await _turno(client, cid))["action_attacks"] == 0


@pytest.mark.caccia(id="CB-812", fonte="2024 · Armi · Leggera · pag. 213: l'attacco extra con un'altra arma Leggera, anche a distanza", zona="flusso:attacco-danno",
                    voce="edizioni", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_2024_attacco_dell_altra_mano_con_una_balestra_a_mano_spende_una_munizione(client, dadi):
    cid = await _pg(client, "fighter", 1, "2024", dexterity=16)
    a = await _arma(client, cid, "Pugnale", "1d4", ["finesse", "light"])
    h = await _arma(client, cid, "Balestra a mano", "1d6", ["ammunition", "light", "loading"], tipo="ranged")
    await _slot(client, cid, a, "main_hand")
    await _slot(client, cid, h, "off_hand")
    q = await _oggetto(client, cid, "Quadrelli", "ammunition", quantity=5)
    dadi(3)
    _j(await _att(client, cid, a))
    dadi(3)
    j = _j(await _att(client, cid, h, attack_mode="offhand"))
    assert j["ammo"]["remaining"] == 4 and (await _pila(client, cid, q))["quantity"] == 4
    assert (await _turno(client, cid))["bonus_used"] is True


@pytest.mark.xfail(strict=True, reason="CB-813 la pila vuota nello slot munizioni blocca le altre pile")
@pytest.mark.caccia(id="CB-813", fonte="invariante: una pila di munizioni finita non blocca le altre pile dello stesso tipo (come la faretra vuota di CB-040)", zona="flusso:attacco-danno",
                    voce="limiti", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_pila_nello_slot_munizioni_finita_si_passa_alle_frecce_sciolte(client, dadi):
    cid = await _pg(client, dexterity=16)
    arco = await _arma(client, cid, "Arco corto", "1d6", ["ammunition", "two-handed"], tipo="ranged", equip=True)
    nello_slot = await _oggetto(client, cid, "Frecce", "ammunition", quantity=1)
    await _slot(client, cid, nello_slot, "ammunition")
    sciolte = await _oggetto(client, cid, "Frecce", "ammunition", quantity=10)
    dadi(3)
    assert _j(await _att(client, cid, arco))["ammo_missing"] is False
    await client.post(f"/characters/{cid}/turn/new")
    dadi(3)
    j = _j(await _att(client, cid, arco))
    assert j["ammo_missing"] is False
    assert (await _pila(client, cid, sciolte))["quantity"] == 9


@pytest.mark.caccia(id="CB-814", fonte="2014 · Combattere con Due Armi · pag. 195: con un'arma da mischia leggera in una mano, attacco con una seconda arma leggera; 2024 · Armi · Leggera · pag. 213", zona="flusso:attacco-danno",
                    voce="edizioni", copre=["POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_primo_attacco_con_arma_non_leggera_non_apre_l_attacco_dell_altra_mano(client, dadi, edizione):
    cid = await _pg(client, "fighter", 1, edizione, strength=16, dexterity=16)
    lunga = await _arma(client, cid, "Spada lunga", "1d8", [])
    a = await _arma(client, cid, "Pugnale", "1d4", ["finesse", "light"])
    b = await _arma(client, cid, "Pugnale secondo", "1d4", ["finesse", "light"])
    await _slot(client, cid, a, "main_hand")
    await _slot(client, cid, b, "off_hand")
    dadi(3)
    _j(await _att(client, cid, lunga))  # l'attacco dell'azione è con un'arma non leggera
    dadi(3)
    r = await _att(client, cid, b, attack_mode="offhand")
    assert r.status_code >= 400, r.text
    assert (await _turno(client, cid))["bonus_used"] is False


@pytest.mark.caccia(id="CB-815", fonte="invariante: sostituendo lo stile di combattimento il bonus del vecchio stile sparisce dall'attacco", zona="flusso:attacco-danno",
                    voce="annullamento", copre=["POST /characters/{char_id}/classes/{class_id}/options/replace", "POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_cambiando_stile_il_duello_non_resta_sull_attacco(client, dadi):
    cid = await _pg24(client, 3, "dueling", strength=16)
    w = await _arma(client, cid, "Spada", "1d8", [])
    await _slot(client, cid, w, "main_hand")
    dadi(3)
    assert _j(await _att(client, cid, w))["damage_bonus"] == 5
    klass = (await client.get(f"/characters/{cid}")).json()["classes"][0]["id"]
    r = await client.post(f"/characters/{cid}/classes/{klass}/options/replace", json={"group": "fighting_style", "old_key": "dueling", "new_key": "defense"})
    assert r.status_code == 200, r.text
    dadi(3)
    assert _j(await _att(client, cid, w, confirm_extra_attack=True))["damage_bonus"] == 3


@pytest.mark.caccia(id="CB-816", fonte="2024 · Maestria · pag. 214: cambiata l'arma scelta, la proprietà dell'arma tolta non vale più", zona="flusso:attacco-danno",
                    voce="annullamento", copre=["POST /characters/{char_id}/classes/{class_id}/options/replace", "GET /characters/{char_id}/roll-options", "route:/char/:id/inventory"])
async def test_cambiando_la_maestria_la_proprieta_dell_arma_tolta_sparisce(client):
    cid = await _pg24(client, 1, None, ("greatsword", "dagger", "handaxe"), strength=16)
    w = await _arma(client, cid, "Spadone", "2d6", ["heavy", "two-handed"])
    await _slot(client, cid, w, "main_hand")
    assert "mastery_graze" in await _chiavi(client, cid, item_id=w)
    klass = (await client.get(f"/characters/{cid}")).json()["classes"][0]["id"]
    r = await client.post(f"/characters/{cid}/classes/{klass}/options/replace", json={"group": "weapon_mastery", "old_key": "greatsword", "new_key": "rapier"})
    assert r.status_code == 200, r.text
    assert "mastery_graze" not in await _chiavi(client, cid, item_id=w)


@pytest.mark.caccia(id="CB-817", fonte="invariante: tolta la condizione o disequipaggiata l'arma, l'attacco torna com'era", zona="flusso:attacco-danno",
                    voce="annullamento", copre=["PATCH /characters/{char_id}/conditions", "PATCH /characters/{char_id}/items/{item_id}", "POST /characters/{char_id}/items/{item_id}/attack", "route:/char/:id/inventory"])
async def test_tolta_la_condizione_e_disequipaggiato_lo_scudo_l_attacco_torna_normale(client, dadi):
    cid = await _pg24(client, 3, "dueling", strength=16)
    w = await _arma(client, cid, "Spada", "1d8", [])
    await _slot(client, cid, w, "main_hand")
    p = await _arma(client, cid, "Pugnale", "1d4", ["light"])
    await _slot(client, cid, p, "off_hand")
    await _condizioni(client, cid, poisoned=True)
    dadi(3)
    j = _j(await _att(client, cid, w, dice=[10, 15]))
    assert (j["mode"], j["damage_bonus"]) == ("disadvantage", 3)
    await _condizioni(client, cid, poisoned=False)
    await client.patch(f"/characters/{cid}/items/{p}", json={"is_equipped": False, "equipment_slot": None})
    dadi(3)
    j = _j(await _att(client, cid, w, dice=[10, 15], confirm_extra_attack=True))
    assert (j["mode"], j["damage_bonus"]) == ("normal", 5)


@pytest.mark.caccia(id="CB-818", fonte="invariante: i dati e gli attacchi di un altro giocatore non si usano né si leggono", zona="flusso:attacco-danno",
                    voce="permessi", copre=["GET /characters/{char_id}/roll-options", "POST /characters/{char_id}/last-roll/options", "POST /characters/{char_id}/choices/{choice_id}/resolve", "POST /characters/{char_id}/classes/{class_id}/options/replace"])
async def test_un_altro_giocatore_non_tocca_maestrie_opzioni_e_ultimo_tiro(client, come_utente, dadi):
    cid = await _pg24(client, 1, None, ("greatsword", "dagger", "handaxe"), strength=16)
    w = await _arma(client, cid, "Spadone", "2d6", ["heavy", "two-handed"])
    klass = (await client.get(f"/characters/{cid}")).json()["classes"][0]["id"]
    _j(await _att(client, cid, w, die=5, defer_damage=True))
    prima = (await client.get(f"/characters/{cid}")).json()["classes"][0]["options"]
    come_utente(9002)
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": w})
    assert r.status_code in (403, 404), r.text
    r = await client.post(f"/characters/{cid}/last-roll/options", json={"options": ["mastery_graze"]})
    assert r.status_code in (403, 404), r.text
    r = await client.post(f"/characters/{cid}/classes/{klass}/options/replace", json={"group": "weapon_mastery", "old_key": "greatsword", "new_key": "rapier"})
    assert r.status_code in (403, 404), r.text
    r = await client.post(f"/characters/{cid}/items/{w}/recover-ammo")
    assert r.status_code in (403, 404), r.text
    come_utente(1234)
    assert (await client.get(f"/characters/{cid}")).json()["classes"][0]["options"] == prima


@pytest.mark.caccia(id="CB-819", fonte="invariante: il master di una sessione non attacca con il PG di un giocatore", zona="flusso:attacco-danno",
                    voce="permessi", copre=["POST /characters/{char_id}/items/{item_id}/attack", "POST /characters/{char_id}/attack/unarmed", "route:/char/:id/inventory"])
async def test_il_master_non_attacca_con_il_personaggio_di_un_giocatore(client, test_session_factory):
    from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session

    as_user(GM_ID)
    sid, cid = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    w = await _arma(client, cid, "Spada", "1d8")
    as_user(GM_ID)
    assert (await _att(client, cid, w)).status_code in (403, 404)
    assert (await _senz_armi(client, cid)).status_code in (403, 404)
    as_user(PLAYER_ID)
    assert (await _turno(client, cid))["action_attacks"] == 0
