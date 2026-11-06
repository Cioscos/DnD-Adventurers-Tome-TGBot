"""Riflessi da Furfante (Ladro 17): nel primo round il ladro ha un secondo turno, all'iniziativa meno 10."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.db.models import Character, Combatant, Encounter
from core.rules.catalog import active_features

FEATURE = "rogue.thiefs_reflexes"
_NAMES = {"it": "Riflessi da Furfante", "en": "Thief's Reflexes"}


async def add_second_turns(db: AsyncSession, enc: Encounter, lang: str, now: str) -> list[Combatant]:
    """Aggiunge, all'avvio dell'incontro, il secondo turno di chi ha Riflessi da Furfante e non è sorpreso. È una riga a parte
    (``extra_turn_of``) con la stessa iniziativa meno 10: l'ordine di turno la salta dal secondo round."""
    pcs = [c for c in enc.combatants if c.kind == "pc" and c.character_id and c.initiative is not None and not c.surprised]
    if not pcs:
        return []
    chars = {c.id: c for c in (await db.execute(
        select(Character).options(selectinload(Character.classes)).where(Character.id.in_([p.character_id for p in pcs])))).scalars()}
    added: list[Combatant] = []
    for pc in pcs:
        char = chars.get(pc.character_id)
        if char is None or not any(spec.key == FEATURE for spec, _row in active_features(char)):
            continue
        extra = Combatant(
            encounter_id=enc.id, kind="pc", character_id=None, extra_turn_of=char.id, owner_user_id=pc.owner_user_id,
            name=f"{pc.name} ({_NAMES.get(lang) or _NAMES['it']})", initiative=pc.initiative - 10,
            initiative_mod=pc.initiative_mod, created_at=now)
        db.add(extra)
        enc.combatants.append(extra)
        added.append(extra)
    await db.flush()  # gli id servono a chi ordina
    return added
