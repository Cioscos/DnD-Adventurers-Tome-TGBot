"""Pydantic schemas for the combat tracker (encounters inside sessions)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

EncounterMode = Literal["light", "full"]
EncounterStatus = Literal["setup", "active", "ended"]


class EncounterCreateRequest(BaseModel):
    mode: EncounterMode


class CombatantAddRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    count: int = Field(default=1, ge=1, le=20)
    initiative_mod: int = Field(default=0, ge=-10, le=10)
    max_hp: Optional[int] = Field(default=None, ge=1)
    ac: Optional[int] = Field(default=None, ge=1, le=30)


class InitiativeRollRequest(BaseModel):
    """die is the 3D-dice detected face; None -> the server rolls."""
    die: Optional[int] = Field(default=None, ge=1, le=20)


class CombatantPatchRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    initiative: Optional[int] = Field(default=None, ge=-10, le=50)
    initiative_mod: Optional[int] = Field(default=None, ge=-10, le=10)
    current_hp: Optional[int] = Field(default=None, ge=0)
    max_hp: Optional[int] = Field(default=None, ge=1)
    ac: Optional[int] = Field(default=None, ge=1, le=30)
    conditions: Optional[dict[str, Any]] = None
    is_dead: Optional[bool] = None


class EncounterStartRequest(BaseModel):
    auto_roll_missing: bool = False


class ReorderRequest(BaseModel):
    combatant_ids: list[int] = Field(min_length=1)


class CombatantLive(BaseModel):
    """Viewer-redacted combatant row.

    Monster HP/AC are exact for the GM and None for players, who get
    hp_bucket instead. PC rows always have HP fields None (the FE joins
    live_characters by character_id).
    """

    id: int
    kind: Literal["pc", "monster"]
    character_id: Optional[int] = None
    owner_user_id: Optional[int] = None
    name: str
    initiative: Optional[int] = None
    initiative_die: Optional[int] = None
    initiative_mod: int = 0
    sort_order: Optional[int] = None
    is_dead: bool = False
    conditions: dict[str, Any] = {}
    current_hp: Optional[int] = None
    max_hp: Optional[int] = None
    ac: Optional[int] = None
    hp_bucket: Optional[str] = None


class EncounterLive(BaseModel):
    id: int
    mode: EncounterMode
    status: EncounterStatus
    round: int
    active_combatant_id: Optional[int] = None
    created_at: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    combatants: list[CombatantLive] = []
