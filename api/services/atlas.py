"""Campaign atlas: constants and visibility rules shared by the map and marker routes."""
from __future__ import annotations

from sqlalchemy import or_

from core.db.models import CampaignMap, CampaignMapMarker

# key -> (lucide icon, color)
BUILTIN_TYPES: dict[str, tuple[str, str]] = {
    "city": ("castle", "gold"),
    "dungeon": ("skull", "arcane"),
    "poi": ("landmark", "cobalt"),
    "danger": ("triangle-alert", "crimson"),
    "npc": ("user", "emerald"),
    "quest": ("scroll", "amber"),
}
# shortcut: provisional icon list, Task 4 finalises it to match the frontend ATLAS_ICONS.
ICONS: frozenset[str] = frozenset({icon for icon, _ in BUILTIN_TYPES.values()} | {"beer"})
COLORS: frozenset[str] = frozenset({"gold", "crimson", "emerald", "arcane", "cobalt", "amber", "parchment"})


def map_visible(m: CampaignMap, is_gm: bool) -> bool:
    return is_gm or m.revealed_at is not None


def marker_visible(user_id: int):
    """SQL clause: own markers plus public ones (for the GM too: player-private never leaks)."""
    return or_(CampaignMapMarker.author_user_id == user_id, CampaignMapMarker.visibility == "public")
