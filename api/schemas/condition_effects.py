"""Schemas for condition effects (expiry, repeated save, source) and pending saves."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from api.schemas.common import RollResult


class ConditionEffectRead(BaseModel):
    id: Optional[int] = None  # più istanze della stessa condizione: la fuga sceglie quale (U36)
    slug: str
    expiry_anchor: Optional[str] = None
    expiry_edge: Optional[str] = None
    expiry_count: Optional[int] = None
    save_ability: Optional[str] = None
    save_dc: Optional[int] = None
    save_edge: Optional[str] = None
    source_name: Optional[str] = None
    ends_with_concentration: bool = False
    applied_by_gm: bool = False
    source_note: Optional[str] = None  # fonte scritta dal GM ("Ragnatela")


class PendingSaveRead(BaseModel):
    id: int
    slug: str
    ability: str
    alt_ability: Optional[str] = None  # il bersaglio può tirare con questa invece di ``ability``
    dc: int
    status: str
    created_at: str
    last_roll: Optional[dict] = None


class EscapeResult(BaseModel):
    """Liberarsi da Trattenuto/Afferrato (U36): la prova, la CD dell'effetto e se è riuscita."""
    roll: RollResult
    dc: int
    escaped: bool


class PendingSaveRollResult(BaseModel):
    save: PendingSaveRead
    roll: RollResult
    passed: bool
    condition_removed: bool
