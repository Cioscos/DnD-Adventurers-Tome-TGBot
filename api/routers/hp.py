"""HP, rest, and death save endpoints."""

from __future__ import annotations

import random
import uuid
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.database import get_db
from api.services.d20 import d20_records, resolve_body
from api.services.dice_stats import record_dice
from api.services.effects import apply_heal
from api.services.item_charges import plan_item_recharges, set_item_charges
from api.services.durations import end_concentration, is_concentrating
from api.routers.companions import _deactivate_others
from api.services.wild_shape import absorb_damage, get_active_form
from api.services.telegram_notify import notify_party_emergency
from api.services.homebrew.dispatcher import dispatch
from api.services.homebrew.passive import get_passive_modifiers
from core.db.models import Character, CharacterHistory, Companion
from api.schemas.character import CharacterFull
from api.schemas.common import (
    D20RollSubmission,
    DeathSaveRollResult,
    DeathSaveUpdate,
    DeathSaveAction,
    HPOp,
    HPUndoRequest,
    HPUpdate,
    ItemChargePreview,
    RestPreview,
    RestRequest,
)
from core.data.damage_types import LABELS_IT, canonical_damage_type, damage_multiplier
from api.services.hp_rolls import stored_rolls
from core.game.stats import total_base_hp
from api.routers._helpers import collect_homebrew_notifications, effective_con_mod, roll_concentration_save
from api.schemas.common import ConcentrationSaveResult
from api.services.character_response import build_character_response


class HitDiceSpendRequest(BaseModel):
    class_id: int
    count: int
    # Facce lette dai dadi 3D; senza, tira il server.
    rolls: list[int] | None = None


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


_CONC_SETTINGS = ("concentration_rounds_left", "concentration_item_spell")


def _hp_state(char: Character, form=None) -> dict:
    """Campi toccati da un'operazione PF (forma selvatica inclusa), per lo snapshot di annullamento."""
    return {
        "form": None if form is None else {
            "form_id": form.id, "current_hp": form.current_hp,
            "temp_hp": form.temp_hp, "is_active": form.is_active,
        },
        "current_hit_points": char.current_hit_points,
        "hit_points": char.hit_points,
        "temp_hp": char.temp_hp,
        "death_saves": dict(char.death_saves or {}),
        "is_dead": char.is_dead,
        "concentrating_spell_id": char.concentrating_spell_id,
        **{k: (char.settings or {}).get(k) for k in _CONC_SETTINGS},
    }


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
    form = await get_active_form(session, char.id)  # the form involved in this op, if any
    before = _hp_state(char, form)
    conc_result: ConcentrationSaveResult | None = None
    notifications: list[dict] = []

    was_at_zero = char.current_hit_points == 0

    if body.op == HPOp.DAMAGE:
        # Danno applicato dopo resistenza/immunità/vulnerabilità, PRIMA di PF temporanei
        # e tiri salvezza morte (tutto il resto usa `applied`).
        slug = canonical_damage_type(body.damage_type)
        mod = body.damage_modifier
        raw = body.raw_value if body.raw_value is not None else body.value
        applied = body.value
        if mod is None and slug is not None:
            mod = damage_multiplier(char.damage_modifiers, slug)
            raw = body.value
            applied = {"half": raw // 2, "double": raw * 2, "immune": 0}.get(mod, raw)
        elif mod == "immune":
            applied = 0
        # Wild shape: the form soaks the (already resistance-adjusted, using the
        # character's modifiers) damage first; only the overflow reaches the character
        # through the normal path below (temp HP, death rules, one concentration save).
        conc_damage = applied
        form_absorbed = False
        pre_form = applied
        form_overflow = 0
        if form is not None and applied > 0:
            overflow = absorb_damage(form, applied)
            if overflow > 0:
                form_overflow = overflow
                form.is_active = False
                _add_history(session, char.id, "companion_hp",
                             f"Forma selvatica terminata: {form.name} (danno in eccesso {overflow})")
                applied = conc_damage = overflow
            else:
                form_absorbed = True
                applied = 0
                _add_history(session, char.id, "companion_hp",
                             f"{form.name}: -{conc_damage} → PF {form.current_hp}/{form.max_hp}, temp {form.temp_hp}")
                if form.current_hp == 0:  # 5e: the form ends at 0 HP, even with no overflow
                    form.is_active = False
                    _add_history(session, char.id, "companion_hp",
                                 f"Forma selvatica terminata: {form.name} (PF a 0)")
        amount = applied
        # Absorb temp HP first
        if char.temp_hp > 0:
            absorbed = min(char.temp_hp, amount)
            char.temp_hp -= absorbed
            amount -= absorbed
        old = char.current_hit_points
        char.current_hit_points = max(0, char.current_hit_points - amount)
        if slug is not None and mod in ("half", "double", "immune"):
            word = {"half": "resistenza", "double": "vulnerabilità", "immune": "immunità"}[mod]
            desc = (f"Danno {raw} {LABELS_IT[slug]} → {pre_form} ({word}) "
                    f"({old} → {char.current_hit_points})")
        else:
            note = ""
            if body.raw_value is not None and mod in ("half", "double"):
                word = "dimezzati" if mod == "half" else "raddoppiati"
                note = f" ({body.raw_value} {word})"
            desc = f"Danni: -{pre_form} HP{note} ({old} → {char.current_hit_points})"
        if form_overflow:
            desc += f" — forma assorbe {pre_form - form_overflow}, eccesso {form_overflow}"
        if not form_absorbed:
            _add_history(session, char.id, "hp_change", desc, meta={"op": "DAMAGE"})

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
            end_concentration(char)

        # Auto concentration save — only if still conscious and concentrating
        if (
            conc_damage > 0
            and is_concentrating(char)
            and char.current_hit_points > 0
        ):
            conc_result = await roll_concentration_save(
                char, conc_damage, session,
                "advantage" if (char.settings or {}).get("war_caster") else "normal",
            )

        # Emit homebrew events: damage_taken (always) + dropped_to_zero (when HP crossed 0).
        # event.amount is the GROSS damage requested (applied, before temp-HP
        # absorption); the actual HP lost is current_hp_before - current_hp_after. This
        # is the canonical semantics — actions.execute_damage_character matches it (#29).
        if applied > 0:
            firing = await dispatch(
                session, char, "damage_taken",
                {
                    "amount": applied,
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
                    "damage_amount": applied,
                    "from_critical": body.was_critical_hit,
                },
            )
            notifications.extend(collect_homebrew_notifications(firing))

    elif body.op == HPOp.HEAL:
        # Shared applier (see api/services/effects.py). The bottom-of-function
        # death-save reset block stays as an idempotent no-op: apply_heal already
        # zeroed the saves, so its guard finds nothing to reset and won't double-log.
        if form is not None:  # while transformed, healing goes to the form
            form.current_hp = min(form.max_hp, form.current_hp + body.value)
            _add_history(session, char.id, "companion_hp",
                         f"{form.name}: +{body.value} → PF {form.current_hp}/{form.max_hp}")
        else:
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

    if (
        body.op in (HPOp.SET_MAX, HPOp.SET_CURRENT)
        and char.current_hit_points == 0
        and form is not None
        and form.is_active
    ):
        form.is_active = False
        _add_history(session, char.id, "companion_hp",
                     f"Forma selvatica terminata: {form.name} (PF a 0)")

    # Auto-reset death saves when rising from 0 HP
    if was_at_zero and char.current_hit_points > 0:
        ds = dict(char.death_saves or {})
        if ds.get("successes", 0) > 0 or ds.get("failures", 0) > 0 or ds.get("stable", False):
            char.death_saves = {"successes": 0, "failures": 0, "stable": False}
            _add_history(session, char.id, "death_save",
                         "Tiri salvezza morte azzerati (HP risaliti sopra 0)")

    # Nuovo dict (non mutazione in place): la colonna JSON non è tracciata.
    op_id = uuid.uuid4().hex
    char.hp_undo = {"op_id": op_id, "before": before, "after": _hp_state(char, form)}

    result = await build_character_response(session, char)
    result.hp_undo_id = op_id
    if conc_result is not None:
        result.concentration_save = conc_result
    if notifications:
        result.homebrew_notifications = notifications
    return result


@router.post("/{char_id}/hp/undo", response_model=CharacterFull)
async def undo_hp(
    char_id: int,
    body: HPUndoRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    """Annulla l'ultima operazione PF, solo se nulla è cambiato dopo di essa."""
    char = await _get_owned_full(char_id, user_id, session)
    snap = char.hp_undo
    form = None
    if snap and (snap.get("after") or {}).get("form"):
        form = (await session.execute(select(Companion).where(
            Companion.id == snap["after"]["form"]["form_id"], Companion.character_id == char.id,
        ))).scalar_one_or_none()
    if (
        not snap
        or snap.get("op_id") != body.op_id
        or _hp_state(char, form) != snap.get("after")
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="hp_undo_not_applicable")

    before = snap["before"]
    if before.get("form"):
        form.current_hp = before["form"]["current_hp"]
        form.temp_hp = before["form"]["temp_hp"]
        form.is_active = before["form"]["is_active"]
        if form.is_active:  # at most one active form
            await _deactivate_others(session, char.id, form.id)
    old = char.current_hit_points
    char.current_hit_points = before["current_hit_points"]
    char.hit_points = before["hit_points"]
    char.temp_hp = before["temp_hp"]
    char.death_saves = dict(before["death_saves"])
    char.is_dead = before["is_dead"]
    spell_id = before["concentrating_spell_id"]
    # L'incantesimo può essere stato eliminato nel frattempo.
    if spell_id is not None and not any(s.id == spell_id for s in char.spells):
        spell_id = None
    char.concentrating_spell_id = spell_id
    settings = dict(char.settings or {})
    for k in _CONC_SETTINGS:
        if before[k] is None:
            settings.pop(k, None)
        else:
            settings[k] = before[k]
    char.settings = settings
    char.hp_undo = None

    _add_history(session, char.id, "hp_change",
                 f"Annullata ultima operazione PF ({old} → {char.current_hit_points})",
                 meta={"op": "UNDO"})
    return await build_character_response(session, char)


# ---------------------------------------------------------------------------
# Rest
# ---------------------------------------------------------------------------

def _restores_ability(ability, rest_type: str) -> bool:
    # A long rest includes short-rest benefits; le ex-risorse di classe sono Ability.
    types = ("long_rest", "short_rest") if rest_type == "long" else ("short_rest",)
    return ability.restoration_type in types and ability.max_uses is not None


def _restores_resource(resource, rest_type: str) -> bool:
    types = ("long_rest", "short_rest") if rest_type == "long" else ("short_rest",)
    return resource.restoration_type in types


def compute_rest_effects(char: Character, rest_type: str, hp_max_bonus: int = 0) -> RestPreview:
    """Pure: cosa cambierebbe un riposo. Usata da /rest (che poi applica) e dall'anteprima."""
    fx = RestPreview()
    if char.is_dead:  # un riposo non rianima un personaggio morto
        return fx
    long = rest_type == "long"
    fx.ends_concentration = is_concentrating(char)
    fx.pact_slots = sum(s.used for s in char.spell_slots if s.is_pact and s.used > 0)
    if long:
        fx.hp_gain = max(0, char.hit_points + hp_max_bonus - char.current_hit_points)
        for s in char.spell_slots:
            if not s.is_pact and s.used > 0:
                fx.slots[s.level] = fx.slots.get(s.level, 0) + s.used
        # Recupero dadi vita (RAW PHB): fino a metà del totale (min 1),
        # dal dado più grande in caso di multiclasse (spec 2026-07-17).
        hd_budget = max(1, sum(c.level for c in char.classes) // 2)
        for cls in sorted(char.classes, key=lambda c: (c.hit_die or 8), reverse=True):
            if hd_budget <= 0:
                break
            spent = min(cls.hit_dice_used or 0, cls.level)
            back = min(spent, hd_budget)
            if back > 0:
                fx.hit_dice_regain[cls.id] = back
                hd_budget -= back
        # A long rest reduces Exhaustion by 1 level (PHB p.186).
        exh = (char.conditions or {}).get("exhaustion", 0)
        if isinstance(exh, int) and not isinstance(exh, bool) and exh > 0:
            fx.exhaustion_change = -1
    fx.abilities = [a.name for a in char.abilities
                    if _restores_ability(a, rest_type) and a.uses != a.max_uses]
    fx.homebrew_resources = [r.name for r in char.homebrew_resources
                             if _restores_resource(r, rest_type) and r.current != r.max]
    for r in plan_item_recharges(char.items, rest_type, roll=False):
        full = r.after is not None
        fx.item_charges.append(ItemChargePreview(
            name=r.item.name, gain=r.after - r.before if full else None,
            formula=None if full else r.formula, full=full))
    return fx


@router.get("/{char_id}/rest/preview", response_model=RestPreview)
async def rest_preview(
    char_id: int,
    rest_type: str,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RestPreview:
    if rest_type not in ("long", "short"):
        raise HTTPException(status_code=400, detail="rest_type must be 'long' or 'short'")
    char = await _get_owned_full(char_id, user_id, session)
    bonus = await get_passive_modifiers(session, char, "character.hit_points_max")
    return compute_rest_effects(char, rest_type, bonus)


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
    hb_hp_bonus = await get_passive_modifiers(session, char, "character.hit_points_max")
    fx = compute_rest_effects(char, body.rest_type, hb_hp_bonus) if body.rest_type in ("long", "short") else None
    if body.rest_type in ("long", "short"):
        for r in plan_item_recharges(char.items, body.rest_type):
            set_item_charges(r.item, r.after)
            _add_history(session, char.id, "item_charges",
                         f"Cariche ricaricate: {r.item.name} ({r.before} → {r.after})")

    if body.rest_type == "long":
        # Restore to effective max HP (base + passive homebrew modifier).
        char.current_hit_points = char.hit_points + hb_hp_bonus
        char.temp_hp = 0
        # Break concentration
        end_concentration(char)
        # Reset all spell slots
        for slot in char.spell_slots:
            slot.used = 0
        hd_regained = sum(fx.hit_dice_regain.values())
        for cls in char.classes:
            if cls.id in fx.hit_dice_regain:
                cls.hit_dice_used = min(cls.hit_dice_used or 0, cls.level) - fx.hit_dice_regain[cls.id]
        if hd_regained:
            _add_history(session, char.id, "hit_dice",
                         f"Dadi vita recuperati: {hd_regained} (riposo lungo)")
        # Restore long-rest AND short-rest abilities (long rest includes short rest
        # benefits). Le ex-risorse di classe sono ora Ability e rientrano qui.
        for ability in char.abilities:
            if _restores_ability(ability, "long"):
                ability.uses = ability.max_uses
        # Homebrew resources auto-restore on rest by restoration_type (D3),
        # mirroring abilities: a long rest restores both long_rest and short_rest.
        for resource in char.homebrew_resources:
            if _restores_resource(resource, "long"):
                resource.current = resource.max
        # Reset death saves
        char.death_saves = {"successes": 0, "failures": 0, "stable": False}
        if fx.exhaustion_change:
            # Keep the value an int (never False/None) to avoid the F04 history-serializer bug.
            conditions = dict(char.conditions or {})
            old_exh = conditions["exhaustion"]
            new_exh = old_exh + fx.exhaustion_change
            conditions["exhaustion"] = new_exh
            char.conditions = conditions
            _add_history(session, char.id, "condition_change",
                         f"Spossatezza: livello {old_exh} → {new_exh} (riposo lungo)")
        _add_history(session, char.id, "rest", "Riposo lungo completato")

        firing = await dispatch(session, char, "long_rest_taken", {})
        notifications.extend(collect_homebrew_notifications(firing))

    elif body.rest_type == "short":
        # Break concentration
        end_concentration(char)
        # Warlock Pact Magic slots recover on a short rest (unlike regular slots).
        for slot in char.spell_slots:
            if slot.is_pact:
                slot.used = 0
        healed = 0
        if body.hit_dice_used and body.hit_dice_used > 0:
            # Simple roll: average hit die value * count (frontend handles the roll display)
            healed = body.hit_dice_used
            # Use effective max HP (base + passive homebrew modifier) as the heal cap.
            char.current_hit_points = min(char.hit_points + hb_hp_bonus, char.current_hit_points + healed)
        # Restore short-rest abilities (le ex-risorse di classe sono ora Ability).
        for ability in char.abilities:
            if _restores_ability(ability, "short"):
                ability.uses = ability.max_uses
        # Homebrew resources: a short rest restores only short_rest resources (D3).
        for resource in char.homebrew_resources:
            if _restores_resource(resource, "short"):
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

    con_mod = effective_con_mod(char)

    if body.rolls is not None:
        if len(body.rolls) != body.count:
            raise HTTPException(
                status_code=400,
                detail=f"rolls length {len(body.rolls)} != expected {body.count}",
            )
        if any(v < 1 or v > hit_die for v in body.rolls):
            raise HTTPException(status_code=400, detail=f"rolls values must be in [1, {hit_die}]")
        rolls = list(body.rolls)
    else:
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

    d20 = resolve_body(body)
    die = d20.kept
    record_dice(char, d20_records(d20))
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
        dice=d20.dice,
        mode=d20.mode,
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
    new_max = total_base_hp(char.classes, con_mod, stored_rolls(char))

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
        end_concentration(char)
        _add_history(session, char.id, "death_save", "Riportato in vita (1 PF)")
    return await build_character_response(session, char)
