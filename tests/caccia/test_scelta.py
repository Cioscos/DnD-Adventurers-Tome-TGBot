"""Test della coda delle zone e della memoria fra i giri."""
from __future__ import annotations

import json
import subprocess

import pytest

from tests.caccia.inventario import VOCI, Controllo, Zona, file_cambiati, filtra, scegli, segna

NIENTE = {v: "non_applicabile" for v in VOCI}


def zona(id_: str) -> Zona:
    return Zona(id=id_, tipo=id_.split(":")[0], file=[f"core/{id_}.py"], router=[], route=[], carte=[])


def voce(data: str = "2026-01-01", commit: str = "c", **voci) -> dict:
    return {"commit": commit, "data": data, "voci": {**NIENTE, **voci}}


def ids(scelte):
    return [(z.id, m) for z, m in scelte]


def nulla(_commit):
    return []


def test_ordine_dei_gruppi():
    zone = [zona(i) for i in ("regola:v", "flusso:v", "regola:a", "flusso:b", "flusso:a", "regola:m", "flusso:m")]
    stato = {"zone": {i: voce() for i in ("regola:v", "flusso:v", "regola:m", "flusso:m")}, "ritirati": []}
    scelte = scegli(zone, [], stato, lambda c: ["core/regola:m.py", "core/flusso:m.py"])
    assert ids(scelte) == [
        ("flusso:m", "modificata"), ("regola:m", "modificata"), ("flusso:a", "scoperta"), ("flusso:b", "scoperta"),
        ("regola:a", "scoperta"), ("flusso:v", "vecchia"), ("regola:v", "vecchia")]


def test_vecchia_per_data():
    stato = {"zone": {"flusso:a": voce("2026-02-01"), "regola:a": voce("2026-01-01")}, "ritirati": []}
    assert [z.id for z, _ in scegli([zona("flusso:a"), zona("regola:a")], [], stato, nulla)] == ["regola:a", "flusso:a"]


def test_massimo_non_perde_le_modificate():
    zone = [zona(f"flusso:{i:02}") for i in range(20)]
    stato = {"zone": {z.id: voce(commit="vecchio") for z in zone}, "ritirati": []}

    def cambiati(commit):
        return [z.file[0] for z in zone] if commit == "vecchio" else []
    prime = scegli(zone, [], stato, cambiati, 8)
    for z, _ in prime:
        stato["zone"][z.id]["commit"] = "nuovo"
    resto = scegli(zone, [], stato, cambiati, 20)
    assert len(prime) == 8
    assert {z.id for z, m in resto if m == "modificata"} == {z.id for z in zone} - {z.id for z, _ in prime}


def test_commit_sparito_conta_come_modificata():
    stato = {"zone": {"flusso:a": voce()}, "ritirati": []}
    assert ids(scegli([zona("flusso:a")], [], stato, lambda c: None)) == [("flusso:a", "modificata")]


def test_controllo_rimosso_rende_scoperta():
    stato = {"zone": {"flusso:a": voce(limiti="fatta")}, "ritirati": []}
    c = Controllo("CB-001", "x", "flusso:a", "limiti", [], "f", False)
    assert ids(scegli([zona("flusso:a")], [c], stato, nulla)) == [("flusso:a", "vecchia")]
    assert ids(scegli([zona("flusso:a")], [], stato, nulla)) == [("flusso:a", "scoperta")]


@pytest.fixture
def radice(tmp_path):
    d = tmp_path / "tests/caccia"
    d.mkdir(parents=True)
    (d / "zone.json").write_text(json.dumps([vars(zona("flusso:a"))]), encoding="utf-8")
    (d / "stato.json").write_text('{"ritirati": ["CB-009"], "zone": {}}', encoding="utf-8")
    (d / "test_cb_a.py").write_text(
        "import pytest\n@pytest.mark.caccia(id='CB-001', fonte='x', zona='flusso:a', voce='limiti', copre=[])\n"
        "def test_a(): ...\n", encoding="utf-8")
    return tmp_path


def leggi(radice):
    return json.loads((radice / "tests/caccia/stato.json").read_text(encoding="utf-8"))


def test_segna_salva_zona_e_ritirati(radice):
    segna(radice, "flusso:a", "abc", {**NIENTE, "limiti": "fatta"})
    assert leggi(radice)["zone"]["flusso:a"]["commit"] == "abc" and leggi(radice)["ritirati"] == ["CB-009"]


@pytest.mark.parametrize("id_,voci", [
    ("flusso:a", {k: v for k, v in NIENTE.items() if k != "regola"}),
    ("flusso:a", {**NIENTE, "normale": "fatta"}),
    ("flusso:a", {**NIENTE, "limiti": "boh"}),
    ("flusso:z", NIENTE),
], ids=["voce mancante", "fatta senza controllo", "esito ignoto", "zona ignota"])
def test_segna_rifiuta(radice, id_, voci):
    with pytest.raises(ValueError):
        segna(radice, id_, "abc", voci)
    assert leggi(radice)["zone"] == {}


def test_interrotto_resta_in_coda():
    zone, stato = [zona("flusso:a"), zona("flusso:b")], {"zone": {"flusso:a": voce()}, "ritirati": []}
    assert ids(scegli(zone, [], stato, nulla))[0] == ("flusso:b", "scoperta")


def test_includi_escludi_edizione():
    zone = [zona(i) for i in ("flusso:a", "flusso:b", "regola:2014/x", "regola:2024/x")]
    assert [z.id for z in filtra(zone, [], [], "2024")] == ["flusso:a", "flusso:b", "regola:2024/x"]
    assert [z.id for z in filtra(zone, ["flusso:*"], ["flusso:b"], None)] == ["flusso:a"]
    with pytest.raises(ValueError):
        filtra(zone, ["flusso:boh"], [], None)


def test_file_cambiati_su_repo_vero(tmp_path):
    def git(*a):
        return subprocess.run(["git", "-c", "user.name=x", "-c", "user.email=x@x", *a], cwd=tmp_path, check=True,
                              capture_output=True, text=True).stdout.strip()
    git("init")
    (tmp_path / "a.py").write_text("1")
    git("add", "a.py")
    git("commit", "-m", "1")
    primo = git("rev-parse", "HEAD")
    (tmp_path / "è.py").write_text("2")
    git("mv", "a.py", "b.py")
    git("add", "è.py")
    git("commit", "-m", "2")
    assert sorted(file_cambiati(tmp_path, primo) or []) == ["a.py", "b.py", "è.py"]
    assert file_cambiati(tmp_path, "f" * 40) is None
