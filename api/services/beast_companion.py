"""La bestia del Signore delle Bestie 2014 al riposo lungo: guarisce, se è viva, e recupera metà dei suoi Dadi Vita."""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Character, Companion
from core.rules.companions import BEAST_COMPANION, companion_stats


async def long_rest_beast(session: AsyncSession, char: Character) -> None:
    """Un riposo lungo ridà alla bestia viva tutti i PF e metà dei Dadi Vita del suo profilo (almeno uno); quella morta non torna."""
    rows = (await session.execute(
        select(Companion).where(Companion.character_id == char.id, Companion.feature_key == BEAST_COMPANION))).scalars()
    for comp in rows:
        if comp.current_hp <= 0:
            continue
        stats = companion_stats(char, comp)
        comp.current_hp = stats.max_hp if stats is not None and stats.max_hp is not None else comp.max_hp
        sb = dict(comp.statblock or {})
        total = re.match(r"(\d+)d\d+", str(sb.get("hit_dice") or ""))
        spent = int(sb.get("hit_dice_spent") or 0)
        if total and spent:
            comp.statblock = {**sb, "hit_dice_spent": max(0, spent - max(1, int(total.group(1)) // 2))}
