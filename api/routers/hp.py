"""HP, rest, and death save endpoints."""

from __future__ import annotations

import random
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.database import get_db
from api.services.dice_stats import record_dice
from api.services.effects import apply_heal
from api.services.telegram_notify import notify_party_emergency
from api.services.homebrew.dispatcher import dispatch
from api.services.homebrew.passive import get_passive_modifiers
from core.db.models import Character, CharacterHistory
from api.schemas.character import CharacterFull
from api.schemas.common import (
    D20RollSubmission,
    DeathSaveRollResult,
    DeathSaveUpdate,
    DeathSaveAction,
    HPOp,
    HPUpdate,
    RestRequest,
)
from core.game.stats import total_base_hp
from api.routers._helpers import collect_homebrew_notifications, effective_con_mod, roll_concentration_save
from api.schemas.common import ConcentrationSaveResult
from api.services.character_response import build_character_response


class HitDiceSpendRequest(BaseModel):
    class_id: int
    count: int


class HitDiceSpendResult(BaseModel):
    rolls: list[int]
    con_bonus: int
    healed: int
    new_current_hp: int

router = APIRouter(prefix="/characters", tags=["hp"])


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


async def _get_owned_full(
    char_id: int, user_id: int, session: AsyncSession
) -> Character:
    from core.db.models import CharacterClass
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
            selectinload(Character.homebrew_resources),
        )
        .where(Character.id == char_id)
    )
    char = result.scalar_one_or_none()
    if char is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    if char.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your character")
    return char


# ---------------------------------------------------------------------------
# HP update
# ---------------------------------------------------------------------------

@router.patch("/{char_id}/hp", response_model=CharacterFull)
async def update_hp(
    char_id: int,
    body: HPUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)
    # Da morto ogni operazione PF è inerte (solo /revive riporta in vita).
    if char.is_dead:
        return await build_character_response(session, char)
    conc_result: ConcentrationSaveResult | None = None
    notifications: list[dict] = []

    was_at_zero = char.current_hit_points == 0

    if body.op == HPOp.DAMAGE:
        amount = body.value
        # Absorb temp HP first
        if char.temp_hp > 0:
            absorbed = min(char.temp_hp, amount)
            char.temp_hp -= absorbed
            amount -= absorbed
        old = char.current_hit_points
        char.current_hit_points = max(0, char.current_hit_points - amount)
        _add_history(session, char.id, "hp_change",
                     f"Danni: -{body.value} HP ({old} → {char.current_hit_points})",
                     meta={"op": "DAMAGE"})

        # --- Morte & tiri salvezza (D&D 5e RAW) ---
        if char.current_hit_points == 0 and amount > 0 and not char.is_dead:
            hb_max_bonus = await get_passive_modifiers(session, char, "character.hit_points_max")
            effective_max = char.hit_points + hb_max_bonus
            # sforamento = danno oltre quello che porta a 0
            overflow = (amount - old) if old > 0 else amount
            ds = dict(char.death_saves or {"successes": 0, "failures": 0, "stable": False})
            if overflow >= effective_max:
                char.is_dead = True
                _add_history(session, char.id, "death_save", "Morte istantanea (danno massiccio)")
            elif old == 0:
                # Danno a una creatura stabile: torna morente con conteggio
                # fresco (RAW: i conteggi si azzerano quando si diventa stabili,
                # quindi i fallimenti pre-stabilizzazione non si sommano).
                if ds.get("stable", False):
                    ds = {"successes": 0, "failures": 0, "stable": False}
                # danno subìto già a 0 PF -> fallimenti (2 se colpo critico)
                inc = 2 if body.was_critical_hit else 1
                ds["failures"] = min(3, ds.get("failures", 0) + inc)
                ds["stable"] = False
                if ds["failures"] >= 3:
                    char.is_dead = True
                    _add_history(session, char.id, "death_save", "Morto — 3 fallimenti (danno a 0 PF)")
                else:
                    _add_history(session, char.id, "death_save",
                                 f"Danno a 0 PF: +{inc} fallimento ({ds['failures']}/3)")
                char.death_saves = ds
            else:
                # old>0 ridotto a 0 senza sforamento massiccio -> privo di sensi/
                # morente con tracker fresco. L'azzeramento esplicito ripulisce
                # anche un eventuale "stable" stantio (RAW: chi scende a 0 HP
                # ricomincia a morire da capo).
                char.death_saves = {"successes": 0, "failures": 0, "stable": False}

        # Notifica best-effort ai compagni di sessione (categoria party_emergency)
        if char.current_hit_points == 0 and amount > 0:
            if char.is_dead:
                await notify_party_emergency(session, char, f"💀 {char.name} è morto!")
            elif old > 0:
                await notify_party_emergency(
                    session, char, f"🩸 {char.name} è a terra (0 PF)!")

        # Privo di sensi (0 PF) => fine concentrazione (RAW)
        if char.current_hit_points == 0:
            char.concentrating_spell_id = None

        # Auto concentration save — only if still conscious and concentrating
        if (
            char.concentrating_spell_id is not None
            and char.current_hit_points > 0
        ):
            conc_result = roll_concentration_save(char, body.value, session)

        # Emit homebrew events: damage_taken (always) + dropped_to_zero (when HP crossed 0).
        # event.amount is the GROSS damage requested (body.value, before temp-HP
        # absorption); the actual HP lost is current_hp_before - current_hp_after. This
        # is the canonical semantics — actions.execute_damage_character matches it (#29).
        firing = await dispatch(
            session, char, "damage_taken",
            {
                "amount": body.value,
                "was_critical_hit": body.was_critical_hit,
                "current_hp_before": old,
                "current_hp_after": char.current_hit_points,
            },
        )
        notifications.extend(collect_homebrew_notifications(firing))
        if old > 0 and char.current_hit_points == 0:
            firing = await dispatch(
                session, char, "dropped_to_zero",
                {
                    "damage_amount": body.value,
                    "from_critical": body.was_critical_hit,
                },
            )
            notifications.extend(collect_homebrew_notifications(firing))

    elif body.op == HPOp.HEAL:
        # Shared applier (see api/services/effects.py). The bottom-of-function
        # death-save reset block stays as an idempotent no-op: apply_heal already
        # zeroed the saves, so its guard finds nothing to reset and won't double-log.
        result = await apply_heal(session, char, body.value)
        notifications.extend(collect_homebrew_notifications(result["firing"]))

    elif body.op == HPOp.SET_MAX:
        old = char.hit_points
        char.hit_points = max(0, body.value)
        # Clamp current to new max
        char.current_hit_points = min(char.current_hit_points, char.hit_points)
        _add_history(session, char.id, "hp_change",
                     f"HP max impostati: {old} → {char.hit_points}",
                     meta={"op": "SET_MAX"})

    elif body.op == HPOp.SET_CURRENT:
        old = char.current_hit_points
        char.current_hit_points = max(0, min(char.hit_points, body.value))
        _add_history(session, char.id, "hp_change",
                     f"HP correnti impostati: {old} → {char.current_hit_points}",
                     meta={"op": "SET_CURRENT"})

    elif body.op == HPOp.SET_TEMP:
        char.temp_hp = max(0, body.value)

    # Auto-reset death saves when rising from 0 HP
    if was_at_zero and char.current_hit_points > 0:
        ds = dict(char.death_saves or {})
        if ds.get("successes", 0) > 0 or ds.get("failures", 0) > 0 or ds.get("stable", False):
            char.death_saves = {"successes": 0, "failures": 0, "stable": False}
            _add_history(session, char.id, "death_save",
                         "Tiri salvezza morte azzerati (HP risaliti sopra 0)")

    result = await build_character_response(session, char)
    if conc_result is not None:
        result.concentration_save = conc_result
    if notifications:
        result.homebrew_notifications = notifications
    return result


# ---------------------------------------------------------------------------
# Rest
# ---------------------------------------------------------------------------

@router.post("/{char_id}/rest", response_model=CharacterFull)
async def rest(
    char_id: int,
    body: RestRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)
    # Un riposo non rianima un personaggio morto.
    if char.is_dead:
        return await build_character_response(session, char)
    notifications: list[dict] = []

    if body.rest_type == "long":
        # Restore to effective max HP (base + passive homebrew modifier).
        hb_hp_bonus = await get_passive_modifiers(session, char, "character.hit_points_max")
        char.current_hit_points = char.hit_points + hb_hp_bonus
        char.temp_hp = 0
        # Break concentration
        char.concentrating_spell_id = None
        # Reset all spell slots
        for slot in char.spell_slots:
            slot.used = 0
        # Restore long-rest AND short-rest abilities (long rest includes short rest
        # benefits). Le ex-risorse di classe sono ora Ability e rientrano qui.
        for ability in char.abilities:
            if ability.restoration_type in ("long_rest", "short_rest") and ability.max_uses is not None:
                ability.uses = ability.max_uses
        # Homebrew resources auto-restore on rest by restoration_type (D3),
        # mirroring abilities: a long rest restores both long_rest and short_rest.
        for resource in char.homebrew_resources:
            if resource.restoration_type in ("long_rest", "short_rest"):
                resource.current = resource.max
        # Reset death saves
        char.death_saves = {"successes": 0, "failures": 0, "stable": False}
        # A long rest reduces Exhaustion by 1 level (PHB p.186). Keep the value an
        # int (never False/None) to avoid the F04 history-serializer bug.
        conditions = dict(char.conditions or {})
        old_exh = conditions.get("exhaustion", 0)
        old_exh = int(old_exh) if isinstance(old_exh, (int, bool)) and old_exh is not None else 0
        if old_exh > 0:
            new_exh = old_exh - 1
            conditions["exhaustion"] = new_exh
            char.conditions = conditions
            _add_history(session, char.id, "condition_change",
                         f"Spossatezza: livello {old_exh} → {new_exh} (riposo lungo)")
        _add_history(session, char.id, "rest", "Riposo lungo completato")

        firing = await dispatch(session, char, "long_rest_taken", {})
        notifications.extend(collect_homebrew_notifications(firing))

    elif body.rest_type == "short":
        # Break concentration
        char.concentrating_spell_id = None
        # Warlock Pact Magic slots recover on a short rest (unlike regular slots).
        for slot in char.spell_slots:
            if slot.is_pact:
                slot.used = 0
        healed = 0
        if body.hit_dice_used and body.hit_dice_used > 0:
            # Simple roll: average hit die value * count (frontend handles the roll display)
            healed = body.hit_dice_used
            # Use effective max HP (base + passive homebrew modifier) as the heal cap.
            hb_hp_bonus_short = await get_passive_modifiers(session, char, "character.hit_points_max")
            char.current_hit_points = min(char.hit_points + hb_hp_bonus_short, char.current_hit_points + healed)
        # Restore short-rest abilities (le ex-risorse di classe sono ora Ability).
        for ability in char.abilities:
            if ability.restoration_type == "short_rest" and ability.max_uses is not None:
                ability.uses = ability.max_uses
        # Homebrew resources: a short rest restores only short_rest resources (D3).
        for resource in char.homebrew_resources:
            if resource.restoration_type == "short_rest":
                resource.current = resource.max
        _add_history(session, char.id, "rest",
                     f"Riposo breve completato (HP recuperati: {healed})")

        firing = await dispatch(session, char, "short_rest_taken", {})
        notifications.extend(collect_homebrew_notifications(firing))
    else:
        raise HTTPException(status_code=400, detail="rest_type must be 'long' or 'short'")

    result = await build_character_response(session, char)
    if notifications:
        result.homebrew_notifications = notifications
    return result


# ---------------------------------------------------------------------------
# Death saves
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Hit dice spending (during short rest)
# ---------------------------------------------------------------------------

@router.post("/{char_id}/hit_dice/spend", response_model=HitDiceSpendResult)
async def spend_hit_dice(
    char_id: int,
    body: HitDiceSpendRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HitDiceSpendResult:
    char = await _get_owned_full(char_id, user_id, session)

    # Find the class
    cls = next((c for c in char.classes if c.id == body.class_id), None)
    if cls is None:
        raise HTTPException(status_code=404, detail="Class not found")
    if body.count < 1:
        raise HTTPException(status_code=400, detail="count must be >= 1")

    # Pool residuo per classe (spec 2026-07-17): level - hit_dice_used.
    remaining = max(0, cls.level - (cls.hit_dice_used or 0))
    if body.count > remaining:
        raise HTTPException(status_code=409, detail="hit_dice_exhausted")

    hit_die = cls.hit_die or 8

    # CON modifier
    con_score = next((s for s in char.ability_scores if s.name == "constitution"), None)
    con_mod = con_score.modifier if con_score else 0

    rolls = [random.randint(1, hit_die) for _ in range(body.count)]
    # Each die heals roll + CON mod (minimum 1 per die)
    per_die = [max(1, r + con_mod) for r in rolls]
    total_healed = sum(per_die)

    old_hp = char.current_hit_points
    char.current_hit_points = min(char.hit_points, old_hp + total_healed)
    actual_healed = char.current_hit_points - old_hp

    cls.hit_dice_used = (cls.hit_dice_used or 0) + body.count

    _add_history(session, char.id, "hit_dice",
                 f"Dado vita {body.count}d{hit_die}+{con_mod}: "
                 f"tiri={rolls}, curati={actual_healed} HP ({old_hp} → {char.current_hit_points})")
    record_dice(char, [(f"d{hit_die}", r) for r in rolls])

    return HitDiceSpendResult(
        rolls=rolls,
        con_bonus=con_mod,
        healed=actual_healed,
        new_current_hp=char.current_hit_points,
    )


@router.patch("/{char_id}/death_saves", response_model=CharacterFull)
async def update_death_saves(
    char_id: int,
    body: DeathSaveUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)
    if char.is_dead:
        return await build_character_response(session, char)
    ds = dict(char.death_saves or {"successes": 0, "failures": 0, "stable": False})

    if body.action == DeathSaveAction.SUCCESS:
        ds["successes"] = min(3, ds.get("successes", 0) + 1)
        if ds["successes"] >= 3:
            ds["stable"] = True
            _add_history(session, char.id, "death_save", "Stabilizzato (3 successi)")
        else:
            _add_history(session, char.id, "death_save",
                         f"Tiro morte: successo ({ds['successes']}/3)")

    elif body.action == DeathSaveAction.FAILURE:
        ds["failures"] = min(3, ds.get("failures", 0) + 1)
        _add_history(session, char.id, "death_save",
                     f"Tiro morte: fallimento ({ds['failures']}/3)")
        if ds["failures"] >= 3:
            char.is_dead = True
            _add_history(session, char.id, "death_save", "Morto — 3 fallimenti")
            await notify_party_emergency(session, char, f"💀 {char.name} è morto!")

    elif body.action == DeathSaveAction.STABILIZE:
        # RAW: stabilizzare (Medicina CD 10, Risparmiare i Morenti) non cura —
        # la creatura resta a 0 HP, priva di sensi ma stabile. La risalita a
        # HP positivi passa solo da cure/riposo, che azzerano il tracker.
        ds["stable"] = True
        _add_history(session, char.id, "death_save", "Stabilizzato")

    elif body.action == DeathSaveAction.RESET:
        ds = {"successes": 0, "failures": 0, "stable": False}

    elif body.action == DeathSaveAction.ROLL:
        # Handled by the dedicated roll endpoint below
        pass

    char.death_saves = ds
    return await build_character_response(session, char)


# ---------------------------------------------------------------------------
# Death save roll (d20 with special D&D 5e rules)
# ---------------------------------------------------------------------------

@router.post("/{char_id}/death_saves/roll", response_model=DeathSaveRollResult)
async def roll_death_save(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    body: Annotated[D20RollSubmission | None, Body()] = None,
) -> DeathSaveRollResult:
    char = await _get_owned_full(char_id, user_id, session)
    if char.is_dead:
        return DeathSaveRollResult(
            die=0, outcome="failure",
            successes=(char.death_saves or {}).get("successes", 0),
            failures=(char.death_saves or {}).get("failures", 0),
            stable=(char.death_saves or {}).get("stable", False),
            revived=False, current_hp=char.current_hit_points,
        )
    ds = dict(char.death_saves or {"successes": 0, "failures": 0, "stable": False})

    die = body.die if body and body.die is not None else random.randint(1, 20)
    record_dice(char, [("d20", die)])
    revived = False

    if die == 20:
        # Natural 20: revive with 1 HP
        ds = {"successes": 0, "failures": 0, "stable": False}
        char.current_hit_points = 1
        revived = True
        outcome = "nat20"
        _add_history(session, char.id, "death_save",
                     f"Tiro morte d20={die}: Naturale 20! Rianimato con 1 HP")

    elif die == 1:
        # Natural 1: counts as 2 failures
        ds["failures"] = min(3, ds.get("failures", 0) + 2)
        outcome = "nat1"
        _add_history(session, char.id, "death_save",
                     f"Tiro morte d20={die}: Naturale 1! 2 fallimenti ({ds['failures']}/3)")

    elif die >= 10:
        # 10+: 1 success
        ds["successes"] = min(3, ds.get("successes", 0) + 1)
        outcome = "success"
        if ds["successes"] >= 3:
            ds["stable"] = True
            _add_history(session, char.id, "death_save",
                         f"Tiro morte d20={die}: Successo! Stabilizzato (3/3)")
        else:
            _add_history(session, char.id, "death_save",
                         f"Tiro morte d20={die}: Successo ({ds['successes']}/3)")

    else:
        # 2-9: 1 failure
        ds["failures"] = min(3, ds.get("failures", 0) + 1)
        outcome = "failure"
        _add_history(session, char.id, "death_save",
                     f"Tiro morte d20={die}: Fallimento ({ds['failures']}/3)")

    char.death_saves = ds

    if ds.get("failures", 0) >= 3:
        char.is_dead = True
        _add_history(session, char.id, "death_save", "Morto — 3 fallimenti")
        await notify_party_emergency(session, char, f"💀 {char.name} è morto!")

    return DeathSaveRollResult(
        die=die,
        outcome=outcome,
        successes=ds["successes"],
        failures=ds["failures"],
        stable=ds.get("stable", False),
        revived=revived,
        current_hp=char.current_hit_points,
    )


# ---------------------------------------------------------------------------
# HP recalculation from D&D 5e fixed formula
# ---------------------------------------------------------------------------

@router.post("/{char_id}/hp/recalc", response_model=CharacterFull)
async def recalc_hp(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    """Recalculate hit_points from D&D 5e fixed formula.

    Computes total_base_hp using character's current classes (with first
    class owning level 1), current CON mod (effective with equipped items),
    then sets hit_points to that value. current_hit_points is clamped:
    - If new_max > old_max: current += (new_max - old_max)
    - If new_max < old_max: current = min(current, new_max)
    """
    char = await _get_owned_full(char_id, user_id, session)

    con_mod = effective_con_mod(char)
    new_max = total_base_hp(char.classes, con_mod)

    old_max = char.hit_points
    char.hit_points = new_max
    if new_max > old_max:
        char.current_hit_points = max(0, char.current_hit_points + (new_max - old_max))
    else:
        char.current_hit_points = min(char.current_hit_points, new_max)

    _add_history(session, char.id, "hp_change",
                 f"HP ricalcolati da formula: {old_max} → {new_max}",
                 meta={"op": "SET_MAX"})

    await session.commit()
    await session.refresh(char)
    return await build_character_response(session, char)


# ---------------------------------------------------------------------------
# Revive (manual revival — represents off-app revival magic)
# ---------------------------------------------------------------------------

@router.post("/{char_id}/revive", response_model=CharacterFull)
async def revive(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    """Bring a dead character back with 1 HP. No-op if not dead (idempotent)."""
    char = await _get_owned_full(char_id, user_id, session)
    if char.is_dead:
        char.is_dead = False
        char.current_hit_points = 1
        char.death_saves = {"successes": 0, "failures": 0, "stable": False}
        char.concentrating_spell_id = None
        _add_history(session, char.id, "death_save", "Riportato in vita (1 PF)")
    return await build_character_response(session, char)
