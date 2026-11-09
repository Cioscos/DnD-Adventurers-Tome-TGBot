"""Ogni condizione ``custom:`` del catalogo ha un'etichetta in italiano e in inglese (I8): mai la chiave grezza."""
from __future__ import annotations

import json
import re
from pathlib import Path

from core.data.labels import CUSTOM_CONDITION_LABELS, condition_label

ROOT = Path(__file__).resolve().parents[3]
LOCALES = ROOT / "webapp" / "src" / "locales"


def _catalog_customs() -> set[str]:
    found: set[str] = set()
    for path in (ROOT / "core" / "rules" / "catalog").rglob("*.py"):
        found |= set(re.findall(r"custom:(\w+)", path.read_text(encoding="utf-8")))
    return found


def test_the_catalog_uses_custom_conditions_so_the_scan_is_not_empty():
    assert {"turned", "thoughts_read"} <= _catalog_customs()


def test_every_custom_condition_of_the_catalog_has_a_label_in_both_languages():
    for slug in sorted(_catalog_customs()):
        assert set(CUSTOM_CONDITION_LABELS[slug]) == {"it", "en"} and all(CUSTOM_CONDITION_LABELS[slug].values()), slug
        assert condition_label(f"custom:{slug}") == CUSTOM_CONDITION_LABELS[slug]["it"]
        for lang in ("it", "en"):
            names = json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8"))["character"]["target_effect"]["custom"]
            assert names.get(slug) == CUSTOM_CONDITION_LABELS[slug][lang], (lang, slug)


def test_the_client_helper_translates_every_custom_condition_of_the_catalog():
    source = (ROOT / "webapp" / "src" / "lib" / "conditions.ts").read_text(encoding="utf-8")
    listed = set(re.findall(r"'(\w+)'", re.search(r"CATALOG_CUSTOM = \[(.*?)\]", source).group(1)))
    assert _catalog_customs() <= listed
