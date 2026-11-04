"""Tipi condivisi delle regole di classe."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

Edition = Literal["2014", "2024"]


@dataclass(frozen=True)
class Uses:
    """Formula degli usi massimi: tabella (livello minimo -> usi) + mod caratteristica + competenza + per livello."""
    table: dict[int, int] | None = None
    ability: str | None = None
    minimum: int = 1
    per_level: int = 0
    proficiency: bool = False
    unlimited_from: int | None = None


@dataclass(frozen=True)
class ChoiceSpec:
    """Opzioni di classe da scegliere salendo di livello (Metamagia, Invocazioni, Stili...).

    ``levels``: livello di classe minimo -> totale delle opzioni conosciute a quel livello.
    ``options(ctx)``: chiavi scegliibili (``ctx.class_row.options[group]`` contiene già le scelte).
    """
    group: str
    levels: dict[int, int]
    options: Callable[["RuleContext"], list[str]]
    replaceable: bool = False


@dataclass(frozen=True)
class UnarmoredAc:
    """CA senza armatura: ``base`` + modificatori di ``abilities``. ``no_shield``: lo scudo la annulla (Monaco)."""
    abilities: tuple[str, ...]
    base: int = 10
    no_shield: bool = False


ENDS_ON = frozenset({
    "rest_short", "rest_long", "unconscious", "incapacitated", "turn_end_inactive", "concentration_end", "manual",
})


@dataclass(frozen=True)
class StateSpec:
    """Stato attivo avviato da un privilegio (Ira, Forma Selvatica...).

    ``ends_on`` (insieme chiuso ``ENDS_ON``): ``turn_end_inactive`` = a fine turno senza aver attaccato né subito
    danno dall'ultimo turno (Ira 2014); ``incapacitated`` = condizione che toglie le azioni o 0 PF.
    ``rounds``: durata in round, ``None`` = senza scadenza."""
    key: str
    rounds: int | None = None
    ends_on: tuple[str, ...] = ("manual",)
    data: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        unknown = set(self.ends_on) - ENDS_ON
        if unknown:
            raise ValueError(f"ends_on sconosciuto: {sorted(unknown)}")


@dataclass(frozen=True)
class OnUse:
    """Cosa fa il pulsante «Usa» di un privilegio oltre a spendere ``cost`` usi.

    ``slot``: slot di turno da spendere (``action``, ``bonus``, ``reaction``...). ``rolls``: dado tirato
    (``1d10``); ``heal(ctx, tirato) -> PF`` converte il tiro in cura. ``grants_action``: +1 azione extra."""
    cost: int = 1
    slot: str | None = None
    heal: Callable[["RuleContext", int], int] | None = None
    state: StateSpec | None = None
    grants_action: bool = False
    rolls: str | None = None


@dataclass(frozen=True)
class FeatureSpec:
    key: str
    class_key: str
    edition: Edition
    level: int
    source_title: str  # titolo esatto della scheda
    name: dict[str, str]
    summary: dict[str, str]
    action_type: str | None
    uses: Uses | None = None
    restoration: str | dict[int, str] = "none"  # dict: livello minimo -> tipo di riposo
    short_rest_recovers: int | None = None
    subclass: str | None = None
    option_group: str | None = None
    option_key: str | None = None
    choices: tuple = ()
    modifiers: tuple = ()
    roll_options: tuple = ()
    on_use: Any = None
    passive: bool = False
    attacks_per_action: int = 0
    target_effect: Any = None
    # categoria (`armor`/`weapons`/`tools`) -> id di `core.rules.proficiencies.LABELS`, concesse una volta sola
    proficiency_grants: dict[str, tuple[str, ...]] | None = None
    unarmored: UnarmoredAc | None = None


@dataclass(frozen=True)
class RuleContext:
    char: Any
    edition: Edition
    class_row: Any = None
    class_level: int = 0
    roll: Any = None
    ability: Any = None
    skill: Any = None
    item: Any = None
    spell: Any = None
    turn: Any = None
