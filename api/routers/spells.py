"""Spell management endpoints."""

from __future__ import annotations

import random
import uuid
from datetime import datetime
from types import SimpleNamespace
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.database import get_db
from core.db.models import Character, CharacterClass, CharacterHistory, Spell, SpellSlot
from api.schemas.character import CharacterFull, SpellAttackResult
from api.schemas.common import ConcentrationSaveResult, D20Dice, OptionResult, RollMode
from api.schemas.spell import (
    ConcentrationUpdate,
    LastDamageBody,
    RollDamageRequest,
    RollDamageResult,
    SpellAttackRequest,
    SpellCreate,
    SpellRead,
    SpellUpdate,
    SpellUseRequest,
)
from api.routers.items import _roll_dice, _DICE_RE
from api.services.durations import end_concentration, start_concentration
from api.services.effects import casts_verbally, end_hide
from api.services.condition_effects import release_concentration_effects
from core.game.actions import parse_duration_rounds
from api.routers._helpers import collect_homebrew_notifications, roll_concentration_save
from api.services.character_response import build_character_response
from api.services.d20 import d20_records, d20_history_label, resolve_body, spend_inspiration_reroll
from core.rules.modifiers import modifiers_for
from api.schemas.item import WeaponAttackResult
from core.rules.roll_options import scale_damage
from api.services.rules_options import merge_options, option_result, remember_roll, roll_option_dice, use_options
from api.services.rules_turn import get_turn, refuse_if_incapacitated
from api.services.dice_stats import record_dice
from api.services.homebrew.dispatcher import dispatch
from api.services.spellcasting import build_spellcasting_info, fill_spell_stats, prepared_class_room
from core.game.stats import cantrip_dice_multiplier
from core.rules.spellcasting import can_ritual, cast_warnings, casting_kind, spell_stats


class ConcentrationSaveRequest(BaseModel):
    damage: int
    mode: RollMode = "normal"
    dice: D20Dice | None = None

router = APIRouter(prefix="/characters", tags=["spells"])


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _add_history(session, char_id: int, event_type: str, description: str,
                 meta: dict | None = None) -> None:
    session.add(CharacterHistory(
        character_id=char_id,
        timestamp=_now(),
        event_type=event_type,
        description=description,
        meta=meta,
    ))


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


def _prepared_cap_error(count: int, cap: int, per_class: bool) -> HTTPException:
    return HTTPException(status_code=400, detail={"code": "prepared_cap", "n": count, "cap": cap, "per_class": per_class})


def _ensure_prepare_capacity(char: Character, class_id: int | None = None) -> None:
    """400 se il PG ha classi preparanti e il tetto, o quello della classe dell'incantesimo, è già raggiunto.

    Grandfathering: lo stato over-cap legacy resta valido — qui si bloccano
    solo i NUOVI prepare (count >= cap), mai gli unprepare.
    """
    room = prepared_class_room(char, class_id) if class_id else None
    if room and room[0] >= room[1]:
        raise _prepared_cap_error(room[0], room[1], True)
    info = build_spellcasting_info(char)
    if info.has_preparing_class and info.prepared_count >= (info.prepared_cap or 0):
        raise _prepared_cap_error(info.prepared_count, info.prepared_cap or 0, False)


def _check_class(char: Character, class_id: int | None) -> None:
    if class_id is not None and all(c.id != class_id for c in char.classes):
        raise HTTPException(status_code=400, detail={"code": "bad_class"})


def _pick_slot(char: Character, spell: Spell, slot_id: int | None, slot_level: int | None) -> SpellSlot:
    """``slot_id`` sceglie il pool. Col solo livello: la prima riga con posto, gli slot normali prima del patto."""
    if slot_id is not None:
        slot = next((s for s in char.spell_slots if s.id == slot_id), None)
        if slot is None:
            raise HTTPException(status_code=400, detail="Slot not found")
        slot_level = slot.level
    elif slot_level is None:
        raise HTTPException(status_code=400, detail="slot_level is required")
    if slot_level < spell.level:
        raise HTTPException(status_code=400, detail={"code": "slot_too_low"})
    if slot_id is None:
        rows = sorted((s for s in char.spell_slots if s.level == slot_level), key=lambda s: bool(s.is_pact))
        if not rows:
            raise HTTPException(status_code=400, detail=f"No slot configured for level {slot_level}")
        slot = next((s for s in rows if s.available > 0), rows[0])
    if slot.available == 0:
        raise HTTPException(status_code=400, detail=f"No slots available at level {slot_level}")
    return slot


def _mark_cast(char: Character, spell: Spell, spent_slot: bool) -> None:
    """Turno salvato per le regole sugli incantesimi nello stesso turno; le reazioni possono cadere fuori dal proprio."""
    kind = casting_kind(spell)
    if kind == "reaction":
        return
    turn = get_turn(char)
    turn["spell_slot_cast"] = turn["spell_slot_cast"] or spent_slot
    turn["bonus_spell_cast"] = turn["bonus_spell_cast"] or kind == "bonus"
    char.turn_state = turn


def _consume_cast(
    session, char: Character, spell: Spell, slot_id: int | None, slot_level: int | None, ritual: bool,
    confirm: list[str] | None = None,
) -> None:
    """Consuma il lancio (slot o rituale) e attiva la concentrazione. Un trucchetto non consuma nulla.

    Condiviso da /use e /attack. Una regola violata e non confermata risponde 409 ``cast_confirm`` prima di spendere.
    """
    if ritual:
        # Lancio rituale: +10 min, nessuno slot. Richiede il tag ritual e chi può celebrarlo per edizione.
        if not spell.is_ritual:
            raise HTTPException(status_code=400, detail="Spell is not a ritual")
        if not can_ritual(char):
            raise HTTPException(
                status_code=400, detail="No class with Ritual Casting"
            )
    slot = None if ritual or spell.level == 0 else _pick_slot(char, spell, slot_id, slot_level)
    missing = [w for w in cast_warnings(char, spell, ritual) if w not in (confirm or [])]
    if missing:
        raise HTTPException(status_code=409, detail={"code": "cast_confirm", "warnings": missing})

    if ritual:
        _add_history(
            session, char.id, "spell_ritual_cast",
            f"Lancio rituale: {spell.name}",
            meta={"ritual": True},
        )
    elif slot is not None:
        slot.use_slot()
        _add_history(session, char.id, "spell_cast",
                     f"Lanciato {spell.name} (slot {slot.level})",
                     meta={"slot_level": slot.level, **({"is_pact": True} if slot.is_pact else {})})
    else:
        _add_history(session, char.id, "spell_cast", f"Lanciato {spell.name}")
    _mark_cast(char, spell, slot is not None)
    if casts_verbally(spell):
        end_hide(session, char)

    if spell.is_concentration:
        start_concentration(char, spell.id, parse_duration_rounds(spell.duration))


@router.get("/{char_id}/spells", response_model=list[SpellRead])
async def list_spells(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = None,
) -> list[SpellRead]:
    char = await _get_owned_full(char_id, user_id, session)
    spells = char.spells
    if q:
        try:
            from rapidfuzz import process, fuzz
            names = [s.name for s in spells]
            matches = process.extract(q, names, scorer=fuzz.partial_ratio, limit=20, score_cutoff=40)
            matched_names = {m[0] for m in matches}
            spells = [s for s in spells if s.name in matched_names]
        except ImportError:
            spells = [s for s in spells if q.lower() in s.name.lower()]
    out = [SpellRead.model_validate(s) for s in spells]
    fill_spell_stats(char, out)
    return out


@router.post("/{char_id}/spells", response_model=SpellRead, status_code=201)
async def add_spell(
    char_id: int,
    body: SpellCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Spell:
    char = await _get_owned_full(char_id, user_id, session)
    _check_class(char, body.class_id)
    if body.is_prepared and body.level >= 1 and not body.always_prepared:
        _ensure_prepare_capacity(char, body.class_id)
    spell = Spell(character_id=char_id, **body.model_dump())
    spell.is_prepared = spell.is_prepared or body.always_prepared
    session.add(spell)
    await session.flush()
    return spell


@router.patch("/{char_id}/spells/{spell_id}", response_model=SpellRead)
async def update_spell(
    char_id: int,
    spell_id: int,
    body: SpellUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Spell:
    char = await _get_owned_full(char_id, user_id, session)
    result = await session.execute(
        select(Spell).where(Spell.id == spell_id, Spell.character_id == char_id)
    )
    spell = result.scalar_one_or_none()
    if spell is None:
        raise HTTPException(status_code=404, detail="Spell not found")
    data = body.model_dump(exclude_unset=True)
    _check_class(char, data.get("class_id"))
    if data.get("always_prepared") is None:
        data.pop("always_prepared", None)
    new_always = data.get("always_prepared", spell.always_prepared)
    if new_always:
        if data.get("is_prepared") is False:
            raise HTTPException(status_code=400, detail={"code": "always_prepared"})
        data["is_prepared"] = True
    new_level = data.get("level", spell.level)
    if data.get("is_prepared") is True and not spell.is_prepared and new_level >= 1 and not new_always:
        _ensure_prepare_capacity(char, data.get("class_id", spell.class_id))
    for field, value in data.items():
        setattr(spell, field, value)
    return spell


@router.delete("/{char_id}/spells/{spell_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_spell(
    char_id: int,
    spell_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    char = await _get_owned_full(char_id, user_id, session)
    result = await session.execute(
        select(Spell).where(Spell.id == spell_id, Spell.character_id == char_id)
    )
    spell = result.scalar_one_or_none()
    if spell is None:
        raise HTTPException(status_code=404, detail="Spell not found")
    if char.concentrating_spell_id == spell_id:
        end_concentration(char)
        await session.flush()
        await release_concentration_effects(session, char)
    await session.delete(spell)


@router.post("/{char_id}/spells/{spell_id}/use", response_model=CharacterFull)
async def use_spell(
    char_id: int,
    spell_id: int,
    body: SpellUseRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)

    # Verify the spell belongs to this character
    result = await session.execute(
        select(Spell).where(Spell.id == spell_id, Spell.character_id == char_id)
    )
    spell = result.scalar_one_or_none()
    if spell is None:
        raise HTTPException(status_code=404, detail="Spell not found")

    _consume_cast(session, char, spell, body.slot_id, body.slot_level, body.as_ritual, body.confirm)
    opts = use_options(session, char, "cast", body, spell=spell)
    rolls, total = roll_option_dice(char, opts)
    await release_concentration_effects(session, char)
    response = await build_character_response(session, char)
    response.option_result = option_result(opts, rolls, total)
    return response


@router.get("/{char_id}/spells/{spell_id}/cast-check", response_model=list[str])
async def cast_check(
    char_id: int,
    spell_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    ritual: bool = False,
) -> list[str]:
    """Le regole che questo lancio violerebbe, da confermare prima di tirare i dadi. Il lancio le ricontrolla."""
    char = await _get_owned_full(char_id, user_id, session)
    spell = next((s for s in char.spells if s.id == spell_id), None)
    if spell is None:
        raise HTTPException(status_code=404, detail="Spell not found")
    return cast_warnings(char, spell, ritual)


@router.post("/{char_id}/spells/{spell_id}/attack", response_model=SpellAttackResult)
async def spell_attack(
    char_id: int,
    spell_id: int,
    body: SpellAttackRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SpellAttackResult:
    char = await _get_owned_full(char_id, user_id, session)
    spell = next((s for s in char.spells if s.id == spell_id), None)
    if spell is None:
        raise HTTPException(status_code=404, detail="Spell not found")
    if (spell.attack_save or "").strip().upper() != "ATK":
        raise HTTPException(status_code=400, detail="Spell is not an attack spell")
    refuse_if_incapacitated(char)

    cast_block = None
    if body.with_inspiration:
        spend_inspiration_reroll(char)
    else:
        _consume_cast(session, char, spell, body.slot_id, body.slot_level, body.ritual, body.confirm)
        cast_body = SimpleNamespace(options=body.cast_options, option_inputs=body.cast_option_inputs)
        cast_opts = use_options(session, char, "cast", cast_body, spell=spell)
        cast_rolls, cast_total = roll_option_dice(char, cast_opts)
        cast_block = option_result(cast_opts, cast_rolls, cast_total)
    await release_concentration_effects(session, char)

    caster = spell_stats(char, spell)
    applied = modifiers_for(char, "attack", spell=spell)
    opts = use_options(session, char, "attack", body, spell=spell)
    merge_options(applied, opts)
    bonus = (caster.attack_bonus if caster else char.proficiency_bonus) + applied.flat + opts.bonus
    outcome = resolve_body(body, applied)
    die = outcome.kept
    total = die + bonus
    is_fumble = die == 1
    is_critical = die >= applied.crit_min or (opts.force_crit and not is_fumble)

    text = f"Attacco incantesimo {spell.name}: {d20_history_label(outcome)}+{bonus}={total}" + (
        " (CRITICO!)" if is_critical else " (FUMBLE!)" if is_fumble else ""
    )
    if body.with_inspiration:
        text = f"Reroll ispirazione: {text}"
    _add_history(session, char_id, "spell_attack", text)
    end_hide(session, char)
    record_dice(char, d20_records(outcome))

    firing = await dispatch(
        session, char, "attack_rolled",
        {
            "spell_id": spell.id,
            "to_hit_die": die,
            "to_hit_total": total,
            "is_critical": is_critical,
            "is_fumble": is_fumble,
        },
    )
    notifications = collect_homebrew_notifications(firing)
    remember_roll(char, "attack", opts, {
        "die": die, "dice": outcome.dice, "mode": outcome.mode, "bonus": bonus, "total": total,
        "notes": applied.notes, "auto_fail": False, "description": "",
    }, spell_id=spell.id)

    return SpellAttackResult(
        spell_name=spell.name,
        to_hit_die=die,
        dice=outcome.dice,
        mode=outcome.mode,
        mode_applied=outcome.mode,
        notes=applied.notes,
        to_hit_bonus=bonus,
        to_hit_total=total,
        is_critical=is_critical,
        is_fumble=is_fumble,
        caster_class=caster.class_name if caster else None,
        cast_option_result=cast_block,
        character=await build_character_response(session, char),
        homebrew_notifications=notifications or None,
    )


@router.patch("/{char_id}/concentration", response_model=CharacterFull)
async def update_concentration(
    char_id: int,
    body: ConcentrationUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)
    if body.spell_id is None:
        end_concentration(char)
    elif body.rounds is not None or body.spell_id != char.concentrating_spell_id:
        # Senza `rounds` sullo stesso incantesimo non cambia nulla: il lancio ha già avviato il contatore.
        spell = next((s for s in char.spells if s.id == body.spell_id), None)
        rounds = body.rounds if body.rounds is not None else parse_duration_rounds(spell.duration) if spell else None
        start_concentration(char, body.spell_id, rounds)
    await release_concentration_effects(session, char)
    return await build_character_response(session, char)


# ---------------------------------------------------------------------------
# Concentration saving throw
# ---------------------------------------------------------------------------

@router.post("/{char_id}/concentration/save", response_model=ConcentrationSaveResult)
async def concentration_save(
    char_id: int,
    body: ConcentrationSaveRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ConcentrationSaveResult:
    char = await _get_owned_full(char_id, user_id, session)
    return await roll_concentration_save(
        char, body.damage, session, body.mode, body.dice,
    )


# ---------------------------------------------------------------------------
# Spell damage roll
# ---------------------------------------------------------------------------

@router.post(
    "/{char_id}/spells/{spell_id}/roll_damage",
    response_model=RollDamageResult,
)
async def roll_spell_damage(
    char_id: int,
    spell_id: int,
    body: RollDamageRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RollDamageResult:
    char = await _get_owned_full(char_id, user_id, session)
    spell = next((s for s in char.spells if s.id == spell_id), None)
    if spell is None:
        raise HTTPException(status_code=404, detail="Spell not found")
    if not spell.damage_dice:
        raise HTTPException(status_code=400, detail="Spell has no damage_dice")

    casting_level = body.casting_level if body.casting_level is not None else spell.level
    if casting_level < spell.level:
        raise HTTPException(
            status_code=400,
            detail=f"casting_level {casting_level} < spell.level {spell.level}",
        )
    if casting_level > 9:
        raise HTTPException(status_code=400, detail="casting_level must be <= 9")

    # Parse spell.damage_dice using shared regex
    m = _DICE_RE.match(spell.damage_dice.strip())
    if not m:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid spell.damage_dice format: {spell.damage_dice!r}",
        )
    base_count = int(m.group(1))
    if spell.level == 0:
        base_count *= cantrip_dice_multiplier(char.total_level)
    sides = int(m.group(2))
    base_bonus = int(m.group(3)) if m.group(3) else 0
    # Upcast automatico: i dadi per livello extra si sommano ai dadi base (solo
    # incantesimi di livello >= 1, stessi lati). "sleep" no: i suoi dadi sono un pool di PF.
    if spell.level > 0 and spell.higher_levels_dice and spell.srd_index != "sleep":
        um = _DICE_RE.match(spell.higher_levels_dice.strip())
        if um and int(um.group(2)) == sides:
            base_count += int(um.group(1)) * (casting_level - spell.level)
            # Bonus fisso per livello (Dardo incantato: +1 per ogni dardo extra).
            base_bonus += int(um.group(3) or 0) * (casting_level - spell.level)

    # Apply critical (double dice count, not the flat bonus)
    dice_count = base_count * 2 if body.is_critical else base_count
    if body.main_rolls is not None:
        if len(body.main_rolls) != dice_count:
            raise HTTPException(
                status_code=400,
                detail=f"main_rolls length {len(body.main_rolls)} != expected {dice_count}",
            )
        if any(v < 1 or v > sides for v in body.main_rolls):
            raise HTTPException(
                status_code=400,
                detail=f"main_rolls values must be in [1, {sides}]",
            )
        main_rolls = list(body.main_rolls)
    else:
        main_rolls = [random.randint(1, sides) for _ in range(dice_count)]

    # Optional extra_dice
    extra_rolls: list[int] = []
    extra_bonus = 0
    extra_sides = 0
    if body.extra_dice:
        em = _DICE_RE.match(body.extra_dice)
        if em:
            e_count = int(em.group(1))
            extra_sides = int(em.group(2))
            extra_bonus = int(em.group(3)) if em.group(3) else 0
            extra_dice_count = e_count * 2 if body.is_critical else e_count
            if body.extra_rolls is not None:
                if len(body.extra_rolls) != extra_dice_count:
                    raise HTTPException(
                        status_code=400,
                        detail=f"extra_rolls length {len(body.extra_rolls)} != expected {extra_dice_count}",
                    )
                if any(v < 1 or v > extra_sides for v in body.extra_rolls):
                    raise HTTPException(
                        status_code=400,
                        detail=f"extra_rolls values must be in [1, {extra_sides}]",
                    )
                extra_rolls = list(body.extra_rolls)
            else:
                extra_rolls = [random.randint(1, extra_sides) for _ in range(extra_dice_count)]

    opts = use_options(session, char, "spell_damage", body, spell=spell)
    option_rolls, option_total = roll_option_dice(char, opts, body.is_critical)
    total = sum(main_rolls) + sum(extra_rolls) + base_bonus + extra_bonus + option_total + opts.bonus
    total = scale_damage(total, opts.multiplier)
    half_damage = total // 2  # per difetto, in entrambe le edizioni

    breakdown_parts = [f"{dice_count}d{sides}={main_rolls}"]
    if extra_rolls:
        breakdown_parts.append(f"+{len(extra_rolls)}d{extra_sides}={extra_rolls}")
    if base_bonus:
        breakdown_parts.append(f"{'+' if base_bonus >= 0 else ''}{base_bonus}")
    if extra_bonus:
        breakdown_parts.append(f"{'+' if extra_bonus >= 0 else ''}{extra_bonus}")
    if opts.keys:
        breakdown_parts.append(f"+{option_rolls}{opts.bonus:+d}" if option_rolls else f"{opts.bonus:+d}")
    breakdown = " ".join(breakdown_parts) + f" = {total}"

    record_dice(
        char,
        [(f"d{sides}", v) for v in main_rolls]
        + [(f"d{extra_sides}", v) for v in extra_rolls],
    )

    # Append to rolls_history if character supports it
    history_entry = {
        "type": "spell_damage",
        "spell_name": spell.name,
        "rolls": main_rolls + extra_rolls,
        "total": total,
        "damage_type": spell.damage_type,
        "casting_level": casting_level,
        "is_critical": body.is_critical,
    }
    if hasattr(char, "rolls_history") and isinstance(char.rolls_history, list):
        char.rolls_history.append(history_entry)
        await session.commit()

    main_kind = f"d{sides}"
    extra_kind = f"d{extra_sides}" if extra_rolls else None

    result = RollDamageResult(
        rolls=main_rolls + extra_rolls,
        total=total,
        half_damage=half_damage,
        damage_type=spell.damage_type,
        breakdown=breakdown,
        casting_level=casting_level,
        is_critical=bool(body.is_critical),
        scaled_dice=f"{base_count}d{sides}",
        main_kind=main_kind,
        main_rolls=main_rolls,
        option_result=option_result(opts, option_rolls, option_total),
        extra_kind=extra_kind,
        extra_rolls=extra_rolls,
    )
    # shortcut: i dadi delle opzioni restano nel fisso, non si ritirano; separarli se un privilegio lo richiede.
    turn = get_turn(char)
    turn["last_damage"] = {
        "roll_id": uuid.uuid4().hex, "spell_id": spell.id,
        "dice": [[sides, v] for v in main_rolls] + [[extra_sides, v] for v in extra_rolls],
        "main": len(main_rolls), "added": [], "multiplier": opts.multiplier,
        "flat": base_bonus + extra_bonus + option_total + opts.bonus,
        "result": result.model_dump(mode="json"),
    }
    char.turn_state = turn
    return result


@router.post("/{char_id}/last-damage/options", response_model=RollDamageResult | WeaponAttackResult)
async def last_damage_options(
    char_id: int,
    body: LastDamageBody,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RollDamageResult | WeaponAttackResult:
    """Privilegi usati dopo aver visto i dadi di danno (incantesimo o arma). Il tiro è quello salvato dal server."""
    char = await _get_owned_full(char_id, user_id, session)
    last = get_turn(char).get("last_damage")
    weapon = bool(last) and last.get("kind") == "weapon"
    spell = next((s for s in char.spells if last and not weapon and s.id == last["spell_id"]), None)
    if not last or (not weapon and spell is None):
        raise HTTPException(status_code=409, detail={"code": "no_last_damage"})
    opts = use_options(session, char, "weapon_damage" if weapon else "spell_damage", body, phase="after_damage",
                       spell=spell)

    dice = [list(d) for d in last["dice"]]
    picked = list(dict.fromkeys(body.reroll))
    valid = (len(opts.keys) == 1 and 1 <= len(picked) <= opts.reroll_limit
             and all(0 <= i < len(dice) and (not opts.keep_rolled or dice[i][1] == dice[i][0]) for i in picked))
    if not valid:  # get_db annulla ciò che le opzioni hanno pagato
        raise HTTPException(status_code=409, detail={"code": "bad_reroll"})

    rolled = [(dice[i][0], random.randint(1, dice[i][0])) for i in picked]
    record_dice(char, [(f"d{sides}", v) for sides, v in rolled])
    added, flat = list(last["added"]), last["flat"]
    if opts.keep_rolled:
        added += [v for _, v in rolled]
        flat += sum(v for _, v in rolled)
    else:
        for i, (_, v) in zip(picked, rolled):
            dice[i][1] = v

    values = [v for _, v in dice]
    total = scale_damage(sum(values) + flat, last["multiplier"])
    old = last["result"]
    if weapon:
        previous = OptionResult(**old["option_result"]) if old.get("option_result") else None
        result = WeaponAttackResult(**{
            **old, "damage_rolls": values + added, "damage_total": total, "attack_id": None,
            "option_result": option_result(opts, [v for _, v in rolled], 0, previous=previous),
        })
        label = result.weapon_name
    else:
        main, extra = values[:last["main"]], values[last["main"]:]
        parts = [f"{len(main)}{old['main_kind']}={main}"]
        if extra:
            parts.append(f"+{len(extra)}{old['extra_kind']}={extra}")
        if flat:
            parts.append(f"{flat:+d}")
        previous = OptionResult(**old["option_result"]) if old.get("option_result") else None
        result = RollDamageResult(**{
            **old, "rolls": values + added, "main_rolls": main, "extra_rolls": extra, "total": total,
            "half_damage": total // 2, "breakdown": " ".join(parts) + f" = {total}",
            "option_result": option_result(opts, [v for _, v in rolled], 0, previous=previous),
        })
        label = f"{spell.name} = {total}"
    _add_history(session, char_id, "attack_roll" if weapon else "spell_damage",
                 f"Dopo il danno ({', '.join(opts.keys)}): {label}" + (f" = {total}" if weapon else ""))
    turn = get_turn(char)  # il pagamento ha riscritto il turno
    turn["last_damage"] = {**last, "dice": dice, "added": added, "flat": flat, "result": result.model_dump(mode="json")}
    char.turn_state = turn
    await session.commit()  # get_db chiude dopo la risposta: il client rilegge subito usi e turno
    return result
