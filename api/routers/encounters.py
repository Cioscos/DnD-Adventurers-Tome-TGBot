"""Combat tracker endpoints (encounters inside game sessions).

The GM opens an encounter (light = initiative/turns only, full = monsters
with HP/AC too), players roll their own initiative, the GM drives turns.
Spec: docs/superpowers/specs/2026-06-09-combat-tracker-design.md
"""

from __future__ import annotations

import logging
import random
from typing import Annotated, Optional

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
from api.services import telegram_notify
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


def _advance_turn(
    enc: Encounter, combatants: list[Combatant], *, backward: bool = False
) -> Optional[Combatant]:
    """Move the turn pointer skipping dead combatants.

    Forward wrap increments the round; backward wrap decrements it, but at
    round 1 the move is a no-op (returns None, pointer untouched).
    """
    rows = _ordered(combatants)
    if not rows or all(c.is_dead for c in rows):
        return None
    try:
        idx = next(i for i, c in enumerate(rows) if c.id == enc.active_combatant_id)
    except StopIteration:
        idx = 0 if backward else -1
    n = len(rows)
    for step in range(1, n + 1):
        pos = idx - step if backward else idx + step
        cand = rows[pos % n]
        if cand.is_dead:
            continue
        if backward and pos < 0:
            if enc.round <= 1:
                return None
            enc.round -= 1
        elif not backward and pos >= n:
            enc.round += 1
        enc.active_combatant_id = cand.id
        return cand
    return None


def _system_feed_message(session: GameSession, body: str) -> SessionMessage:
    return SessionMessage(
        session_id=session.id,
        user_id=session.gm_user_id,
        role=SessionRole.GAME_MASTER,
        body=body,
        sent_at=_now(),
        sender_display_name="__GM__",
    )


async def _notify_turn(enc: Encounter, combatant: Combatant) -> None:
    """Fire-and-forget 'your turn' ping to the PC owner's private chat."""
    if combatant.kind != "pc" or not combatant.owner_user_id:
        return
    await telegram_notify.send_telegram_message(
        combatant.owner_user_id,
        f"⚔️ Tocca a te! Round {enc.round} — {combatant.name}",
        button=("Apri la sessione",
                telegram_notify.miniapp_url(f"/session/{enc.session_id}")),
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


@router.post("/{session_id}/encounter/start", response_model=EncounterLive)
async def start_encounter(
    session_id: int,
    body: EncounterStartRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EncounterLive:
    session = await _load_session(session_id, db)
    _assert_participant(session, user_id)
    _assert_gm(session, user_id)
    _assert_session_active(session)
    enc = await _require_open_encounter(session_id, db)
    if enc.status != "setup":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Encounter already started")
    if not enc.combatants:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No combatants")
    missing = [c for c in enc.combatants if c.initiative is None]
    if missing and not body.auto_roll_missing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "missing_initiative", "names": [c.name for c in missing]},
        )
    for c in missing:
        c.initiative_die = random.randint(1, 20)
        c.initiative = c.initiative_die + c.initiative_mod
    ordered = sorted(
        enc.combatants, key=lambda c: (-(c.initiative or 0), -c.initiative_mod, c.id),
    )
    for i, c in enumerate(ordered):
        c.sort_order = (i + 1) * 10
    enc.status = "active"
    enc.round = 1
    enc.started_at = _now()
    first = next((c for c in ordered if not c.is_dead), None)
    enc.active_combatant_id = first.id if first else None
    db.add(_system_feed_message(session, "⚔️ Combattimento iniziato"))
    _touch(session)
    await db.flush()
    if first is not None:
        await _notify_turn(enc, first)
    return build_encounter_block(enc, viewer_is_gm=True)


async def _turn_endpoint(
    session_id: int, user_id: int, db: AsyncSession, *, backward: bool
) -> EncounterLive:
    session = await _load_session(session_id, db)
    _assert_participant(session, user_id)
    _assert_gm(session, user_id)
    _assert_session_active(session)
    enc = await _require_open_encounter(session_id, db)
    if enc.status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Encounter not active")
    moved = _advance_turn(enc, list(enc.combatants), backward=backward)
    _touch(session)
    await db.flush()
    if moved is not None:
        await _notify_turn(enc, moved)
    return build_encounter_block(enc, viewer_is_gm=True)


@router.post("/{session_id}/encounter/next-turn", response_model=EncounterLive)
async def next_turn(
    session_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EncounterLive:
    return await _turn_endpoint(session_id, user_id, db, backward=False)


@router.post("/{session_id}/encounter/prev-turn", response_model=EncounterLive)
async def prev_turn(
    session_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EncounterLive:
    return await _turn_endpoint(session_id, user_id, db, backward=True)


@router.patch(
    "/{session_id}/encounter/combatants/{combatant_id}",
    response_model=EncounterLive,
)
async def patch_combatant(
    session_id: int,
    combatant_id: int,
    body: CombatantPatchRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EncounterLive:
    session = await _load_session(session_id, db)
    _assert_participant(session, user_id)
    _assert_gm(session, user_id)
    _assert_session_active(session)
    enc = await _require_open_encounter(session_id, db)
    comb = next((c for c in enc.combatants if c.id == combatant_id), None)
    if comb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Combatant not found")

    touches_hp = (
        body.current_hp is not None or body.max_hp is not None or body.ac is not None
    )
    if touches_hp and (enc.mode == "light" or comb.kind == "pc"):
        # HP/CA dei mostri esistono solo in full; quelli dei PG vivono sulla scheda.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="HP/AC fields not allowed here",
        )

    if body.name is not None:
        comb.name = body.name
    if body.initiative_mod is not None:
        comb.initiative_mod = body.initiative_mod
    if body.initiative is not None:
        comb.initiative = body.initiative
        comb.initiative_die = None       # valore manuale: nessuna faccia da mostrare
    if body.ac is not None:
        comb.ac = body.ac
    if body.max_hp is not None:
        comb.max_hp = body.max_hp
        if comb.current_hp is None or comb.current_hp > body.max_hp:
            comb.current_hp = body.max_hp
    if body.current_hp is not None:
        cap = comb.max_hp if comb.max_hp is not None else body.current_hp
        comb.current_hp = max(0, min(body.current_hp, cap))
        if comb.current_hp == 0 and comb.kind == "monster":
            comb.is_dead = True
    conditions_changed = False
    if body.conditions is not None:
        conditions_changed = (comb.conditions or {}) != body.conditions
        comb.conditions = body.conditions
    if body.is_dead is not None:        # override esplicito del GM, vince sull'auto
        comb.is_dead = body.is_dead

    _touch(session)
    await db.flush()

    # Notifica best-effort al proprietario del PG (categoria gm_events)
    if (
        conditions_changed
        and comb.kind == "pc"
        and comb.owner_user_id
        and comb.owner_user_id != user_id
    ):
        rec_char = (
            await db.get(Character, comb.character_id)
            if comb.character_id is not None else None
        )
        if telegram_notify.notifications_enabled(rec_char, "gm_events"):
            active = ", ".join(sorted(
                k for k, v in (comb.conditions or {}).items() if v))
            text = (
                f"🌀 Il GM ha aggiornato le condizioni di {comb.name}: {active}"
                if active
                else f"🌀 Il GM ha rimosso le condizioni di {comb.name}"
            )
            await telegram_notify.send_telegram_message(
                comb.owner_user_id, text,
                button=("Apri la sessione",
                        telegram_notify.miniapp_url(f"/session/{session_id}")),
            )

    return build_encounter_block(enc, viewer_is_gm=True)


def _move_pointer_off(enc: Encounter, combatants: list[Combatant], removed_id: int) -> None:
    """Point `active_combatant_id` at the next alive combatant, skipping the
    one being removed. No round change. None if nobody else is alive."""
    rows = _ordered(combatants)
    idx = next((i for i, c in enumerate(rows) if c.id == removed_id), 0)
    n = len(rows)
    for step in range(1, n + 1):
        cand = rows[(idx + step) % n]
        if cand.id == removed_id or cand.is_dead:
            continue
        enc.active_combatant_id = cand.id
        return
    enc.active_combatant_id = None


@router.delete(
    "/{session_id}/encounter/combatants/{combatant_id}",
    response_model=EncounterLive,
)
async def delete_combatant(
    session_id: int,
    combatant_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EncounterLive:
    session = await _load_session(session_id, db)
    _assert_participant(session, user_id)
    _assert_gm(session, user_id)
    _assert_session_active(session)
    enc = await _require_open_encounter(session_id, db)
    comb = next((c for c in enc.combatants if c.id == combatant_id), None)
    if comb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Combatant not found")
    if enc.active_combatant_id == comb.id:
        _move_pointer_off(enc, list(enc.combatants), comb.id)
    await db.delete(comb)
    _touch(session)
    await db.flush()
    await db.refresh(enc, attribute_names=["combatants"])
    return build_encounter_block(enc, viewer_is_gm=True)


@router.post("/{session_id}/encounter/reorder", response_model=EncounterLive)
async def reorder_combatants(
    session_id: int,
    body: ReorderRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EncounterLive:
    session = await _load_session(session_id, db)
    _assert_participant(session, user_id)
    _assert_gm(session, user_id)
    _assert_session_active(session)
    enc = await _require_open_encounter(session_id, db)
    if enc.status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Encounter not active")
    current_ids = sorted(c.id for c in enc.combatants)
    requested = body.combatant_ids
    if sorted(requested) != current_ids or len(requested) != len(set(requested)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="combatant_ids must match the encounter combatants exactly",
        )
    position = {cid: (i + 1) * 10 for i, cid in enumerate(requested)}
    for c in enc.combatants:
        c.sort_order = position[c.id]
    _touch(session)
    await db.flush()
    return build_encounter_block(enc, viewer_is_gm=True)


@router.post("/{session_id}/encounter/end", response_model=EncounterLive)
async def end_encounter(
    session_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EncounterLive:
    session = await _load_session(session_id, db)
    _assert_participant(session, user_id)
    _assert_gm(session, user_id)
    _assert_session_active(session)
    enc = await _require_open_encounter(session_id, db)
    enc.status = "ended"
    enc.ended_at = _now()
    db.add(_system_feed_message(session, "🕊️ Combattimento terminato"))
    _touch(session)
    await db.flush()
    return build_encounter_block(enc, viewer_is_gm=True)
