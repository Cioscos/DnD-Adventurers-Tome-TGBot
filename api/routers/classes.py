"""Multiclass and class resource endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user, get_current_lang
from api.database import get_db
from core.db.models import Character, CharacterClass
from api.schemas.character import CharacterFull
from api.schemas.common import (
    CharacterClassCreate,
    CharacterClassRead,
    CharacterClassUpdate,
    ClassDistribute,
)
from core.data.classes import (
    CLASS_HIT_DIE,
    CLASS_SPELLCASTING,
    get_saving_throw_proficiencies,
)
from api.services.class_features import sync_class_feature_abilities
from core.data.xp_thresholds import xp_to_level
from core.game.stats import hit_points_for_level, total_base_hp
from api.routers._helpers import collect_homebrew_notifications, effective_con_mod
from api.services.homebrew.dispatcher import dispatch
from api.services.character_response import build_character_response
from api.services.spell_slots import recalc_spell_slots

router = APIRouter(prefix="/characters", tags=["classes"])


async def _get_owned_full(char_id: int, user_id: int, session: AsyncSession) -> Character:
    result = await session.execute(
        select(Character)
        .options(
            selectinload(Character.classes),
            selectinload(Character.ability_scores),
            selectinload(Character.spells),
            selectinload(Character.spell_slots),
            selectinload(Character.items),
            selectinload(Character.currency),
            selectinload(Character.abilities),
            selectinload(Character.maps),
        )
        .where(Character.id == char_id)
    )
    char = result.scalar_one_or_none()
    if char is None:
        raise HTTPException(status_code=404, detail="Character not found")
    if char.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your character")
    return char


async def _refresh_char_full(char_id: int, user_id: int, session: AsyncSession) -> Character:
    """Flush pending mutations, then re-SELECT a fully-loaded character.

    Mirror of ``api.routers.characters._refresh_char_full`` (duplicated here to
    avoid a circular import: characters.py already imports from classes.py).
    A bare in-memory ``char`` whose ``classes.resources`` collection was loaded
    by an earlier ``selectinload`` will NOT contain ``ClassResource`` rows added
    in the same transaction — serializing it drops them (finding #6). ``expire``
    alone is insufficient (autoflush may pull related objects into the identity
    map), so we ``expunge_all()`` and re-issue the full eager-load query.
    """
    await session.flush()
    session.expunge_all()
    return await _get_owned_full(char_id, user_id, session)


async def _get_class(class_id: int, char_id: int, session: AsyncSession) -> CharacterClass:
    result = await session.execute(
        select(CharacterClass)
        .where(CharacterClass.id == class_id, CharacterClass.character_id == char_id)
    )
    cls = result.scalar_one_or_none()
    if cls is None:
        raise HTTPException(status_code=404, detail="Class not found")
    return cls


async def create_class_for_character(
    char: Character,
    body: CharacterClassCreate,
    session: AsyncSession,
    *,
    is_first_class: bool | None = None,
    lang: str = "it",
) -> CharacterClass:
    """Insert a CharacterClass + class-feature Ability rows + run the auto-HP bootstrap.

    Shared between POST /characters (atomic create-with-initial-class) and
    POST /characters/{id}/classes. The caller is responsible for committing
    the surrounding transaction. Any exception raised here aborts the
    surrounding transaction (auto-rollback in get_db middleware).

    `is_first_class` lets the caller declare whether this is the first class
    on the character; when None we compute it from char.classes (requires
    that relationship to be loaded).
    """
    if is_first_class is None:
        is_first_class = len(char.classes) == 0

    hit_die = body.hit_die
    spellcasting_ability = body.spellcasting_ability
    if body.class_name in CLASS_HIT_DIE:
        if hit_die is None:
            hit_die = CLASS_HIT_DIE[body.class_name]
        if spellcasting_ability is None:
            spellcasting_ability = CLASS_SPELLCASTING.get(body.class_name)

    cls = CharacterClass(
        character_id=char.id,
        class_name=body.class_name,
        level=body.level,
        subclass=body.subclass,
        spellcasting_ability=spellcasting_ability,
        hit_die=hit_die,
    )
    session.add(cls)
    await session.flush()

    # char.abilities deve essere caricato per il sync (selectinload in _get_owned_full).
    if getattr(char, "abilities", None) is None:
        char.abilities = []
    # cls deve essere visibile in char.classes per coerenza del sync.
    if cls not in char.classes:
        char.classes.append(cls)
    await sync_class_feature_abilities(session, char, cls, lang=lang)

    # Seed saving throw proficiencies from the *starting* class only (D&D 5e:
    # multiclassing does not grant additional save proficiencies). We only fill
    # in saves not already present so we never clobber user-set proficiencies.
    if is_first_class:
        class_saves = get_saving_throw_proficiencies(body.class_name)
        if class_saves:
            current_saves = dict(char.saving_throws or {})
            for ability, proficient in class_saves.items():
                current_saves.setdefault(ability, proficient)
            char.saving_throws = current_saves

    settings = char.settings or {}
    auto_calc = settings.get("hp_auto_calc", True)
    if is_first_class and char.hit_points == 0 and auto_calc and hit_die:
        con_row = next((a for a in char.ability_scores if a.name == "constitution"), None)
        con_mod = (con_row.value - 10) // 2 if con_row else 0
        hp = hit_points_for_level(hit_die, con_mod, 1)
        char.hit_points = hp
        char.current_hit_points = hp
        await session.flush()

    return cls


# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

@router.post("/{char_id}/classes", response_model=CharacterFull, status_code=201)
async def add_class(
    char_id: int,
    body: CharacterClassCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)
    await create_class_for_character(char, body, session, lang=lang)
    session.expire(char)
    char = await _get_owned_full(char_id, user_id, session)
    await recalc_spell_slots(session, char)
    return await build_character_response(session, char)


@router.patch("/{char_id}/classes/distribute", response_model=CharacterFull)
async def distribute_class_levels(
    char_id: int,
    body: ClassDistribute,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    """Atomically redistribute class levels.

    Validates that:
    1. Every entry's `class_id` belongs to the character.
    2. The body covers every existing class (no missing nor extra ids).
    3. `sum(level)` equals `xp_to_level(char.experience_points)`.

    On success, updates each class's level, syncs predefined class-feature
    abilities (grow or shrink via `sync_class_feature_abilities`),
    and recalculates HP proportionally if `settings.hp_auto_calc` is true.
    """
    char = await _get_owned_full(char_id, user_id, session)

    existing_ids = {cls.id for cls in char.classes}
    body_ids = {entry.class_id for entry in body.classes}
    if existing_ids != body_ids:
        raise HTTPException(status_code=400, detail="classes_mismatch")

    target_sum = xp_to_level(char.experience_points or 0)
    new_sum = sum(entry.level for entry in body.classes)
    # Allow sum <= target (multi-pending level-up applies +1 per commit and
    # reopens the modal for remaining levels). Reject only sum > target,
    # which would exceed the character's XP-derived level cap.
    if new_sum > target_sum:
        raise HTTPException(status_code=400, detail="sum_exceeds_target")
    if new_sum < 1:
        raise HTTPException(status_code=400, detail="sum_too_low")

    # Map id -> new_level for O(1) lookup
    new_levels = {entry.class_id: entry.level for entry in body.classes}

    # Snapshot old total HP for ratio scaling
    old_total_hp = char.hit_points or 0
    old_current_hp = char.current_hit_points or 0

    # Apply level changes + resource sync
    for cls in char.classes:
        new_level = new_levels[cls.id]
        if new_level == cls.level:
            continue
        cls.level = new_level
        await sync_class_feature_abilities(session, char, cls, lang=lang)

    # HP recalc (respecting hp_auto_calc); populate hp_gained for toast parity with PATCH /xp
    settings = char.settings or {}
    hp_gained = 0
    if settings.get("hp_auto_calc", True):
        con_mod = effective_con_mod(char)
        new_total_hp = total_base_hp(char.classes, con_mod)
        if old_total_hp > 0:
            ratio = old_current_hp / old_total_hp
            new_current = round(ratio * new_total_hp)
        else:
            new_current = old_current_hp
        hp_gained = max(0, new_total_hp - old_total_hp)
        char.hit_points = new_total_hp
        char.current_hit_points = max(0, min(new_current, new_total_hp))

    # Re-fetch so newly-inserted ClassResource rows (e.g. Punti Ki on a fresh
    # Monaco level) appear in the response — otherwise the FE multiclass card
    # misses them until a reload (finding #6).
    char = await _refresh_char_full(char_id, user_id, session)
    await recalc_spell_slots(session, char)
    result = await build_character_response(session, char)
    if hp_gained > 0:
        result.hp_gained = hp_gained
    return result


# Note: keep static paths (e.g. /classes/distribute) declared BEFORE this
# parametric {class_id} route — FastAPI matches in declaration order.
@router.patch("/{char_id}/classes/{class_id}", response_model=CharacterFull)
async def update_class(
    char_id: int,
    class_id: int,
    body: CharacterClassUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)
    # Usa la stessa istanza tracciata in char.classes (così le nuove Ability
    # puntano al source_class_id corretto e il sync vede le esistenti).
    cls = next((c for c in char.classes if c.id == class_id), None)
    if cls is None:
        raise HTTPException(status_code=404, detail="Class not found")
    old_level = cls.level
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(cls, field, value)

    # When level changes, sync class-feature abilities for predefined classes.
    if body.level is not None and body.level != old_level:
        await sync_class_feature_abilities(session, char, cls, lang=lang)

    # Flush pending setattr mutations before any relationship traversal —
    # `CharacterFull.model_validate(char)` (and dispatch's `total_level`
    # access via `_char_to_ctx_dict`) would otherwise trip SQLAlchemy
    # autoflush during attribute access (sync context → "greenlet_spawn
    # has not been called").
    await session.flush()
    await session.refresh(char, attribute_names=["classes"])

    # Emit level_up event for installed homebrew rules.
    # DEVIATION FROM PLAN LITERAL: plan says `if new_level != old_level`, which
    # would fire on level decreases too. We restrict to actual UP transitions
    # (`> old_level`) since the canonical effect — apply_modifier_once granting
    # +HP per level — is asymmetric and meaningless on level-down. A future
    # `level_down` event can be added if rules need to react to demotions.
    notifications: list[dict] = []
    if body.level is not None and body.level > old_level:
        firing = await dispatch(
            session,
            char,
            "level_up",
            {
                "class_name": cls.class_name,
                "new_level": cls.level,
                "old_level": old_level,
                "total_level_new": char.total_level,
            },
        )
        notifications = collect_homebrew_notifications(firing)

    await recalc_spell_slots(session, char)
    response = await build_character_response(session, char)
    if notifications:
        response.homebrew_notifications = notifications
    return response


@router.delete("/{char_id}/classes/{class_id}", response_model=CharacterFull)
async def remove_class(
    char_id: int,
    class_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)
    cls = await _get_class(class_id, char_id, session)

    # Snapshot HP before the delete so we can scale current HP proportionally,
    # mirroring PATCH /classes/distribute.
    old_total_hp = char.hit_points or 0
    old_current_hp = char.current_hit_points or 0

    await session.delete(cls)
    await session.flush()
    session.expire(char)
    char = await _get_owned_full(char_id, user_id, session)

    # Removing a class lowers total_level → recalc max HP from the remaining
    # classes (finding #3: previously only spell slots were recalculated, leaving
    # "ghost" HP). Mirror the distribute block: ratio-scale current HP. With no
    # classes left, total_base_hp returns 0 → HP 0/0.
    settings = char.settings or {}
    if settings.get("hp_auto_calc", True):
        con_mod = effective_con_mod(char)
        new_total_hp = total_base_hp(char.classes, con_mod)
        if old_total_hp > 0:
            ratio = old_current_hp / old_total_hp
            new_current = round(ratio * new_total_hp)
        else:
            new_current = old_current_hp
        char.hit_points = new_total_hp
        char.current_hit_points = max(0, min(new_current, new_total_hp))
        await session.flush()

    await recalc_spell_slots(session, char)
    return await build_character_response(session, char)
