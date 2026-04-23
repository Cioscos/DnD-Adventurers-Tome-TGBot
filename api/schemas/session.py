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
    recipient_user_id: Optional[int] = None


class SessionMessageRead(BaseModel):
    id: int
    user_id: int
    role: str
    body: str
    sent_at: str
    recipient_user_id: Optional[int] = None
    sender_display_name: Optional[str] = None

    model_config = {"from_attributes": True}


class CharacterLiveSnapshot(BaseModel):
    """Lightweight character state shown in the live session view.

    Raw HP/AC/death_saves fields are nullable: they are populated for the GM
    and for the character's owner, but redacted to None for other players.
    hp_bucket / armor_category are always populated and carry the redacted
    summary.
    """

    id: int
    name: str
    race: Optional[str] = None
    class_summary: str = ""
    total_level: int = 0
    hit_points: Optional[int] = None
    current_hit_points: Optional[int] = None
    temp_hp: Optional[int] = None
    ac: Optional[int] = None
    conditions: Optional[dict[str, Any]] = None
    death_saves: Optional[dict[str, Any]] = None
    heroic_inspiration: bool = False
    last_roll: Optional[dict[str, Any]] = None
    hp_bucket: Optional[str] = None
    armor_category: Optional[str] = None


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


class IdentityView(BaseModel):
    """Public + optionally private identity fields for a session participant.

    Private fields (background, personality_traits, ideals, bonds, flaws)
    are populated only when the target has enabled `show_private_identity`
    or when the caller is the target themselves.
    """

    user_id: int
    character_id: int
    # public (always populated)
    name: str
    race: Optional[str] = None
    gender: Optional[str] = None
    alignment: Optional[str] = None
    speed: Optional[int] = None
    languages: Optional[str] = None  # comma-joined for display
    general_proficiencies: Optional[str] = None  # comma-joined for display
    # private (null if target has show_private_identity = False)
    background: Optional[str] = None
    personality_traits: Optional[str] = None
    ideals: Optional[str] = None
    bonds: Optional[str] = None
    flaws: Optional[str] = None
    show_private: bool = False
