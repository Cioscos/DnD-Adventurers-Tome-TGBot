"""Reazioni degli alleati a un danno (Intercettazione, Parole Taglienti)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AllyReactionOpen(BaseModel):
    damage: int = Field(ge=0, le=100000)
    damage_type: str | None = Field(default=None, max_length=40)


class WaitingDonor(BaseModel):
    character_id: int
    name: str
    feature_key: str


class AllyReactionOpened(BaseModel):
    request_id: int | None
    waiting: list[WaitingDonor]
    expires_in: int


class AllyReactionAnswerRead(BaseModel):
    name: str
    feature_key: str
    status: str
    reduction: int | None


class AllyReactionRead(BaseModel):
    status: str  # "open" | "closed"
    waiting: list[WaitingDonor]
    answers: list[AllyReactionAnswerRead]
    total_reduction: int


class ReactionPrompt(BaseModel):
    request_id: int
    receiver_name: str
    damage: int
    damage_type: str | None
    feature_key: str
    dice: str


class ReactionAnswerBody(BaseModel):
    use: bool


class ReactionAnswerResult(BaseModel):
    reduction: int
    rolls: list[int]
