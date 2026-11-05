"""Companions: familiars, companions, mounts, summons and wild shape records."""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_lang, get_current_user
from api.database import get_db
from api.schemas.common import HPOp, HPUpdate
from api.schemas.companion import (
    DICE_RE, MAX_COMPANIONS, CompanionActivate, CompanionAttack, CompanionAttackResult, CompanionCreate,
    CompanionHp, CompanionRead, CompanionUpdate, WildHealRequest, WildHealResult,
)
from api.routers.hp import _get_owned_full, update_hp
from api.routers.items import _option_damage
from api.services.d20 import d20_history_label, d20_records, resolve_applied
from api.services.dice_stats import record_dice
from api.services.last_damage import pairs
from api.services.rules_options import merge_options, option_result, use_options
from api.services.rules_turn import get_turn, refuse_if_incapacitated, spend
from api.services.wild_shape import (
    deactivate_other_forms, end_form, form_limits, form_own_hp, get_active_form, return_to_normal, start_form,
)
from core.db.models import Ability, Character, CharacterHistory, Companion, SpellSlot
from core.rules.companions import companion_stats
from core.rules.edition import character_edition
from core.rules.catalog import active_features
from core.rules.forms import elemental_violations, form_violations, is_elemental_form
from core.rules.modifiers import Applied, modifiers_for

router = APIRouter(prefix="/characters", tags=["companions"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _history(session: AsyncSession, char_id: int, event_type: str, description: str) -> None:
    session.add(CharacterHistory(
        character_id=char_id, timestamp=datetime.utcnow().isoformat(timespec="seconds"),
        event_type=event_type, description=description,
    ))


async def _get_char(session: AsyncSession, char_id: int, user_id: int) -> Character:
    return await _get_owned_full(char_id, user_id, session)


def form_limits_moon(char: Character) -> bool:
    return any(c.subclass_key == "moon" for c in char.classes)


def _read(char: Character, comp: Companion) -> CompanionRead:
    """La riga com'è scritta, con PF, CA e bonus del compagno di privilegio calcolati dal livello e dalla competenza."""
    out = CompanionRead.model_validate(comp)
    stats = companion_stats(char, comp)
    if stats is not None:
        out.max_hp = stats.max_hp if stats.max_hp is not None else comp.max_hp
        out.armor_class = stats.armor_class if stats.armor_class is not None else comp.armor_class
        out.attack_bonus_extra, out.damage_bonus_extra = stats.attack_bonus, stats.damage_bonus
        out.current_hp = min(comp.current_hp, out.max_hp)
    return out


def _effective_max_hp(char: Character, comp: Companion) -> int:
    stats = companion_stats(char, comp)
    return stats.max_hp if stats is not None and stats.max_hp is not None else comp.max_hp


async def _get_companion(session: AsyncSession, char_id: int, comp_id: int) -> Companion:
    comp = (await session.execute(
        select(Companion).where(Companion.id == comp_id, Companion.character_id == char_id)
    )).scalar_one_or_none()
    if comp is None:
        raise HTTPException(status_code=404, detail="Companion not found")
    return comp


@router.get("/{char_id}/companions", response_model=list[CompanionRead])
async def list_companions(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[CompanionRead]:
    char = await _get_char(session, char_id, user_id)
    res = await session.execute(
        select(Companion).where(Companion.character_id == char_id).order_by(Companion.id)
    )
    return [_read(char, c) for c in res.scalars()]


@router.post("/{char_id}/companions", response_model=CompanionRead, status_code=status.HTTP_201_CREATED)
async def create_companion(
    char_id: int,
    body: CompanionCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CompanionRead:
    char = await _get_char(session, char_id, user_id)
    rows = list((await session.execute(select(Companion).where(Companion.character_id == char_id))).scalars())
    if len(rows) >= MAX_COMPANIONS:
        raise HTTPException(status_code=422, detail="companion_limit")
    if body.is_active and body.kind != "wild_shape":
        raise HTTPException(status_code=422, detail="active_only_wild_shape")
    limits = form_limits(char)
    if body.kind == "wild_shape" and limits is not None and limits.known_forms is not None:
        if sum(c.kind == "wild_shape" for c in rows) >= limits.known_forms:  # 2024: forme conosciute, se ne sostituisce una
            raise HTTPException(status_code=422, detail="known_forms_limit")
    data = body.model_dump()
    data["current_hp"] = min(body.max_hp if body.current_hp is None else body.current_hp, body.max_hp)
    comp = Companion(character_id=char_id, created_at=_now(), **data)
    if body.current_hp is None and body.feature_key:  # parte dai PF che il privilegio gli dà
        comp.current_hp = _effective_max_hp(char, comp)
    session.add(comp)
    await session.flush()
    if comp.is_active:
        await deactivate_other_forms(session, char_id, comp.id)
        start_form(char, comp)
    _history(session, char_id, "companion_added", f"Aggiunto: {comp.name}")
    return _read(char, comp)


@router.patch("/{char_id}/companions/{comp_id}", response_model=CompanionRead)
async def update_companion(
    char_id: int,
    comp_id: int,
    body: CompanionUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CompanionRead:
    char = await _get_char(session, char_id, user_id)
    comp = await _get_companion(session, char_id, comp_id)
    was_active = comp.is_active
    changes = body.model_dump(exclude_unset=True)
    for required in ("kind", "name", "statblock", "max_hp", "armor_class", "temp_hp", "is_active", "current_hp"):
        if required in changes and changes[required] is None:
            raise HTTPException(status_code=422, detail=f"{required}_required")
    for k, v in changes.items():
        setattr(comp, k, v)
    if comp.is_active and comp.kind != "wild_shape":
        raise HTTPException(status_code=422, detail="active_only_wild_shape")
    comp.current_hp = min(comp.current_hp, _effective_max_hp(char, comp))
    if comp.is_active and comp.current_hp == 0 and form_own_hp(char):  # a 0 PF la forma finisce, anche se corretta a mano
        end_form(char, comp)
    elif comp.is_active and not was_active:
        await deactivate_other_forms(session, char_id, comp.id)
        start_form(char, comp)
    elif was_active and not comp.is_active:
        end_form(char, comp)
    return _read(char, comp)


@router.post("/{char_id}/companions/{comp_id}/activate", response_model=CompanionRead)
async def activate_wild_shape(
    char_id: int,
    comp_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    body: Annotated[CompanionActivate | None, Body()] = None,
) -> CompanionRead:
    char = await _get_char(session, char_id, user_id)
    comp = await _get_companion(session, char_id, comp_id)
    if comp.kind != "wild_shape":
        raise HTTPException(status_code=422, detail="active_only_wild_shape")
    if comp.is_active:
        return _read(char, comp)
    if char.is_dead or char.current_hit_points == 0:
        raise HTTPException(status_code=409, detail="character_down")
    force = bool(body and body.force)
    limits = form_limits(char)
    if limits is not None:
        refuse_if_incapacitated(char)  # chi non può agire non si trasforma
    # Forma Selvatica Elementale (2014): un elementale costa due usi e ha regole sue
    elemental = character_edition(char) == "2014" and is_elemental_form(comp.statblock or {}, comp.srd_index)
    reasons: list[str] = []
    if limits is not None:
        reasons = (elemental_violations(limits, comp.statblock or {}, comp.srd_index) if elemental
                   else form_violations(limits, comp.statblock or {}))
    if reasons and not force:  # la forma rompe i limiti di livello e circolo: si ammette solo confermando
        raise HTTPException(status_code=409, detail={"code": "form_not_allowed", "reasons": reasons})
    if limits is not None:  # 2014 azione (Luna: bonus), 2024 azione bonus; 409 turn_slot_used prima di spendere usi
        slot = "bonus" if character_edition(char) == "2024" or form_limits_moon(char) else "action"
        try:
            spend(char, slot)
        except HTTPException as exc:  # il client dice quale slot è finito
            raise HTTPException(exc.status_code, detail={**exc.detail, "slot": slot}) from exc
    ability = (await session.execute(
        select(Ability).where(Ability.character_id == char_id, Ability.feature_key == "druid.wild_shape")
    )).scalars().first()
    if ability is not None and ability.max_uses is not None:  # NULL: illimitata
        needed, have = (2 if elemental and limits is not None else 1), ability.uses or 0
        if have >= needed:
            ability.uses = have - needed
        elif not force:
            raise HTTPException(status_code=409, detail="no_wild_shape_uses")
        else:
            ability.uses = 0
    comp.is_active = True
    comp.current_hp = comp.max_hp  # each transformation starts at full HP
    comp.temp_hp = 0
    await deactivate_other_forms(session, char_id, comp.id)
    start_form(char, comp)
    _history(session, char_id, "companion_hp", f"Forma selvatica: {comp.name}")
    return _read(char, comp)


@router.post("/{char_id}/companions/{comp_id}/deactivate", response_model=CompanionRead)
async def deactivate_wild_shape(
    char_id: int,
    comp_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CompanionRead:
    char = await _get_char(session, char_id, user_id)
    comp = await _get_companion(session, char_id, comp_id)
    if comp.is_active:
        if await get_active_form(session, char_id) is None:  # lo stato era già finito: nessun costo
            return _read(char, comp)
        return_to_normal(char, comp)  # 2014: azione bonus; già spesa = 409 e la forma resta
        _history(session, char_id, "companion_hp", "Forma selvatica terminata")
    return _read(char, comp)


@router.post("/{char_id}/companions/{comp_id}/wild-heal", response_model=WildHealResult)
async def wild_heal(
    char_id: int,
    comp_id: int,
    body: WildHealRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WildHealResult:
    """Forma Selvatica da Combattimento (Druido 2014, Circolo della Luna): in forma, azione bonus e uno slot per curare la
    forma di 1d8 per livello dello slot. Il server tira; lo slot si prende con un UPDATE condizionato."""
    char = await _get_char(session, char_id, user_id)
    comp = await _get_companion(session, char_id, comp_id)
    active = await get_active_form(session, char_id) if comp.kind == "wild_shape" else None
    if active is None or active.id != comp.id:  # lo stato attivo è la verità, non il flag della riga
        raise HTTPException(status_code=409, detail={"code": "form_not_active"})
    if not any(spec.key == "druid.combat_wild_shape" for spec, _row in active_features(char)):
        raise HTTPException(status_code=409, detail={"code": "feature_unavailable"})
    candidates = sorted((s for s in char.spell_slots if s.level == body.slot_level and s.used < s.total),
                        key=lambda s: s.is_pact)  # prima gli slot normali, poi quelli del Patto
    if not candidates:
        raise HTTPException(status_code=409, detail={"code": "no_slot"})
    refuse_if_incapacitated(char)
    if comp.current_hp >= _effective_max_hp(char, comp):  # non si spende nulla per curare chi è già pieno
        raise HTTPException(status_code=409, detail={"code": "form_full_hp"})
    spend(char, "bonus")  # 409 turn_slot_used: la risposta annulla tutto, nulla è ancora speso
    taken = await session.execute(
        update(SpellSlot).where(SpellSlot.id == candidates[0].id, SpellSlot.used < SpellSlot.total)
        .values(used=SpellSlot.used + 1))
    if taken.rowcount != 1:  # un'altra richiesta ha preso l'ultimo slot
        raise HTTPException(status_code=409, detail={"code": "no_slot"})
    await session.refresh(candidates[0])
    rolls = [random.randint(1, 8) for _ in range(body.slot_level)]
    record_dice(char, [("d8", r) for r in rolls])
    before = comp.current_hp
    comp.current_hp = min(_effective_max_hp(char, comp), before + sum(rolls))
    _history(session, char_id, "companion_hp",
             f"Forma selvatica da combattimento: {comp.name} +{comp.current_hp - before} PF (slot di livello {body.slot_level})")
    return WildHealResult(companion=_read(char, comp), slot_level=body.slot_level, rolls=rolls,
                          healed=comp.current_hp - before)


@router.delete("/{char_id}/companions/{comp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_companion(
    char_id: int,
    comp_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    char = await _get_char(session, char_id, user_id)
    comp = await _get_companion(session, char_id, comp_id)
    if comp.is_active:
        end_form(char, comp)
    await session.delete(comp)


@router.patch("/{char_id}/companions/{comp_id}/hp", response_model=CompanionRead)
async def companion_hp(
    char_id: int,
    comp_id: int,
    body: CompanionHp,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CompanionRead:
    char = await _get_char(session, char_id, user_id)
    comp = await _get_companion(session, char_id, comp_id)
    active = await get_active_form(session, char_id) if comp.kind == "wild_shape" else None
    if body.op == "damage" and active is not None and active.id == comp.id and form_own_hp(char):
        # il danno alla forma attiva ha un solo percorso, quello di PATCH /hp: PF temporanei, chiusura a 0 PF, eccesso al personaggio
        await update_hp(char_id, HPUpdate(op=HPOp.DAMAGE, value=body.value), user_id, session, lang)
        out = _read(char, comp)
        out.down = comp.current_hp == 0
        return out
    if body.op == "damage":
        absorbed = min(comp.temp_hp, body.value)
        comp.temp_hp -= absorbed
        comp.current_hp = max(0, comp.current_hp - (body.value - absorbed))
    elif body.op == "heal":
        comp.current_hp = min(_effective_max_hp(char, comp), comp.current_hp + body.value)
    else:
        comp.temp_hp = body.value
    out = _read(char, comp)
    _history(session, char_id, "companion_hp",
             f"{comp.name}: {body.op} {body.value} → PF {out.current_hp}/{out.max_hp}, temp {comp.temp_hp}")
    out.down = comp.current_hp == 0
    return out


@router.post("/{char_id}/companions/{comp_id}/attack", response_model=CompanionAttackResult)
async def companion_attack(
    char_id: int,
    comp_id: int,
    body: CompanionAttack,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CompanionAttackResult:
    char = await _get_char(session, char_id, user_id)
    comp = await _get_companion(session, char_id, comp_id)
    actions = (comp.statblock or {}).get("actions") or []
    if body.action_index >= len(actions):
        raise HTTPException(status_code=422, detail="unknown_action")
    action = actions[body.action_index]
    if action.get("attack_bonus") is None:
        raise HTTPException(status_code=422, detail="action_not_attack")

    # In Forma Selvatica attacca il personaggio: le sue condizioni restano; un compagno è un altro combattente.
    applied = Applied()
    in_form = comp.kind == "wild_shape" and comp.is_active
    if in_form:
        refuse_if_incapacitated(char)
        applied = modifiers_for(char, "attack", ability="strength")
    opts = use_options(session, char, "attack", body)
    merge_options(applied, opts)
    outcome = resolve_applied(body.mode, body.dice, None, applied)
    stats = companion_stats(char, comp)
    bonus = int(action["attack_bonus"]) + applied.flat + opts.bonus + (stats.attack_bonus if stats else 0)
    is_fumble = outcome.kept == 1
    is_critical = outcome.kept >= applied.crit_min or (opts.force_crit and not is_fumble)

    rolls: list[int] = []
    flat = 0
    m = DICE_RE.match(str(action.get("damage_dice") or "").strip())
    if m:
        count, sides = int(m.group(1)), int(m.group(2))
        flat = int(m.group(3) or 0)
        need = count * (2 if is_critical else 1)
        if need > 100 or not 1 <= sides <= 1000:
            raise HTTPException(status_code=422, detail="damage_dice_out_of_range")
        if body.damage_rolls is not None:
            if len(body.damage_rolls) != need or any(not 1 <= r <= sides for r in body.damage_rolls):
                raise HTTPException(status_code=422, detail="damage_rolls_mismatch")
            rolls = list(body.damage_rolls)
        else:
            rolls = [random.randint(1, sides) for _ in range(need)]
    elif body.damage_rolls:
        raise HTTPException(status_code=422, detail="damage_rolls_mismatch")
    option_rolls: list[int] = []
    option_total = 0
    total = 0
    mod = flat + (stats.damage_bonus if stats else 0)
    if m and not is_fumble:
        base = max(0, sum(rolls) + mod)
        option_rolls, option_total, total = _option_damage(char, opts, is_critical, base)

    _history(
        session, char_id, "attack_roll",
        f"{comp.name} - {action.get('name', 'Attacco')}: colpire {d20_history_label(outcome)}+{bonus}={outcome.kept + bonus}"
        + (" (CRITICO!)" if is_critical else " (FUMBLE!)" if is_fumble else "")
        + (f" | Danno: {total}" if m else ""),
    )
    record_dice(char, d20_records(outcome) + ([(f"d{m.group(2)}", r) for r in rolls] if m and not is_fumble else []))
    result = CompanionAttackResult(
        to_hit_die=outcome.kept, to_hit_bonus=bonus, to_hit_total=outcome.kept + bonus,
        dice=outcome.dice, mode=outcome.mode, notes=applied.notes, is_critical=is_critical, damage_rolls=rolls,
        damage_total=total, damage_type=action.get("damage_type"),
        is_magical=in_form and any(spec.key == "druid.primal_strike" for spec, _row in active_features(char)),
        option_result=option_result(opts, option_rolls, option_total),
    )
    turn = get_turn(char)  # i dadi di questo colpo si possono ritirare, come per l'arma
    turn.pop("last_damage", None)
    if m and (rolls or opts.rolled_dice) and not is_fumble:
        dice = [[int(m.group(2)), v] for v in rolls] + pairs(opts.rolled_dice)
        result.reroll_dice = dice
        turn["last_damage"] = {
            "kind": "companion", "roll_id": uuid.uuid4().hex, "name": comp.name, "dice": dice, "main": len(rolls),
            "base": len(rolls), "added": [], "multiplier": opts.multiplier, "mod": mod,
            "flat": opts.damage_unscaled - base - sum(v for _, v in opts.rolled_dice),
            "result": result.model_dump(mode="json"),
        }
    char.turn_state = turn
    return result
