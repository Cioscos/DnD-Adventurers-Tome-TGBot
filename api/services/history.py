"""Riga di storico del personaggio (``CharacterHistory``): un solo punto per tutti i router e i servizi."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, event, select
from sqlalchemy.orm import Session

from core.db.models import Character, CharacterHistory

logger = logging.getLogger(__name__)
_DIRTY = "history_char_ids"


def add_history(session, char_id: int, event_type: str, description: str, meta: dict | None = None) -> None:
    session.add(CharacterHistory(
        character_id=char_id,
        timestamp=datetime.utcnow().isoformat(timespec="seconds"),
        event_type=event_type,
        description=description,
        meta=meta,
    ))


def prune(session: Session, char_id: int, settings: dict | None) -> int:
    """Toglie le righe oltre il limite scelto nelle Impostazioni (``history_retention_*``); dice quante."""
    settings = settings if isinstance(settings, dict) else {}
    mode = settings.get("history_retention_mode", "off")
    if mode not in ("events", "days"):
        return 0
    mine = CharacterHistory.character_id == char_id
    try:
        if mode == "events":
            keep = max(1, int(settings.get("history_retention_events", 100) or 100))
            old = select(CharacterHistory.id).where(mine).order_by(
                CharacterHistory.timestamp.desc(), CharacterHistory.id.desc()).offset(keep)
            stmt = delete(CharacterHistory).where(CharacterHistory.id.in_(old))
        else:
            days = max(1, int(settings.get("history_retention_days", 30) or 30))
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat(timespec="seconds")
            stmt = delete(CharacterHistory).where(mine, CharacterHistory.timestamp < cutoff)
        return session.execute(stmt, execution_options={"synchronize_session": False}).rowcount or 0
    except Exception as exc:  # la pulizia non fa fallire l'azione
        logger.warning("prune_history failed for char %s: %s", char_id, exc)
        return 0


@event.listens_for(Session, "after_flush")
def _note_history(session: Session, _ctx) -> None:
    ids = {o.character_id for o in session.new if isinstance(o, CharacterHistory)}
    if ids:
        session.info.setdefault(_DIRTY, set()).update(ids)


@event.listens_for(Session, "before_commit")
def _prune_written(session: Session) -> None:
    """Un punto solo per ogni via che scrive in cronologia: a fine richiesta, quando nessuna riga verrà più modificata."""
    if session.in_nested_transaction():
        return
    session.flush()
    for char_id in session.info.pop(_DIRTY, ()):
        prune(session, char_id, session.scalar(select(Character.settings).where(Character.id == char_id)))
