"""Pydantic schemas exposed by the homebrew router."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.services.homebrew.dsl import RuleDSL
from api.services.homebrew.types import Severity


class HomebrewRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    dsl: dict
    enabled: bool = True
    template_id: Optional[str] = None

    @field_validator("dsl")
    @classmethod
    def _dsl_valid(cls, v: dict) -> dict:
        # Strict validation — raises ValidationError if shape is wrong.
        RuleDSL.model_validate(v)
        return v


class HomebrewRuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    dsl: Optional[dict] = None
    enabled: Optional[bool] = None

    @field_validator("dsl")
    @classmethod
    def _dsl_valid(cls, v):
        if v is not None:
            RuleDSL.model_validate(v)
        return v


class HomebrewRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    character_id: int
    name: str
    description: Optional[str] = None
    enabled: bool
    dsl: dict
    version: int
    template_id: Optional[str] = None
    created_at: str
    updated_at: str


class HomebrewResourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    rule_id: int
    character_id: int
    key: str
    name: str
    current: int
    max: int
    restoration_type: str


class HomebrewResourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current: int = Field(..., ge=0)


class TemplateRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    description: str
    icon: str


class TemplateDetailRead(TemplateRead):
    dsl: dict


class NotificationRead(BaseModel):
    severity: Severity
    message: str
    rule_id: int | None = None
    rule_name: str | None = None


class RuleFiringResultRead(BaseModel):
    # history_entries are persisted server-side; not surfaced to clients.
    rule_id: int
    rule_name: str
    notifications: list[NotificationRead] = []
    errors: list[str] = []
