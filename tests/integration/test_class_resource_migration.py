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
    assert ki[6] and "Ki" in ki[6]  # descrizione di catalogo (it)
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
