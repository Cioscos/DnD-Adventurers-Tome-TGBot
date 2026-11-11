"""Caricamento del personaggio con le relazioni che le risposte usano, condiviso dai router (404 se manca, 403 se non è suo)."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.db.models import Character


def full_load():
    """Return selectinload options for a fully-populated character."""
    return [
        selectinload(Character.classes),
        selectinload(Character.ability_scores),
        selectinload(Character.spells),
        selectinload(Character.spell_slots),
        selectinload(Character.items),
        selectinload(Character.currency),
        selectinload(Character.abilities),
        selectinload(Character.maps),
    ]


async def get_owned(
    char_id: int,
    user_id: int,
    session: AsyncSession,
    *,
    full: bool = False,
    extra: tuple = (),
) -> Character:
    """Fetch a character by id, verifying ownership. Raises 404/403. ``extra``: altre opzioni di caricamento."""
    opts = [*(full_load() if full else []), *extra]
    result = await session.execute(
        select(Character).options(*opts).where(Character.id == char_id)
    )
    char = result.scalar_one_or_none()
    if char is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    if char.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your character")
    return char


async def get_owned_full(char_id: int, user_id: int, session: AsyncSession) -> Character:
    return await get_owned(char_id, user_id, session, full=True)


async def get_owned_full_with_resources(char_id: int, user_id: int, session: AsyncSession) -> Character:
    """Come ``get_owned_full`` più le risorse homebrew e i compagni (PF, forme, regole)."""
    return await get_owned(char_id, user_id, session, full=True,
                           extra=(selectinload(Character.homebrew_resources),
                                  selectinload(Character.companions)))  # Compagno Selvatico crea e sostituisce il famiglio


async def refresh_char_full(session: AsyncSession, char_id: int, user_id: int) -> Character:
    """Flush pending mutations, then re-SELECT a fully-loaded character.

    Use this in endpoints that mutate ``char.*`` and return ``CharacterFull``. A bare ``session.refresh(char,
    attribute_names=[...])`` re-runs each relation's default loader (lazy="select") and strips the nested
    ``selectinload`` chains (notably ``classes.resources``), so serialization either fails with ``MissingGreenlet`` or
    silently returns an empty list. ``expunge_all()`` (autoflush may have pulled related objects into the identity map;
    ``expunge(char)`` alone isn't enough) and a new full eager-load query fix it.
    """
    await session.flush()
    session.expunge_all()
    return await get_owned(char_id, user_id, session, full=True)
