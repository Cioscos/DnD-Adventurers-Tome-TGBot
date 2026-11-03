"""Pydantic schemas for the campaigns API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal, Optional

from pydantic import AfterValidator, BaseModel, StringConstraints

from api.schemas.common import CurrencyRead
from api.schemas.item import ItemRead

MemberStatus = Literal["active", "reserve", "dead"]


class CampaignCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class CampaignEnroll(BaseModel):
    code: str
    character_id: int


class MemberStatusUpdate(BaseModel):
    status: MemberStatus


class CampaignRead(BaseModel):
    id: int
    name: str
    invite_code: Optional[str] = None
    is_gm: bool


class InviteCodeRead(BaseModel):
    invite_code: str


class CampaignSummary(BaseModel):
    id: int
    name: str
    is_gm: bool
    member_count: int
    last_session_at: Optional[str] = None
    active_session_id: Optional[int] = None


class CampaignMemberRead(BaseModel):
    character_id: int
    character_name: str
    class_summary: str
    total_level: int
    user_id: int
    player_name: Optional[str] = None
    status: MemberStatus
    is_mine: bool


class CampaignStash(BaseModel):
    items: list[ItemRead]
    currency: CurrencyRead


class CampaignSessionRead(BaseModel):
    id: int
    created_at: str
    duration_seconds: int
    number: int  # position among the campaign's sessions by created_at (1 = first)
    has_recap: bool


class CampaignDetail(BaseModel):
    id: int
    name: str
    invite_code: Optional[str] = None
    is_gm: bool
    gm_user_id: int
    active_session_id: Optional[int] = None
    members: list[CampaignMemberRead]
    stash: CampaignStash
    sessions: list[CampaignSessionRead]
    my_last_character_id: Optional[int] = None


class CampaignSessionJoin(BaseModel):
    character_id: int


class LoreRead(BaseModel):
    id: int
    title: str
    body: str
    tags: list[str]
    has_image: bool
    has_audio: bool
    revealed: bool
    revealed_at: Optional[str] = None
    created_at: str
    updated_at: str


def _utc_naive(value: str) -> str:
    """ISO with offset/'Z' -> naive UTC 'YYYY-MM-DDTHH:MM:SS'; naive input is ambiguous."""
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid_starts_at") from exc
    if dt.tzinfo is None:
        raise ValueError("starts_at_needs_offset")
    return dt.astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


StartsAt = Annotated[str, AfterValidator(_utc_naive)]
ScheduleNote = Annotated[Optional[str], StringConstraints(strip_whitespace=True, max_length=200)]


class ScheduleCreate(BaseModel):
    starts_at: StartsAt
    note: ScheduleNote = None


class ScheduleUpdate(BaseModel):
    starts_at: Optional[StartsAt] = None
    note: ScheduleNote = None


class ScheduleRead(BaseModel):
    id: int
    starts_at: str
    note: Optional[str] = None
    session_id: Optional[int] = None
    status: Literal["planned", "done", "skipped"]


class ActiveCampaignSession(BaseModel):
    campaign_id: int
    campaign_name: str
    session_id: int
    my_last_character_id: Optional[int] = None
