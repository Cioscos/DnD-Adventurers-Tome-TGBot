"""GET /health espone la versione del server (letta da pyproject.toml)."""
from __future__ import annotations

import tomllib
from pathlib import Path


async def test_health_returns_pyproject_version(client) -> None:
    root = Path(__file__).resolve().parents[2]
    expected = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "version": expected}
