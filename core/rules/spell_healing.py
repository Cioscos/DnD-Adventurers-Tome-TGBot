"""Incantesimi di cura (R41): quanti PF restituiscono, per ``srd_index``. Dati nostri, non testo dei manuali."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HealingSpec:
    """``dice``: dadi base (``NdM``); ``per_level``: dadi in più per ogni livello di slot oltre quello dell'incantesimo
    (stessi lati); ``fixed``/``fixed_per_level``: PF fissi (Cura Completa); ``add_mod``: somma il modificatore da incantatore."""
    dice: str | None
    per_level: str | None = None
    fixed: int = 0
    fixed_per_level: int = 0
    add_mod: bool = True


SPELL_HEALING: dict[str, HealingSpec] = {
    "cure-wounds": HealingSpec("1d8", "1d8"),
    "healing-word": HealingSpec("1d4", "1d4"),
    "mass-cure-wounds": HealingSpec("3d8", "1d8"),
    "mass-healing-word": HealingSpec("1d4", "1d4"),
    "prayer-of-healing": HealingSpec("2d8", "1d8"),
    "heal": HealingSpec(None, fixed=70, fixed_per_level=10, add_mod=False),
    "regenerate": HealingSpec("4d8", fixed=15, add_mod=False),
    # Gli altri che ridanno PF: i privilegi che contano «ogni incantesimo di 1° livello o superiore che ripristina PF»
    # (Discepolo della Vita) li vedono. Bacca benefica: una bacca (ognuna ridà 1 PF).
    "mass-heal": HealingSpec(None, fixed=700, add_mod=False),
    "revivify": HealingSpec(None, fixed=1, add_mod=False),
    "raise-dead": HealingSpec(None, fixed=1, add_mod=False),
    "goodberry": HealingSpec(None, fixed=1, add_mod=False),
}

# Dove il manuale 2024 differisce (le altre cure valgono per entrambe le edizioni): Cura Ferite e Parola di Guarigione
# raddoppiano i dadi, Cura Ferite di Massa parte da 5d8, Parola Guaritrice di Massa da 2d4.
SPELL_HEALING_2024: dict[str, HealingSpec] = {
    "cure-wounds": HealingSpec("2d8", "2d8"),
    "healing-word": HealingSpec("2d4", "2d4"),
    "mass-cure-wounds": HealingSpec("5d8", "1d8"),
    "mass-healing-word": HealingSpec("2d4", "1d4"),
}


def healing_spec(srd_index: str | None, edition: str) -> HealingSpec | None:
    """La cura di un incantesimo per l'edizione di chi lancia; ``None`` se non ridà PF."""
    if edition == "2024" and srd_index in SPELL_HEALING_2024:
        return SPELL_HEALING_2024[srd_index]
    return SPELL_HEALING.get(srd_index or "")


def healing_dice(spec: HealingSpec, spell_level: int, casting_level: int) -> tuple[int, int]:
    """(numero di dadi, lati) allo slot ``casting_level``; ``(0, 0)`` se la cura è solo fissa."""
    if spec.dice is None:
        return 0, 0
    count, sides = (int(x) for x in spec.dice.split("d"))
    if spec.per_level:
        count += int(spec.per_level.split("d")[0]) * max(0, casting_level - spell_level)
    return count, sides


def healing_fixed(spec: HealingSpec, spell_level: int, casting_level: int) -> int:
    return spec.fixed + spec.fixed_per_level * max(0, casting_level - spell_level)
