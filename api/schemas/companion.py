"""Companions (familiars, companions, mounts, summons, wild shape forms)."""
from __future__ import annotations

import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.rules.companions import COMPANION_FEATURES, MAX_HIT_DICE, MAX_MULTIATTACK
from api.schemas.common import ConcentrationSaveResult, D20Dice, OptionResult, RollMode, RollOptionsBody, absent_when_none

CompanionKind = Literal["familiar", "companion", "mount", "summon", "wild_shape"]
DICE_RE = re.compile(r"^(\d+)d(\d+)([+-]\d+)?$", re.IGNORECASE)
MAX_COMPANIONS = 30


def validate_statblock(sb: Any) -> dict:
    """Minimal shape check: dict, actions list with typed attack_bonus / damage_dice."""
    if not isinstance(sb, dict):
        raise ValueError("statblock must be an object")
    actions = sb.get("actions", [])
    if not isinstance(actions, list):
        raise ValueError("actions must be a list")
    for a in actions:
        if not isinstance(a, dict):
            raise ValueError("each action must be an object")
        ab = a.get("attack_bonus")
        if ab is not None and (isinstance(ab, bool) or not isinstance(ab, int)):
            raise ValueError("attack_bonus must be an integer")
        dd = a.get("damage_dice")
        if dd is not None and not (isinstance(dd, str) and DICE_RE.match(dd.strip())):
            raise ValueError("damage_dice must be dice notation")
        dt = a.get("damage_type")
        if dt is not None and not isinstance(dt, str):
            raise ValueError("damage_type must be a string")
    # numeri che il server legge per la bestia del ranger (ordini, Dadi Vita): mai fidarsi del tipo
    hd = sb.get("hit_dice")
    if hd is not None:
        m = DICE_RE.match(hd.strip()) if isinstance(hd, str) else None
        if m is None or not 1 <= int(m.group(1)) <= MAX_HIT_DICE or not 2 <= int(m.group(2)) <= 100:
            raise ValueError("hit_dice must be NdM")
    for key, high in (("hit_dice_spent", MAX_HIT_DICE), ("multiattack", MAX_MULTIATTACK)):
        v = sb.get(key)
        if v is not None and (isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= high):
            raise ValueError(f"{key} must be an integer between 0 and {high}")
    return sb


class CompanionCreate(BaseModel):
    kind: CompanionKind
    name: str = Field(min_length=1, max_length=100)
    srd_index: Optional[str] = Field(default=None, max_length=80)
    statblock: dict = Field(default_factory=dict)
    max_hp: int = Field(default=0, ge=0, le=100_000)
    current_hp: Optional[int] = Field(default=None, ge=0, le=100_000)
    temp_hp: int = Field(default=0, ge=0, le=100_000)
    armor_class: int = Field(default=10, ge=0, le=100)
    notes: Optional[str] = Field(default=None, max_length=5000)
    is_active: bool = False
    feature_key: Optional[str] = Field(default=None, max_length=80)  # compagno di privilegio: PF e bonus dal livello

    @field_validator("statblock", mode="before")
    @classmethod
    def _sb(cls, v):
        return validate_statblock(v)

    @field_validator("feature_key")
    @classmethod
    def _feature(cls, v):
        if v is not None and v not in COMPANION_FEATURES:
            raise ValueError("unknown feature_key")
        return v


class CompanionUpdate(BaseModel):
    kind: Optional[CompanionKind] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    srd_index: Optional[str] = Field(default=None, max_length=80)
    statblock: Optional[dict] = None
    max_hp: Optional[int] = Field(default=None, ge=0, le=100_000)
    current_hp: Optional[int] = Field(default=None, ge=0, le=100_000)
    temp_hp: Optional[int] = Field(default=None, ge=0, le=100_000)
    armor_class: Optional[int] = Field(default=None, ge=0, le=100)
    notes: Optional[str] = Field(default=None, max_length=5000)
    is_active: Optional[bool] = None

    @field_validator("statblock", mode="before")
    @classmethod
    def _sb(cls, v):
        return None if v is None else validate_statblock(v)


class CompanionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    character_id: int
    kind: str
    name: str
    srd_index: Optional[str] = None
    statblock: dict
    max_hp: int
    current_hp: int
    temp_hp: int
    armor_class: int
    notes: Optional[str] = None
    is_active: bool
    created_at: str
    feature_key: Optional[str] = None
    attack_bonus_extra: int = 0  # compagno di privilegio: si somma al bonus dello statblock
    damage_bonus_extra: int = 0
    down: bool = False  # set by the hp endpoint: 0 HP means "a terra" (no death saves)
    concentration_save: Optional[ConcentrationSaveResult] = None  # danno alla forma attiva: il TS del personaggio


class CompanionActivate(BaseModel):
    force: bool = False  # activate even with no Wild Shape uses left


class WildHealRequest(BaseModel):
    slot_level: int = Field(ge=1, le=9)  # Forma Selvatica da Combattimento: il livello dello slot da spendere


class WildHealResult(BaseModel):
    companion: CompanionRead
    slot_level: int
    rolls: list[int]
    healed: int  # PF che la forma ha recuperato davvero (il massimo della forma non si supera)


class CompanionHp(BaseModel):
    op: Literal["damage", "heal", "set_temp"]
    value: int = Field(ge=0, le=100_000)


class CompanionAttack(RollOptionsBody):
    action_index: int = Field(ge=0)
    reaction: bool = False  # la reazione della bestia del ranger (attacco di opportunità) non ha bisogno di un ordine
    mode: RollMode = "normal"
    dice: D20Dice | None = None
    damage_rolls: Optional[list[int]] = Field(default=None, max_length=100)


class CompanionCommand(BaseModel):
    """Ordine del ranger alla bestia compagna: con l'azione, o con l'azione bonus (Addestramento Straordinario)."""
    command: Literal["attack", "help", "disengage", "dash", "dodge"]
    bonus: bool = False


class CompanionCommandResult(BaseModel):
    command: str
    bonus: bool
    attacks_left: int  # attacchi che la bestia può ancora fare in questo turno


class HitDiceRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=20)


class HitDiceResult(BaseModel):
    companion: CompanionRead
    rolls: list[int]
    healed: int  # PF che la bestia ha recuperato davvero (il massimo non si supera)
    hit_dice_left: int


class CompanionAttackResult(BaseModel):
    to_hit_die: int
    to_hit_bonus: int
    to_hit_total: int
    dice: list[int]
    mode: RollMode
    notes: list[str] = []
    is_critical: bool
    damage_rolls: list[int]
    damage_total: int
    damage_type: Optional[str] = None
    is_magical: bool = False  # Colpo Primordiale: l'attacco in forma bestiale conta come magico per resistenze e immunità
    option_result: OptionResult | None = absent_when_none()
    reroll_dice: list[list[int]] | None = absent_when_none()  # [lati, valore] dei dadi ritirabili, con l'indice del server
