"""Character CRUD endpoints."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.services.history import add_history
from api.auth import get_current_user, get_current_lang
from api.database import get_db
from core.db.models import (
    Ability,
    AbilityScore,
    ABILITY_NAMES,
    Character,
    CharacterClass,
    ConditionEffect,
    Currency,
    Item,
    PendingSave,
    GameSession,
    CampaignMember,
    SessionParticipant,
    SessionStatus,
)
from core.data.xp_thresholds import xp_to_level
from core.rules.subclasses import sync_subclass_keys
from core.data.skills import SKILL_ABILITY_MAP
from api.services.skills import check_bonus, skill_bonus
from core.data.labels import ability_label, condition_label, skill_label
from api.services.choices import take_feat
from api.services.class_features import sync_cataloged_features, sync_class_feature_abilities
from core.rules.feature_sync import ABILITY_BONUS_KEY, ARCHIVED_FEATURES, GRANTED_CREATED, GRANTED_SPELL_KEYS, REPLACED_AT_REST, RETROFIT_DONE
from core.rules.level_choices import FREE_KNOWN_KEY, sync_level_choices
from core.rules.states import ALLY_EXCLUSIVE, COND_RELEASE, SPELL_CAST_TYPE, SPELL_GIVEN, SPELL_RELEASE, SPELL_SPENT, SUSPENDED_KEY, SUSPENDED_ON, TARGET_IMMUNITY, SPELL_TEMP_DROPPED, TEMP_GIVEN, TEMP_RELEASE, ZERO_HP_USES, release_given_spells
from core.game.stats import AC_MIGRATED_FLAG, hit_points_for_level, roll_ability_mod
from core.rules.proficiencies import FEATURE_GRANTS_KEY, SEEDED_FLAG
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
from api.schemas.condition_effects import PendingSaveRead, PendingSaveRollResult
from api.routers.classes import create_class_for_character
from api.routers.sessions import active_encounter_row
from api.services.rules_targets import activate_pending_effect, drop_pending_effect
from core.game.item_bonuses import item_bonus_total
from core.game.actions import HIDE_MIN_TOTAL
from api.routers._helpers import effective_ability_mod, effective_con_mod, prune_history, saving_throw_bonus
from api.services import telegram_notify
from api.services.d20 import d20_history_label, d20_records, resolve_body, spend_inspiration_reroll
from api.services.rules_options import (
    LAST_ROLL_FIELDS,
    merge_options,
    option_result,
    remember_roll,
    roll_option_dice,
    use_options,
)
from api.services.effects import cap_current_hp, sync_zero_hp
from core.data.spell_slots import normalize_class_name
from core.rules.edition import character_edition
from core.rules.starting_equipment import ASSASSIN_KITS_FLAG, resolve as resolve_starting_equipment, starting_groups
from api.services.rules_turn import get_turn, refuse_if_incapacitated
from api.services.session_allies import attach_party_auras, attach_spell_auras
from core.rules.modifiers import ac_delta, effective_hp_max, modifiers_for, rule_hp_bonus
from api.services.dice_stats import record_dice
from api.services.character_response import build_character_response
from api.services.effects import apply_conditions
from api.services.condition_effects import ExpirySpec, effects_for_character, pending_read, upsert_effect
from api.services.durations import tick_rounds
from api.services.spell_slots import CREATED_SLOTS, recalc_spell_slots
from api.services.hp_rolls import record_rolls, stored_rolls
from api.services.homebrew.passive import get_passive_modifiers
from api.services.character_load import full_load, get_owned, refresh_char_full

router = APIRouter(prefix="/characters", tags=["characters"])

# settings keys written only by server endpoints (level-up, conditions, rounds tick, cast).
SERVER_OWNED_SETTINGS = ("hp_rolls", "condition_durations", "resolved_choice_levels",
                         "concentration_rounds_left", REPLACED_AT_REST, "concentration_item_spell", ARCHIVED_FEATURES,
                         GRANTED_SPELL_KEYS, GRANTED_CREATED, ABILITY_BONUS_KEY, ZERO_HP_USES, TARGET_IMMUNITY, FREE_KNOWN_KEY,
                         RETROFIT_DONE, ALLY_EXCLUSIVE, TEMP_GIVEN, TEMP_RELEASE, SPELL_GIVEN, SPELL_RELEASE, SPELL_SPENT, SPELL_TEMP_DROPPED, SPELL_CAST_TYPE, SUSPENDED_KEY, COND_RELEASE, SUSPENDED_ON, CREATED_SLOTS,
                         "saved_dice", "knocked_out", "hiding", "inspiration_extra", AC_MIGRATED_FLAG,
                         SEEDED_FLAG, FEATURE_GRANTS_KEY, ASSASSIN_KITS_FLAG)

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


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@router.get("", response_model=list[CharacterSummary])
async def list_characters(
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> list[CharacterSummary]:
    result = await session.execute(
        select(Character)
        .options(selectinload(Character.classes), selectinload(Character.items), selectinload(Character.ability_scores),
                 selectinload(Character.abilities))  # i talenti (Robusto) contano nei PF massimi
        .where(Character.user_id == user_id)
        .order_by(Character.id)
    )
    summaries: list[CharacterSummary] = []
    for c in result.scalars().all():
        summary = CharacterSummary.model_validate(c)
        # Modificatori passivi homebrew, coerenti con la scheda completa.
        summary.hp_max_homebrew_modifier = await get_passive_modifiers(
            session, c, "character.hit_points_max"
        )
        summary.ac_homebrew_modifier = await get_passive_modifiers(
            session, c, "character.ac"
        )
        summary.ac_items_modifier = item_bonus_total(c.items, "ac")
        summary.ac += ac_delta(c, summary.ac, summary.ac_items_modifier + summary.ac_homebrew_modifier)
        summary.hp_max_effective = effective_hp_max(c, summary.hp_max_homebrew_modifier)
        summaries.append(summary)
    return summaries


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

_SHORT_ABILITY = {a[:3]: a for a in ABILITY_NAMES}
_ROLL_NOTE_KEY = re.compile(r"^(save\.(%s)|skill\.(%s))$" % ("|".join(ABILITY_NAMES), "|".join(SKILL_ABILITY_MAP)))


def _apply_creation_extras(char: Character, body: CharacterCreate) -> None:
    """Scores (+species bonuses), species fields, skills; 422 on invalid input."""
    def bad(msg: str):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, msg)

    scores = {a: 10 for a in ABILITY_NAMES}
    for k, v in (body.ability_scores or {}).items():
        if k not in scores:
            raise bad(f"Unknown ability: {k}")
        scores[k] = v
    sp = body.species
    if sp:
        for k, v in sp.ability_bonuses.items():
            full = _SHORT_ABILITY.get(k, k)
            if full not in scores:
                raise bad(f"Unknown ability bonus: {k}")
            scores[full] += v
        for k, v in sp.roll_notes.items():
            if not _ROLL_NOTE_KEY.match(k) or len(v) > 120:
                raise bad(f"Invalid roll note: {k}")
    if body.ability_scores or sp:
        if any(not 3 <= v <= 20 for v in scores.values()):
            raise bad("Ability scores must be between 3 and 20")
        for row in char.ability_scores:
            row.value = scores[row.name]
    if body.skills:
        if any(k not in SKILL_ABILITY_MAP for k in body.skills):
            raise bad("Unknown skill")
        char.skills = {k: bool(v) for k, v in body.skills.items()}
    if sp:
        char.race = sp.name
        if sp.speed_ft is not None:
            char.speed = sp.speed_ft
        s = dict(char.settings or {})
        if sp.senses:
            s["senses"] = [x.model_dump() for x in sp.senses]
        if sp.roll_notes:
            s["roll_notes"] = dict(sp.roll_notes)
        char.settings = s
        langs = list(char.languages or [])
        char.languages = langs + [l for l in sp.languages if l not in langs]


def _add_starting_equipment(char: Character, body: CharacterCreate, lang: str) -> None:
    """Equipaggiamento di partenza (Task 47): oggetti normali non equipaggiati e monete, nessun effetto."""
    try:
        rows, gold = resolve_starting_equipment(
            body.rules_edition, normalize_class_name(body.initial_class.class_name) or "", body.starting_equipment, lang)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    for r in rows:
        meta = r.pop("item_metadata")
        char.items.append(Item(**r, item_metadata=json.dumps(meta) if meta else None))
    char.currency.gold += gold
    char.recalculate_encumbrance()


@router.post("", response_model=CharacterFull, status_code=status.HTTP_201_CREATED)
async def create_character(
    body: CharacterCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    if body.starting_equipment is not None and (
        body.initial_class is None or not starting_groups(body.rules_edition, normalize_class_name(body.initial_class.class_name) or "")
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_starting_equipment")
    char = Character(user_id=user_id, name=body.name, hit_points=0, current_hit_points=0,
                     rules_edition=body.rules_edition)
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
    char.abilities = [
        Ability(name=t.name, description=t.description, is_passive=True)
        for t in (body.species.traits if body.species else [])
    ]
    # Stesso motivo: create_class_for_character fa `if cls not in char.classes`.
    # Su un char appena flushato (persistente) la collection classes non è
    # caricata, quindi senza questa init l'accesso scatena un lazy-load async →
    # MissingGreenlet (rompe POST /characters con initial_class).
    char.classes = []
    char.items = []  # Stesso motivo: gli usi a catalogo leggono la caratteristica effettiva.
    # Apply optional identity in the SAME transaction (atomic create). Same
    # field→column mapping as update_character; set before flush so it lands
    # in the initial INSERT.
    if body.identity is not None:
        for field, value in body.identity.model_dump(exclude_unset=True).items():
            setattr(char, field, value)
    _apply_creation_extras(char, body)  # after identity so species languages merge
    session.add(char)
    await session.flush()  # assign id (cascades ability_scores + currency)

    # Optional atomic initial class. The whole request runs inside one
    # transaction (api.database.get_db middleware) — any exception here
    # rolls back the character + ability_scores + currency too.
    if body.initial_class is not None:
        await create_class_for_character(
            char, body.initial_class, session, is_first_class=True, lang=lang,
        )
        if body.starting_equipment is not None:
            _add_starting_equipment(char, body, lang)

    if body.origin_feat:  # nella stessa transazione: un talento non valido annulla tutta la creazione
        take_feat(session, char, body.origin_feat, None, lang, "creation")
        await sync_cataloged_features(session, char, lang)
        if char.current_hit_points >= char.hit_points:  # nasce a PF pieni anche col massimo alzato (Robusto)
            char.current_hit_points = effective_hp_max(char)

    # Re-fetch with selectinload so all relations are eagerly loaded for
    # response serialization. See refresh_char_full for the full rationale.
    char = await refresh_char_full(session, char.id, user_id)
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
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CharacterFull:
    char = await get_owned(char_id, user_id, session, full=True)
    response = await build_character_response(session, char, persist=False)
    if char.hp_undo:  # l'annullo resta raggiungibile dopo un ricaricamento, finché il server lo accetterebbe
        from api.routers.hp import undo_op_id
        response.hp_undo_id = await undo_op_id(session, char)
    return response


# ---------------------------------------------------------------------------
# Update (identity / metadata fields)
# ---------------------------------------------------------------------------

@router.patch("/{char_id}", response_model=CharacterFull)
async def update_character(
    char_id: int,
    body: CharacterUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    char = await get_owned(char_id, user_id, session, full=True)
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "settings" and value is not None:
            # Server-owned keys: a stale client snapshot must never overwrite them.
            old = char.settings or {}
            value = {k: v for k, v in value.items() if k not in SERVER_OWNED_SETTINGS}
            value.update({k: old[k] for k in SERVER_OWNED_SETTINGS if k in old})
        setattr(char, field, value)
    if "rules_edition" in body.model_fields_set:
        sync_subclass_keys(char)  # una sottoclasse assente nell'altra edizione resta solo testo
        await sync_cataloged_features(session, char, lang)
    # Flush + re-SELECT so CharacterFull serialization sees a non-expired row
    # AND nested eager-loads (classes.resources) survive. See
    # refresh_char_full() for the full rationale.
    char = await refresh_char_full(session, char_id, user_id)
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
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> None:
    char = await get_owned(char_id, user_id, session)

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

    await session.execute(delete(CampaignMember).where(CampaignMember.character_id == char.id))
    release_given_spells(char, [{"key": clock} for clock in (char.settings or {}).get(SPELL_GIVEN) or {}])  # i bersagli perdono gli effetti
    await session.flush()
    await session.delete(char)


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

@router.patch("/{char_id}/skills", response_model=CharacterFull)
async def update_skills(
    char_id: int,
    body: SkillsUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CharacterFull:
    char = await get_owned(char_id, user_id, session, full=True)
    current = dict(char.skills or {})
    current.update(body.skills)
    char.skills = current
    # See refresh_char_full() for why expunge + re-SELECT is required here.
    char = await refresh_char_full(session, char_id, user_id)
    return await build_character_response(session, char)


# ---------------------------------------------------------------------------
# Saving Throws
# ---------------------------------------------------------------------------

@router.patch("/{char_id}/saving_throws", response_model=CharacterFull)
async def update_saving_throws(
    char_id: int,
    body: SavingThrowsUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CharacterFull:
    char = await get_owned(char_id, user_id, session, full=True)
    current = dict(char.saving_throws or {})
    current.update(body.saving_throws)
    char.saving_throws = current
    # See refresh_char_full() for why expunge + re-SELECT is required here.
    char = await refresh_char_full(session, char_id, user_id)
    return await build_character_response(session, char)


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------

@router.patch("/{char_id}/conditions", response_model=CharacterFull)
async def update_conditions(
    char_id: int,
    body: ConditionsUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CharacterFull:
    char = await get_owned(char_id, user_id, session, full=True)
    result = await apply_conditions(session, char, body.conditions)
    # apply_conditions already dropped the effects of conditions turned off
    gm_slugs = {e.slug for e in await effects_for_character(session, char_id) if e.applied_by_gm}
    for slug, rounds in (body.durations or {}).items():
        if slug != "exhaustion" and rounds and rounds > 0 and (char.conditions or {}).get(slug) and slug not in gm_slugs:
            await upsert_effect(session, ("character", char_id), slug,
                                expiry=ExpirySpec("owner", "start", rounds))
    if result["changed"]:
        await prune_history(session, char)

    # See refresh_char_full() for why expunge + re-SELECT is required here.
    # The CharacterHistory side-effect rows added above are exactly the kind
    # of mutation that triggers autoflush → column expiration during response
    # serialization.
    char = await refresh_char_full(session, char_id, user_id)
    return await build_character_response(session, char)


@router.post("/{char_id}/hide", response_model=CharacterFull)
async def hide(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CharacterFull:
    """Azione Nascondersi 2024: l'ultima prova di Furtività, salvata dal server, di almeno 15 (con le condizioni
    confermate dal giocatore) rende Invisibili; il totale è la CD per trovarti. Nel 2014 l'esito lo decide il DM."""
    char = await get_owned(char_id, user_id, session, full=True)
    if character_edition(char) != "2024":
        raise HTTPException(status_code=422, detail={"code": "hide_2024_only"})
    refuse_if_incapacitated(char)
    last = get_turn(char).get("last_roll") or {}
    if last.get("roll") != "skill" or last.get("skill") != "stealth":
        raise HTTPException(status_code=409, detail={"code": "no_stealth_roll"})
    total = last["total"]
    if total < HIDE_MIN_TOTAL:
        raise HTTPException(status_code=409, detail={"code": "hide_failed"})
    # Nascondersi di nuovo mentre ci si nasconde già: l'Invisibilità di prima è del nascondiglio, non di un'altra fonte.
    hiding = (char.settings or {}).get("hiding")
    was_invisible = bool(hiding.get("was_invisible")) if hiding else bool((char.conditions or {}).get("invisible"))
    await apply_conditions(session, char, {"invisible": True})
    char.settings = {**(char.settings or {}), "hiding": {"dc": total, "was_invisible": was_invisible}}
    char = await refresh_char_full(session, char_id, user_id)
    return await build_character_response(session, char)


@router.post("/{char_id}/rounds/tick", response_model=CharacterFull)
async def tick_round(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CharacterFull:
    char = await get_owned(char_id, user_id, session, full=True)
    if await active_encounter_row(session, char_id) is not None:
        # In combat the turn edges drive durations: a manual tick would double-count.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"code": "in_encounter"})
    expired = await tick_rounds(session, char)
    await prune_history(session, char)
    char = await refresh_char_full(session, char_id, user_id)
    resp = await build_character_response(session, char)
    resp.expired_effects = expired
    return resp


# ---------------------------------------------------------------------------
# Inspiration
# ---------------------------------------------------------------------------

@router.patch("/{char_id}/inspiration", response_model=CharacterFull)
async def update_inspiration(
    char_id: int,
    body: InspirationUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CharacterFull:
    char = await get_owned(char_id, user_id, session, full=True)
    settings = dict(char.settings or {})
    if body.heroic_inspiration and char.heroic_inspiration and character_edition(char) == "2024":
        settings["inspiration_extra"] = True  # se ne ha una sola: questa è da cedere a chi ne è privo, o persa
    else:
        settings.pop("inspiration_extra", None)
    char.settings = settings
    char.heroic_inspiration = body.heroic_inspiration
    # See refresh_char_full() for why expunge + re-SELECT is required here.
    char = await refresh_char_full(session, char_id, user_id)
    return await build_character_response(session, char)


@router.delete("/{char_id}/inspiration/extra", response_model=CharacterFull)
async def discard_extra_inspiration(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CharacterFull:
    """Scarta l'Ispirazione ricevuta in più che non si vuole cedere: quella propria resta."""
    char = await get_owned(char_id, user_id, session, full=True)
    if not (char.settings or {}).get("inspiration_extra"):
        raise HTTPException(status_code=409, detail={"code": "no_extra_inspiration"})
    char.settings = {k: v for k, v in char.settings.items() if k != "inspiration_extra"}
    char = await refresh_char_full(session, char_id, user_id)
    return await build_character_response(session, char)


# ---------------------------------------------------------------------------
# Experience Points
# ---------------------------------------------------------------------------

@router.patch("/{char_id}/xp", response_model=CharacterFull)
async def update_xp(
    char_id: int,
    body: XPUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    char = await get_owned(char_id, user_id, session, full=True)
    old_xp = char.experience_points or 0
    if body.set is not None:
        char.experience_points = max(0, body.set)
    elif body.add is not None:
        char.experience_points = max(0, (char.experience_points or 0) + body.add)

    settings = char.settings or {}
    auto_calc = settings.get("hp_auto_calc", True)

    total_hp_gained = 0
    old_hp_bonus = rule_hp_bonus(char)  # Resilienza Draconica: sale con il livello da stregone

    # Milestone mode: level-ups go through classes/distribute, never from XP.
    milestone = settings.get("advancement") == "milestone"

    # For single-class characters, keep class level in sync with XP-derived level.
    # hp_rolls only make sense for a single class in XP mode (others use the level-up modal).
    if body.hp_rolls is not None and (milestone or len(char.classes) != 1):
        raise HTTPException(status_code=422, detail="hp_rolls_not_applicable")
    if len(char.classes) == 1 and not milestone:
        cls = char.classes[0]
        old_level = cls.level
        new_level = xp_to_level(char.experience_points)
        if new_level != old_level or body.hp_rolls:
            cls.level = new_level
            lost_rolls = stored_rolls(char).get(cls.id, {})  # read before record_rolls drops them
            # Validates hp_rolls (count/range -> 422) and drops stale rolls. Omitted rolls in
            # rolled mode fall back to the fixed value so older clients keep working.
            record_rolls(char, cls, old_level, new_level, body.hp_rolls)
            sync_level_choices(char, cls, old_level, new_level)
            await sync_class_feature_abilities(session, char, cls, lang=lang)

            con_mod = effective_con_mod(char)
            if auto_calc and cls.hit_die and new_level < old_level:
                # Symmetric to level-up: each lost level gives back its stored roll or the fixed value.
                lost = sum(
                    max(1, lost_rolls[lvl] + effective_con_mod(char)) if lvl in lost_rolls
                    else hit_points_for_level(cls.hit_die, con_mod, max(2, lvl))
                    for lvl in range(new_level + 1, old_level + 1)
                )
                char.hit_points = max(1, char.hit_points - lost)
                char.current_hit_points = min(char.current_hit_points, effective_hp_max(char))
            if auto_calc and cls.hit_die and new_level > old_level:
                for lvl in range(old_level + 1, new_level + 1):
                    if body.hp_rolls:
                        # rolled: roll + effective CON, min 1
                        total_hp_gained += max(1, body.hp_rolls[lvl - old_level - 1] + effective_con_mod(char))
                    else:
                        # level 1 was handled at character creation; always use level 2+ formula
                        total_hp_gained += hit_points_for_level(cls.hit_die, con_mod, max(2, lvl))

    if auto_calc and rule_hp_bonus(char) > old_hp_bonus:  # come i PF del livello, il massimo in più si aggiunge anche ai correnti
        total_hp_gained_current = total_hp_gained + rule_hp_bonus(char) - old_hp_bonus
    else:
        total_hp_gained_current = total_hp_gained
    if total_hp_gained_current > 0:
        was_at_zero = char.current_hit_points == 0
        char.hit_points += total_hp_gained
        char.current_hit_points += total_hp_gained_current
        await cap_current_hp(session, char)
        await sync_zero_hp(session, char, was_at_zero)

    # Notifica best-effort: solo all'attraversamento di soglia (categoria level_up)
    old_level_from_xp = xp_to_level(old_xp)
    new_level_from_xp = xp_to_level(char.experience_points)
    if (
        not milestone
        and new_level_from_xp > old_level_from_xp
        and telegram_notify.notifications_enabled(char, "level_up")
    ):
        if len(char.classes) == 1:
            text = f"🎉 {char.name} è salito al livello {new_level_from_xp}!"
        else:
            text = f"✨ Level-up disponibile per {char.name} (liv. {new_level_from_xp})!"
        telegram_notify.send_detached(telegram_notify.send_telegram_message(
            user_id, text,
            button=("Apri Esperienza",
                    telegram_notify.miniapp_url(f"/char/{char_id}/xp")),
        ))

    # Re-SELECT so model_validate sees non-expired columns AND the freshly
    # generated class-feature Ability rows are loaded via selectinload. See
    # refresh_char_full() for the full rationale.
    fresh = await refresh_char_full(session, char_id, user_id)

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
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    body: Annotated[D20RollSubmission | None, Body()] = None,
) -> RollResult:
    if skill_name not in _SKILL_ABILITY:
        raise HTTPException(status_code=400, detail=f"Unknown skill: {skill_name}")
    char = await get_owned(char_id, user_id, session, full=True)

    if body and body.with_inspiration:
        spend_inspiration_reroll(char)

    await attach_spell_auras(session, char)  # le aure vive dei compagni (Passare Senza Tracce)
    opts = use_options(session, char, "skill", body, skill=skill_name, ability=_SKILL_ABILITY[skill_name])
    # Una prova fatta con un'altra caratteristica (Conoscenza Primordiale) è a tutti gli effetti quella: bonus e modificatori.
    ability = opts.ability_override or _SKILL_ABILITY[skill_name]
    bonus = await check_bonus(session, char, ability, skill_name) if opts.ability_override else await skill_bonus(session, char, skill_name)

    applied = modifiers_for(char, "skill", skill=skill_name, ability=ability)
    merge_options(applied, opts)
    outcome = resolve_body(body, applied)
    die = outcome.kept
    option_rolls, option_total = roll_option_dice(char, opts)
    bonus += opts.bonus
    raw_total = die + bonus + option_total
    # Totale minimo (Potenza Indomabile): il tiro ricordato dal server resta senza, il minimo si rimette a ogni ritocco.
    total = raw_total if applied.min_total is None else max(raw_total, applied.min_total)
    is_crit = False  # una prova di abilità o di caratteristica non ha il critico (in 5e il 20 naturale conta solo per attacchi e tiri salvezza contro la morte)
    is_fumble = die == 1

    history_msg = (
        f"Abilità {skill_label(skill_name)}: {d20_history_label(outcome)} {'+ ' if bonus >= 0 else ''}{bonus} = {total}"
        + (" (FUMBLE)" if is_fumble else "")
        + (" (fallimento automatico)" if applied.auto_fail else "")
    )
    if body and body.with_inspiration:
        history_msg = f"Reroll ispirazione: {history_msg}"
    add_history(session, char.id, "skill_roll", history_msg)
    record_dice(char, d20_records(outcome))
    await prune_history(session, char)

    result = RollResult(
        die=die,
        dice=outcome.dice,
        mode=outcome.mode,
        mode_applied=outcome.mode,
        notes=applied.notes,
        auto_fail=applied.auto_fail,
        bonus=bonus,
        total=total,
        is_critical=is_crit,
        is_fumble=is_fumble,
        description=skill_name,
        option_result=option_result(opts, option_rolls, option_total),
    )
    remember_roll(char, "skill", opts, {**result.model_dump(mode="json", include=LAST_ROLL_FIELDS), "total": raw_total},
                  skill=skill_name, ability=ability)
    return result


# ---------------------------------------------------------------------------
# Ability check roll (prova di caratteristica pura, R35)
# ---------------------------------------------------------------------------

@router.post("/{char_id}/ability_checks/{ability}/roll", response_model=RollResult)
async def roll_ability_check(
    char_id: int,
    ability: str,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    body: Annotated[D20RollSubmission | None, Body()] = None,
) -> RollResult:
    """Prova di caratteristica senza abilità (spingere, sollevare, spezzare): modificatore, nessuna competenza, stessi
    modi, opzioni al tiro e cronologia di ``skills/roll``. Per il catalogo il tiro è ``ability``."""
    if ability not in ABILITY_NAMES:
        raise HTTPException(status_code=400, detail=f"Unknown ability: {ability}")
    char = await get_owned(char_id, user_id, session, full=True)

    if body and body.with_inspiration:
        spend_inspiration_reroll(char)

    await attach_spell_auras(session, char)
    applied = modifiers_for(char, "ability", ability=ability)
    bonus = await check_bonus(session, char, ability)
    opts = use_options(session, char, "ability", body, ability=ability)
    merge_options(applied, opts)
    outcome = resolve_body(body, applied)
    die = outcome.kept
    option_rolls, option_total = roll_option_dice(char, opts)
    bonus += opts.bonus
    raw_total = die + bonus + option_total
    total = raw_total if applied.min_total is None else max(raw_total, applied.min_total)
    is_crit = False
    is_fumble = die == 1

    history_msg = (
        f"Prova di {ability_label(ability)}: {d20_history_label(outcome)} {'+ ' if bonus >= 0 else ''}{bonus} = {total}"
        + (" (FUMBLE)" if is_fumble else "")
        + (" (fallimento automatico)" if applied.auto_fail else "")
    )
    if body and body.with_inspiration:
        history_msg = f"Reroll ispirazione: {history_msg}"
    add_history(session, char.id, "skill_roll", history_msg)
    record_dice(char, d20_records(outcome))
    await prune_history(session, char)

    result = RollResult(
        die=die, dice=outcome.dice, mode=outcome.mode, mode_applied=outcome.mode, notes=applied.notes,
        auto_fail=applied.auto_fail, bonus=bonus, total=total, is_critical=is_crit, is_fumble=is_fumble,
        description=ability, option_result=option_result(opts, option_rolls, option_total),
    )
    remember_roll(char, "ability", opts, {**result.model_dump(mode="json", include=LAST_ROLL_FIELDS), "total": raw_total},
                  ability=ability)
    return result


# ---------------------------------------------------------------------------
# Saving throw roll
# ---------------------------------------------------------------------------

@router.post("/{char_id}/saving_throws/{ability}/roll", response_model=RollResult)
async def roll_saving_throw(
    char_id: int,
    ability: str,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    body: Annotated[D20RollSubmission | None, Body()] = None,
) -> RollResult:
    if ability not in ABILITY_NAMES:
        raise HTTPException(status_code=400, detail=f"Unknown ability: {ability}")
    char = await get_owned(char_id, user_id, session, full=True)

    if body and body.with_inspiration:
        spend_inspiration_reroll(char)

    bonus = await saving_throw_bonus(session, char, ability)

    applied = modifiers_for(char, "save", ability=ability)
    await attach_party_auras(session, char)
    opts = use_options(session, char, "save", body, ability=ability)
    merge_options(applied, opts)
    outcome = resolve_body(body, applied)
    die = outcome.kept
    option_rolls, option_total = roll_option_dice(char, opts)
    bonus += opts.bonus
    raw_total = die + bonus + option_total
    # Totale minimo (Potenza Indomabile 2024): il tiro ricordato dal server resta senza, il minimo si rimette a ogni ritocco.
    total = raw_total if applied.min_total is None else max(raw_total, applied.min_total)
    is_crit = die == 20 and not applied.auto_fail
    is_fumble = die == 1

    history_msg = (
        f"TS {ability_label(ability)}: {d20_history_label(outcome)} {'+ ' if bonus >= 0 else ''}{bonus} = {total}"
        + (" (CRITICO)" if is_crit else " (FUMBLE)" if is_fumble else "")
        + (" (fallimento automatico)" if applied.auto_fail else "")
    )
    if body and body.with_inspiration:
        history_msg = f"Reroll ispirazione: {history_msg}"
    add_history(session, char.id, "saving_throw", history_msg)
    record_dice(char, d20_records(outcome))
    await prune_history(session, char)

    result = RollResult(
        die=die,
        dice=outcome.dice,
        mode=outcome.mode,
        mode_applied=outcome.mode,
        notes=applied.notes,
        auto_fail=applied.auto_fail,
        bonus=bonus,
        total=total,
        is_critical=is_crit,
        is_fumble=is_fumble,
        description=ability,
        option_result=option_result(opts, option_rolls, option_total),
    )
    remember_roll(char, "save", opts, {**result.model_dump(mode="json", include=LAST_ROLL_FIELDS), "total": raw_total},
                  ability=ability)
    return result


# ---------------------------------------------------------------------------
# Pending (repeated) saving throws on condition effects
# ---------------------------------------------------------------------------

async def _owned_pending_save(session: AsyncSession, char_id: int, psid: int) -> PendingSave:
    ps = await session.get(PendingSave, psid)
    if ps is None or ps.character_id != char_id:
        raise HTTPException(status_code=404, detail="Pending save not found")
    return ps


async def close_pending_save(
    session: AsyncSession, char: Character, ps: PendingSave, effect: ConditionEffect, roll: dict,
) -> tuple[PendingSaveRead, bool]:
    """Registra l'esito del TS e, se riuscito, libera dalla condizione. ``roll`` è ciò che resta in ``ps.last_roll``."""
    passed = roll["total"] >= ps.dc and not roll["auto_fail"]
    ps.status = "passed" if passed else "failed"
    ps.resolved_at = datetime.utcnow().isoformat(timespec="seconds")
    ps.last_roll = {**roll, "passed": passed}
    # Build the read model before apply_conditions deletes the effect and its saves.
    save_read = pending_read(ps, effect.slug)
    if effect.pending:  # effetto di un privilegio: il TS decide se la condizione esiste, nulla di preesistente si tocca
        if passed:
            await drop_pending_effect(session, effect)
        else:
            await activate_pending_effect(session, effect)
            add_history(session, char.id, "condition_change", f"Condizione subita: {condition_label(effect.slug)}")
        return save_read, passed
    if passed:
        add_history(session, char.id, "condition_change", f"Liberato da: {condition_label(effect.slug)}")
        await apply_conditions(session, char, {effect.slug: False})
    await session.flush()
    return save_read, passed


async def open_failed_save(session: AsyncSession, char: Character, psid: int) -> tuple[PendingSave, ConditionEffect]:
    """Il TS in sospeso del tiro appena fatto, se fallito e ancora ritoccabile; altrimenti 409."""
    ps = await session.get(PendingSave, psid)
    if ps is None:  # riuscito: la condizione e i suoi TS non ci sono più
        raise HTTPException(status_code=409, detail={"code": "no_last_roll"})
    effect = await session.get(ConditionEffect, ps.effect_id)
    newer = (await session.execute(select(PendingSave.id).where(
        PendingSave.effect_id == ps.effect_id, PendingSave.id > ps.id))).first()
    if effect is None or ps.status != "failed" or ps.dismissed or newer or not (char.conditions or {}).get(effect.slug):
        raise HTTPException(status_code=409, detail={"code": "not_rerollable"})
    return ps, effect


@router.post("/{char_id}/pending-saves/{psid}/roll", response_model=PendingSaveRollResult)
async def roll_pending_save(
    char_id: int,
    psid: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    body: Annotated[D20RollSubmission | None, Body()] = None,
) -> PendingSaveRollResult:
    char = await get_owned(char_id, user_id, session, full=True)
    ps = await _owned_pending_save(session, char_id, psid)
    reroll = bool(body and body.with_inspiration)

    effect = await session.get(ConditionEffect, ps.effect_id)
    if effect is None or not (effect.pending or (char.conditions or {}).get(effect.slug)):
        ps.dismissed = True
        await session.commit()  # persist before the 409 (get_db rolls back on errors)
        raise HTTPException(status_code=409, detail={"code": "condition_gone"})
    if ps.status == "pending":
        if reroll:
            raise HTTPException(status_code=409, detail={"code": "not_rerollable"})
    else:
        newer = (await session.execute(select(PendingSave.id).where(
            PendingSave.effect_id == ps.effect_id, PendingSave.id > ps.id))).first()
        if ps.status != "failed" or not reroll or newer:
            raise HTTPException(status_code=409, detail={"code": "not_rerollable"})
        if not char.heroic_inspiration:
            raise HTTPException(status_code=409, detail={"code": "inspiration_unavailable"})
    if reroll:
        spend_inspiration_reroll(char)

    bonus = await saving_throw_bonus(session, char, ps.ability)
    applied = modifiers_for(char, "save", ability=ps.ability)
    await attach_party_auras(session, char)
    opts = use_options(session, char, "save", body, ability=ps.ability)
    merge_options(applied, opts)
    outcome = resolve_body(body, applied)
    die = outcome.kept
    option_rolls, option_total = roll_option_dice(char, opts)
    bonus += opts.bonus
    raw_total = die + bonus + option_total
    total = raw_total if applied.min_total is None else max(raw_total, applied.min_total)
    is_crit, is_fumble = die == 20 and not applied.auto_fail, die == 1

    history_msg = (
        f"TS {ability_label(ps.ability)} per {condition_label(effect.slug)}: "
        f"{d20_history_label(outcome)} {'+ ' if bonus >= 0 else ''}{bonus} = {total} (CD {ps.dc})"
        + (" (fallimento automatico)" if applied.auto_fail else "")
    )
    if reroll:
        history_msg = f"Reroll ispirazione: {history_msg}"
    add_history(session, char.id, "saving_throw", history_msg)
    record_dice(char, d20_records(outcome))
    await prune_history(session, char)

    save_read, passed = await close_pending_save(session, char, ps, effect, {
        "die": die, "dice": outcome.dice, "bonus": bonus, "total": total, "mode": outcome.mode,
        "auto_fail": applied.auto_fail, "notes": applied.notes,
    })
    result = RollResult(die=die, dice=outcome.dice, mode=outcome.mode, mode_applied=outcome.mode,
                        notes=applied.notes, auto_fail=applied.auto_fail, bonus=bonus, total=total,
                        is_critical=is_crit, is_fumble=is_fumble, description=save_read.ability,
                        option_result=option_result(opts, option_rolls, option_total))
    remember_roll(char, "save", opts, {**result.model_dump(mode="json", include=LAST_ROLL_FIELDS), "total": raw_total},
                  ability=save_read.ability, pending_save_id=psid)
    return PendingSaveRollResult(save=save_read, passed=passed, condition_removed=passed, roll=result)


@router.post("/{char_id}/pending-saves/{psid}/dismiss", status_code=204)
async def dismiss_pending_save(
    char_id: int,
    psid: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> None:
    await get_owned(char_id, user_id, session)
    ps = await _owned_pending_save(session, char_id, psid)
    if ps.status not in ("failed", "passed"):
        raise HTTPException(status_code=409, detail={"code": "not_dismissable"})
    ps.dismissed = True
