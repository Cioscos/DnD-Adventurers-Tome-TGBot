"""Stati attivi dei privilegi (``Character.active_states``) e uso reale dei privilegi."""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.rules_turn import grant_action, set_damaged, spend
from core.rules.catalog import active_features
from core.rules.edition import character_edition
from core.rules.roll_options import keep_target_effect
from core.rules.types import RuleContext, StateSpec

_DICE = re.compile(r"^(\d+)d(\d+)$")


def _err(code: int, name: str) -> HTTPException:
    return HTTPException(code, detail={"code": name})


def get_states(char) -> list[dict]:
    return list(char.active_states or [])


def end_states(char, *reasons: str) -> list[str]:
    """Chiude gli stati che finiscono per uno dei ``reasons``. Restituisce le chiavi chiuse."""
    states = get_states(char)
    kept = [s for s in states if not set(s["ends_on"]) & set(reasons)]
    if len(kept) != len(states):
        char.active_states = kept  # nuova lista: SQLAlchemy non vede le mutazioni in place
    return [s["key"] for s in states if s not in kept]


def tick_states(char) -> list[str]:
    """Un round: scala ``rounds_left``; gli stati a 0 finiscono. Restituisce le chiavi scadute."""
    states, expired = [], []
    for s in get_states(char):
        if s["rounds_left"] is None:
            states.append(s)
        elif s["rounds_left"] > 1:
            states.append({**s, "rounds_left": s["rounds_left"] - 1})
        else:
            expired.append(s["key"])
    if any(s["rounds_left"] is not None for s in get_states(char)):
        char.active_states = states
    return expired


def on_damage(char, applied: int) -> None:
    """Unico punto per il danno ai PF (`update_hp`, homebrew): segna il danno e chiude gli stati a 0 PF."""
    if applied > 0:
        set_damaged(char)
    if char.current_hit_points == 0:
        end_states(char, "unconscious", "incapacitated")


_INCAPACITATING = {"incapacitated", "paralyzed", "stunned", "petrified"}


def on_conditions(char, changes: dict) -> None:
    """Unico punto per le condizioni impostate (`apply_conditions`): chiude gli stati che non reggono."""
    on = {c for c, v in changes.items() if v}
    if "unconscious" in on:
        end_states(char, "unconscious", "incapacitated")
    elif on & _INCAPACITATING:
        end_states(char, "incapacitated")


def extend_state(char, key: str, rounds: int) -> None:
    """Riporta `rounds_left` a `rounds` senza spendere usi (prolungamento a fine turno, Ira 2024)."""
    states = get_states(char)
    if all(s["key"] != key for s in states):
        raise _err(status.HTTP_404_NOT_FOUND, "state_not_found")
    char.active_states = [{**s, "rounds_left": rounds} if s["key"] == key else s for s in states]


def remove_state(char, key: str) -> None:
    states = get_states(char)
    if all(s["key"] != key for s in states):
        raise _err(status.HTTP_404_NOT_FOUND, "state_not_found")
    char.active_states = [s for s in states if s["key"] != key]


def start_state(char, spec: StateSpec, feature_key: str) -> dict:
    """Avvia lo stato; se la chiave è già attiva lo rinnova."""
    state = {"key": spec.key, "feature_key": feature_key, "rounds_left": spec.rounds,
             "ends_on": list(spec.ends_on), "data": dict(spec.data)}
    char.active_states = [*(s for s in get_states(char) if s["key"] != spec.key), state]
    return state


@dataclass
class UseResult:
    rolls: list[int] = field(default_factory=list)
    healed: int = 0
    state: dict | None = None
    notes: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)  # chiavi per ``POST /target-effects``


async def use_feature(session: AsyncSession, char, feature_key: str, amount: int = 1,
                      params: dict | None = None) -> UseResult:
    """Usa un privilegio a catalogo con ``on_use``: spende gli usi della sua riga ``Ability``,
    lo slot di turno e applica cura, stato e azione extra. Tutti i controlli prima di ogni modifica."""
    found = next(((s, r) for s, r in active_features(char) if s.key == feature_key and s.on_use), None)
    if found is None:
        raise _err(status.HTTP_404_NOT_FOUND, "feature_not_usable")
    spec, row = found
    on_use = spec.on_use
    ability = next((a for a in char.abilities if a.feature_key == feature_key and a.source_class_id == row.id), None)
    cost = on_use.cost * amount
    if spec.uses is not None:
        # senza riga o con usi a None il contatore è illimitato solo se la formula lo dichiara (max_uses None)
        if ability is None or (ability.max_uses is not None and (ability.uses or 0) < cost):
            raise _err(status.HTTP_409_CONFLICT, "no_uses")
    if on_use.slot:
        spend(char, on_use.slot)  # 409 turn_slot_used prima di toccare gli usi
    if ability is not None and ability.max_uses is not None and ability.uses is not None:
        ability.uses -= cost

    result = UseResult()
    if on_use.rolls:
        m = _DICE.match(on_use.rolls)
        result.rolls = [random.randint(1, int(m[2])) for _ in range(int(m[1]))]
    if on_use.heal:
        from api.services.effects import apply_heal  # import locale: effects richiama on_conditions
        ctx = RuleContext(char=char, edition=character_edition(char), class_row=row, class_level=row.level)
        amount_hp = max(0, on_use.heal(ctx, sum(result.rolls)))
        result.healed = (await apply_heal(session, char, amount_hp))["healed"]
    if on_use.state:
        result.state = start_state(char, on_use.state, feature_key)
    if on_use.grants_action:
        grant_action(char)
    if on_use.target_effect:
        ctx = RuleContext(char=char, edition=character_edition(char), class_row=row, class_level=row.level)
        keep_target_effect(char, feature_key, on_use.target_effect(ctx, params or {}))
        result.targets.append(feature_key)
    return result
