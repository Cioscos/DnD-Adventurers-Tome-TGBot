"""Versione del server, letta una volta da pyproject.toml (None se non leggibile)."""
from __future__ import annotations

import tomllib
from pathlib import Path


def _read() -> str | None:
    try:
        path = Path(__file__).resolve().parents[1] / "pyproject.toml"
        return tomllib.loads(path.read_text(encoding="utf-8"))["project"]["version"]
    except Exception:
        return None


APP_VERSION: str | None = _read()
