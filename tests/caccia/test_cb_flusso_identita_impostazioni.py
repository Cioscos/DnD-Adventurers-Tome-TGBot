"""Controlli della zona flusso:identità-impostazioni."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.routers import maps, notes, silhouette


@pytest.mark.caccia(id="CB-009", fonte="invariante: eliminare un personaggio elimina i suoi file", zona="flusso:identità-impostazioni",
                    voce="annullamento", copre=["DELETE /characters/{char_id}"])
async def test_personaggio_eliminato_senza_file_orfani(client, tmp_path, monkeypatch):
    base = tmp_path / "file"
    monkeypatch.setattr(maps, "_MAPS_DIR", base / "maps")
    monkeypatch.setattr(notes, "_VOICE_DIR", base / "voice")
    monkeypatch.setattr(silhouette, "_SIL_DIR", base / "sil")

    def file():
        return [f for f in base.rglob("*") if f.is_file()]

    ids = [(await client.post("/characters", json={"name": n})).json()["id"] for n in "PQ"]
    for cid in ids:
        await client.post(f"/characters/{cid}/maps/upload", data={"zone_name": "z"}, files={"file": ("a.png", b"x")})
        await client.post(f"/characters/{cid}/notes/voice", data={"title": "v"}, files={"file": ("a.webm", b"x")})
        await client.post(f"/characters/{cid}/silhouette", files={"file": ("a.png", b"x")})
    assert len(file()) == 6
    estraneo = tmp_path / "estraneo.webm"
    estraneo.write_bytes(b"x")
    await client.post(f"/characters/{ids[0]}/notes", json={"title": "finta", "body": f"[VOICE:{estraneo}]"})
    assert (await client.delete(f"/characters/{ids[0]}")).status_code == 204
    assert len(file()) == 3 and all(f.parent.name == str(ids[1]) for f in file())
    assert estraneo.exists()


@pytest.mark.caccia(id="CB-034", fonte="invariante: personaggi e oggetti hanno un nome", zona="flusso:identità-impostazioni",
                    voce="limiti", copre=["POST /characters", "PATCH /characters/{char_id}", "POST /characters/{char_id}/items"])
@pytest.mark.parametrize("nome", ["", "   "])
async def test_nomi_vuoti_rifiutati(client, nome):
    assert (await client.post("/characters", json={"name": nome})).status_code == 422
    cid = (await client.post("/characters", json={"name": "P"})).json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"name": nome})).status_code == 422
    assert (await client.post(f"/characters/{cid}/items", json={"name": nome})).status_code == 422
    pg = (await client.post(f"/characters/{cid}/items", json={"name": "Corda"})).json()
    oggetto = (await client.get(f"/characters/{cid}")).json()["items"][0]["id"]
    assert pg and (await client.patch(f"/characters/{cid}/items/{oggetto}", json={"name": nome})).status_code == 422
    assert (await client.get(f"/characters/{cid}")).json()["name"] == "P"


@pytest.mark.caccia(id="CB-035", fonte="invariante: se il database rifiuta l'eliminazione i file restano", zona="flusso:identità-impostazioni",
                    voce="annullamento", copre=["DELETE /characters/{char_id}"])
async def test_file_conservati_se_il_database_rifiuta(client, monkeypatch, tmp_path):
    cid = (await client.post("/characters", json={"name": "P"})).json()["id"]
    await client.post(f"/characters/{cid}/maps/upload", data={"zone_name": "z"}, files={"file": ("a.png", b"x")})
    file = [f for f in (tmp_path / "maps").rglob("*") if f.is_file()]

    async def rifiuta(self):
        raise RuntimeError("database bloccato")
    with monkeypatch.context() as m:
        m.setattr(AsyncSession, "commit", rifiuta)
        with pytest.raises(RuntimeError):
            await client.delete(f"/characters/{cid}")
    assert len(file) == 1 and file[0].exists()
    assert (await client.get(f"/characters/{cid}")).status_code == 200
