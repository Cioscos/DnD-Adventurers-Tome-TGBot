"""Test delle affermazioni: ogni caso ha un controllo o un'esenzione motivata, altrimenti la zona non si chiude."""
from __future__ import annotations

import json

import pytest

from tests.caccia.inventario import (
    VOCI, Controllo, Zona, casi_da_provare, importati, scegli, segna, verifica,
)

ENDPOINT = [("POST", "/characters/{char_id}/rest", "hp")]
NIENTE = {v: "non_applicabile" for v in VOCI}
LIMITI = {**NIENTE, "limiti": "fatta"}


def affermazione(**kw) -> dict:
    return {"A01": {"voce": "limiti", "testo": "Usi pari a 1 + CAR", "fonte": "2014 · Paladino · pag. 97",
                    "casi": {"a": "CAR 16: 4", "b": "CAR 8: 0"}, **kw}}


def scrivi(radice, nome, testo):
    f = radice / nome
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(testo, encoding="utf-8")


def scrivi_affermazioni(radice, dati):
    scrivi(radice, "tests/caccia/affermazioni/flusso-a.json", dati if isinstance(dati, str) else json.dumps(dati))


def scrivi_controllo(radice, prova):
    scrivi(radice, "tests/caccia/test_cb_a.py",
           "import pytest\n@pytest.mark.caccia(id='CB-001', fonte='x', zona='flusso:a', voce='limiti', copre=[], "
           f"prova={prova!r})\ndef test_a(): ...\n")


@pytest.fixture
def radice(tmp_path):
    z = Zona(id="flusso:a", tipo="flusso", file=["api/services/a.py"], router=["hp"], route=["/a"], carte=[])
    scrivi(tmp_path, "tests/caccia/zone.json", json.dumps([vars(z)]))
    scrivi(tmp_path, "tests/caccia/stato.json", '{"ritirati": [], "zone": {}}')
    scrivi(tmp_path, "api/services/a.py", "")
    scrivi(tmp_path, "webapp/src/App.tsx", '<Route path="/a" element={<A />} />')
    scrivi_affermazioni(tmp_path, affermazione())
    scrivi_controllo(tmp_path, ["A01a", "A01b"])
    return tmp_path


def test_tutti_i_casi_provati(radice):
    assert casi_da_provare(radice, "flusso:a") == {}
    assert verifica(radice, ENDPOINT) == []
    segna(radice, "flusso:a", "abc", LIMITI)


def test_caso_senza_controllo_blocca_la_zona(radice):
    scrivi_controllo(radice, ["A01a"])
    assert casi_da_provare(radice, "flusso:a") == {"A01b": "CAR 8: 0"}
    with pytest.raises(ValueError, match="A01b"):
        segna(radice, "flusso:a", "abc", LIMITI)


def test_esenzione_motivata(radice):
    scrivi_controllo(radice, ["A01a"])
    scrivi_affermazioni(radice, affermazione(esenti={"b": "CAR 8 non creabile"}))
    segna(radice, "flusso:a", "abc", LIMITI)


def test_zona_senza_affermazioni_non_si_chiude(radice):
    (radice / "tests/caccia/affermazioni/flusso-a.json").unlink()
    scrivi_controllo(radice, [])
    with pytest.raises(ValueError, match="affermazioni"):
        segna(radice, "flusso:a", "abc", LIMITI)


def test_voce_con_affermazioni_non_e_non_applicabile(radice):
    with pytest.raises(ValueError, match="limiti"):
        segna(radice, "flusso:a", "abc", NIENTE)


DIFETTI = {
    "prova ignota": lambda r: scrivi_controllo(r, ["A01a", "A01b", "A09z"]),
    "affermazione illeggibile": lambda r: (scrivi_controllo(r, []), scrivi_affermazioni(r, "{no")),
    "affermazione incompleta": lambda r: scrivi_affermazioni(r, affermazione(fonte=" ")),
    "esenzione senza motivo": lambda r: scrivi_affermazioni(r, affermazione(esenti={"b": " "})),
}


@pytest.mark.parametrize("difetto", DIFETTI)
def test_verifica_segnala(radice, difetto):
    DIFETTI[difetto](radice)
    errori = verifica(radice, ENDPOINT)
    assert len(errori) == 1 and errori[0].startswith(difetto + ": "), errori


def test_caso_nuovo_rende_scoperta(radice):
    segna(radice, "flusso:a", "abc", LIMITI)
    stato = json.loads((radice / "tests/caccia/stato.json").read_text(encoding="utf-8"))
    z = Zona("flusso:a", "flusso", [], [], [], [])
    c = Controllo("CB-001", "x", "flusso:a", "limiti", [], "f", False, ["A01a"])
    assert scegli([z], [c], stato, lambda _: [], 8, {"flusso:a": {"A01b": "x"}})[0][1] == "scoperta"
    assert scegli([z], [c], stato, lambda _: [], 8, {})[0][1] == "vecchia"


def test_importati_diretti_di_una_zona(radice):
    scrivi(radice, "webapp/src/pages/A.tsx", "import { x } from '@/hooks/useX'\nimport y from './y'\nimport React from 'react'\n")
    scrivi(radice, "webapp/src/hooks/useX.ts", "import '@/lib/lontano'\n")
    scrivi(radice, "webapp/src/pages/y.tsx", "")
    scrivi(radice, "webapp/src/lib/lontano.ts", "")
    scrivi(radice, "api/services/a.py", "from api.schemas.b import C\nfrom api.services import d\nimport json\n")
    scrivi(radice, "api/schemas/b.py", "")
    scrivi(radice, "api/services/d.py", "")
    z = Zona("flusso:a", "flusso", ["api/services/a.py", "webapp/src/pages/A.tsx"], [], [], [])
    assert importati(radice, [z])["flusso:a"] == {
        "webapp/src/hooks/useX.ts", "webapp/src/pages/y.tsx", "api/schemas/b.py", "api/services/d.py"}


def test_importato_da_molte_zone_non_le_segna_tutte(radice):
    scrivi(radice, "webapp/src/pages/A.tsx", "import { x } from '@/hooks/useX'\n")
    scrivi(radice, "webapp/src/hooks/useX.ts", "")
    zone = [Zona(f"flusso:{i}", "flusso", ["webapp/src/pages/A.tsx"], [], [], []) for i in range(9)]
    assert all(v == set() for v in importati(radice, zone).values())


def test_file_importato_cambiato_rende_modificata():
    z = Zona("flusso:a", "flusso", [], [], [], [])
    stato = {"zone": {"flusso:a": {"commit": "c", "data": "2026-01-01", "voci": NIENTE}}, "ritirati": []}
    scelte = scegli([z], [], stato, lambda _: ["webapp/src/hooks/useX.ts"], 8, {}, {"flusso:a": {"webapp/src/hooks/useX.ts"}})
    assert scelte[0][1] == "modificata"
