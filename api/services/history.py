"""Riga di storico del personaggio (``CharacterHistory``): un solo punto per tutti i router e i servizi."""
from __future__ import annotations

from datetime import datetime

from core.db.models import CharacterHistory


def add_history(session, char_id: int, event_type: str, description: str, meta: dict | None = None) -> None:
    session.add(CharacterHistory(
        character_id=char_id,
        timestamp=datetime.utcnow().isoformat(timespec="seconds"),
        event_type=event_type,
        description=description,
        meta=meta,
    ))
