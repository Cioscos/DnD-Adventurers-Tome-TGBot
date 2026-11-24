"""Controlli della zona flusso:compagni-forme."""
import asyncio

import pytest

from tests.integration.rules.test_2014_bard import _full
from tests.integration.rules.test_2014_druid import _activate, _beast, _druid, _form
from tests.integration.rules.test_2014_ranger_beast import _beast as _bestia14, _bite, _companion, _master, _order
from tests.integration.rules.test_2024_druid import _druid24, _new_turn
from tests.integration.rules.test_2024_druid_circles import _circle
from tests.integration.rules.test_2024_ranger_subclasses import _beast as _bestia24, _sub

WILD = "druid.wild_shape"


async def _lista(client, cid) -> list[dict]:
    return (await client.get(f"/characters/{cid}/companions")).json()


async def _usi(client, cid) -> int:
    return next(a["uses"] for a in (await _full(client, cid))["abilities"] if a["feature_key"] == WILD)


async def _nuovo_turno(client, cid) -> None:
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200


# ---------------------------------------------------------------------------
# Rossi
# ---------------------------------------------------------------------------

@pytest.mark.caccia(id="CB-337", fonte="2024 · Druido · Circolo della Luna · Forme del Circolo · pag. 86", zona="flusso:compagni-forme",
                    voce="annullamento", copre=["POST /characters/{char_id}/companions/{comp_id}/deactivate",
                                                "carta:2024/classes/druid.md#Forme del Circolo / Circle Forms (Circolo della Luna 3, pag. 86)"])
async def test_la_ca_della_luna_vale_solo_finche_si_e_in_forma(client):
    cid = await _circle(client, "moon", level=3, wisdom=18)
    forma = await _form(client, cid, _beast(0.25), hp=10)  # CA della bestia 12
    r = await _activate(client, cid, forma)
    assert r.json()["armor_class"] == 17  # 13 + SAG (+4), maggiore di quella della bestia
    await _nuovo_turno(client, cid)
    assert (await client.post(f"/characters/{cid}/companions/{forma}/deactivate")).status_code == 200
    scheda = next(c for c in await _lista(client, cid) if c["id"] == forma)
    assert scheda["armor_class"] == 12


@pytest.mark.caccia(id="CB-338", fonte="2024 · Druido · Forma Selvatica · pag. 80", zona="flusso:compagni-forme", voce="limiti",
                    copre=["PATCH /characters/{char_id}/companions/{comp_id}", "carta:2024/classes/druid.md#Forma Selvatica / Wild Shape (Druido 2, pag. 80)"])
async def test_cambiare_tipo_non_aggira_le_forme_conosciute(client):
    cid = await _druid24(client, 2)  # 4 forme conosciute
    for i in range(4):
        await _form(client, cid, _beast(0.25), name=f"Forma {i}")
    r = await client.post(f"/characters/{cid}/companions", json={"kind": "familiar", "name": "Gufo", "statblock": {}, "max_hp": 1})
    await client.patch(f"/characters/{cid}/companions/{r.json()['id']}", json={"kind": "wild_shape"})
    assert sum(c["kind"] == "wild_shape" for c in await _lista(client, cid)) <= 4


@pytest.mark.caccia(id="CB-339", fonte="2014 · Ranger · Signore delle Bestie · Compagno del Ranger · pag. 106", zona="flusso:compagni-forme",
                    voce="annullamento", copre=["DELETE /characters/{char_id}/companions/{comp_id}", "POST /characters/{char_id}/companions/{comp_id}/attack",
                                                "carta:2014/classes/ranger.md#Compagno del Ranger / Ranger's Companion (Signore delle Bestie 3, pag. 106)"])
async def test_l_ordine_dato_a_una_bestia_eliminata_non_passa_alla_nuova(client):
    cid, vecchia = await _bestia14(client, 3)
    assert (await _order(client, cid, vecchia, "attack")).status_code == 200
    assert (await client.delete(f"/characters/{cid}/companions/{vecchia}")).status_code == 204
    nuova = (await _companion(client, cid)).json()["id"]
    r = await _bite(client, cid, nuova)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "no_order"


@pytest.mark.caccia(id="CB-340", fonte="invariante: un compagno nascosto perché dell'altra edizione non riceve ordini e non costa azioni",
                    zona="flusso:compagni-forme", voce="edizioni",
                    copre=["POST /characters/{char_id}/companions/{comp_id}/command", "PATCH /characters/{char_id}"])
async def test_la_bestia_2014_nascosta_in_2024_non_riceve_ordini(client):
    cid, bestia = await _bestia14(client, 3)
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    assert await _lista(client, cid) == []
    r = await _order(client, cid, bestia, "dodge")
    turno = (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]
    assert r.status_code in (404, 409) and turno["action_used"] is False


@pytest.mark.caccia(id="CB-341", fonte="invariante: un nome di soli spazi è un nome vuoto (la UI disabilita Aggiungi con il nome vuoto)",
                    zona="flusso:compagni-forme", voce="limiti", copre=["POST /characters/{char_id}/companions"])
@pytest.mark.parametrize("nome", [" ", "   ", "\t"])
async def test_un_compagno_senza_nome_non_si_crea(client, nome):
    cid = await _druid(client, 4)
    r = await client.post(f"/characters/{cid}/companions", json={"kind": "familiar", "name": nome, "statblock": {}, "max_hp": 1})
    assert r.status_code == 422


@pytest.mark.caccia(id="CB-342", fonte="invariante: un nome di soli spazi è un nome vuoto", zona="flusso:compagni-forme", voce="limiti",
                    copre=["PATCH /characters/{char_id}/companions/{comp_id}"])
async def test_un_compagno_non_si_rinomina_con_soli_spazi(client):
    cid = await _druid(client, 4)
    comp = (await client.post(f"/characters/{cid}/companions", json={"kind": "familiar", "name": "Gufo", "statblock": {}, "max_hp": 1})).json()["id"]
    r = await client.patch(f"/characters/{cid}/companions/{comp}", json={"name": "   "})
    assert r.status_code == 422
    assert (await _lista(client, cid))[0]["name"] == "Gufo"


# ---------------------------------------------------------------------------
# Verdi
# ---------------------------------------------------------------------------

LIMITI = [  # edizione, livello, circolo, GS massimo atteso (dalle schede)
    ("2014", 2, None, 0.25), ("2014", 4, None, 0.5), ("2014", 8, None, 1),
    ("2014", 2, "moon", 1), ("2014", 6, "moon", 2), ("2014", 9, "moon", 3),
    ("2024", 2, None, 0.25), ("2024", 4, None, 0.5), ("2024", 8, None, 1),
    ("2024", 3, "moon", 1), ("2024", 6, "moon", 2), ("2024", 9, "moon", 3),
]


@pytest.mark.caccia(id="CB-343", fonte="2014 e 2024 · Druido · Forme Bestiali e Forme del Circolo · pag. 66-69 e 80-86", zona="flusso:compagni-forme",
                    voce="regola", copre=["POST /characters/{char_id}/companions/{comp_id}/activate", "carta:2014/classes/druid.md#Forma Selvatica / Wild Shape (Druido 2, pag. 66)", "carta:2024/classes/druid.md#Forma Selvatica / Wild Shape (Druido 2, pag. 80)"])
@pytest.mark.parametrize("edizione, livello, circolo, gs", LIMITI)
async def test_il_gs_massimo_della_forma_segue_la_scheda(client, edizione, livello, circolo, gs):
    async def pg():
        if edizione == "2014":
            return await _druid(client, livello, circolo)
        return await (_circle(client, circolo, level=livello) if circolo else _druid24(client, livello))
    cid = await pg()
    ok = await _form(client, cid, _beast(gs))
    assert (await _activate(client, cid, ok)).status_code == 200
    cid = await pg()
    troppo = await _form(client, cid, _beast(gs + 0.5 if gs < 1 and not circolo else gs + 1))
    r = await _activate(client, cid, troppo)
    assert r.status_code == 409 and "cr" in r.json()["detail"]["reasons"]


@pytest.mark.caccia(id="CB-344", fonte="2014 · Druido · Forme Bestiali · pag. 66 (2° nessun nuoto né volo, 4° nuoto, 8° volo)", zona="flusso:compagni-forme",
                    voce="regola", copre=["POST /characters/{char_id}/companions/{comp_id}/activate", "carta:2014/classes/druid.md#Forma Selvatica / Wild Shape (Druido 2, pag. 66)"])
@pytest.mark.parametrize("livello, nuoto, volo", [(2, False, False), (3, False, False), (4, True, False), (7, True, False), (8, True, True)])
async def test_nuoto_e_volo_2014_per_livello(client, livello, nuoto, volo):
    for chiave, atteso in (("swim", nuoto), ("fly", volo)):
        cid = await _druid(client, livello)
        forma = await _form(client, cid, _beast(0.25, **{chiave: 30}))
        assert (await _activate(client, cid, forma)).status_code == (200 if atteso else 409)


@pytest.mark.caccia(id="CB-345", fonte="2014 · Ranger · Compagno del Ranger · pag. 106", zona="flusso:compagni-forme", voce="regola",
                    copre=["POST /characters/{char_id}/companions",
                           "carta:2014/classes/ranger.md#Compagno del Ranger / Ranger's Companion (Signore delle Bestie 3, pag. 106)"])
async def test_la_bestia_del_ranger_multiclasse_usa_il_livello_da_ranger(client):
    cid = await _master(client, 3)  # competenza +2 a 3° livello
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 2, "hit_die": 10})).status_code == 201
    b = (await _companion(client, cid)).json()  # scheda: 13 PF, CA 12; livello totale 5, competenza +3
    assert (b["max_hp"], b["armor_class"], b["attack_bonus_extra"], b["damage_bonus_extra"]) == (13, 15, 3, 3)


@pytest.mark.caccia(id="CB-346", fonte="2024 · Ranger · Signore delle Bestie · Bestia del Cielo · pag. 124", zona="flusso:compagni-forme", voce="regola",
                    copre=["GET /characters/{char_id}/companions",
                           "carta:2024/classes/ranger.md#Bestia del Cielo / Beast of the Sky (Signore delle Bestie 3, pag. 124)"])
async def test_la_bestia_del_cielo_ha_pf_ca_e_bonus_dal_livello(client):
    cid = await _sub(client, 5, "beast_master", wisdom=14)
    b = await _bestia24(client, cid, "sky")
    assert (b["max_hp"], b["armor_class"], b["attack_bonus_extra"], b["damage_bonus_extra"]) == (24, 15, 5, 2)


@pytest.mark.caccia(id="CB-347", fonte="2014 · Druido · Circolo della Luna · Forma Selvatica Elementale · pag. 69", zona="flusso:compagni-forme",
                    voce="regola", copre=["POST /characters/{char_id}/companions/{comp_id}/activate",
                                         "carta:2014/classes/druid.md#Forma Selvatica Elementale / Elemental Wild Shape (Circolo della Luna 10, pag. 69)"])
async def test_la_forma_elementale_costa_due_usi_e_con_uno_solo_non_parte(client):
    cid = await _druid(client, 10, "moon")
    elementale = await _form(client, cid, _beast(0, kind="elemental"), name="Elementale")
    assert (await _activate(client, cid, elementale)).status_code == 200
    assert await _usi(client, cid) == 0
    cid = await _druid(client, 10, "moon")
    bestia = await _form(client, cid, _beast(1))
    assert (await _activate(client, cid, bestia)).status_code == 200
    await _nuovo_turno(client, cid)
    elementale = await _form(client, cid, _beast(0, kind="elemental"), name="Elementale")
    assert (await _activate(client, cid, elementale)).status_code == 409
    assert await _usi(client, cid) == 1


@pytest.mark.caccia(id="CB-348", fonte="2024 · Druido · Regole della Forma Selvatica e Forme del Circolo · pag. 81 e 86", zona="flusso:compagni-forme",
                    voce="regola", copre=["POST /characters/{char_id}/companions/{comp_id}/activate",
                                           "carta:2024/classes/druid.md#Regole della Forma Selvatica / Rules While Shape-Shifted (Druido 2, pag. 81)"])
@pytest.mark.parametrize("luna, livello, atteso", [(False, 4, 4), (True, 4, 12), (True, 6, 18)])
async def test_pf_temporanei_all_assunzione_della_forma_2024(client, luna, livello, atteso):
    cid = await (_circle(client, "moon", level=livello) if luna else _druid24(client, livello))
    forma = await _form(client, cid, _beast(0.25))
    assert (await _activate(client, cid, forma)).status_code == 200
    assert (await _full(client, cid))["temp_hp"] == atteso


@pytest.mark.caccia(id="CB-349", fonte="2014 · Druido · Forma Selvatica da Combattimento · pag. 69", zona="flusso:compagni-forme", voce="ripetizione",
                    copre=["POST /characters/{char_id}/companions/{comp_id}/wild-heal",
                           "carta:2014/classes/druid.md#Forma Selvatica da Combattimento / Combat Wild Shape (Circolo della Luna 2, pag. 69)"])
async def test_due_cure_insieme_spendono_un_solo_slot(client, dadi):
    cid = await _druid(client, 4, "moon")
    forma = await _form(client, cid, _beast(1), hp=30)
    await _activate(client, cid, forma)
    await _nuovo_turno(client, cid)
    await client.patch(f"/characters/{cid}/companions/{forma}/hp", json={"op": "damage", "value": 20})
    dadi(5, 5, 5, 5)
    rs = await asyncio.gather(*[client.post(f"/characters/{cid}/companions/{forma}/wild-heal", json={"slot_level": 2}) for _ in range(2)])
    assert sorted(r.status_code for r in rs) == [200, 409]
    assert next(s for s in (await _full(client, cid))["spell_slots"] if s["level"] == 2)["used"] == 1
    assert next(c for c in await _lista(client, cid) if c["id"] == forma)["current_hp"] == 20


@pytest.mark.caccia(id="CB-350", fonte="2024 · Druido · Circolo della Luna: nessuna Forma Selvatica da Combattimento (solo nel 2014)", zona="flusso:compagni-forme",
                    voce="edizioni", copre=["POST /characters/{char_id}/companions/{comp_id}/wild-heal"])
async def test_la_cura_in_forma_con_uno_slot_non_esiste_nel_2024(client):
    cid = await _circle(client, "moon", level=5)
    forma = await _form(client, cid, _beast(1), hp=30)
    await _activate(client, cid, forma)
    await _nuovo_turno(client, cid)
    await client.patch(f"/characters/{cid}/companions/{forma}/hp", json={"op": "set_temp", "value": 0})
    r = await client.post(f"/characters/{cid}/companions/{forma}/wild-heal", json={"slot_level": 1})
    assert r.status_code == 409
    assert next(s for s in (await _full(client, cid))["spell_slots"] if s["level"] == 1)["used"] == 0


@pytest.mark.caccia(id="CB-351", fonte="2014 e 2024 · Druido · Forma Selvatica · usi e ricarica (pag. 66 e 80)", zona="flusso:compagni-forme", voce="edizioni",
                    copre=["POST /characters/{char_id}/rest", "carta:2014/classes/druid.md#Forma Selvatica / Wild Shape (Druido 2, pag. 66)", "carta:2024/classes/druid.md#Forma Selvatica / Wild Shape (Druido 2, pag. 80)"])
@pytest.mark.parametrize("edizione, dopo_breve", [("2014", 2), ("2024", 1)])
async def test_il_riposo_breve_ridona_gli_usi_della_forma_per_edizione(client, edizione, dopo_breve):
    cid = await (_druid(client, 4) if edizione == "2014" else _druid24(client, 4))
    for _ in range(2):
        forma = await _form(client, cid, _beast(0.25))
        assert (await _activate(client, cid, forma)).status_code == 200
        await _nuovo_turno(client, cid)
    assert await _usi(client, cid) == 0
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "short", "confirm_early": True})).status_code == 200
    assert await _usi(client, cid) == dopo_breve


@pytest.mark.caccia(id="CB-352", fonte="invariante: una richiesta ripetuta non spende due volte l'uso di Forma Selvatica", zona="flusso:compagni-forme",
                    voce="ripetizione", copre=["POST /characters/{char_id}/companions/{comp_id}/activate"])
async def test_due_attivazioni_insieme_spendono_un_solo_uso(client):
    cid = await _druid(client, 4)
    forma = await _form(client, cid, _beast(0.25))
    rs = await asyncio.gather(_activate(client, cid, forma), _activate(client, cid, forma))
    assert [r.status_code for r in rs] == [200, 200]
    assert await _usi(client, cid) == 1


@pytest.mark.caccia(id="CB-353", fonte="invariante: export e import conservano la forma attiva e il suo stato", zona="flusso:compagni-forme",
                    voce="persistenza", copre=["GET /characters/{char_id}/export", "POST /characters/import"])
async def test_la_forma_attiva_sopravvive_a_export_e_import(client):
    cid = await _druid(client, 4)
    forma = await _form(client, cid, _beast(0.25))
    await _activate(client, cid, forma)
    nuovo = (await client.post("/characters/import", json=(await client.get(f"/characters/{cid}/export")).json())).json()["id"]
    assert [c["is_active"] for c in await _lista(client, nuovo)] == [True]
    assert (await _full(client, nuovo))["active_form"] is not None


@pytest.mark.caccia(id="CB-354", fonte="2024 · Ranger · Compagno Primordiale · pag. 122 (svanisce se muori)", zona="flusso:compagni-forme", voce="persistenza",
                    copre=["PATCH /characters/{char_id}/death_saves",
                           "carta:2024/classes/ranger.md#Compagno Primordiale / Primal Companion (Signore delle Bestie 3, pag. 122)"])
async def test_la_bestia_primordiale_svanisce_con_la_morte_del_ranger(client):
    cid = await _sub(client, 5, "beast_master")
    await _bestia24(client, cid, "land")
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 0})
    for _ in range(3):
        await client.patch(f"/characters/{cid}/death_saves", json={"action": "failure"})
    assert (await _full(client, cid))["is_dead"] is True
    assert await _lista(client, cid) == []


@pytest.mark.caccia(id="CB-355", fonte="2014 · Ranger · Compagno del Ranger: la bestia spende Dadi Vita nei riposi brevi; dado + COS, mai sotto 0",
                    zona="flusso:compagni-forme", voce="limiti", copre=["POST /characters/{char_id}/companions/{comp_id}/hit-dice"])
async def test_dadi_vita_della_bestia_con_costituzione_bassa(client, dadi):
    cid, bestia = await _bestia14(client, 5)
    sb = {"hit_dice": "3d8", "abilities": {"con": 3}, "actions": [{"name": "Morso", "attack_bonus": 4, "damage_dice": "1d6+2", "damage_type": "piercing"}]}
    await client.patch(f"/characters/{cid}/companions/{bestia}", json={"statblock": sb})
    await client.patch(f"/characters/{cid}/companions/{bestia}/hp", json={"op": "damage", "value": 15})  # 20 -> 5 PF
    dadi(2, 8)  # COS 3 = -4: il 2 cura 0, l'8 cura 4
    r = await client.post(f"/characters/{cid}/companions/{bestia}/hit-dice", json={"count": 2})
    assert r.status_code == 200
    assert (r.json()["rolls"], r.json()["healed"], r.json()["hit_dice_left"], r.json()["companion"]["current_hp"]) == ([2, 8], 4, 1, 9)
    assert (await client.post(f"/characters/{cid}/companions/{bestia}/hit-dice", json={"count": 2})).status_code == 409


@pytest.mark.caccia(id="CB-356", fonte="2014 · Regole generali · tiro per colpire: 20 naturale raddoppia i dadi di danno, non il bonus fisso",
                    zona="flusso:compagni-forme", voce="limiti", copre=["POST /characters/{char_id}/companions/{comp_id}/attack"])
async def test_il_critico_della_bestia_raddoppia_i_dadi_e_non_il_fisso(client):
    cid, bestia = await _bestia14(client, 5)  # competenza +3: morso 1d6+2, +4 al colpire
    assert (await _order(client, cid, bestia, "attack")).status_code == 200
    r = await _bite(client, cid, bestia, dice=[20], damage_rolls=[3, 4])
    assert r.status_code == 200
    j = r.json()
    assert (j["is_critical"], j["to_hit_total"], j["damage_total"]) == (True, 27, 12)  # 3+4 dadi, +2 scheda, +3 competenza


@pytest.mark.caccia(id="CB-357", fonte="2014 · Regole generali · tiro per colpire: 1 naturale manca sempre, nessun danno", zona="flusso:compagni-forme",
                    voce="limiti", copre=["POST /characters/{char_id}/companions/{comp_id}/attack"])
async def test_il_fallimento_naturale_della_bestia_non_fa_danno(client):
    cid, bestia = await _bestia14(client, 5)
    assert (await _order(client, cid, bestia, "attack")).status_code == 200
    r = await _bite(client, cid, bestia, dice=[1], damage_rolls=[6])
    assert r.status_code == 200 and r.json()["damage_total"] == 0 and r.json()["is_critical"] is False


@pytest.mark.caccia(id="CB-358", fonte="invariante: i compagni di un altro personaggio non si leggono né si toccano", zona="flusso:compagni-forme",
                    voce="permessi", copre=["GET /characters/{char_id}/companions", "PATCH /characters/{char_id}/companions/{comp_id}",
                                           "DELETE /characters/{char_id}/companions/{comp_id}", "POST /characters/{char_id}/companions/{comp_id}/activate",
                                           "PATCH /characters/{char_id}/companions/{comp_id}/hp"])
@pytest.mark.parametrize("metodo, suffisso, corpo", [
    ("get", "", None), ("patch", "/{comp}", {"name": "Altro"}), ("delete", "/{comp}", None),
    ("post", "/{comp}/activate", {}), ("patch", "/{comp}/hp", {"op": "damage", "value": 3}),
])
async def test_i_compagni_di_un_altro_utente_sono_protetti(client, come_utente, metodo, suffisso, corpo):
    come_utente(1)
    cid = await _druid(client, 4)
    forma = await _form(client, cid, _beast(0.25))
    come_utente(2)
    mio = await _druid(client, 4)
    kw = {} if corpo is None else {"json": corpo}
    assert (await getattr(client, metodo)(f"/characters/{cid}/companions" + suffisso.format(comp=forma), **kw)).status_code in (403, 404)
    if "{comp}" in suffisso:  # il mio personaggio con l'id di un compagno altrui
        assert (await getattr(client, metodo)(f"/characters/{mio}/companions" + suffisso.format(comp=forma), **kw)).status_code == 404
    come_utente(1)
    mia = next(c for c in await _lista(client, cid) if c["id"] == forma)
    assert (mia["name"], mia["current_hp"], mia["is_active"]) == ("Bestia", 10, False)


# ---------------------------------------------------------------------------
# Interazione con il resto della scheda e contratto
# ---------------------------------------------------------------------------

async def _concentra(client, cid) -> int:
    spell = await client.post(f"/characters/{cid}/spells", json={"name": "Benedizione", "level": 1, "is_concentration": True, "is_prepared": True})
    assert (await client.post(f"/characters/{cid}/spells/{spell.json()['id']}/use", json={"slot_level": 1})).status_code == 200
    await _nuovo_turno(client, cid)
    return spell.json()["id"]


@pytest.mark.caccia(id="CB-365", fonte="2014 · Druido · Forma Selvatica · pag. 66; 2024 · Regole della Forma Selvatica · pag. 81 (la trasformazione non spezza la Concentrazione)",
                    zona="flusso:compagni-forme", voce="interazione", copre=["POST /characters/{char_id}/companions/{comp_id}/activate", "POST /characters/{char_id}/spells/{spell_id}/use"])
@pytest.mark.parametrize("edizione", ["2014", "2024"])
async def test_entrare_in_forma_mantiene_la_concentrazione(client, edizione):
    cid = await (_druid(client, 4) if edizione == "2014" else _druid24(client, 4))
    incantesimo = await _concentra(client, cid)
    forma = await _form(client, cid, _beast(0.25))
    assert (await _activate(client, cid, forma)).status_code == 200
    assert (await _full(client, cid))["concentrating_spell_id"] == incantesimo


@pytest.mark.caccia(id="CB-366", fonte="2014 · Forma Selvatica · pag. 66 (si assumono FOR, DES, COS della bestia); 2024 · Regole della Forma Selvatica · pag. 81 (vale il modificatore più alto fra druido e bestia)",
                    zona="flusso:compagni-forme", voce="interazione", copre=["POST /characters/{char_id}/skills/{skill_name}/roll", "POST /characters/{char_id}/saving_throws/{ability}/roll",
                                                                            "POST /characters/{char_id}/companions/{comp_id}/activate"])
@pytest.mark.parametrize("edizione, prova_forza, ts_costituzione", [("2014", 0, 3), ("2024", 4, 3)])
async def test_i_punteggi_fisici_della_forma_sulle_prove_e_i_ts(client, edizione, prova_forza, ts_costituzione):
    cid = await (_druid(client, 4, strength=18, constitution=8) if edizione == "2014" else _druid24(client, 4, strength=18, constitution=8))
    bestia = {**_beast(0.25), "abilities": {"str": 10, "dex": 10, "con": 16, "int": 3, "wis": 12, "cha": 6}}
    assert (await _activate(client, cid, await _form(client, cid, bestia))).status_code == 200
    prova = (await client.post(f"/characters/{cid}/skills/athletics/roll", json={})).json()["bonus"]
    ts = (await client.post(f"/characters/{cid}/saving_throws/constitution/roll", json={})).json()["bonus"]
    assert (prova, ts) == (prova_forza, ts_costituzione)


@pytest.mark.caccia(id="CB-367", fonte="2024 · Regole della Forma Selvatica · pag. 81 (i PF sono quelli del druido, con i temporanei); regole generali: a 0 PF si perde la concentrazione",
                    zona="flusso:compagni-forme", voce="interazione", copre=["PATCH /characters/{char_id}/hp", "GET /characters/{char_id}/companions"])
async def test_il_danno_che_azzera_il_druido_in_forma_2024_chiude_forma_e_concentrazione(client):
    cid = await _druid24(client, 4)
    await _concentra(client, cid)
    forma = await _form(client, cid, _beast(0.25))
    await _activate(client, cid, forma)
    pg = await _full(client, cid)
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": pg["current_hit_points"] + pg["temp_hp"]})).status_code == 200
    pg = await _full(client, cid)
    assert (pg["current_hit_points"], pg["active_form"], pg["concentrating_spell_id"]) == (0, None, None)
    assert [c["is_active"] for c in await _lista(client, cid)] == [False]


@pytest.mark.caccia(id="CB-368", fonte="2014 · Forma Selvatica · pag. 66 (il danno in eccesso passa alla forma normale); CLAUDE.md · Wild shape: damage beyond the form's HP carries over",
                    zona="flusso:compagni-forme", voce="interazione", copre=["PATCH /characters/{char_id}/hp", "GET /characters/{char_id}"])
async def test_il_danno_oltre_la_forma_2014_porta_il_druido_a_zero_e_spezza_la_concentrazione(client):
    cid = await _druid(client, 4)
    await _concentra(client, cid)
    forma = await _form(client, cid, _beast(0.25), hp=10)
    await _activate(client, cid, forma)
    await _nuovo_turno(client, cid)
    pf = (await _full(client, cid))["current_hit_points"]
    assert (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10 + pf})).status_code == 200
    pg = await _full(client, cid)
    assert (pg["current_hit_points"], pg["active_form"], pg["concentrating_spell_id"]) == (0, None, None)


CAMPI_COMPAGNO = {"id": int, "character_id": int, "kind": str, "name": str, "statblock": dict, "max_hp": int, "current_hp": int, "temp_hp": int,
                  "armor_class": int, "is_active": bool, "created_at": str, "attack_bonus_extra": int, "damage_bonus_extra": int,
                  "fly_or_swim_m": int, "damage_type_options": list, "can_resist": bool, "down": bool}


def _forma_letta_dal_frontend(c: dict) -> None:
    for campo, tipo in CAMPI_COMPAGNO.items():
        assert campo in c and isinstance(c[campo], tipo) and not (tipo is int and isinstance(c[campo], bool)), (campo, c.get(campo))
    for campo in ("notes", "feature_key", "save_dc", "concentration_save"):  # letti dal frontend, ammessi null o assenti
        assert c.get(campo) is None or campo in ("notes", "feature_key", "save_dc"), campo


@pytest.mark.caccia(id="CB-369", fonte="invariante: la risposta ha tutti i campi che Extras e CompanionCard leggono, anche con statblock vuoto e senza azioni",
                    zona="flusso:compagni-forme", voce="contratto",
                    copre=["GET /characters/{char_id}/companions", "POST /characters/{char_id}/companions", "POST /characters/{char_id}/companions/{comp_id}/activate",
                           "POST /characters/{char_id}/companions/{comp_id}/deactivate"])
async def test_le_risposte_dei_compagni_hanno_i_campi_letti_dal_frontend(client):
    cid = await _druid(client, 4)
    vuoto = await client.post(f"/characters/{cid}/companions", json={"kind": "familiar", "name": "Vuoto", "statblock": {}})
    assert vuoto.status_code == 201
    senza_azioni = await client.post(f"/characters/{cid}/companions", json={"kind": "mount", "name": "Senza azioni", "statblock": {"actions": [], "traits": []}, "max_hp": 0})
    forma = await client.post(f"/characters/{cid}/companions", json={"kind": "wild_shape", "name": "Lupo", "statblock": {"type": "beast", "challenge_rating": 0.25}, "max_hp": 5, "notes": None})
    risposte = [vuoto.json(), senza_azioni.json(), forma.json()]
    attivata = await _activate(client, cid, forma.json()["id"])
    assert attivata.status_code == 200
    risposte.append(attivata.json())
    await _nuovo_turno(client, cid)
    disattivata = await client.post(f"/characters/{cid}/companions/{forma.json()['id']}/deactivate")
    assert disattivata.status_code == 200
    risposte += [disattivata.json(), *await _lista(client, cid)]
    for c in risposte:
        _forma_letta_dal_frontend(c)
    pg = await _full(client, cid)  # campi che Extras legge dalla scheda
    assert all("feature_key" in a and "uses" in a and "max_uses" in a for a in pg["abilities"])
    assert all("level" in s and "available" in s for s in pg["spell_slots"])
    assert all("class_name" in c and "level" in c and "subclass_key" in c for c in pg["classes"]) and "rules_edition" in pg


@pytest.mark.caccia(id="CB-370", fonte="2014 · Druido · Forma Selvatica · pag. 66", zona="flusso:compagni-forme", voce="limiti",
                    copre=["PATCH /characters/{char_id}/companions/{comp_id}", "carta:2014/classes/druid.md#Forma Selvatica / Wild Shape (Druido 2, pag. 66)"])
async def test_attivare_con_patch_rispetta_gs_usi_e_azione(client):
    cid = await _druid(client, 4)
    forma = await _form(client, cid, _beast(2.0), hp=10)
    assert (await _activate(client, cid, forma)).status_code == 409
    r = await client.patch(f"/characters/{cid}/companions/{forma}", json={"is_active": True})
    usi = await _usi(client, cid)
    azione = (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]
    assert r.status_code in (409, 422) or (usi < 2 and (azione["action_used"] or azione["bonus_used"]))
    nata = await client.post(f"/characters/{cid}/companions", json={  # stessa regola per una forma creata già attiva
        "kind": "wild_shape", "name": "Subito attiva", "max_hp": 10, "statblock": _beast(2.0), "is_active": True})
    assert nata.status_code in (409, 422), nata.text


@pytest.mark.caccia(id="CB-371", fonte="2024 · Druido · Regole della Forma Selvatica · pag. 81", zona="flusso:compagni-forme", voce="edizioni",
                    copre=["PATCH /characters/{char_id}/companions/{comp_id}/hp", "carta:2024/classes/druid.md#Regole della Forma Selvatica / Rules While Shape-Shifted (Druido 2, pag. 81)"])
async def test_il_danno_alla_forma_2024_va_ai_pf_del_druido(client):
    cid = await _druid24(client, 4)
    forma = await _form(client, cid, _beast(0.25))
    await _activate(client, cid, forma)
    prima = await _full(client, cid)
    r = await client.patch(f"/characters/{cid}/companions/{forma}/hp", json={"op": "damage", "value": 7})
    dopo = await _full(client, cid)
    assert r.status_code in (409, 422) or (dopo["temp_hp"], dopo["current_hit_points"]) == (prima["temp_hp"] - 4, prima["current_hit_points"] - 3)


@pytest.mark.caccia(id="CB-372", fonte="invariante: un compagno a 0 PF non attacca (la bestia del ranger risponde 409 companion_down)", zona="flusso:compagni-forme",
                    voce="limiti", copre=["POST /characters/{char_id}/companions/{comp_id}/attack"])
async def test_un_compagno_a_zero_pf_non_attacca(client):
    cid = await _druid(client, 4)
    sb = {"actions": [{"name": "Morso", "attack_bonus": 4, "damage_dice": "1d4", "damage_type": "piercing"}]}
    fam = (await client.post(f"/characters/{cid}/companions", json={"kind": "familiar", "name": "Gufo", "statblock": sb, "max_hp": 5})).json()["id"]
    assert (await client.patch(f"/characters/{cid}/companions/{fam}/hp", json={"op": "damage", "value": 5})).json()["down"] is True
    r = await client.post(f"/characters/{cid}/companions/{fam}/attack", json={"action_index": 0, "dice": [10], "damage_rolls": [2]})
    assert r.status_code == 409


@pytest.mark.caccia(id="CB-373", fonte="2014 · Druido · Forma Selvatica · pag. 66 (2 usi, azione, PF propri della bestia, ritorno con azione bonus, i PF del druido restano)",
                    zona="flusso:compagni-forme", voce="normale",
                    copre=["POST /characters/{char_id}/companions", "POST /characters/{char_id}/companions/{comp_id}/activate",
                           "PATCH /characters/{char_id}/companions/{comp_id}/hp", "POST /characters/{char_id}/companions/{comp_id}/deactivate",
                           "GET /characters/{char_id}/companions", "carta:2014/classes/druid.md#Forma Selvatica / Wild Shape (Druido 2, pag. 66)"])
async def test_percorso_comune_della_forma_selvatica_2014(client):
    cid = await _druid(client, 2)
    pf_druido = (await _full(client, cid))["current_hit_points"]
    forma = await _form(client, cid, _beast(0.25), hp=11)
    assert await _usi(client, cid) == 2
    r = await _activate(client, cid, forma)
    assert r.status_code == 200 and (r.json()["is_active"], r.json()["current_hp"]) == (True, 11)
    assert await _usi(client, cid) == 1
    assert (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]["action_used"] is True
    r = await client.patch(f"/characters/{cid}/companions/{forma}/hp", json={"op": "damage", "value": 4})
    assert r.status_code == 200 and r.json()["current_hp"] == 7
    pg = await _full(client, cid)
    assert pg["current_hit_points"] == pf_druido and pg["active_form"]["current_hp"] == 7
    assert (await client.post(f"/characters/{cid}/companions/{forma}/deactivate")).status_code == 200
    scheda = next(c for c in await _lista(client, cid) if c["id"] == forma)
    assert (scheda["is_active"], scheda["current_hp"]) == (False, 7)
    pg = await _full(client, cid)
    assert pg["current_hit_points"] == pf_druido and pg["active_form"] is None and await _usi(client, cid) == 1


@pytest.mark.caccia(id="CB-762", fonte="2024 · Druido · Regole della Forma Selvatica · pag. 81 (i PF restano quelli del druido)", zona="flusso:compagni-forme",
                    voce="edizioni", copre=["PATCH /characters/{char_id}/companions/{comp_id}/hp"])
async def test_cura_e_pf_temporanei_alla_forma_2024_vanno_al_druido(client):
    cid = await _druid24(client, 4)
    forma = await _form(client, cid, _beast(0.25))
    await _activate(client, cid, forma)
    await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10})
    prima = await _full(client, cid)
    assert (await client.patch(f"/characters/{cid}/companions/{forma}/hp", json={"op": "heal", "value": 3})).status_code == 200
    assert (await client.patch(f"/characters/{cid}/companions/{forma}/hp", json={"op": "set_temp", "value": 9})).status_code == 200
    dopo = await _full(client, cid)
    assert (dopo["current_hit_points"], dopo["temp_hp"]) == (prima["current_hit_points"] + 3, 9)


@pytest.mark.caccia(id="CB-763", fonte="invariante: l'ordine dato a una bestia sparisce con lei", zona="flusso:compagni-forme", voce="annullamento",
                    copre=["PATCH /characters/{char_id}/hp"])
async def test_la_bestia_che_svanisce_con_il_ranger_porta_via_l_ordine(client, test_session_factory):
    from api.services.beast_companion import drop_primal_beast
    from core.db.models import Character, Companion
    from core.rules.companions import PRIMAL_COMPANION

    cid = await _druid24(client, 4)
    async with test_session_factory() as s:
        comp = Companion(character_id=cid, kind="companion", name="B", feature_key=PRIMAL_COMPANION, max_hp=5, current_hp=5,
                         statblock={}, created_at="2026-01-01T00:00:00")
        s.add(comp)
        await s.flush()
        char = await s.get(Character, cid)
        char.turn_state = {**(char.turn_state or {}), "beast": {"id": comp.id, "attacks_left": 1}}
        await drop_primal_beast(s, char)
        assert not (char.turn_state or {}).get("beast")
        char.turn_state = {**char.turn_state, "beast": {"id": comp.id + 100, "attacks_left": 1}}  # un'altra bestia tiene il suo
        await drop_primal_beast(s, char)
        assert char.turn_state["beast"]["id"] == comp.id + 100


# ---------------------------------------------------------------------------
# Giro 2: bestie di privilegio, riposi, import/export, permessi, contratto
# ---------------------------------------------------------------------------

PRIMORDIALE = "ranger.primal_companion"
BESTIA_2014 = "ranger.rangers_companion"


async def _primordiale(client, cid):
    return await client.post(f"/characters/{cid}/companions", json={
        "kind": "companion", "name": "Bestia", "feature_key": PRIMORDIALE, "max_hp": 5, "statblock": {}})


@pytest.mark.caccia(id="CB-1073", fonte="2024 · Ranger · Signore delle Bestie · Compagno Primordiale · pag. 122 (privilegio della sottoclasse; come per il compagno 2014 il server rifiuta chi non lo ha)",
                    zona="flusso:compagni-forme", voce="regola", copre=["POST /characters/{char_id}/companions", "carta:2024/classes/ranger.md#Compagno Primordiale / Primal Companion (Signore delle Bestie 3, pag. 122)"])
async def test_la_bestia_primordiale_non_si_crea_senza_il_privilegio(client):
    from tests.integration.rules.test_2024_ranger import _ranger24
    cid = await _ranger24(client, 5)  # ranger 2024 senza Signore delle Bestie
    r = await _primordiale(client, cid)
    assert r.status_code == 422
    assert await _lista(client, cid) == []


@pytest.mark.caccia(id="CB-1074", fonte="2024 · Ranger · Signore delle Bestie · Compagno Primordiale · pag. 122 (una sola bestia alla volta)",
                    zona="flusso:compagni-forme", voce="limiti", copre=["POST /characters/{char_id}/companions", "carta:2024/classes/ranger.md#Compagno Primordiale / Primal Companion (Signore delle Bestie 3, pag. 122)"])
async def test_la_bestia_primordiale_e_una_sola_alla_volta(client):
    cid = await _sub(client, 5, "beast_master")
    await _bestia24(client, cid, "land")
    r = await _primordiale(client, cid)
    assert r.status_code == 422
    assert sum(c["feature_key"] == PRIMORDIALE for c in await _lista(client, cid)) == 1


@pytest.mark.caccia(id="CB-1075", fonte="2014 · Druido · Forma Selvatica · pag. 66 (si torna normali prima del tempo con un'azione bonus)",
                    zona="flusso:compagni-forme", voce="annullamento",
                    copre=["PATCH /characters/{char_id}/companions/{comp_id}", "POST /characters/{char_id}/turn/use", "carta:2014/classes/druid.md#Forma Selvatica / Wild Shape (Druido 2, pag. 66)"])
async def test_terminare_la_forma_con_patch_costa_l_azione_bonus(client):
    cid = await _druid(client, 4)
    forma = await _form(client, cid, _beast(0.25))
    assert (await _activate(client, cid, forma)).status_code == 200
    assert (await client.post(f"/characters/{cid}/turn/use", json={"slot": "bonus", "used": True})).status_code == 200
    r = await client.patch(f"/characters/{cid}/companions/{forma}", json={"is_active": False})
    assert r.status_code == 409  # come POST /deactivate con l'azione bonus già spesa
    assert (await _full(client, cid))["active_form"] is not None


@pytest.mark.xfail(strict=True, reason="CB-1076: l'import accetta un compagno con nome di soli spazi")
@pytest.mark.caccia(id="CB-1076", fonte="invariante: un nome di soli spazi è un nome vuoto (CB-341, CB-342): anche un file importato non lo introduce",
                    zona="flusso:compagni-forme", voce="persistenza", copre=["POST /characters/import", "GET /characters/{char_id}/export"])
async def test_l_import_rifiuta_un_compagno_senza_nome(client):
    cid = await _druid(client, 4)
    await _form(client, cid, _beast(0.25))
    file = (await client.get(f"/characters/{cid}/export")).json()
    file["companions"][0]["name"] = "   "
    r = await client.post("/characters/import", json=file)
    assert r.status_code == 422


@pytest.mark.caccia(id="CB-1077", fonte="invariante: export e import conservano la bestia del ranger con PF, temporanei e Dadi Vita spesi",
                    zona="flusso:compagni-forme", voce="persistenza",
                    copre=["GET /characters/{char_id}/export", "POST /characters/import", "POST /characters/{char_id}/companions/{comp_id}/hit-dice"])
async def test_export_e_import_conservano_la_bestia_del_ranger(client, dadi):
    cid, bestia = await _bestia14(client, 5)
    await client.patch(f"/characters/{cid}/companions/{bestia}/hp", json={"op": "damage", "value": 12})  # 20 -> 8
    dadi(3)
    assert (await client.post(f"/characters/{cid}/companions/{bestia}/hit-dice", json={"count": 1})).status_code == 200  # 8 + 3 = 11
    await client.patch(f"/characters/{cid}/companions/{bestia}/hp", json={"op": "set_temp", "value": 5})
    prima = (await _lista(client, cid))[0]
    nuovo = (await client.post("/characters/import", json=(await client.get(f"/characters/{cid}/export")).json())).json()["id"]
    dopo = (await _lista(client, nuovo))[0]
    chiavi = lambda c: (c["feature_key"], c["max_hp"], c["current_hp"], c["temp_hp"], c["statblock"]["hit_dice"], c["statblock"]["hit_dice_spent"])  # noqa: E731
    assert chiavi(dopo) == chiavi(prima) == (BESTIA_2014, 20, 11, 5, "3d8", 1)


@pytest.mark.caccia(id="CB-1078", fonte="2014 · Regole generali · Riposo Lungo · pag. 186 (tutti i PF, Dadi Vita spesi fino a metà del totale, minimo uno)",
                    zona="flusso:compagni-forme", voce="persistenza",
                    copre=["POST /characters/{char_id}/rest", "POST /characters/{char_id}/companions/{comp_id}/hit-dice", "carta:2014/general.md#Riposo Lungo / Long Rest (pag. 186)"])
@pytest.mark.parametrize("totale, restano_spesi", [(1, 0), (3, 2), (4, 2), (5, 3)])
async def test_il_riposo_lungo_ridona_alla_bestia_pf_e_meta_dei_dadi_vita(client, dadi, totale, restano_spesi):
    cid, bestia = await _bestia14(client, 5)
    sb = {"hit_dice": f"{totale}d8", "abilities": {"con": 10}, "actions": []}
    await client.patch(f"/characters/{cid}/companions/{bestia}", json={"statblock": sb})
    for _ in range(totale):  # li spende tutti
        await client.patch(f"/characters/{cid}/companions/{bestia}/hp", json={"op": "damage", "value": 6})
        dadi(8)
        assert (await client.post(f"/characters/{cid}/companions/{bestia}/hit-dice", json={"count": 1})).status_code == 200
    await client.patch(f"/characters/{cid}/companions/{bestia}/hp", json={"op": "damage", "value": 6})
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})).status_code == 200
    c = (await _lista(client, cid))[0]
    assert (c["current_hp"], c["statblock"]["hit_dice_spent"]) == (20, restano_spesi)


PERMESSI = [  # tipo di compagno, metodo, suffisso, corpo
    ("forma", "post", "/{comp}/deactivate", None), ("forma", "post", "/{comp}/wild-heal", {"slot_level": 1}),
    ("bestia", "post", "/{comp}/hit-dice", {"count": 1}), ("bestia", "post", "/{comp}/command", {"command": "dodge", "bonus": False}),
    ("bestia", "post", "/{comp}/attack", {"action_index": 0, "mode": "normal", "dice": [10]}),
    ("bestia", "post", "", {"kind": "familiar", "name": "Intruso", "statblock": {}, "max_hp": 1}),
]


@pytest.mark.caccia(id="CB-1079", fonte="invariante: i compagni di un altro personaggio non si toccano, nemmeno con ordini, Dadi Vita, attacchi o cure della forma",
                    zona="flusso:compagni-forme", voce="permessi",
                    copre=["POST /characters/{char_id}/companions/{comp_id}/deactivate", "POST /characters/{char_id}/companions/{comp_id}/wild-heal",
                           "POST /characters/{char_id}/companions/{comp_id}/hit-dice", "POST /characters/{char_id}/companions/{comp_id}/command",
                           "POST /characters/{char_id}/companions/{comp_id}/attack", "POST /characters/{char_id}/companions"])
@pytest.mark.parametrize("tipo, metodo, suffisso, corpo", PERMESSI)
async def test_gli_altri_endpoint_dei_compagni_rifiutano_un_altro_utente(client, come_utente, tipo, metodo, suffisso, corpo):
    come_utente(1)
    if tipo == "forma":
        cid = await _druid(client, 4)
        comp = await _form(client, cid, _beast(0.25))
    else:
        cid, comp = await _bestia14(client, 3)
    prima = (await _lista(client, cid), (await client.get(f"/characters/{cid}/turn-state")).json()["turn"])
    come_utente(2)
    mio = await _druid(client, 4)
    kw = {} if corpo is None else {"json": corpo}
    assert (await getattr(client, metodo)(f"/characters/{cid}/companions" + suffisso.format(comp=comp), **kw)).status_code in (403, 404)
    if "{comp}" in suffisso:  # il mio personaggio con l'id di un compagno altrui
        assert (await getattr(client, metodo)(f"/characters/{mio}/companions" + suffisso.format(comp=comp), **kw)).status_code == 404
    come_utente(1)
    assert (await _lista(client, cid), (await client.get(f"/characters/{cid}/turn-state")).json()["turn"]) == prima


@pytest.mark.caccia(id="CB-1080", fonte="invariante: le richieste che CompanionForm e CompanionCard mandano (client.ts) sono accettate dall'API, anche con note nulle e opzioni vuote",
                    zona="flusso:compagni-forme", voce="contratto",
                    copre=["POST /characters/{char_id}/companions", "PATCH /characters/{char_id}/companions/{comp_id}", "PATCH /characters/{char_id}/companions/{comp_id}/hp",
                           "POST /characters/{char_id}/companions/{comp_id}/attack", "POST /characters/{char_id}/companions/{comp_id}/command",
                           "POST /characters/{char_id}/companions/{comp_id}/hit-dice", "POST /characters/{char_id}/companions/{comp_id}/activate",
                           "POST /characters/{char_id}/companions/{comp_id}/deactivate"])
async def test_le_richieste_del_frontend_sono_accettate(client):
    cid, bestia = await _bestia14(client, 5)
    base = f"/characters/{cid}/companions"
    r = await client.post(base, json={"kind": "familiar", "name": "Gufo", "max_hp": 4, "armor_class": 11, "notes": None, "spell_school": None,
                                      "statblock": {"actions": [{"name": "Artigli", "attack_bonus": 3, "damage_dice": "1d4+1"}]}})
    assert r.status_code == 201, r.text
    gufo = r.json()["id"]
    assert (await client.patch(f"{base}/{gufo}", json={"name": "Gufetto", "notes": "x"})).status_code == 200
    assert (await client.patch(f"{base}/{gufo}/hp", json={"op": "damage", "value": 1})).status_code == 200
    r = await client.post(f"{base}/{gufo}/attack", json={"action_index": 0, "mode": "normal", "dice": [12], "options": [], "option_inputs": {}})
    assert r.status_code == 200, r.text
    assert (await client.post(f"{base}/{bestia}/command", json={"command": "attack", "bonus": False})).status_code == 200
    r = await client.post(f"{base}/{bestia}/attack", json={"action_index": 0, "mode": "normal", "dice": [12], "options": [], "option_inputs": {}, "reaction": True})
    assert r.status_code == 200, r.text
    r = await client.post(f"{base}/{bestia}/hit-dice", json={"count": 1})  # PF pieni: 409, non 422
    assert r.status_code == 409 and r.json()["detail"]["code"] == "hp_full"
    druido = await _druid(client, 4)
    forma = await _form(client, druido, _beast(0.25))
    assert (await client.post(f"/characters/{druido}/companions/{forma}/activate", json={"force": False})).status_code == 200
    await _nuovo_turno(client, druido)
    assert (await client.post(f"/characters/{druido}/companions/{forma}/deactivate")).status_code == 200


@pytest.mark.caccia(id="CB-1081", fonte="2014 · Druido · Forma Selvatica · pag. 66 (finisce se privo di sensi); 2024 · Druido · Forma Selvatica · pag. 80 (finisce se Incapacitato)",
                    zona="flusso:compagni-forme", voce="edizioni",
                    copre=["PATCH /characters/{char_id}/conditions", "carta:2014/classes/druid.md#Forma Selvatica / Wild Shape (Druido 2, pag. 66)", "carta:2024/classes/druid.md#Forma Selvatica / Wild Shape (Druido 2, pag. 80)"])
@pytest.mark.parametrize("edizione, condizione, finisce", [
    ("2024", "incapacitated", True), ("2024", "stunned", True), ("2024", "unconscious", True),
    ("2014", "incapacitated", False), ("2014", "stunned", False), ("2014", "unconscious", True)])
async def test_la_forma_finisce_con_la_condizione_giusta_per_edizione(client, edizione, condizione, finisce):
    cid = await (_druid24(client, 4) if edizione == "2024" else _druid(client, 4))
    forma = await _form(client, cid, _beast(0.25))
    assert (await _activate(client, cid, forma)).status_code == 200
    assert (await client.patch(f"/characters/{cid}/conditions", json={"conditions": {condizione: True}})).status_code == 200
    assert ((await _full(client, cid))["active_form"] is not None) is (not finisce)
    assert next(c for c in await _lista(client, cid) if c["id"] == forma)["is_active"] is (not finisce)


@pytest.mark.caccia(id="CB-1082", fonte="invariante: due richieste uguali insieme spendono un solo Dado Vita della bestia",
                    zona="flusso:compagni-forme", voce="ripetizione", copre=["POST /characters/{char_id}/companions/{comp_id}/hit-dice"])
async def test_due_richieste_di_dadi_vita_insieme_ne_spendono_uno(client, dadi):
    cid, bestia = await _bestia14(client, 5)
    sb = {"hit_dice": "1d8", "abilities": {"con": 10}, "actions": []}
    await client.patch(f"/characters/{cid}/companions/{bestia}", json={"statblock": sb})
    await client.patch(f"/characters/{cid}/companions/{bestia}/hp", json={"op": "damage", "value": 15})  # 20 -> 5
    dadi(5)
    rs = await asyncio.gather(*[client.post(f"/characters/{cid}/companions/{bestia}/hit-dice", json={"count": 1}) for _ in range(2)])
    assert sorted(r.status_code for r in rs) == [200, 409]
    c = (await _lista(client, cid))[0]
    assert (c["current_hp"], c["statblock"]["hit_dice_spent"]) == (10, 1)


@pytest.mark.caccia(id="CB-1083", fonte="2024 · Druido · Forma Selvatica · pag. 80 (2 usi, 3 dal 6°, 4 dal 17°); 2014 · Druido · Forma Selvatica · pag. 66 (2 usi, illimitati al 20°)",
                    zona="flusso:compagni-forme", voce="limiti", copre=["POST /characters/{char_id}/companions/{comp_id}/activate", "carta:2014/classes/druid.md#Forma Selvatica / Wild Shape (Druido 2, pag. 66)", "carta:2024/classes/druid.md#Forma Selvatica / Wild Shape (Druido 2, pag. 80)"])
@pytest.mark.parametrize("edizione, livello, usi", [
    ("2024", 2, 2), ("2024", 5, 2), ("2024", 6, 3), ("2024", 16, 3), ("2024", 17, 4), ("2014", 19, 2), ("2014", 20, None)])
async def test_gli_usi_della_forma_selvatica_seguono_il_livello(client, edizione, livello, usi):
    cid = await (_druid24(client, livello) if edizione == "2024" else _druid(client, livello))
    riga = next(a for a in (await _full(client, cid))["abilities"] if a["feature_key"] == WILD)
    assert (riga["max_uses"], riga["uses"]) == (usi, usi)
    forma = await _form(client, cid, _beast(0.25))
    assert (await _activate(client, cid, forma)).status_code == 200
    assert await _usi(client, cid) == (None if usi is None else usi - 1)


@pytest.mark.caccia(id="CB-1084", fonte="invariante: annullare il danno che ha chiuso la forma rimette forma, PF della forma e PF del druido com'erano",
                    zona="flusso:compagni-forme", voce="annullamento", copre=["PATCH /characters/{char_id}/hp", "POST /characters/{char_id}/hp/undo"])
@pytest.mark.parametrize("danno", [10, 15])  # la forma ha 10 PF: azzerata esatta, e con eccesso
async def test_annullare_il_danno_che_chiude_la_forma_la_riapre(client, danno):
    cid = await _druid(client, 4)
    forma = await _form(client, cid, _beast(0.25), hp=10)
    await _activate(client, cid, forma)
    pf = (await _full(client, cid))["current_hit_points"]
    op = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": danno})).json()["hp_undo_id"]
    assert (await _full(client, cid))["active_form"] is None
    assert (await client.post(f"/characters/{cid}/hp/undo", json={"op_id": op})).status_code == 200
    c = next(c for c in await _lista(client, cid) if c["id"] == forma)
    assert (c["is_active"], c["current_hp"], (await _full(client, cid))["current_hit_points"]) == (True, 10, pf)
    assert (await _full(client, cid))["active_form"] is not None
    assert (await client.post(f"/characters/{cid}/hp/undo", json={"op_id": op})).status_code == 409  # una volta sola


@pytest.mark.caccia(id="CB-1085", fonte="2024 · Druido · Regole della Forma Selvatica · pag. 81 e Regole generali · Punti Ferita Temporanei · pag. 29 (non si sommano: si tengono i vecchi o i nuovi)",
                    zona="flusso:compagni-forme", voce="interazione",
                    copre=["POST /characters/{char_id}/companions/{comp_id}/activate", "PATCH /characters/{char_id}/hp",
                           "carta:2024/classes/druid.md#Regole della Forma Selvatica / Rules While Shape-Shifted (Druido 2, pag. 81)",
                           "carta:2024/general.md#Punti Ferita Temporanei / Temporary Hit Points (pag. 29)"])
@pytest.mark.parametrize("prima, atteso", [(0, 4), (2, 4), (4, 4), (20, 20)])
async def test_i_pf_temporanei_della_forma_non_si_sommano_a_quelli_che_ha_gia(client, prima, atteso):
    cid = await _druid24(client, 4)  # 4 PF temporanei dalla forma
    if prima:
        assert (await client.patch(f"/characters/{cid}/hp", json={"op": "set_temp", "value": prima})).status_code == 200
    forma = await _form(client, cid, _beast(0.25))
    assert (await _activate(client, cid, forma)).status_code == 200
    assert (await _full(client, cid))["temp_hp"] == atteso


@pytest.mark.xfail(strict=True, reason="CB-1089: una forma salvata ma non assunta attacca")
@pytest.mark.caccia(id="CB-1089", fonte="2014 · Druido · Forma Selvatica · pag. 66; 2024 · Druido · Forma Selvatica · pag. 80-81 (la forma vale solo mentre la si è assunta)",
                    zona="flusso:compagni-forme", voce="regola", copre=["POST /characters/{char_id}/companions/{comp_id}/attack", "carta:2014/classes/druid.md#Forma Selvatica / Wild Shape (Druido 2, pag. 66)"])
async def test_una_forma_non_assunta_non_attacca(client):
    cid = await _druid(client, 4)
    sb = {**_beast(0.25), "actions": [{"name": "Morso", "attack_bonus": 4, "damage_dice": "1d6+2", "damage_type": "piercing"}]}
    forma = await _form(client, cid, sb)
    r = await client.post(f"/characters/{cid}/companions/{forma}/attack", json={"action_index": 0, "mode": "normal", "dice": [10], "damage_rolls": [3]})
    assert r.status_code == 409


@pytest.mark.xfail(strict=True, reason="CB-1091: il danno su un compagno 0/0 risponde down true")
@pytest.mark.caccia(id="CB-1091", fonte="tests/caccia/decisioni.md D-015 (compagno con PF massimi 0: PF non segnati, mai a terra)",
                    zona="flusso:compagni-forme", voce="limiti", copre=["PATCH /characters/{char_id}/companions/{comp_id}/hp"])
async def test_un_compagno_senza_pf_segnati_non_va_a_terra(client):
    cid = await _druid(client, 4)
    r = await client.post(f"/characters/{cid}/companions", json={"kind": "familiar", "name": "Gufo", "statblock": {}, "max_hp": 0})
    comp = r.json()["id"]
    r = await client.patch(f"/characters/{cid}/companions/{comp}/hp", json={"op": "damage", "value": 3})
    assert r.status_code == 200 and r.json()["down"] is False


@pytest.mark.xfail(strict=True, reason="CB-1092: l'import accetta un personaggio con nome di soli spazi")
@pytest.mark.caccia(id="CB-1092", fonte="invariante: un nome di soli spazi è un nome vuoto (stessa famiglia di CB-1076): anche il personaggio importato",
                    zona="flusso:compagni-forme", voce="persistenza", copre=["POST /characters/import", "GET /characters/{char_id}/export"])
async def test_l_import_rifiuta_un_personaggio_senza_nome(client):
    cid = await _druid(client, 4)
    file = (await client.get(f"/characters/{cid}/export")).json()
    file["name"] = "   "
    r = await client.post("/characters/import", json=file)
    assert r.status_code == 422
