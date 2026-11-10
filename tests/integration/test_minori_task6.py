"""Task 6 dei minori rinviati: punti 26, 27, 50, 51, 53."""
from __future__ import annotations

from api.services import catalog_migration
from tests.integration.rules.test_2014_bard_round2 import _bump
from tests.integration.rules.test_class_mechanisms import _fighter


async def test_minori_50_a_broken_character_does_not_resync_everyone_at_every_start(client, test_session_factory, monkeypatch):
    broken = await _fighter(client, 3)
    await _fighter(client, 3)
    real = catalog_migration.sync_cataloged_features
    seen: list[int] = []

    async def flaky(session, char, lang, **kw):
        seen.append(char.id)
        if char.id == broken:
            raise ValueError("dati rotti")
        return await real(session, char, lang, **kw)

    monkeypatch.setattr(catalog_migration, "sync_cataloged_features", flaky)
    await _bump(test_session_factory)
    assert await catalog_migration.migrate_catalog(test_session_factory) == 1  # l'altro personaggio passa lo stesso
    seen.clear()
    assert await catalog_migration.migrate_catalog(test_session_factory) == 0
    assert seen == []  # al secondo avvio nessuno viene risincronizzato
