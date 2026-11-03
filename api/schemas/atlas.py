from __future__ import annotations

from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, StringConstraints, model_validator

from api.services.atlas import COLORS, ICONS


MarkerName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class AtlasMapRead(BaseModel):
    id: int
    name: str
    revealed: bool
    revealed_at: Optional[str]
    updated_at: str
    marker_count: int


class AtlasMapRename(BaseModel):
    name: MarkerName


class AtlasMapDeleted(BaseModel):
    deleted_markers: int


Visibility = Literal["private", "public"]
Coord = Annotated[float, Field(ge=0, le=1)]


class MarkerTypeRead(BaseModel):
    id: Optional[int]  # None for builtin types
    key: Optional[str]
    name: str  # builtin: the key itself, translated by the client
    icon: str
    color: str
    builtin: bool
    can_delete: bool


class MarkerTypeCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    icon: str
    color: str

    @model_validator(mode="after")
    def _known(self) -> "MarkerTypeCreate":
        if self.icon not in ICONS or self.color not in COLORS:
            raise ValueError("unknown icon or color")
        return self


class MarkerRead(BaseModel):
    id: int
    map_id: int
    name: str
    description: str
    x: float
    y: float
    visibility: Visibility
    type: MarkerTypeRead
    author_role: Literal["gm", "player"]
    author_name: Optional[str]
    mine: bool
    link_map_id: Optional[int]
    can_edit: bool
    can_delete: bool
    updated_at: str


class MarkerCreate(BaseModel):
    name: MarkerName
    description: str = Field(default="", max_length=2000)
    x: Coord
    y: Coord
    type_key: Optional[str] = None
    custom_type_id: Optional[int] = None
    visibility: Visibility = "private"
    link_map_id: Optional[int] = None

    @model_validator(mode="after")
    def _one_type(self) -> "MarkerCreate":
        if (self.type_key is None) == (self.custom_type_id is None):
            raise ValueError("exactly one of type_key, custom_type_id")
        return self


class MarkerUpdate(BaseModel):
    name: Optional[MarkerName] = None
    description: Optional[str] = Field(default=None, max_length=2000)
    x: Optional[Coord] = None
    y: Optional[Coord] = None
    type_key: Optional[str] = None
    custom_type_id: Optional[int] = None
    link_map_id: Optional[int] = None  # explicit null clears the link

    @model_validator(mode="after")
    def _one_type(self) -> "MarkerUpdate":
        touched = {"type_key", "custom_type_id"} & self.model_fields_set
        if touched and (self.type_key is None) == (self.custom_type_id is None):
            raise ValueError("exactly one of type_key, custom_type_id")
        return self


class MarkerVisibility(BaseModel):
    visibility: Visibility
