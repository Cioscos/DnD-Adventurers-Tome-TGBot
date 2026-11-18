"""``cached_features``: nel blocco i privilegi attivi si calcolano una volta per personaggio, fuori sempre."""
from __future__ import annotations

from types import SimpleNamespace

import core.rules.catalog as catalog
from core.rules.catalog import active_features, cached_features


def test_nel_blocco_una_volta_fuori_sempre(monkeypatch):
    calls = []
    monkeypatch.setattr(catalog, "_active_features", lambda char: calls.append(char) or [("spec", char)])
    a, b = SimpleNamespace(), SimpleNamespace()

    active_features(a)
    active_features(a)
    assert len(calls) == 2  # fuori dal blocco nessuna memoria

    with cached_features():
        first = active_features(a)
        first.append("sporco")  # chi riceve la lista può modificarla senza sporcare la memoria
        assert active_features(a) == [("spec", a)]
        assert active_features(b) == [("spec", b)]
        assert len(calls) == 4  # una volta per personaggio

    active_features(a)
    assert len(calls) == 5  # uscito dal blocco, la memoria non resta
