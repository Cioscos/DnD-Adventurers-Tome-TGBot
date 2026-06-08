"""Inventory (bag) endpoints."""

from __future__ import annotations

import json
import random
import re
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_user
from api.database import get_db
from core.db.models import Character, CharacterClass, CharacterHistory, EquipmentSlot, Item
from api.schemas.character import CharacterFull
from api.schemas.item import ItemCreate, ItemRead, ItemUpdate, WeaponAttackResult
from core.game.stats import effective_ability_score
from core.game.attacks import unarmed_strike_profile
from api.routers._helpers import collect_homebrew_notifications, effective_con_mod
from api.services.equipment import slot_allowed_for_type, swap_slot_occupant
from api.services.homebrew.dispatcher import dispatch
from api.services.character_response import build_character_response
from api.services.effects import apply_heal, apply_conditions
from api.schemas.common import ConsumableUseResult

router = APIRouter(prefix="/characters", tags=["items"])


def _apply_hp_delta(char, delta_hp: int) -> None:
    """Apply an integer HP delta to both max and current, floor at 0."""
    if delta_hp == 0:
        return
    char.hit_points = max(0, char.hit_points + delta_hp)
    char.current_hit_points = max(0, min(char.current_hit_points + delta_hp, char.hit_points))


_DICE_RE = re.compile(r"^(\d+)d(\d+)([+-]\d+)?$", re.IGNORECASE)


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _add_history(session, char_id: int, event_type: str, description: str) -> None:
    session.add(CharacterHistory(
        character_id=char_id,
        timestamp=_now(),
        event_type=event_type,
        description=description,
    ))


def _roll_dice(notation: str) -> tuple[list[int], int]:
    """Roll dice from notation like '1d8' or '2d6+2'. Returns (rolls, bonus)."""
    m = _DICE_RE.match(notation.strip())
    if not m:
        return [0], 0
    count = int(m.group(1))
    sides = int(m.group(2))
    bonus = int(m.group(3)) if m.group(3) else 0
    rolls = [random.randint(1, sides) for _ in range(count)]
    return rolls, bonus


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


@router.get("/{char_id}/items", response_model=list[ItemRead])
async def list_items(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[Item]:
    char = await _get_owned_full(char_id, user_id, session)
    return char.items


@router.post("/{char_id}/items", response_model=CharacterFull, status_code=201)
async def add_item(
    char_id: int,
    body: ItemCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)

    # Deduplication for generic items: merge quantity if same name exists
    if body.item_type == "generic":
        existing_result = await session.execute(
            select(Item).where(
                Item.character_id == char_id,
                Item.item_type == "generic",
                Item.name == body.name,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            existing.quantity += body.quantity
            await session.flush()
            char.recalculate_encumbrance()
            await session.refresh(char, attribute_names=["items"])
            return await build_character_response(session, char)

    metadata_str = json.dumps(body.item_metadata) if body.item_metadata else None
    item = Item(
        character_id=char_id,
        name=body.name,
        description=body.description,
        weight=body.weight,
        quantity=body.quantity,
        item_type=body.item_type,
        item_metadata=metadata_str,
        is_equipped=body.is_equipped,
        equipment_slot=body.equipment_slot,
    )
    session.add(item)
    await session.flush()
    char.recalculate_encumbrance()
    await session.refresh(char, attribute_names=["items"])
    return await build_character_response(session, char)


@router.patch("/{char_id}/items/{item_id}", response_model=CharacterFull)
async def update_item(
    char_id: int,
    item_id: int,
    body: ItemUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)
    result = await session.execute(
        select(Item).where(Item.id == item_id, Item.character_id == char_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    # Snapshot CON modifier BEFORE any item changes
    old_con_mod = effective_con_mod(char)

    # Snapshot equipped state for the homebrew event below. Captured BEFORE the
    # setattr loop so we can detect a True→False / False→True transition.
    was_equipped = item.is_equipped

    data = body.model_dump(exclude_unset=True)
    if "item_metadata" in data:
        data["item_metadata"] = json.dumps(data["item_metadata"]) if data["item_metadata"] else None

    # Validate slot/type compatibility using the (post-update) item_type.
    new_type = data.get("item_type", item.item_type)
    new_slot = data.get("equipment_slot", item.equipment_slot)
    if new_slot is not None and not slot_allowed_for_type(new_type, new_slot):
        raise HTTPException(
            status_code=422,
            detail=f"equipment_slot {new_slot.value!r} not allowed for item_type {new_type!r}",
        )

    # Apply the partial update.
    for field, value in data.items():
        setattr(item, field, value)

    # Slot bookkeeping: when equipped with a slot, displace prior occupant atomically.
    # When unequipped, clear the slot so it never leaks.
    displaced: Optional[Item] = None
    if "is_equipped" in data or "equipment_slot" in data:
        if item.is_equipped and item.equipment_slot is not None:
            displaced = await swap_slot_occupant(session, char.id, item.id, item.equipment_slot)
        if not item.is_equipped:
            item.equipment_slot = None

    # Auto-update character AC when equipping/unequipping armor or shields.
    # Skip the base when the user set a manual override OR Unarmored Defense is active
    # (the latter owns the base AC and requires wearing no armor).
    if "is_equipped" in data or "equipment_slot" in data:
        item_meta = json.loads(item.item_metadata) if item.item_metadata else {}
        base_locked = char.base_armor_class_override or bool(char.unarmored_defense_ability)
        if item.item_type == "armor" and not base_locked:
            char.base_armor_class = item_meta.get("ac_value", 10) if item.is_equipped else 10
        elif item.item_type == "shield" and not char.shield_armor_class_override:
            char.shield_armor_class = item_meta.get("ac_bonus", 2) if item.is_equipped else 0

        # If the swap displaced an armor or shield, reset its AC contribution.
        if displaced is not None:
            if displaced.item_type == "armor" and not base_locked:
                char.base_armor_class = 10
            elif displaced.item_type == "shield" and not char.shield_armor_class_override:
                char.shield_armor_class = 0

    # Auto-recompute HP when CON modifier changes due to equip/unequip
    settings = char.settings or {}
    if settings.get("hp_auto_calc", True):
        new_con_mod = effective_con_mod(char)
        delta = new_con_mod - old_con_mod
        if delta != 0:
            _apply_hp_delta(char, delta * char.total_level)

    char.recalculate_encumbrance()
    # Flush + refresh so the post-update Character (and items) are visible to
    # both dispatch (which inspects subjects) and the response builder. The
    # earlier swap_slot_occupant() can autoflush + expire `char` attributes,
    # which would otherwise break `CharacterFull.model_validate(char)` below.
    await session.flush()
    await session.refresh(char, attribute_names=["items"])

    # Emit item_equipped / item_unequipped events for installed homebrew rules.
    # SCOPE: only the explicitly-patched item — the displaced occupant (from
    # swap_slot_occupant) is NOT dispatched on, even though its `is_equipped`
    # was flipped to False as a side-effect. This keeps the event surface
    # 1-to-1 with the user's PATCH intent; if rules need to react to slot-swap
    # displacement, that's a separate event for a future iteration.
    notifications: list[dict] = []
    if body.is_equipped is not None and body.is_equipped != was_equipped:
        event_type = "item_equipped" if body.is_equipped else "item_unequipped"
        slot_value = item.equipment_slot.value if item.equipment_slot is not None else None
        firing = await dispatch(
            session, char, event_type,
            {
                "item_id": item.id,
                "item_type": item.item_type,
                "slot": slot_value,
                "was_equipped": was_equipped,
                "is_equipped": item.is_equipped,
            },
        )
        notifications = collect_homebrew_notifications(firing)

    response = await build_character_response(session, char)
    if notifications:
        response.homebrew_notifications = notifications
    return response


@router.delete("/{char_id}/items/{item_id}", response_model=CharacterFull)
async def delete_item(
    char_id: int,
    item_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)
    result = await session.execute(
        select(Item).where(Item.id == item_id, Item.character_id == char_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    await session.delete(item)
    await session.flush()
    char.recalculate_encumbrance()
    await session.refresh(char, attribute_names=["items"])
    return await build_character_response(session, char)


# ---------------------------------------------------------------------------
# Use consumable
# ---------------------------------------------------------------------------

@router.post("/{char_id}/items/{item_id}/use", response_model=CharacterFull)
async def use_consumable(
    char_id: int,
    item_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)
    # Da morto ogni uso di consumabile è inerte (coerente con /hp).
    if char.is_dead:
        return await build_character_response(session, char)

    result = await session.execute(
        select(Item).where(Item.id == item_id, Item.character_id == char_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.item_type != "consumable":
        raise HTTPException(status_code=400, detail="Item is not a consumable")

    meta = json.loads(item.item_metadata) if item.item_metadata else {}
    effects = meta.get("effects") or []
    if not effects:
        raise HTTPException(status_code=400, detail="Consumable has no usable effects")
    if item.quantity <= 0:
        raise HTTPException(status_code=409, detail="No quantity left")

    heal_rolls: list[int] = []
    total_healed = 0
    cond_changes: dict[str, bool] = {}
    notifications: list[dict] = []

    for eff in effects:
        kind = eff.get("kind")
        if kind == "heal":
            amount_str = str(eff.get("amount", "0")).strip()
            if _DICE_RE.match(amount_str):
                rolls, bonus = _roll_dice(amount_str)
                amount = max(0, sum(rolls) + bonus)
                heal_rolls.extend(rolls)
            else:
                try:
                    amount = max(0, int(amount_str))
                except ValueError:
                    amount = 0
                heal_rolls.append(amount)
            heal_result = await apply_heal(session, char, amount)
            total_healed += heal_result["healed"]
            notifications.extend(collect_homebrew_notifications(heal_result["firing"]))
        elif kind == "add_condition":
            slug = eff.get("condition")
            if slug:
                cond_changes[slug] = True
        elif kind == "remove_condition":
            slug = eff.get("condition")
            if slug:
                cond_changes[slug] = False

    conditions_added = sorted(s for s, v in cond_changes.items() if v)
    conditions_removed = sorted(s for s, v in cond_changes.items() if not v)
    if cond_changes:
        await apply_conditions(session, char, cond_changes)

    item.quantity = max(0, item.quantity - 1)
    _add_history(session, char.id, "item_used", f"Usato: {item.name}")

    await session.flush()
    await session.refresh(char, attribute_names=["items"])
    response = await build_character_response(session, char)
    response.consumable_use = ConsumableUseResult(
        heal_rolls=heal_rolls,
        total_healed=total_healed,
        conditions_added=conditions_added,
        conditions_removed=conditions_removed,
    )
    if notifications:
        response.homebrew_notifications = notifications
    return response


# ---------------------------------------------------------------------------
# Weapon attack roll
# ---------------------------------------------------------------------------

class AttackSubmission(BaseModel):
    """Optional payload for weapon attacks. Today only carries the inspiration flag."""
    with_inspiration: bool = False


@router.post("/{char_id}/items/{item_id}/attack", response_model=WeaponAttackResult)
async def attack_with_weapon(
    char_id: int,
    item_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    body: Annotated[AttackSubmission | None, Body()] = None,
) -> WeaponAttackResult:
    char = await _get_owned_full(char_id, user_id, session)
    result = await session.execute(
        select(Item).where(Item.id == item_id, Item.character_id == char_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.item_type != "weapon":
        raise HTTPException(status_code=400, detail="Item is not a weapon")

    if body and body.with_inspiration:
        if not char.heroic_inspiration:
            raise HTTPException(status_code=409, detail="Ispirazione non disponibile")
        char.heroic_inspiration = False

    meta = json.loads(item.item_metadata) if item.item_metadata else {}
    damage_dice_str: str = meta.get("damage_dice", "1d4")
    weapon_type: str = meta.get("weapon_type", "melee")
    properties: list[str] = meta.get("properties", [])

    # Determine ability modifier
    def _mod(ability: str) -> int:
        sc = next((s for s in char.ability_scores if s.name == ability), None)
        return sc.modifier if sc else 0

    str_mod = _mod("strength")
    dex_mod = _mod("dexterity")

    is_finesse = any("finesse" in p.lower() for p in properties)
    is_ranged = weapon_type == "ranged"

    if is_finesse:
        ability_mod = max(str_mod, dex_mod)
    elif is_ranged:
        ability_mod = dex_mod
    else:
        ability_mod = str_mod

    pb = char.proficiency_bonus

    # To-hit roll
    to_hit_die = random.randint(1, 20)
    to_hit_bonus = ability_mod + pb
    to_hit_total = to_hit_die + to_hit_bonus
    is_critical = to_hit_die == 20
    is_fumble = to_hit_die == 1

    # Damage roll
    damage_rolls, dice_bonus = _roll_dice(damage_dice_str)
    if is_critical:
        # Double the dice on crit
        extra_rolls, _ = _roll_dice(damage_dice_str)
        damage_rolls = damage_rolls + extra_rolls
    if is_fumble:
        damage_rolls = [0]
        dice_bonus = 0
        damage_bonus = 0
        damage_total = 0
    else:
        damage_bonus = ability_mod + dice_bonus
        damage_total = max(0, sum(damage_rolls) + damage_bonus)

    result_str = (
        f"Attacco {item.name}: colpire d20={to_hit_die}+{to_hit_bonus}={to_hit_total}"
        + (" (CRITICO!)" if is_critical else " (FUMBLE!)" if is_fumble else "")
        + f" | Danno: {'+'.join(str(r) for r in damage_rolls)}+{damage_bonus}={damage_total}"
    )
    if body and body.with_inspiration:
        result_str = f"Reroll ispirazione (to-hit): {result_str}"
    _add_history(session, char.id, "attack_roll", result_str)

    # Emit homebrew event so installed rules (e.g. Qualità & Usura) can react.
    firing_results = await dispatch(
        session, char, "attack_rolled",
        {
            "item_id": item.id,
            "to_hit_die": to_hit_die,
            "to_hit_total": to_hit_total,
            "is_critical": is_critical,
            "is_fumble": is_fumble,
            "damage_total": damage_total,
        },
    )
    notifications = collect_homebrew_notifications(firing_results)

    return WeaponAttackResult(
        weapon_name=item.name,
        to_hit_die=to_hit_die,
        to_hit_bonus=to_hit_bonus,
        to_hit_total=to_hit_total,
        is_critical=is_critical,
        is_fumble=is_fumble,
        damage_dice=damage_dice_str,
        damage_rolls=damage_rolls,
        damage_bonus=damage_bonus if not is_fumble else 0,
        damage_total=damage_total,
        homebrew_notifications=notifications if notifications else None,
    )


# ---------------------------------------------------------------------------
# Unarmed strike
# ---------------------------------------------------------------------------

@router.post("/{char_id}/attack/unarmed", response_model=WeaponAttackResult)
async def attack_unarmed(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    body: Annotated[AttackSubmission | None, Body()] = None,
) -> WeaponAttackResult:
    """Unarmed strike: 1+STR bludgeoning; Monk uses best of STR/DEX + Martial Arts die."""
    char = await _get_owned_full(char_id, user_id, session)

    if body and body.with_inspiration:
        if not char.heroic_inspiration:
            raise HTTPException(status_code=409, detail="Ispirazione non disponibile")
        char.heroic_inspiration = False

    def _mod(ability: str) -> int:
        sc = next((s for s in char.ability_scores if s.name == ability), None)
        return sc.modifier if sc else 0

    str_mod = _mod("strength")
    dex_mod = _mod("dexterity")
    monk_level = next(
        (c.level for c in char.classes if c.class_name.lower() == "monaco"), 0
    )

    ability_mod, damage_dice_str = unarmed_strike_profile(str_mod, dex_mod, monk_level)
    pb = char.proficiency_bonus

    to_hit_die = random.randint(1, 20)
    to_hit_bonus = ability_mod + pb
    to_hit_total = to_hit_die + to_hit_bonus
    is_critical = to_hit_die == 20
    is_fumble = to_hit_die == 1

    dice_bonus = 0
    if damage_dice_str == "1":
        # Flat-1 unarmed damage (non-Monk): no dice component, so a crit does
        # NOT double it (D&D 5e: crit doubles dice, not the flat 1 + mod).
        damage_rolls = [1]
    else:
        damage_rolls, dice_bonus = _roll_dice(damage_dice_str)
        if is_critical:
            extra_rolls, _ = _roll_dice(damage_dice_str)
            damage_rolls = damage_rolls + extra_rolls

    if is_fumble:
        damage_rolls = [0]
        damage_bonus = 0
        damage_total = 0
    else:
        damage_bonus = ability_mod + dice_bonus
        damage_total = max(0, sum(damage_rolls) + damage_bonus)

    weapon_name = "Attacco a mano libera"
    result_str = (
        f"Attacco {weapon_name}: colpire d20={to_hit_die}+{to_hit_bonus}={to_hit_total}"
        + (" (CRITICO!)" if is_critical else " (FUMBLE!)" if is_fumble else "")
        + f" | Danno: {'+'.join(str(r) for r in damage_rolls)}+{damage_bonus}={damage_total}"
    )
    if body and body.with_inspiration:
        result_str = f"Reroll ispirazione (to-hit): {result_str}"
    _add_history(session, char.id, "attack_roll", result_str)

    firing_results = await dispatch(
        session, char, "attack_rolled",
        {
            "item_id": None,
            "to_hit_die": to_hit_die,
            "to_hit_total": to_hit_total,
            "is_critical": is_critical,
            "is_fumble": is_fumble,
            "damage_total": damage_total,
        },
    )
    notifications = collect_homebrew_notifications(firing_results)

    return WeaponAttackResult(
        weapon_name=weapon_name,
        to_hit_die=to_hit_die,
        to_hit_bonus=to_hit_bonus,
        to_hit_total=to_hit_total,
        is_critical=is_critical,
        is_fumble=is_fumble,
        damage_dice=damage_dice_str,
        damage_rolls=damage_rolls,
        damage_bonus=damage_bonus if not is_fumble else 0,
        damage_total=damage_total,
        homebrew_notifications=notifications if notifications else None,
    )
