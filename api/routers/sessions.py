"""Game session endpoints (invite-code based, replaces the bot /party command).

A Game Master creates a session and obtains a 6-character invite code. Players
join with the code and pick one of their characters. The webapp polls `/live`
for HP/AC/conditions snapshots and `/messages` for the in-session chat.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import TelegramUser, get_current_lang, get_current_telegram_user, get_current_user
from api.database import get_db
from core.game.containers import is_container, trade_snapshot
from core.rules.edition import character_edition
from core.rules.modifiers import ac_delta
from api.schemas.session import (
    CharacterLiveSnapshot,
    GameSessionLiveRead,
    GameSessionRead,
    GMGrantItemRequest,
    GMGrantItemResponse,
    GMGrantItemResult,
    IdentityView,
    SessionCreateRequest,
    SessionFeedItem,
    SessionFeedResponse,
    SessionJoinRequest,
    SessionMessageCreate,
    SessionMessageRead,
    StashGMAddRequest,
    StashGMRemoveRequest,
    StashPutRequest,
    StashTakeRequest,
    InspirationGiveRequest,
    TradeRequest,
    TurnState,
)
from api.schemas.campaign import CampaignStash
from api.schemas.common import CurrencyRead
from api.schemas.item import ItemRead
from api.routers._helpers import apply_con_hp, collect_homebrew_notifications, effective_con_mod
from api.schemas.character import CharacterFull
from api.services import telegram_notify
from api.services.character_response import build_character_response
from api.services.class_features import sync_cataloged_features
from api.services.recap import close_game_session, dice_baseline, record_departure
from api.services.homebrew.dispatcher import dispatch
from api.services.trades import add_coins, give_coins, give_item, remove_coins, remove_item
from api.services.condition_effects import character_effect_payload
from api.services.rules_turn import attacks_allowed, get_turn
from api.services.encounter_view import build_encounter_block, public_states
from core.db.models import (
    Campaign,
    CampaignMember,
    CampaignSchedule,
    Character,
    CharacterHistory,
    Combatant,
    Encounter,
    GameSession,
    Item,
    SessionMessage,
    SessionParticipant,
    SessionRole,
    SessionStatus,
)
from core.utils.session_code import generate_session_code
from core.utils.session_view import hp_bucket, armor_category

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])
# Stato del turno visto dalla scheda: vive sotto /characters ma usa i modelli di sessione.
character_turn_router = APIRouter(prefix="/characters", tags=["sessions"])


_MAX_CODE_RETRIES = 10


_SESSION_FEED_EVENT_TYPES: set[str] = {
    "hp_change",
    "rest",
    "skill_roll",
    "saving_throw",
    "attack_roll",
    "death_save",
    "condition_change",
    "concentration_save",
    "hit_dice",
}


def _redact_event_description(
    event: CharacterHistory,
    character_name: str,
    viewer_user_id: int,
    owner_user_id: int,
    is_gm: bool,
) -> str:
    # Owner or GM → raw description.
    if viewer_user_id == owner_user_id or is_gm:
        return event.description

    # Only hp_change is redacted.
    if event.event_type != "hp_change":
        return event.description

    meta = event.meta or {}
    op = str(meta.get("op") or "").upper()

    if op == "HEAL":
        return f"{character_name} si è curato"
    if op in ("SET_CURRENT", "SET_MAX", "SET_TEMP"):
        return f"{character_name} ha modificato i PF"
    if op == "DAMAGE":
        return event.description

    # Legacy fallback (meta missing): best-effort sniff on description.
    desc_lower = event.description.lower()
    if "cura" in desc_lower or "heal" in desc_lower:
        return f"{character_name} si è curato"
    if "danni" in desc_lower or "danno" in desc_lower or "damage" in desc_lower:
        return event.description
    return f"{character_name} ha modificato i PF"


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _load_session(session_id: int, db: AsyncSession) -> GameSession:
    result = await db.execute(
        select(GameSession)
        .options(selectinload(GameSession.participants).selectinload(SessionParticipant.character))
        .where(GameSession.id == session_id)
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return obj


async def _load_session_by_code(code: str, db: AsyncSession) -> GameSession:
    result = await db.execute(
        select(GameSession)
        .options(selectinload(GameSession.participants).selectinload(SessionParticipant.character))
        .where(GameSession.code == code.upper())
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return obj


def _assert_participant(session: GameSession, user_id: int) -> SessionParticipant:
    for p in session.participants:
        if p.user_id == user_id:
            return p
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a session participant")


async def _find_active_session_for_user(user_id: int, db: AsyncSession) -> Optional[GameSession]:
    """Active session where user is GM or player."""
    result = await db.execute(
        select(GameSession)
        .join(SessionParticipant, SessionParticipant.session_id == GameSession.id)
        .options(selectinload(GameSession.participants).selectinload(SessionParticipant.character))
        .where(
            GameSession.status == SessionStatus.ACTIVE,
            SessionParticipant.user_id == user_id,
        )
    )
    return result.scalars().first()


async def _generate_unique_code(db: AsyncSession) -> str:
    for _ in range(_MAX_CODE_RETRIES):
        code = generate_session_code()
        existing = await db.execute(select(GameSession.id).where(GameSession.code == code))
        if existing.scalar_one_or_none() is None:
            return code
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Could not generate a unique session code. Try again.",
    )


async def session_read(db: AsyncSession, session: GameSession) -> GameSessionRead:
    """GameSessionRead with campaign_name (explicit query: no async lazy-load)."""
    name = None
    if session.campaign_id is not None:
        name = await db.scalar(select(Campaign.name).where(Campaign.id == session.campaign_id))
    return GameSessionRead.model_validate(session).model_copy(update={"campaign_name": name})


def _touch(session: GameSession) -> None:
    session.last_activity_at = _now()


async def _load_live_characters(
    char_ids: list[int],
    db: AsyncSession,
    joined_at_by_char: Optional[dict[int, str]] = None,
    lang: str = "it",
) -> dict[int, dict]:
    """Return raw snapshot dicts keyed by character id.

    Full (un-redacted) data is returned here; redaction happens per viewer
    in get_session_live.

    ``joined_at_by_char`` maps character id → ISO timestamp of when its
    participant joined the session: rolls older than that (or with no
    timestamp at all) are hidden, so pre-session rolls never leak into the
    session view. History is append-only, so checking the last entry suffices.
    """
    if not char_ids:
        return {}
    result = await db.execute(
        select(Character)
        .options(
            selectinload(Character.classes),
            selectinload(Character.items),
            selectinload(Character.abilities),
        )
        .where(Character.id.in_(char_ids))
    )
    out: dict[int, dict] = {}
    for char in result.scalars().all():
        last_roll = None
        history = char.rolls_history or []
        if history and isinstance(history[-1], dict):
            last_roll = history[-1]
        if last_roll is not None and joined_at_by_char is not None:
            joined = joined_at_by_char.get(char.id)
            ts = last_roll.get("timestamp")
            if joined and (not isinstance(ts, str) or ts < joined):
                last_roll = None
        effects, pendings = await character_effect_payload(db, char.id)
        out[char.id] = dict(
            id=char.id,
            user_id=char.user_id,
            name=char.name,
            race=char.race,
            class_summary=char.class_summary,
            total_level=char.total_level,
            hit_points=char.hit_points,
            current_hit_points=char.current_hit_points,
            temp_hp=char.temp_hp or 0,
            ac=char.ac + ac_delta(char, char.ac),
            conditions=char.conditions or {},
            death_saves=char.death_saves or {},
            heroic_inspiration=bool(char.heroic_inspiration),
            last_roll=last_roll,
            hp_bucket=hp_bucket(char),
            armor_category=armor_category(char),
            condition_effects=effects,
            has_pending_save=any(p.status == "pending" for p in pendings),
            is_concentrating=char.concentrating_spell_id is not None,
            active_states=public_states(char, lang),
        )
    return out


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/me", response_model=Optional[GameSessionRead])
async def my_active_session(
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> Optional[GameSessionRead]:
    session = await _find_active_session_for_user(user_id, db)
    if session is None:
        return None
    enc_status = (
        await db.execute(
            select(Encounter.status).where(
                Encounter.session_id == session.id, Encounter.status != "ended"
            )
        )
    ).scalars().first()
    return (await session_read(db, session)).model_copy(update={"encounter_status": enc_status})


async def active_encounter_row(db: AsyncSession, character_id: int):
    """(Encounter, combatant_id) of the PC's active encounter in an active session, or None."""
    return (
        await db.execute(
            select(Encounter, Combatant.id)
            .join(Combatant, Combatant.encounter_id == Encounter.id)
            .join(GameSession, GameSession.id == Encounter.session_id)
            .where(
                Combatant.character_id == character_id,
                Encounter.status == "active",
                GameSession.status == SessionStatus.ACTIVE,
            )
            .limit(1)
        )
    ).first()


@character_turn_router.get("/{character_id}/turn-state", response_model=TurnState)
async def character_turn_state(
    character_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    item_id: int | None = None,
) -> TurnState:
    """``item_id``: l'arma che sta per attaccare; senza, ``attacks_allowed`` è il limite generale e
    ``attacks_allowed_pact`` quello con l'arma del patto."""
    char = (await db.execute(select(Character).where(Character.id == character_id)
                             .options(selectinload(Character.classes), selectinload(Character.items)))).scalar_one_or_none()
    if char is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    if char.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    _, pendings = await character_effect_payload(db, character_id)
    item = next((i for i in char.items if i.id == item_id), None)
    block = {"turn": get_turn(char), "attacks_allowed": attacks_allowed(char, item),
             "attacks_allowed_pact": attacks_allowed(char, with_pact=True)}
    row = await active_encounter_row(db, character_id)
    if row is None:
        return TurnState(in_encounter=False, is_my_turn=False, pending_saves=pendings, **block)
    enc, combatant_id = row
    return TurnState(
        **block,
        pending_saves=pendings,
        in_encounter=True,
        is_my_turn=enc.active_combatant_id == combatant_id,
        round=enc.round,
        session_id=enc.session_id,
    )


def _compute_gm_display_name(tg_user: TelegramUser, custom_title: Optional[str]) -> str:
    """Pick the best human-readable name for the GM/session.

    Priority: explicit title → first_name → @username → fallback "#<user_id>".
    """
    if custom_title and custom_title.strip():
        return custom_title.strip()[:120]
    if tg_user.first_name:
        return tg_user.first_name[:120]
    if tg_user.username:
        return f"@{tg_user.username}"[:120]
    return f"#{tg_user.id}"


@router.post("", response_model=GameSessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: SessionCreateRequest,
    tg_user: Annotated[TelegramUser, Depends(get_current_telegram_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> GameSessionRead:
    user_id = tg_user.id
    # Users can only be in one active session at a time (regardless of role)
    existing = await _find_active_session_for_user(user_id, db)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an active session",
        )

    title = body.title
    if body.campaign_id is not None:
        camp = await db.get(Campaign, body.campaign_id)
        if camp is None or camp.gm_user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="gm_only")
        active = await db.scalar(select(GameSession.id).where(
            GameSession.campaign_id == camp.id, GameSession.status == SessionStatus.ACTIVE
        ))
        if active is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="campaign_session_active")
        title = title or camp.name

    code = await _generate_unique_code(db)
    now = _now()
    gm_display_name = _compute_gm_display_name(tg_user, title)
    session = GameSession(
        campaign_id=body.campaign_id,
        code=code,
        gm_user_id=user_id,
        status=SessionStatus.ACTIVE,
        title=title,
        gm_display_name=gm_display_name,
        created_at=now,
        last_activity_at=now,
    )
    db.add(session)
    await db.flush()
    if body.campaign_id is not None:  # link the nearest unlinked planned evening within ±12h
        t0 = datetime.utcnow()
        rows = (await db.execute(select(CampaignSchedule).where(
            CampaignSchedule.campaign_id == body.campaign_id, CampaignSchedule.session_id.is_(None)
        ))).scalars().all()
        near = [(abs((datetime.fromisoformat(r.starts_at) - t0).total_seconds()), r.id, r) for r in rows]
        near = [x for x in near if x[0] <= 12 * 3600]
        if near:
            min(near, key=lambda x: x[:2])[2].session_id = session.id
    db.add(SessionParticipant(
        session_id=session.id,
        user_id=user_id,
        role=SessionRole.GAME_MASTER,
        character_id=None,
        joined_at=now,
    ))
    await db.flush()
    await db.refresh(session, attribute_names=["participants"])
    return await session_read(db, session)


@router.post("/join", response_model=GameSessionRead)
async def join_session(
    body: SessionJoinRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> GameSessionRead:
    # Users can only be in one active session at a time
    existing = await _find_active_session_for_user(user_id, db)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an active session",
        )

    session = await _load_session_by_code(body.code, db)
    if session.status != SessionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Session is closed",
        )

    # Verify character ownership
    char_result = await db.execute(
        select(Character).where(Character.id == body.character_id)
    )
    char = char_result.scalar_one_or_none()
    if char is None or char.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Character not found or not yours",
        )

    # Campaign sessions expose the party stash: the code must not bypass membership.
    if session.campaign_id is not None:
        member = await db.scalar(select(CampaignMember).where(
            CampaignMember.campaign_id == session.campaign_id,
            CampaignMember.character_id == char.id,
        ))
        if member is None:
            raise HTTPException(status_code=422, detail="not_a_member")
        if member.status == "dead":
            raise HTTPException(status_code=422, detail="character_dead")

    db.add(SessionParticipant(
        session_id=session.id,
        user_id=user_id,
        role=SessionRole.PLAYER,
        character_id=char.id,
        character=char,
        display_name=char.name,
        joined_at=_now(),
        dice_stats_start=dice_baseline(session, char),
    ))
    _touch(session)
    await db.flush()
    await db.refresh(session, attribute_names=["participants"])
    return await session_read(db, session)


@router.get("/{session_id}", response_model=GameSessionRead)
async def get_session(
    session_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> GameSessionRead:
    session = await _load_session(session_id, db)
    _assert_participant(session, user_id)
    return await session_read(db, session)


@router.get("/{session_id}/live", response_model=GameSessionLiveRead)
async def get_session_live(
    session_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    lang: Annotated[str, Depends(get_current_lang)],
) -> GameSessionLiveRead:
    session = await _load_session(session_id, db)
    _assert_participant(session, user_id)

    char_ids = [p.character_id for p in session.participants if p.character_id is not None]
    joined_at_by_char = {
        p.character_id: p.joined_at
        for p in session.participants
        if p.character_id is not None
    }
    raw_map = await _load_live_characters(char_ids, db, joined_at_by_char, lang)
    viewer_is_gm = (user_id == session.gm_user_id)

    snapshots: list[CharacterLiveSnapshot] = []
    for raw in raw_map.values():
        owner_id = raw["user_id"]
        full = viewer_is_gm or (owner_id == user_id)
        if full:
            snapshots.append(CharacterLiveSnapshot(
                id=raw["id"],
                name=raw["name"],
                race=raw["race"],
                class_summary=raw["class_summary"],
                total_level=raw["total_level"],
                hit_points=raw["hit_points"],
                current_hit_points=raw["current_hit_points"],
                temp_hp=raw["temp_hp"],
                ac=raw["ac"],
                conditions=raw["conditions"],
                condition_effects=raw["condition_effects"],
                has_pending_save=raw["has_pending_save"],
                is_concentrating=raw["is_concentrating"],
                death_saves=raw["death_saves"],
                heroic_inspiration=raw["heroic_inspiration"],
                last_roll=raw["last_roll"],
                hp_bucket=raw["hp_bucket"],
                armor_category=raw["armor_category"],
                active_states=raw["active_states"],
            ))
        else:
            snapshots.append(CharacterLiveSnapshot(
                id=raw["id"],
                name=raw["name"],
                race=raw["race"],
                class_summary=raw["class_summary"],
                total_level=raw["total_level"],
                hit_points=None,
                current_hit_points=None,
                temp_hp=None,
                ac=None,
                conditions=raw["conditions"],
                condition_effects=raw["condition_effects"],
                has_pending_save=raw["has_pending_save"],
                is_concentrating=raw["is_concentrating"],
                death_saves=None,
                heroic_inspiration=raw["heroic_inspiration"],
                last_roll=raw["last_roll"],
                hp_bucket=raw["hp_bucket"],
                armor_category=None,
                active_states=raw["active_states"],
            ))

    if session.status == SessionStatus.ACTIVE:
        _touch(session)

    enc_result = await db.execute(
        select(Encounter)
        .options(selectinload(Encounter.combatants))
        .where(Encounter.session_id == session.id, Encounter.status != "ended")
    )
    open_encounter = enc_result.scalars().first()
    encounter_block = (
        await build_encounter_block(db, open_encounter, viewer_is_gm=viewer_is_gm, lang=lang)
        if open_encounter is not None
        else None
    )

    return GameSessionLiveRead(
        id=session.id,
        code=session.code,
        gm_user_id=session.gm_user_id,
        gm_display_name=session.gm_display_name,
        status=session.status.value if hasattr(session.status, "value") else str(session.status),
        title=session.title,
        created_at=session.created_at,
        last_activity_at=session.last_activity_at,
        closed_at=session.closed_at,
        campaign_id=session.campaign_id,
        campaign_name=(await session_read(db, session)).campaign_name,
        participants=[
            {
                "user_id": p.user_id,
                "role": p.role.value if hasattr(p.role, "value") else str(p.role),
                "character_id": p.character_id,
                "display_name": p.display_name,
                "character_name": p.character_name,
                "joined_at": p.joined_at,
            }
            for p in session.participants
        ],
        live_characters=snapshots,
        encounter=encounter_block,
    )


@router.post("/{session_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_session(
    session_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> None:
    session = await _load_session(session_id, db)
    participant = _assert_participant(session, user_id)
    if session.status != SessionStatus.ACTIVE:
        return None

    # GM leaving closes the whole session
    if user_id == session.gm_user_id:
        await close_game_session(db, session)
    else:
        record_departure(session, participant)
        await db.delete(participant)
    _touch(session)
    return None


@router.post("/{session_id}/close", status_code=status.HTTP_204_NO_CONTENT)
async def close_session(
    session_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> None:
    session = await _load_session(session_id, db)
    if user_id != session.gm_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the Game Master can close the session",
        )
    await close_game_session(db, session)
    return None


@router.get("/{session_id}/recap")
async def get_session_recap(
    session_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> dict:
    """End-of-evening snapshot: GM, participants or members of the session's campaign."""
    session = await _load_session(session_id, db)
    allowed = (user_id == session.gm_user_id or any(p.user_id == user_id for p in session.participants)
               or any(d.get("user_id") == user_id for d in session.departed or []))
    if not allowed and session.campaign_id is not None:
        allowed = await db.scalar(select(CampaignMember.id).where(
            CampaignMember.campaign_id == session.campaign_id, CampaignMember.user_id == user_id,
        ).limit(1)) is not None
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    if session.recap is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="recap_not_found")
    return session.recap


@router.get("/{session_id}/messages", response_model=list[SessionMessageRead])
async def list_messages(
    session_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    after_id: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[SessionMessage]:
    session = await _load_session(session_id, db)
    _assert_participant(session, user_id)
    stmt = (
        select(SessionMessage)
        .where(SessionMessage.session_id == session_id)
        .where(
            or_(
                SessionMessage.recipient_user_id.is_(None),
                SessionMessage.recipient_user_id == user_id,
                SessionMessage.user_id == user_id,
            )
        )
    )
    if after_id > 0:
        stmt = stmt.where(SessionMessage.id > after_id)
    stmt = stmt.order_by(SessionMessage.id.asc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


_SLOW_MODE_SECONDS = 3.0


@router.post(
    "/{session_id}/messages",
    response_model=SessionMessageRead,
    status_code=status.HTTP_201_CREATED,
)
async def post_message(
    session_id: int,
    body: SessionMessageCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> SessionMessage:
    session = await _load_session(session_id, db)
    sender = _assert_participant(session, user_id)
    if session.status != SessionStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Session is closed")

    recipient_id: Optional[int] = body.recipient_user_id
    if recipient_id is not None:
        recipient = next((p for p in session.participants if p.user_id == recipient_id), None)
        if recipient is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Recipient not in session")
        if recipient_id == user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot whisper to yourself")

    # Slow mode anti-spam: same user must wait between messages in the same session.
    last_msg = await db.scalar(
        select(SessionMessage)
        .where(SessionMessage.session_id == session_id)
        .where(SessionMessage.user_id == user_id)
        .where(SessionMessage.trade_payload.is_(None))  # feed/system rows are not chat
        .order_by(SessionMessage.sent_at.desc())
        .limit(1)
    )
    now_iso = _now()
    if last_msg is not None:
        try:
            elapsed = (
                datetime.fromisoformat(now_iso) - datetime.fromisoformat(last_msg.sent_at)
            ).total_seconds()
        except ValueError:
            elapsed = _SLOW_MODE_SECONDS  # malformed timestamp → don't block
        if elapsed < _SLOW_MODE_SECONDS:
            retry_after = round(_SLOW_MODE_SECONDS - elapsed, 2)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": "slow_mode", "retry_after": retry_after},
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

    if sender.role == SessionRole.GAME_MASTER:
        sender_display_name = "__GM__"
    else:
        sender_display_name = sender.display_name or f"#{user_id}"

    msg = SessionMessage(
        session_id=session_id,
        user_id=user_id,
        role=sender.role,
        body=body.body.strip(),
        sent_at=now_iso,
        recipient_user_id=recipient_id,
        sender_display_name=sender_display_name,
    )
    db.add(msg)
    _touch(session)
    await db.flush()
    return msg


@router.get(
    "/{code}/participants/{user_id}/identity",
    response_model=IdentityView,
)
async def get_participant_identity(
    code: str,
    user_id: int,
    caller_user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> IdentityView:
    session = await _load_session_by_code(code, db)
    _assert_participant(session, caller_user_id)

    target = next((p for p in session.participants if p.user_id == user_id), None)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant not found",
        )
    if target.character_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participant has no character",
        )

    result = await db.execute(
        select(Character).where(Character.id == target.character_id)
    )
    char = result.scalar_one_or_none()
    if char is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Character not found",
        )

    settings_ = char.settings or {}
    show_private = bool(settings_.get("show_private_identity")) or caller_user_id == user_id

    def _join_list(val) -> Optional[str]:
        if isinstance(val, dict):  # proficiencies by category
            val = [x for v in val.values() for x in v]
        if not val:
            return None
        if isinstance(val, list):
            cleaned = [str(x).strip() for x in val if str(x).strip()]
            return ", ".join(cleaned) if cleaned else None
        return str(val) or None

    personality = char.personality or {}

    return IdentityView(
        user_id=target.user_id,
        character_id=char.id,
        name=char.name,
        race=char.race,
        gender=char.gender,
        alignment=char.alignment,
        speed=char.speed,
        languages=_join_list(char.languages),
        general_proficiencies=_join_list(char.general_proficiencies),
        background=char.background if show_private else None,
        personality_traits=(personality.get("traits") or None) if show_private else None,
        ideals=(personality.get("ideals") or None) if show_private else None,
        bonds=(personality.get("bonds") or None) if show_private else None,
        flaws=(personality.get("flaws") or None) if show_private else None,
        show_private=show_private,
    )


async def _create_or_merge_item(db: AsyncSession, char: Character, new, *, is_equipped: bool) -> Item:
    """Put an ItemCreate in `char`'s inventory: stack onto a same-name generic root, else create."""
    is_box = isinstance((new.item_metadata or {}).get("container"), dict)
    if new.item_type == "generic" and not is_box:
        existing = next(
            (it for it in char.items
             if it.item_type == "generic" and it.name == new.name
             and it.container_id is None and not is_container(it)),
            None,
        )
        if existing is not None:
            existing.quantity += new.quantity
            return existing
    row = Item(
        character_id=char.id, name=new.name, description=new.description,
        weight=new.weight, quantity=new.quantity, item_type=new.item_type,
        item_metadata=json.dumps(new.item_metadata) if new.item_metadata else None,
        is_equipped=is_equipped,
    )
    db.add(row)
    await db.flush()
    return row


@router.post(
    "/{session_id}/gm/grant_item",
    response_model=GMGrantItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def gm_grant_item(
    session_id: int,
    body: GMGrantItemRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> GMGrantItemResponse:
    """GM-only: deliver a freshly created item to one or more session players.

    Creates the item in each recipient's inventory and posts a private whisper
    in the session feed. Players without an associated character are skipped.
    """
    session_obj = await _load_session(session_id, db)
    if user_id != session_obj.gm_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the Game Master can grant items",
        )
    if session_obj.status != SessionStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Session is closed")

    granting_box = isinstance((body.item.item_metadata or {}).get("container"), dict)
    if granting_box and body.item.quantity != 1:
        raise HTTPException(status_code=422, detail="container_quantity")
    now_iso = _now()
    results: list[GMGrantItemResult] = []

    for rid in body.recipient_user_ids:
        participant = next((p for p in session_obj.participants if p.user_id == rid), None)
        if participant is None or participant.role != SessionRole.PLAYER:
            results.append(GMGrantItemResult(user_id=rid, status="not_a_player"))
            continue
        if participant.character_id is None:
            results.append(GMGrantItemResult(user_id=rid, status="no_character"))
            continue

        char_res = await db.execute(
            select(Character)
            .options(selectinload(Character.items))
            .where(Character.id == participant.character_id)
        )
        char = char_res.scalar_one_or_none()
        if char is None:
            results.append(GMGrantItemResult(user_id=rid, status="character_not_found"))
            continue

        granted_item_id = (
            await _create_or_merge_item(db, char, body.item, is_equipped=body.item.is_equipped)
        ).id

        char.recalculate_encumbrance()

        whisper_body = f"Il GM ti ha consegnato: {body.item.name} (×{body.item.quantity})"
        msg = SessionMessage(
            session_id=session_obj.id,
            user_id=user_id,
            role=SessionRole.GAME_MASTER,
            body=whisper_body,
            sent_at=now_iso,
            recipient_user_id=rid,
            sender_display_name="__GM__",
            item_id=granted_item_id,
            item_name=body.item.name,
            item_quantity=body.item.quantity,
        )
        db.add(msg)

        results.append(GMGrantItemResult(
            user_id=rid,
            character_id=char.id,
            item_id=granted_item_id,
            status="ok",
        ))

        if telegram_notify.notifications_enabled(char, "gm_events"):
            await telegram_notify.send_telegram_message(
                rid,
                f"🎁 Il GM ti ha consegnato: {body.item.name} (×{body.item.quantity})",
                button=("Apri l'inventario",
                        telegram_notify.miniapp_url(f"/char/{char.id}/inventory")),
            )

    _touch(session_obj)
    await db.flush()
    return GMGrantItemResponse(results=results)


_COIN_LABELS = {"copper": "rame", "silver": "argento", "electrum": "electrum", "gold": "oro", "platinum": "platino"}


async def _load_char_full(db: AsyncSession, char_id: int) -> Character:
    result = await db.execute(
        select(Character)
        .options(
            selectinload(Character.classes),
            selectinload(Character.ability_scores),
            selectinload(Character.spells),
            selectinload(Character.spell_slots),
            selectinload(Character.items),
            selectinload(Character.currency),
            selectinload(Character.abilities),
            selectinload(Character.maps),
        )
        .where(Character.id == char_id)
    )
    return result.scalar_one()


async def _settle_move(db, actor: Character, other: Character, old_con_mod, removed: list, lang: str) -> list[dict]:
    """After an item/coin move out of `actor`: CON-HP, class feature uses, encumbrance of both, item_unequipped dispatch.

    `removed` = (id, type, name, slot) of rows taken off the actor's paper-doll. Returns notifications.
    """
    await apply_con_hp(db, actor, old_con_mod)
    await db.flush()
    for c in (actor, other):
        await db.refresh(c, attribute_names=["items"])
        c.recalculate_encumbrance()
    await db.flush()
    await sync_cataloged_features(db, actor, lang)
    notifications: list[dict] = []
    for item_id, item_type, _name, slot in removed:
        firing = await dispatch(db, actor, "item_unequipped", {
            "item_id": item_id, "item_type": item_type,
            "slot": slot.value if slot is not None else None,
            "was_equipped": True, "is_equipped": False,
        })
        notifications += collect_homebrew_notifications(firing)
    return notifications


async def _move_response(db, actor: Character, removed: list, notifications: list[dict]) -> CharacterFull:
    response = await build_character_response(db, actor)
    response.unequipped_item_names = [name for _i, _t, name, _s in removed]
    if notifications:
        response.homebrew_notifications = notifications
    return response


@router.post("/{session_id}/trade", response_model=CharacterFull)
async def trade(
    session_id: int,
    body: TradeRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    """Player action: give an item/container/coins to another PG of the session.

    Posts a public feed row (no item_* columns, so it is not read as a GM grant)
    and notifies the recipient. Returns the sender's updated sheet.
    """
    session_obj = await _load_session(session_id, db)
    if session_obj.status != SessionStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Session is closed")
    me = _assert_participant(session_obj, user_id)
    if me.role != SessionRole.PLAYER or me.character_id is None or me.character_id != body.from_character_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_your_character")
    if (body.item_id is None) == (body.coins is None):
        raise HTTPException(status_code=422, detail="nothing_to_give")
    other = next((p for p in session_obj.participants if p.user_id == body.to_user_id), None)
    if (other is None or other.role != SessionRole.PLAYER or other.character_id is None
            or other.user_id == user_id):
        raise HTTPException(status_code=422, detail="invalid_recipient")

    sender = await _load_char_full(db, me.character_id)
    recipient = await _load_char_full(db, other.character_id)
    old_con_mod = effective_con_mod(sender)

    snapshots: list[dict] = []
    removed: list = []
    coins_given: dict[str, int] = {}
    if body.item_id is not None:
        snap, taken = await give_item(db, sender, recipient, body.item_id, body.quantity)
        # read what dispatch needs now: a merged-away root is deleted by the flush
        removed = [(i.id, i.item_type, i.name, slot) for i, slot in taken]
        snapshots = [snap]
        what = f"{snap['name']} (×{snap['quantity']})"
    else:
        coins_given = give_coins(sender, recipient, body.coins)
        what = _coins_text(coins_given)

    notifications = await _settle_move(db, sender, recipient, old_con_mod, removed, lang)

    payload = {
        "kind": "trade",
        "from": {"character_id": sender.id, "name": sender.name},
        "to": {"character_id": recipient.id, "name": recipient.name},
        "items": snapshots,
        "coins": coins_given,
    }
    db.add(SessionMessage(
        session_id=session_obj.id,
        user_id=user_id,
        role=SessionRole.PLAYER,
        body=f"{sender.name} ha dato a {recipient.name}: {what}",
        sent_at=_now(),
        sender_display_name=me.display_name or sender.name,
        trade_payload=json.dumps(payload),
    ))
    _touch(session_obj)
    await db.flush()

    if telegram_notify.notifications_enabled(recipient, "gm_events"):
        await telegram_notify.send_telegram_message(
            body.to_user_id,
            f"🤝 {sender.name} ti ha dato: {what}",
            button=("Apri l'inventario",
                    telegram_notify.miniapp_url(f"/char/{recipient.id}/inventory")),
        )

    return await _move_response(db, sender, removed, notifications)


@router.post("/{session_id}/inspiration/give", response_model=CharacterFull)
async def give_inspiration(
    session_id: int,
    body: InspirationGiveRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CharacterFull:
    """Cede l'Ispirazione a un compagno che ne è privo. 2024: ricevendone un'altra (``PATCH /inspiration`` con una
    già in mano) quella in più si può cedere e chi cede tiene la propria. 2014: si cede la propria e la si perde."""
    session_obj = await _load_session(session_id, db)
    if session_obj.status != SessionStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Session is closed")
    me = _assert_participant(session_obj, user_id)
    if me.role != SessionRole.PLAYER or me.character_id is None or me.character_id != body.from_character_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_your_character")
    other = next((p for p in session_obj.participants if p.user_id == body.to_user_id), None)
    if (other is None or other.role != SessionRole.PLAYER or other.character_id is None
            or other.user_id == user_id):
        raise HTTPException(status_code=422, detail="invalid_recipient")
    sender = await _load_char_full(db, me.character_id)
    recipient = await _load_char_full(db, other.character_id)
    is_2024 = character_edition(sender) == "2024"
    if is_2024 and not ((sender.settings or {}).get("inspiration_extra") and sender.heroic_inspiration):
        raise HTTPException(status_code=409, detail={"code": "no_extra_inspiration"})
    if not is_2024 and not sender.heroic_inspiration:
        raise HTTPException(status_code=409, detail={"code": "no_inspiration"})
    if recipient.heroic_inspiration:
        raise HTTPException(status_code=409, detail={"code": "recipient_has_inspiration"})
    if is_2024:  # chi cede conserva la propria: si cede quella ricevuta in più
        sender.settings = {k: v for k, v in sender.settings.items() if k != "inspiration_extra"}
    else:  # 2014 (decisione del coordinatore, il capitolo non è nei testi di lavoro): chi cede la perde
        sender.heroic_inspiration = False
    recipient.heroic_inspiration = True
    for char, text in ((sender, f"Ispirazione Eroica ceduta a {recipient.name}"),
                       (recipient, f"Ispirazione Eroica ricevuta da {sender.name}")):
        db.add(CharacterHistory(character_id=char.id, timestamp=_now(), event_type="other", description=text))
    db.add(SessionMessage(
        session_id=session_obj.id, user_id=session_obj.gm_user_id, role=SessionRole.GAME_MASTER,
        body=f"{sender.name} ha ceduto l'Ispirazione Eroica a {recipient.name}", sent_at=_now(),
        sender_display_name="__GM__",
    ))
    _touch(session_obj)
    await db.flush()
    if telegram_notify.notifications_enabled(recipient, "gm_events"):
        await telegram_notify.send_telegram_message(
            body.to_user_id, f"✨ {sender.name} ti ha ceduto l'Ispirazione Eroica")
    return await build_character_response(db, sender)


_STASH = {"character_id": None, "name": "stash"}
_GM = {"character_id": None, "name": "gm"}


async def _stash_ctx(session_id: int, user_id: int, db: AsyncSession, *, mutate: bool = True):
    """Session + caller's participant row + the campaign's stash (items and currency only)."""
    session_obj = await _load_session(session_id, db)
    me = _assert_participant(session_obj, user_id)
    if session_obj.campaign_id is None:
        raise HTTPException(status_code=422, detail="no_campaign")
    if mutate and session_obj.status != SessionStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Session is closed")
    camp = await db.get(Campaign, session_obj.campaign_id)
    return session_obj, me, await _load_stash(db, camp.stash_character_id)


async def _load_stash(db: AsyncSession, stash_id: int) -> Character:
    return (await db.execute(
        select(Character)
        .options(selectinload(Character.items), selectinload(Character.currency))
        .where(Character.id == stash_id)
    )).scalar_one()


async def _stash_read(db: AsyncSession, stash: Character) -> CampaignStash:
    await db.refresh(stash, attribute_names=["items", "currency"])
    return CampaignStash(
        items=[ItemRead.model_validate(i) for i in sorted(stash.items, key=lambda i: i.id)],
        currency=CurrencyRead.model_validate(stash.currency),
    )


def _coins_text(coins: dict[str, int]) -> str:
    return ", ".join(f"{n} {_COIN_LABELS[c]}" for c, n in coins.items())


def _post_stash_message(db, session_obj, user_id, role, display_name, body, kind, frm, to, snaps, coins):
    db.add(SessionMessage(
        session_id=session_obj.id, user_id=user_id, role=role, body=body,
        sent_at=_now(), sender_display_name=display_name,
        trade_payload=json.dumps({"kind": kind, "from": frm, "to": to, "items": snaps, "coins": coins}),
    ))
    _touch(session_obj)


@router.get("/{session_id}/stash", response_model=CampaignStash)
async def get_stash(
    session_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CampaignStash:
    _s, _me, stash = await _stash_ctx(session_id, user_id, db, mutate=False)
    return await _stash_read(db, stash)


async def _player_stash_move(session_id, user_id, db, char_id, item_id, quantity, coins, putting: bool, lang: str):
    """Shared body of put (PG -> stash) and take (stash -> PG)."""
    session_obj, me, stash = await _stash_ctx(session_id, user_id, db)
    if me.role != SessionRole.PLAYER or me.character_id is None or me.character_id != char_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not_your_character")
    if (item_id is None) == (coins is None):
        raise HTTPException(status_code=422, detail="nothing_to_give")
    pg = await _load_char_full(db, me.character_id)
    old_con_mod = effective_con_mod(pg)
    src, dst = (pg, stash) if putting else (stash, pg)

    snapshots: list[dict] = []
    removed: list = []
    moved: dict[str, int] = {}
    if item_id is not None:
        snap, taken = await give_item(db, src, dst, item_id, quantity)
        if putting:  # only the PG has a paper-doll; read before the flush
            removed = [(i.id, i.item_type, i.name, slot) for i, slot in taken]
        snapshots = [snap]
        what = f"{snap['name']} (×{snap['quantity']})"
    else:
        moved = give_coins(src, dst, coins)
        what = _coins_text(moved)

    # on take the PG's CON can't change: apply_con_hp is a no-op there
    notifications = await _settle_move(db, pg, stash, old_con_mod, removed, lang)

    me_ref = {"character_id": pg.id, "name": pg.name}
    verb = "messo nel" if putting else "preso dal"
    _post_stash_message(
        db, session_obj, user_id, SessionRole.PLAYER, me.display_name or pg.name,
        f"{pg.name} ha {verb} deposito: {what}",
        "stash_put" if putting else "stash_take",
        me_ref if putting else _STASH, _STASH if putting else me_ref, snapshots, moved,
    )
    await db.flush()
    return await _move_response(db, pg, removed, notifications)


@router.post("/{session_id}/stash/put", response_model=CharacterFull)
async def stash_put(
    session_id: int,
    body: StashPutRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    """Player: move an item/container/coins from their PG into the party stash."""
    return await _player_stash_move(
        session_id, user_id, db, body.from_character_id, body.item_id, body.quantity, body.coins, True, lang)


@router.post("/{session_id}/stash/take", response_model=CharacterFull)
async def stash_take(
    session_id: int,
    body: StashTakeRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    """Player: move an item/container/coins from the party stash to their PG."""
    return await _player_stash_move(
        session_id, user_id, db, body.to_character_id, body.item_id, body.quantity, body.coins, False, lang)


async def _gm_stash_ctx(session_id, user_id, db):
    ctx = await _stash_ctx(session_id, user_id, db)
    if ctx[0].gm_user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="gm_only")
    return ctx


@router.post("/{session_id}/stash/gm-add", response_model=CampaignStash)
async def stash_gm_add(
    session_id: int,
    body: StashGMAddRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CampaignStash:
    """GM: create an item or coins straight into the party stash."""
    session_obj, _me, stash = await _gm_stash_ctx(session_id, user_id, db)
    if (body.item is None) == (body.coins is None):
        raise HTTPException(status_code=422, detail="nothing_to_give")
    snapshots: list[dict] = []
    added: dict[str, int] = {}
    if body.item is not None:
        new = body.item
        is_box = isinstance((new.item_metadata or {}).get("container"), dict)
        if is_box and new.quantity != 1:
            raise HTTPException(status_code=422, detail="container_quantity")
        if new.quantity < 1:
            raise HTTPException(status_code=422, detail="invalid_quantity")
        row = await _create_or_merge_item(db, stash, new, is_equipped=False)
        await db.flush()
        await db.refresh(stash, attribute_names=["items"])
        snapshots = [trade_snapshot(stash.items, row.id, new.quantity)]
        what = f"{snapshots[0]['name']} (×{snapshots[0]['quantity']})"
    else:
        added = add_coins(stash, body.coins)
        what = _coins_text(added)
    await db.refresh(stash, attribute_names=["items"])
    stash.recalculate_encumbrance()
    _post_stash_message(
        db, session_obj, user_id, SessionRole.GAME_MASTER, "__GM__",
        f"Il master ha messo nel deposito: {what}", "gm_stash_add", _GM, _STASH, snapshots, added)
    await db.flush()
    return await _stash_read(db, stash)


@router.post("/{session_id}/stash/gm-remove", response_model=CampaignStash)
async def stash_gm_remove(
    session_id: int,
    body: StashGMRemoveRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CampaignStash:
    """GM: destroy an item (or part of a stack) or coins from the party stash."""
    session_obj, _me, stash = await _gm_stash_ctx(session_id, user_id, db)
    if (body.item_id is None) == (body.coins is None):
        raise HTTPException(status_code=422, detail="nothing_to_give")
    snapshots: list[dict] = []
    removed: dict[str, int] = {}
    if body.item_id is not None:
        snap = await remove_item(db, stash, body.item_id, body.quantity)
        snapshots = [snap]
        what = f"{snap['name']} (×{snap['quantity']})"
    else:
        removed = remove_coins(stash, body.coins)
        what = _coins_text(removed)
    await db.flush()
    await db.refresh(stash, attribute_names=["items"])
    stash.recalculate_encumbrance()
    _post_stash_message(
        db, session_obj, user_id, SessionRole.GAME_MASTER, "__GM__",
        f"Il master ha tolto dal deposito: {what}", "gm_stash_remove", _STASH, _GM, snapshots, removed)
    await db.flush()
    return await _stash_read(db, stash)


@router.get(
    "/{code}/feed",
    response_model=SessionFeedResponse,
)
async def get_session_feed(
    code: str,
    caller_user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    since: Annotated[Optional[str], Query()] = None,
    before: Annotated[Optional[str], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> SessionFeedResponse:
    if since is not None and before is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use either 'since' or 'before', not both",
        )

    session = await _load_session_by_code(code, db)
    _assert_participant(session, caller_user_id)

    is_gm = session.gm_user_id == caller_user_id
    session_start = session.created_at

    char_ids: list[int] = []
    char_meta: dict[int, tuple[int, str]] = {}
    for p in session.participants:
        if p.character_id is not None:
            char_ids.append(p.character_id)

    if char_ids:
        result = await db.execute(
            select(Character.id, Character.user_id, Character.name).where(
                Character.id.in_(char_ids)
            )
        )
        for cid, owner, name in result.all():
            char_meta[cid] = (owner, name)

    # Messages
    msg_stmt = select(SessionMessage).where(
        SessionMessage.session_id == session.id,
        SessionMessage.sent_at >= session_start,
    )
    if since:
        msg_stmt = msg_stmt.where(SessionMessage.sent_at > since)
    if before:
        msg_stmt = msg_stmt.where(SessionMessage.sent_at < before)
    msg_stmt = msg_stmt.order_by(SessionMessage.sent_at.asc(), SessionMessage.id.asc())
    msg_result = await db.execute(msg_stmt)
    messages = list(msg_result.scalars().all())

    # Events
    events: list[CharacterHistory] = []
    if char_ids:
        ev_stmt = select(CharacterHistory).where(
            CharacterHistory.character_id.in_(char_ids),
            CharacterHistory.timestamp >= session_start,
            CharacterHistory.event_type.in_(_SESSION_FEED_EVENT_TYPES),
        )
        if since:
            ev_stmt = ev_stmt.where(CharacterHistory.timestamp > since)
        if before:
            ev_stmt = ev_stmt.where(CharacterHistory.timestamp < before)
        ev_stmt = ev_stmt.order_by(CharacterHistory.timestamp.asc(), CharacterHistory.id.asc())
        ev_result = await db.execute(ev_stmt)
        events = list(ev_result.scalars().all())

    items: list[SessionFeedItem] = []

    for m in messages:
        if m.recipient_user_id is not None:
            if not (
                caller_user_id == m.user_id
                or caller_user_id == m.recipient_user_id
                or is_gm
            ):
                continue
        sender_role = "game_master" if m.user_id == session.gm_user_id else "player"
        items.append(SessionFeedItem(
            type="message",
            timestamp=m.sent_at,
            message_id=m.id,
            user_id=m.user_id,
            display_name=m.sender_display_name,
            role=sender_role,
            body=m.body,
            recipient_user_id=m.recipient_user_id,
            item_id=m.item_id,
            item_name=m.item_name,
            item_quantity=m.item_quantity,
            trade=json.loads(m.trade_payload) if m.trade_payload else None,
        ))

    for e in events:
        owner_id, char_name = char_meta.get(e.character_id, (None, f"#{e.character_id}"))
        if owner_id is None:
            continue
        redacted = _redact_event_description(e, char_name, caller_user_id, owner_id, is_gm)
        meta_op = None
        if e.meta and isinstance(e.meta, dict):
            op_val = e.meta.get("op")
            if isinstance(op_val, str):
                meta_op = op_val
        items.append(SessionFeedItem(
            type="event",
            timestamp=e.timestamp,
            event_id=e.id,
            character_id=e.character_id,
            character_name=char_name,
            owner_user_id=owner_id,
            event_type=e.event_type,
            description=redacted,
            op=meta_op,
        ))

    def _sort_key(it: SessionFeedItem):
        sec = it.message_id if it.type == "message" else (it.event_id or 0)
        return (it.timestamp, 0 if it.type == "message" else 1, sec or 0)

    items.sort(key=_sort_key)

    has_more = len(items) > limit
    if has_more:
        if since is not None:
            items = items[:limit]      # earliest-N for since cursor
        else:
            items = items[-limit:]     # latest-N for before or no-param

    return SessionFeedResponse(items=items, has_more=has_more)
