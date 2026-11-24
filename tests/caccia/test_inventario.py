"""Test dell'inventario: niente app né manuali veri, tranne `test_catalogo_reale`."""
from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from api.auth import get_current_user
from api.main import app
from tests.caccia import inventario as inv
from tests.caccia.inventario import (
    RADICE, Controllo, carte, endpoint_app, leggi_controlli, prossimo_id, route_fe, verifica,
)

ENDPOINT = [("POST", "/characters/{char_id}/rest", "hp")]


def controllo(id_: str, zona: str = "flusso:riposo", voce: str = "limiti") -> Controllo:
    return Controllo(id=id_, fonte="x", zona=zona, voce=voce, copre=[], file="f", aperto=False)


def marcatore(**kw) -> str:
    base = {"id": "CB-001", "fonte": "CLAUDE.md", "zona": "flusso:riposo", "voce": "limiti",
            "copre": ["POST /characters/{char_id}/rest"], **kw}
    return "@pytest.mark.caccia(" + ", ".join(f"{k}={v!r}" for k, v in base.items()) + ")"


def ts(funzione: str = "test", **kw) -> str:
    base = {"id": "CB-010", "fonte": "x", "zona": "flusso:riposo", "voce": "limiti", "copre": [], **kw}
    return f"// caccia: {json.dumps(base)}\n{funzione}('x', () => {{}})\n"


def scrivi(radice: Path, nome: str, testo: str) -> None:
    f = radice / nome
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(testo, encoding="utf-8")


def scrivi_py(radice: Path, *righe: str) -> None:
    scrivi(radice, "tests/caccia/test_cb_x.py", "import pytest\n" + "\n".join(righe) + "\n")


def modifica_zone(radice: Path, **campi) -> None:
    f = radice / "tests/caccia/zone.json"
    zone = json.loads(f.read_text(encoding="utf-8"))
    zone[0].update(campi)
    f.write_text(json.dumps(zone), encoding="utf-8")


@pytest.fixture
def radice(tmp_path):
    scrivi(tmp_path, "tests/caccia/zone.json", json.dumps([{
        "id": "flusso:riposo", "tipo": "flusso", "file": ["api/services/r*.py"], "router": ["hp"],
        "route": ["/char/:id/hp"], "carte": [{"file": "2024/general.md"}, {"file": "2024/feats.md"}]}]))
    scrivi(tmp_path, "tests/caccia/stato.json", json.dumps({"zone": {}, "ritirati": []}))
    scrivi(tmp_path, "api/services/riposo.py", "")
    scrivi(tmp_path, "webapp/src/App.tsx",
           '<Route path="/char/:id/hp" element={<HP />} />\n<Route path="*" element={<Navigate to="/" />} />')
    scrivi(tmp_path, "docs/superpowers/rules/2024/general.md", "# X\n## Capitolo\n### Riposo / Rest (pag. 1)\n")
    scrivi_py(tmp_path, marcatore(), "def test_a(): ...")
    return tmp_path


def test_legge_marcatore_python_e_xfail(radice):
    scrivi_py(radice, marcatore(), "def test_a(): ...", marcatore(id="CB-002", voce="regola"),
              '@pytest.mark.xfail(strict=True, reason="CB-002 x")', "async def test_b(): ...")
    assert [(c.id, c.voce, c.aperto) for c in leggi_controlli(radice)] == [
        ("CB-001", "limiti", False), ("CB-002", "regola", True)]


def test_legge_metadati_ts(radice):
    scrivi(radice, "webapp/tests/unit/caccia/a.test.tsx", ts("test.fails", id="CB-003") + ts(id="CB-005"))
    scrivi(radice, "webapp/tests/e2e-playwright/caccia/a.spec.ts", ts("test.fail", id="CB-004"))
    assert {c.id for c in leggi_controlli(radice) if c.aperto} == {"CB-003", "CB-004"}
    assert "CB-005" in {c.id for c in leggi_controlli(radice)}


def test_id_mai_riusato():
    assert prossimo_id([controllo("CB-007")], ["CB-009"]) == "CB-010"
    assert prossimo_id([], []) == "CB-001"


def test_route_senza_rimandi(radice):
    assert route_fe(radice) == ["/char/:id/hp"]


def test_carte_con_titoli_di_secondo_livello(radice):
    scrivi(radice, "docs/superpowers/rules/2014/feats.md", "# T\n## Note\n## Abile / Skilled (pag. 165)\n")
    assert carte(radice)["2014/feats.md"] == ["Abile / Skilled (pag. 165)"]


def test_carte_da_tabella_incantesimi(radice):
    scrivi(radice, "docs/superpowers/rules/2024/spells.md",
           "# I\n| titolo IT | titolo EN |\n|---|---|\n| Aiuto | Aid |\n\n## Note degli autori\n"
           "| a | b |\n|---|---|\n| no | x |\n")
    assert carte(radice)["2024/spells.md"] == ["Aiuto"]


def test_manuali_assenti(radice, capsys):
    (radice / "docs/superpowers/rules/2024/general.md").unlink()
    (radice / "docs/superpowers/rules/2024").rmdir()
    assert carte(radice) is None
    inv.elenco(radice, ENDPOINT)
    assert "Manuali assenti: carte non conteggiate" in capsys.readouterr().out
    assert verifica(radice, ENDPOINT) == []


def test_base_senza_errori(radice):
    assert verifica(radice, ENDPOINT) == []


def _extra(radice, riga):
    scrivi_py(radice, marcatore(), riga, "def test_a(): ...")


DIFETTI = {
    "id doppio": lambda r: scrivi_py(r, marcatore(), "def test_a(): ...", marcatore(), "def test_b(): ..."),
    "fonte vuota": lambda r: scrivi_py(r, marcatore(fonte=" "), "def test_a(): ..."),
    "voce ignota": lambda r: scrivi_py(r, marcatore(voce="boh"), "def test_a(): ..."),
    "zona ignota": lambda r: scrivi_py(r, marcatore(zona="flusso:boh"), "def test_a(): ..."),
    "copre ignoto": lambda r: scrivi_py(r, marcatore(copre=["GET /boh"]), "def test_a(): ..."),
    "id malformato": lambda r: scrivi_py(r, marcatore(id="X1"), "def test_a(): ..."),
    "metadati illeggibili": lambda r: scrivi(r, "webapp/tests/unit/caccia/a.test.ts", "// caccia: {no}\ntest('x', f)\n"),
    "id ritirato riusato": lambda r: scrivi(r, "tests/caccia/stato.json", '{"zone": {}, "ritirati": ["CB-001"]}'),
    "skip": lambda r: _extra(r, "@pytest.mark.skipif(True, reason='x')"),
    "only": lambda r: scrivi(r, "webapp/tests/unit/caccia/a.test.ts", ts("test.only")),
    "xfail non strict": lambda r: _extra(r, "@pytest.mark.xfail(reason='CB-001 x')"),
    "xfail senza id": lambda r: _extra(r, "@pytest.mark.xfail(strict=True, reason='x')"),
    "test senza marcatore": lambda r: scrivi_py(r, marcatore(), "def test_a(): ...", "def test_b(): ..."),
    "endpoint senza zona": lambda r: modifica_zone(r, router=[]),
    "route senza zona": lambda r: modifica_zone(r, route=[]),
    "carta senza zona": lambda r: modifica_zone(r, carte=[{"file": "2024/general.md", "titoli": "^Z"}]),
    "file senza zona": lambda r: scrivi(r, "api/services/altro.py", ""),
    "glob vuoto": lambda r: modifica_zone(r, file=["api/services/r*.py", "core/niente*"]),
    "file senza carte": lambda r: scrivi(r, "docs/superpowers/rules/2024/feats.md", "# vuoto\n"),
}


@pytest.mark.parametrize("difetto", DIFETTI)
def test_verifica_segnala(radice, difetto):
    DIFETTI[difetto](radice)
    errori = verifica(radice, ENDPOINT)
    assert len(errori) == 1 and errori[0].startswith(difetto + ": "), errori


@pytest.mark.parametrize("funzione,atteso", [
    ("test.skip", "skip"), ("test.fixme", "skip"), ("test.describe.skip", "skip"),
    ("describe.only", "only"), ("it", None), ("test.describe", None)])
def test_varianti_ts(radice, funzione, atteso):
    testo = ts(funzione) if "describe" not in funzione else f"{funzione}('x', () => {{}})\n"
    scrivi(radice, "webapp/tests/unit/caccia/a.test.ts", testo)
    assert [e.split(":")[0] for e in verifica(radice, ENDPOINT)] == ([atteso] if atteso else [])


def test_ts_senza_marcatore(radice):
    scrivi(radice, "webapp/tests/e2e-playwright/caccia/a.spec.ts", ts() + "test.fail('y', f)\n")
    assert verifica(radice, ENDPOINT)[0].startswith("test senza marcatore: ")


def test_catalogo_reale():
    assert verifica(RADICE, endpoint_app()) == []


def test_endpoint_app():
    assert ("POST", "/characters/{char_id}/rest", "hp") in endpoint_app()


def test_dadi_in_ordine(dadi):
    dadi(3, 5)
    assert (random.randint(1, 6), random.randint(1, 8)) == (3, 5)
    with pytest.raises(AssertionError):
        random.randint(1, 6)


def test_dadi_fuori_dai_limiti(dadi):
    dadi(7)
    with pytest.raises(AssertionError):
        random.randint(1, 6)


def test_seme_fisso():
    assert random.random() == random.Random(0).random()


async def test_come_utente(client, come_utente):
    cid = (await client.post("/characters", json={"name": "Prova"})).json()["id"]
    come_utente(9002)
    assert (await client.get(f"/characters/{cid}")).status_code in (403, 404)
    assert app.dependency_overrides[get_current_user]() == 9002
