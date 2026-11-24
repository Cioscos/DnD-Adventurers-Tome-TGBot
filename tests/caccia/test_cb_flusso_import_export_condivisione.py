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
    assert (await client.post("/characters/import", json=dati)).status_code == 422
    if parte in ("spells", "abilities"):
        assert (await client.post(f"/characters/{cid}/{parte}", json={"name": "   "})).status_code == 422


@pytest.mark.caccia(id="CB-1506", fonte="invariante (come CB-1374): la caratteristica da incantatore è una delle sei", zona="flusso:import-export-condivisione",
                    voce="contratto", copre=["POST /characters/import"])
async def test_import_scarta_una_caratteristica_da_incantatore_inventata(client):
    _cid, dati = await _file_di_prova(client)
    dati["classes"][0]["spellcasting_ability"] = "pippo"
    r = await client.post("/characters/import", json=dati)
    assert r.status_code == 201, r.text
    assert r.json()["classes"][0]["spellcasting_ability"] is None
