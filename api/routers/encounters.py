"""Combat tracker endpoints (encounters inside game sessions).

The GM opens an encounter (light = initiative/turns only, full = monsters
with HP/AC too), players roll their own initiative, the GM drives turns.
Spec: docs/superpowers/specs/2026-06-09-combat-tracker-design.md
"""

from __future__ import annotations

import logging
import os
import random
from typing import Annotated, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.database import get_db
from api.routers.sessions import _assert_participant, _load_session, _now, _touch
from api.schemas.encounter import (
    CombatantAddRequest,
    CombatantPatchRequest,
    EncounterCreateRequest,
    EncounterLive,
    EncounterStartRequest,
    InitiativeRollRequest,
    ReorderRequest,
)
from api.services.encounter_view import build_encounter_block
from core.db.models import (
    Character,
    Combatant,
    Encounter,
    GameSession,
    SessionMessage,
    SessionRole,
    SessionStatus,
)
from core.game.stats import effective_ability_score

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["encounters"])

_BOT_TOKEN = os.environ.get("BOT_TOKEN", "")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_gm(session: GameSession, user_id: int) -> None:
    if user_id != session.gm_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the Game Master can do this",
        )


def _assert_session_active(session: GameSession) -> None:
    if session.status != SessionStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Session is closed")


async def _load_open_encounter(session_id: int, db: AsyncSession) -> Optional[Encounter]:
    result = await db.execute(
        select(Encounter)
        .options(selectinload(Encounter.combatants))
        .where(Encounter.session_id == session_id, Encounter.status != "ended")
    )
    return result.scalars().first()


async def _require_open_encounter(session_id: int, db: AsyncSession) -> Encounter:
    enc = await _load_open_encounter(session_id, db)
    if enc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No open encounter")
    return enc


def _dex_modifier(char: Character) -> int:
    """Same effective-DEX resolution the sheet shows (CharacterFull)."""
    base = next((a.value for a in (char.ability_scores or []) if a.name == "dexterity"), 10)
    equipped = [i for i in (char.items or []) if i.is_equipped]
    effective, _ = effective_ability_score("dexterity", base, equipped)
    return (effective - 10) // 2


async def _add_missing_pc_combatants(
    session: GameSession, enc: Encounter, db: AsyncSession
) -> list[Combatant]:
    # Query esplicita: leggere enc.combatants su un'istanza appena flushata
    # scatenerebbe un lazy-load sincrono (MissingGreenlet) in contesto async.
    res = await db.execute(
        select(Combatant.character_id).where(
            Combatant.encounter_id == enc.id,
            Combatant.character_id.is_not(None),
        )
    )
    existing = set(res.scalars().all())
    added: list[Combatant] = []
    for p in session.participants:
        if p.character_id is None or p.character_id in existing:
            continue
        res = await db.execute(
            select(Character)
            .options(selectinload(Character.ability_scores), selectinload(Character.items))
            .where(Character.id == p.character_id)
        )
        char = res.scalar_one_or_none()
        if char is None:
            continue
        comb = Combatant(
            encounter_id=enc.id,
            kind="pc",
            character_id=char.id,
            owner_user_id=p.user_id,
            name=char.name,
            initiative_mod=_dex_modifier(char),
            created_at=_now(),
        )
        db.add(comb)
        added.append(comb)
    return added


def _ordered(combatants: list[Combatant]) -> list[Combatant]:
    rows = [c for c in combatants if c.sort_order is not None]
    rows.sort(key=lambda c: (c.sort_order, c.id))
    return rows


def _system_feed_message(session: GameSession, body: str) -> SessionMessage:
    return SessionMessage(
        session_id=session.id,
        user_id=session.gm_user_id,
        role=SessionRole.GAME_MASTER,
        body=body,
        sent_at=_now(),
        sender_display_name="__GM__",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{session_id}/encounter",
    response_model=EncounterLive,
    status_code=status.HTTP_201_CREATED,
)
async def create_encounter(
    session_id: int,
    body: EncounterCreateRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EncounterLive:
    session = await _load_session(session_id, db)
    _assert_participant(session, user_id)
    _assert_gm(session, user_id)
    _assert_session_active(session)
    if await _load_open_encounter(session_id, db) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An encounter is already open in this session",
        )
    enc = Encounter(
        session_id=session_id, mode=body.mode, status="setup",
        round=1, created_at=_now(),
    )
    db.add(enc)
    await db.flush()
    await _add_missing_pc_combatants(session, enc, db)
    _touch(session)
    await db.flush()
    await db.refresh(enc, attribute_names=["combatants"])
    return build_encounter_block(enc, viewer_is_gm=True)


@router.post(
    "/{session_id}/encounter/combatants",
    response_model=EncounterLive,
    status_code=status.HTTP_201_CREATED,
)
async def add_combatants(
    session_id: int,
    body: CombatantAddRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EncounterLive:
    session = await _load_session(session_id, db)
    _assert_participant(session, user_id)
    _assert_gm(session, user_id)
    _assert_session_active(session)
    enc = await _require_open_encounter(session_id, db)
    if enc.mode == "light" and (body.max_hp is not None or body.ac is not None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="HP/AC fields are not allowed in light mode",
        )
    rows = _ordered(enc.combatants)
    next_order = (rows[-1].sort_order + 10) if rows else 10
    for i in range(body.count):
        name = body.name if body.count == 1 else f"{body.name} {i + 1}"
        db.add(Combatant(
            encounter_id=enc.id,
            kind="monster",
            name=name,
            initiative_mod=body.initiative_mod,
            max_hp=body.max_hp,
            current_hp=body.max_hp,
            ac=body.ac,
            # Rinforzi a combattimento avviato: in coda all'ordine corrente.
            sort_order=(next_order + i * 10) if enc.status == "active" else None,
            created_at=_now(),
        ))
    _touch(session)
    await db.flush()
    await db.refresh(enc, attribute_names=["combatants"])
    return build_encounter_block(enc, viewer_is_gm=True)


@router.post(
    "/{session_id}/encounter/combatants/{combatant_id}/initiative",
    response_model=EncounterLive,
)
async def roll_initiative(
    session_id: int,
    combatant_id: int,
    body: InitiativeRollRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EncounterLive:
    session = await _load_session(session_id, db)
    _assert_participant(session, user_id)
    _assert_session_active(session)
    enc = await _require_open_encounter(session_id, db)
    comb = next((c for c in enc.combatants if c.id == combatant_id), None)
    if comb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Combatant not found")
    is_gm = user_id == session.gm_user_id
    if not is_gm and comb.owner_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not your combatant",
        )
    if comb.initiative is not None:
        # Anche per il GM: la correzione passa dal PATCH.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Initiative already rolled",
        )
    die = body.die if body.die is not None else random.randint(1, 20)
    comb.initiative_die = die
    comb.initiative = die + comb.initiative_mod
    _touch(session)
    await db.flush()
    return build_encounter_block(enc, viewer_is_gm=is_gm)


@router.post("/{session_id}/encounter/sync-pcs", response_model=EncounterLive)
async def sync_pcs(
    session_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EncounterLive:
    session = await _load_session(session_id, db)
    _assert_participant(session, user_id)
    _assert_gm(session, user_id)
    _assert_session_active(session)
    enc = await _require_open_encounter(session_id, db)
    # next_order calcolato PRIMA di aggiungere (enc.combatants non vede i nuovi)
    rows = _ordered(enc.combatants)
    next_order = (rows[-1].sort_order + 10) if rows else 10
    added = await _add_missing_pc_combatants(session, enc, db)
    if enc.status == "active":
        for j, comb in enumerate(added):
            comb.sort_order = next_order + j * 10
    _touch(session)
    await db.flush()
    await db.refresh(enc, attribute_names=["combatants"])
    return build_encounter_block(enc, viewer_is_gm=True)
