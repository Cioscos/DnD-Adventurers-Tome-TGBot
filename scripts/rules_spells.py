"""Lettura delle tabelle incantesimi dei manuali (docs/superpowers/rules/{2014,2024}/spells.md).

Ogni riga: titolo IT | titolo EN | livello | scuola | classi | tempo | gittata | componenti | durata |
concentrazione | rituale | effetto meccanico (nostro riassunto) | pagina.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Nomenclatura italiana 2014: Evocazione = Conjuration, Invocazione = Evocation.
SCHOOLS = {
    "abiurazione": "abjuration", "evocazione": "conjuration", "divinazione": "divination", "ammaliamento": "enchantment",
    "invocazione": "evocation", "illusione": "illusion", "necromanzia": "necromancy", "trasmutazione": "transmutation",
}
SCHOOLS.update({v: v for v in SCHOOLS.values()})
CLASSES = {"bardo": "bard", "chierico": "cleric", "druido": "druid", "mago": "wizard", "paladino": "paladin",
           "ranger": "ranger", "stregone": "sorcerer", "warlock": "warlock", "artefice": "artificer"}
# Nomi del manuale che nel SRD cambiano oltre al possessivo.
MANUAL_TO_SRD = {"Bigby's Hand": "arcane-hand", "Mordenkainen's Sword": "arcane-sword",
                 "Nystul's Magic Aura": "arcanists-magic-aura", "Wall of Wind": "wind-wall"}
YES = {"sì", "si", "yes"}


@dataclass
class RuleSpell:
    name_it: str
    name_en: str
    level: int
    school: str
    classes: list[str]
    casting_time: str
    range_text: str
    range_ft: int | None
    components: list[str]
    material: str | None
    duration: str
    concentration: bool
    ritual: bool
    summary_it: str


def range_ft(s: str) -> int | None:
    """Gittata in piedi; contatto, incantatore, vista e simili -> None."""
    s = s.strip()
    if m := re.search(r"\((\d+)\s*ft\)", s):
        return int(m[1])
    if m := re.fullmatch(r"(\d+)\s*(feet|foot|ft\.?|piedi)", s, re.I):
        return int(m[1])
    if m := re.fullmatch(r"(\d+)\s*(miles?|miglia|miglio)", s, re.I):
        return int(m[1]) * 5280
    if m := re.fullmatch(r"(\d+(?:,\d+)?)\s*(m|metri)", s, re.I):
        return round(float(m[1].replace(",", ".")) / 1.5) * 5
    return None


def _components(s: str) -> tuple[list[str], str | None]:
    m = re.search(r"\((.*)\)\s*$", s)
    letters = re.sub(r"\(.*\)\s*$", "", s)
    return [c.strip() for c in letters.split(",") if c.strip() in ("V", "S", "M")], (m[1].strip() if m else None)


def parse_table(path: Path) -> list[RuleSpell]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ") or line.startswith("| titolo"):
            continue
        c = [x.strip() for x in line.split("|")[1:-1]]
        if len(c) != 13:
            raise ValueError(f"riga con {len(c)} celle: {line[:80]}")
        it, en, lvl, school, classes, cast, rng, comps, dur, conc, rit, summary, _page = c
        try:
            parts, material = _components(comps)
            out.append(RuleSpell(
                name_it=it, name_en=en, level=int(lvl), school=SCHOOLS[school.lower()],
                classes=sorted(CLASSES[k.strip().lower()] for k in classes.split(",")),
                casting_time=cast, range_text=rng, range_ft=range_ft(rng), components=parts, material=material,
                duration=dur, concentration=conc.lower() in YES, ritual=rit.lower() in YES, summary_it=summary))
        except (KeyError, ValueError) as e:
            raise ValueError(f"{en}: valore non riconosciuto {e}") from e
    return out


def phb_index(name_en: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"['’]", "", name_en.lower())).strip("-")


def srd_index_for(name_en: str, srd_indexes: set[str]) -> str | None:
    if name_en in MANUAL_TO_SRD:
        return MANUAL_TO_SRD[name_en]
    for cand in (phb_index(name_en), phb_index(re.sub(r"^[A-Z][a-z]+['’]s ", "", name_en))):
        if cand in srd_indexes:
            return cand
    return None
