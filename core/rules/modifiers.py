"""Modificatori di classe ed effetti delle condizioni: unica fonte per ogni tiro e valore derivato.

I modificatori homebrew restano sommati dai router accanto a questi: qui non si importano.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from core.data.damage_types import damage_multiplier
from core.game.item_bonuses import item_meta
from core.rules.catalog import active_features
from core.rules.edition import character_edition
from core.rules.proficiencies import is_armor_proficient
from core.rules.states import exhaustion_level, immune_conditions
from core.rules.types import Edition, Modifier, RuleContext
from core.rules.weapons import ability_score, has_property, small_race

INCAPACITATING = frozenset({"incapacitated", "paralyzed", "petrified", "stunned", "unconscious"})

_SAVES = {"save", "death_save", "concentration"}
_CHECKS = {"skill", "ability", "initiative", "passive"}
_STR_DEX = {"strength", "dexterity"}

# Tiro -> target le cui somme gli si applicano.
_FLAT_TARGET = {
    "attack": "attack", "damage": "damage", "ac": "ac", "speed": "speed", "hp_max": "hp_max",
    "initiative": "initiative", "passive": "passive", "skill": "skill", "ability": "skill",
    "save": "save", "death_save": "save", "concentration": "save", "spell_healing": "healing",
}
_FLAGS = {"advantage", "disadvantage", "auto_fail", "speed_zero", "speed_half", "carry_double", "fly_speed",
          "maximize_healing"}
_FLAG_FIELD = {"hp_max_half": "hp_half"}


@dataclass
class Applied:
    flat: int = 0
    advantage: bool = False
    disadvantage: bool = False
    auto_fail: bool = False
    min_d20: int | None = None
    crit_min: int = 20
    resistances: set[str] = field(default_factory=set)
    immunities: set[str] = field(default_factory=set)
    notes: list[str] = field(default_factory=list)
    speed_zero: bool = False
    speed_half: bool = False
    hp_half: bool = False
    replace_die: int | None = None  # d20 dichiarato (Portento): nessun dado si tira
    min_total: int | None = None  # totale minimo di una prova (Potenza Indomabile)
    crit_dice: int = 0  # dadi dell'arma in più al critico (Critico Brutale)
    carry_double: bool = False
    fly_speed: bool = False
    maximize_healing: bool = False  # i dadi di cura di un incantesimo valgono il massimo
    advantage_from: list[str] = field(default_factory=list)
    disadvantage_from: list[str] = field(default_factory=list)


def has_state(ctx: RuleContext, key: str) -> bool:
    """Per i ``when`` dei modificatori: lo stato attivo ``key`` è in corso (Ira, Forma Selvatica...)."""
    return any(s.get("key") == key for s in ctx.char.active_states or [])


def surprised_turn(char: Any) -> bool:
    """2014: è il turno della sorpresa, la creatura non agisce né si muove né reagisce (``turn_state``, scritto dal turno).
    Un privilegio con ``acts_when_surprised`` (Istinto Ferino) la toglie finché ha lo stato richiesto (Ira)."""
    if not (getattr(char, "turn_state", None) or {}).get("surprised"):
        return False
    return not any(spec.acts_when_surprised and any(s.get("key") == spec.acts_when_surprised
                                                    for s in char.active_states or [])
                   for spec, _row in active_features(char))


def surprise_exit_features(char: Any) -> list[str]:
    """Con il turno da sorpreso in corso: i privilegi il cui «Usa» avvia lo stato che permette di agire (Ira per
    l'Istinto Ferino). Restano utilizzabili anche se la scheda è incapacitata (la UI non li spegne)."""
    if not surprised_turn(char):
        return []
    wanted = {spec.acts_when_surprised for spec, _row in active_features(char) if spec.acts_when_surprised}
    out: list[str] = []
    for spec, row in active_features(char):
        use = spec.on_use
        if use is None or use.state is None:
            continue
        ctx = RuleContext(char=char, edition=character_edition(char), class_row=row, class_level=row.level)
        state = use.state(ctx, {}) if callable(use.state) else use.state
        if state.key in wanted and (use.available is None or use.available(ctx)):
            out.append(spec.key)
    return out


def is_incapacitated(char: Any) -> bool:
    return surprised_turn(char) or any((char.conditions or {}).get(c) for c in INCAPACITATING)


def compute_condition_effects(char: Any, edition: Edition, ctx: RuleContext) -> list[Modifier]:
    """Effetti sui tiri del personaggio. Quelli degli attacchi subiti sono del pannello Combat (Task 14)."""
    on = {k for k, v in (char.conditions or {}).items()
          if v and k != "exhaustion" and not k.startswith("custom:")} - immune_conditions(char)
    if "petrified" in on:
        on.discard("poisoned")  # 2014 veleno sospeso, 2024 immune alla condizione
    level = exhaustion_level(char)
    roll = ctx.roll
    is_2024 = edition == "2024"
    out: list[Modifier] = []

    def add(target: str, *slugs: str, value: int = 1) -> None:
        out.extend(Modifier(target, value, source=f"condition:{s}") for s in slugs)

    if roll == "attack":
        add("disadvantage", *sorted(on & {"blinded", "poisoned", "prone", "restrained"}))
        if "invisible" in on:
            add("advantage", "invisible")
    if roll in _CHECKS and "poisoned" in on:
        add("disadvantage", "poisoned")
    # Spaventato, Afferrato 2024, Accecato e Assordato sulle prove dipendono da ciò che l'app non vede:
    # sono conferme al tiro in core.rules.roll_options.
    if roll == "initiative" and is_2024:
        if "invisible" in on:
            add("advantage", "invisible")
        add("disadvantage", *sorted(on & INCAPACITATING))
    if roll in _SAVES and ctx.ability in _STR_DEX:
        add("auto_fail", *sorted(on & {"paralyzed", "petrified", "stunned", "unconscious"}))
    if roll in _SAVES and ctx.ability == "dexterity" and "restrained" in on:
        add("disadvantage", "restrained")

    zero = {"grappled", "restrained", "paralyzed", "petrified", "unconscious"}
    add("speed_zero", *sorted(on & (zero if is_2024 else zero | {"stunned"})))
    if surprised_turn(char):
        add("speed_zero", "surprised")
    if "petrified" in on:
        add("resistance:all", "petrified")
        if not is_2024:
            add("immunity:poison", "petrified")

    if level:
        if is_2024:
            # La passiva parte dal bonus di abilità, che ha già il meno fisso.
            if roll == "attack" or roll in _SAVES or (roll in _CHECKS and roll != "passive"):
                add(_FLAT_TARGET[roll], "exhaustion", value=-2 * level)
            add("speed", "exhaustion", value=-5 * level)
        else:
            if roll in _CHECKS:
                add("disadvantage", "exhaustion")
            if level >= 3 and (roll == "attack" or roll in _SAVES):
                add("disadvantage", "exhaustion")
            if level >= 2:
                add("speed_half", "exhaustion")
            if level >= 4:
                add("hp_max_half", "exhaustion")
            if level >= 5:
                add("speed_zero", "exhaustion")
    return out


def _strength_required(item: Any) -> int:
    try:
        return int(item_meta(item).get("strength_req") or 0)
    except (TypeError, ValueError):
        return 0


def _armor_modifiers(ctx: RuleContext) -> list[Modifier]:
    """Armatura o scudo (R21): senza addestramento, Forza insufficiente (velocità -10 ft) e Furtività. Il blocco degli
    incantesimi è del Task 15."""
    out: list[Modifier] = []
    is_2024 = ctx.edition == "2024"
    d20 = ctx.roll == "attack" or ctx.roll in _SAVES or ctx.roll in _CHECKS
    for item in ctx.char.items or []:
        if not item.is_equipped or item.item_type not in ("armor", "shield"):
            continue
        if item.item_type == "armor":
            required = _strength_required(item)
            if required and ability_score(ctx.char, "strength") < required:
                out.append(Modifier("speed", -10, source="armor:strength"))
            if item_meta(item).get("stealth_disadvantage") and ctx.roll == "skill" and ctx.skill == "stealth":
                out.append(Modifier("disadvantage", 1, source="armor:stealth"))
        if is_armor_proficient(ctx.char, item):
            continue
        if item.item_type == "shield" and is_2024:
            out.append(Modifier("ac", -(ctx.char.shield_armor_class or 0), source="armor:untrained"))
        elif d20 and ctx.ability in _STR_DEX:
            out.append(Modifier("disadvantage", 1, source="armor:untrained"))
    return out


def _heavy_weapon(ctx: RuleContext) -> list[Modifier]:
    """2024: Forza o Destrezza sotto 13. 2014: creatura Piccola; una razza sconosciuta passa dalla conferma al tiro."""
    if ctx.roll != "attack" or ctx.item is None or not has_property(ctx.item, "heavy"):
        return []
    if ctx.edition == "2024":
        weak = ability_score(ctx.char, "dexterity" if ctx.attack_mode == "ranged" else "strength") < 13
    else:
        weak = small_race(ctx.char) is True
    return [Modifier("disadvantage", 1, source="weapon:heavy")] if weak else []


def _half_prof(ctx: RuleContext) -> int:
    """Mezza competenza per difetto su prove e TS, solo dove il personaggio non è già competente.
    La passiva parte dal bonus di abilità, che la comprende già."""
    if ctx.roll not in _SAVES and ctx.roll not in ("skill", "ability", "initiative"):
        return 0
    if ctx.skill and (ctx.char.skills or {}).get(ctx.skill):
        return 0
    if ctx.roll in _SAVES and ctx.ability and (ctx.char.saving_throws or {}).get(ctx.ability):
        return 0
    return ctx.char.proficiency_bonus // 2


def collect_modifiers(ctx: RuleContext) -> Applied:
    """Somma condizioni, armatura e privilegi attivi per il tiro ``ctx.roll``."""
    pairs: list[tuple[Modifier, RuleContext, str]] = [
        (m, ctx, m.source) for m in compute_condition_effects(ctx.char, ctx.edition, ctx)
    ]
    pairs += [(m, ctx, m.source) for m in [*_armor_modifiers(ctx), *_heavy_weapon(ctx)]]
    for spec, row in active_features(ctx.char):
        feature_ctx = replace(ctx, class_row=row, class_level=row.level)
        pairs += [(m, feature_ctx, m.source or f"feature:{spec.key}") for m in spec.modifiers]

    out = Applied()
    half_prof = False
    flat_target = _FLAT_TARGET.get(ctx.roll)
    for m, mctx, source in pairs:
        if m.when is not None and not m.when(mctx):
            continue
        counted = False
        if m.target == flat_target:
            value = m.value(mctx) if callable(m.value) else m.value
            out.flat += value
            counted = value != 0
        elif m.target == "half_prof":
            half_prof = counted = True
        elif m.target == "note":
            counted = True
        elif m.target in _FLAGS:
            setattr(out, m.target, True)
            if m.target in ("advantage", "disadvantage"):
                getattr(out, f"{m.target}_from").append(source)
            counted = m.target in ("advantage", "disadvantage", "auto_fail")
        elif m.target in _FLAG_FIELD:
            setattr(out, _FLAG_FIELD[m.target], True)
        elif m.target == "min_d20":
            out.min_d20 = max(out.min_d20 or 0, m.value(mctx) if callable(m.value) else m.value)
            counted = True
        elif m.target == "min_total":
            out.min_total = max(out.min_total or 0, m.value(mctx) if callable(m.value) else m.value)
            counted = True
        elif m.target == "crit_dice":
            out.crit_dice += m.value(mctx) if callable(m.value) else m.value
            counted = True
        elif m.target == "crit_min":
            out.crit_min = min(out.crit_min, m.value(mctx) if callable(m.value) else m.value)
        elif m.target.startswith("resistance:"):
            out.resistances.add(m.target.split(":", 1)[1])
        elif m.target.startswith("immunity:"):
            out.immunities.add(m.target.split(":", 1)[1])
        if counted and source and source not in out.notes:
            out.notes.append(source)
    if half_prof:
        out.flat += _half_prof(ctx)
    return out


def modifiers_for(char: Any, roll: str | None, **kw: Any) -> Applied:
    return collect_modifiers(RuleContext(char=char, edition=character_edition(char), roll=roll, **kw))


def final_mode(player_mode: str, applied: Applied) -> str:
    """Modo scelto dal giocatore + automatici: più fonti uguali contano una volta, i due opposti si annullano."""
    advantage = player_mode == "advantage" or applied.advantage
    disadvantage = player_mode == "disadvantage" or applied.disadvantage
    if advantage == disadvantage:
        return "normal"
    return "advantage" if advantage else "disadvantage"


def effective_hp_max(char: Any, homebrew_bonus: int = 0, exhaustion: int | None = None) -> int:
    """PF massimi: base + homebrew + privilegi; ``exhaustion`` simula un altro livello (anteprima del riposo)."""
    applied = modifiers_for(char if exhaustion is None else _WithExhaustion(char, exhaustion), "hp_max")
    total = char.hit_points + homebrew_bonus + applied.flat
    return total // 2 if applied.hp_half else total


class _WithExhaustion:
    """Il personaggio con un livello di spossatezza diverso, senza toccarne i dati."""

    def __init__(self, char: Any, level: int) -> None:
        self._char = char
        self.conditions = {**(char.conditions or {}), "exhaustion": level}

    def __getattr__(self, name: str) -> Any:
        return getattr(self._char, name)


def effective_speed(char: Any, base: int) -> int:
    """``base`` = velocità con i bonus già sommati (homebrew, oggetti, ingombro)."""
    applied = modifiers_for(char, "speed")
    if applied.speed_zero:
        return 0
    total = base + applied.flat
    return max(0, total // 2 if applied.speed_half else total)


def passive_adjustment(char: Any, skill: str) -> int:
    """Passiva: +5 con vantaggio, -5 con svantaggio, più i modificatori ``passive``."""
    applied = modifiers_for(char, "passive", skill=skill)
    return applied.flat + {"advantage": 5, "disadvantage": -5, "normal": 0}[final_mode("normal", applied)]


def damage_taken_mode(char: Any, slug: str | None) -> str:
    """Come ``damage_multiplier``, con resistenze e immunità di condizioni e privilegi. Non scrive nulla."""
    applied = modifiers_for(char, None)
    mods = char.damage_modifiers if isinstance(char.damage_modifiers, dict) else {}
    if slug is None:
        return "half" if "all" in applied.resistances else "none"
    resistances = [*(mods.get("resistances") or []), *applied.resistances]
    if "all" in applied.resistances:
        resistances.append(slug)
    return damage_multiplier({
        "immunities": [*(mods.get("immunities") or []), *applied.immunities],
        "resistances": resistances,
        "vulnerabilities": mods.get("vulnerabilities") or [],
    }, slug)
