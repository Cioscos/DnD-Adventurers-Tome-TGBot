"""SQLAlchemy async engine and session factory.

Database file is stored at ``data/dnd_bot.db`` relative to the project root.
``init_db()`` must be called once at startup to create all tables.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import event, inspect as sa_inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.db.models import Base

logger = logging.getLogger(__name__)

_DB_PATH = os.environ.get("DB_PATH", "data/dnd_bot.db")
_DATABASE_URL = f"sqlite+aiosqlite:///{_DB_PATH}"

engine = create_async_engine(_DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    """Enable FK enforcement (and cascade deletes) for every SQLite connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# ---------------------------------------------------------------------------
# Schema migration helpers
# ---------------------------------------------------------------------------

# NOTE: ALTER TABLE ADD COLUMN only. New tables are auto-created by
# Base.metadata.create_all from the ORM models — no entry here is needed.

# Columns to ensure on existing tables: (table, column, DDL type, default)
_MIGRATIONS: list[tuple[str, str, str, str | None]] = [
    # Spell extended properties
    ("spells", "casting_time", "VARCHAR(100)", None),
    ("spells", "range_area", "VARCHAR(100)", None),
    ("spells", "components", "VARCHAR(200)", None),
    ("spells", "duration", "VARCHAR(100)", None),
    ("spells", "is_concentration", "BOOLEAN", "0"),
    ("spells", "is_ritual", "BOOLEAN", "0"),
    ("spells", "higher_level", "TEXT", None),
    ("spells", "attack_save", "VARCHAR(100)", None),
    ("spells", "is_pinned", "BOOLEAN", "0"),
    # Character concentration tracking
    ("characters", "concentrating_spell_id", "INTEGER REFERENCES spells(id) ON DELETE SET NULL", None),
    # CharacterClass subclass
    ("character_classes", "subclass", "VARCHAR(100)", None),
    # Conditions feature
    ("characters", "conditions", "TEXT", None),
    # Skills feature
    ("characters", "skills", "TEXT", None),
    # Item type system
    ("items", "item_type", "VARCHAR(20)", "'generic'"),
    ("items", "item_metadata", "TEXT", None),
    ("items", "is_equipped", "BOOLEAN", "0"),
    # Equipment slot for paper-doll
    ("items", "equipment_slot", "VARCHAR(20)", None),
    # Heroic Inspiration
    ("characters", "heroic_inspiration", "BOOLEAN", "0"),
    # Saving throw proficiencies
    ("characters", "saving_throws", "TEXT", None),
    # Experience points
    ("characters", "experience_points", "INTEGER", "0"),
    # Death saving throws
    ("characters", "death_saves", "TEXT", None),
    # Permanent death state (Morte & stato Morto epic)
    ("characters", "is_dead", "BOOLEAN", "0"),
    # Temporary hit points
    ("characters", "temp_hp", "INTEGER", "0"),
    # Movement speed
    ("characters", "speed", "INTEGER", "30"),
    # Expanded identity
    ("characters", "background", "VARCHAR(200)", None),
    ("characters", "alignment", "VARCHAR(50)", None),
    ("characters", "personality", "TEXT", None),
    ("characters", "languages", "TEXT", None),
    ("characters", "general_proficiencies", "TEXT", None),
    ("characters", "damage_modifiers", "TEXT", None),
    # CharacterClass extensions
    ("character_classes", "spellcasting_ability", "VARCHAR(50)", None),
    ("character_classes", "hit_die", "INTEGER", None),
    # Spell damage fields
    ("spells", "damage_dice", "VARCHAR(100)", None),
    ("spells", "damage_type", "VARCHAR(100)", None),
    # Map local file upload support
    ("maps", "local_file_path", "VARCHAR(500)", None),
    # Map drag-reorder (G1)
    ("maps", "position", "INTEGER", "0"),
    # Map size in bytes for inline PDF preview decision (G2)
    ("maps", "size_bytes", "INTEGER", "0"),
    # Session whisper support
    ("session_messages", "recipient_user_id", "BIGINT", None),
    ("session_messages", "sender_display_name", "VARCHAR(120)", None),
    # Session GM display name (Telegram first_name / @username / fallback)
    ("game_sessions", "gm_display_name", "VARCHAR(120)", None),
    # Character history meta (for op tagging on hp_change, Gruppo H)
    ("character_history", "meta", "TEXT", None),
    # GM grant payload on session whispers
    ("session_messages", "item_id", "BIGINT", None),
    ("session_messages", "item_name", "VARCHAR(120)", None),
    ("session_messages", "item_quantity", "INTEGER", None),
    # AC manual override flags — preserve user-edited Base/Shield across equip/unequip
    ("characters", "base_armor_class_override", "BOOLEAN", "0"),
    ("characters", "shield_armor_class_override", "BOOLEAN", "0"),
    # Carry-capacity manual override flag — preserve user-set capacity across STR changes
    ("characters", "carry_capacity_override", "BOOLEAN", "0"),
    # Unarmored Defense — second ability ('wisdom'/'constitution'); NULL = disabled
    ("characters", "unarmored_defense_ability", "VARCHAR(20)", None),
    # Custom paper-doll silhouette (E4)
    ("characters", "silhouette_path", "VARCHAR(500)", None),
    # Risorse di classe assorbite in Ability (refactor risorse → abilità)
    ("abilities", "source_class_id", "INTEGER REFERENCES character_classes(id) ON DELETE CASCADE", None),
    ("abilities", "is_class_feature", "BOOLEAN", "0"),
    ("abilities", "feature_key", "VARCHAR(100)", None),
    # Incantesimi preparati — backfill legacy a 1 (preparato): nulla cambia per
    # i personaggi esistenti finché l'utente non gestisce la preparazione.
    ("spells", "is_prepared", "BOOLEAN", "1"),
    # Statistiche cumulative dei tiri (contatori per faccia, per tipo di dado)
    ("characters", "dice_stats", "JSON", None),
]

# Tables to drop if they exist (legacy feature cleanup)
_DROP_TABLES: list[str] = [
    "party_sessions",
    "group_members",
]

# Columns to drop if they exist: (table, column)
_DROP_COLUMNS: list[tuple[str, str]] = [
    ("characters", "is_party_active"),
]


def _rebuild_spell_slots_for_pact(connection) -> None:
    """Add ``is_pact`` to spell_slots and widen its UNIQUE key (idempotent).

    The original table carried ``UNIQUE(character_id, level)``, which is part
    of the CREATE TABLE statement — SQLite cannot drop it via ALTER TABLE, so
    a full table rebuild is required to relax it to
    ``UNIQUE(character_id, level, is_pact)``. Detected by the absence of the
    ``is_pact`` column; once rebuilt the function is a no-op. Fresh databases
    get the new shape directly from ``create_all`` and skip this entirely.

    No other table references spell_slots, so dropping it is safe even with
    foreign-key enforcement on (PRAGMA toggles are no-ops inside a transaction
    anyway).
    """
    inspector = sa_inspect(connection)
    if "spell_slots" not in inspector.get_table_names():
        return  # create_all will build it fresh with the new schema
    cols = {c["name"] for c in inspector.get_columns("spell_slots")}
    if "is_pact" in cols:
        return  # already migrated

    logger.info("Rebuilding spell_slots to add is_pact + UNIQUE(character_id, level, is_pact)")
    # Crash-safety: a prior run may have created spell_slots_new and then been
    # interrupted before the DROP/RENAME (process kill, deploy mid-migration,
    # power loss), leaving an orphan table. Without this, every subsequent
    # startup hits "table spell_slots_new already exists" and the API enters a
    # systemd crash loop. spell_slots is still intact here (we only reach this
    # point when is_pact is absent, i.e. the rename never happened), so the
    # orphan is a stale partial copy and is safe to discard.
    connection.execute(text("DROP TABLE IF EXISTS spell_slots_new"))
    connection.execute(text(
        "CREATE TABLE spell_slots_new ("
        " id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,"
        " character_id INTEGER NOT NULL,"
        " level INTEGER NOT NULL,"
        " total INTEGER NOT NULL DEFAULT 0,"
        " used INTEGER NOT NULL DEFAULT 0,"
        " is_pact BOOLEAN NOT NULL DEFAULT 0,"
        " UNIQUE (character_id, level, is_pact),"
        " FOREIGN KEY(character_id) REFERENCES characters(id) ON DELETE CASCADE"
        ")"
    ))
    # Only carry over rows whose character still exists. spell_slots_new has
    # FOREIGN KEY(character_id) REFERENCES characters(id); with FK enforcement
    # on (the app sets PRAGMA foreign_keys=ON per connection, and it cannot be
    # toggled inside this transaction) a dangling row — left behind when a
    # character was deleted while FK enforcement was off — makes this INSERT
    # fail with "FOREIGN KEY constraint failed", aborting startup. Such rows are
    # unusable orphans (their owning character is gone), so we drop them here.
    connection.execute(text(
        "INSERT INTO spell_slots_new (id, character_id, level, total, used, is_pact) "
        "SELECT id, character_id, level, total, used, 0 FROM spell_slots "
        "WHERE character_id IN (SELECT id FROM characters)"
    ))
    connection.execute(text("DROP TABLE spell_slots"))
    connection.execute(text("ALTER TABLE spell_slots_new RENAME TO spell_slots"))


def _migrate_schema(connection) -> None:
    """Add missing columns, drop legacy columns/tables (idempotent)."""
    _rebuild_spell_slots_for_pact(connection)

    inspector = sa_inspect(connection)
    existing_tables = set(inspector.get_table_names())
    column_cache: dict[str, set[str]] = {}

    for table, column, col_type, default in _MIGRATIONS:
        if table not in column_cache:
            try:
                cols = inspector.get_columns(table)
                column_cache[table] = {c["name"] for c in cols}
            except Exception:
                # Table doesn't exist yet — create_all will handle it
                column_cache[table] = set()
                continue

        if column not in column_cache[table]:
            default_clause = f" DEFAULT {default}" if default is not None else ""
            ddl = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}{default_clause}"
            logger.info("Migrating: %s", ddl)
            connection.execute(text(ddl))
            column_cache[table].add(column)

    # Ad-hoc index for whisper filter queries
    try:
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_session_messages_recipient "
            "ON session_messages(recipient_user_id)"
        ))
    except Exception as exc:
        logger.warning("CREATE INDEX failed for session_messages.recipient_user_id: %s", exc)

    # Backfill gm_display_name for sessions created before the column existed.
    # The WHERE clause makes this idempotent — only NULL/empty rows are touched.
    if "game_sessions" in column_cache and "gm_display_name" in column_cache["game_sessions"]:
        try:
            result = connection.execute(text(
                "UPDATE game_sessions "
                "SET gm_display_name = '#' || gm_user_id "
                "WHERE gm_display_name IS NULL OR gm_display_name = ''"
            ))
            if result.rowcount:
                logger.info("Backfilled gm_display_name for %d session(s)", result.rowcount)
        except Exception as exc:
            logger.warning("Backfill gm_display_name failed: %s", exc)

    # Backfill maps.size_bytes for files uploaded before the column existed.
    # Idempotent: WHERE clause only matches rows that haven't been measured yet.
    if (
        "maps" in column_cache
        and "size_bytes" in column_cache["maps"]
        and "local_file_path" in column_cache["maps"]
    ):
        try:
            rows = connection.execute(text(
                "SELECT id, local_file_path FROM maps "
                "WHERE local_file_path IS NOT NULL AND size_bytes = 0"
            )).fetchall()
            updated = 0
            for row in rows:
                local_path = row[1]
                if not local_path:
                    continue
                try:
                    size = os.path.getsize(local_path)
                except OSError:
                    continue
                connection.execute(
                    text("UPDATE maps SET size_bytes = :s WHERE id = :id"),
                    {"s": size, "id": row[0]},
                )
                updated += 1
            if updated:
                logger.info("Backfilled size_bytes for %d map(s)", updated)
        except Exception as exc:
            logger.warning("Backfill maps.size_bytes failed: %s", exc)

    # Consolidate legacy item_type='other' rows to canonical 'generic'.
    # Idempotent — once converged the WHERE clause matches no rows.
    if "items" in column_cache and "item_type" in column_cache["items"]:
        try:
            result = connection.execute(text(
                "UPDATE items SET item_type = 'generic' WHERE item_type = 'other'"
            ))
            if result.rowcount:
                logger.info(
                    "Consolidated %d items from item_type='other' -> 'generic'",
                    result.rowcount,
                )
        except Exception as exc:
            logger.warning("item_type 'other' -> 'generic' migration failed: %s", exc)

    # Heal rows poisoned with the raw value 'manual' written before
    # RestorationType had a MANUAL member (PR #148). SQLAlchemy persists enum
    # *names* ('MANUAL'), but the pre-fix Enum pass-through (validate_strings is
    # False by default) stored the raw value 'manual'. On read SQLAlchemy can no
    # longer map 'manual' back to the enum and raises LookupError, which 500s
    # every load of the owning character — bricking it. Adding MANUAL to the
    # enum fixes new writes but NOT these already-stored rows, so normalize them
    # to the enum name here. Idempotent: once converged the WHERE matches no rows.
    for _tbl in ("abilities", "homebrew_resources"):
        if _tbl not in existing_tables:
            continue
        try:
            result = connection.execute(text(
                f"UPDATE {_tbl} SET restoration_type = 'MANUAL' "
                "WHERE restoration_type = 'manual'"
            ))
            if result.rowcount:
                logger.info(
                    "Healed %d %s row(s) with invalid restoration_type='manual'",
                    result.rowcount, _tbl,
                )
        except Exception as exc:
            logger.warning(
                "restoration_type 'manual' heal failed for %s: %s", _tbl, exc
            )

    for table, column in _DROP_COLUMNS:
        if table not in existing_tables:
            continue
        cols = column_cache.get(table)
        if cols is None:
            cols = {c["name"] for c in inspector.get_columns(table)}
            column_cache[table] = cols
        if column in cols:
            ddl = f"ALTER TABLE {table} DROP COLUMN {column}"
            logger.info("Migrating: %s", ddl)
            try:
                connection.execute(text(ddl))
                cols.discard(column)
            except Exception as exc:
                # SQLite < 3.35 does not support DROP COLUMN.
                logger.warning("DROP COLUMN failed for %s.%s: %s", table, column, exc)

    for table in _DROP_TABLES:
        if table in existing_tables:
            logger.info("Dropping legacy table: %s", table)
            connection.execute(text(f"DROP TABLE IF EXISTS {table}"))
            existing_tables.discard(table)


def _migrate_class_resources_to_abilities(connection) -> None:
    """Converte le righe ``class_resources`` legacy in Ability, poi droppa la tabella.

    Idempotente: se ``class_resources`` non esiste più (già migrata / DB nuovo) è
    un no-op. Il match contro il catalogo ``CLASS_RESOURCES`` (per
    ``(class_name, resource_name)``) marca la riga come feature di classe
    (``is_class_feature=1`` + ``feature_key`` + ``source_class_id`` + descrizione
    italiana di catalogo); le righe senza match diventano abilità manuali.
    ``restoration_type`` è copiato verbatim (stessa rappresentazione enum).
    """
    inspector = sa_inspect(connection)
    if "class_resources" not in inspector.get_table_names():
        return

    from core.data.classes import CLASS_RESOURCES

    # (class_name, resource_name) -> (feature_key, description_it)
    lookup: dict[tuple[str, str], tuple[str, str]] = {}
    for class_name, configs in CLASS_RESOURCES.items():
        for cfg in configs:
            lookup[(class_name, cfg.name)] = (cfg.key, cfg.description.get("it") or "")

    rows = connection.execute(text(
        "SELECT cr.name, cr.current, cr.total, cr.restoration_type, cr.note,"
        "       cc.id AS class_id, cc.character_id, cc.class_name "
        "FROM class_resources cr "
        "JOIN character_classes cc ON cc.id = cr.class_id"
    )).fetchall()

    migrated = 0
    for row in rows:
        name, current, total, restoration_type, note, class_id, character_id, class_name = row
        matched = lookup.get((class_name, name))
        if matched is not None:
            feature_key, desc = matched
            connection.execute(text(
                "INSERT INTO abilities "
                "(character_id, name, description, max_uses, uses, is_passive, is_active,"
                " restoration_type, source_class_id, is_class_feature, feature_key) "
                "VALUES (:cid, :name, :desc, :max_uses, :uses, 0, 1, :rt, :scid, 1, :fk)"
            ), {
                "cid": character_id, "name": name, "desc": desc,
                "max_uses": total, "uses": current, "rt": restoration_type,
                "scid": class_id, "fk": feature_key,
            })
        else:
            connection.execute(text(
                "INSERT INTO abilities "
                "(character_id, name, description, max_uses, uses, is_passive, is_active,"
                " restoration_type, source_class_id, is_class_feature, feature_key) "
                "VALUES (:cid, :name, :desc, :max_uses, :uses, 0, 1, :rt, NULL, 0, NULL)"
            ), {
                "cid": character_id, "name": name, "desc": note,
                "max_uses": total, "uses": current, "rt": restoration_type,
            })
        migrated += 1

    connection.execute(text("DROP TABLE class_resources"))
    if migrated:
        logger.info("Migrate %d class_resources -> abilities; dropped class_resources", migrated)


async def init_db() -> None:
    """Create all tables and run schema + data migrations."""
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_schema)
        await conn.run_sync(_migrate_class_resources_to_abilities)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager that yields an ``AsyncSession``."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
