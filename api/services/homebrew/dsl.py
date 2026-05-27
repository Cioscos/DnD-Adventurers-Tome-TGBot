"""Pydantic strict schemas for the Homebrew DSL v1.

See design spec: docs/superpowers/specs/2026-05-27-homebrew-rules-engine-design.md
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FilterOp(str, Enum):
    EQ = "eq"
    NEQ = "neq"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
    IN = "in"
    HAS_PROPERTY = "has_property"


class Filter(BaseModel):
    """A single boolean condition. Filters in a list are ANDed."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    path: str = Field(..., min_length=1, max_length=200)
    op: FilterOp
    value: Any = None


_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,59}$")


def _validate_key(v: str) -> str:
    if not _KEY_PATTERN.match(v):
        raise ValueError(
            f"Key '{v}' must match {_KEY_PATTERN.pattern} (lowercase snake_case, max 60 chars)"
        )
    return v


PropertyType = Literal["enum", "number", "boolean", "text"]


class Property(BaseModel):
    """A custom property attached to subjects matching the rule."""
    model_config = ConfigDict(extra="forbid")

    key: str
    type: PropertyType
    values: Optional[list[str]] = None
    default: Any
    label_i18n: dict[str, str]
    value_labels_i18n: Optional[dict[str, dict[str, str]]] = None

    @field_validator("key")
    @classmethod
    def _key_format(cls, v: str) -> str:
        return _validate_key(v)

    @field_validator("label_i18n")
    @classmethod
    def _label_languages(cls, v: dict[str, str]) -> dict[str, str]:
        missing = {"it", "en"} - set(v.keys())
        if missing:
            raise ValueError(f"label_i18n missing languages: {missing}")
        return v

    @model_validator(mode="after")
    def _enum_consistency(self) -> "Property":
        if self.type == "enum":
            if not self.values:
                raise ValueError("type='enum' requires non-empty 'values' list")
            if self.default not in self.values:
                raise ValueError(f"default '{self.default}' must be in values {self.values}")
        return self
