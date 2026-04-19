"""Pydantic schemas for game sessions (invite-code based webapp feature)."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=120)


class SessionJoinRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)
    character_id: int


class SessionMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=1000)


class SessionMessageRead(BaseModel):
    id: int
    user_id: int
    role: str
    body: str
    sent_at: str

    model_config = {"from_attributes": True}


class CharacterLiveSnapshot(BaseModel):
    """Lightweight character state shown in the live session view."""

    id: int
    name: str
    race: Optional[str] = None
    class_summary: str = ""
    total_level: int = 0
    hit_points: int
    current_hit_points: int
    temp_hp: int = 0
    ac: int
    conditions: Optional[dict[str, Any]] = None
    death_saves: Optional[dict[str, Any]] = None
    heroic_inspiration: bool = False
    last_roll: Optional[dict[str, Any]] = None


class SessionParticipantRead(BaseModel):
    user_id: int
    role: str
    character_id: Optional[int] = None
    display_name: Optional[str] = None
    joined_at: str

    model_config = {"from_attributes": True}


class GameSessionRead(BaseModel):
    id: int
    code: str
    gm_user_id: int
    status: str
    title: Optional[str] = None
    created_at: str
    last_activity_at: str
    closed_at: Optional[str] = None
    participants: list[SessionParticipantRead] = []

    model_config = {"from_attributes": True}


class GameSessionLiveRead(GameSessionRead):
    live_characters: list[CharacterLiveSnapshot] = []
