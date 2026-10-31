"""La migrazione converte class_resources in Ability e droppa la tabella.

Usa un engine SQLite sincrono e self-contained: la FK enforcement è OFF
(nessun PRAGMA foreign_keys), quindi non serve seminare la tabella characters.
"""
from __future__ import annotations

from sqlalchemy import create_engine, text

from core.db.models import Base
from core.db.engine import _migrate_class_resources_to_abilities, _migrate_schema


def _legacy_db(url: str):
    """Crea un DB con lo schema attuale + tabella legacy class_resources + righe."""
    engine = create_engine(url)
    with engine.begin() as conn:
        Base.metadata.create_all(conn)
        _migrate_schema(conn)  # garantisce le colonne nuove su abilities
        # Ricrea la tabella legacy (rimossa dai modelli) a mano
        conn.execute(text(
            "CREATE TABLE class_resources ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " class_id INTEGER NOT NULL,"
            " name VARCHAR(100) NOT NULL,"
            " current INTEGER DEFAULT 0,"
            " total INTEGER DEFAULT 0,"
            " restoration_type VARCHAR(20),"
            " note TEXT)"
        ))
        conn.execute(text(
            "INSERT INTO character_classes (id, character_id, class_name, level)"
            " VALUES (10, 1, 'Monaco', 5)"
        ))
        # Match catalogo (monk.ki)
        conn.execute(text(
            "INSERT INTO class_resources (class_id, name, current, total, restoration_type)"
            " VALUES (10, 'Punti Ki', 2, 5, 'short_rest')"
        ))
        # Risorsa custom (nessun match)
        conn.execute(text(
            "INSERT INTO class_resources (class_id, name, current, total, restoration_type, note)"
            " VALUES (10, 'Risorsa Custom', 1, 3, 'long_rest', 'mia nota')"
        ))
    return engine


def test_migration_converts_and_drops(tmp_path):
    url = f"sqlite:///{tmp_path/'t.db'}"
    engine = _legacy_db(url)
    with engine.begin() as conn:
        _migrate_class_resources_to_abilities(conn)
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT name, max_uses, uses, is_class_feature, feature_key, source_class_id, description"
            " FROM abilities ORDER BY name"
        )).fetchall()
        tables = {r[0] for r in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )).fetchall()}
    by_name = {r[0]: r for r in rows}
    assert "class_resources" not in tables  # droppata
    ki = by_name["Punti Ki"]
    assert ki[1] == 5 and ki[2] == 2 and ki[3] == 1 and ki[4] == "monk.ki" and ki[5] == 10
    assert ki[6] and "monaco" in ki[6].lower()  # descrizione di catalogo (it)
    custom = by_name["Risorsa Custom"]
    assert custom[3] == 0 and custom[4] is None and custom[5] is None  # manuale
    assert custom[6] == "mia nota"  # note legacy -> description


def test_migration_idempotent(tmp_path):
    url = f"sqlite:///{tmp_path/'t.db'}"
    engine = _legacy_db(url)
    with engine.begin() as conn:
        _migrate_class_resources_to_abilities(conn)
    # Seconda esecuzione: tabella assente → no-op, nessun errore, nessun duplicato
    with engine.begin() as conn:
        _migrate_class_resources_to_abilities(conn)
    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM abilities")).scalar()
    assert n == 2


def test_backfill_action_type_is_idempotent_and_selective(tmp_path):
    from core.db.engine import _backfill_ability_action_types

    engine = create_engine(f"sqlite:///{tmp_path/'b.db'}")
    with engine.begin() as conn:
        Base.metadata.create_all(conn)
        _migrate_schema(conn)
        for name, fk, cf, at in (
            ("Furia", "barbarian.rage", 1, None),
            ("Mia", None, 0, None),
            ("Furia custom", "barbarian.rage", 1, "free"),
        ):
            conn.execute(text(
                "INSERT INTO abilities (character_id, name, is_class_feature, feature_key, action_type,"
                " restoration_type, is_passive, is_active) VALUES (1, :n, :cf, :fk, :at, 'NONE', 0, 1)"
            ), {"n": name, "cf": cf, "fk": fk, "at": at})
        for _ in range(2):
            _backfill_ability_action_types(conn)
        got = dict(conn.execute(text("SELECT name, action_type FROM abilities")).fetchall())
    assert got == {"Furia": "bonus_action", "Mia": None, "Furia custom": "free"}


async def test_api_startup_backfills_action_type(tmp_path, monkeypatch):
    """Il lifespan dell'API esegue il backfill su una riga legacy con action_type NULL."""
    from sqlalchemy.ext.asyncio import create_async_engine

    import api.main as api_main

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path/'s.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(
            "INSERT INTO abilities (character_id, name, is_class_feature, feature_key,"
            " restoration_type, is_passive, is_active) VALUES (1, 'Furia', 1, 'barbarian.rage', 'NONE', 0, 1)"
        ))
    monkeypatch.setattr(api_main, "engine", engine)
    async with api_main.lifespan(api_main.app):
        pass
    async with engine.connect() as conn:
        at = (await conn.execute(text("SELECT action_type FROM abilities"))).scalar_one()
    await engine.dispose()
    assert at == "bonus_action"
