#!/usr/bin/env python3
"""Parser for dnd5e_classi.md -> webapp/src/data/class-progression.json.

Reads the Italian-labelled D&D 5e class progression tables and produces a
structured JSON consumed by the webapp multiclass level-up modal (Gruppo G).
Run manually whenever dnd5e_classi.md changes.

Usage:
    uv run python scripts/parse_class_progression.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MD_PATH = REPO_ROOT / "dnd5e_classi.md"
OUT_PATH = REPO_ROOT / "webapp" / "src" / "data" / "class-progression.json"

EN_TO_IT: dict[str, str] = {
    "Barbarian": "Barbaro",
    "Bard": "Bardo",
    "Cleric": "Chierico",
    "Druid": "Druido",
    "Fighter": "Guerriero",
    "Monk": "Monaco",
    "Paladin": "Paladino",
    "Ranger": "Ranger",
    "Rogue": "Ladro",
    "Sorcerer": "Stregone",
    "Warlock": "Warlock",
    "Wizard": "Mago",
}

FEATURES_LABELS = {"Caratteristiche", "Features"}
PB_LABELS = {"Bonus Competenza", "Bonus Comp."}
SLOT_PATTERN = re.compile(r"^([1-9])°$")
LEVEL_PATTERN = re.compile(r"^(\d+)°$")
SEPARATOR_PATTERN = re.compile(r"^\|[\s:|-]+\|?\s*$")


def _split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _parse_int_or_zero(s: str) -> int:
    s = s.strip()
    if s in ("—", "-", ""):
        return 0
    try:
        return int(s)
    except ValueError:
        return 0


def _parse_class_table(rows: list[str]) -> list[dict]:
    """Parse one class's markdown table rows and return 20-level progression."""
    if len(rows) < 2:
        raise ValueError("table too short")
    header = _split_row(rows[0])

    feat_idx = next((i for i, h in enumerate(header) if h in FEATURES_LABELS), None)
    pb_idx = next((i for i, h in enumerate(header) if h in PB_LABELS), None)
    if feat_idx is None:
        raise ValueError(f"no Caratteristiche column in header: {header}")
    if pb_idx is None:
        raise ValueError(f"no Bonus Comp. column in header: {header}")

    # Standard spellcaster columns 1°..9°
    slot_cols: dict[int, int] = {}
    for i, h in enumerate(header):
        m = SLOT_PATTERN.match(h)
        if m:
            slot_cols[int(m.group(1))] = i

    # Warlock pact magic columns
    warlock_count_idx = next((i for i, h in enumerate(header) if h == "Slot"), None)
    warlock_level_idx = next((i for i, h in enumerate(header) if h == "Livello Slot"), None)
    is_warlock = warlock_count_idx is not None and warlock_level_idx is not None
    has_casting = bool(slot_cols) or is_warlock

    progression: list[dict] = []
    for row in rows[1:]:
        if SEPARATOR_PATTERN.match(row):
            continue
        cells = _split_row(row)
        if not cells or not LEVEL_PATTERN.match(cells[0]):
            continue
        level = int(cells[0].rstrip("°"))
        if level < 1 or level > 20:
            continue

        features = cells[feat_idx] if feat_idx < len(cells) else "—"
        pb_raw = cells[pb_idx].replace("+", "").strip() if pb_idx < len(cells) else "0"
        pb = int(pb_raw) if pb_raw.isdigit() else 0

        if has_casting:
            spell_slots = [0] * 9
            if is_warlock:
                count = _parse_int_or_zero(cells[warlock_count_idx])
                lvl_str = cells[warlock_level_idx].strip()
                lvl_m = re.match(r"^(\d+)°?$", lvl_str)
                slot_level = int(lvl_m.group(1)) if lvl_m else 0
                if 1 <= slot_level <= 9 and count > 0:
                    spell_slots[slot_level - 1] = count
            else:
                for lvl, idx in slot_cols.items():
                    if idx < len(cells):
                        spell_slots[lvl - 1] = _parse_int_or_zero(cells[idx])
        else:
            spell_slots = None

        progression.append(
            {
                "features": features,
                "proficiency_bonus": pb,
                "spell_slots": spell_slots,
            }
        )

    return progression


def main() -> None:
    if not MD_PATH.exists():
        raise SystemExit(f"missing source: {MD_PATH}")

    text = MD_PATH.read_text(encoding="utf-8")
    # Split on class headers (## ClassName)
    sections = re.split(r"^## ", text, flags=re.MULTILINE)[1:]

    out: dict[str, list[dict]] = {}
    for section in sections:
        lines = section.splitlines()
        if not lines:
            continue
        name_en = lines[0].strip()
        if name_en not in EN_TO_IT:
            continue
        name_it = EN_TO_IT[name_en]
        table_lines = [ln for ln in lines[1:] if ln.startswith("|")]
        progression = _parse_class_table(table_lines)
        if len(progression) != 20:
            raise SystemExit(
                f"{name_en}: expected 20 levels, parsed {len(progression)}"
            )
        out[name_it] = progression

    missing = set(EN_TO_IT.values()) - set(out.keys())
    if missing:
        raise SystemExit(f"missing classes in output: {sorted(missing)}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    rel = OUT_PATH.relative_to(REPO_ROOT)
    print(f"wrote {rel}: {len(out)} classes x 20 levels")


if __name__ == "__main__":
    main()
