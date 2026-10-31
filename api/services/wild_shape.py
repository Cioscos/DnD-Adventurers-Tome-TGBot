"""Wild shape: the active form absorbs damage before the character does."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Companion


async def get_active_form(session: AsyncSession, char_id: int) -> Companion | None:
    return (await session.execute(
        select(Companion).where(
            Companion.character_id == char_id,
            Companion.kind == "wild_shape",
            Companion.is_active.is_(True),
        ).order_by(Companion.id)
    )).scalars().first()


def absorb_damage(form: Companion, amount: int) -> int:
    """Apply `amount` to the form (temp HP first); return the overflow past 0 HP."""
    absorbed = min(form.temp_hp, amount)
    form.temp_hp -= absorbed
    rest = amount - absorbed
    lost = min(form.current_hp, rest)
    form.current_hp -= lost
    return rest - lost
