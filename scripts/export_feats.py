"""Rigenera webapp/src/data/feats2024.json e feats2014.json dai cataloghi core/data/feats*.py (lo specchio del frontend)."""
from __future__ import annotations

import json
from pathlib import Path

from core.data.feats import FEATS, FeatSpec
from core.data.feats_2024 import FEATS_2024
from core.rules.catalog.feats import FEAT_NEEDS
from core.rules.catalog.y2014.fighter import MANEUVERS

DATA = Path(__file__).resolve().parent.parent / "webapp" / "src" / "data"
# Scelte da un elenco fisso che la webapp non ha altrove: le manovre di Adepto Marziale
_CHOICES = {"martial_adept": [{"key": k, "name": {"it": it, "en": en}} for k, it, en in MANEUVERS]}


def build(feats: list[FeatSpec]) -> list[dict]:
    return [{
        "key": f.key, "name": f.name, "summary": f.summary, "category": f.category,
        "abilities": f.ability_increase, "min_level": f.min_level, "max_score": f.max_score,
        "prereq_abilities": {"any_of": list(f.prereq_abilities[0]), "min": f.prereq_abilities[1]}
        if f.prereq_abilities else None,
        "needs_spellcasting": f.needs_spellcasting, "repeatable": f.repeatable,
        "prereq_armor": f.prereq_armor, "needs_fighting_style": f.needs_fighting_style,
        "needs": list(FEAT_NEEDS.get(f"feat.{f.key}", ())),
        **({"choices": _CHOICES[f.key]} if f.key in _CHOICES else {}),
    } for f in feats]


def write(name: str, feats: list[FeatSpec]) -> None:
    (DATA / name).write_text(json.dumps(build(feats), ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    write("feats2024.json", FEATS_2024)
    write("feats2014.json", list(FEATS.values()))
