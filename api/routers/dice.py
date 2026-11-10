"""Dice roll endpoints."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from api.auth import get_current_user
from api.database import get_db
from api.services import telegram_notify
from api.routers._helpers import initiative_bonus
from api.services.d20 import d20_records, resolve_body, resolve_d20, spend_inspiration_reroll
from api.services.dice_stats import record_dice
from api.services.effects import apply_heal
from api.services.rules_options import (
    LAST_ROLL_FIELDS,
    merge_options,
    option_result,
    remember_roll,
    roll_option_dice,
    use_options,
)
from api.services.history import add_history
from core.db.models import Character
from core.rules.modifiers import modifiers_for
from api.schemas.common import (
    D20Dice, DiceResultEntry, DiceResultRequest, DiceRollResult, RollMode, RollOptionsBody, RollResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/characters", tags=["dice"])

_MAX_HISTORY = 50


async def _get_owned(char_id: int, user_id: int, session: AsyncSession) -> Character:
    result = await session.execute(
        select(Character).where(Character.id == char_id)
    )
    char = result.scalar_one_or_none()
    if char is None:
        raise HTTPException(status_code=404, detail="Character not found")
    if char.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your character")
    return char


_RANGES_PER_KIND = {
    "d4": (1, 4),
    "d6": (1, 6),
    "d8": (1, 8),
    "d10": (1, 10),
    "d12": (1, 12),
    "d20": (1, 20),
}


def _log_roll(session: AsyncSession, char: Character, notation: str, rolls: list[int], total: int, modifier: int,
              source: str, label: str | None, with_inspiration: bool = False) -> None:
    """Storico dei dadi e feed generale, così il tiro compare anche in /history."""
    history = list(char.rolls_history or [])
    history.append({
        "notation": notation,
        "rolls": rolls,
        "total": total,
        "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
        "source": source,
        "label": label,
    })
    char.rolls_history = history[-_MAX_HISTORY:]
    flag_modified(char, "rolls_history")

    if len(rolls) > 1:
        rolls_str = "+".join(str(r) for r in rolls)
        description = f"🎲 {notation}: [{rolls_str}] = {total}"
    else:
        description = f"🎲 {notation}: {total}"
    if label:
        description = f"{label}: {description}"
    if with_inspiration:
        description = f"Reroll ispirazione: {description}"
    add_history(session, char.id, "dice_roll", description,
                {"notation": notation, "rolls": rolls, "total": total, "modifier": modifier})


class InitiativeSubmission(RollOptionsBody):
    """Facce lette dai dadi 3D (senza, tira il server) ed etichetta tradotta per lo storico."""
    die: int | None = Field(default=None, ge=1, le=20)
    mode: RollMode = "normal"
    dice: D20Dice | None = None
    label: str | None = Field(default=None, max_length=120)


@router.post("/{char_id}/dice/initiative", response_model=RollResult)
async def roll_character_initiative(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    body: Annotated[InitiativeSubmission | None, Body()] = None,
) -> RollResult:
    """Iniziativa fuori da un incontro: stesso bonus della scheda, modo e note come gli altri tiri."""
    await _get_owned(char_id, user_id, session)
    char = (await session.execute(
        select(Character)
        .options(selectinload(Character.classes), selectinload(Character.items), selectinload(Character.ability_scores),
                 selectinload(Character.abilities), selectinload(Character.spell_slots))
        .where(Character.id == char_id)
        .execution_options(populate_existing=True)
    )).scalar_one()
    applied = modifiers_for(char, "initiative", ability="dexterity")
    opts = use_options(session, char, "initiative", body, ability="dexterity")
    merge_options(applied, opts)
    if opts.self_heal:  # Metabolismo Prodigioso: la cura passa dal percorso comune (massimo, tiri salvezza morte, storico)
        await apply_heal(session, char, opts.self_heal)
    bonus = await initiative_bonus(session, char) + opts.bonus
    outcome = resolve_body(body, applied)
    die = outcome.kept
    option_rolls, option_total = roll_option_dice(char, opts)
    total = die + bonus + option_total
    keep = {"advantage": "kh1", "disadvantage": "kl1"}.get(outcome.mode, "")
    record_dice(char, d20_records(outcome))
    _log_roll(session, char, f"{len(outcome.dice)}d20{keep}{bonus:+d}", outcome.dice, total, bonus, "init",
              body.label if body else None)
    await session.flush()
    result = RollResult(
        die=die, dice=outcome.dice, mode=outcome.mode, mode_applied=outcome.mode, notes=applied.notes,
        auto_fail=applied.auto_fail, bonus=bonus, total=total,
        is_critical=die == 20 and not applied.auto_fail, is_fumble=die == 1, description="initiative",
        option_result=option_result(opts, option_rolls, option_total),
    )
    remember_roll(char, "initiative", opts, result.model_dump(mode="json", include=LAST_ROLL_FIELDS), ability="dexterity")
    return result


@router.post("/{char_id}/dice/result", response_model=DiceRollResult)
async def post_dice_result(
    char_id: int,
    body: DiceResultRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> DiceRollResult:
    # validate ranges
    for entry in body.rolls:
        lo, hi = _RANGES_PER_KIND[entry.kind]
        if not (lo <= entry.value <= hi):
            raise HTTPException(
                status_code=400,
                detail=f"value {entry.value} out of range for {entry.kind} ({lo}..{hi})",
            )

    rolls = [e.value for e in body.rolls]
    total = body.total if body.total is not None else sum(rolls) + body.modifier
    # An inspiration reroll is a single d20: it falls through to the legacy path.
    if body.mode != "normal" and not body.with_inspiration:
        if any(e.kind != "d20" for e in body.rolls):
            raise HTTPException(status_code=422, detail="dice_count_mismatch")
        total = resolve_d20(body.mode, rolls, None).kept + body.modifier

    # notation: prefer client-supplied, else infer
    if body.notation:
        notation = body.notation
    else:
        from collections import Counter
        c = Counter(e.kind for e in body.rolls)
        notation = " + ".join(f"{n}{k}" if n > 1 else k for k, n in c.items())
        if body.modifier:
            notation += f"{'+' if body.modifier > 0 else ''}{body.modifier}"

    char = await _get_owned(char_id, user_id, session)

    if body.with_inspiration:
        spend_inspiration_reroll(char)

    record_dice(char, [(e.kind, e.value) for e in body.rolls])
    _log_roll(session, char, notation, rolls, total, body.modifier, body.source or "manual", body.label,
              body.with_inspiration)

    await session.flush()
    logger.info(
        "dice/result persisted: char=%s notation=%s total=%s history_len=%s",
        char_id, notation, total, len(char.rolls_history or []),
    )

    return DiceRollResult(notation=notation, rolls=rolls, total=total)


@router.get("/{char_id}/dice/history", response_model=list[DiceRollResult])
async def get_dice_history(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> list[DiceRollResult]:
    char = await _get_owned(char_id, user_id, session)
    history = list(char.rolls_history or [])
    return [
        DiceRollResult(
            notation=entry.get("notation", "?"),
            rolls=entry.get("rolls", []),
            total=entry.get("total", 0),
            timestamp=entry.get("timestamp"),
            source=entry.get("source"),
            label=entry.get("label"),
        )
        for entry in reversed(history)  # most recent first
    ]


class DicePostToChatRequest(BaseModel):
    notation: str
    rolls: list[int]
    total: int


@router.post("/{char_id}/dice/post-to-chat", status_code=200)
async def post_dice_to_chat(
    char_id: int,
    body: DicePostToChatRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> dict:
    """Send a dice roll result to the user's private Telegram chat.

    Replaces the ``Telegram.WebApp.sendData()`` mechanism, which only works
    when the Mini App is opened via a reply keyboard button (and therefore
    cannot authenticate). This endpoint is called from the Mini App when
    opened via the BotFather menu button (initData present → auth works).
    """
    await _get_owned(char_id, user_id, session)

    if not telegram_notify.bot_token_configured():
        raise HTTPException(status_code=503, detail="BOT_TOKEN not configured")

    rolls = body.rolls
    if len(rolls) > 1:
        rolls_str = " + ".join(str(r) for r in rolls)
        text = f"🎲 {body.notation}: {rolls_str} = *{body.total}*"
    else:
        text = f"🎲 {body.notation}: *{body.total}*"

    ok = await telegram_notify.send_telegram_message(
        user_id, text, parse_mode="Markdown")
    if not ok:
        raise HTTPException(status_code=502, detail="Failed to send Telegram message")

    return {"ok": True}


@router.delete("/{char_id}/dice/history", status_code=204)
async def clear_dice_history(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> None:
    char = await _get_owned(char_id, user_id, session)
    char.rolls_history = []


@router.get("/{char_id}/dice/stats")
async def get_dice_stats(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> dict:
    """Contatori cumulativi raw {kind: {faccia: conteggio}}; il FE deriva il resto."""
    char = await _get_owned(char_id, user_id, session)
    return {"stats": char.dice_stats or {}}


@router.delete("/{char_id}/dice/stats", status_code=204)
async def reset_dice_stats(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> None:
    char = await _get_owned(char_id, user_id, session)
    char.dice_stats = {}
    flag_modified(char, "dice_stats")
