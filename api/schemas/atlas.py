from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AtlasMapRead(BaseModel):
    id: int
    name: str
    revealed: bool
    revealed_at: Optional[str]
    updated_at: str
    marker_count: int


class AtlasMapRename(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class AtlasMapDeleted(BaseModel):
    deleted_markers: int
