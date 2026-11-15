"""Rigenera species-2024.json, backgrounds-2024.json ed equipment-2024.json (specchio del frontend) da core/data/*_2024.py.

L'equipaggiamento 2024 deriva da equipment.json (SRD 2014, generato) con le differenze del PHB 2024 pag. 214-215.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from core.data.backgrounds_2024 import BACKGROUNDS_2024, GOLD_OPTION
from core.data.species_2024 import SPECIES_2024

SRD = Path(__file__).resolve().parent.parent / "webapp" / "src" / "data" / "srd"
FILES = {n: SRD / f"{n}-2024.json" for n in ("species", "backgrounds", "equipment")}


def _species() -> list[dict]:
    return [{
        "key": s.key, "name": s.name, "size": list(s.size), "speed_ft": s.speed_ft,
        "choices": [{"key": c.key, "label": c.label, "from_level": c.from_level,
                     "options": [{"key": o, "label": c.option_labels[o]} for o in c.options]} for c in s.choices],
        "traits": [{"key": k, "name": n, "summary": sm} for k, n, sm in s.traits],
    } for s in SPECIES_2024.values()]


def _backgrounds() -> dict:
    return {"gold_option": GOLD_OPTION, "items": [{
        "key": b.key, "name": b.name, "abilities": list(b.abilities), "origin_feat": b.origin_feat,
        "skills": list(b.skills), "tool": list(b.tool) if isinstance(b.tool, tuple) else b.tool,
        "equipment": b.equipment, "feat_list": b.feat_list,
    } for b in BACKGROUNDS_2024.values()]}


def _prop(item: dict, *add: str) -> None:
    item["properties"] = sorted({*item["properties"], *add})


def _equipment() -> dict:
    data = json.loads((SRD / "equipment.json").read_text(encoding="utf-8"))
    items = {e["index"]: copy.deepcopy(e) for e in data["items"] if e["index"] != "net"}  # PHB 2024: la Rete è un attrezzo
    lance = items["lance"]
    lance.update(damage_dice="1d10")
    _prop(lance, "prop_heavy", "prop_two_handed")
    items["trident"].update(damage_dice="1d8", versatile_dice="1d10")
    items["war-pick"].update(versatile_dice="1d10")
    _prop(items["war-pick"], "prop_versatile")
    base = {"weight_lb": 0, "damage_type": "piercing", "weapon_category": "martial", "weapon_range": "ranged",
            "versatile_dice": None, "thrown_range_ft": None}
    items["musket"] = {"index": "musket", "name": {"en": "Musket", "it": "Moschetto"}, **base, "weight_lb": 10,
                       "damage_dice": "1d12", "range_ft": 40, "mastery": "slow",
                       "properties": ["prop_ammunition", "prop_loading", "prop_two_handed"]}
    items["pistol"] = {"index": "pistol", "name": {"en": "Pistol", "it": "Pistola"}, **base, "weight_lb": 3,
                       "damage_dice": "1d10", "range_ft": 30, "mastery": "vex",
                       "properties": ["prop_ammunition", "prop_loading"]}
    return {"_meta": {**data["_meta"], "source": "SRD 2014 + differenze PHB 2024 (pag. 214-215)"}, "items": list(items.values())}


def build_all() -> dict[Path, object]:
    return {FILES["species"]: _species(), FILES["backgrounds"]: _backgrounds(), FILES["equipment"]: _equipment()}


if __name__ == "__main__":
    for path, data in build_all().items():
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
