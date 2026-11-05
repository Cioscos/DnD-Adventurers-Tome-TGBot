"""Privilegi che agiscono all'inizio del turno di chi li ha (Sopravvissuto del Campione)."""
from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.effects import apply_heal
from core.db.models import Character
from core.rules.catalog import active_features
from core.rules.edition import character_edition
from core.rules.types import RuleContext

_NEEDED = {"classes", "items", "ability_scores"}


async def apply_turn_start(session: AsyncSession, char: Character) -> int:
    """Cura i PF che i privilegi attivi danno a inizio turno e restituisce quelli recuperati davvero.

    Un solo punto per i due ingressi del turno: il passaggio di turno dell'incontro (``process_edge`` e il primo turno) e
    «Nuovo turno» fuori da un incontro. Ogni privilegio decide da sé se la condizione c'è (``turn_start_heal`` dà 0 se no)."""
    if missing := _NEEDED & inspect(char).unloaded:  # chi chiama non carica sempre le relazioni (scadenze, GM)
        await session.refresh(char, attribute_names=list(missing))
    specs = [(spec, row) for spec, row in active_features(char) if spec.turn_start_heal]
    healed = 0
    for spec, row in specs:
        ctx = RuleContext(char=char, edition=character_edition(char), class_row=row, class_level=row.level)
        amount = spec.turn_start_heal(ctx)
        if amount > 0:
            healed += (await apply_heal(session, char, amount))["healed"]
    return healed
