"""La bestia del Signore delle Bestie al riposo lungo: guarisce, se è viva, e recupera metà (2014) o tutti (2024) i suoi Dadi Vita."""
from __future__ import annotations

import re

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Character, Companion
from core.rules.companions import BEAST_KEYS, PRIMAL_COMPANION, companion_stats, other_edition, stat_int


async def long_rest_beast(session: AsyncSession, char: Character) -> None:
    """Un riposo lungo ridà alla bestia viva tutti i PF e metà dei Dadi Vita del suo profilo (almeno uno; 2024 Glossario,
    Riposo Lungo pag. 370: tutti); quella morta non torna."""
    rows = (await session.execute(
        select(Companion).where(Companion.character_id == char.id, Companion.feature_key.in_(BEAST_KEYS)))).scalars()
    for comp in rows:
        if comp.current_hp <= 0 or other_edition(char, comp):
            continue
        stats = companion_stats(char, comp)
        comp.current_hp = stats.max_hp if stats is not None and stats.max_hp is not None else comp.max_hp
        sb = dict(comp.statblock or {})
        total = re.match(r"(\d+)d\d+", str(sb.get("hit_dice") or ""))
        spent = stat_int(sb, "hit_dice_spent")
        if total and spent:
            back = spent if comp.feature_key == PRIMAL_COMPANION else max(1, int(total.group(1)) // 2)
            comp.statblock = {**sb, "hit_dice_spent": max(0, spent - back)}


async def drop_primal_beast(session: AsyncSession, char: Character) -> None:
    """Il ranger muore: la bestia primordiale 2024 svanisce con lui."""
    if other_edition(char, Companion(feature_key=PRIMAL_COMPANION)):  # in 2014 quella salvata è nascosta: non è sua
        return
    mine = (Companion.character_id == char.id, Companion.feature_key == PRIMAL_COMPANION)
    gone = (await session.execute(select(Companion.id).where(*mine))).scalars().all()
    turn = char.turn_state or {}
    if (turn.get("beast") or {}).get("id") in gone:  # come l'eliminazione a mano: SQLite riusa l'id
        char.turn_state = {k: v for k, v in turn.items() if k != "beast"}
    await session.execute(delete(Companion).where(*mine))
