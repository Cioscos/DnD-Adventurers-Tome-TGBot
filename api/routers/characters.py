"""Character CRUD endpoints."""

from __future__ import annotations

import random
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.database import get_db
from core.db.models import (
    AbilityScore,
    ABILITY_NAMES,
    Character,
    CharacterClass,
    CharacterHistory,
    ClassResource,
    Currency,
    GameSession,
    SessionParticipant,
    SessionStatus,
)
from core.data.xp_thresholds import xp_to_level
from core.data.classes import get_resources_for_class, update_resources_for_level
from api.schemas.character import (
    CharacterCreate,
    CharacterFull,
    CharacterSummary,
    CharacterUpdate,
    ConditionsUpdate,
    InspirationUpdate,
    SkillsUpdate,
    SavingThrowsUpdate,
    XPUpdate,
)
from api.schemas.common import RollResult

router = APIRouter(prefix="/characters", tags=["characters"])

# Mapping from skill name to governing ability
_SKILL_ABILITY: dict[str, str] = {
    "acrobatics": "dexterity",
    "animal_handling": "wisdom",
    "arcana": "intelligence",
    "athletics": "strength",
    "deception": "charisma",
    "history": "intelligence",
    "insight": "wisdom",
    "intimidation": "charisma",
    "investigation": "intelligence",
    "medicine": "wisdom",
    "nature": "intelligence",
    "perception": "wisdom",
    "performance": "charisma",
    "persuasion": "charisma",
    "religion": "intelligence",
    "sleight_of_hand": "dexterity",
    "stealth": "dexterity",
    "survival": "wisdom",
}


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M")


def _add_history(session, char_id: int, event_type: str, description: str) -> None:
    session.add(CharacterHistory(
        character_id=char_id,
        timestamp=_now(),
        event_type=event_type,
        description=description,
    ))


def _full_load():
    """Return selectinload options for a fully-populated character."""
    return [
        selectinload(Character.classes).selectinload(
            __import__("core.db.models", fromlist=["CharacterClass"]).CharacterClass.resources
        ),
        selectinload(Character.ability_scores),
        selectinload(Character.spells),
        selectinload(Character.spell_slots),
        selectinload(Character.items),
        selectinload(Character.currency),
        selectinload(Character.abilities),
        selectinload(Character.maps),
    ]


async def _get_owned(
    char_id: int,
    user_id: int,
    session: AsyncSession,
    *,
    full: bool = False,
) -> Character:
    """Fetch a character by id, verifying ownership. Raises 404/403."""
    opts = _full_load() if full else []
    result = await session.execute(
        select(Character).options(*opts).where(Character.id == char_id)
    )
    char = result.scalar_one_or_none()
    if char is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    if char.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your character")
    return char


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@router.get("", response_model=list[CharacterSummary])
async def list_characters(
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[Character]:
    result = await session.execute(
        select(Character)
        .options(selectinload(Character.classes))
        .where(Character.user_id == user_id)
        .order_by(Character.id)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@router.post("", response_model=CharacterFull, status_code=status.HTTP_201_CREATED)
async def create_character(
    body: CharacterCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Character:
    char = Character(user_id=user_id, name=body.name, hit_points=0, current_hit_points=0)
    session.add(char)
    await session.flush()  # assign id

    # Initialize ability scores at 10
    for ability in ABILITY_NAMES:
        session.add(AbilityScore(character_id=char.id, name=ability, value=10))

    # Initialize currency row
    session.add(Currency(character_id=char.id))

    await session.flush()
    await session.refresh(char, attribute_names=[
        "classes", "ability_scores", "spells", "spell_slots",
        "items", "currency", "abilities", "maps",
    ])
    return char


# ---------------------------------------------------------------------------
# Get full
# ---------------------------------------------------------------------------

@router.get("/{char_id}", response_model=CharacterFull)
async def get_character(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Character:
    return await _get_owned(char_id, user_id, session, full=True)


# ---------------------------------------------------------------------------
# Update (identity / metadata fields)
# ---------------------------------------------------------------------------

@router.patch("/{char_id}", response_model=CharacterFull)
async def update_character(
    char_id: int,
    body: CharacterUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Character:
    char = await _get_owned(char_id, user_id, session, full=True)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(char, field, value)
    return char


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@router.delete("/{char_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    char = await _get_owned(char_id, user_id, session)

    # Auto-leave any active session where this character is pinned as a player.
    # GM participants have character_id=None so they're never matched here.
    participant_q = (
        select(SessionParticipant)
        .join(GameSession, GameSession.id == SessionParticipant.session_id)
        .where(
            SessionParticipant.user_id == user_id,
            SessionParticipant.character_id == char.id,
            GameSession.status == SessionStatus.ACTIVE,
        )
    )
    participant = (await session.execute(participant_q)).scalar_one_or_none()
    if participant is not None:
        game_session = await session.get(GameSession, participant.session_id)
        await session.delete(participant)
        if game_session is not None:
            game_session.last_activity_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M")

    await session.delete(char)


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

@router.patch("/{char_id}/skills", response_model=CharacterFull)
async def update_skills(
    char_id: int,
    body: SkillsUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Character:
    char = await _get_owned(char_id, user_id, session, full=True)
    current = dict(char.skills or {})
    current.update(body.skills)
    char.skills = current
    return char


# ---------------------------------------------------------------------------
# Saving Throws
# ---------------------------------------------------------------------------

@router.patch("/{char_id}/saving_throws", response_model=CharacterFull)
async def update_saving_throws(
    char_id: int,
    body: SavingThrowsUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Character:
    char = await _get_owned(char_id, user_id, session, full=True)
    current = dict(char.saving_throws or {})
    current.update(body.saving_throws)
    char.saving_throws = current
    return char


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------

@router.patch("/{char_id}/conditions", response_model=CharacterFull)
async def update_conditions(
    char_id: int,
    body: ConditionsUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Character:
    char = await _get_owned(char_id, user_id, session, full=True)
    old_conditions = dict(char.conditions or {})
    current = dict(old_conditions)
    current.update(body.conditions)
    char.conditions = current

    # Log changes to history
    for cond, new_val in body.conditions.items():
        old_val = old_conditions.get(cond, False)
        if new_val != old_val:
            if cond == "exhaustion":
                _add_history(session, char.id, "condition_change",
                             f"Spossatezza: livello {old_val} → {new_val}")
            elif new_val:
                _add_history(session, char.id, "condition_change",
                             f"Condizione attivata: {cond}")
            else:
                _add_history(session, char.id, "condition_change",
                             f"Condizione rimossa: {cond}")

    return char


# ---------------------------------------------------------------------------
# Inspiration
# ---------------------------------------------------------------------------

@router.patch("/{char_id}/inspiration", response_model=CharacterFull)
async def update_inspiration(
    char_id: int,
    body: InspirationUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Character:
    char = await _get_owned(char_id, user_id, session, full=True)
    char.heroic_inspiration = body.heroic_inspiration
    return char


# ---------------------------------------------------------------------------
# Experience Points
# ---------------------------------------------------------------------------

@router.patch("/{char_id}/xp", response_model=CharacterFull)
async def update_xp(
    char_id: int,
    body: XPUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Character:
    char = await _get_owned(char_id, user_id, session, full=True)
    if body.set is not None:
        char.experience_points = max(0, body.set)
    elif body.add is not None:
        char.experience_points = max(0, (char.experience_points or 0) + body.add)

    # For single-class characters, keep class level in sync with XP-derived level.
    if len(char.classes) == 1:
        cls = char.classes[0]
        new_level = xp_to_level(char.experience_points)
        if new_level != cls.level:
            cls.level = new_level
            update_resources_for_level(cls.class_name, new_level, list(cls.resources), char)
            existing_names = {r.name for r in cls.resources}
            for res_data in get_resources_for_class(cls.class_name, new_level, char):
                if res_data["name"] not in existing_names:
                    session.add(ClassResource(class_id=cls.id, **res_data))

    return char


# ---------------------------------------------------------------------------
# Skill roll
# ---------------------------------------------------------------------------

@router.post("/{char_id}/skills/{skill_name}/roll", response_model=RollResult)
async def roll_skill(
    char_id: int,
    skill_name: str,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RollResult:
    if skill_name not in _SKILL_ABILITY:
        raise HTTPException(status_code=400, detail=f"Unknown skill: {skill_name}")
    char = await _get_owned(char_id, user_id, session, full=True)

    ability_name = _SKILL_ABILITY[skill_name]
    score = next((s for s in char.ability_scores if s.name == ability_name), None)
    ability_mod = score.modifier if score else 0

    skills: dict = char.skills or {}
    level = skills.get(skill_name)
    pb = char.proficiency_bonus
    if level == "expert":
        bonus = ability_mod + 2 * pb
    elif level is True or level == 1:
        bonus = ability_mod + pb
    else:
        bonus = ability_mod

    die = random.randint(1, 20)
    total = die + bonus
    is_crit = die == 20
    is_fumble = die == 1

    _add_history(session, char.id, "skill_roll",
                 f"Abilità {skill_name}: d20={die} {'+ ' if bonus >= 0 else ''}{bonus} = {total}"
                 + (" (CRITICO)" if is_crit else " (FUMBLE)" if is_fumble else ""))

    return RollResult(
        die=die,
        bonus=bonus,
        total=total,
        is_critical=is_crit,
        is_fumble=is_fumble,
        description=skill_name,
    )


# ---------------------------------------------------------------------------
# Saving throw roll
# ---------------------------------------------------------------------------

@router.post("/{char_id}/saving_throws/{ability}/roll", response_model=RollResult)
async def roll_saving_throw(
    char_id: int,
    ability: str,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RollResult:
    if ability not in ABILITY_NAMES:
        raise HTTPException(status_code=400, detail=f"Unknown ability: {ability}")
    char = await _get_owned(char_id, user_id, session, full=True)

    score = next((s for s in char.ability_scores if s.name == ability), None)
    ability_mod = score.modifier if score else 0

    saves: dict = char.saving_throws or {}
    is_proficient = bool(saves.get(ability, False))
    pb = char.proficiency_bonus
    bonus = ability_mod + (pb if is_proficient else 0)

    die = random.randint(1, 20)
    total = die + bonus
    is_crit = die == 20
    is_fumble = die == 1

    _add_history(session, char.id, "saving_throw",
                 f"TS {ability}: d20={die} {'+ ' if bonus >= 0 else ''}{bonus} = {total}"
                 + (" (CRITICO)" if is_crit else " (FUMBLE)" if is_fumble else ""))

    return RollResult(
        die=die,
        bonus=bonus,
        total=total,
        is_critical=is_crit,
        is_fumble=is_fumble,
        description=ability,
    )
