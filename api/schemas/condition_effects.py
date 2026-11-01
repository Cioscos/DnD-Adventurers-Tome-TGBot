"""Schemas for condition effects (expiry, repeated save, source) and pending saves."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from api.schemas.common import RollResult


class ConditionEffectRead(BaseModel):
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


class PendingSaveRead(BaseModel):
    id: int
    slug: str
    ability: str
    dc: int
    status: str
    created_at: str
    last_roll: Optional[dict] = None


class PendingSaveRollResult(BaseModel):
    save: PendingSaveRead
    roll: RollResult
    passed: bool
    condition_removed: bool
