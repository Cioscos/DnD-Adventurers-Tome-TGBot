"""Slot creati con Incantesimi Flessibili (Stregone 2014): restano fino al riposo lungo."""
from __future__ import annotations

from core.db.models import Character, SpellSlot


CREATED_SLOTS = "created_slots"  # settings: {"3": 1} = slot creati con Incantesimi Flessibili, per livello (scritto dal server)


def _created(char: Character) -> dict[int, int]:
    raw = (char.settings or {}).get(CREATED_SLOTS)
    return {int(k): v for k, v in raw.items() if str(k).isdigit() and type(v) is int and v > 0} if isinstance(raw, dict) else {}


def clean_created_slots(value: object) -> dict[str, int]:
    """Da un file importato: solo i livelli 1-5, con un conteggio ragionevole."""
    if not isinstance(value, dict):
        return {}
    return {str(k): v for k, v in value.items() if str(k) in "12345" and type(v) is int and 0 < v <= 20}


def add_created_slot(char: Character, level: int) -> None:
    """Uno slot in più di ``level`` fino al prossimo riposo lungo (Creare Slot Incantesimo). Il ricalcolo automatico lo conserva."""
    slot = next((s for s in char.spell_slots if s.level == level and not s.is_pact), None)
    if slot is None:
        char.spell_slots.append(SpellSlot(level=level, total=1, used=0, is_pact=False))
    else:
        slot.total += 1
    created = _created(char)
    created[level] = created.get(level, 0) + 1
    char.settings = {**(char.settings or {}), CREATED_SLOTS: {str(k): v for k, v in created.items()}}


def clear_created_slots(char: Character) -> None:
    """Il riposo lungo li fa svanire: il totale scende e una riga rimasta senza slot sparisce."""
    created = _created(char)
    if not created and CREATED_SLOTS not in (char.settings or {}):
        return
    for level, count in created.items():
        slot = next((s for s in char.spell_slots if s.level == level and not s.is_pact), None)
        if slot is not None:
            slot.total = max(0, slot.total - count)
            slot.used = min(slot.used, slot.total)
            if slot.total == 0:
                char.spell_slots.remove(slot)
    char.settings = {k: v for k, v in (char.settings or {}).items() if k != CREATED_SLOTS}
