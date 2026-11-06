"""Recupero Naturale (Druido 2014, Circolo della Terra) e Recupero Arcano (Mago 2014): durante un riposo breve si
recuperano slot spesi.

Il giocatore sceglie quanti slot di ogni livello; il server convalida tutto prima di scrivere, poi spende l'uso con un
UPDATE condizionato (due richieste insieme recuperano una volta sola) e restituisce gli slot."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Ability, Character, SpellSlot
from core.rules.catalog import active_features

FEATURE = "druid.natural_recovery"
ARCANE_FEATURE = "wizard.arcane_recovery"
MAX_SLOT_LEVEL = 5  # nessuno slot di 6° livello o superiore


def _refuse(code: int, name: str) -> HTTPException:
    return HTTPException(code, detail={"code": name})


def budget(druid_level: int) -> int:
    """Livelli di slot recuperabili: metà del livello da druido, per eccesso."""
    return (druid_level + 1) // 2


async def recover(session: AsyncSession, char: Character, wanted: dict[int, int],
                  feature: str = FEATURE) -> dict[int, int]:
    """Restituisce gli slot ``livello -> quanti``; ogni rifiuto lascia tutto com'era (la risposta annulla la transazione).
    Il tetto segue il livello della classe che ha il privilegio ``feature``: un Mago/Druido ha i due privilegi separati."""
    found = next(((spec, row) for spec, row in active_features(char) if spec.key == feature), None)
    if found is None:
        raise _refuse(status.HTTP_422_UNPROCESSABLE_ENTITY, "natural_recovery_unavailable")
    row = found[1]
    plan = {level: count for level, count in wanted.items() if count != 0}
    if not plan or any(count < 1 or not 1 <= level <= MAX_SLOT_LEVEL for level, count in plan.items()):
        raise _refuse(status.HTTP_422_UNPROCESSABLE_ENTITY, "natural_recovery_level")
    if sum(level * count for level, count in plan.items()) > budget(row.level):
        raise _refuse(status.HTTP_422_UNPROCESSABLE_ENTITY, "natural_recovery_cap")
    slots = {s.level: s for s in char.spell_slots if not s.is_pact}
    if any(level not in slots or slots[level].used < count for level, count in plan.items()):
        raise _refuse(status.HTTP_422_UNPROCESSABLE_ENTITY, "natural_recovery_unspent")
    ability = next((a for a in char.abilities if a.feature_key == feature), None)
    if ability is None or (ability.max_uses is not None and (ability.uses or 0) < 1):
        raise _refuse(status.HTTP_409_CONFLICT, "no_uses")

    # Primo atto di scrittura: l'uso si spende con un UPDATE condizionato.
    spent = await session.execute(
        update(Ability).where(Ability.id == ability.id, Ability.uses >= 1).values(uses=Ability.uses - 1))
    if spent.rowcount != 1:
        raise _refuse(status.HTTP_409_CONFLICT, "no_uses")
    for level, count in plan.items():
        done = await session.execute(update(SpellSlot).where(SpellSlot.id == slots[level].id, SpellSlot.used >= count)
                                     .values(used=SpellSlot.used - count))
        if done.rowcount != 1:
            raise _refuse(status.HTTP_422_UNPROCESSABLE_ENTITY, "natural_recovery_unspent")
    await session.refresh(ability)
    for level in plan:
        await session.refresh(slots[level])
    return plan
