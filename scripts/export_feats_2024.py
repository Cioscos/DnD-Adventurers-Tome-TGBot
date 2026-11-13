"""Rigenera webapp/src/data/feats2024.json dal catalogo core/data/feats_2024.py (lo specchio del frontend)."""
from __future__ import annotations

import json
from pathlib import Path

from core.data.feats_2024 import FEATS_2024
from core.rules.catalog.feats import FEAT_NEEDS

TARGET = Path(__file__).resolve().parent.parent / "webapp" / "src" / "data" / "feats2024.json"


def build() -> list[dict]:
    return [{
        "key": f.key, "name": f.name, "summary": f.summary, "category": f.category,
        "abilities": f.ability_increase, "min_level": f.min_level, "max_score": f.max_score,
        "prereq_abilities": {"any_of": list(f.prereq_abilities[0]), "min": f.prereq_abilities[1]}
        if f.prereq_abilities else None,
        "needs_spellcasting": f.needs_spellcasting, "repeatable": f.repeatable,
        "needs": list(FEAT_NEEDS.get(f"feat.{f.key}", ())),
    } for f in FEATS_2024]


if __name__ == "__main__":
    TARGET.write_text(json.dumps(build(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
