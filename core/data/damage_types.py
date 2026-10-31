"""Tipi di danno 5e: slug canonici, normalizzazione e moltiplicatore da resistenze."""

from __future__ import annotations

from typing import Literal

DAMAGE_TYPES: tuple[str, ...] = (
    "acid", "bludgeoning", "cold", "fire", "force", "lightning", "necrotic",
    "piercing", "poison", "psychic", "radiant", "slashing", "thunder",
)

# Etichette italiane = `character.inventory.damage_types.*` in webapp it.json.
LABELS_IT: dict[str, str] = {
    "slashing": "Taglio", "piercing": "Perforazione", "bludgeoning": "Contundente",
    "fire": "Fuoco", "cold": "Freddo", "lightning": "Fulmine", "acid": "Acido",
    "poison": "Veleno", "necrotic": "Necrotico", "radiant": "Radiante",
    "force": "Forza", "psychic": "Psichico", "thunder": "Tuono",
}

_LOOKUP: dict[str, str] = {s: s for s in DAMAGE_TYPES}
_LOOKUP.update({label.lower(): slug for slug, label in LABELS_IT.items()})
# Sinonimi comuni digitati a mano nelle vecchie liste di resistenze.
_LOOKUP.update({"tagliente": "slashing", "perforante": "piercing", "radioso": "radiant"})


def canonical_damage_type(value: str | None) -> str | None:
    """Slug, `dmg_<slug>`, etichetta IT/EN, qualsiasi maiuscola/spazio; ignoto -> None."""
    if not isinstance(value, str):
        return None
    v = value.strip().lower()
    if v.startswith("dmg_"):
        v = v[4:]
    return _LOOKUP.get(v)


def _contains(values: object, slug: str) -> bool:
    return isinstance(values, list) and any(
        canonical_damage_type(v) == slug for v in values if isinstance(v, str)
    )


def damage_multiplier(
    char_damage_modifiers: dict | None, damage_type: str | None,
) -> Literal["immune", "half", "double", "none"]:
    """Immunità prevale; resistenza + vulnerabilità si annullano (PHB 2014 p.197)."""
    slug = canonical_damage_type(damage_type)
    mods = char_damage_modifiers if isinstance(char_damage_modifiers, dict) else {}
    if slug is None:
        return "none"
    if _contains(mods.get("immunities"), slug):
        return "immune"
    res = _contains(mods.get("resistances"), slug)
    vul = _contains(mods.get("vulnerabilities"), slug)
    if res == vul:
        return "none"
    return "half" if res else "double"
