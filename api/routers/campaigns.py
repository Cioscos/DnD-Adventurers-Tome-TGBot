"""Campaign endpoints: CRUD, enrollment by invite code, member status.

The party stash is a hidden Character (user_id=0, see api/services/campaigns.py).
"""
from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import TelegramUser, get_current_telegram_user, get_current_user
from api.database import get_db
from api.schemas.campaign import (
    CampaignCreate,
    CampaignDetail,
    CampaignEnroll,
    CampaignMemberRead,
    CampaignRead,
    CampaignSessionRead,
    CampaignStash,
    CampaignSummary,
    ActiveCampaignSession,
    CampaignSessionJoin,
    InviteCodeRead,
    MemberStatusUpdate,
    ScheduleCreate,
    ScheduleRead,
    ScheduleUpdate,
)
from api.schemas.common import CurrencyRead
from api.schemas.item import ItemRead
from api.routers.sessions import _find_active_session_for_user, _load_session, _touch, session_read
from api.schemas.session import GameSessionRead
from api.services import campaigns as svc
from api.services.campaigns import create_campaign, generate_campaign_code
from api.services.recap import dice_baseline
from core.db.models import (
    Campaign,
    CampaignLore,
    CampaignMember,
    CampaignSchedule,
    Character,
    GameSession,
    SessionParticipant,
    SessionRole,
    SessionStatus,
)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _err(code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=code, detail=detail)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def _get_campaign(
    db: AsyncSession, campaign_id: int, user_id: int, *, gm_only: bool = False
) -> Campaign:
    """Campaign visible to the caller (GM or owner of an enrolled PG), else 404."""
    camp = (await db.execute(
        select(Campaign).options(selectinload(Campaign.members)).where(Campaign.id == campaign_id)
    )).scalar_one_or_none()
    is_gm = camp is not None and camp.gm_user_id == user_id
    if camp is None or not (is_gm or any(m.user_id == user_id for m in camp.members)):
        raise _err(404, "campaign_not_found")
    if gm_only and not is_gm:
        raise _err(403, "gm_only")
    return camp


async def _active_session_id(db: AsyncSession, campaign_id: int) -> Optional[int]:
    return (await db.execute(
        select(GameSession.id).where(
            GameSession.campaign_id == campaign_id, GameSession.status == SessionStatus.ACTIVE
        )
    )).scalars().first()


async def _my_last_character_id(db: AsyncSession, campaign_id: int, user_id: int) -> Optional[int]:
    """The caller's PG from the most recent campaign session, if still an enrolled non-dead member."""
    return (await db.execute(
        select(SessionParticipant.character_id)
        .join(GameSession, GameSession.id == SessionParticipant.session_id)
        .join(CampaignMember, and_(
            CampaignMember.character_id == SessionParticipant.character_id,
            CampaignMember.campaign_id == campaign_id,
            CampaignMember.status != "dead",
        ))
        .where(
            GameSession.campaign_id == campaign_id,
            SessionParticipant.user_id == user_id,
            SessionParticipant.character_id.is_not(None),
        )
        .order_by(GameSession.created_at.desc(), GameSession.id.desc())
    )).scalars().first()


def _duration(created: str, last: str) -> int:
    try:
        return max(0, int((datetime.fromisoformat(last) - datetime.fromisoformat(created)).total_seconds()))
    except ValueError:
        return 0


async def _detail(db: AsyncSession, camp: Campaign, user_id: int) -> CampaignDetail:
    is_gm = camp.gm_user_id == user_id
    chars = {
        c.id: c for c in (await db.execute(
            select(Character).options(selectinload(Character.classes))
            .where(Character.id.in_([m.character_id for m in camp.members]))
        )).scalars()
    } if camp.members else {}
    members = [
        CampaignMemberRead(
            character_id=m.character_id,
            character_name=chars[m.character_id].name,
            class_summary=chars[m.character_id].class_summary,
            total_level=chars[m.character_id].total_level,
            user_id=m.user_id,
            player_name=m.player_name,
            status=m.status,
            is_mine=m.user_id == user_id,
        )
        for m in sorted(camp.members, key=lambda m: m.id) if m.character_id in chars
    ]

    stash = (await db.execute(
        select(Character)
        .options(selectinload(Character.items), selectinload(Character.currency))
        .where(Character.id == camp.stash_character_id)
    )).scalar_one()
    currency = (
        CurrencyRead.model_validate(stash.currency) if stash.currency else CurrencyRead(id=0)
    )

    sessions = (await db.execute(
        select(GameSession).where(GameSession.campaign_id == camp.id)
        .order_by(GameSession.created_at.desc(), GameSession.id.desc())
    )).scalars().all()
    my_last = await _my_last_character_id(db, camp.id, user_id)

    return CampaignDetail(
        id=camp.id,
        name=camp.name,
        invite_code=camp.invite_code if is_gm else None,
        is_gm=is_gm,
        gm_user_id=camp.gm_user_id,
        active_session_id=next((s.id for s in sessions if s.status == SessionStatus.ACTIVE), None),
        members=members,
        stash=CampaignStash(
            items=[ItemRead.model_validate(i) for i in sorted(stash.items, key=lambda i: i.id)],
            currency=currency,
        ),
        sessions=[
            CampaignSessionRead(
                id=s.id, created_at=s.created_at,
                duration_seconds=_duration(s.created_at, s.last_activity_at),
                # newest first; at most one active session and it is the latest, so this
                # matches the recap's rank among closed sessions
                number=len(sessions) - i, has_recap=s.recap is not None,
            )
            for i, s in enumerate(sessions)
        ],
        my_last_character_id=my_last,
    )


@router.post("", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
async def create(
    body: CampaignCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignRead:
    camp = await create_campaign(db, user_id, body.name.strip())
    return CampaignRead(id=camp.id, name=camp.name, invite_code=camp.invite_code, is_gm=True)


@router.get("", response_model=list[CampaignSummary])
async def list_campaigns(
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CampaignSummary]:
    mine = select(CampaignMember.campaign_id).where(CampaignMember.user_id == user_id)
    camps = (await db.execute(
        select(Campaign).where(or_(Campaign.gm_user_id == user_id, Campaign.id.in_(mine)))
    )).scalars().all()
    ids = [c.id for c in camps]
    counts = dict((await db.execute(
        select(CampaignMember.campaign_id, func.count()).where(CampaignMember.campaign_id.in_(ids))
        .group_by(CampaignMember.campaign_id)
    )).all()) if ids else {}
    sessions = (await db.execute(
        select(GameSession).where(GameSession.campaign_id.in_(ids))
        .order_by(GameSession.created_at.desc(), GameSession.id.desc())
    )).scalars().all() if ids else []
    last: dict[int, GameSession] = {}
    active: dict[int, int] = {}
    for s in sessions:  # newest first
        last.setdefault(s.campaign_id, s)
        if s.status == SessionStatus.ACTIVE:
            active.setdefault(s.campaign_id, s.id)
    out = [
        CampaignSummary(
            id=c.id, name=c.name, is_gm=c.gm_user_id == user_id,
            member_count=counts.get(c.id, 0),
            last_session_at=last[c.id].created_at if c.id in last else None,
            active_session_id=active.get(c.id),
        )
        for c in camps
    ]
    # most recent session first, then created_at; two stable passes
    created = {c.id: c.created_at for c in camps}
    out.sort(key=lambda s: created[s.id], reverse=True)
    out.sort(key=lambda s: s.last_session_at or "", reverse=True)
    return out


# Static routes before /{campaign_id}.
@router.post("/enroll", response_model=CampaignDetail)
async def enroll(
    body: CampaignEnroll,
    tg_user: Annotated[TelegramUser, Depends(get_current_telegram_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignDetail:
    user_id = tg_user.id
    camp = (await db.execute(
        select(Campaign).options(selectinload(Campaign.members))
        .where(Campaign.invite_code == body.code.strip().upper())
    )).scalar_one_or_none()
    if camp is None:
        raise _err(404, "campaign_not_found")
    if camp.gm_user_id == user_id:
        raise _err(422, "gm_cannot_enroll")
    char = await db.get(Character, body.character_id)
    if char is None or char.user_id != user_id:
        raise _err(403, "not_your_character")
    taken = (await db.execute(
        select(CampaignMember.id).where(CampaignMember.character_id == char.id)
    )).first()
    if taken is not None:
        raise _err(409, "already_in_campaign")
    camp.members.append(CampaignMember(
        character_id=char.id, user_id=user_id, player_name=(tg_user.first_name or None),
        status="active", joined_at=_now(),
    ))
    await db.flush()
    return await _detail(db, camp, user_id)


@router.get("/active-for-me", response_model=list[ActiveCampaignSession])
async def active_for_me(
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ActiveCampaignSession]:
    """Campaigns with a live session the caller can join (drives the player banner)."""
    rows = (await db.execute(
        select(Campaign.id, Campaign.name, GameSession.id)
        .join(GameSession, GameSession.campaign_id == Campaign.id)
        .where(
            GameSession.status == SessionStatus.ACTIVE,
            Campaign.id.in_(
                select(CampaignMember.campaign_id).where(
                    CampaignMember.user_id == user_id, CampaignMember.status != "dead"
                )
            ),
            ~GameSession.id.in_(
                select(SessionParticipant.session_id).where(SessionParticipant.user_id == user_id)
            ),
        )
        .order_by(GameSession.id)
    )).all()
    return [
        ActiveCampaignSession(
            campaign_id=cid, campaign_name=name, session_id=sid,
            my_last_character_id=await _my_last_character_id(db, cid, user_id),
        )
        for cid, name, sid in rows
    ]


@router.get("/{campaign_id}", response_model=CampaignDetail)
async def get_campaign(
    campaign_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignDetail:
    return await _detail(db, await _get_campaign(db, campaign_id, user_id), user_id)


@router.patch("/{campaign_id}", response_model=CampaignRead)
async def rename(
    campaign_id: int,
    body: CampaignCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignRead:
    camp = await _get_campaign(db, campaign_id, user_id, gm_only=True)
    camp.name = body.name.strip()
    stash = await db.get(Character, camp.stash_character_id)
    stash.name = camp.name
    return CampaignRead(id=camp.id, name=camp.name, invite_code=camp.invite_code, is_gm=True)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    camp = await _get_campaign(db, campaign_id, user_id, gm_only=True)
    if await _active_session_id(db, camp.id) is not None:
        raise _err(409, "campaign_session_active")
    # game_sessions.campaign_id has no FK: detach closed sessions in code.
    await db.execute(
        update(GameSession).where(GameSession.campaign_id == camp.id).values(campaign_id=None)
    )
    stash = await db.get(Character, camp.stash_character_id)
    await db.execute(delete(CampaignLore).where(CampaignLore.campaign_id == camp.id))
    await db.execute(delete(CampaignSchedule).where(CampaignSchedule.campaign_id == camp.id))
    await db.delete(camp)  # cascades campaign_members
    await db.flush()
    await db.delete(stash)  # cascades items and currency
    await db.flush()
    shutil.rmtree(svc.LORE_DIR / str(camp.id), ignore_errors=True)  # only after the DB delete went through
    shutil.rmtree(svc.ATLAS_DIR / str(camp.id), ignore_errors=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _naive_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _schedule_read(row: CampaignSchedule) -> ScheduleRead:
    # Skipped only once the ±12h link window (sessions.create_session) has passed.
    late = (datetime.fromisoformat(row.starts_at) + timedelta(hours=12)).isoformat(timespec="seconds")
    st = "done" if row.session_id is not None else ("skipped" if late < _naive_now() else "planned")
    return ScheduleRead(id=row.id, starts_at=row.starts_at, note=row.note, session_id=row.session_id, status=st)


async def _get_schedule(db: AsyncSession, campaign_id: int, sid: int) -> CampaignSchedule:
    row = await db.get(CampaignSchedule, sid)
    if row is None or row.campaign_id != campaign_id:
        raise _err(404, "schedule_not_found")
    return row


@router.get("/{campaign_id}/schedule", response_model=list[ScheduleRead])
async def list_schedule(
    campaign_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ScheduleRead]:
    await _get_campaign(db, campaign_id, user_id)
    rows = (await db.execute(
        select(CampaignSchedule).where(CampaignSchedule.campaign_id == campaign_id)
        .order_by(CampaignSchedule.starts_at, CampaignSchedule.id)
    )).scalars().all()
    return [_schedule_read(r) for r in rows]


@router.post("/{campaign_id}/schedule", response_model=ScheduleRead, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    campaign_id: int,
    body: ScheduleCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ScheduleRead:
    await _get_campaign(db, campaign_id, user_id, gm_only=True)
    if body.starts_at <= _naive_now():
        raise _err(422, "starts_at_in_past")
    row = CampaignSchedule(campaign_id=campaign_id, starts_at=body.starts_at,
                           note=body.note or None, created_at=_naive_now())
    db.add(row)
    await db.flush()
    return _schedule_read(row)


@router.patch("/{campaign_id}/schedule/{sid}", response_model=ScheduleRead)
async def update_schedule(
    campaign_id: int,
    sid: int,
    body: ScheduleUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ScheduleRead:
    await _get_campaign(db, campaign_id, user_id, gm_only=True)
    row = await _get_schedule(db, campaign_id, sid)
    if body.starts_at is not None and body.starts_at != row.starts_at:
        if body.starts_at <= _naive_now():
            raise _err(422, "starts_at_in_past")
        row.starts_at = body.starts_at
        row.reminded_day_at = row.reminded_hour_at = None
    if "note" in body.model_fields_set:
        row.note = body.note or None
    await db.flush()
    return _schedule_read(row)


@router.delete("/{campaign_id}/schedule/{sid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    campaign_id: int,
    sid: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await _get_campaign(db, campaign_id, user_id, gm_only=True)
    await db.delete(await _get_schedule(db, campaign_id, sid))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{campaign_id}/invite-code", response_model=InviteCodeRead)
async def regenerate_invite_code(
    campaign_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InviteCodeRead:
    camp = await _get_campaign(db, campaign_id, user_id, gm_only=True)
    camp.invite_code = await generate_campaign_code(db)
    return InviteCodeRead(invite_code=camp.invite_code)


async def _get_member(
    db: AsyncSession, campaign_id: int, character_id: int, user_id: int
) -> CampaignMember:
    """Member row, only for the PG owner or the GM (campaign visibility checked first)."""
    camp = await _get_campaign(db, campaign_id, user_id)
    member = next((m for m in camp.members if m.character_id == character_id), None)
    if member is None:
        raise _err(404, "member_not_found")
    if user_id not in (member.user_id, camp.gm_user_id):
        raise _err(403, "forbidden")
    return member


@router.patch("/{campaign_id}/members/{character_id}", response_model=CampaignDetail)
async def set_member_status(
    campaign_id: int,
    character_id: int,
    body: MemberStatusUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignDetail:
    member = await _get_member(db, campaign_id, character_id, user_id)
    member.status = body.status
    await db.flush()
    return await _detail(db, await _get_campaign(db, campaign_id, user_id), user_id)


@router.delete("/{campaign_id}/members/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    campaign_id: int,
    character_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    member = await _get_member(db, campaign_id, character_id, user_id)
    # also drop the PG from the campaign's live session (it would keep stash access)
    live = select(GameSession.id).where(
        GameSession.campaign_id == campaign_id, GameSession.status == SessionStatus.ACTIVE
    )
    await db.execute(delete(SessionParticipant).where(
        SessionParticipant.character_id == character_id,
        SessionParticipant.session_id.in_(live),
    ))
    await db.delete(member)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{campaign_id}/session/join", response_model=GameSessionRead)
async def join_campaign_session(
    campaign_id: int,
    body: CampaignSessionJoin,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GameSessionRead:
    """One-tap join of the campaign's active session with a chosen enrolled PG."""
    camp = await _get_campaign(db, campaign_id, user_id)
    char = await db.get(Character, body.character_id)
    if char is None or char.user_id != user_id:
        raise _err(403, "not_your_character")
    member = next((m for m in camp.members if m.character_id == char.id), None)
    if member is None:
        raise _err(422, "not_a_member")
    if member.status == "dead":
        raise _err(422, "character_dead")
    session_id = await _active_session_id(db, camp.id)
    if session_id is None:
        raise _err(404, "no_active_session")
    if await _find_active_session_for_user(user_id, db) is not None:
        raise _err(409, "You already have an active session")
    session = await _load_session(session_id, db)
    db.add(SessionParticipant(
        session_id=session.id, user_id=user_id, role=SessionRole.PLAYER,
        character_id=char.id, character=char, display_name=char.name, joined_at=_now(),
        dice_stats_start=dice_baseline(session, char),
    ))
    _touch(session)
    await db.flush()
    await db.refresh(session, attribute_names=["participants"])
    return await session_read(db, session)
