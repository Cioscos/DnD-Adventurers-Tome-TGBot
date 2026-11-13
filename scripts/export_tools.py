"""Rigenera webapp/src/data/tools.json dal catalogo core/data/tools.py (lo specchio del frontend)."""
from __future__ import annotations

import json
from pathlib import Path

from core.data.tools import TOOLS

DATA = Path(__file__).resolve().parent.parent / "webapp" / "src" / "data"
_ORDER = ("artisan", "gaming", "instrument", "kit", "thieves", "vehicle")


def build() -> list[dict]:
    tools = sorted(TOOLS.values(), key=lambda t: (_ORDER.index(t.category), t.it.lower()))
    return [{"key": t.key, "it": t.it, "en": t.en, "category": t.category, "ability": t.ability} for t in tools]


if __name__ == "__main__":
    (DATA / "tools.json").write_text(json.dumps(build(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
