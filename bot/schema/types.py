"""Data types for the introspected GraphQL schema."""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field


@dataclass
class FieldInfo:
    """A single field inside a GraphQL type."""

    name: str
    type_name: str  # resolved base type, e.g. "String", "Class", "AnyEquipment"
    type_kind: str  # SCALAR | OBJECT | UNION | ENUM | INTERFACE
    is_list: bool = False
    is_non_null: bool = False

    @property
    def is_scalar(self) -> bool:
        return self.type_kind in ("SCALAR", "ENUM")

    @property
    def is_object(self) -> bool:
        return self.type_kind == "OBJECT"

    @property
    def is_union(self) -> bool:
        return self.type_kind == "UNION"


@dataclass
class TypeInfo:
    """Metadata for a single GraphQL type (OBJECT, UNION, …)."""

    name: str
    kind: str  # OBJECT | UNION | SCALAR | ENUM | …
    fields: dict[str, FieldInfo] = dc_field(default_factory=dict)
    possible_types: list[str] = dc_field(default_factory=list)  # union members

    # Root-query mapping (populated by the registry)
    list_query_field: str | None = None   # e.g. "classes", "spells"
    detail_query_field: str | None = None  # e.g. "class", "spell"
    has_pagination: bool = False            # True when list field has skip/limit

    # Navigable sub-entity fields (computed by the registry)
    navigable_fields: list[str] = dc_field(default_factory=list)

    def has_field(self, name: str) -> bool:
        return name in self.fields


@dataclass(frozen=True)
class MenuCategory:
    """Static configuration for a top-level menu button."""

    type_name: str  # GraphQL type name: "Spell", "Class", …
    label: str      # Display label: "Spells", "Classes", …
    emoji: str      # Button emoji: 🔮, ⚔️, …
