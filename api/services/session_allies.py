"""Chi siede alla stessa serata di un personaggio: il bersaglio dei privilegi che aiutano un alleato (R38)."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Character, GameSession, SessionParticipant, SessionStatus


async def seated_allies(session: AsyncSession, char: Character) -> list[Character]:
    """Gli altri personaggi seduti alle serate attive in cui siede ``char``. Conta il personaggio seduto, non l'utente:
    un secondo PG dello stesso giocatore, rimasto a casa, non è al tavolo."""
    mine = select(SessionParticipant.session_id).join(GameSession, GameSession.id == SessionParticipant.session_id).where(
        SessionParticipant.character_id == char.id, GameSession.status == SessionStatus.ACTIVE)
    rows = await session.execute(
        select(Character).join(SessionParticipant, SessionParticipant.character_id == Character.id)
        .where(SessionParticipant.session_id.in_(mine), Character.id != char.id).order_by(Character.id))
    return list(dict.fromkeys(rows.scalars().all()))


async def ally_target(session: AsyncSession, char: Character, target_id: object) -> Character:
    """Il bersaglio scelto, se siede alla stessa serata e non è ``char``; altrimenti 422 ``invalid_target``."""
    if type(target_id) is int:
        found = next((a for a in await seated_allies(session, char) if a.id == target_id), None)
        if found is not None:
            return found
    raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "invalid_target"})
