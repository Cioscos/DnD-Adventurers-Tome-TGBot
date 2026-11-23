"""Controlli della zona flusso:note-mappe."""
import pytest

from api.routers import maps, notes


async def _pg(client) -> int:
    return (await client.post("/characters", json={"name": "P"})).json()["id"]


@pytest.mark.caccia(id="CB-004", fonte="invariante: una nota creata si può modificare ed eliminare", zona="flusso:note-mappe",
                    voce="normale", copre=[])
@pytest.mark.parametrize("titolo, url", [("Atto 1/2", "Atto%201%2F2"), ("a/b/c", "a%2Fb%2Fc"), ("voice/x", "voice%2Fx")])
async def test_nota_con_barra_nel_titolo(client, titolo, url):
    cid = await _pg(client)
    assert (await client.post(f"/characters/{cid}/notes", json={"title": titolo, "body": "x"})).status_code == 201
    r = await client.patch(f"/characters/{cid}/notes/{url}", json={"body": "nuovo"})
    assert r.status_code == 200 and r.json()[0]["body"] == "nuovo"
    r = await client.delete(f"/characters/{cid}/notes/{url}")
    assert r.status_code == 200 and r.json() == []


@pytest.mark.caccia(id="CB-018", fonte="invariante: una nota senza titolo non è raggiungibile", zona="flusso:note-mappe",
                    voce="limiti", copre=["POST /characters/{char_id}/notes", "POST /characters/{char_id}/notes/voice"])
@pytest.mark.parametrize("titolo", ["", "   "])
async def test_nota_senza_titolo_rifiutata(client, tmp_path, monkeypatch, titolo):
    monkeypatch.setattr(notes, "_VOICE_DIR", tmp_path)
    cid = await _pg(client)
    assert (await client.post(f"/characters/{cid}/notes", json={"title": titolo, "body": "x"})).status_code == 422
    r = await client.post(f"/characters/{cid}/notes/voice", data={"title": titolo}, files={"file": ("a.webm", b"x")})
    assert r.status_code == 422
    assert (await client.get(f"/characters/{cid}/notes")).json() == []


@pytest.mark.caccia(id="CB-019", fonte="invariante: una mappa ha una zona con un nome", zona="flusso:note-mappe",
                    voce="limiti", copre=["POST /characters/{char_id}/maps/upload"])
@pytest.mark.parametrize("zona", ["", "   "])
async def test_mappa_senza_zona_rifiutata(client, tmp_path, monkeypatch, zona):
    monkeypatch.setattr(maps, "_MAPS_DIR", tmp_path)
    cid = await _pg(client)
    r = await client.post(f"/characters/{cid}/maps/upload", data={"zone_name": zona}, files={"file": ("a.png", b"x")})
    assert r.status_code == 422
    assert list(tmp_path.rglob("*.png")) == []


@pytest.mark.caccia(id="CB-027", fonte="invariante: eliminare una nota non tocca altro che la nota", zona="flusso:note-mappe",
                    voce="limiti", copre=["POST /characters/{char_id}/notes", "POST /characters/{char_id}/notes/voice"])
@pytest.mark.parametrize("titolo", ["..", ".", "a/../.."])
async def test_titolo_che_cambierebbe_l_indirizzo_rifiutato(client, tmp_path, monkeypatch, titolo):
    monkeypatch.setattr(notes, "_VOICE_DIR", tmp_path)
    cid = await _pg(client)
    assert (await client.post(f"/characters/{cid}/notes", json={"title": titolo, "body": "x"})).status_code == 422
    r = await client.post(f"/characters/{cid}/notes/voice", data={"title": titolo}, files={"file": ("a.webm", b"x")})
    assert r.status_code == 422
    assert (await client.post(f"/characters/{cid}/notes", json={"title": "Fine...", "body": "x"})).status_code == 201
