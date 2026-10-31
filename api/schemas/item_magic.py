"""Typed magic-item fields stored inside ``Item.item_metadata`` (validated on write)."""

from __future__ import annotations

import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

_ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
BonusTarget = Literal[
    "ac", "saves", *(f"save.{a}" for a in _ABILITIES),
    "attack", "damage", "spell_attack", "spell_dc", "speed", "initiative",
]


class ItemBonus(BaseModel):
    target: BonusTarget
    value: int = Field(ge=-10, le=10)


_AMOUNT_RE = re.compile(r"^\d{1,2}d\d{1,3}([+-]\d{1,3})?$", re.IGNORECASE)


class ItemCharges(BaseModel):
    model_config = ConfigDict(extra="allow")
    max: int = Field(ge=1, le=100)
    current: int = Field(ge=0)
    recharge: Literal["long_rest", "short_rest", "dawn", "none"] = "none"
    recharge_amount: str = "all"  # "all" or dice notation like "1d6+1"

    @model_validator(mode="after")
    def _check(self) -> "ItemCharges":
        if self.current > self.max:
            raise ValueError("current must be <= max")
        self.recharge_amount = self.recharge_amount.strip()
        if self.recharge_amount != "all" and not _AMOUNT_RE.match(self.recharge_amount):
            raise ValueError("recharge_amount must be 'all' or dice notation")
        return self


class GrantedSpell(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str = Field(min_length=1, max_length=200)
    level: int = Field(ge=0, le=9)
    charges_cost: int = Field(default=0, ge=0, le=100)
    srd_index: Optional[str] = None
    save_dc: Optional[int] = None
    attack_bonus: Optional[int] = None
    is_concentration: bool = False
    duration: Optional[str] = None


class MagicFields(BaseModel):
    model_config = ConfigDict(extra="allow")
    rarity: Optional[Literal["common", "uncommon", "rare", "very_rare", "legendary", "artifact"]] = None
    is_magic: bool = False
    cost_gp: Optional[float] = Field(default=None, ge=0)
    requires_attunement: bool = False
    attuned: bool = False
    bonuses: list[ItemBonus] = Field(default_factory=list)
    charges: Optional[ItemCharges] = None
    granted_spells: list[GrantedSpell] = Field(default_factory=list)


_KNOWN = tuple(MagicFields.model_fields)


def validate_magic_meta(v: dict[str, Any]) -> None:
    """Validate only the magic keys present; unknown keys pass through untouched."""
    subset = {k: v[k] for k in _KNOWN if k in v and v[k] is not None}
    if not subset:
        return
    m = MagicFields.model_validate(subset)  # ValidationError is a ValueError
    if m.attuned and not m.requires_attunement:
        raise ValueError("attuned requires requires_attunement")
    cap = m.charges.max if m.charges else 0
    if any(g.charges_cost > cap for g in m.granted_spells):
        raise ValueError("charges_cost exceeds charges.max")
