"""Cataloghi incantesimi per edizione con i nomi dei manuali.

    uv run python scripts/build_spell_catalogs.py update-2014   # rinomina e aggiunge i non SRD a spells.json
    uv run python scripts/build_spell_catalogs.py build-2024    # genera spells-2024.json dal SRD 5.2 + non SRD
    uv run python scripts/build_spell_catalogs.py todo-en OUT   # elenca i testi inglesi mancanti dei non SRD

Non rilancia build_srd_catalog.py (cancellerebbe le traduzioni). L'italiano dei testi SRD 2024 arriva poi da
srd_translation_batches.py (kind ``spells-2024``); i non SRD usano il nostro riassunto (it) e
``scripts/data/phb_spells_en.json`` (en).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rules_spells import MECHANICS_OVERRIDES, RuleSpell, mechanics, parse_table, phb_index, srd_index_for  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "webapp" / "src" / "data" / "srd"
RULES = ROOT / "docs" / "superpowers" / "rules"
EN_FILE = Path(__file__).resolve().parent / "data" / "phb_spells_en.json"
API = "https://www.dnd5eapi.co/api/2024"

# --- tempi e durate: sempre ricondotti alle chiavi del glossario -------------------------------------------------

_TIME_WORDS = {"azione bonus": "1 bonus action", "bonus action": "1 bonus action", "azione": "1 action",
               "action": "1 action", "reazione": "1 reaction", "reaction": "1 reaction"}


def norm_time(s: str, g: dict) -> str:
    t = re.split(r"\s+o\s+|\s+or\s+|[,(]", s.strip().lower())[0].strip()
    t = re.sub(r"^1 ", "", t) if re.sub(r"^1 ", "", t) in _TIME_WORDS else t
    if t in _TIME_WORDS:
        return _TIME_WORDS[t]
    inv = {v.lower(): k for k, v in g["casting_times"].items()} | {k.lower(): k for k in g["casting_times"]}
    if t in inv:
        return inv[t]
    raise ValueError(f"tempo di lancio non riconosciuto: {s!r}")


def norm_duration(s: str, g: dict, concentration: bool = False) -> str:
    t = s.strip().lower()
    durs = g["durations"]
    plain = {v.lower(): k for k, v in durs.items() if not k.startswith("Up to")} | {k.lower(): k for k in durs if not k.startswith("Up to")}
    if re.match(r"(finch[eé]|fino a dissolvimento|until dispelled)", t):
        return "Until dispelled"
    if m := re.fullmatch(r"(?:concentrazione|concentration),?\s*(?:fino a |up to )?(.+)", t):
        base = plain.get(m[1].strip())
        if base and f"Up to {base}" in durs:
            return f"Up to {base}"
    t = re.sub(r"^(fino a|up to)\s+", "", t)
    if t in plain:  # concentrazione dichiarata solo dal flag: la durata va comunque nella forma «fino a»
        return f"Up to {plain[t]}" if concentration and f"Up to {plain[t]}" in durs else plain[t]
    raise ValueError(f"durata non riconosciuta: {s!r}")


def localize(key: str, table: dict) -> dict:
    return {"en": key, "it": table[key]}


# --- gittata e area -----------------------------------------------------------------------------------------------

_RANGE_WORDS = {"contatto": "Touch", "touch": "Touch", "incantatore": "Self", "personale": "Self", "self": "Self",
                "vista": "Sight", "linea di vista": "Sight", "sight": "Sight", "illimitata": "Unlimited",
                "unlimited": "Unlimited", "speciale": "Special", "special": "Special"}
_RANGE_IT = {"Touch": "Contatto", "Self": "Personale", "Sight": "Linea di vista", "Unlimited": "Illimitata",
             "Special": "Speciale"}
_RANGE_OVERRIDES = {"1,5 km": "1 mile", "1 miglio": "1 mile", "1 mile": "1 mile", "1,6 km (1 mile)": "1 mile",
                    "750 km": "500 miles", "800 km (500 miglia)": "500 miles", "500 miles": "500 miles"}
_AREA_IT = {"raggio": "sphere", "sfera": "sphere", "semisfera": "sphere", "cono": "cone", "linea": "line", "cubo": "cube"}


def range_en(text: str, ft: int | None) -> str:
    t = text.strip()
    if t in _RANGE_OVERRIDES:
        return _RANGE_OVERRIDES[t]
    if ft is not None and ft < 5280:
        return f"{ft} feet"
    low = t.lower()
    if low.startswith("incantatore") or low.startswith("personale") or low.startswith("self"):
        return "Self"
    if low in _RANGE_WORDS:
        return _RANGE_WORDS[low]
    raise ValueError(f"gittata non riconosciuta: {text!r}")


def range_text(en: str) -> dict:
    if en in _RANGE_IT:
        return {"en": en, "it": _RANGE_IT[en]}
    if m := re.fullmatch(r"(\d+) feet", en):
        return {"en": en, "it": f"{m[1]} piedi"}
    if m := re.fullmatch(r"(\d+) miles?", en):
        return {"en": en, "it": f"{m[1]} {'miglio' if m[1] == '1' else 'miglia'}"}
    raise ValueError(f"gittata non riconosciuta: {en!r}")


def area_from_it(text: str) -> dict | None:
    m = re.search(r"(raggio|semisfera|sfera|cono|linea|cubo)\D*?(\d+(?:,\d+)?)\s*(m|metri)\b", text, re.I)
    return {"type": _AREA_IT[m[1].lower()], "size_ft": round(float(m[2].replace(",", ".")) / 1.5) * 5} if m else None


_LINE_EN = re.compile(r"(\d+)-foot-long[^.]*?Line|Line (\d+) feet long", re.I)
_AREA_EN = re.compile(r"(\d+)-foot(?:-radius|-long)?[\s-](?:[\w-]+\s)?(Sphere|Cone|Cube|Cylinder|Emanation|Line)", re.I)


def area_from_en(text: str) -> dict | None:
    if m := _LINE_EN.search(text):
        return {"type": "line", "size_ft": int(m[1] or m[2])}
    m = _AREA_EN.search(text)
    return {"type": m[2].lower(), "size_ft": int(m[1])} if m else None


# --- voci -----------------------------------------------------------------------------------------------------------

def phb_entry(row: RuleSpell, index: str, en: dict, g: dict) -> dict:
    mech = {**mechanics(row.summary_it), **MECHANICS_OVERRIDES.get(index, {})}
    rng = range_en(row.range_text, row.range_ft)
    return {
        "index": index, "name": {"en": row.name_en, "it": row.name_it}, "level": row.level, "school": row.school,
        "casting_time": localize(norm_time(row.casting_time, g), g["casting_times"]),
        "range_ft": row.range_ft if rng.endswith("feet") else None, "range_text": range_text(rng),
        "area": area_from_it(row.range_text), "components": row.components,
        "material": {"en": en["material"], "it": row.material} if row.material else None,
        "duration": localize(norm_duration(row.duration, g, row.concentration), g["durations"]),
        "concentration": row.concentration, "ritual": row.ritual,
        "desc": {"en": en["desc"], "it": row.summary_it}, "higher_level": None, **mech,
        "classes": row.classes, "source": "phb",
    }


def _missing_en(rows: list[tuple[RuleSpell, str]], en: dict) -> list[str]:
    return [i for r, i in rows if not (en.get(i, {}).get("desc") and (not r.material or en[i].get("material")))]


def _phb_rows(rows: list[RuleSpell], srd: set[str]) -> list[tuple[RuleSpell, str]]:
    return [(r, phb_index(r.name_en)) for r in rows if srd_index_for(r.name_en, srd) is None]


def merge_2014(doc: dict, rows: list[RuleSpell], en: dict, g: dict) -> dict:
    items = [i for i in doc["items"] if i.get("source") != "phb"]
    srd = {i["index"] for i in items}
    phb = _phb_rows(rows, srd)
    if missing := _missing_en(phb, en):
        raise SystemExit(f"testo inglese mancante in phb_spells_en.json (2014): {', '.join(missing)}")
    by = {i["index"]: i for i in items}
    for r in rows:
        if (idx := srd_index_for(r.name_en, srd)) is None:
            continue
        item = by[idx]
        old = item["name"].get("it")
        aliases = item.get("aliases", [])
        if old and old.casefold() != r.name_it.casefold() and old not in aliases:
            aliases = [*aliases, old]
        item["name"] = {"en": r.name_en, "it": r.name_it}
        if aliases:
            item["aliases"] = aliases
        item["classes"] = r.classes
        item["source"] = "srd"
    items += [phb_entry(r, i, en[i], g) for r, i in phb]
    return {"_meta": {**doc["_meta"], "phb": "nomi dei manuali; non SRD: riassunti nostri (source: phb)"},
            "items": sorted(items, key=lambda i: i["index"])}


def _dice(d: str | None) -> str | None:
    m = re.match(r"\s*(\d+d\d+(?:\s*\+\s*\d+)?)", d or "")
    return m[1].replace(" ", "") if m else None


_MECH = ("attack_type", "save_ability", "damage_dice", "damage_type", "higher_levels_dice", "area")
_UP_EN = re.compile(r"increases by (\d+d\d+) for each (?:spell )?slot level above", re.I)
_SAVE_EN = re.compile(r"(Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma) saving throw")
_ATK_EN = re.compile(r"\b(?:melee|ranged) spell attack", re.I)


def srd_2024_entry(s: dict, row: RuleSpell, g: dict, prev: dict | None = None) -> dict:
    desc = re.sub(r"\n\s*", "\n\n", s["description"].strip())
    higher = (s.get("higher_level") or "").strip() or None
    if higher and higher in desc:
        higher = None
    dmg = s.get("damage") or {}
    table = dmg.get("damage_at_slot_level") or dmg.get("damage_at_character_level") or {}
    keys = sorted(table, key=int)
    base = _dice(table[keys[0]]) if keys else None
    inc = None
    if len(keys) > 1 and all(_dice(table[k]) for k in keys):
        parts = [tuple(map(int, _dice(table[k]).split("+")[0].split("d"))) for k in keys]
        steps = {b[0] - a[0] for a, b in zip(parts, parts[1:])}
        if len(steps) == 1 and len({p[1] for p in parts}) == 1 and (n := steps.pop()) > 0:
            inc = f"{n}d{parts[0][1]}"
    if inc is None and base and s["level"] > 0 and (m := _UP_EN.search(f"{higher or ''} {desc}")):
        inc = m[1]
    save = _SAVE_EN.search(desc)
    raw = re.sub(r"\s*Components?:.*$", "", s["range"]).strip()  # l'API a volte accoda le componenti
    rng = raw if re.fullmatch(r"\d+ feet", raw) else range_en(raw, None)
    out = {
        "index": s["index"], "name": {"en": row.name_en, "it": row.name_it}, "level": s["level"],
        "school": s["school"]["index"], "casting_time": localize(norm_time(s["casting_time"], g), g["casting_times"]),
        "range_ft": int(rng.split()[0]) if rng.endswith("feet") else None, "range_text": range_text(rng),
        "area": area_from_en(desc), "components": s["components"],
        "material": {"en": s["material"].strip()} if s.get("material") else None,
        "duration": localize(norm_duration(s["duration"], g, s["concentration"]), g["durations"]),
        "concentration": s["concentration"], "ritual": s["ritual"],
        "desc": {"en": desc}, "higher_level": {"en": higher} if higher else None,
        "attack_type": "ATK" if _ATK_EN.search(desc) else ("SAVE" if save else None),
        "save_ability": save[1][:3].lower() if save else None,
        "damage_dice": base, "damage_type": dmg.get("damage_type", {}).get("index") if dmg else None,
        "higher_levels_dice": inc, "classes": row.classes, "source": "srd",
    }
    # Il 2024 dell'API non dice tutto (Dardo Incantato senza danni): dove resta vuoto vale la voce 2014 omonima.
    for f in _MECH:
        if out[f] is None and prev and prev.get(f) is not None:
            out[f] = prev[f]
    return out



def build_2024(api: list[dict], rows: list[RuleSpell], en: dict, g: dict, prev14: dict | None = None) -> dict:
    srd = {s["index"] for s in api}
    by_srd = {i: r for r in rows if (i := srd_index_for(r.name_en, srd))}
    if missing := sorted(srd - set(by_srd)):
        raise SystemExit(f"incantesimi SRD 2024 senza riga nella tabella: {', '.join(missing)}")
    phb = _phb_rows(rows, srd)
    if missing := _missing_en(phb, en):
        raise SystemExit(f"testo inglese mancante in phb_spells_en.json (2024): {', '.join(missing)}")
    items = [srd_2024_entry(s, by_srd[s["index"]], g, (prev14 or {}).get(s["index"])) for s in api] + [phb_entry(r, i, en[i], g) for r, i in phb]
    return {"_meta": {"source": f"{API} (D&D 5e SRD 5.2)", "license": "CC-BY-4.0",
                      "generated_at": date.today().isoformat(),
                      "phb": "nomi dei manuali; non SRD: riassunti nostri (source: phb)"},
            "items": sorted(items, key=lambda i: i["index"])}


# --- CLI ------------------------------------------------------------------------------------------------------------

def _read(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _write(p: Path, doc: dict) -> None:
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


async def _fetch_2024() -> list[dict]:
    import httpx
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        idx = (await c.get(f"{API}/spells")).json()["results"]
        out = []
        for x in idx:  # una alla volta, con pazienza: l'API risponde vuoto se la si incalza
            for wait in (0, 1, 3, 10):
                await asyncio.sleep(wait)
                r = await c.get(f"{API}/spells/{x['index']}")
                if r.status_code == 200 and r.content:
                    out.append(r.json())
                    break
            else:
                raise SystemExit(f"API 2024: {x['index']} non risponde")
        return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("update-2014")
    sub.add_parser("build-2024")
    t = sub.add_parser("todo-en")
    t.add_argument("out", type=Path)
    a = ap.parse_args()
    g = _read(DATA / "glossary-it.json")
    en = _read(EN_FILE) if EN_FILE.exists() else {"2014": {}, "2024": {}}
    rows14, rows24 = parse_table(RULES / "2014" / "spells.md"), parse_table(RULES / "2024" / "spells.md")
    if a.cmd == "todo-en":
        srd14 = {i["index"] for i in _read(DATA / "spells.json")["items"] if i.get("source") != "phb"}
        srd24 = {s["index"] for s in json.loads(__import__("urllib.request").request.urlopen(f"{API}/spells").read())["results"]}
        todo = {ed: {i: {"desc_it": r.summary_it, "material_it": r.material}
                     for r, i in _phb_rows(rows, srd) if i in _missing_en([(r, i)], en.get(ed, {}))}
                for ed, rows, srd in (("2014", rows14, srd14), ("2024", rows24, srd24))}
        _write(a.out, todo)
        print({ed: len(v) for ed, v in todo.items()})
        return
    if a.cmd == "update-2014":
        doc = merge_2014(_read(DATA / "spells.json"), rows14, en["2014"], g)
        _write(DATA / "spells.json", doc)
        print(f"spells: {len(doc['items'])}")
    else:
        prev14 = {i["index"]: i for i in _read(DATA / "spells.json")["items"]}
        doc = build_2024(asyncio.run(_fetch_2024()), rows24, en["2024"], g, prev14)
        old = DATA / "spells-2024.json"
        if old.exists():  # non perdere le traduzioni già fatte
            prev = {i["index"]: i for i in _read(old)["items"]}
            for item in doc["items"]:
                for f in ("desc", "higher_level", "material"):
                    p = prev.get(item["index"], {}).get(f)
                    if item.get(f) and p and p.get("en") == item[f]["en"] and "it" in p:
                        item[f]["it"] = p["it"]
        _write(old, doc)
        print(f"spells-2024: {len(doc['items'])}")


if __name__ == "__main__":
    main()
