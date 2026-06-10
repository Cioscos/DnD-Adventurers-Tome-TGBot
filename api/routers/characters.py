"""Character CRUD endpoints."""

from __future__ import annotations

import random
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user, get_current_lang
from api.database import get_db
from core.db.models import (
    AbilityScore,
    ABILITY_NAMES,
    Character,
    CharacterClass,
    CharacterHistory,
    Currency,
    GameSession,
    SessionParticipant,
    SessionStatus,
)
from core.data.xp_thresholds import xp_to_level
from core.data.labels import ability_label, skill_label
from api.services.class_features import sync_class_feature_abilities
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
from api.routers.classes import create_class_for_character
from api.routers._helpers import prune_history
from api.services import telegram_notify
from api.services.character_response import build_character_response
from api.services.effects import apply_conditions
from api.services.spell_slots import recalc_spell_slots

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
        selectinload(Character.classes),
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


async def _refresh_char_full(
    session: AsyncSession, char_id: int, user_id: int
) -> Character:
    """Flush pending mutations, then re-SELECT a fully-loaded character.

    Use this in PATCH endpoints that mutate ``char.*`` and return
    ``CharacterFull`` via FastAPI's ``response_model``. A bare
    ``session.refresh(char, attribute_names=[...])`` is insufficient: it
    re-runs each relation's *default* loader strategy (lazy="select") and
    strips the nested ``selectinload`` chains set up by ``_full_load()`` —
    notably ``classes.resources``. Pydantic serialization of the nested
    ``CharacterClassRead.resources`` list field then either triggers
    ``MissingGreenlet`` (lazy-load in sync context) or silently returns an
    empty list — in either case, newly-added ``ClassResource`` rows from the
    same transaction never appear in the response body.

    The reliable fix is to ``session.expunge_all()`` (autoflush may have
    pulled related objects into the identity map; ``expunge(char)`` alone
    isn't enough) and then re-issue the full eager-load query. This matches
    the pattern already used by ``create_character`` after the
    ``initial_class`` branch.

    Caller pattern: replace ``await session.refresh(char, attribute_names=[
    "classes", ...]); return char`` with ``return await _refresh_char_full(
    session, char.id, user_id)``.
    """
    await session.flush()
    session.expunge_all()
    return await _get_owned(char_id, user_id, session, full=True)


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
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    char = Character(user_id=user_id, name=body.name, hit_points=0, current_hit_points=0)
    # Populate ability scores + currency via the relationships (not raw
    # character_id FKs) so the in-memory collections are loaded before the
    # flush. This lets create_class_for_character read char.ability_scores
    # for the CON/HP bootstrap without triggering a lazy-load in the async
    # (sync-attribute) context — which would raise MissingGreenlet. The
    # cascade="all, delete-orphan" on both relationships persists them.
    char.ability_scores = [
        AbilityScore(name=ability, value=10) for ability in ABILITY_NAMES
    ]
    char.currency = Currency()
    # Inizializza la collection abilities in memoria così che il sync delle
    # feature di classe (in create_class_for_character) non tenti un lazy-load
    # in contesto async (MissingGreenlet). Mirror di ability_scores/currency.
    char.abilities = []
    # Stesso motivo: create_class_for_character fa `if cls not in char.classes`.
    # Su un char appena flushato (persistente) la collection classes non è
    # caricata, quindi senza questa init l'accesso scatena un lazy-load async →
    # MissingGreenlet (rompe POST /characters con initial_class).
    char.classes = []
    # Apply optional identity in the SAME transaction (atomic create). Same
    # field→column mapping as update_character; set before flush so it lands
    # in the initial INSERT.
    if body.identity is not None:
        for field, value in body.identity.model_dump(exclude_unset=True).items():
            setattr(char, field, value)
    session.add(char)
    await session.flush()  # assign id (cascades ability_scores + currency)

    # Optional atomic initial class. The whole request runs inside one
    # transaction (api.database.get_db middleware) — any exception here
    # rolls back the character + ability_scores + currency too.
    if body.initial_class is not None:
        await create_class_for_character(
            char, body.initial_class, session, is_first_class=True, lang=lang,
        )

    # Re-fetch with selectinload so all relations are eagerly loaded for
    # response serialization. See _refresh_char_full for the full rationale.
    char = await _refresh_char_full(session, char.id, user_id)
    # Seed spell slots for a caster initial class (automatic mode is the default).
    await recalc_spell_slots(session, char)
    return await build_character_response(session, char)


# ---------------------------------------------------------------------------
# Get full
# ---------------------------------------------------------------------------

@router.get("/{char_id}", response_model=CharacterFull)
async def get_character(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned(char_id, user_id, session, full=True)
    return await build_character_response(session, char)


# ---------------------------------------------------------------------------
# Update (identity / metadata fields)
# ---------------------------------------------------------------------------

@router.patch("/{char_id}", response_model=CharacterFull)
async def update_character(
    char_id: int,
    body: CharacterUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned(char_id, user_id, session, full=True)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(char, field, value)
    # Flush + re-SELECT so CharacterFull serialization sees a non-expired row
    # AND nested eager-loads (classes.resources) survive. See
    # _refresh_char_full() for the full rationale.
    char = await _refresh_char_full(session, char_id, user_id)
    # Re-derive spell slots when automatic mode is active (e.g. the user just
    # switched manual → automatic, or edited a class through this endpoint).
    await recalc_spell_slots(session, char)
    return await build_character_response(session, char)


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
) -> CharacterFull:
    char = await _get_owned(char_id, user_id, session, full=True)
    current = dict(char.skills or {})
    current.update(body.skills)
    char.skills = current
    # See _refresh_char_full() for why expunge + re-SELECT is required here.
    char = await _refresh_char_full(session, char_id, user_id)
    return await build_character_response(session, char)


# ---------------------------------------------------------------------------
# Saving Throws
# ---------------------------------------------------------------------------

@router.patch("/{char_id}/saving_throws", response_model=CharacterFull)
async def update_saving_throws(
    char_id: int,
    body: SavingThrowsUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned(char_id, user_id, session, full=True)
    current = dict(char.saving_throws or {})
    current.update(body.saving_throws)
    char.saving_throws = current
    # See _refresh_char_full() for why expunge + re-SELECT is required here.
    char = await _refresh_char_full(session, char_id, user_id)
    return await build_character_response(session, char)


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------

@router.patch("/{char_id}/conditions", response_model=CharacterFull)
async def update_conditions(
    char_id: int,
    body: ConditionsUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned(char_id, user_id, session, full=True)
    result = await apply_conditions(session, char, body.conditions)
    if result["changed"]:
        await prune_history(session, char)

    # See _refresh_char_full() for why expunge + re-SELECT is required here.
    # The CharacterHistory side-effect rows added above are exactly the kind
    # of mutation that triggers autoflush → column expiration during response
    # serialization.
    char = await _refresh_char_full(session, char_id, user_id)
    return await build_character_response(session, char)


# ---------------------------------------------------------------------------
# Inspiration
# ---------------------------------------------------------------------------

@router.patch("/{char_id}/inspiration", response_model=CharacterFull)
async def update_inspiration(
    char_id: int,
    body: InspirationUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned(char_id, user_id, session, full=True)
    char.heroic_inspiration = body.heroic_inspiration
    # See _refresh_char_full() for why expunge + re-SELECT is required here.
    char = await _refresh_char_full(session, char_id, user_id)
    return await build_character_response(session, char)


# ---------------------------------------------------------------------------
# Experience Points
# ---------------------------------------------------------------------------

@router.patch("/{char_id}/xp", response_model=CharacterFull)
async def update_xp(
    char_id: int,
    body: XPUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    char = await _get_owned(char_id, user_id, session, full=True)
    old_xp = char.experience_points or 0
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
            await sync_class_feature_abilities(session, char, cls, lang=lang)

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

    # Notifica best-effort: solo all'attraversamento di soglia (categoria level_up)
    old_level_from_xp = xp_to_level(old_xp)
    new_level_from_xp = xp_to_level(char.experience_points)
    if (
        new_level_from_xp > old_level_from_xp
        and telegram_notify.notifications_enabled(char, "level_up")
    ):
        if len(char.classes) == 1:
            text = f"🎉 {char.name} è salito al livello {new_level_from_xp}!"
        else:
            text = f"✨ Level-up disponibile per {char.name} (liv. {new_level_from_xp})!"
        await telegram_notify.send_telegram_message(
            user_id, text,
            button=("Apri Esperienza",
                    telegram_notify.miniapp_url(f"/char/{char_id}/xp")),
        )

    # Re-SELECT so model_validate sees non-expired columns AND the freshly
    # generated class-feature Ability rows are loaded via selectinload. See
    # _refresh_char_full() for the full rationale.
    fresh = await _refresh_char_full(session, char_id, user_id)

    # Single-class level may have changed above; re-derive spell slots when
    # automatic mode is active so the XP-driven level-up grows the slots.
    await recalc_spell_slots(session, fresh)

    result = await build_character_response(session, fresh)
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
        f"Abilità {skill_label(skill_name)}: d20={die} {'+ ' if bonus >= 0 else ''}{bonus} = {total}"
        + (" (CRITICO)" if is_crit else " (FUMBLE)" if is_fumble else "")
    )
    if body and body.with_inspiration:
        history_msg = f"Reroll ispirazione: {history_msg}"
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
        f"TS {ability_label(ability)}: d20={die} {'+ ' if bonus >= 0 else ''}{bonus} = {total}"
        + (" (CRITICO)" if is_crit else " (FUMBLE)" if is_fumble else "")
    )
    if body and body.with_inspiration:
        history_msg = f"Reroll ispirazione: {history_msg}"
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
