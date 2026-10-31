"""Single source of truth for obtaining the kept d20 of any roll (normal/adv/dis)."""

from __future__ import annotations

import random
from dataclasses import dataclass

from fastapi import HTTPException

from api.schemas.common import RollMode


@dataclass
class D20Outcome:
    dice: list[int]
    kept: int
    mode: RollMode


def resolve_d20(mode: RollMode, dice: list[int] | None, die: int | None) -> D20Outcome:
    """Legacy ``die`` means ``dice=[die]``; missing values are rolled server-side."""
    need = 1 if mode == "normal" else 2
    if dice is None and die is not None:
        dice = [die]
    if dice is None:
        dice = [random.randint(1, 20) for _ in range(need)]
    if len(dice) != need:
        raise HTTPException(status_code=422, detail="dice_count_mismatch")
    kept = {"normal": dice[0], "advantage": max(dice), "disadvantage": min(dice)}[mode]
    return D20Outcome(dice=list(dice), kept=kept, mode=mode)


def resolve_body(body) -> D20Outcome:
    """resolve_d20 from an optional request body; inspiration is a single-die reroll."""
    if body is None:
        return resolve_d20("normal", None, None)
    mode = "normal" if getattr(body, "with_inspiration", False) else body.mode
    return resolve_d20(mode, body.dice, body.die)


def d20_history_label(o: D20Outcome) -> str:
    if o.mode == "normal":
        return f"d20={o.kept}"
    word = "vantaggio" if o.mode == "advantage" else "svantaggio"
    return f"2d20 {word}: {o.dice[0]}, {o.dice[1]} → {o.kept}"


def d20_records(o: D20Outcome) -> list[tuple[str, int]]:
    return [("d20", d) for d in o.dice]
