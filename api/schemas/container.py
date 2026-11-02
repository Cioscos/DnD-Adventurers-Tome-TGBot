"""Container fields stored under ``Item.item_metadata["container"]`` (validated on write)."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.game.containers import COINS

Coin = Annotated[int, Field(ge=0, le=10_000_000)]


class ContainerCoins(BaseModel):
    model_config = ConfigDict(extra="forbid")
    copper: Coin = 0
    silver: Coin = 0
    electrum: Coin = 0
    gold: Coin = 0
    platinum: Coin = 0


class ContainerFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capacity_lb: Optional[float] = Field(default=None, ge=0, le=100_000)
    counts_weight: bool = True
    quick_access: bool = False
    coins: ContainerCoins = Field(default_factory=ContainerCoins)


assert tuple(ContainerCoins.model_fields) == COINS


class ItemMoveRequest(BaseModel):
    item_ids: list[int] = Field(min_length=1, max_length=200)
    container_id: Optional[int] = None
    quantity: Optional[int] = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _check(self):
        if len(set(self.item_ids)) != len(self.item_ids):
            raise ValueError("item_ids must be unique")
        if self.quantity is not None and len(self.item_ids) != 1:
            raise ValueError("quantity requires a single item")
        return self


class ContainerStatsRead(BaseModel):
    contents_weight: float
    items_count: int
    containers_count: int
    over_capacity: bool


class CoinLocationRead(BaseModel):
    container_id: Optional[int] = None
    name: Optional[str] = None
    coins: dict[str, int]


def validate_container_meta(v: dict[str, Any]) -> None:
    """Validate the ``container`` key if present; other keys pass through untouched."""
    if v.get("container") is not None:
        ContainerFields.model_validate(v["container"])  # ValidationError is a ValueError
