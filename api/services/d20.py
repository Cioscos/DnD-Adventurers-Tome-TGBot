"""Single source of truth for obtaining the kept d20 of any roll (normal/adv/dis)."""

from __future__ import annotations

import random
from dataclasses import dataclass

from fastapi import HTTPException

from api.schemas.common import RollMode
from core.rules.modifiers import Applied, final_mode


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


def resolve_applied(
    player_mode: RollMode, dice: list[int] | None, die: int | None, applied: Applied, reroll: bool = False,
) -> D20Outcome:
    """Tiro con i modificatori automatici. Il client conosce solo il modo scelto dal giocatore: se quello
    finale chiede un altro numero di dadi si tengono i suoi e si tira il mancante (mai un 422)."""
    mode: RollMode = player_mode if reroll else final_mode(player_mode, applied)
    if applied.replace_die is not None:
        mode, dice = "normal", [applied.replace_die]
    elif mode != player_mode:
        given = dice if dice is not None else [die] if die is not None else None
        if given is not None:
            need = 1 if mode == "normal" else 2
            dice = [*given[:need], *(random.randint(1, 20) for _ in range(need - len(given)))]
    outcome = resolve_d20(mode, dice, die)
    if applied.min_d20 is not None:
        outcome.kept = max(outcome.kept, applied.min_d20)
    return outcome


def resolve_body(body, applied: Applied | None = None) -> D20Outcome:
    """resolve_d20 from an optional request body; inspiration is a single-die reroll."""
    applied = applied or Applied()
    if body is None:
        return resolve_applied("normal", None, None, applied)
    reroll = getattr(body, "with_inspiration", False)
    return resolve_applied("normal" if reroll else body.mode, body.dice, body.die, applied, reroll)


def d20_history_label(o: D20Outcome) -> str:
    if o.mode == "normal":
        return f"d20={o.kept}"
    word = "vantaggio" if o.mode == "advantage" else "svantaggio"
    return f"2d20 {word}: {o.dice[0]}, {o.dice[1]} → {o.kept}"


def d20_records(o: D20Outcome) -> list[tuple[str, int]]:
    return [("d20", d) for d in o.dice]
