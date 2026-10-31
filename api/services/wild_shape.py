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


async def deactivate_other_forms(session: AsyncSession, char_id: int, keep_id: int | None) -> None:
    """At most one active wild shape: activating one deactivates the others (no 409)."""
    res = await session.execute(
        select(Companion).where(Companion.character_id == char_id, Companion.is_active.is_(True))
    )
    for other in res.scalars():
        if other.id != keep_id:
            other.is_active = False


def absorb_damage(form: Companion, amount: int) -> int:
    """Apply `amount` to the form (temp HP first); return the overflow past 0 HP."""
    absorbed = min(form.temp_hp, amount)
    form.temp_hp -= absorbed
    rest = amount - absorbed
    lost = min(form.current_hp, rest)
    form.current_hp -= lost
    return rest - lost
