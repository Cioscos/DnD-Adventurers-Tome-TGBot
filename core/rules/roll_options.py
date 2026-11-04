"""Conferma al tiro: quali opzioni offrire per un tiro e cosa comportano. Il giudizio è del giocatore, il calcolo qui."""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

from core.db.models import CharacterHistory
from core.rules.catalog import active_features
from core.rules.types import TURN_FLAGS, RollOptionSpec, RuleContext

_DICE = re.compile(r"^(\d+)d(\d+)([+-]\d+)?$")


def _on(condition: str):
    return lambda ctx: bool((ctx.char.conditions or {}).get(condition))


# Condizioni i cui effetti dipendono da ciò che l'app non vede (R25, R25 bis).
_CONDITION_OPTIONS = (
    RollOptionSpec(
        key="condition:frightened", phase="before", rolls=("attack", "skill", "initiative"), mode="disadvantage",
        label={"it": "Spaventato: vedi la fonte della paura?", "en": "Frightened: can you see the source of your fear?"},
        available=_on("frightened"),
    ),
    RollOptionSpec(
        key="condition:grappled", phase="before", rolls=("attack",), mode="disadvantage",
        label={"it": "Afferrato: il bersaglio non è chi ti afferra?", "en": "Grappled: is the target someone other than your grappler?"},
        available=lambda ctx: ctx.edition == "2024" and _on("grappled")(ctx),
    ),
    RollOptionSpec(
        key="condition:blinded", phase="before", rolls=("skill",), auto_fail=True,
        label={"it": "Accecato: la prova richiede la vista?", "en": "Blinded: does this check require sight?"},
        available=_on("blinded"),
    ),
    RollOptionSpec(
        key="condition:deafened", phase="before", rolls=("skill",), auto_fail=True,
        label={"it": "Assordato: la prova richiede l'udito?", "en": "Deafened: does this check require hearing?"},
        available=_on("deafened"),
    ),
)


class OptionUnavailable(Exception):
    """Opzione non applicabile adesso: già usata, senza risorse, di un'altra fase o inesistente."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


@dataclass(frozen=True)
class RollOption:
    spec: RollOptionSpec
    ctx: RuleContext  # con la classe che possiede il privilegio
    source: str  # nota del tiro: `condition:<slug>` o `feature:<chiave>`


@dataclass
class AppliedOptions:
    keys: list[str] = field(default_factory=list)
    extra_dice: list[str] = field(default_factory=list)
    bonus: int = 0
    modes: list[str] = field(default_factory=list)
    multiplier: float = 1
    spent: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    auto_fail: bool = False
    force_crit: bool = False

    @property
    def mode(self) -> str | None:
        """Modo confermato; i due opposti si annullano in ``normal``."""
        if not self.modes:
            return None
        return self.modes[0] if len(set(self.modes)) == 1 else "normal"


def _turn(char: Any) -> dict:
    return dict(char.turn_state or {})


def slot_choices(char: Any, minimum: int) -> dict[int, int]:
    """Livello -> slot liberi (patto compreso) da ``minimum`` in su."""
    out: dict[int, int] = {}
    for slot in char.spell_slots:
        if slot.level >= minimum and slot.available > 0:
            out[slot.level] = out.get(slot.level, 0) + slot.available
    return dict(sorted(out.items()))


def _ability_row(char: Any, feature_key: str, amount: int) -> Any:
    """La riga con usi sufficienti; senza massimo il contatore è illimitato (come ``use_feature``)."""
    return next((a for a in char.abilities if a.feature_key == feature_key
                 and (a.max_uses is None or (a.uses or 0) >= amount)), None)


def _slot_free(char: Any, slot: str) -> bool:
    turn = _turn(char)
    return not turn.get(TURN_FLAGS[slot]) or (slot == "action" and turn.get("extra_actions", 0) > 0)


def _affordable(char: Any, spec: RollOptionSpec) -> bool:
    if spec.once_per_turn and spec.key in _turn(char).get("once_per_turn", []):
        return False
    if spec.slot and not _slot_free(char, spec.slot):
        return False
    cost = spec.cost
    if cost and cost.feature_key and _ability_row(char, cost.feature_key, cost.amount) is None:
        return False
    return not (cost and cost.spell_slot_min is not None and not slot_choices(char, cost.spell_slot_min))


def roll_options_for(ctx: RuleContext) -> list[RollOption]:
    """Opzioni da offrire per ``ctx.roll``: disponibili e ancora pagabili. Una chiave di due classi vale una volta."""
    found: dict[str, RollOption] = {s.key: RollOption(s, ctx, s.key) for s in _CONDITION_OPTIONS}
    for spec, row in active_features(ctx.char):
        feature_ctx = replace(ctx, class_row=row, class_level=row.level)
        for option in spec.roll_options:
            found.setdefault(option.key, RollOption(option, feature_ctx, f"feature:{spec.key}"))
    return [o for o in found.values()
            if ctx.roll in o.spec.rolls and o.spec.available(o.ctx) and _affordable(ctx.char, o.spec)]


def _slot_level(char: Any, spec: RollOptionSpec, inputs: dict) -> int:
    level = inputs.get("slot_level")
    if type(level) is not int or level not in slot_choices(char, (spec.cost.spell_slot_min if spec.cost else None) or 0):
        raise OptionUnavailable(spec.key)
    return level


def _spend(session: Any, char: Any, spec: RollOptionSpec, inputs: dict) -> list[str]:
    """Paga l'opzione. Ricontrolla ogni risorsa: due opzioni possono contendersi l'ultima."""
    if not _affordable(char, spec):
        raise OptionUnavailable(spec.key)
    spent: list[str] = []
    turn = _turn(char)
    if spec.once_per_turn:
        turn["once_per_turn"] = [*turn.get("once_per_turn", []), spec.key]
    if spec.slot:
        flag = TURN_FLAGS[spec.slot]
        if turn.get(flag):  # solo l'azione arriva qui già usata: consuma l'azione extra
            turn["extra_actions"] -= 1
        turn[flag] = True
        spent.append(f"turn:{spec.slot}")
    char.turn_state = turn  # nuovo dict: SQLAlchemy non vede le mutazioni in place
    cost = spec.cost
    if cost and cost.feature_key:
        row = _ability_row(char, cost.feature_key, cost.amount)
        if row.max_uses is not None:
            row.uses = (row.uses or 0) - cost.amount
        spent.append(f"feature:{cost.feature_key}:{cost.amount}")
    if spec.requires_input == "slot":
        level = _slot_level(char, spec, inputs)
        next(s for s in char.spell_slots if s.level == level and s.available > 0).use_slot()
        spent.append(f"slot:{level}")
    if spent:
        session.add(CharacterHistory(
            character_id=char.id, timestamp=datetime.utcnow().isoformat(timespec="seconds"),
            event_type="roll_option", description=f"{spec.label['it']} ({', '.join(spent)})",
        ))
    return spent


def apply_options(session: Any, ctx: RuleContext, keys: list[str], inputs: dict | None = None,
                  phase: str = "before") -> AppliedOptions:
    """Riconvalida e paga le opzioni scelte. ``OptionUnavailable`` lascia pagamenti a metà: il chiamante annulla."""
    inputs = inputs or {}
    keys = list(dict.fromkeys(keys))
    usable = {o.spec.key: o for o in roll_options_for(ctx) if o.spec.phase == phase}
    out = AppliedOptions()
    for key in keys:
        option = usable.get(key)
        if option is None or (option.spec.needs and option.spec.needs not in keys):
            raise OptionUnavailable(key)
        spec, given = option.spec, inputs.get(key) or {}
        if spec.requires_input == "slot":
            _slot_level(ctx.char, spec, given)  # i dadi dipendono dallo slot: va controllato prima di calcolarli
        out.spent += _spend(session, ctx.char, spec, given)
        out.keys.append(key)
        if spec.extra_dice:
            out.extra_dice.append(spec.extra_dice(option.ctx, given))
        if spec.bonus:
            out.bonus += spec.bonus(option.ctx, given)
        if spec.mode:
            out.modes.append(spec.mode)
        if spec.multiplier is not None:
            out.multiplier *= spec.multiplier
        out.auto_fail = out.auto_fail or spec.auto_fail
        out.force_crit = out.force_crit or spec.force_crit
        if option.source not in out.notes:
            out.notes.append(option.source)
    return out


def roll_extra(dice: list[str], critical: bool = False) -> tuple[list[tuple[str, int]], int]:
    """Tira ``["2d6+3", ...]``: restituisce (tipo di dado, valore) e il bonus fisso. Il critico raddoppia i soli dadi."""
    rolled: list[tuple[str, int]] = []
    flat = 0
    for expr in dice:
        match = _DICE.match(expr)
        if match is None:
            raise ValueError(f"dadi non validi: {expr}")
        count, sides = int(match[1]) * (2 if critical else 1), int(match[2])
        rolled += [(f"d{sides}", random.randint(1, sides)) for _ in range(count)]
        flat += int(match[3] or 0)
    return rolled, flat


def scale_damage(value: int, multiplier: float) -> int:
    """Moltiplicatore sul danno, per difetto."""
    return int(value * multiplier)
