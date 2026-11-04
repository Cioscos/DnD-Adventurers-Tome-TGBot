"""Conferma al tiro lato API: contesto, errore HTTP, dadi e risposta. La logica sta in ``core.rules.roll_options``."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import HTTPException, status

from api.schemas.common import OptionResult
from api.schemas.rules import RollOptionCost, RollOptionRead, RollOptionSlot
from api.services.dice_stats import record_dice
from api.services.rules_turn import get_turn
from core.rules.edition import character_edition
from core.rules.modifiers import Applied
from core.rules.roll_options import (
    AppliedOptions,
    OptionUnavailable,
    RollOption,
    apply_options,
    roll_extra,
    roll_options_for,
    slot_choices,
)
from core.rules.types import RuleContext


def roll_context(char: Any, roll: str, **kw: Any) -> RuleContext:
    turn = char.turn_state or {}
    confirmed = tuple((turn.get("pending_attack") or {}).get("options", [])) if roll == "attack" else ()
    return RuleContext(char=char, edition=character_edition(char), roll=roll, turn=turn, confirmed=confirmed, **kw)


def use_options(session: Any, char: Any, roll: str, body: Any, phase: str = "before", **kw: Any) -> AppliedOptions:
    """Le opzioni della richiesta, pagate. 409 ``option_unavailable`` se il server non le riconosce.

    Il rilancio con ispirazione è lo stesso tiro: ritrova ciò che era stato confermato, senza pagarlo di nuovo."""
    if getattr(body, "with_inspiration", False):
        stored = get_turn(char).get("last_options") or {}
        return AppliedOptions(**stored["applied"]) if stored.get("roll") == roll else AppliedOptions()
    keys = getattr(body, "options", None) or []
    try:
        opts = apply_options(session, roll_context(char, roll, **kw), keys,
                             getattr(body, "option_inputs", None), phase)
    except OptionUnavailable as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "option_unavailable", "key": exc.key}) from exc
    if phase == "before" and (keys or (char.turn_state or {}).get("last_options")):
        turn = get_turn(char)
        turn.pop("last_options", None)
        if keys:
            # il modo non torna: l'ispirazione ritira un solo dado
            turn["last_options"] = {"roll": roll, "applied": {**asdict(opts), "modes": [], "spent": []}}
        char.turn_state = turn
    return opts


def merge_options(applied: Applied, opts: AppliedOptions) -> None:
    """Il modo confermato passa dalle stesse regole di quelli automatici (i due opposti si annullano)."""
    applied.advantage = applied.advantage or opts.mode in ("advantage", "normal")
    applied.disadvantage = applied.disadvantage or opts.mode in ("disadvantage", "normal")
    applied.auto_fail = applied.auto_fail or opts.auto_fail
    applied.notes += [n for n in opts.notes if n not in applied.notes]


def roll_option_dice(char: Any, opts: AppliedOptions, critical: bool = False) -> tuple[list[int], int]:
    """Tira i dadi delle opzioni e li registra nelle statistiche: (valori, totale con il fisso dell'espressione)."""
    rolled, flat = roll_extra(opts.extra_dice, critical)
    fixed, fixed_flat = roll_extra(opts.fixed_dice)
    rolled += fixed
    opts.separate_rolls, opts.separate_total = [], 0
    for expr, doubles in opts.separate_dice:
        apart, apart_flat = roll_extra([expr], critical and doubles)
        record_dice(char, apart)
        opts.separate_rolls += [v for _, v in apart]
        opts.separate_total += sum(v for _, v in apart) + apart_flat
    record_dice(char, rolled)
    values = [v for _, v in rolled]
    return values, sum(values) + flat + fixed_flat


def option_result(opts: AppliedOptions, rolls: list[int], total: int, previous: OptionResult | None = None,
                  **extra: Any) -> OptionResult | None:
    """Il blocco della risposta (``None`` senza opzioni); ``previous``: opzioni già confermate per lo stesso attacco."""
    if not opts.keys:
        return previous
    before = previous or OptionResult()
    return OptionResult(
        keys=[*before.keys, *opts.keys], extra_rolls=[*before.extra_rolls, *rolls],
        extra_total=before.extra_total + total, bonus=before.bonus + opts.bonus,
        separate_rolls=[*before.separate_rolls, *opts.separate_rolls],
        separate_total=before.separate_total + opts.separate_total,
        multiplier=before.multiplier * opts.multiplier, spent=[*before.spent, *opts.spent], **extra,
    )


def option_read(option: RollOption, lang: str) -> RollOptionRead:
    spec, ctx = option.spec, option.ctx
    slots = []
    if spec.requires_input == "slot":
        minimum = (spec.cost.spell_slot_min if spec.cost else None) or 0
        slots = [RollOptionSlot(level=level, available=free,
                                dice=spec.extra_dice(ctx, {"slot_level": level}) if spec.extra_dice else None)
                 for level, free in slot_choices(ctx.char, minimum).items()]
    fixed = spec.requires_input is None
    return RollOptionRead(
        key=spec.key, phase=spec.phase, label=spec.label.get(lang) or spec.label["it"], source=option.source,
        dice=spec.extra_dice(ctx, {}) if fixed and spec.extra_dice else None,
        bonus=spec.bonus(ctx, {}) if fixed and spec.bonus else None,
        mode=spec.mode, multiplier=spec.multiplier, once_per_turn=spec.once_per_turn, slot=spec.slot,
        needs=None if spec.needs in ctx.confirmed else spec.needs, group=spec.group, dice_cost=spec.dice_cost,
        requires_input=spec.requires_input, input_options=slots, auto_fail=spec.auto_fail,
        cost=RollOptionCost(feature_key=spec.cost.feature_key, amount=spec.cost.amount,
                            spell_slot_min=spec.cost.spell_slot_min) if spec.cost else None,
    )


def list_options(char: Any, roll: str, lang: str, **kw: Any) -> list[RollOptionRead]:
    return [option_read(o, lang) for o in roll_options_for(roll_context(char, roll, **kw))]
