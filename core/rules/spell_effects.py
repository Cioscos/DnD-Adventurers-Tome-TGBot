"""Effetti degli incantesimi lanciati sui personaggi: tipi del catalogo e modificatori degli stati ``spell:<chiave>``."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from core.rules.types import Modifier, RollOptionSpec

SPELL_STATE_PREFIX = "spell:"
SPELL_CLOCK_PREFIX = "spell_cast:"


def roll(count: int, sides: int, bonus: int = 0) -> int:
    """``count`` dadi a ``sides`` facce più ``bonus`` (Vita Falsata, Rigenerazione, Resistenza dell'Orso)."""
    return sum(random.randint(1, sides) for _ in range(count)) + bonus


@dataclass(frozen=True)
class SpellTarget:
    kind: Literal["self", "ally", "allies", "aura"]
    count: Callable[[int], int] = lambda slot: 1  # numero massimo di bersagli per livello di slot


@dataclass(frozen=True)
class SpellChoice:
    key: str
    label: dict[str, str]
    options: Callable[[str], list[str]]  # per edizione


@dataclass(frozen=True)
class SpellVariant:
    # riceve i ``data`` dello stato: slot_level, choices, caster_id, caster_name, spell_key
    modifiers: Callable[[dict], tuple[Modifier, ...]] = lambda d: ()
    options: tuple[RollOptionSpec, ...] = ()
    rounds: int | None = None
    until_rest: bool = False
    concentration: bool = False
    choices: tuple[SpellChoice, ...] = ()
    on_apply: Callable[[Any, dict], None] | None = None
    text: dict[str, str] | None = None
    condition: str | None = None  # condizione che lo stato impone al bersaglio e toglie quando finisce (Invisibile)
    immune_conditions: tuple[str, ...] = ()  # condizioni che il bersaglio non può avere finché dura
    ends_on: tuple[str, ...] = ("manual",)  # fini dello stato sul bersaglio (``attack`` / ``cast``: Invisibilità)
    max_targets: Callable[[int], int] | None = None  # sostituisce ``target.count`` quando il numero di bersagli cambia con l'edizione (Saltare 2014)
    track: bool = False  # lo stato (e l'orologio di concentrazione) esiste anche senza modificatori: effetti solo descrittivi
    # PF al lancio, per ogni bersaglio: i temporanei (il maggiore vince) e la cura (limitata al massimo, Aiuto alza prima il massimo).
    # Senza altro effetto l'incantesimo è istantaneo: nessuno stato né orologio (Vita Falsata 2024, Parola del Potere: Fortificare).
    per_target: Callable[[dict], dict] | None = None  # dati tirati per ogni bersaglio e uniti ai ``data`` dello stato (Banchetto degli Eroi: 2d10)
    temp_hp: Callable[[dict], int] | None = None
    temp_hp_ends: bool = False  # i PF temporanei dati e rimasti al bersaglio svaniscono quando lo stato finisce (Eroismo, Resistenza dell'Orso)
    heal: Callable[[dict], int] | None = None
    # A inizio del turno del bersaglio: ``turn_heal(data, personaggio)`` (Rigenerazione, Aura di Vita) e PF temporanei (Eroismo)
    turn_heal: Callable[[dict, Any], int] | None = None
    turn_temp_hp: Callable[[dict], int] | None = None
    clock_ends_on: tuple[str, ...] = ()  # fini dell'orologio del lanciatore oltre a concentrazione e riposo (``unconscious``: Legame di Protezione)
    ends_at_zero_temp: bool = False  # 2024: lo stato sul bersaglio finisce quando i PF temporanei sono esauriti (Armatura di Agathys)
    # Promemoria per il GM quando il bersaglio subisce danno: ``f(data, aveva_PF_temporanei) -> {"it", "en"}`` o ``None``
    retaliation: Callable[[dict, bool], dict[str, str] | None] | None = None
    shares_damage: bool = False  # il lanciatore subisce lo stesso danno del bersaglio (Legame di Protezione)


@dataclass(frozen=True)
class SpellEffect:
    key: str
    srd_index: tuple[str, ...]
    names: tuple[str, ...]  # it, en, e gli altri nomi (2024)
    target: SpellTarget
    variants: dict[str, SpellVariant] = field(default_factory=dict)  # "2014" / "2024"

    def max_targets(self, edition: str, slot: int) -> int:
        variant = self.variants.get(edition)
        return (variant.max_targets if variant and variant.max_targets else self.target.count)(slot)


def spell_state_modifiers(char: Any) -> list[tuple[Modifier, str]]:
    """Per ogni stato ``spell:*`` i modificatori della variante dell'edizione del lanciatore (``data["edition"]``)."""
    from core.rules.catalog.spells import SPELL_EFFECTS  # import locale: il registro importa questo modulo

    out: list[tuple[Modifier, str]] = []
    for state in char.active_states or []:
        key = str(state.get("key", ""))
        if not key.startswith(SPELL_STATE_PREFIX):
            continue
        data = state.get("data") or {}
        effect = SPELL_EFFECTS.get(data.get("spell_key") or key[len(SPELL_STATE_PREFIX):])
        variant = effect and effect.variants.get(data.get("edition", "2014"))
        if variant:
            out += [(m, f"spell:{effect.key}") for m in variant.modifiers(data)]
    return out


def spell_state_options(char: Any) -> list[tuple[RollOptionSpec, dict]]:
    """Le opzioni al tiro degli stati ``spell:*`` (variante dell'edizione del lanciatore), ognuna con i ``data`` del suo stato."""
    from core.rules.catalog.spells import SPELL_EFFECTS  # import locale: il registro importa questo modulo

    out: list[tuple[RollOptionSpec, dict]] = []
    for state in char.active_states or []:
        key = str(state.get("key", ""))
        if not key.startswith(SPELL_STATE_PREFIX):
            continue
        data = state.get("data") or {}
        effect = SPELL_EFFECTS.get(data.get("spell_key") or key[len(SPELL_STATE_PREFIX):])
        variant = effect and effect.variants.get(data.get("edition", "2014"))
        out += [(o, data) for o in variant.options] if variant else []
    return out
