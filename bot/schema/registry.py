"""Schema registry — discovers and caches GraphQL schema metadata.

On startup the registry runs a single introspection query and builds a
mapping from type names to :class:`~bot.schema.types.TypeInfo` objects.
It also computes which fields are *navigable* (sub-entity lists the bot
can let users browse).
"""

from __future__ import annotations

import logging
from typing import Any

from bot.api.client import dnd_client
from bot.api.introspection import (
    INTROSPECTION_QUERY,
    parse_introspection,
    resolve_type,
)
from bot.schema.types import MenuCategory, TypeInfo

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Top-level menu — order determines button layout in /start.
# ------------------------------------------------------------------
MENU_CATEGORIES: list[MenuCategory] = [
    MenuCategory("Spell", "Spells", "🔮"),
    MenuCategory("Monster", "Monsters", "🐉"),
    MenuCategory("Class", "Classes", "⚔️"),
    MenuCategory("Race", "Races", "🧝"),
    MenuCategory("AnyEquipment", "Equipment", "🎒"),
    MenuCategory("Condition", "Conditions", "🩹"),
    MenuCategory("MagicItem", "Magic Items", "✨"),
    MenuCategory("Rule", "Rules", "📖"),
    MenuCategory("WeaponProperty", "Weapon Props", "🗡️"),
]


class SchemaRegistry:
    """Singleton that holds introspected schema information."""

    def __init__(self) -> None:
        self._types: dict[str, TypeInfo] = {}
        self._initialized = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Run the introspection query and build the type map."""
        logger.info("Running GraphQL introspection…")
        data = await dnd_client.execute(INTROSPECTION_QUERY)
        schema = data.get("__schema", {})
        self._types, root_fields = parse_introspection(schema)

        self._map_root_queries(root_fields)
        self._compute_navigable_fields()

        self._initialized = True
        nav_count = sum(len(t.navigable_fields) for t in self._types.values())
        logger.info(
            "Schema loaded: %d types, %d navigable relationships",
            len(self._types),
            nav_count,
        )

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_type(self, name: str) -> TypeInfo | None:
        return self._types.get(name)

    def get_all_types(self) -> dict[str, TypeInfo]:
        return dict(self._types)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _map_root_queries(self, root_fields: list[dict[str, Any]]) -> None:
        """Link root query fields (``classes``, ``class``) to TypeInfos."""
        for field in root_fields:
            fname = field.get("name", "")
            if fname.startswith("__"):
                continue

            type_name, _kind, is_list, _ = resolve_type(field.get("type"))
            args = [a.get("name", "") for a in field.get("args") or []]

            ti = self._types.get(type_name)
            if ti is None:
                continue

            if is_list:
                ti.list_query_field = fname
                ti.has_pagination = "skip" in args and "limit" in args
            elif "index" in args:
                ti.detail_query_field = fname

    def _compute_navigable_fields(self) -> None:
        """A field is *navigable* when it is a list of objects that the
        user can click to browse.  Requirements:

        1. The field is a ``LIST`` of ``OBJECT`` or ``UNION`` items.
        2. The element type (or, for unions, *every* possible type) has
           ``index`` and ``name`` fields.
        3. The element type (or at least one union member) has a root
           detail query so we can fetch the full item.
        """
        for ti in self._types.values():
            nav: list[str] = []
            for fi in ti.fields.values():
                if fi.name == "updated_at":
                    continue
                if not fi.is_list:
                    continue
                if fi.type_kind not in ("OBJECT", "UNION"):
                    continue

                ref = self._types.get(fi.type_name)
                if ref is None:
                    continue

                if ref.kind == "UNION":
                    if not ref.possible_types:
                        continue
                    # Every member must have index + name
                    if not all(
                        self._has_index_and_name(pt)
                        for pt in ref.possible_types
                    ):
                        continue
                    # At least one member needs a root detail query
                    if not any(
                        (self._types.get(pt) or TypeInfo(pt, "")).detail_query_field
                        for pt in ref.possible_types
                    ):
                        continue
                else:
                    if not self._has_index_and_name(fi.type_name):
                        continue
                    if not ref.detail_query_field:
                        continue

                nav.append(fi.name)

            ti.navigable_fields = nav

    def _has_index_and_name(self, type_name: str) -> bool:
        ref = self._types.get(type_name)
        if ref is None:
            return False
        return ref.has_field("index") and ref.has_field("name")


# Module-level singleton
registry = SchemaRegistry()
