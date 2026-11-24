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
