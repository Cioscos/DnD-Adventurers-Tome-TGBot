"""Controlli della zona flusso:import-export-condivisione."""
import pytest
from sqlalchemy import select

from core.db.models import Item


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
