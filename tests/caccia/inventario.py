"""Inventario della caccia ai bug: catalogo dei controlli, zone, copertura. Nessun modello coinvolto.

Uso (da Windows, dalla radice): uv run python -m tests.caccia.inventario elenco|verifica|prossimo-id|scegli|segna|casi|coda|fonti
"""
from __future__ import annotations

import argparse
import ast
import json
import posixpath
import re
import subprocess
import sys
import unicodedata
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from fnmatch import fnmatchcase
from functools import cache
from pathlib import Path
from typing import Any

RADICE = Path(__file__).resolve().parents[2]
VOCI = ("contratto", "normale", "limiti", "ripetizione", "annullamento", "persistenza", "permessi", "edizioni",
        "interazione", "regola")
_ID = re.compile(r"^CB-\d{3,}$")
_META_TS = re.compile(r"^\s*//\s*caccia:\s*(.*)$")
_TEST_TS = re.compile(r"^\s*(?:test|it|describe)((?:\.\w+)*)\s*\(")
_CARTELLE_TS = ("webapp/tests/unit/caccia", "webapp/tests/e2e-playwright/caccia")
_SORGENTI = ("api", "core", "webapp/src")
_MOLTE_ZONE = 8  # shortcut: un file importato da più zone (client.ts, models.py) non le rimette tutte in coda; resta la regressione
_CON_ZONA = ("api/services/", "core/rules/", "webapp/src/pages/")

Endpoint = tuple[str, str, str]


@dataclass
class Controllo:
    id: str
    fonte: str
    zona: str
    voce: str
    copre: list[str]
    file: str
    aperto: bool
    prova: list[str] = field(default_factory=list)


@dataclass
class Zona:
    id: str
    tipo: str
    file: list[str]
    router: list[str]
    route: list[str]
    carte: list[dict]

    @property
    def glob(self) -> list[str]:
        return self.file + [f"api/routers/{r}.py" for r in self.router]


# --- lettura del catalogo ---------------------------------------------------------------------------------------

def _scansiona_py(f: Path, nome: str) -> tuple[list[Controllo], list[str]]:
    controlli, errori = [], []
    albero = ast.parse(f.read_text(encoding="utf-8"), str(f))
    for n in ast.walk(albero):
        if isinstance(n, ast.Attribute) and n.attr in ("skip", "skipif", "importorskip") and ast.unparse(n).startswith("pytest."):
            errori.append(f"skip: {nome}:{n.lineno}")
        if isinstance(n, ast.Attribute) and n.attr == "xfail":
            chiamata = next((c for c in ast.walk(albero) if isinstance(c, ast.Call) and c.func is n), None)
            kw = {k.arg: k.value.value for k in chiamata.keywords if isinstance(k.value, ast.Constant)} if chiamata else {}
            if kw.get("strict") is not True:
                errori.append(f"xfail non strict: {nome}:{n.lineno}")
            elif not re.match(r"CB-\d{3,}\b", str(kw.get("reason", ""))):
                errori.append(f"xfail senza id: {nome}:{n.lineno}")
    for n in ast.walk(albero):
        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) or not n.name.startswith("test_"):
            continue
        marche = [d for d in n.decorator_list if isinstance(d, ast.Call) and ast.unparse(d.func) == "pytest.mark.caccia"]
        if not marche:
            errori.append(f"test senza marcatore: {nome}:{n.lineno} {n.name}")
            continue
        aperto = any(isinstance(x, ast.Attribute) and x.attr == "xfail" for d in n.decorator_list for x in ast.walk(d))
        try:
            meta: dict[str, Any] = {str(k.arg): ast.literal_eval(k.value) for k in marche[0].keywords}
            controlli.append(Controllo(**meta, file=nome, aperto=aperto))
        except (ValueError, TypeError) as e:
            errori.append(f"metadati illeggibili: {nome}:{n.lineno} {e}")
    return controlli, errori


def _scansiona_ts(f: Path, nome: str) -> tuple[list[Controllo], list[str]]:
    controlli, errori = [], []
    meta: dict[str, Any] | None = None
    annotato = False
    for i, riga in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        m = _META_TS.match(riga)
        if m:
            annotato, meta = True, None
            try:
                meta = dict(json.loads(m.group(1)))
                Controllo(**meta, file=nome, aperto=False)
            except (ValueError, TypeError) as e:
                meta = None
                errori.append(f"metadati illeggibili: {nome}:{i} {e}")
            continue
        t = _TEST_TS.match(riga)
        if not t:
            continue
        parti = set(t.group(1).split("."))
        if parti & {"skip", "fixme", "todo", "skipIf", "runIf"}:
            errori.append(f"skip: {nome}:{i}")
        if "only" in parti:
            errori.append(f"only: {nome}:{i}")
        if "describe" in riga.split("(")[0] or parti & {"beforeEach", "afterEach", "beforeAll", "afterAll", "use", "step", "extend"}:
            continue
        if not annotato:
            errori.append(f"test senza marcatore: {nome}:{i}")
        elif meta:
            controlli.append(Controllo(**meta, file=nome, aperto=bool(parti & {"fail", "fails"})))
        annotato, meta = False, None
    return controlli, errori


def _scansiona(radice: Path) -> tuple[list[Controllo], list[str]]:
    controlli: list[Controllo] = []
    errori: list[str] = []
    sorgenti = [(f, _scansiona_py) for f in sorted((radice / "tests/caccia").glob("test_cb_*.py"))]
    for cartella in _CARTELLE_TS:
        for f in sorted((radice / cartella).rglob("*.ts*")):
            if re.search(r"\.(test|spec)\.tsx?$", f.name):
                sorgenti.append((f, _scansiona_ts))
    for f, leggi in sorgenti:
        c, e = leggi(f, f.relative_to(radice).as_posix())
        controlli += c
        errori += e
    return controlli, errori


def leggi_controlli(radice: Path) -> list[Controllo]:
    return _scansiona(radice)[0]


def leggi_zone(radice: Path) -> list[Zona]:
    return [Zona(**z) for z in json.loads((radice / "tests/caccia/zone.json").read_text(encoding="utf-8"))]


def leggi_stato(radice: Path) -> dict:
    return json.loads((radice / "tests/caccia/stato.json").read_text(encoding="utf-8"))


class AffermazioneDoppia(ValueError):
    pass


def _affermazioni(radice: Path, zona: str) -> dict[str, dict]:
    """Le affermazioni di una zona, dal file `<zona>.json` e dalle sue parti `<zona>--<parte>.json`."""
    cartella, nome = radice / "tests/caccia/affermazioni", re.sub(r"[:/]", "-", zona)
    tutte: dict[str, dict] = {}
    for f in [cartella / f"{nome}.json", *sorted(cartella.glob(f"{nome}--*.json"))]:
        if f.exists():
            nuove = json.loads(f.read_text(encoding="utf-8"))
            if doppie := set(tutte) & set(nuove):
                raise AffermazioneDoppia(f"{zona} {', '.join(sorted(doppie))}")
            tutte |= nuove
    return tutte


def casi_da_provare(radice: Path, zona: str, controlli: list[Controllo] | None = None) -> dict[str, str]:
    """Casi delle affermazioni della zona senza un controllo che li provi né un'esenzione motivata."""
    if controlli is None:
        controlli = leggi_controlli(radice)
    provati = {p for c in controlli if c.zona == zona for p in c.prova}
    return {a + c: testo for a, v in _affermazioni(radice, zona).items() for c, testo in v["casi"].items()
            if a + c not in provati and c not in v.get("esenti", {})}


def coda(radice: Path, zone: list[str], budget: int) -> list[tuple[str, str, str]]:
    """(zona, caso, testo) da provare: prima il rischio più alto, poi l'ordine delle zone. Ciò che eccede resta in coda."""
    controlli = leggi_controlli(radice)
    righe = []
    for n, zona in enumerate(zone):
        rischi = {a + c: v["rischio"] for a, v in _affermazioni(radice, zona).items() for c in v["casi"]}
        righe += [(rischi[c], n, c, zona, t) for c, t in casi_da_provare(radice, zona, controlli).items()]
    return [(zona, c, t) for _, _, c, zona, t in sorted(righe)[:budget]]


def fonti_scoperte(radice: Path, z: Zona) -> list[str]:
    """Pagine e carte della zona che nessuna affermazione tratta ancora."""
    trattate = {x for v in _affermazioni(radice, z.id).values() for x in v.get("copre", [])}
    fonti = [f"route:{r}" for r in z.route]
    fonti += [f"carta:{f}#{t}" for f, titoli in (carte(radice) or {}).items() for t in titoli if _ha_carta(z, f, t)]
    return [x for x in fonti if x not in trattate]


def _errori_affermazioni(radice: Path, zona: str, controlli: list[Controllo], noti: set[str], manuali: bool) -> list[str]:
    try:
        tutte = _affermazioni(radice, zona)
    except AffermazioneDoppia as e:
        return [f"affermazione doppia: {e}"]
    except ValueError as e:
        return [f"affermazione illeggibile: {zona} {e}"]
    errori, casi = [], set()
    for a, v in tutte.items():
        testi = [v.get("testo"), v.get("fonte")]
        errori += [f"copre ignoto: {zona} {a} {x}" for x in v.get("copre", []) if x not in noti and (manuali or not x.startswith("carta:"))]
        if v.get("voce") not in VOCI or v.get("rischio") not in (1, 2, 3) or not v.get("casi") or not all(isinstance(t, str) and t.strip() for t in testi):
            errori.append(f"affermazione incompleta: {zona} {a}")
        errori += [f"esenzione senza motivo: {zona} {a}{c}" for c, motivo in v.get("esenti", {}).items() if not motivo.strip()]
        casi |= {a + c for c in v.get("casi", {})}
    return errori + [f"prova ignota: {c.id} {p}" for c in controlli if c.zona == zona for p in c.prova if p not in casi]


def prossimo_id(controlli: list[Controllo], ritirati: list[str]) -> str:
    usati = [int(i[3:]) for i in [c.id for c in controlli] + ritirati if _ID.match(i)]
    return f"CB-{max(usati, default=0) + 1:03d}"


# --- lettura dell'app e dei manuali -----------------------------------------------------------------------------

def endpoint_app() -> list[Endpoint]:
    from fastapi.routing import APIRoute

    from api.main import app
    return sorted((m, r.path, r.endpoint.__module__.rsplit(".", 1)[-1])
                  for r in app.routes if isinstance(r, APIRoute) for m in r.methods)


def route_fe(radice: Path) -> list[str]:
    testo = (radice / "webapp/src/App.tsx").read_text(encoding="utf-8")
    return [p for p, elemento in re.findall(r'<Route\s+path="([^"]+)"\s+element=\{<(\w+)', testo) if elemento != "Navigate"]


def carte(radice: Path) -> dict[str, list[str]] | None:
    """Titoli delle carte per file; None se i manuali (locali, non versionati) non ci sono."""
    base = radice / "docs/superpowers/rules"
    trovate = {}
    for edizione in ("2014", "2024"):
        for f in sorted((base / edizione).rglob("*.md")):
            righe = f.read_text(encoding="utf-8").splitlines()
            if f.name == "spells.md":  # una tabella: ogni riga dati è una carta, fino al primo titolo di nota
                corpo = []
                for r in righe:
                    if r.startswith("## "):
                        break
                    corpo += [r] if r.startswith("|") else []
                titoli = [r.split("|")[1].strip() for r in corpo[2:]]
            else:
                titoli = [r.lstrip("# ") for r in righe if r.startswith("### ") or (r.startswith("## ") and "(pag" in r)]
            trovate[f.relative_to(base).as_posix()] = titoli
    return trovate or None


def _normale(testo: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", testo) if not unicodedata.combining(c)).upper()


def _ha_carta(z: Zona, file: str, titolo: str) -> bool:
    return any(c["file"] == file and re.search(c.get("titoli", ""), _normale(titolo)) for c in z.carte)


def _sorgenti(radice: Path) -> list[str]:
    return [f.relative_to(radice).as_posix() for s in _SORGENTI for f in (radice / s).rglob("*")
            if f.suffix in (".py", ".ts", ".tsx", ".json") and f.name != "__init__.py" and "graphify-out" not in f.parts]


# --- verifica e stampa -------------------------------------------------------------------------------------------

def verifica(radice: Path, endpoint: list[Endpoint]) -> list[str]:
    controlli, errori = _scansiona(radice)
    zone, schede, ritirati = leggi_zone(radice), carte(radice), leggi_stato(radice)["ritirati"]
    route = route_fe(radice)
    id_zone = {z.id for z in zone}
    noti = {f"{m} {p}" for m, p, _ in endpoint} | {f"route:{r}" for r in route}
    noti |= {f"carta:{f}#{t}" for f, titoli in (schede or {}).items() for t in titoli}

    for id_, n in Counter(c.id for c in controlli).items():
        if n > 1:
            errori.append(f"id doppio: {id_}")
    for c in controlli:
        dove = f"{c.id} {c.file}"
        if not _ID.match(c.id):
            errori.append(f"id malformato: {dove}")
        if c.id in ritirati:
            errori.append(f"id ritirato riusato: {dove}")
        if not c.fonte.strip():
            errori.append(f"fonte vuota: {dove}")
        if c.voce not in VOCI:
            errori.append(f"voce ignota: {dove} {c.voce}")
        if c.zona not in id_zone:
            errori.append(f"zona ignota: {dove} {c.zona}")
        errori += [f"copre ignoto: {dove} {x}" for x in c.copre
                   if x not in noti and not (schede is None and x.startswith("carta:"))]

    for z in zone:
        errori += _errori_affermazioni(radice, z.id, controlli, noti, schede is not None)
    for m, p, modulo in endpoint:
        if not any(modulo in z.router for z in zone):
            errori.append(f"endpoint senza zona: {m} {p} ({modulo})")
    for r in route:
        if not any(r in z.route for z in zone):
            errori.append(f"route senza zona: {r}")
    for f, titoli in (schede or {}).items():
        if not titoli:
            errori.append(f"file senza carte: {f}")
        errori += [f"carta senza zona: {f}#{t}" for t in titoli if not any(_ha_carta(z, f, t) for z in zone)]
    sorgenti = _sorgenti(radice)
    for s in sorgenti:
        if s.startswith(_CON_ZONA) and not any(fnmatchcase(s, g) for z in zone for g in z.glob):
            errori.append(f"file senza zona: {s}")
    for z in zone:
        errori += [f"glob vuoto: {z.id} {g}" for g in z.file if not any(fnmatchcase(s, g) for s in sorgenti)]
    return errori


def elenco(radice: Path, endpoint: list[Endpoint]) -> None:
    controlli, schede = leggi_controlli(radice), carte(radice)
    coperti = {x for c in controlli for x in c.copre}
    print(f"Controlli: {len(controlli)}, aperti: {sum(c.aperto for c in controlli)}")
    gruppi = {"Endpoint": [f"{m} {p}" for m, p, _ in endpoint], "Route": [f"route:{r}" for r in route_fe(radice)]}
    if schede is None:
        print("Manuali assenti: carte non conteggiate")
    else:
        gruppi["Carte"] = [f"carta:{f}#{t}" for f, titoli in schede.items() for t in titoli]
    for nome, voci in gruppi.items():
        print(f"{nome}: {sum(v in coperti for v in voci)}/{len(voci)} coperti")
    for z in leggi_zone(radice):
        fatte = {c.voce for c in controlli if c.zona == z.id}
        print(f"  {z.id}: {len(fatte)}/{len(VOCI)} voci con un controllo")


# --- scelta delle zone e memoria fra i giri ------------------------------------------------------------------------

def file_cambiati(radice: Path, commit: str) -> list[str] | None:
    """File toccati da `commit` a HEAD; None se il commit non esiste più (rebase o branch cancellato)."""
    p = subprocess.run(["git", "-c", "core.quotepath=off", "diff", "--name-only", "--no-renames", commit, "HEAD", "--"],
                       cwd=radice, capture_output=True, text=True, encoding="utf-8")
    return p.stdout.splitlines() if p.returncode == 0 else None


def _moduli_py(testo: str) -> set[str]:
    fuori = set()
    for n in ast.walk(ast.parse(testo)):
        if isinstance(n, ast.ImportFrom) and n.module and not n.level:
            fuori |= {n.module, *(f"{n.module}.{a.name}" for a in n.names)}
        elif isinstance(n, ast.Import):
            fuori |= {a.name for a in n.names}
    return {m.replace(".", "/") + ".py" for m in fuori}


def _moduli_ts(nome: str, testo: str) -> set[str]:
    fuori = set()
    for m in re.findall(r"""(?:from|import)\s*\(?\s*['"]([^'"]+)['"]""", testo):
        if m.startswith("@/"):
            base = "webapp/src/" + m[2:]
        elif m.startswith("."):
            base = posixpath.normpath(posixpath.join(posixpath.dirname(nome), m))
        else:
            continue
        fuori |= {base + e for e in ("", ".ts", ".tsx", "/index.ts", "/index.tsx")}
    return fuori


def importati(radice: Path, zone: list[Zona]) -> dict[str, set[str]]:
    """Per zona, i file importati direttamente dai suoi: una modifica a un hook o a uno schema rimette la zona in coda."""
    sorgenti = set(_sorgenti(radice))

    @cache
    def diretti(nome: str) -> frozenset[str]:
        if not nome.endswith((".py", ".ts", ".tsx")):
            return frozenset()
        testo = (radice / nome).read_text(encoding="utf-8")
        return frozenset((_moduli_py(testo) if nome.endswith(".py") else _moduli_ts(nome, testo)) & sorgenti)
    per_zona = {z.id: {d for s in sorgenti if any(fnmatchcase(s, g) for g in z.glob) for d in diretti(s)} for z in zone}
    quante = Counter(f for files in per_zona.values() for f in files)
    return {i: {f for f in files if quante[f] <= _MOLTE_ZONE} for i, files in per_zona.items()}


def filtra(zone: list[Zona], includi: list[str], escludi: list[str], edizione: str | None) -> list[Zona]:
    for g in [*includi, *escludi]:
        if not any(fnmatchcase(z.id, g) for z in zone):
            raise ValueError(f"nessuna zona corrisponde a {g}")
    return [z for z in zone
            if (not includi or any(fnmatchcase(z.id, g) for g in includi))
            and not any(fnmatchcase(z.id, g) for g in escludi)
            and (edizione is None or z.tipo == "flusso" or z.id.startswith(f"regola:{edizione}/"))]


def _motivo(z: Zona, controlli: list[Controllo], stato: dict, cambiati: Callable[[str], list[str] | None],
            scoperti: dict[str, dict], dipendenze: dict[str, set[str]]) -> str:
    visto = stato["zone"].get(z.id)
    if not visto:
        return "scoperta"
    diff = cambiati(visto["commit"])
    vicini = dipendenze.get(z.id, set())
    if diff is None or any(f in vicini or any(fnmatchcase(f, g) for g in z.glob) for f in diff):
        return "modificata"
    con_controllo = {c.voce for c in controlli if c.zona == z.id}
    coperta = all(visto["voci"].get(v) == "non_applicabile" or (visto["voci"].get(v) == "fatta" and v in con_controllo)
                  for v in VOCI)
    return "vecchia" if coperta and not scoperti.get(z.id) else "scoperta"


def scegli(zone: list[Zona], controlli: list[Controllo], stato: dict,
           cambiati: Callable[[str], list[str] | None], massimo: int = 8,
           scoperti: dict[str, dict] | None = None, dipendenze: dict[str, set[str]] | None = None) -> list[tuple[Zona, str]]:
    gruppi = ("modificata", "scoperta", "vecchia")

    def chiave(coppia: tuple[Zona, str]):
        z, motivo = coppia
        data = stato["zone"][z.id]["data"] if motivo == "vecchia" else ""
        return gruppi.index(motivo), data, z.tipo, z.id
    return sorted(((z, _motivo(z, controlli, stato, cambiati, scoperti or {}, dipendenze or {})) for z in zone), key=chiave)[:massimo]


def segna(radice: Path, zona: str, commit: str, voci: dict[str, str]) -> None:
    if zona not in {z.id for z in leggi_zone(radice)}:
        raise ValueError(f"zona ignota: {zona}")
    if set(voci) != set(VOCI) or not set(voci.values()) <= {"fatta", "non_applicabile"}:
        raise ValueError(f"servono tutte le voci, fatta o non_applicabile: {', '.join(VOCI)}")
    affermazioni, controlli = _affermazioni(radice, zona), leggi_controlli(radice)
    if not affermazioni:
        raise ValueError(f"mancano le affermazioni di {zona}")
    if scoperte := fonti_scoperte(radice, next(z for z in leggi_zone(radice) if z.id == zona)):
        raise ValueError("pagine o carte senza affermazioni: " + ", ".join(scoperte))
    negate = {v["voce"] for v in affermazioni.values() if set(v["casi"]) - set(v.get("esenti", {}))
              and voci[v["voce"]] == "non_applicabile"}
    if negate:
        raise ValueError(f"voci con affermazioni dichiarate non applicabili: {', '.join(sorted(negate))}")
    if da_provare := casi_da_provare(radice, zona, controlli):
        raise ValueError("casi senza controllo: " + ", ".join(da_provare))
    con_controllo = {c.voce for c in controlli if c.zona == zona}
    senza = [v for v, esito in voci.items() if esito == "fatta" and v not in con_controllo]
    if senza:
        raise ValueError(f"voci fatte senza un controllo: {', '.join(senza)}")
    stato = leggi_stato(radice)
    stato["zone"][zona] = {"commit": commit, "data": date.today().isoformat(), "voci": voci}
    (radice / "tests/caccia/stato.json").write_text(
        json.dumps(stato, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    for flusso in (sys.stdout, sys.stderr):
        getattr(flusso, "reconfigure")(encoding="utf-8")  # la console Windows non è UTF-8
    p = argparse.ArgumentParser(prog="tests.caccia.inventario")
    sub = p.add_subparsers(dest="comando", required=True)
    for nome in ("elenco", "prossimo-id"):
        sub.add_parser(nome)
    sub.add_parser("verifica").add_argument("--contiene", default="", help="solo gli errori che nominano questo testo")
    s = sub.add_parser("scegli")
    s.add_argument("--max", type=int, default=8)
    s.add_argument("--includi", nargs="*", default=[])
    s.add_argument("--escludi", nargs="*", default=[])
    s.add_argument("--edizione", choices=("2014", "2024"))
    sub.add_parser("casi").add_argument("zona")
    sub.add_parser("fonti").add_argument("zona")
    s = sub.add_parser("coda")
    s.add_argument("--budget", type=int, default=200)
    s.add_argument("zone", nargs="+")
    s = sub.add_parser("segna")
    s.add_argument("zona")
    s.add_argument("commit")
    s.add_argument("--voci", nargs="+", required=True, metavar="VOCE=ESITO")
    a = p.parse_args(argv)
    if a.comando == "elenco":
        elenco(RADICE, endpoint_app())
    elif a.comando == "prossimo-id":
        print(prossimo_id(leggi_controlli(RADICE), leggi_stato(RADICE)["ritirati"]))
    elif a.comando == "verifica":
        errori = [e for e in verifica(RADICE, endpoint_app()) if a.contiene in e]
        print("\n".join(errori) or "Nessun errore")
        return 1 if errori else 0
    elif a.comando == "scegli":
        zone = filtra(leggi_zone(RADICE), a.includi, a.escludi, a.edizione)
        controlli = leggi_controlli(RADICE)
        tutte = scegli(zone, controlli, leggi_stato(RADICE), cache(lambda commit: file_cambiati(RADICE, commit)), len(zone),
                       {z.id: casi_da_provare(RADICE, z.id, controlli) for z in zone}, importati(RADICE, leggi_zone(RADICE)))
        for z, motivo in tutte[:a.max]:
            print(f"{z.id}\t{motivo}\t{len(fonti_scoperte(RADICE, z))} fonti da scomporre\t{len(casi_da_provare(RADICE, z.id, controlli))} casi in coda")
        print("Restano:", dict(Counter(m for _, m in tutte[a.max:])) or "nessuna")
    elif a.comando == "fonti":
        print("\n".join(fonti_scoperte(RADICE, next(z for z in leggi_zone(RADICE) if z.id == a.zona))))
    elif a.comando == "coda":
        tutti = coda(RADICE, a.zone, 10**9)
        for zona, caso, testo in tutti[:a.budget]:
            print(f"{zona}\t{caso}\t{testo}")
        print(f"Restano in coda: {max(len(tutti) - a.budget, 0)}")
    elif a.comando == "casi":
        for caso, testo in casi_da_provare(RADICE, a.zona).items():
            print(f"{caso}\t{testo}")
    elif a.comando == "segna":
        segna(RADICE, a.zona, a.commit, dict(v.split("=", 1) for v in a.voci))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
