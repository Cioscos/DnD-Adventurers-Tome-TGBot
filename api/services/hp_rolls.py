"""PF tirati al level-up: i tiri grezzi vivono in ``settings.hp_rolls`` come
``{"<class_id>": {"<livello_di_classe>": tiro}}`` (senza CON), cosi' ogni ricalcolo
successivo (``total_base_hp``) riusa il tiro con il mod CON effettivo corrente."""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from core.db.models import Character, CharacterClass


def stored_rolls(char: Character) -> dict[int, dict[int, int]]:
    raw = (char.settings or {}).get("hp_rolls")
    out: dict[int, dict[int, int]] = {}
    for c, lv_map in (raw.items() if isinstance(raw, dict) else ()):  # tolerant: imported files are untrusted
        try:
            out[int(c)] = {int(lv): int(r) for lv, r in lv_map.items()}
        except (TypeError, ValueError, AttributeError):
            continue
    return out


def record_rolls(
    char: Character, cls: CharacterClass, old_level: int, new_level: int,
    rolls: Optional[list[int]],
) -> None:
    """Salva i tiri per i livelli old+1..new e scarta quelli obsoleti (> min(old, new))."""
    gained = max(0, new_level - old_level)
    if rolls is not None and len(rolls) != gained:
        raise HTTPException(422, "hp_rolls must have one value per gained level")
    if any(not 1 <= r <= (cls.hit_die or 0) for r in rolls or []):
        raise HTTPException(422, "each hp roll must be between 1 and the hit die")
    all_rolls = {c: dict(m) for c, m in stored_rolls(char).items()}
    kept = {lv: r for lv, r in all_rolls.get(cls.id, {}).items() if lv <= min(old_level, new_level)}
    kept.update({old_level + 1 + i: r for i, r in enumerate(rolls or [])})
    all_rolls[cls.id] = kept
    s = dict(char.settings or {})
    s["hp_rolls"] = {str(c): {str(lv): r for lv, r in m.items()} for c, m in all_rolls.items() if m}
    char.settings = s
