from pydantic import BaseModel

from api.schemas.common import (
    ConcentrationSaveResult,
    D20Dice,
    DeathSaveRollResult,
    RollMode,
    RollOptionsBody,
    RollResult,
    absent_when_none,
)
from api.schemas.condition_effects import PendingSaveRead
from api.schemas.item import WeaponAttackResult


class SubclassRead(BaseModel):
    key: str
    name: dict[str, str]
    choice_level: int


class ProficiencyGrantRead(BaseModel):
    armor: list[str]
    weapons: list[str]
    tools: list[str]
    saves: list[str]
    skills_from: list[str]
    skills_count: int
    languages: list[str]


class RollOptionCost(BaseModel):
    feature_key: str | None = None
    amount: int = 1
    spell_slot_min: int | None = None


class RollOptionSlot(BaseModel):
    level: int
    available: int
    dice: str | None = None


class RollOptionRead(BaseModel):
    key: str
    phase: str
    label: str
    source: str
    dice: str | None = None
    bonus: int | None = None
    mode: str | None = None
    multiplier: float | None = None
    once_per_turn: bool = False
    slot: str | None = None
    needs: str | None = None
    group: str | None = None
    dice_cost: int = 0
    requires_input: str | None = None
    after: str | None = None
    pay_if_success: bool = False
    saved_dice: list[int] = []
    reroll_limit: int | None = None
    keep_rolled: bool = False
    input_options: list[RollOptionSlot] = []
    auto_fail: bool = False
    cost: RollOptionCost | None = None
    ranged_unarmed: bool | None = absent_when_none()  # l'attacco è un lancio a distanza senz'armi: mai con l'arma impugnata
    offered_on_damage: bool | None = absent_when_none()  # la propone l'app dopo un danno subito; assente: sì se ha lo slot reazione


class LastRollBody(RollOptionsBody):
    """``dice``: facce dei dadi 3D per un ritiro; senza, tira il server."""
    mode: RollMode = "normal"
    dice: D20Dice | None = None


class LastRollResult(RollResult):
    """Il tiro aggiornato; ``attack`` per un attacco in sospeso, ``passed``/``save`` per un TS in sospeso."""
    forced_hit: bool | None = absent_when_none()
    refundable: list[str] | None = absent_when_none()  # opzioni da rimborsare se il giocatore dichiara il fallimento
    passed: bool | None = absent_when_none()
    condition_removed: bool | None = absent_when_none()
    save: PendingSaveRead | None = absent_when_none()
    attack: WeaponAttackResult | None = absent_when_none()
    death: DeathSaveRollResult | None = absent_when_none()
    concentration: ConcentrationSaveResult | None = absent_when_none()


class LastRollRefund(BaseModel):
    """``succeeded``: il giocatore dichiara il tiro riuscito, il pagamento resta e la domanda si chiude."""
    succeeded: bool = False


class TargetEffectRead(BaseModel):
    """L'effetto tenuto dal server alla conferma dell'opzione (``core.rules.types.TargetEffect``)."""
    condition: str | None = None
    save_ability: str | None = None
    save_dc: int | None = None
    rounds: int | None = None
    ends_at: dict | None = None
    on_failure_only: bool = True
    damage_dice: str | None = None
    extends: bool = False
    immune_on_success: bool = False


class TargetCandidate(BaseModel):
    id: int
    name: str
    kind: str
    immune: bool = False  # ha superato questo effetto: fino al prossimo riposo lungo non si può colpire di nuovo


class TargetEffectPreview(BaseModel):
    """Effetto e combattenti a cui applicarlo (vuoti fuori da un incontro attivo)."""
    result: TargetEffectRead
    combatants: list[TargetCandidate] = []


class TargetEffectBody(BaseModel):
    effect_key: str
    combatant_id: int | None = None  # senza incontro non serve


class TargetEffectResult(BaseModel):
    applied: bool
    result: TargetEffectRead
    target_name: str | None = None
    pending_save_id: int | None = None
