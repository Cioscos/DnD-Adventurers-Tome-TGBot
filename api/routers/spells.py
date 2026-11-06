"""Spell management endpoints."""

from __future__ import annotations

import random
import re
import uuid
from datetime import datetime
from types import SimpleNamespace
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.database import get_db
from core.db.models import Ability, Character, CharacterClass, CharacterHistory, Spell, SpellSlot
from api.schemas.character import CharacterFull, SpellAttackResult
from api.schemas.common import ConcentrationSaveResult, D20Dice, OptionResult, RollMode
from api.schemas.spell import (
    ConcentrationUpdate,
    LastDamageBody,
    RollDamageRequest,
    RollDamageResult,
    RollHealingRequest,
    RollHealingResult,
    SpellAttackRequest,
    SpellCreate,
    SpellRead,
    SpellUpdate,
    SpellUseRequest,
)
from api.routers.items import _roll_dice, _DICE_RE
from api.services.durations import end_concentration, start_concentration
from core.data.damage_types import canonical_damage_type
from api.services.effects import casts_verbally, end_hide
from api.services.rules_states import end_on_action
from api.services.condition_effects import release_concentration_effects
from core.game.actions import parse_duration_rounds
from api.routers._helpers import collect_homebrew_notifications, roll_concentration_save
from api.services.character_response import build_character_response
from api.services.d20 import d20_records, d20_history_label, resolve_applied, resolve_body, spend_inspiration_reroll
from core.rules.catalog.y2014.sorcerer import SUBTLE_KEY, TWINNED_TURN_KEY
from core.rules.modifiers import modifiers_for
from api.schemas.companion import CompanionAttackResult
from api.schemas.item import WeaponAttackResult
from api.services.last_damage import damage_parts, last_damage_total, pairs, regroup
from core.rules.roll_options import scale_damage
from api.services.rules_options import merge_options, option_result, remember_roll, roll_option_dice, use_options
from api.services.rules_states import _spend_atomically, remove_state
from api.services.rules_turn import get_turn, refuse_if_incapacitated, spend
from core.rules.pact_casts import pact_cast
from core.rules.states import free_cast_state
from api.services.choices import consume_spell_pick, release_spell_pick, spell_pick_target
from core.rules.level_choices import reconcile_choices
from api.services.dice_stats import record_dice
from api.services.homebrew.dispatcher import dispatch
from api.services.spellcasting import build_spellcasting_info, fill_spell_stats, prepared_class_room
from core.game.stats import cantrip_dice_multiplier
from core.rules.spell_healing import SPELL_HEALING, healing_dice, healing_fixed
from core.rules.spellcasting import (
    at_will, can_ritual, cast_warnings, caster_stats, casting_kind, ki_cast_info, spell_stats,
)


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


def _pick_slot(char: Character, spell: Spell, slot_id: int | None, slot_level: int | None,
               pact_only: bool = False) -> SpellSlot:
    """``slot_id`` sceglie il pool. Col solo livello: la prima riga con posto, gli slot normali prima del patto.
    ``pact_only``: solo uno slot di Patto (le suppliche «una volta con uno slot da warlock»), 409 ``pact_slot_required``."""
    if slot_id is not None:
        slot = next((s for s in char.spell_slots if s.id == slot_id), None)
        if slot is None:
            raise HTTPException(status_code=400, detail="Slot not found")
        if pact_only and not slot.is_pact:
            raise HTTPException(status_code=409, detail={"code": "pact_slot_required"})
        slot_level = slot.level
    elif slot_level is None:
        raise HTTPException(status_code=400, detail="slot_level is required")
    if slot_level < spell.level:
        raise HTTPException(status_code=400, detail={"code": "slot_too_low"})
    if slot_id is None:
        rows = sorted((s for s in char.spell_slots if s.level == slot_level and (s.is_pact or not pact_only)),
                      key=lambda s: bool(s.is_pact))
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
    if kind == "action":  # Magia da Battaglia: quale classe ha lanciato con l'azione (l'ultimo lancio vale)
        casters = caster_stats(char)
        turn["action_spell_class"] = spell.class_id or (casters[0].class_id if len(casters) == 1 else None)
        turn["action_spell_level"] = spell.level  # Magia da Guerra: 0 è un trucchetto
    char.turn_state = turn


_LONG_CASTING = re.compile(r"minut|minute|\bor[ae]\b|hour", re.IGNORECASE)


def _ki_payment(char: Character, spell: Spell, ritual: bool, free_cast: bool, extra: int) -> tuple[Any, int]:
    """Lancio coi punti ki: la riserva e quanto costa. Ogni rifiuto viene prima di spendere qualcosa."""
    info = ki_cast_info(char, spell)
    if info is None or ritual or free_cast:
        raise HTTPException(status_code=409, detail={"code": "ki_cast_unavailable"})
    if extra and not info.upcast:
        raise HTTPException(status_code=409, detail={"code": "ki_extra_not_allowed"})
    if extra > info.max_extra and info.ki_left >= info.cost + extra:
        raise HTTPException(status_code=409, detail={"code": "ki_cap", "max_extra": info.max_extra})
    pool = next(a for a in char.abilities if a.feature_key == info.pool)
    total = info.cost + extra
    if (pool.uses or 0) < total:
        raise HTTPException(status_code=409, detail={"code": "no_uses"})
    return pool, total


def _consume_cast(
    session, char: Character, spell: Spell, slot_id: int | None, slot_level: int | None, ritual: bool,
    confirm: list[str] | None = None, free_cast: bool = False, ki: bool = False, ki_extra: int = 0,
    silent: bool = False,
) -> Ability | None:
    """Consuma il lancio (slot o rituale) e attiva la concentrazione. Un trucchetto non consuma nulla.

    Condiviso da /use e /attack. Una regola violata e non confermata risponde 409 ``cast_confirm`` prima di spendere.
    Restituisce la riga del privilegio il cui uso il lancio spende (Arcanum Mistico, suppliche a uso singolo): lo spende
    il chiamante con ``_charge_pact_use``, con un UPDATE condizionato.
    """
    ki_pool, ki_total = _ki_payment(char, spell, ritual, free_cast, ki_extra) if ki else (None, 0)
    free_state = None
    free_at_will = False
    pact = pact_cast(char, spell) if not ritual and not ki and spell.level >= 1 else None
    arcanum = None  # Arcanum Mistico: senza slot, spende l'uso della sua riga
    if free_cast:  # R43: serve uno stato attivo (o un privilegio a volontà) per questo incantesimo; costa l'azione, non uno slot
        free_state = free_cast_state(char, spell)
        free_at_will = free_state is None and at_will(char, spell)
        arcanum = pact if pact is not None and pact.kind == "arcanum" and free_state is None and not free_at_will else None
        if (free_state is None and not free_at_will and arcanum is None) or ritual:
            raise HTTPException(status_code=409, detail={"code": "free_cast_unavailable"})
    # Suppliche a uso singolo: lo slot è di Patto e il lancio spende l'uso. Tutti i rifiuti vengono prima di spendere.
    invocation = pact if pact is not None and pact.kind == "invocation" and not free_cast else None
    pact_row = None
    if arcanum is not None or invocation is not None:
        used = arcanum or invocation
        pact_row = next((a for a in char.abilities if a.feature_key == used.feature_key), None)
        if pact_row is None or (pact_row.uses or 0) < 1:
            raise HTTPException(status_code=409, detail={"code": "no_uses"})
    if ritual:
        # Lancio rituale: +10 min, nessuno slot. Richiede il tag ritual e chi può celebrarlo per edizione.
        if not spell.is_ritual:
            raise HTTPException(status_code=400, detail="Spell is not a ritual")
        if not can_ritual(char, spell):
            raise HTTPException(
                status_code=400, detail="No class with Ritual Casting"
            )
    slot = None if ritual or free_cast or ki or spell.level == 0 else _pick_slot(
        char, spell, slot_id, slot_level, pact_only=invocation is not None)
    missing = [w for w in cast_warnings(char, spell, ritual) if w not in (confirm or [])]
    if missing:
        raise HTTPException(status_code=409, detail={"code": "cast_confirm", "warnings": missing})

    if ki_pool is not None:
        if not _LONG_CASTING.search(spell.casting_time or ""):  # un lancio di minuti o ore non è un'azione del turno
            spend(char, casting_kind(spell))  # 409 turn_slot_used: nulla è ancora scritto
        ki_pool.uses = (ki_pool.uses or 0) - ki_total
        _add_history(session, char.id, "spell_cast", f"Lanciato {spell.name} con {ki_total} ki",
                     meta={"ki": ki_total, "slot_level": spell.level + ki_extra})
    elif arcanum is not None:
        spend(char, casting_kind(spell))  # 409 turn_slot_used: nulla è ancora scritto
        _add_history(session, char.id, "spell_cast", f"Lanciato {spell.name} (Arcanum Mistico)",
                     meta={"slot_level": spell.level, "arcanum": True})
    elif free_at_will:
        spend(char, casting_kind(spell))  # 409 turn_slot_used: nulla è ancora scritto
        _add_history(session, char.id, "spell_cast", f"Lanciato {spell.name} a volontà")
    elif free_state is not None:
        spend(char, "action")  # 409 turn_slot_used: nulla è ancora scritto
        remove_state(char, free_state["key"])
        _add_history(session, char.id, "spell_cast", f"Lanciato {spell.name} senza slot ({free_state.get('name') or free_state['key']})")
    elif ritual:
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
    end_on_action(char, "cast")
    if casts_verbally(spell) and not silent:  # Incantesimo Celato: nessuna componente verbale, il nascondiglio resta
        end_hide(session, char)

    if spell.is_concentration:
        start_concentration(char, spell.id, parse_duration_rounds(spell.duration))
    return pact_row


async def _charge_pact_use(session: AsyncSession, row: Ability | None) -> None:
    """Spende l'uso del privilegio con un UPDATE condizionato: due lanci insieme non spendono lo stesso uso (409 ``no_uses``,
    e l'errore annulla tutto il lancio)."""
    if row is not None:
        await _spend_atomically(session, row, 1)


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
    pick = None
    if body.pick_id:  # Segreti Magici: l'incantesimo è di qualsiasi classe e passa alla classe del bardo
        pick = spell_pick_target(char, body.pick_id, body.level, body.class_id, body.name, body.srd_index, body.is_ritual)
        body.class_id = pick[0].id
    if body.is_prepared and body.level >= 1 and not body.always_prepared:
        _ensure_prepare_capacity(char, body.class_id)
    spell = Spell(character_id=char_id, **body.model_dump(exclude={"pick_id"}))
    spell.is_prepared = spell.is_prepared or body.always_prepared
    session.add(spell)
    await session.flush()
    if pick:
        consume_spell_pick(session, char, *pick, spell)
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
    if release_spell_pick(char, spell):
        reconcile_choices(char)  # la scelta torna in coda: un errore di battitura si recupera
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

    await _charge_pact_use(session, _consume_cast(
        session, char, spell, body.slot_id, body.slot_level, body.as_ritual, body.confirm, body.free_cast,
        body.ki, body.ki_extra, silent=SUBTLE_KEY in (body.options or [])))
    _close_twinned(char)  # un nuovo lancio: il segno di Raddoppiato di uno precedente non vale più
    opts = use_options(session, char, "cast", body, spell=spell, casting_level=_cast_level(spell, body.slot_level, body.as_ritual))
    rolls, total = roll_option_dice(char, opts)
    await release_concentration_effects(session, char)
    response = await build_character_response(session, char)
    response.option_result = option_result(opts, rolls, total)
    # Dadi che il server non sa tirare: l'incantesimo si lancia lo stesso, senza danno, e la scheda lo dice
    response.damage_unrollable = any(d and not _DICE_RE.match(d.strip()) for d in (spell.damage_dice, spell.extra_damage_dice))
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
        await _charge_pact_use(session, _consume_cast(session, char, spell, body.slot_id, body.slot_level, body.ritual, body.confirm,
                                                      silent=SUBTLE_KEY in (body.cast_options or [])))
        cast_body = SimpleNamespace(options=body.cast_options, option_inputs=body.cast_option_inputs)
        _close_twinned(char)
        cast_opts = use_options(session, char, "cast", cast_body, spell=spell,
                                casting_level=_cast_level(spell, body.slot_level, body.ritual))
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
    end_on_action(char, "attack")
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

    twinned = _twinned_attack(char, spell, body.mode, applied, bonus, keep=body.with_inspiration)
    return SpellAttackResult(
        twinned_attack=twinned,
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


def _cast_level(spell: Spell, slot_level: int | None, ritual: bool = False) -> int:
    """Il livello a cui si lancia: quello dello slot (un incantesimo di livello superiore «assume il livello superiore»),
    il proprio se è un trucchetto, un rituale o un lancio senza slot."""
    return slot_level if slot_level and slot_level >= spell.level and not ritual else spell.level


def _close_twinned(char: Character) -> None:
    """Il segno di Incantesimo Raddoppiato vale per un solo lancio: un lancio nuovo lo chiude, l'opzione lo riapre."""
    turn = get_turn(char)
    if turn.pop(TWINNED_TURN_KEY, None) is not None:
        char.turn_state = turn


def _twinned_attack(char: Character, spell: Spell, mode: RollMode, applied: Any, bonus: int, keep: bool = False) -> dict | None:
    """Incantesimo Raddoppiato: il secondo bersaglio ha il suo tiro per colpire, con lo stesso modo e lo stesso bonus. Il
    critico (o il 1 naturale) resta sul turno per il danno del secondo bersaglio. Il rilancio dell'altro bersaglio non
    tocca il suo tiro: ``keep`` restituisce quello già fatto."""
    twin = (char.turn_state or {}).get(TWINNED_TURN_KEY)
    if not twin or twin.get("spell_id") != spell.id:
        return None
    if keep and twin.get("attack"):
        return twin["attack"]
    outcome = resolve_applied(mode, None, None, applied)
    record_dice(char, d20_records(outcome))
    critical = outcome.kept >= applied.crit_min
    result = {"die": outcome.kept, "dice": outcome.dice, "mode": outcome.mode, "total": outcome.kept + bonus,
              "is_critical": critical, "is_fumble": outcome.kept == 1}
    turn = get_turn(char)
    turn[TWINNED_TURN_KEY] = {**twin, "is_critical": critical, "is_fumble": result["is_fumble"], "attack": result}
    char.turn_state = turn
    return result


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
        raise HTTPException(status_code=422, detail={"code": "bad_damage_dice"})
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

    # Privilegi che aggiungono un fisso ai danni di un incantesimo (Incantesimi Potenti)
    base_bonus += modifiers_for(char, "damage", spell=spell).flat

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

    # Seconda parte del danno dell'incantesimo (di un altro tipo; il giocatore sceglie fra i tipi se ce n'e' piu' di uno)
    second_count = second_sides = 0
    second_type: str | None = None
    if spell.extra_damage_dice:
        sm = _DICE_RE.match(spell.extra_damage_dice.strip())
        if not sm:
            raise HTTPException(status_code=422, detail={"code": "bad_damage_dice"})
        second_sides = int(sm.group(2))
        second_count = int(sm.group(1)) * (2 if body.is_critical else 1)
        types = [t for t in (spell.extra_damage_type or "").split("|") if t]
        if body.extra_damage_type is not None and body.extra_damage_type not in types:
            raise HTTPException(status_code=422, detail={"code": "invalid_damage_type"})
        second_type = body.extra_damage_type or (types[0] if types else None)

    # Dadi extra scritti dal giocatore: si sommano, di tipo ignoto
    extra_bonus = 0
    extra_sides = 0
    extra_count = 0
    if body.extra_dice:
        em = _DICE_RE.match(body.extra_dice)
        if em:
            extra_sides = int(em.group(2))
            extra_bonus = int(em.group(3)) if em.group(3) else 0
            extra_count = int(em.group(1)) * (2 if body.is_critical else 1)
    groups = [("second", second_count, second_sides), ("extra", extra_count, extra_sides)]
    extra_total = second_count + extra_count
    if body.extra_rolls is not None and extra_total:
        if len(body.extra_rolls) != extra_total:
            raise HTTPException(
                status_code=400,
                detail=f"extra_rolls length {len(body.extra_rolls)} != expected {extra_total}",
            )
        at = 0
        for _, count, group_sides in groups:
            if any(v < 1 or v > group_sides for v in body.extra_rolls[at:at + count]):
                raise HTTPException(
                    status_code=400,
                    detail=f"extra_rolls values must be in [1, {group_sides}]",
                )
            at += count
        all_extra = list(body.extra_rolls)
    else:
        all_extra = [random.randint(1, group_sides) for _, count, group_sides in groups for _ in range(count)]
    second_rolls, extra_rolls = all_extra[:second_count], all_extra[second_count:]

    opts = use_options(session, char, "spell_damage", body, spell=spell)
    if opts.maximize:  # Collera Distruttiva: valgono il massimo i dadi dei tipi che l'opzione tocca, mai quelli messi a mano
        def maximized(kind: str | None) -> bool:
            return opts.maximize_types is None or canonical_damage_type(kind) in opts.maximize_types
        if maximized(spell.damage_type):
            main_rolls = [sides] * len(main_rolls)
        if second_rolls and maximized(second_type):
            second_rolls = [second_sides] * len(second_rolls)
    option_rolls, option_total = roll_option_dice(char, opts, body.is_critical)
    total = (sum(main_rolls) + sum(second_rolls) + sum(extra_rolls) + base_bonus + extra_bonus + option_total + opts.bonus)
    total = scale_damage(total, opts.multiplier)
    half_damage = total // 2  # per difetto, in entrambe le edizioni

    parts = damage_parts([("main", spell.damage_type, sides, main_rolls), ("second", second_type, second_sides, second_rolls),
                          ("extra", None, extra_sides, extra_rolls)])
    breakdown_parts = [f"{len(main_rolls)}d{sides}={main_rolls}"]
    for part in parts[1:]:
        breakdown_parts.append(f"+{len(part['rolls'])}{part['kind']}={part['rolls']}")
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
        + [(f"d{second_sides}", v) for v in second_rolls]
        + [(f"d{extra_sides}", v) for v in extra_rolls],
    )

    # Append to rolls_history if character supports it
    history_entry = {
        "type": "spell_damage",
        "spell_name": spell.name,
        "rolls": main_rolls + second_rolls + extra_rolls,
        "total": total,
        "damage_type": spell.damage_type,
        "casting_level": casting_level,
        "is_critical": body.is_critical,
    }
    if hasattr(char, "rolls_history") and isinstance(char.rolls_history, list):
        char.rolls_history.append(history_entry)
        await session.commit()

    all_extra = second_rolls + extra_rolls
    extra_kind = f"d{second_sides}" if second_rolls else (f"d{extra_sides}" if extra_rolls else None)

    result = RollDamageResult(
        rolls=main_rolls + all_extra,
        total=total,
        half_damage=half_damage,
        damage_type=spell.damage_type,
        breakdown=breakdown,
        casting_level=casting_level,
        is_critical=bool(body.is_critical),
        scaled_dice=f"{base_count}d{sides}",
        main_kind=f"d{sides}",
        main_rolls=main_rolls,
        option_result=option_result(opts, option_rolls, option_total),
        extra_kind=extra_kind,
        extra_rolls=all_extra,
        extra_damage_type=second_type if second_rolls else None,
        parts=parts,
        twinned_damage=_twinned_damage(char, spell, base_count, sides, base_bonus),
    )
    # I dadi delle opzioni vengono dopo quelli dell'incantesimo e si ritirano come loro; il loro fisso resta nel resto.
    base_dice = ([[sides, v] for v in main_rolls] + [[second_sides, v] for v in second_rolls]
                 + [[extra_sides, v] for v in extra_rolls])
    dice = base_dice + pairs(opts.rolled_dice)
    result.reroll_dice = dice
    turn = get_turn(char)
    turn["last_damage"] = {
        "roll_id": uuid.uuid4().hex, "spell_id": spell.id, "dice": dice,
        "main": len(main_rolls), "base": len(base_dice), "added": [], "multiplier": opts.multiplier, "mod": 0,
        "flat": base_bonus + extra_bonus + option_total - sum(v for _, v in opts.rolled_dice) + opts.bonus,
        "groups": [[p["label"], p["type"], p["kind"], len(p["rolls"])] for p in parts],
        "result": result.model_dump(mode="json"),
    }
    char.turn_state = turn
    return result


def _twinned_damage(char: Character, spell: Spell, count: int, sides: int, bonus: int) -> dict | None:
    """Incantesimo Raddoppiato: l'incantesimo con tiro per colpire ripete i danni per il secondo bersaglio (uno con TS tira una
    volta sola per entrambi). Il segno si consuma: vale per un solo tiro di danno."""
    turn = get_turn(char)
    twin = turn.pop(TWINNED_TURN_KEY, None)
    if not twin or twin.get("spell_id") != spell.id:
        return None
    char.turn_state = turn
    if (spell.attack_save or "").strip().upper() != "ATK" or twin.get("is_fumble"):  # il 1 naturale manca: nessun danno
        return None
    rolls = [random.randint(1, sides) for _ in range(count * (2 if twin.get("is_critical") else 1))]
    record_dice(char, [(f"d{sides}", v) for v in rolls])
    return {"rolls": rolls, "total": sum(rolls) + bonus}


@router.post("/{char_id}/spells/{spell_id}/roll_healing", response_model=RollHealingResult)
async def roll_spell_healing(
    char_id: int,
    spell_id: int,
    body: RollHealingRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RollHealingResult:
    """PF che un incantesimo di cura restituisce (R41): dadi allo slot scelto, modificatore da incantatore e privilegi
    (Discepolo della Vita, Guarigione Suprema). Il server tira e somma; con ``apply_to_self`` li aggiunge a chi lancia."""
    from api.services.effects import apply_heal  # import locale: effects importa il router degli incantesimi
    char = await _get_owned_full(char_id, user_id, session)
    spell = next((s for s in char.spells if s.id == spell_id), None)
    if spell is None:
        raise HTTPException(status_code=404, detail="Spell not found")
    healing = SPELL_HEALING.get(spell.srd_index or "")
    if healing is None:
        raise HTTPException(status_code=400, detail={"code": "not_a_healing_spell"})
    level = body.casting_level if body.casting_level is not None else spell.level
    if level < spell.level or level > 9:
        raise HTTPException(status_code=400, detail="invalid casting_level")
    count, sides = healing_dice(healing, spell.level, level)
    main_rolls = [random.randint(1, sides) for _ in range(count)]

    opts = use_options(session, char, "spell_healing", body, spell=spell, casting_level=level)
    applied = modifiers_for(char, "spell_healing", spell=spell, casting_level=level)
    maximized = bool(main_rolls) and (applied.maximize_healing or opts.maximize)
    if maximized:
        main_rolls = [sides] * len(main_rolls)
    option_rolls, option_total = roll_option_dice(char, opts)
    modifier = healing_fixed(healing, spell.level, level)
    if healing.add_mod:
        from core.game.stats import effective_ability_mod  # import locale
        caster = spell_stats(char, spell)
        modifier += effective_ability_mod(char, caster.ability) if caster else 0
    total = max(0, sum(main_rolls) + modifier + applied.flat + opts.bonus + option_total)
    record_dice(char, [(f"d{sides}", v) for v in main_rolls])
    parts = [f"{count}d{sides}={main_rolls}" if count else "fisso"]
    if modifier:
        parts.append(f"{modifier:+d}")
    if applied.flat:
        parts.append(f"{applied.flat:+d}")
    breakdown = " ".join(parts) + f" = {total}"
    healed = 0
    if body.apply_to_self:
        healed = (await apply_heal(session, char, total))["healed"]
    self_healed = 0
    if opts.self_heal:
        self_healed = (await apply_heal(session, char, opts.self_heal))["healed"]
    _add_history(session, char_id, "spell_healing", f"{spell.name}: cura {breakdown}")
    return RollHealingResult(
        rolls=main_rolls, total=total, breakdown=breakdown, casting_level=level, main_kind=f"d{sides}" if count else None,
        main_rolls=main_rolls, modifier=modifier, bonus=applied.flat + opts.bonus, maximized=maximized, healed=healed,
        self_healed=self_healed, option_result=option_result(opts, option_rolls, option_total))


@router.post("/{char_id}/last-damage/options",
             response_model=RollDamageResult | WeaponAttackResult | CompanionAttackResult)
async def last_damage_options(
    char_id: int,
    body: LastDamageBody,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RollDamageResult | WeaponAttackResult | CompanionAttackResult:
    """Privilegi usati dopo aver visto i dadi di danno (incantesimo, arma o compagno). Il tiro è quello salvato dal server."""
    char = await _get_owned_full(char_id, user_id, session)
    last = get_turn(char).get("last_damage")
    kind = (last or {}).get("kind", "spell")
    spell = next((s for s in char.spells if last and kind == "spell" and s.id == last["spell_id"]), None)
    if not last or (kind == "spell" and spell is None):
        raise HTTPException(status_code=409, detail={"code": "no_last_damage"})
    opts = use_options(session, char, "spell_damage" if kind == "spell" else "weapon_damage", body, phase="after_damage",
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
    total = last_damage_total(values, {**last, "flat": flat})
    base = last.get("base", len(values))
    old = last["result"]
    previous = OptionResult(**old["option_result"]) if old.get("option_result") else None
    block = option_result(opts, [], 0, previous=previous)
    if block is not None:  # i dadi delle opzioni sono quelli di adesso, non si accodano ai vecchi
        old_values, new_values = [v for _, v in last["dice"][base:]], values[base:]
        newly = added[len(last["added"]):]
        block = block.model_copy(update={
            "extra_rolls": [*new_values, *added],
            "extra_total": block.extra_total - sum(old_values) + sum(new_values) + sum(newly)})
    if kind == "weapon":
        # Danno base fisso ("1"): senza dadi di base il fisso già mostrato resta nell'elenco.
        result = WeaponAttackResult(**{**old, "damage_rolls": (values[:base] if base else old["damage_rolls"]) + added,
                                       "damage_total": total,
                                       "attack_id": None, "reroll_dice": dice, "option_result": block})
        label = result.weapon_name
    elif kind == "companion":
        result = CompanionAttackResult(**{**old, "damage_rolls": values[:base] + added, "damage_total": total,
                                          "reroll_dice": dice, "option_result": block})
        label = last.get("name") or "Compagno"
    else:
        main, extra = values[:last["main"]], values[last["main"]:base]
        shown = regroup(last.get("groups"), values[:base]) if last.get("groups") else old.get("parts") or []
        text = [f"{len(main)}{old['main_kind']}={main}"]
        text += [f"+{len(p['rolls'])}{p['kind']}={p['rolls']}" for p in shown[1:]]
        if flat:
            text.append(f"{flat:+d}")
        result = RollDamageResult(**{
            **old, "rolls": values[:base] + added, "main_rolls": main, "extra_rolls": extra, "total": total,
            "half_damage": total // 2, "breakdown": " ".join(text) + f" = {total}", "reroll_dice": dice,
            "option_result": block, "parts": shown,
        })
        label = f"{spell.name} = {total}"
    _add_history(session, char_id, "spell_damage" if kind == "spell" else "attack_roll",
                 f"Dopo il danno ({', '.join(opts.keys)}): {label}" + (f" = {total}" if kind != "spell" else ""))
    turn = get_turn(char)  # il pagamento ha riscritto il turno
    turn["last_damage"] = {**last, "dice": dice, "added": added, "flat": flat, "result": result.model_dump(mode="json")}
    char.turn_state = turn
    await session.commit()  # get_db chiude dopo la risposta: il client rilegge subito usi e turno
    return result
