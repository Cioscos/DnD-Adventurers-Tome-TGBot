"""Tipi condivisi delle regole di classe."""
from __future__ import annotations

import re
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
    ``label(key)``: ``{"name": ..., "summary": ...}`` delle opzioni che non sono privilegi del catalogo (armi, abilità).
    ``grants``: alla risoluzione le opzioni scelte sono abilità e diventano ``proficient`` (competenza) o ``expert``
    (maestria); un'abilità già ``expert`` non scende mai. ``spell_pick``: le scelte non sono opzioni di un elenco ma
    incantesimi di qualsiasi classe, aggiunti dalla pagina degli incantesimi (``known`` conta fra i conosciuti,
    ``extra`` no: Segreti Magici Aggiuntivi); ``options`` non si usa.
    ``owned(ctx)``: abilità che il giocatore ha già sulla scheda e che, per un personaggio esistente prima del catalogo
    (scelta con ``retrofit``, R39), si possono dichiarare «già sulla scheda» invece di aggiungerne altre.
    """
    group: str
    levels: dict[int, int]
    options: Callable[["RuleContext"], list[str]]
    replaceable: bool = False
    label: Callable[[str], dict] | None = None
    grants: Literal["proficient", "expert"] | None = None
    spell_pick: Literal["known", "extra"] | None = None
    owned: Callable[["RuleContext"], list[str]] | None = None

    def __post_init__(self) -> None:
        if self.grants not in (None, "proficient", "expert"):
            raise ValueError(f"grants sconosciuto: {self.grants}")
        if self.spell_pick not in (None, "known", "extra"):
            raise ValueError(f"spell_pick sconosciuto: {self.spell_pick}")


@dataclass(frozen=True)
class UnarmoredAc:
    """CA senza armatura: ``base`` + modificatori di ``abilities``. ``no_shield``: lo scudo la annulla (Monaco)."""
    abilities: tuple[str, ...]
    base: int = 10
    no_shield: bool = False


_DICE = re.compile(r"(\d+)d(\d+)")


def parse_dice(text: str) -> tuple[int, int] | None:
    """``"2d6"`` -> ``(2, 6)``; ``None`` se non è esattamente ``NdM`` con N >= 1 e M >= 2."""
    m = _DICE.fullmatch(text)
    if m is None or int(m[1]) < 1 or int(m[2]) < 2:
        return None
    return int(m[1]), int(m[2])


ENDS_ON = frozenset({
    "rest_short", "rest_long", "unconscious", "incapacitated", "turn_end_inactive", "concentration_end", "manual",
    "new_turn",
})

BARDIC_DIE = "bardic_die"  # stato sul ricevente del dado di Ispirazione Bardica (R38); `data`: die, combat
WAR_GODS_BLESSING = "war_gods_blessing"  # stato sul ricevente del +10 al tiro per colpire (Benedizione del Dio della Guerra)
TRICKSTER_BLESSING = "trickster_blessing"  # stato sul ricevente del vantaggio a Furtività (Benedizione dell'Ingannatore)


@dataclass(frozen=True)
class StateSpec:
    """Stato attivo avviato da un privilegio (Ira, Forma Selvatica...).

    ``ends_on`` (insieme chiuso ``ENDS_ON``): ``turn_end_inactive`` = a fine turno senza aver attaccato né subito
    danno dall'ultimo turno (Ira 2014); ``incapacitated`` = condizione che toglie le azioni o 0 PF; ``new_turn`` = al
    prossimo «Nuovo turno» di chi lo porta (Canto di Riposo).
    ``rounds``: durata in round, ``None`` = senza scadenza. ``blocks_casting``: finché dura non si lanciano
    incantesimi (conferma al lancio). ``exhaustion_on_end``: livelli di spossatezza quando lo stato finisce, per
    qualunque via. ``immune_conditions``: condizioni che non si possono aggiungere finché dura; quelle già presenti
    sono sospese (restano sulla scheda ma non hanno effetto). ``end_slot``: slot di turno che costa terminarlo a mano
    (``bonus`` per l'Ira): se è già speso lo stato finisce lo stesso, così un tocco sbagliato si corregge; le fini
    automatiche (perdita dei sensi, durata, riposo) non costano nulla."""
    key: str
    rounds: int | None = None
    ends_on: tuple[str, ...] = ("manual",)
    data: dict = field(default_factory=dict)
    blocks_casting: bool = False
    exhaustion_on_end: int = 0
    immune_conditions: tuple[str, ...] = ()
    end_slot: str | None = None

    def __post_init__(self) -> None:
        unknown = set(self.ends_on) - ENDS_ON
        if unknown:
            raise ValueError(f"ends_on sconosciuto: {sorted(unknown)}")
        if self.end_slot is not None and self.end_slot not in TURN_FLAGS:
            raise ValueError(f"end_slot sconosciuto: {self.end_slot}")


@dataclass(frozen=True)
class TargetEffect:
    """Effetto di un privilegio su un altro combattente dell'incontro (D1: nessun modello di posizioni o bersagli).

    ``condition``: slug applicato (anche ``custom:*``). ``save_ability``/``save_dc``: TS del bersaglio; senza, l'effetto
    si applica subito. ``on_failure_only=False``: si applica comunque e il TS non lo toglie (resta solo il risultato).
    Durata: ``ends_at`` = ``{"anchor": "owner"|"source", "edge": "start"|"end", "count": n}`` (stesso formato di
    ``ExpirySpec``, ``source`` = chi usa il privilegio); altrimenti ``rounds`` round sul turno del bersaglio; senza
    nessuno dei due dura finché non viene tolta. ``damage_dice``: danno dell'effetto, mostrato nell'esito.
    ``extends``: se il bersaglio porta già la condizione da chi usa il privilegio, la durata si rinnova senza un nuovo TS
    (prolungamento). ``immune_on_success``: chi supera il TS non è più bersaglio di questo effetto fino al prossimo
    riposo lungo di chi lo usa (le «24 ore» delle schede)."""
    condition: str | None = None
    save_ability: str | None = None
    save_dc: int | None = None
    rounds: int | None = None
    ends_at: dict | None = None
    on_failure_only: bool = True
    damage_dice: str | None = None
    extends: bool = False
    immune_on_success: bool = False


@dataclass(frozen=True)
class UseToggle:
    """Scelta sì/no all'uso di un privilegio: ``params[key]`` vale ``True`` se il giocatore l'ha attivata."""
    key: str
    label: dict[str, str]
    available: "Callable[[RuleContext], bool]" = lambda _ctx: True


@dataclass(frozen=True)
class UseChoice:
    """Scelta fra più valori all'uso di un privilegio (Conoscenze Secolari: quale abilità): ``params[key]`` ne contiene uno.
    ``options(ctx)`` elenca le chiavi ammesse, ``option_label(key)`` dà il nome bilingue."""
    key: str
    label: dict[str, str]
    options: "Callable[[RuleContext], list[str]]"
    option_label: "Callable[[str], dict[str, str]]"


@dataclass(frozen=True)
class OnUse:
    """Cosa fa il pulsante «Usa» di un privilegio oltre a spendere ``cost`` usi.

    ``slot``: slot di turno da spendere (``action``, ``bonus``, ``reaction``...). ``rolls``: dado tirato
    (``1d10``, validato alla definizione); ``heal(ctx, tirato) -> PF`` converte il tiro in cura. ``grants_action``: +1
    azione extra. Con ``amount`` = N (pool come Imposizione delle Mani) l'effetto per unità si ripete N volte: tiri, cura
    e azioni extra; lo stato e l'effetto sul bersaglio si avviano una volta sola.
    ``rolls`` può essere anche ``f(ctx) -> "NdM"`` quando il dado dipende dal livello (Parole Taglienti).
    ``spends``: chiave di un altro privilegio i cui usi si spendono (``cost``), invece degli usi di questo; senza usi
    sufficienti l'uso è rifiutato (409 ``no_uses``) prima di toccare il turno.
    ``ally_state``: con ``params["target_character_id"]`` lo stato non va a chi usa il privilegio ma a quell'altro
    personaggio della stessa serata (Ispirazione Bardica, R38); un bersaglio non valido è rifiutato (422
    ``invalid_target``) prima di spendere qualcosa. Senza bersaglio lo stato è di chi lo usa.
    ``concentration``: l'uso avvia una concentrazione che non è di un incantesimo (Invocare Duplicato), per la durata
    dello stato; gli stati con ``concentration_end`` finiscono con lei.
    ``choices``: scelte da fare all'uso, validate prima di spendere qualcosa (422 ``invalid_choice``).
    ``choose_amount``: il giocatore sceglie quanti usi spendere (selettore in «Turno», massimo gli usi rimasti);
    ``max_amount``: tetto per un uso solo.
    ``state``: uno ``StateSpec`` oppure ``f(ctx, params) -> StateSpec`` quando dipende dal livello o da una scelta fatta
    all'uso. ``ends_concentration``: l'uso interrompe la concentrazione. ``available(ctx)``: l'uso è possibile solo se
    vero (409 ``feature_unavailable``), per esempio solo con uno stato attivo. ``toggles``: scelte facoltative da
    fare all'uso (Frenesia), mostrate come interruttori e lette dal privilegio in ``params``."""
    cost: int = 1
    slot: str | None = None
    heal: Callable[["RuleContext", int], int] | None = None
    state: "StateSpec | Callable[[RuleContext, dict], StateSpec] | None" = None
    ends_concentration: bool = False
    available: "Callable[[RuleContext], bool] | None" = None
    toggles: "tuple[UseToggle, ...]" = ()
    grants_action: bool = False
    rolls: "str | Callable[[RuleContext], str] | None" = None
    target_effect: "Callable[[RuleContext, dict], TargetEffect] | None" = None
    choose_amount: bool = False
    max_amount: int | None = None
    spends: str | None = None
    ally_state: bool = False
    concentration: bool = False
    choices: "tuple[UseChoice, ...]" = ()

    def __post_init__(self) -> None:
        if self.max_amount is not None and (not self.choose_amount or self.max_amount < 1):
            raise ValueError("max_amount (>= 1) vale solo con choose_amount")
        if isinstance(self.rolls, str) and not parse_dice(self.rolls):
            raise ValueError(f"rolls non valido: {self.rolls!r} (atteso NdM, per esempio 1d10)")


@dataclass(frozen=True)
class Modifier:
    """Effetto su un tiro o su un valore derivato. Vedi ``core.rules.modifiers.collect_modifiers``.

    ``target``: ``attack``, ``damage``, ``ac``, ``speed``, ``initiative``, ``save``, ``skill``, ``passive``,
    ``hp_max`` (somme); ``advantage``, ``disadvantage``, ``auto_fail``, ``note`` (segnali, ``value`` ignorato);
    ``min_d20``, ``crit_min`` (soglie); ``min_total`` (totale minimo di una prova); ``crit_dice`` (dadi dell'arma in più
    al critico); ``resistance:<tipo>``, ``immunity:<tipo>`` (``all`` = ogni tipo);
    ``half_prof``; ``speed_zero``, ``speed_half``, ``hp_max_half``; ``carry_double`` (capacità di carico doppia);
    ``fly_speed`` (velocità di volo pari a quella a terra).
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
    """Costo di un'opzione al tiro: usi della riga ``feature_key``, uno slot di livello almeno ``spell_slot_min`` e/o lo
    stato attivo ``state_key``, che si chiude (e il rimborso rimette com'era)."""
    feature_key: str | None = None
    amount: int = 1
    spell_slot_min: int | None = None
    state_key: str | None = None


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
    ``cancels``: la conferma toglie il vantaggio o lo svantaggio dato da quelle fonti, lasciando le altre.
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
    cancels: tuple[str, ...] = ()  # fonti di vantaggio o svantaggio (`condition:<slug>`) tolte dal tiro
    maximize: bool = False  # i dadi di danno dell'incantesimo valgono il massimo (solo ``before`` su ``spell_damage``)

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
        if self.phase == "after_damage" and self.requires_input:
            raise ValueError("after_damage non chiede input: il client manda sempre option_inputs vuoto")
        if self.keep_rolled and self.reroll_dice is None:
            raise ValueError("keep_rolled riguarda reroll_dice")
        if self.maximize and (self.phase != "before" or "spell_damage" not in self.rolls):
            raise ValueError("maximize vale solo prima del danno di un incantesimo")
        if self.dice_cost and not self.needs:
            raise ValueError("dice_cost toglie dadi all'opzione indicata da needs")


@dataclass(frozen=True)
class ZeroHpSave:
    """A 0 PF senza morte istantanea, con lo stato ``state`` attivo, tiro salvezza automatico (Ira Implacabile).

    CD = ``base_dc`` + ``step`` per ogni uso già fatto; se riesce i PF tornano a ``hp(ctx)``. Gli usi si azzerano con un
    riposo (breve o lungo)."""
    state: str
    ability: str = "constitution"
    base_dc: int = 10
    step: int = 5
    hp: "Callable[[RuleContext], int]" = lambda _ctx: 1


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
    cast_in_form: bool = False  # in Forma Selvatica si lanciano incantesimi senza conferma (Incantesimi Bestiali)
    attacks_per_action: int = 0
    target_effect: Any = None
    # categoria (`armor`/`weapons`/`tools`) -> id di `core.rules.proficiencies.LABELS`, concesse una volta sola
    proficiency_grants: dict[str, tuple[str, ...]] | None = None
    unarmored: UnarmoredAc | None = None
    granted_spells: tuple[str, ...] = ()  # chiavi di `core.rules.catalog.granted_spells.GRANTED_SPELLS`
    granted_ritual_only: bool = False  # gli incantesimi concessi si lanciano solo come rituale (Cercatore di Spiriti)
    acts_when_surprised: str | None = None  # 2014: con quello stato attivo il turno da sorpreso non toglie le azioni
    zero_hp_save: ZeroHpSave | None = None
    # punteggio -> bonus, con massimo `ability_cap`: scritto sul punteggio dal sync, tolto se il privilegio sparisce
    ability_bonus: dict[str, int] | None = None
    ability_cap: int = 20
    no_row: bool = False  # solo catalogo: nessuna riga Ability sulla scheda (regole generali, scelte di livello)
    # dove è coperta una riga senza `Ability` che la mappatura vuole da implementare o correggere: `lavori-successivi`
    # (fuori dai cataloghi, R32) oppure il punto del codice o del test; `check_catalog` lo pretende insieme a `no_row`
    covered_by: str | None = None


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
