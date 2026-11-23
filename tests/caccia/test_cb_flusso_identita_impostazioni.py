"""Controlli della zona flusso:identità-impostazioni."""
import pytest

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
