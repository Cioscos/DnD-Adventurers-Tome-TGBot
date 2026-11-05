"""Automatic spell-slot recalculation.

When a character's ``spell_slots_mode`` is AUTOMATIC, the spell slots are fully
derived from class levels via the D&D 5e tables in ``core.data.spell_slots``.
``recalc_spell_slots`` reconciles the character's ``SpellSlot`` rows against the
computed targets, preserving each slot's ``used`` count (clamped to the new
``total``) so a level-up never silently refunds spent slots.

It mutates the loaded ``char.spell_slots`` relationship in place (append / remove
→ delete-orphan cascade) so the canonical ``build_character_response`` — which
serializes the in-memory collection without re-querying — reflects the change.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Character, SpellSlot
from core.rules.edition import character_edition
from core.rules.spellcasting import slots_for


def _is_automatic(char: Character) -> bool:
    # Source of truth is the `settings` JSON the frontend reads/writes
    # (`spell_slots_mode`: 'auto' | 'manual'), NOT the legacy `spell_slots_mode`
    # column (which the frontend never sets). Absent key defaults to 'auto',
    # matching the frontend default.
    settings = char.settings or {}
    return (settings.get("spell_slots_mode") or "auto") == "auto"


async def recalc_spell_slots(session: AsyncSession, char: Character) -> None:
    """Reconcile ``char.spell_slots`` with the auto-computed targets.

    No-op unless the character's slot mode is automatic (``settings``-driven,
    default on). Requires ``char.classes`` and ``char.spell_slots`` to be loaded
    (true for every level-up endpoint).
    """
    if not _is_automatic(char):
        return

    # Target totals keyed by (spell_level, is_pact).
    targets: dict[tuple[int, bool], int] = {}
    table = slots_for(character_edition(char), char.classes)
    for level, total in table.regular.items():
        targets[(level, False)] = total
    for level, total in table.pact.items():
        targets[(level, True)] = total

    seen: set[tuple[int, bool]] = set()
    for slot in list(char.spell_slots):
        key = (slot.level, bool(slot.is_pact))
        if key in targets:
            slot.total = targets[key]
            if slot.used > slot.total:
                slot.used = slot.total
            seen.add(key)
        else:
            # Automatic mode is authoritative: drop slots the rules no longer grant.
            char.spell_slots.remove(slot)

    for (level, is_pact), total in targets.items():
        if (level, is_pact) not in seen:
            char.spell_slots.append(
                SpellSlot(level=level, total=total, used=0, is_pact=is_pact)
            )

    await session.flush()
