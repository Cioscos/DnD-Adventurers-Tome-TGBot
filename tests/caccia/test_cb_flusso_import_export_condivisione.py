"""Controlli della zona flusso:import-export-condivisione."""
import pytest
from sqlalchemy import select

from core.db.models import Character, Item


@pytest.mark.caccia(id="CB-011", fonte="invariante: export, import e duplica conservano le munizioni da recuperare",
                    zona="flusso:import-export-condivisione", voce="persistenza",
                    copre=["GET /characters/{char_id}/export", "POST /characters/import", "POST /characters/{char_id}/duplicate"])
async def test_munizioni_spese_conservate(client, test_session_factory):
    cid = (await client.post("/characters", json={"name": "P"})).json()["id"]
    await client.post(f"/characters/{cid}/items", json={"name": "Frecce", "item_type": "ammunition", "quantity": 16})
    async with test_session_factory() as s:
        (await s.execute(select(Item).where(Item.character_id == cid))).scalar_one().ammo_spent = 4
        await s.commit()
    dati = (await client.get(f"/characters/{cid}/export")).json()
    nuovi = [(await client.post("/characters/import", json=dati)).json(),
             (await client.post(f"/characters/{cid}/duplicate")).json()]
    async with test_session_factory() as s:
        for pg in nuovi:
            oggetto = (await s.execute(select(Item).where(Item.character_id == pg["id"]))).scalar_one()
            assert (oggetto.quantity, oggetto.ammo_spent) == (16, 4)
    dati["items"][0].pop("ammo_spent", None)  # file esportato prima
    assert (await client.post("/characters/import", json=dati)).status_code == 201


@pytest.mark.caccia(id="CB-031", fonte="invariante: una nota importata si può modificare ed eliminare", zona="flusso:import-export-condivisione",
                    voce="limiti", copre=["POST /characters/import", "POST /characters/{char_id}/duplicate"])
async def test_titoli_irraggiungibili_rinominati_nell_import(client, test_session_factory):
    cid = (await client.post("/characters", json={"name": "P"})).json()["id"]
    dati = (await client.get(f"/characters/{cid}/export")).json()
    nota = {"body": "x", "tags": []}
    dati["character"]["notes"] = {"Nota": nota, "..": nota, "": nota, "a/../..": nota, "Buona": nota}
    nuovo = (await client.post("/characters/import", json=dati)).json()["id"]
    titoli = [n["title"] for n in (await client.get(f"/characters/{nuovo}/notes")).json()]
    assert titoli == ["Nota", "Nota (2)", "Nota (3)", "a-..-..", "Buona"]
    async with test_session_factory() as s:
        (await s.get(Character, nuovo)).notes = {"..": nota}
        await s.commit()
    copia = (await client.post(f"/characters/{nuovo}/duplicate")).json()["id"]
    assert [n["title"] for n in (await client.get(f"/characters/{copia}/notes")).json()] == ["Nota"]


async def _file_di_prova(client):
    cid = (await client.post("/characters", json={"name": "F", "initial_class": {"class_name": "wizard", "level": 1}})).json()["id"]
    for path, body in (("items", {"name": "Corda", "item_type": "gear"}), ("spells", {"name": "Luce", "level": 0}), ("abilities", {"name": "Dono"})):
        assert (await client.post(f"/characters/{cid}/{path}", json=body)).status_code == 201
    return cid, (await client.get(f"/characters/{cid}/export")).json()


@pytest.mark.caccia(id="CB-1505", fonte="invariante (come CB-1076): un nome di soli spazi è un nome vuoto, anche in un file", zona="flusso:import-export-condivisione",
                    voce="contratto", copre=["POST /characters/import", "POST /characters/{char_id}/spells", "POST /characters/{char_id}/abilities"])
@pytest.mark.parametrize("parte,campo", [("classes", "class_name"), ("items", "name"), ("spells", "name"), ("abilities", "name")])
async def test_import_rifiuta_classi_oggetti_incantesimi_e_capacita_senza_nome(client, parte, campo):
    cid, dati = await _file_di_prova(client)
    assert (await client.post("/characters/import", json=dati)).status_code == 201
    dati[parte][-1][campo] = "   "
    r = await client.post("/characters/import", json=dati)
    if parte in ("spells", "abilities"):  # l'app fino alla 3.14.7 li salvava senza nome: il file resta importabile, il vuoto no
        assert r.status_code == 201 and all(x["name"].strip() for x in r.json()[parte])
        assert (await client.post(f"/characters/{cid}/{parte}", json={"name": "   "})).status_code == 422
    else:
        assert r.status_code == 422


@pytest.mark.caccia(id="CB-1506", fonte="invariante (come CB-1374): la caratteristica da incantatore è una delle sei", zona="flusso:import-export-condivisione",
                    voce="contratto", copre=["POST /characters/import"])
@pytest.mark.parametrize("valore", ["pippo", "INT", "Intelligenza"])
async def test_import_al_posto_di_una_caratteristica_sconosciuta_usa_quella_della_classe(client, valore):
    _cid, dati = await _file_di_prova(client)
    dati["classes"][0]["spellcasting_ability"] = valore
    r = await client.post("/characters/import", json=dati)
    assert r.status_code == 201, r.text
    assert r.json()["classes"][0]["spellcasting_ability"] == "intelligence"


@pytest.mark.caccia(id="CB-1536", fonte="invariante (come CB-1505): un nome che non si vede è un nome vuoto", zona="flusso:import-export-condivisione",
                    voce="contratto", copre=["POST /characters/import"])
async def test_import_un_nome_di_soli_caratteri_invisibili_e_vuoto(client):
    _cid, dati = await _file_di_prova(client)
    dati["spells"][-1]["name"] = "\u200b"
    r = await client.post("/characters/import", json=dati)
    assert r.status_code == 201 and r.json()["spells"][-1]["name"] == "?"
    dati["character"]["name"] = "\u200b\u200b"
    assert (await client.post("/characters/import", json=dati)).status_code == 422


@pytest.mark.caccia(id="CB-1537", fonte="decisione D-016 (tests/caccia/decisioni.md): massimo 9999 round; invariante: gli id di un altro personaggio non viaggiano",
                    zona="flusso:import-export-condivisione", voce="limiti", copre=["POST /characters/import"])
async def test_import_concentrazione_da_oggetto_senza_id_altrui_e_con_i_round_al_massimo(client):
    _cid, dati = await _file_di_prova(client)
    dati["character"]["settings"] = {"concentration_rounds_left": 50000, "concentration_item_spell": {"item_id": 1, "name": "X"}}
    r = await client.post("/characters/import", json=dati)
    assert r.status_code == 201, r.text
    s = r.json()["settings"]
    assert s["concentration_rounds_left"] == 9999 and s["concentration_item_spell"] == {"name": "X"}


@pytest.mark.caccia(id="CB-1546", fonte="invariante: un file illeggibile in un punto non rompe la scheda importata", zona="flusso:import-export-condivisione",
                    voce="contratto", copre=["POST /characters/import", "PATCH /characters/{char_id}/hp"])
@pytest.mark.parametrize("valore", ["X", [1], 5, True])
async def test_import_concentrazione_da_oggetto_illeggibile_scartata(client, valore):
    _cid, dati = await _file_di_prova(client)
    dati["character"]["settings"] = {"concentration_item_spell": valore}
    r = await client.post("/characters/import", json=dati)
    assert r.status_code == 201, r.text
    assert (await client.patch(f"/characters/{r.json()['id']}/hp", json={"op": "damage", "value": 1})).status_code == 200
    assert (await client.patch(f"/characters/{r.json()['id']}/concentration", json={"spell_id": None})).status_code == 200


@pytest.mark.caccia(id="CB-1548", fonte="invariante (come CB-1536): un nome che non si vede è un nome vuoto, anche dall'app", zona="flusso:import-export-condivisione",
                    voce="contratto", copre=["POST /characters", "PATCH /characters/{char_id}", "POST /characters/{char_id}/items"])
async def test_un_nome_invisibile_e_rifiutato_ovunque(client):
    assert (await client.post("/characters", json={"name": "\u200b"})).status_code == 422
    cid, _dati = await _file_di_prova(client)
    assert (await client.patch(f"/characters/{cid}", json={"name": "\u200b"})).status_code == 422
    for parte in ("items", "spells", "abilities"):
        assert (await client.post(f"/characters/{cid}/{parte}", json={"name": "\u200b"})).status_code == 422
    nuovo = (await client.post("/characters", json={"name": "\ue000"})).json()["id"]  # ciò che l'app accetta, il file lo riporta
    assert (await client.post("/characters/import", json=(await client.get(f"/characters/{nuovo}/export")).json())).status_code == 201
    assert (await client.patch(f"/characters/{cid}", json={"name": "Ünï ‍👩‍🚀"})).status_code == 200
