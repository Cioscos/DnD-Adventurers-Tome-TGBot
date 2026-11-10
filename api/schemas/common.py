"""Shared Pydantic schemas for simple character sub-resources."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from core.db.models import RestorationType
from core.game.actions import ActionType

# Valid restoration_type values, derived from the enum so the schema can never
# drift from the DB column. Accepting an unknown string here would silently
# corrupt the Enum(RestorationType) column (SQLAlchemy passes unrecognized
# strings straight through with validate_strings=False) and brick the character
# on the next read — see the heal migration in core/db/engine.py.
_ALLOWED_RESTORATION = frozenset(e.value for e in RestorationType)


def _validate_restoration_type(value: Optional[str]) -> Optional[str]:
    if value is not None and value not in _ALLOWED_RESTORATION:
        raise ValueError(
            f"restoration_type must be one of {sorted(_ALLOWED_RESTORATION)}"
        )
    return value


# ---------------------------------------------------------------------------
# AbilityScore
# ---------------------------------------------------------------------------

PROFICIENCY_CATEGORIES = ("armor", "weapons", "tools", "other")


def normalize_proficiencies(v: Any) -> dict[str, list[str]]:
    """Legacy plain list -> ``other``; object -> the four known categories only.

    Stored data is migrated lazily: reads always return the object, writes store it.
    """
    if isinstance(v, dict):
        return {k: [str(x) for x in (v.get(k) or [])] for k in PROFICIENCY_CATEGORIES}
    return {**normalize_proficiencies({}), "other": [str(x) for x in (v or [])]}


class AppliedModifierRead(BaseModel):
    """A single equipped-item modifier applied to an ability score."""
    source: str
    ability: str
    kind: str  # "absolute" | "relative"
    value: int
    item_id: int
    model_config = {"from_attributes": True}


def _resolve_ability_effective(ability_obj: Any, equipped_items: list[Any]) -> dict:
    """Build response payload for a single AbilityScore given equipped items.

    Imports stats lazily to avoid circular imports.
    """
    from core.game.stats import effective_ability_score

    base_value = ability_obj.value
    effective, applied = effective_ability_score(
        ability_obj.name,
        base_value,
        equipped_items,
    )
    return {
        "id": ability_obj.id,
        "name": ability_obj.name,
        "value": effective,
        "base_value": base_value,
        "modifier": (effective - 10) // 2,
        "modifiers_applied": [
            {
                "source": m.source,
                "ability": m.ability,
                "kind": m.kind,
                "value": m.value,
                "item_id": m.item_id,
            }
            for m in applied
        ],
    }


class AbilityScoreRead(BaseModel):
    id: int
    name: str
    value: int           # effective value (after equipped-item modifiers)
    base_value: int      # raw value stored on AbilityScore row
    modifier: int        # derived from effective value
    modifiers_applied: list[AppliedModifierRead] = []

    model_config = {"from_attributes": True}


class AbilityScoreUpdate(BaseModel):
    value: int  # 1–30


# ---------------------------------------------------------------------------
# CharacterClass
# ---------------------------------------------------------------------------

class CharacterClassRead(BaseModel):
    id: int
    class_name: str
    level: int
    subclass: Optional[str] = None
    subclass_key: Optional[str] = None
    options: dict[str, list[str]] = Field(default_factory=dict)
    spellcasting_ability: Optional[str] = None
    hit_die: Optional[int] = None
    hit_dice_used: int = 0

    @field_validator("options", mode="before")
    @classmethod
    def _options(cls, v):
        return v or {}

    model_config = {"from_attributes": True}


def _blank_to_none(v: Optional[str]) -> Optional[str]:
    return (v.strip() or None) if isinstance(v, str) else v


class CharacterClassCreate(BaseModel):
    class_name: str
    level: int = 1
    subclass: Optional[str] = None
    spellcasting_ability: Optional[str] = None
    hit_die: Optional[int] = None
    # Abilità scelte fra quelle della classe (vedi GET /rules/proficiencies); validate nel router.
    skill_choices: Optional[list[str]] = None

    _subclass_blank = field_validator("subclass")(_blank_to_none)


class CharacterClassUpdate(BaseModel):
    level: Optional[int] = None
    subclass: Optional[str] = None
    spellcasting_ability: Optional[str] = None
    hit_die: Optional[int] = None
    hit_dice_used: Optional[int] = None
    hp_rolls: Optional[list[int]] = None  # one die roll per gained level (not a column)

    _subclass_blank = field_validator("subclass")(_blank_to_none)


class ClassLevelEntry(BaseModel):
    """One (class_id, level) pair for the distribute endpoint."""
    class_id: int
    level: int = Field(ge=1, le=20)


class ClassDistribute(BaseModel):
    """Atomic redistribution of class levels for a character.

    The body must cover every existing class on the character; the sum of
    `level` values must equal the character's XP-derived total level.
    """
    classes: list[ClassLevelEntry]
    # One die roll per gained level, in body order (each 1..hit_die). Used when
    # settings.hp_mode == "rolled"; omitted -> fixed value.
    hp_rolls: Optional[list[int]] = None


# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------

class CurrencyRead(BaseModel):
    id: int
    copper: int = 0
    silver: int = 0
    electrum: int = 0
    gold: int = 0
    platinum: int = 0

    model_config = {"from_attributes": True}


class CurrencyUpdate(BaseModel):
    copper: Optional[int] = None
    silver: Optional[int] = None
    electrum: Optional[int] = None
    gold: Optional[int] = None
    platinum: Optional[int] = None


class CurrencyConvert(BaseModel):
    source: str   # "copper" | "silver" | "electrum" | "gold" | "platinum"
    target: str
    amount: int


# ---------------------------------------------------------------------------
# Ability (special features)
# ---------------------------------------------------------------------------

class AbilityRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    max_uses: Optional[int] = None
    uses: Optional[int] = None
    is_passive: bool = False
    is_active: bool = False
    restoration_type: str = "none"
    source_class_id: Optional[int] = None
    is_class_feature: bool = False
    feature_key: Optional[str] = None
    action_type: Optional[str] = None
    # Il privilegio a catalogo ha un effetto reale al «Usa» (POST /features/{key}/use); popolato da build_character_response
    has_on_use: bool = False
    # Il «Usa» dà lo stato a un altro personaggio della serata (Ispirazione Bardica): il client chiede a chi (R38)
    gives_to_ally: bool = False
    # Valori della scelta «mode» rivolti a un'altra creatura (Imposizione delle Mani): il client chiede a chi
    ally_modes: list[str] = []
    # Quante creature della serata possono ricevere i PF temporanei del «Usa» (con gives_to_ally)
    ally_max: int = 1
    # Pool (Imposizione delle Mani): il giocatore sceglie quanti usi spendere, al massimo `max_amount` (None: gli usi rimasti)
    choose_amount: bool = False
    max_amount: Optional[int] = None
    min_amount: int = 1  # usi minimi da spendere insieme (Frusta d'Acqua: 2 ki)
    # Scelte sì/no da fare all'uso (Frenesia all'ingresso in ira): `[{key, label: {it, en}}]`, già filtrate per questo personaggio
    use_toggles: list[dict[str, Any]] = []
    use_choices: list[dict[str, Any]] = []
    # Testi liberi da scrivere all'uso (nome di un'identità, di un incantesimo rubato): `[{key, label, max_len, optional}]`
    use_texts: list[dict[str, Any]] = []
    # Il «Usa» toglie condizioni nel foglio comune (Task 48): stessa forma di ``SpellRead.removal``, già filtrata per questo personaggio
    removal: Optional[dict[str, Any]] = None
    use_panel: Optional[str] = None
    # L'uso ora non costa nulla e si può fare (prolungare l'Ira 2024): il «Usa» resta acceso anche a 0 usi; lo decide il server
    free_use: bool = False
    # Usi che restano al privilegio di cui questo spende gli usi (Preservare Vita: la riserva di Incanalare Divinità)
    spends_left: Optional[int] = None
    # Riga di riserva a catalogo (Incanalare Divinita): solo contatore, l'uso passa dai privilegi che la spendono
    is_pool: bool = False
    # CD dei tiri salvezza del privilegio (ki del Monaco: 8 + competenza + Saggezza), calcolata dal server
    dc: Optional[int] = None
    # Homebrew rule notifications surfaced when an ability_used event fired
    # (PATCH /abilities/{id} with a decremented `uses`). Omitted/None on
    # POST/list responses to match CharacterFull's contract (Phase 2 pattern).
    homebrew_notifications: Optional[list[dict]] = None

    model_config = {"from_attributes": True}


class AbilityCreate(BaseModel):
    name: str
    description: Optional[str] = None
    max_uses: Optional[int] = None
    uses: Optional[int] = None
    is_passive: bool = False
    is_active: bool = False
    restoration_type: str = "none"
    action_type: Optional[ActionType] = None

    _check_restoration = field_validator("restoration_type")(_validate_restoration_type)


class AbilityUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    max_uses: Optional[int] = None
    uses: Optional[int] = None
    is_passive: Optional[bool] = None
    is_active: Optional[bool] = None
    restoration_type: Optional[str] = None
    action_type: Optional[ActionType] = None

    _check_restoration = field_validator("restoration_type")(_validate_restoration_type)


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------

class MapRead(BaseModel):
    id: int
    zone_name: str
    file_id: str
    file_type: str
    local_file_path: Optional[str] = None
    position: int = 0
    size_bytes: int = 0

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# HP operations
# ---------------------------------------------------------------------------

class RollOptionsBody(BaseModel):
    """Conferma al tiro: opzioni scelte e, per chiave, gli input (``{"slot_level": 2}``). Il server riconvalida."""
    options: list[str] = Field(default_factory=list, max_length=30)
    option_inputs: dict[str, dict[str, int]] = Field(default_factory=dict)


class OptionResult(BaseModel):
    """Cosa hanno prodotto le opzioni confermate. Assente nelle risposte senza opzioni."""
    keys: list[str] = []
    extra_rolls: list[int] = []
    extra_total: int = 0  # dadi + eventuale fisso nell'espressione dei dadi
    extra_types: list[str | None] = []  # tipo di danno di ogni valore di ``extra_rolls`` (assente se nessun dado ne ha uno)
    separate_type: str | None = None  # tipo del danno a parte
    separate_rolls: list[int] = []  # danno a parte, fuori dal totale
    separate_total: int = 0
    bonus: int = 0
    multiplier: float = 1
    spent: list[str] = []
    effects: list[dict[str, str]] = []  # {"it", "en"}: esiti da mostrare (CD, durata)
    targets: list[str] = []  # opzioni con un effetto da applicare a un combattente (target-effects)
    second_die: int | None = None  # secondo tiro per colpire di un'opzione (Cleave)
    second_total: int | None = None
    damage_before: int | None = None  # solo danno subito
    damage_after: int | None = None
    hp_lost: int | None = None  # danno tenuto a 1 PF: i PF persi davvero


def absent_when_none() -> Any:
    """Campo che sparisce dal JSON quando vale None: chi non usa le opzioni vede la risposta di prima."""
    return Field(default=None, exclude_if=lambda v: v is None)


class HPOp(str, Enum):
    DAMAGE = "damage"
    HEAL = "heal"
    SET_MAX = "set_max"
    SET_CURRENT = "set_current"
    SET_TEMP = "set_temp"


class HPUpdate(RollOptionsBody):
    op: HPOp
    value: int
    was_critical_hit: bool = False
    # Override esplicito: `value` è già il danno applicato dal client (annotazione),
    # tranne "immune" che azzera. Senza override il server applica le resistenze
    # del personaggio al `damage_type`.
    damage_modifier: Literal["half", "double", "half_double", "none", "immune"] | None = None
    raw_value: int | None = Field(None, ge=0)
    damage_type: str | None = Field(None, max_length=40)
    # Chi porta a 0 PF con un attacco in mischia può tramortire invece di abbattere (2014 stabile a 0, 2024 a 1 PF).
    knock_out: bool = False


class HPUndoRequest(BaseModel):
    op_id: str


class MemorizeSpellRequest(BaseModel):
    out: int  # id dell'incantesimo preparato che si lascia
    into: int  # id dell'incantesimo del libro che si prepara al suo posto


class RestRequest(BaseModel):
    rest_type: str  # "long" | "short"
    interrupted: bool = False
    ate_and_drank: bool = True  # 2014: senza cibo e acqua il riposo lungo non riduce la spossatezza
    confirm_early: bool = False  # riposo lungo prima del limite di 24 h (2014) / 16 h (2024)
    # Recupero Naturale (Druido 2014): livello dello slot -> quanti ne recupera durante un riposo breve
    natural_recovery: Optional[dict[int, int]] = None
    arcane_recovery: Optional[dict[int, int]] = None  # Recupero Arcano del Mago: stessi controlli
    reopen_tome: bool = False  # Patto del Tomo: i trucchetti e i rituali del Libro delle Ombre tornano da scegliere
    memorize_spell: Optional[MemorizeSpellRequest] = None  # Memorizzare Incantesimo (Mago 2024, 5°): scambio al riposo breve
    sorcerous_restoration: Optional[int] = None  # Ripristino Stregonesco (Stregone 2024): punti stregoneria da recuperare
    temp_hp_allies: list[int] = []  # Resilienza Celestiale: PG della serata che ricevono i PF temporanei a fine riposo (fino a 5)


class ItemChargePreview(BaseModel):
    name: str
    gain: Optional[int] = None  # note when known (recharge to max)
    formula: Optional[str] = None  # dice recharge, e.g. "1d6+1"
    full: bool = False  # recharges to max


class RestPreview(BaseModel):
    """Cosa recupererebbe un riposo (nessuna scrittura)."""
    hp_gain: int = 0
    hit_dice_regain: dict[int, int] = {}  # class_id -> dadi vita
    slots: dict[int, int] = {}  # livello -> slot (non patto) recuperati
    pact_slots: int = 0
    abilities: list[str] = []
    homebrew_resources: list[str] = []
    item_charges: list[ItemChargePreview] = []
    exhaustion_change: int = 0
    ends_concentration: bool = False


class DeathSaveAction(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    RESET = "reset"
    STABILIZE = "stabilize"
    ROLL = "roll"


RollMode = Literal["normal", "advantage", "disadvantage"]
D20Dice = Annotated[list[Annotated[int, Field(ge=1, le=20)]], Field(max_length=2)]


class DeathSaveUpdate(BaseModel):
    action: DeathSaveAction


class DeathSaveRollResult(BaseModel):
    die: int
    dice: list[int] = []
    mode: RollMode = "normal"
    mode_applied: RollMode = "normal"
    notes: list[str] = []
    outcome: str  # "nat20" | "nat1" | "success" | "failure" | "revived" (Vendetta Ardente: nessun tiro)
    successes: int
    failures: int
    stable: bool
    revived: bool = False
    current_hp: int
    option_result: OptionResult | None = absent_when_none()


# ---------------------------------------------------------------------------
# Dice
# ---------------------------------------------------------------------------

class DiceResultEntry(BaseModel):
    kind: Literal["d4", "d6", "d8", "d10", "d12", "d20"]
    value: int


class DiceResultRequest(BaseModel):
    rolls: list[DiceResultEntry] = Field(min_length=1, max_length=200)
    label: str | None = Field(default=None, max_length=120)
    modifier: int = 0
    notation: str | None = Field(default=None, max_length=80)
    with_inspiration: bool = False
    source: Literal["manual", "weapon", "skill", "save", "spell", "init"] | None = None
    # Optional client-supplied total override. Used by stat-rolls (4d6kh3) where the
    # displayed total is the sum of the kept dice, not all rolls.
    total: int | None = None
    # advantage/disadvantage: rolls must be exactly two d20; total computed server-side.
    mode: RollMode = "normal"


class DiceRollResult(BaseModel):
    notation: str
    rolls: list[int]
    total: int
    modifier: int = 0
    timestamp: str | None = None
    source: str | None = None
    label: str | None = None


# ---------------------------------------------------------------------------
# Generic roll result (skill check, saving throw, initiative…)
# ---------------------------------------------------------------------------

class RollResult(BaseModel):
    die: int = 20
    dice: list[int] = []
    mode: RollMode = "normal"
    # Modo finale dopo gli automatismi e perché: `condition:<slug>`, `armor:untrained`, `feature:<key>`.
    mode_applied: RollMode = "normal"
    notes: list[str] = []
    auto_fail: bool = False
    bonus: int
    total: int
    is_critical: bool = False
    is_fumble: bool = False
    description: str = ""
    option_result: OptionResult | None = absent_when_none()


class ZeroHpSaveResult(BaseModel):
    """TS automatico a 0 PF di un privilegio (Ira Implacabile): se riesce, il personaggio resta in piedi."""
    feature_key: str
    ability: str
    die: int
    bonus: int
    total: int
    dc: int
    success: bool
    hp: int = 0  # PF a cui torna se riesce


class D20RollSubmission(RollOptionsBody):
    """Optional client-supplied d20 value (from 3D physics face detection)."""
    die: Optional[int] = Field(default=None, ge=1, le=20)
    with_inspiration: bool = False
    mode: RollMode = "normal"
    dice: Optional[D20Dice] = None


class ConcentrationSaveResult(RollResult):
    """Result of a concentration saving throw.

    Extends RollResult with the DC rolled against, the binary outcome,
    and whether the character lost concentration as a result.
    """
    dc: int
    success: bool
    lost_concentration: bool


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

class HistoryEntryRead(BaseModel):
    id: int
    timestamp: str
    event_type: str
    description: str

    model_config = {"from_attributes": True}


class HistoryRetentionPreview(BaseModel):
    """Counts that would be purged under each retention mode.

    Lets the Settings UI show users what they're about to lose before
    they commit a retention mode change.
    """
    total: int
    events_keep: int
    days_window: int
    would_purge_events: int
    would_purge_days: int


# ---------------------------------------------------------------------------
# Consumable use result
# ---------------------------------------------------------------------------

class ConsumableUseResult(BaseModel):
    """Summary of what a single `POST .../items/{id}/use` applied."""
    heal_rolls: list[int] = []
    total_healed: int = 0
    conditions_added: list[str] = []
    conditions_removed: list[str] = []
