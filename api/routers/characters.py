"""Character CRUD endpoints."""

from __future__ import annotations

import random
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status
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
from core.game.stats import hit_points_for_level
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
from api.schemas.common import D20RollSubmission, RollResult
from api.routers.classes import create_class_for_character, _get_owned_full
from api.routers._helpers import prune_history

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
    return datetime.utcnow().isoformat(timespec="seconds")


def _add_history(
    session,
    char_id: int,
    event_type: str,
    description: str,
    meta: dict | None = None,
) -> None:
    session.add(CharacterHistory(
        character_id=char_id,
        timestamp=_now(),
        event_type=event_type,
        description=description,
        meta=meta,
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

    # Optional atomic initial class. The whole request runs inside one
    # transaction (api.database.get_db middleware) — any exception here
    # rolls back the character + ability_scores + currency too.
    if body.initial_class is not None:
        await create_class_for_character(
            char, body.initial_class, session, is_first_class=True,
        )
        await session.flush()
        # Re-fetch with selectinload so `classes.resources` (and the other
        # relations) are eagerly loaded for response serialization. A bare
        # `session.refresh(char, attribute_names=["classes"])` leaves
        # `cls.resources` unloaded and triggers MissingGreenlet during
        # Pydantic serialization. We expunge the in-memory `char` first so
        # the subsequent SELECT issues a fresh load (rather than returning
        # the cached object with empty `classes`).
        char_id = char.id
        session.expunge(char)
        return await _get_owned_full(char_id, user_id, session)

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
    # Flush + refresh so CharacterFull serialization sees a non-expired row.
    # Without this, autoflush during response_model validation can expire char
    # columns; `_resolve_abilities` then swallows the resulting lazy-load
    # exception via `try/except: continue`, silently dropping required fields
    # and returning 422. Same pattern as items.py and classes.py.
    await session.flush()
    await session.refresh(char, attribute_names=[
        "classes", "ability_scores", "spells", "spell_slots",
        "items", "currency", "abilities", "maps",
    ])
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
            game_session.last_activity_at = _now()

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
    # See update_character() for why flush + refresh is required here.
    await session.flush()
    await session.refresh(char, attribute_names=[
        "classes", "ability_scores", "spells", "spell_slots",
        "items", "currency", "abilities", "maps",
    ])
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
    # See update_character() for why flush + refresh is required here.
    await session.flush()
    await session.refresh(char, attribute_names=[
        "classes", "ability_scores", "spells", "spell_slots",
        "items", "currency", "abilities", "maps",
    ])
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
    changed = False
    for cond, new_val in body.conditions.items():
        is_exhaustion = cond == "exhaustion"
        default = 0 if is_exhaustion else False
        old_val = old_conditions.get(cond, default)
        if is_exhaustion:
            old_val = int(old_val) if isinstance(old_val, (int, bool)) and old_val is not None else 0
            new_val_display = int(new_val) if isinstance(new_val, (int, bool)) and new_val is not None else 0
        else:
            new_val_display = new_val
        if new_val_display != old_val:
            changed = True
            if is_exhaustion:
                _add_history(session, char.id, "condition_change",
                             f"Spossatezza: livello {old_val} → {new_val_display}")
            elif new_val:
                _add_history(session, char.id, "condition_change",
                             f"Condizione attivata: {cond}")
            else:
                _add_history(session, char.id, "condition_change",
                             f"Condizione rimossa: {cond}")

    if changed:
        await prune_history(session, char)

    # See update_character() for why flush + refresh is required here. The
    # CharacterHistory side-effect rows added above are exactly the kind of
    # mutation that triggers autoflush → column expiration during response
    # serialization.
    await session.flush()
    await session.refresh(char, attribute_names=[
        "classes", "ability_scores", "spells", "spell_slots",
        "items", "currency", "abilities", "maps",
    ])
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
    # See update_character() for why flush + refresh is required here.
    await session.flush()
    await session.refresh(char, attribute_names=[
        "classes", "ability_scores", "spells", "spell_slots",
        "items", "currency", "abilities", "maps",
    ])
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
) -> CharacterFull:
    char = await _get_owned(char_id, user_id, session, full=True)
    if body.set is not None:
        char.experience_points = max(0, body.set)
    elif body.add is not None:
        char.experience_points = max(0, (char.experience_points or 0) + body.add)

    settings = char.settings or {}
    auto_calc = settings.get("hp_auto_calc", True)

    total_hp_gained = 0

    # For single-class characters, keep class level in sync with XP-derived level.
    if len(char.classes) == 1:
        cls = char.classes[0]
        old_level = cls.level
        new_level = xp_to_level(char.experience_points)
        if new_level != old_level:
            cls.level = new_level
            update_resources_for_level(cls.class_name, new_level, list(cls.resources), char)
            existing_names = {r.name for r in cls.resources}
            for res_data in get_resources_for_class(cls.class_name, new_level, char):
                if res_data["name"] not in existing_names:
                    session.add(ClassResource(class_id=cls.id, **res_data))

            if auto_calc and cls.hit_die and new_level > old_level:
                con_row = next(
                    (a for a in char.ability_scores if a.name == "constitution"), None
                )
                con_mod = (con_row.value - 10) // 2 if con_row else 0
                for lvl in range(old_level + 1, new_level + 1):
                    # level 1 was handled at character creation; always use level 2+ formula
                    total_hp_gained += hit_points_for_level(cls.hit_die, con_mod, max(2, lvl))

    if total_hp_gained > 0:
        char.hit_points += total_hp_gained
        char.current_hit_points += total_hp_gained

    # Flush pending mutations (new ClassResource rows, level / HP updates) and
    # refresh char so model_validate sees non-expired columns. See
    # update_character() for the full rationale.
    await session.flush()
    await session.refresh(char, attribute_names=[
        "classes", "ability_scores", "spells", "spell_slots",
        "items", "currency", "abilities", "maps",
    ])

    result = CharacterFull.model_validate(char)
    if total_hp_gained > 0:
        result.hp_gained = total_hp_gained
    return result


# ---------------------------------------------------------------------------
# Skill roll
# ---------------------------------------------------------------------------

@router.post("/{char_id}/skills/{skill_name}/roll", response_model=RollResult)
async def roll_skill(
    char_id: int,
    skill_name: str,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    body: Annotated[D20RollSubmission | None, Body()] = None,
) -> RollResult:
    if skill_name not in _SKILL_ABILITY:
        raise HTTPException(status_code=400, detail=f"Unknown skill: {skill_name}")
    char = await _get_owned(char_id, user_id, session, full=True)

    if body and body.with_inspiration:
        if not char.heroic_inspiration:
            raise HTTPException(status_code=409, detail="Ispirazione non disponibile")
        char.heroic_inspiration = False

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

    die = body.die if body and body.die is not None else random.randint(1, 20)
    total = die + bonus
    is_crit = die == 20
    is_fumble = die == 1

    history_msg = (
        f"Abilità {skill_name}: d20={die} {'+ ' if bonus >= 0 else ''}{bonus} = {total}"
        + (" (CRITICO)" if is_crit else " (FUMBLE)" if is_fumble else "")
    )
    if body and body.with_inspiration:
        history_msg = f"Reroll ispirazione — {history_msg}"
    _add_history(session, char.id, "skill_roll", history_msg)
    await prune_history(session, char)

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
    body: Annotated[D20RollSubmission | None, Body()] = None,
) -> RollResult:
    if ability not in ABILITY_NAMES:
        raise HTTPException(status_code=400, detail=f"Unknown ability: {ability}")
    char = await _get_owned(char_id, user_id, session, full=True)

    if body and body.with_inspiration:
        if not char.heroic_inspiration:
            raise HTTPException(status_code=409, detail="Ispirazione non disponibile")
        char.heroic_inspiration = False

    score = next((s for s in char.ability_scores if s.name == ability), None)
    ability_mod = score.modifier if score else 0

    saves: dict = char.saving_throws or {}
    is_proficient = bool(saves.get(ability, False))
    pb = char.proficiency_bonus
    bonus = ability_mod + (pb if is_proficient else 0)

    die = body.die if body and body.die is not None else random.randint(1, 20)
    total = die + bonus
    is_crit = die == 20
    is_fumble = die == 1

    history_msg = (
        f"TS {ability}: d20={die} {'+ ' if bonus >= 0 else ''}{bonus} = {total}"
        + (" (CRITICO)" if is_crit else " (FUMBLE)" if is_fumble else "")
    )
    if body and body.with_inspiration:
        history_msg = f"Reroll ispirazione — {history_msg}"
    _add_history(session, char.id, "saving_throw", history_msg)
    await prune_history(session, char)

    return RollResult(
        die=die,
        bonus=bonus,
        total=total,
        is_critical=is_crit,
        is_fumble=is_fumble,
        description=ability,
    )
