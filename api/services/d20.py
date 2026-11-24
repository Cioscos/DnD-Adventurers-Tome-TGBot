"""Single source of truth for obtaining the kept d20 of any roll (normal/adv/dis)."""

from __future__ import annotations

import random
from dataclasses import dataclass

from fastapi import HTTPException

from api.schemas.common import RollMode
from core.rules.edition import character_edition
from core.rules.modifiers import Applied, final_mode


@dataclass
class D20Outcome:
    dice: list[int]
    kept: int
    mode: RollMode


def spend_inspiration_reroll(char) -> None:
    """Il rilancio è del 2024. Nel 2014 l'Ispirazione si spende prima del tiro, con l'opzione ``inspiration:advantage``."""
    if character_edition(char) == "2014":
        raise HTTPException(status_code=409, detail="inspiration_before_roll")
    if not char.heroic_inspiration:
        raise HTTPException(status_code=409, detail="Ispirazione non disponibile")
    spend_inspiration(char)


def spend_inspiration_attack(char, *, item_id: int | None = None, spell_id: int | None = None) -> None:
    """Rilancio di un attacco: 2024, si ritira il d20 dell'attacco appena tirato (stessa arma o stesso incantesimo; senza id, il colpo
    senz'armi). Senza quel tiro sarebbe un attacco gratuito. Nel 2014 il rilancio è rifiutato comunque."""
    last = (char.turn_state or {}).get("last_roll") or {}
    if character_edition(char) == "2024" and (
            last.get("roll") != "attack" or (last.get("item_id"), last.get("spell_id")) != (item_id, spell_id)
            or bool(last.get("unarmed")) != (item_id is None and spell_id is None)):  # nemmeno l'attacco di una bestia ha id
        raise HTTPException(status_code=409, detail={"code": "no_roll_to_reroll"})
    spend_inspiration_reroll(char)


def set_inspiration(char, value: bool) -> None:
    """Concede o toglie l'Ispirazione (giocatore o GM). 2024: riceverne una con una già in mano la rende «in più»."""
    settings = dict(char.settings or {})
    if value and char.heroic_inspiration and character_edition(char) == "2024":
        settings["inspiration_extra"] = True  # se ne ha una sola: questa è da cedere a chi ne è privo, o persa
    else:
        settings.pop("inspiration_extra", None)
    char.settings = settings
    char.heroic_inspiration = value


def spend_inspiration(char) -> None:
    """Spesa l'Ispirazione, cade anche quella «in più» da cedere: non ce n'è più nessuna."""
    char.heroic_inspiration = False
    if (char.settings or {}).get("inspiration_extra"):
        char.settings = {k: v for k, v in char.settings.items() if k != "inspiration_extra"}


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
    # Un dado in più si scarta: il client anima i d20 delle opzioni scelte, ma un automatismo può annullarli (avvelenato).
    elif mode != player_mode or (dice is not None and len(dice) > (1 if mode == "normal" else 2)):
        given = dice if dice is not None else [die] if die is not None else None
        if given is not None:
            need = 1 if mode == "normal" else 2
            dice = [*given[:need], *(random.randint(1, 20) for _ in range(need - len(given)))]
    outcome = resolve_d20(mode, dice, die)
    if applied.min_d20 is not None:
        outcome.kept = max(outcome.kept, applied.min_d20)
    return outcome


def resolve_body(body, applied: Applied | None = None) -> D20Outcome:
    """resolve_d20 from an optional request body; inspiration (2024 only) is a single-die reroll."""
    applied = applied or Applied()
    if body is None:
        return resolve_applied("normal", None, None, applied)
    if not getattr(body, "with_inspiration", False):
        return resolve_applied(body.mode, body.dice, body.die, applied)
    prev = applied.reroll_of or {}
    dice, mode = list(prev.get("dice") or []), prev.get("mode")
    if mode not in ("advantage", "disadvantage") or len(dice) != 2 or applied.replace_die is not None:
        return resolve_applied("normal", body.dice, body.die, applied, True)
    # 2024 pag. 12-13: con vantaggio o svantaggio il rilancio tocca un solo d20 e il modo resta. Si rilancia il più basso,
    # che in entrambi i modi è la scelta migliore per chi tira.
    dice[dice.index(min(dice))] = resolve_d20("normal", (body.dice or [])[:1] or None, body.die).kept
    outcome = resolve_d20(mode, dice, None)
    if applied.min_d20 is not None:
        outcome.kept = max(outcome.kept, applied.min_d20)
    return outcome


def d20_history_label(o: D20Outcome) -> str:
    if o.mode == "normal":
        return f"d20={o.kept}"
    word = "vantaggio" if o.mode == "advantage" else "svantaggio"
    return f"2d20 {word}: {o.dice[0]}, {o.dice[1]} → {o.kept}"


def d20_records(o: D20Outcome) -> list[tuple[str, int]]:
    return [("d20", d) for d in o.dice]
