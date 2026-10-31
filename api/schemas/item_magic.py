"""Typed magic-item fields stored inside ``Item.item_metadata`` (validated on write)."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

_ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
BonusTarget = Literal[
    "ac", "saves", *(f"save.{a}" for a in _ABILITIES),
    "attack", "damage", "spell_attack", "spell_dc", "speed", "initiative",
]


class ItemBonus(BaseModel):
    target: BonusTarget
    value: int = Field(ge=-10, le=10)


class ItemCharges(BaseModel):
    """Minimal shape; Task 14 extends it."""

    model_config = ConfigDict(extra="allow")
    max: int = Field(ge=0)
    current: int = Field(ge=0)
    recharge: Literal["long_rest", "short_rest", "dawn", "none"] = "none"
    recharge_amount: str = "all"


class GrantedSpell(BaseModel):
    """Minimal shape; Task 14 extends it."""

    model_config = ConfigDict(extra="allow")


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
