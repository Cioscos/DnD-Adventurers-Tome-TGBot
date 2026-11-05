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
    ``label(key)``: ``{"name": ..., "summary": ...}`` delle opzioni che non sono privilegi del catalogo (armi).
    """
    group: str
    levels: dict[int, int]
    options: Callable[["RuleContext"], list[str]]
    replaceable: bool = False
    label: Callable[[str], dict] | None = None


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
class TargetEffect:
    """Effetto di un privilegio su un altro combattente dell'incontro (D1: nessun modello di posizioni o bersagli).

    ``condition``: slug applicato (anche ``custom:*``). ``save_ability``/``save_dc``: TS del bersaglio; senza, l'effetto
    si applica subito. ``on_failure_only=False``: si applica comunque e il TS non lo toglie (resta solo il risultato).
    Durata: ``ends_at`` = ``{"anchor": "owner"|"source", "edge": "start"|"end", "count": n}`` (stesso formato di
    ``ExpirySpec``, ``source`` = chi usa il privilegio); altrimenti ``rounds`` round sul turno del bersaglio; senza
    nessuno dei due dura finché non viene tolta. ``damage_dice``: danno dell'effetto, mostrato nell'esito."""
    condition: str | None = None
    save_ability: str | None = None
    save_dc: int | None = None
    rounds: int | None = None
    ends_at: dict | None = None
    on_failure_only: bool = True
    damage_dice: str | None = None


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
    target_effect: "Callable[[RuleContext, dict], TargetEffect] | None" = None


@dataclass(frozen=True)
class Modifier:
    """Effetto su un tiro o su un valore derivato. Vedi ``core.rules.modifiers.collect_modifiers``.

    ``target``: ``attack``, ``damage``, ``ac``, ``speed``, ``initiative``, ``save``, ``skill``, ``passive``,
    ``hp_max`` (somme); ``advantage``, ``disadvantage``, ``auto_fail``, ``note`` (segnali, ``value`` ignorato);
    ``min_d20``, ``crit_min`` (soglie); ``resistance:<tipo>``, ``immunity:<tipo>`` (``all`` = ogni tipo);
    ``half_prof``; ``speed_zero``, ``speed_half``, ``hp_max_half``.
    ``when`` limita l'effetto (di solito su ``ctx.roll``); senza, vale sempre."""
    target: str
    value: "Callable[[RuleContext], int] | int"
    when: "Callable[[RuleContext], bool] | None" = None
    source: str = ""


# slot di turno -> chiave booleana in ``Character.turn_state``
TURN_FLAGS = {
    "action": "action_used",
    "bonus": "bonus_used",
    "reaction": "reaction_used",
    "free_interaction": "free_interaction_used",
    "spell_slot": "spell_slot_cast",
    "bonus_spell": "bonus_spell_cast",
}


@dataclass(frozen=True)
class Cost:
    """Costo di un'opzione al tiro: usi della riga ``feature_key`` e/o uno slot di livello almeno ``spell_slot_min``."""
    feature_key: str | None = None
    amount: int = 1
    spell_slot_min: int | None = None


@dataclass(frozen=True)
class RollOptionSpec:
    """Conferma al tiro: ciò che l'app non vede lo dichiara il giocatore, il calcolo resta al server.

    ``phase``: ``before`` (prima del d20, del danno da incantesimo o del lancio), ``after_hit`` (dopo il colpo, solo
    attacchi), ``after_damage`` (dadi di danno già visti di ``spell_damage``), ``damage_in`` (danno subito).
    ``rolls``: ``attack``, ``spell_damage``, ``skill``, ``save``, ``initiative``, ``damage_taken``, ``cast`` (il lancio:
    ``/use`` e ``cast_options`` di ``/attack``, ``ctx.spell`` è l'incantesimo). ``available(ctx)``: ciò che l'app sa già.

    ``extra_dice(ctx, inputs) -> "2d6"`` e ``bonus(ctx, inputs) -> int``, dove ``inputs`` è ciò che il giocatore ha
    scelto per l'opzione. Effetto per fase: ``before`` su un attacco, ``bonus`` al colpire e dadi al danno, che
    raddoppiano al critico; ``before`` sugli altri d20, entrambi al totale; ``before`` su ``spell_damage`` e
    ``after_hit``, entrambi al danno; ``damage_in``, entrambi riducono il danno. ``multiplier`` agisce sul danno,
    per difetto; sul danno subito viene prima di resistenza e vulnerabilità.

    ``requires_input="slot"``: il giocatore sceglie ``slot_level`` (con ``cost.spell_slot_min``). ``needs``: un'altra
    opzione da scegliere insieme (+1d8 di Punizione Divina). ``auto_fail``: fallimento automatico confermato.
    ``force_crit``: il colpo a segno è critico (solo ``before``).

    ``group``: una sola opzione del gruppo per richiesta; con ``once_per_turn`` si registra il gruppo, non la chiave.
    ``dice_cost``: dadi tolti all'opzione ``needs`` della stessa richiesta (Colpo Astuto su Attacco Furtivo).
    ``needs`` vale anche per un'opzione confermata prima del tiro di questo attacco (``RuleContext.confirmed``).
    ``crit_doubles=False``: i dadi non raddoppiano al critico. ``separate_damage``: dadi riportati a parte, fuori dal
    totale (seconda creatura). ``on_confirm(session, ctx, inputs)``: effetto collaterale dopo il pagamento, nella
    stessa transazione; è sincrono e ``/hp/undo`` non lo annulla.
    ``after`` (solo ``after_roll``): ``add`` somma al totale, ``reroll`` impone un nuovo d20 (``bonus`` e ``mode``
    valgono su quello), ``succeed`` porta prova o TS a 20 e fa di un attacco un colpo a segno non critico,
    ``miss`` chiude un attacco mancato con il danno ``miss_damage(ctx)`` (Graze).
    ``effect(ctx, inputs) -> {"it": ..., "en": ...}``: esito da mostrare al giocatore (CD, durata).
    ``target_effect(ctx, inputs) -> TargetEffect``: effetto sul combattente scelto; confermata l'opzione, il server lo tiene
    in ``turn_state["target_effects"][key]`` finché il giocatore lo applica (``POST /characters/{id}/target-effects``).
    ``second_attack``: i dadi ``separate_damage`` valgono per un secondo tiro per colpire, fatto dal server (Cleave).
    ``pay_if_success``: si rimborsa se il tiro resta fallito. ``replace_die`` (solo ``before``): il d20 è uno dei
    valori di ``Character.settings["saved_dice"][key]``, dichiarato con ``{"die": n}`` e consumato.
    ``reroll_dice(ctx, inputs) -> n`` (obbligatorio in ``after_damage``): quanti dadi di danno ritirare, scelti dal
    giocatore. ``keep_rolled``: solo dadi al massimo, il nuovo si somma invece di sostituire (Bombardamento Magico)."""
    key: str
    phase: Literal["before", "after_roll", "after_hit", "after_damage", "damage_in"]
    rolls: tuple[str, ...]
    label: dict[str, str]
    available: "Callable[[RuleContext], bool]" = lambda _ctx: True
    extra_dice: "Callable[[RuleContext, dict], str] | None" = None
    bonus: "Callable[[RuleContext, dict], int] | None" = None
    mode: Literal["advantage", "disadvantage"] | None = None
    cost: Cost | None = None
    once_per_turn: bool = False
    slot: str | None = None
    multiplier: float | None = None
    requires_input: Literal["slot"] | None = None
    needs: str | None = None
    auto_fail: bool = False
    force_crit: bool = False
    group: str | None = None
    dice_cost: int = 0
    crit_doubles: bool = True
    separate_damage: bool = False
    on_confirm: "Callable[[Any, RuleContext, dict], None] | None" = None
    after: Literal["add", "reroll", "succeed", "miss"] | None = None
    pay_if_success: bool = False
    replace_die: bool = False
    miss_damage: "Callable[[RuleContext], int] | None" = None
    effect: "Callable[[RuleContext, dict], dict[str, str]] | None" = None
    second_attack: bool = False
    target_effect: "Callable[[RuleContext, dict], TargetEffect] | None" = None
    reroll_dice: "Callable[[RuleContext, dict], int] | None" = None
    keep_rolled: bool = False

    def __post_init__(self) -> None:
        if self.phase not in ("before", "after_roll", "after_hit", "after_damage", "damage_in"):
            raise ValueError(f"fase sconosciuta: {self.phase}")
        if (self.phase == "after_roll") != (self.after in ("add", "reroll", "succeed", "miss")):
            raise ValueError("after è obbligatorio in after_roll e vale solo lì")
        if self.phase == "after_roll" and self.requires_input:
            raise ValueError("after_roll è un pulsante nel modale di esito: non chiede input")
        if self.pay_if_success and self.phase != "after_roll":
            raise ValueError("pay_if_success vale solo dopo il tiro")
        if self.replace_die and (self.phase != "before" or self.requires_input):
            raise ValueError("replace_die vale solo prima del tiro e il suo input è il dado salvato")
        if self.slot is not None and self.slot not in TURN_FLAGS:
            raise ValueError(f"slot sconosciuto: {self.slot}")
        if self.requires_input not in (None, "slot"):
            raise ValueError(f"input sconosciuto: {self.requires_input}")
        if self.force_crit and self.phase != "before":
            raise ValueError("force_crit vale solo prima del tiro")
        if self.cost and self.cost.spell_slot_min is not None and self.requires_input != "slot":
            raise ValueError("uno slot come costo richiede requires_input='slot'")
        if (self.after == "miss") != (self.miss_damage is not None):
            raise ValueError("after='miss' e miss_damage vanno insieme")
        if self.second_attack and not self.separate_damage:
            raise ValueError("second_attack riguarda i dadi separate_damage")
        if (self.phase == "after_damage") != (self.reroll_dice is not None):
            raise ValueError("after_damage e reroll_dice vanno insieme")
        if self.keep_rolled and self.reroll_dice is None:
            raise ValueError("keep_rolled riguarda reroll_dice")
        if self.dice_cost and not self.needs:
            raise ValueError("dice_cost toglie dadi all'opzione indicata da needs")


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
    granted_spells: tuple[str, ...] = ()  # chiavi di `core.rules.catalog.granted_spells.GRANTED_SPELLS`


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
    damage_type: Any = None
    attack_mode: Any = None  # solo attacchi: `melee`, `thrown` o `ranged`
    grip: Any = None  # solo attacchi: `one` o `two`
    offhand: bool = False  # solo attacchi: l'attacco extra della proprietà Leggera
    confirmed: tuple = ()  # opzioni già confermate per questo attacco, nel primo tempo
