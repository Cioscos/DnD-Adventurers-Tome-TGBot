"""Effetti degli incantesimi lanciati sui personaggi: tipi del catalogo e modificatori degli stati ``spell:<chiave>``."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from core.rules.types import Modifier, RollOptionSpec

SPELL_STATE_PREFIX = "spell:"
SPELL_CLOCK_PREFIX = "spell_cast:"


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


@dataclass(frozen=True)
class SpellEffect:
    key: str
    srd_index: tuple[str, ...]
    names: tuple[str, ...]  # it, en, e gli altri nomi (2024)
    target: SpellTarget
    variants: dict[str, SpellVariant] = field(default_factory=dict)  # "2014" / "2024"


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
