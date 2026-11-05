"""Canto di Riposo (Bardo 2014): il dado extra di PF per chi spende Dadi Vita mentre il bardo si esibisce."""
from __future__ import annotations

import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Character, GameSession, SessionParticipant, SessionStatus
from core.rules.states import begin_state, has_state
from core.rules.types import StateSpec

SONG = "song_of_rest"  # lo stato del bardo che si esibisce (dado in `data["die"]`)
RECEIVED = "song_of_rest_received"  # chi ha già avuto il dado extra: uno a testa, fino al prossimo riposo
FEATURE = "bard.song_of_rest"


def _die(char: Character) -> int | None:
    state = next((s for s in char.active_states or [] if s.get("key") == SONG), None)
    die = (state or {}).get("data", {}).get("die")
    return die if isinstance(die, int) and die > 1 else None


async def song_die(session: AsyncSession, char: Character) -> int | None:
    """Taglia del dado che `char` può ricevere: il suo Canto di Riposo o quello di un bardo seduto alla sua stessa serata."""
    if (own := _die(char)) is not None:
        return own
    mine = select(SessionParticipant.session_id).join(GameSession, GameSession.id == SessionParticipant.session_id).where(
        SessionParticipant.user_id == char.user_id, GameSession.status == SessionStatus.ACTIVE)
    friends = (await session.execute(
        select(Character).join(SessionParticipant, SessionParticipant.character_id == Character.id)
        .where(SessionParticipant.session_id.in_(mine), Character.id != char.id))).scalars().all()
    return max((d for d in map(_die, friends) if d is not None), default=None)


async def roll_song_of_rest(session: AsyncSession, char: Character) -> tuple[int | None, list[int]]:
    """Il dado extra per questo riposo: `(taglia, [tiro])`, oppure `(None, [])` se non spetta o l'ha già avuto."""
    if has_state(char, RECEIVED):
        return None, []
    die = await song_die(session, char)
    if die is None:
        return None, []
    begin_state(char, StateSpec(RECEIVED, ends_on=("rest_short", "rest_long")), FEATURE, "Canto di Riposo")
    return die, [random.randint(1, die)]
