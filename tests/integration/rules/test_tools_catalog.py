"""Catalogo degli strumenti (punto 3 dei lavori successivi)."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from core.data.tools import TOOLS, tool_key, tool_label


def test_catalog_has_every_category():
    counts = Counter(t.category for t in TOOLS.values())
    assert counts["artisan"] == 17 and counts["instrument"] == 10 and counts["gaming"] == 4
    assert counts["thieves"] == 1 and counts["vehicle"] == 2 and counts["kit"] == 5
    assert all(t.ability in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
               for t in TOOLS.values())


def test_tool_key_aliases():
    assert tool_key("Arnesi da scasso") == tool_key("thieves' TOOLS") == "thieves_tools"
    assert tool_key("Strumenti da ladro") == "thieves_tools"
    assert tool_key("Strumenti da alchimista") == tool_key("Scorte da Alchimista") == "alchemists_supplies"
    assert tool_key("Strumenti musicali") is None and tool_key("Set da gioco") is None
    assert tool_key("Liuto") == tool_key(" lute ") == "lute"
    assert tool_label("lute", "it") == "Liuto" and tool_label("lute", "en") == "Lute"


def test_export_matches_catalog():
    from scripts.export_tools import build
    path = Path(__file__).resolve().parents[3] / "webapp" / "src" / "data" / "tools.json"
    assert json.loads(path.read_text(encoding="utf-8")) == build()
