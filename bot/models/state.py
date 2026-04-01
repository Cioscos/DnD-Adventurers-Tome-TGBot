"""Category registry and callback-data helpers.

Defines the mapping between category keys and their display metadata,
GraphQL query/field names, and provides encode/decode utilities for
Telegram ``callback_data`` strings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from bot.api import queries


@dataclass(frozen=True)
class Category:
    """Metadata for a single D&D category."""

    key: str
    label: str
    emoji: str
    list_query: str
    list_field: str
    detail_query: str
    detail_field: str
    paginated: bool = True


# ------------------------------------------------------------------
# Category registry – order determines the button layout in /start.
# ------------------------------------------------------------------
CATEGORIES: dict[str, Category] = {
    "spells": Category(
        key="spells",
        label="Spells",
        emoji="🔮",
        list_query=queries.SPELLS_LIST,
        list_field="spells",
        detail_query=queries.SPELL_DETAIL,
        detail_field="spell",
    ),
    "monsters": Category(
        key="monsters",
        label="Monsters",
        emoji="🐉",
        list_query=queries.MONSTERS_LIST,
        list_field="monsters",
        detail_query=queries.MONSTER_DETAIL,
        detail_field="monster",
    ),
    "classes": Category(
        key="classes",
        label="Classes",
        emoji="⚔️",
        list_query=queries.CLASSES_LIST,
        list_field="classes",
        detail_query=queries.CLASS_DETAIL,
        detail_field="class",
        paginated=False,
    ),
    "races": Category(
        key="races",
        label="Races",
        emoji="🧝",
        list_query=queries.RACES_LIST,
        list_field="races",
        detail_query=queries.RACE_DETAIL,
        detail_field="race",
        paginated=False,
    ),
    "equipment": Category(
        key="equipment",
        label="Equipment",
        emoji="🎒",
        list_query=queries.EQUIPMENT_LIST,
        list_field="equipments",
        detail_query=queries.EQUIPMENT_DETAIL,
        detail_field="equipment",
    ),
    "conditions": Category(
        key="conditions",
        label="Conditions",
        emoji="🩹",
        list_query=queries.CONDITIONS_LIST,
        list_field="conditions",
        detail_query=queries.CONDITION_DETAIL,
        detail_field="condition",
        paginated=False,
    ),
    "magicitems": Category(
        key="magicitems",
        label="Magic Items",
        emoji="✨",
        list_query=queries.MAGIC_ITEMS_LIST,
        list_field="magicItems",
        detail_query=queries.MAGIC_ITEM_DETAIL,
        detail_field="magicItem",
    ),
    "feats": Category(
        key="feats",
        label="Feats",
        emoji="💪",
        list_query=queries.FEATS_LIST,
        list_field="feats",
        detail_query=queries.FEAT_DETAIL,
        detail_field="feat",
        paginated=False,
    ),
    "rules": Category(
        key="rules",
        label="Rules",
        emoji="📖",
        list_query=queries.RULES_LIST,
        list_field="rules",
        detail_query=queries.RULE_DETAIL,
        detail_field="rule",
        paginated=False,
    ),
    "backgrounds": Category(
        key="backgrounds",
        label="Backgrounds",
        emoji="📜",
        list_query=queries.BACKGROUNDS_LIST,
        list_field="backgrounds",
        detail_query=queries.BACKGROUND_DETAIL,
        detail_field="background",
        paginated=False,
    ),
    "weaponprops": Category(
        key="weaponprops",
        label="Weapon Props",
        emoji="🗡️",
        list_query=queries.WEAPON_PROPERTIES_LIST,
        list_field="weaponProperties",
        detail_query=queries.WEAPON_PROPERTY_DETAIL,
        detail_field="weaponProperty",
        paginated=False,
    ),
}


# ------------------------------------------------------------------
# callback_data encoding helpers
# Format: "<action>:<category>:<payload>"
#   cat:<key>:<page>   – show item list at page N
#   itm:<key>:<index>  – show item detail
#   back:main          – go back to top-level categories
#   noop               – do nothing (informational buttons)
# ------------------------------------------------------------------

def encode_category(key: str, page: int = 0) -> str:
    """Encode a 'show category list' callback."""
    return f"cat:{key}:{page}"


def encode_item(category_key: str, index: str) -> str:
    """Encode a 'show item detail' callback."""
    return f"itm:{category_key}:{index}"


def encode_back_to_list(category_key: str, page: int = 0) -> str:
    """Encode a 'back to list' callback."""
    return f"cat:{category_key}:{page}"


BACK_TO_MAIN = "back:main"
NOOP = "noop"


@dataclass
class ParsedCallback:
    """Parsed callback_data."""

    action: str  # "cat", "itm", "back", "noop"
    category: Optional[str] = None
    payload: Optional[str] = None


def parse_callback(data: str) -> ParsedCallback:
    """Parse a callback_data string into its components."""
    parts = data.split(":", 2)
    action = parts[0]
    if action == "noop":
        return ParsedCallback(action="noop")
    if action == "back":
        return ParsedCallback(action="back", category=parts[1] if len(parts) > 1 else None)
    category = parts[1] if len(parts) > 1 else None
    payload = parts[2] if len(parts) > 2 else None
    return ParsedCallback(action=action, category=category, payload=payload)
