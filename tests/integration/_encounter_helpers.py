"""Seed helpers shared by the encounter test modules (not collected by pytest)."""
from __future__ import annotations

from api.auth import get_current_user
from api.main import app
from core.db.models import (
    AbilityScore,
    Character,
    GameSession,
    SessionParticipant,
    SessionRole,
    SessionStatus,
)

GM_ID = 1234       # == tests/integration/conftest.py TEST_USER_ID (default auth)
PLAYER_ID = 5678
NOW = "2026-06-09T10:00:00"


def as_user(uid: int) -> None:
    """Re-point the auth override at a different user (cleared by the fixture)."""
    app.dependency_overrides[get_current_user] = lambda: uid


async def seed_session(test_session_factory, *, player_dex: int = 16):
    """GM session + one player with a DEX `player_dex` character.

    Returns (session_id, char_id). DEX 16 -> initiative_mod +3.
    """
    async with test_session_factory() as s:
        char = Character(user_id=PLAYER_ID, name="Eroe")
        s.add(char)
        await s.flush()
        s.add(AbilityScore(character_id=char.id, name="dexterity", value=player_dex))
        sess = GameSession(
            code="ABC123", gm_user_id=GM_ID, status=SessionStatus.ACTIVE,
            created_at=NOW, last_activity_at=NOW,
        )
        s.add(sess)
        await s.flush()
        s.add(SessionParticipant(
            session_id=sess.id, user_id=GM_ID,
            role=SessionRole.GAME_MASTER, joined_at=NOW,
        ))
        s.add(SessionParticipant(
            session_id=sess.id, user_id=PLAYER_ID, character_id=char.id,
            role=SessionRole.PLAYER, display_name="Eroe", joined_at=NOW,
        ))
        await s.commit()
        return sess.id, char.id
