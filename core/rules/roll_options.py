"""Conferma al tiro: quali opzioni offrire per un tiro e cosa comportano. Il giudizio è del giocatore, il calcolo qui."""
from __future__ import annotations

import random
import re
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from typing import Any

from core.db.models import CharacterHistory
from core.rules.catalog import active_features
from core.rules.types import TURN_FLAGS, RollOptionSpec, RuleContext
from core.rules.weapons import has_property, small_race

_DICE = re.compile(r"^(\d+)d(\d+)([+-]\d+)?$")


def _on(condition: str):
    return lambda ctx: bool((ctx.char.conditions or {}).get(condition))


def _spend_inspiration(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    ctx.char.heroic_inspiration = False


# Regole generali, e condizioni i cui effetti dipendono da ciò che l'app non vede (R25, R25 bis).
_CONDITION_OPTIONS = (
    RollOptionSpec(
        key="inspiration:advantage", phase="before", rolls=("attack", "skill", "save", "initiative", "death_save"),
        mode="advantage", on_confirm=_spend_inspiration,
        label={"it": "Spendi l'Ispirazione: tiro con vantaggio", "en": "Spend Inspiration: roll with advantage"},
        available=lambda ctx: ctx.edition == "2014" and bool(ctx.char.heroic_inspiration),
    ),
    RollOptionSpec(
        key="weapon:heavy_small", phase="before", rolls=("attack",), mode="disadvantage",
        label={"it": "Arma pesante: sei una creatura Piccola?", "en": "Heavy weapon: are you a Small creature?"},
        available=lambda ctx: (ctx.edition == "2014" and ctx.item is not None and has_property(ctx.item, "heavy")
                               and small_race(ctx.char) is None),
    ),
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
    extra_dice: list[str] = field(default_factory=list)  # raddoppiano al critico
    fixed_dice: list[str] = field(default_factory=list)  # nel totale, senza raddoppio
    separate_dice: list[list] = field(default_factory=list)  # [espressione, raddoppia], fuori dal totale
    separate_rolls: list[int] = field(default_factory=list)
    separate_total: int = 0
    bonus: int = 0
    modes: list[str] = field(default_factory=list)
    multiplier: float = 1
    spent: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    auto_fail: bool = False
    force_crit: bool = False
    reroll: bool = False
    succeed: bool = False
    refundable: dict[str, list[str]] = field(default_factory=dict)  # chiave -> gettoni, per ``pay_if_success``
    replace_die: int | None = None
    miss_damage: int | None = None
    effects: list[dict[str, str]] = field(default_factory=list)  # {"it", "en"}: esiti da mostrare
    second_attack: bool = False
    targets: list[str] = field(default_factory=list)  # chiavi con un ``target_effect`` da applicare

    @property
    def mode(self) -> str | None:
        """Modo confermato; i due opposti si annullano in ``normal``."""
        if not self.modes:
            return None
        return self.modes[0] if len(set(self.modes)) == 1 else "normal"


def keep_target_effect(char: Any, key: str, effect: Any) -> None:
    """Tiene l'effetto deciso dal server fino a quando il giocatore sceglie il combattente (si consuma una volta)."""
    turn = _turn(char)
    turn["target_effects"] = {**turn.get("target_effects", {}), key: asdict(effect)}
    char.turn_state = turn


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


def _once_key(spec: RollOptionSpec) -> str:
    return spec.group or spec.key


def saved_dice(char: Any, key: str) -> list[int]:
    """Valori del d20 salvati per l'opzione ``key`` (Portento), ognuno usabile una volta."""
    return list(((char.settings or {}).get("saved_dice") or {}).get(key) or [])


def _store_saved_dice(char: Any, key: str, values: list[int]) -> None:
    settings = dict(char.settings or {})
    settings["saved_dice"] = {**(settings.get("saved_dice") or {}), key: values}
    char.settings = settings  # nuovo dict: SQLAlchemy non vede le mutazioni in place


def _affordable(char: Any, spec: RollOptionSpec) -> bool:
    if spec.replace_die and not saved_dice(char, spec.key):
        return False
    if spec.once_per_turn and _once_key(spec) in _turn(char).get("once_per_turn", []):
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


def _spend(session: Any, option: RollOption, inputs: dict) -> list[str]:
    """Paga l'opzione e ne applica l'effetto collaterale. Ricontrolla ogni risorsa: due opzioni possono contendersi
    l'ultima. I gettoni restituiti sono quelli che ``refund_spent`` sa rimborsare."""
    spec, char = option.spec, option.ctx.char
    if not _affordable(char, spec):
        raise OptionUnavailable(spec.key)
    spent: list[str] = []
    turn = _turn(char)
    if spec.once_per_turn:
        turn["once_per_turn"] = [*turn.get("once_per_turn", []), _once_key(spec)]
        spent.append(f"once:{_once_key(spec)}")
    if spec.slot:
        flag = TURN_FLAGS[spec.slot]
        if turn.get(flag):  # solo l'azione arriva qui già usata: consuma l'azione extra
            turn["extra_actions"] -= 1
            spent.append("turn:extra_action")
        else:
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
        slot = next(s for s in char.spell_slots if s.level == level and s.available > 0)
        slot.use_slot()
        spent.append(f"slot:{level}:pact" if slot.is_pact else f"slot:{level}")
    if spec.replace_die:
        values = saved_dice(char, spec.key)
        if inputs.get("die") not in values:
            raise OptionUnavailable(spec.key)
        values.remove(inputs["die"])
        _store_saved_dice(char, spec.key, values)
        spent.append(f"die:{spec.key}:{inputs['die']}")
    if spent:
        session.add(CharacterHistory(
            character_id=char.id, timestamp=datetime.utcnow().isoformat(timespec="seconds"),
            event_type="roll_option", description=f"{spec.label['it']} ({', '.join(spent)})",
        ))
    if spec.on_confirm:
        spec.on_confirm(session, option.ctx, inputs)
    return spent


def _take_dice(expr: str, cost: int) -> str | None:
    """``expr`` con ``cost`` dadi in meno; ``None`` se non ne restano abbastanza."""
    match = _DICE.match(expr)
    if match is None or int(match[1]) < cost:
        return None
    return f"{int(match[1]) - cost}d{match[2]}{match[3] or ''}"


def apply_options(session: Any, ctx: RuleContext, keys: list[str], inputs: dict | None = None,
                  phase: str = "before") -> AppliedOptions:
    """Riconvalida e paga le opzioni scelte. ``OptionUnavailable`` lascia pagamenti a metà: il chiamante annulla."""
    inputs = inputs or {}
    keys = list(dict.fromkeys(keys))
    usable = {o.spec.key: o for o in roll_options_for(ctx) if o.spec.phase == phase}
    confirmed = ctx.confirmed if phase != "before" else ()
    out = AppliedOptions()
    dice: dict[str, str] = {}
    groups: set[str] = set()
    for key in keys:
        option = usable.get(key)
        if option is None or (option.spec.needs and option.spec.needs not in keys
                              and option.spec.needs not in confirmed):
            raise OptionUnavailable(key)
        spec, given = option.spec, inputs.get(key) or {}
        if spec.group:
            if spec.group in groups:
                raise OptionUnavailable(key)
            groups.add(spec.group)
        if spec.requires_input == "slot":
            _slot_level(ctx.char, spec, given)  # i dadi dipendono dallo slot: va controllato prima di calcolarli
        paid = _spend(session, option, given)
        out.spent += paid
        out.keys.append(key)
        if spec.pay_if_success:
            out.refundable[key] = paid
        if spec.replace_die:
            out.replace_die = given["die"]
        out.reroll = out.reroll or spec.after == "reroll"
        out.succeed = out.succeed or spec.after == "succeed"
        out.second_attack = out.second_attack or spec.second_attack
        if spec.miss_damage:
            out.miss_damage = max(0, spec.miss_damage(option.ctx))
        if spec.effect:
            out.effects.append(spec.effect(option.ctx, given))
        if spec.target_effect:
            keep_target_effect(ctx.char, key, spec.target_effect(option.ctx, given))
            out.targets.append(key)
        if spec.extra_dice:
            dice[key] = spec.extra_dice(option.ctx, given)
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
    for key in keys:
        spec = usable[key].spec
        if spec.dice_cost:
            left = _take_dice(dice.get(spec.needs, ""), spec.dice_cost)
            if left is None:
                raise OptionUnavailable(key)
            dice[spec.needs] = left
    for key, expr in dice.items():
        if expr.startswith("0d") and "+" not in expr and "-" not in expr:
            continue
        spec = usable[key].spec
        if spec.separate_damage:
            out.separate_dice.append([expr, spec.crit_doubles])
        else:
            (out.extra_dice if spec.crit_doubles else out.fixed_dice).append(expr)
    return out


def refund_spent(char: Any, spent: list[str]) -> None:
    """Restituisce ciò che ``_spend`` ha pagato, a partire dai suoi gettoni."""
    turn = _turn(char)
    for token in spent:
        kind, _, rest = token.partition(":")
        if kind == "once":
            turn["once_per_turn"] = [k for k in turn.get("once_per_turn", []) if k != rest]
        elif kind == "turn" and rest == "extra_action":
            turn["extra_actions"] = turn.get("extra_actions", 0) + 1
        elif kind == "turn":
            turn[TURN_FLAGS[rest]] = False
        elif kind == "feature":
            feature_key, _, amount = rest.rpartition(":")
            row = next((a for a in char.abilities if a.feature_key == feature_key
                        and a.max_uses is not None and (a.uses or 0) < a.max_uses), None)
            if row is not None:
                row.uses = min(row.max_uses, (row.uses or 0) + int(amount))
        elif kind == "slot":
            level, _, pact = rest.partition(":")
            slot = next((s for s in char.spell_slots
                         if s.level == int(level) and bool(s.is_pact) == bool(pact) and s.used > 0), None)
            if slot is not None:
                slot.used -= 1
        elif kind == "die":
            key, _, value = rest.rpartition(":")
            _store_saved_dice(char, key, [*saved_dice(char, key), int(value)])
    char.turn_state = turn


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


def doubled_dice(expr: str) -> str:
    """Il critico raddoppia i dadi, non il fisso."""
    match = _DICE.match(expr)
    return f"{int(match[1]) * 2}d{match[2]}{match[3] or ''}" if match else expr


def scale_damage(value: int, multiplier: float) -> int:
    """Moltiplicatore sul danno, per difetto."""
    return int(value * multiplier)
