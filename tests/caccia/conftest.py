"""Fixture dei controlli: riusa quelle di integrazione, fissa i dadi e permette di cambiare utente."""
from __future__ import annotations

import random

import pytest

from api.auth import get_current_user
from api.main import app
from api.routers import maps, notes, silhouette
from api.services import content_shares
from tests.integration.conftest import (  # noqa: F401
    _isolate_campaign_files, _schema_db, client, rules_catalog, test_session_factory,
)


@pytest.fixture(autouse=True)
def _file_isolati(tmp_path, monkeypatch):
    """I file caricati dai controlli non finiscono mai nella cartella data/ dello sviluppatore."""
    monkeypatch.setattr(maps, "_MAPS_DIR", tmp_path / "maps")
    monkeypatch.setattr(silhouette, "_SIL_DIR", tmp_path / "silhouettes")
    monkeypatch.setattr(notes, "_VOICE_DIR", tmp_path / "voice")
    monkeypatch.setattr(content_shares, "VOICE_NOTES_DIR", tmp_path / "voice")
    monkeypatch.setattr(content_shares, "SHARED_VOICE_DIR", tmp_path / "shared_voice")


@pytest.fixture(autouse=True)
def _seme():
    random.seed(0)


@pytest.fixture
def dadi(monkeypatch):
    """`dadi(3, 5)`: i prossimi `random.randint` danno 3 e 5. Finiti o fuori dai limiti chiesti, il test fallisce."""
    coda: list[int] = []

    def randint(a: int, b: int) -> int:
        assert coda, f"dado non previsto: randint({a}, {b})"
        v = coda.pop(0)
        assert a <= v <= b, f"valore {v} fuori da {a}-{b}"
        return v

    def imposta(*valori: int) -> None:
        coda.extend(valori)
        monkeypatch.setattr(random, "randint", randint)
    return imposta


@pytest.fixture
def come_utente(client):  # noqa: F811
    """`come_utente(9002)`: da qui in poi le richieste arrivano da quell'utente."""
    def imposta(user_id: int) -> None:
        app.dependency_overrides[get_current_user] = lambda: user_id
    return imposta
