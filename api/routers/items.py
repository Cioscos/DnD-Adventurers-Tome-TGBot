"""Inventory (bag) endpoints."""

from __future__ import annotations

import json
import random
import re
import uuid
from datetime import datetime
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.auth import get_current_lang, get_current_user
from api.services.rules_options import (
    merge_options,
    option_result,
    remember_roll,
    roll_context,
    roll_option_dice,
    use_options,
)
from api.services.rules_turn import attacks_allowed, get_turn, refuse_if_incapacitated, spend
from api.services.class_features import sync_cataloged_features
from api.database import get_db
from api.services.d20 import D20Outcome, d20_history_label, d20_records, resolve_applied, resolve_body, spend_inspiration_reroll
from core.rules.modifiers import modifiers_for
from api.services.dice_stats import record_dice
from api.services.last_damage import pairs
from core.db.models import Character, CharacterClass, CharacterHistory, EquipmentSlot, HomebrewRule, Item
from api.schemas.character import CharacterFull
from api.schemas.item import AmmoState, ItemCreate, ItemRead, ItemUpdate, WeaponAttackResult
from core.game.stats import effective_ability_score, roll_ability_mod
from core.game.containers import container_meta, is_container
from core.game.item_bonuses import attack_bonus_total, is_attuned, item_meta
from api.routers._helpers import (
    apply_con_hp as _apply_con_hp,
    collect_homebrew_notifications,
    effective_con_mod,
    unarmed_attack_profile,
    weapon_attack_profile,
)
from api.services.durations import start_concentration
from api.services.condition_effects import release_concentration_effects
from api.services import weapon_bond
from api.services.item_charges import attunement_limit, charges_spent, set_item_charges
from core.game.actions import parse_duration_rounds
from api.services.equipment import apply_equip_ac, slot_allowed_for_type, swap_slot_occupant
from api.services.containers import move_items, reparent_contents
from api.schemas.container import ItemMoveRequest
from api.services.homebrew.dispatcher import dispatch
from api.services.character_response import build_character_response
from api.services.effects import apply_heal, apply_conditions, end_hide
from api.services.rules_states import end_on_action, end_states
from core.utils.session_view import armor_category
from api.schemas.common import ConsumableUseResult, D20Dice, RollMode, RollOptionsBody
from core.game.attacks import martial_arts_die
from core.rules.catalog import active_features
from core.rules.catalog._common import unarmored_unshielded
from core.rules.edition import character_edition
from core.rules.proficiencies import is_weapon_proficient
from core.rules.roll_options import AppliedOptions, doubled_dice, roll_options_for, scale_damage, throws_unarmed, uses_own_slot
from core.rules.weapons import NICK_OPTION, best_damage_dice, has_property, martial_arts_level

router = APIRouter(prefix="/characters", tags=["items"])


_DICE_RE = re.compile(r"^(\d+)d(\d+)([+-]\d+)?$", re.IGNORECASE)


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


def _record_attack_dice(
    char: Character,
    outcome: D20Outcome,
    damage_dice_str: str,
    damage_rolls: list[int],
    is_fumble: bool,
) -> None:
    """Statistiche: d20 di to-hit + dadi danno (esclusi fumble e danno piatto '1')."""
    record_dice(char, d20_records(outcome) + ([] if is_fumble else _damage_records(damage_dice_str, damage_rolls)))


def _damage_records(damage_dice_str: str, damage_rolls: list[int]) -> list[tuple[str, int]]:
    m = _DICE_RE.match(damage_dice_str.strip()) if damage_dice_str else None
    return [(f"d{m.group(2)}", v) for v in damage_rolls] if m else []


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


async def _apply_item_property_defaults(
    session: AsyncSession, char_id: int, item: Item
) -> None:
    """Materialize hb_<key> defaults from every enabled item-scoped homebrew rule
    onto a single newly-created item, so a rule installed BEFORE the item is
    acquired still applies to it (#32). Item-first mirror of
    homebrew._materialize_property_defaults; only sets missing keys.
    """
    res = await session.execute(
        select(HomebrewRule).where(
            HomebrewRule.character_id == char_id,
            HomebrewRule.enabled.is_(True),
        )
    )
    md = json.loads(item.item_metadata or "{}")
    changed = False
    for rule in res.scalars():
        subject_def = rule.dsl.get("subject", {})
        if subject_def.get("type") != "item":
            continue
        properties = rule.dsl.get("properties") or []
        item_types = (subject_def.get("filter") or {}).get("item_types")
        if item_types and item.item_type not in item_types:
            continue
        for prop in properties:
            key = f"hb_{prop['key']}"
            if key not in md:
                md[key] = prop["default"]
                changed = True
    if changed:
        item.item_metadata = json.dumps(md)


def is_container_meta(meta: dict | None) -> bool:
    return isinstance((meta or {}).get("container"), dict)


def _check_attunement_limit(char, item, new_meta: dict | None) -> None:
    """409 when this write newly attunes an item and the character already has 3 (4 with Use Magic Device)."""
    if not (new_meta or {}).get("attuned") or (item is not None and is_attuned(item)):
        return
    if sum(1 for i in char.items if i is not item and is_attuned(i)) >= attunement_limit(char):
        raise HTTPException(status_code=409, detail="attunement_limit")


@router.post("/{char_id}/items", response_model=CharacterFull, status_code=201)
async def add_item(
    char_id: int,
    body: ItemCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)

    if body.container_id is not None:
        parent = next((i for i in char.items if i.id == body.container_id), None)
        if parent is None:
            raise HTTPException(status_code=404, detail="Container not found")
        if not is_container(parent):
            raise HTTPException(status_code=422, detail="not_a_container")

    if is_container_meta(body.item_metadata) and body.quantity != 1:
        raise HTTPException(status_code=422, detail="container_quantity")
    if body.container_id is not None:  # contained items are never equipped
        body.is_equipped, body.equipment_slot = False, None

    # Deduplication for generic items: merge with a same-name generic in the same container
    if body.item_type == "generic" and not is_container_meta(body.item_metadata):
        existing_result = await session.execute(
            select(Item).where(
                Item.character_id == char_id,
                Item.item_type == "generic",
                Item.name == body.name,
                Item.container_id == body.container_id,
            )
        )
        existing = next((e for e in existing_result.scalars() if not is_container(e)), None)
        if existing is not None:
            existing.quantity += body.quantity
            await session.flush()
            char.recalculate_encumbrance()
            await session.refresh(char, attribute_names=["items"])
            return await build_character_response(session, char)

    _check_attunement_limit(char, None, body.item_metadata)
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
        container_id=body.container_id,
    )
    session.add(item)
    await session.flush()
    # Apply homebrew property defaults from rules installed before this item (#32).
    await _apply_item_property_defaults(session, char_id, item)
    char.recalculate_encumbrance()
    await session.refresh(char, attribute_names=["items"])
    if item.is_equipped:
        await sync_cataloged_features(session, char, lang)
    return await build_character_response(session, char)


@router.patch("/{char_id}/items/{item_id}", response_model=CharacterFull)
async def update_item(
    char_id: int,
    item_id: int,
    body: ItemUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    lang: Annotated[str, Depends(get_current_lang)],
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

    if "item_metadata" in body.model_fields_set:
        _check_attunement_limit(char, item, body.item_metadata)

    # Validate slot/type compatibility using the (post-update) item_type.
    new_type = data.get("item_type", item.item_type)
    new_slot = data.get("equipment_slot", item.equipment_slot)
    if new_slot is not None and not slot_allowed_for_type(new_type, new_slot):
        raise HTTPException(
            status_code=422,
            detail=f"equipment_slot {new_slot.value!r} not allowed for item_type {new_type!r}",
        )

    new_meta = (
        json.loads(data["item_metadata"]) if data.get("item_metadata")
        else None if "item_metadata" in data else item_meta(item)
    )
    if is_container_meta(new_meta) and data.get("quantity", item.quantity) != 1:
        raise HTTPException(status_code=422, detail="container_quantity")
    if is_container(item) and not is_container_meta(new_meta):
        await reparent_contents(session, char, item)
    if data.get("is_equipped") and item.container_id is not None:
        item.container_id = None  # equipping pulls the item out of its container

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

    if "is_equipped" in data or "equipment_slot" in data:
        apply_equip_ac(char, item, displaced)

    # Auto-recompute HP when CON modifier changes due to equip/unequip
    await _apply_con_hp(session, char, old_con_mod)

    char.recalculate_encumbrance()
    # Flush + refresh so the post-update Character (and items) are visible to
    # both dispatch (which inspects subjects) and the response builder. The
    # earlier swap_slot_occupant() can autoflush + expire `char` attributes,
    # which would otherwise break `CharacterFull.model_validate(char)` below.
    await session.flush()
    await session.refresh(char, attribute_names=["items"])
    if item.is_equipped and item.item_type == "armor" and armor_category(char) == "heavy":
        end_states(char, "heavy_armor")  # l'Ira 2024 finisce se si indossa un'armatura pesante
    await sync_cataloged_features(session, char, lang)

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


@router.post("/{char_id}/items/move", response_model=CharacterFull)
async def move_items_endpoint(
    char_id: int,
    body: ItemMoveRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)
    old_con_mod = effective_con_mod(char)
    worn = [(i, i.equipment_slot) for i in char.items if i.id in body.item_ids and i.is_equipped]
    names = await move_items(session, char, body.item_ids, body.container_id, body.quantity)
    await _apply_con_hp(session, char, old_con_mod)
    char.recalculate_encumbrance()
    await session.flush()
    await session.refresh(char, attribute_names=["items"])
    await sync_cataloged_features(session, char, lang)
    notifications: list[dict] = []
    for it, slot in worn:
        if not it.is_equipped:
            firing = await dispatch(session, char, "item_unequipped", {
                "item_id": it.id, "item_type": it.item_type,
                "slot": slot.value if slot is not None else None,
                "was_equipped": True, "is_equipped": False,
            })
            notifications += collect_homebrew_notifications(firing)
    response = await build_character_response(session, char)
    response.unequipped_item_names = names
    if notifications:
        response.homebrew_notifications = notifications
    return response


@router.delete("/{char_id}/items/{item_id}", response_model=CharacterFull)
async def delete_item(
    char_id: int,
    item_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)
    result = await session.execute(
        select(Item).where(Item.id == item_id, Item.character_id == char_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if is_container(item):
        await reparent_contents(session, char, item)
    await session.delete(item)
    await session.flush()
    char.recalculate_encumbrance()
    await session.refresh(char, attribute_names=["items"])
    await sync_cataloged_features(session, char, lang)
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

class AttackSubmission(RollOptionsBody):
    """Optional payload for attacks: inspiration flag and the d20 read by the 3D dice.

    ``defer_damage``: il danno finale aspetta le opzioni ``after_hit`` di ``/attack/{attack_id}/damage``."""
    defer_damage: bool = False
    with_inspiration: bool = False
    die: int | None = Field(default=None, ge=1, le=20)
    mode: RollMode = "normal"
    dice: D20Dice | None = None
    grip: Literal["one", "two"] = "one"
    attack_mode: Literal["melee", "thrown", "offhand"] = "melee"
    ability: Literal["strength", "dexterity"] | None = None  # dove la regola lascia la scelta; senza, la migliore
    confirm_extra_attack: bool = False  # oltre il limite dell'azione: privilegio, reazione, decisione del giocatore
    effect: Literal["damage", "grapple", "shove"] = "damage"  # colpo senz'armi 2024


def _set_pending_attack(char: Character, pending: dict | None) -> None:
    """Un solo attacco in sospeso: ogni nuovo attacco sostituisce il precedente (R8)."""
    turn = get_turn(char)
    turn.pop("pending_attack", None)
    if pending:
        turn["pending_attack"] = pending
    char.turn_state = turn


def _own_slot_attack(char: Character, body: AttackSubmission | None) -> bool:
    return bool(body and uses_own_slot(char, body.options or []))


def _note_martial_attack(char: Character, item: Item | None, body: AttackSubmission | None) -> None:
    """Arti Marziali: l'azione Attacco è stata fatta con un colpo senz'armi o un'arma da monaco, senza armatura né scudo.
    Solo così il colpo senz'armi extra con l'azione bonus è ammesso (``turn_state["martial_attack"]``)."""
    if _own_slot_attack(char, body) or not martial_arts_level(char, item):
        return
    turn = get_turn(char)
    if not turn.get("martial_attack"):
        char.turn_state = {**turn, "martial_attack": True}


def _check_attack_limit(char: Character, body: AttackSubmission | None, item: Item | None = None) -> None:
    """Il limite dell'azione Attacco si supera solo confermando: chi ha privilegi in più non va impedito.
    Non vale per un attacco con un'opzione che ha uno slot proprio (Frenesia, Ritorsione): non è un attacco dell'azione."""
    if body and (body.with_inspiration or body.confirm_extra_attack or _own_slot_attack(char, body)):
        return
    made, allowed = get_turn(char)["action_attacks"], attacks_allowed(char, item)
    if made >= allowed:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "attack_limit", "made": made, "allowed": allowed})


def _settle_attack(
    char: Character, body: AttackSubmission | None, result: WeaponAttackResult, item: Item | None, ability: str,
    attack_mode: str, grip: str, opts: AppliedOptions, offhand: bool = False,
) -> WeaponAttackResult:
    """Tiene da parte l'attacco se il danno finale aspetta le opzioni.

    Un 1 naturale non ha danno da aspettare, a meno che un'opzione dopo il tiro possa ancora cambiarlo."""
    pending = None
    item_id = item.id if item else None
    context = roll_context(char, "attack", ability=ability, item=item, attack_mode=attack_mode, grip=grip, offhand=offhand)
    if body and body.defer_damage and (
            not result.is_fumble or any(o.spec.phase == "after_roll" for o in roll_options_for(context))):
        result.attack_id = uuid.uuid4().hex
        pending = {"attack_id": result.attack_id, "item_id": item_id, "ability": ability,
                   "attack_mode": attack_mode, "grip": grip, "offhand": offhand,
                   "options": result.option_result.keys if result.option_result else [],
                   "option_dice": pairs(opts.rolled_dice), "result": result.model_dump(mode="json")}
    _set_pending_attack(char, pending)
    if pending is None:
        remember_weapon_damage(char, result, opts, opts.rolled_dice)
    remember_roll(char, "attack", opts, {
        "die": result.to_hit_die, "dice": result.dice, "mode": result.mode, "bonus": result.to_hit_bonus,
        "total": result.to_hit_total, "notes": result.notes, "auto_fail": False, "description": "",
        "option_result": result.option_result.model_dump(mode="json") if result.option_result else None,
    }, item_id=item_id, ability=ability)
    return result


_DIE = re.compile(r"(\d+)d(\d+)")


def remember_weapon_damage(
    char: Character, result: WeaponAttackResult, opts: AppliedOptions, option_dice: list, extra_bonus: int = 0,
) -> None:
    """Dadi del danno finale in ``turn_state["last_damage"]``, come per gli incantesimi: l'Ispirazione Eroica ne ritira uno.

    Valgono anche i dadi aggiunti dalle opzioni (``option_dice``). Senza dadi (danno fisso, 1 naturale, mancato) non c'è
    nulla da ritirare. ``extra_bonus``: bonus arrivato dopo il colpo, che sta nel fisso e non nel modificatore.

    shortcut: con due moltiplicatori in fasi diverse (prima del tiro e dopo il colpo) conta solo quello dell'ultima fase;
    nessuna opzione di ``core/rules`` ne dichiara uno, da rivedere con i task di classe che lo faranno."""
    turn = get_turn(char)
    turn.pop("last_damage", None)
    die = _DIE.search(result.damage_dice or "")
    # Un danno base fisso (colpo senz'armi "1") non ha dadi, ma quelli delle opzioni si ritirano lo stesso.
    if (die or option_dice) and not (result.is_fumble or result.grazed or result.effect) and opts.damage_unscaled is not None:
        fixed = 0 if die else sum(result.damage_rolls)
        rolls = result.damage_rolls if die else []
        mod = result.damage_bonus - extra_bonus + fixed
        base = len(rolls)
        dice = [[int(die[2]), v] for v in rolls] + pairs(option_dice)
        flat = opts.damage_unscaled - max(0, sum(rolls) + mod) - sum(v for _, v in option_dice)
        result.reroll_dice = dice
        turn["last_damage"] = {
            "kind": "weapon", "roll_id": uuid.uuid4().hex, "dice": dice, "main": base, "base": base, "added": [],
            "multiplier": opts.multiplier, "mod": mod, "flat": flat, "result": result.model_dump(mode="json"),
        }
    char.turn_state = turn


def retouch_pending_attack(char: Character, pending: dict, applied: dict, roll: dict) -> WeaponAttackResult:
    """Il tiro per colpire è cambiato dopo un'opzione. Il danno già tirato resta, salvo che cambino critico o 1 naturale."""
    # shortcut: l'evento homebrew `attack_rolled` resta sul primo d20 (Qualità & Usura usura su un 1 poi trasformato);
    # da rivedere se una regola homebrew deve reagire all'esito finale, rinviando il dispatch al danno o al «Mancato».
    result = WeaponAttackResult(**pending["result"])
    block = roll["option_result"]
    option_dice = pending.get("option_dice", [])
    if (result.is_critical, result.is_fumble) != (roll["is_critical"], roll["is_fumble"]):
        before = AppliedOptions(**applied)
        extra_rolls, extra_total = [], 0
        if roll["is_fumble"]:
            result.damage_rolls, result.damage_bonus, result.damage_total = [0], 0, 0
            option_dice = []
        else:
            item = next((i for i in char.items if i.id == pending["item_id"]), None)
            ability_mod = (weapon_attack_profile(char, item, pending["attack_mode"], pending["ability"]) if item
                           else unarmed_attack_profile(char, pending["attack_mode"] == "ranged"))[0]
            if pending.get("offhand"):
                ability_mod = min(ability_mod, 0)
            rerolled: list[list[int]] = []
            result.damage_rolls, result.damage_bonus = _base_damage(
                char, item, result.damage_dice, pending["ability"], ability_mod, result.magic_bonus, roll["is_critical"],
                pending["attack_mode"], pending["grip"], bool(pending.get("offhand")), rerolled)
            result.rerolled = rerolled or None
            record_dice(char, _damage_records(result.damage_dice, result.damage_rolls))
            extra_rolls, extra_total, result.damage_total = _option_damage(
                char, before, roll["is_critical"], max(0, sum(result.damage_rolls) + result.damage_bonus))
            option_dice = pairs(before.rolled_dice)
        if block and before.keys:  # i dadi delle opzioni prima del tiro sono stati ritirati col danno
            block = block.model_copy(update={"extra_rolls": extra_rolls, "extra_total": extra_total,
                                             "separate_rolls": before.separate_rolls,
                                             "separate_total": before.separate_total})
    result.to_hit_die, result.dice, result.mode, result.mode_applied = (
        roll["die"], roll["dice"], roll["mode"], roll["mode"])
    result.to_hit_bonus, result.to_hit_total = roll["total"] - roll["die"], roll["total"]
    result.is_critical, result.is_fumble = roll["is_critical"], roll["is_fumble"]
    result.forced_hit = roll["forced_hit"] or None
    result.notes = roll["notes"]
    result.option_result = block
    _set_pending_attack(char, {**pending, "options": block.keys if block else [], "option_dice": option_dice,
                               "result": result.model_dump(mode="json")})
    return result


def close_grazed_attack(char: Character, attack: WeaponAttackResult, damage: int) -> WeaponAttackResult:
    """L'attacco è mancato ma un'opzione infligge comunque danno: niente dadi, niente più da chiedere."""
    _set_pending_attack(char, None)
    return attack.model_copy(update={"attack_id": None, "grazed": True, "damage_rolls": [], "damage_bonus": damage,
                                     "damage_total": damage})


def _second_attack(char: Character, opts: AppliedOptions, pending: dict, item: Item | None, bonus: int) -> dict:
    """Il secondo tiro per colpire di un'opzione: un 1 naturale manca, un critico raddoppia i dadi a parte."""
    applied = modifiers_for(char, "attack", ability=pending["ability"], item=item, attack_mode=pending["attack_mode"])
    outcome = resolve_applied("normal", None, None, applied)
    record_dice(char, d20_records(outcome))
    if outcome.kept == 1:
        opts.separate_dice = []
    elif outcome.kept >= applied.crit_min:
        opts.separate_dice = [[doubled_dice(expr), False] for expr, _ in opts.separate_dice]
    return {"second_die": outcome.kept, "second_total": outcome.kept + bonus}


def _base_damage(
    char: Character, item: Item | None, damage_dice_str: str, ability: str, ability_mod: int, magic_bonus: int,
    is_critical: bool, attack_mode: str | None = None, grip: str = "one", offhand: bool = False,
    rerolled: list[list[int]] | None = None,
) -> tuple[list[int], int]:
    """Dadi e bonus del danno dell'arma o del colpo senz'armi. Il danno piatto '1' non ha dadi da raddoppiare.

    ``attack_mode``, ``grip``, ``offhand``: i privilegi che valgono solo in certe condizioni (Ira e Critico Brutale in
    mischia, Duellare con una mano, Combattere con Due Armi con l'altra) li leggono dal contesto. ``rerolled`` riceve
    ``[vecchio, nuovo]`` per ogni dado che un privilegio ha fatto ritirare (Combattere con Armi Possenti)."""
    dice_bonus = 0
    applied = modifiers_for(char, "damage", ability=ability, item=item, attack_mode=attack_mode, grip=grip, offhand=offhand)
    if damage_dice_str == "1":
        damage_rolls = [1]
    else:
        damage_rolls, dice_bonus = _roll_dice(damage_dice_str)
        if is_critical:
            damage_rolls = damage_rolls + _roll_dice(damage_dice_str)[0]
            # Dadi dell'arma in più al critico (Critico Brutale): dello stesso tipo, uno per ogni dado indicato.
            if applied.crit_dice and (die := _DICE_RE.match(damage_dice_str.strip())):
                damage_rolls += [random.randint(1, int(die.group(2))) for _ in range(applied.crit_dice)]
        if applied.damage_reroll and (die := _DICE_RE.match(damage_dice_str.strip())):
            for i, value in enumerate(damage_rolls):  # una volta sola: il nuovo risultato vale anche se è ancora basso
                if value <= applied.damage_reroll:
                    damage_rolls[i] = random.randint(1, int(die.group(2)))
                    if rerolled is not None:
                        rerolled.append([value, damage_rolls[i]])
        if applied.damage_min_die:  # «conta come 3»: il dado mostrato è già quello che vale
            for i, value in enumerate(damage_rolls):
                if value < applied.damage_min_die:
                    damage_rolls[i] = applied.damage_min_die
                    if rerolled is not None:
                        rerolled.append([value, damage_rolls[i]])
    return damage_rolls, (ability_mod + magic_bonus + attack_bonus_total(char.items, item, "damage") + dice_bonus
                          + applied.flat)


def _option_damage(char: Character, opts: AppliedOptions, is_critical: bool, damage: int) -> tuple[list[int], int, int]:
    """Dadi delle opzioni al danno: (valori, loro totale, danno finale)."""
    rolls, total = roll_option_dice(char, opts, is_critical)
    opts.damage_unscaled = damage + total
    return rolls, total, scale_damage(damage + total, opts.multiplier)


@router.post("/{char_id}/attack/{attack_id}/damage", response_model=WeaponAttackResult)
async def deferred_attack_damage(
    char_id: int,
    attack_id: str,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    body: Annotated[RollOptionsBody | None, Body()] = None,
) -> WeaponAttackResult:
    """Secondo tempo dell'attacco: opzioni ``after_hit`` confermate sul danno già tirato."""
    char = await _get_owned_full(char_id, user_id, session)
    pending = get_turn(char).get("pending_attack")
    if not pending or pending["attack_id"] != attack_id:
        raise HTTPException(status_code=404, detail={"code": "attack_not_found"})
    item = next((i for i in char.items if i.id == pending["item_id"]), None)
    if pending["item_id"] is not None and item is None:
        raise HTTPException(status_code=404, detail={"code": "attack_not_found"})
    if pending["result"]["is_fumble"]:
        raise HTTPException(status_code=409, detail={"code": "attack_missed"})
    opts = use_options(session, char, "attack", body, phase="after_hit", ability=pending["ability"], item=item,
                       attack_mode=pending["attack_mode"], grip=pending["grip"], offhand=pending.get("offhand", False))
    result = WeaponAttackResult(**pending["result"])
    result.homebrew_notifications = None  # già consegnate col tiro per colpire
    result.attack_id = None  # il danno è definitivo: da qui si può ritirare un dado
    second = _second_attack(char, opts, pending, item, result.to_hit_bonus) if opts.second_attack else {}
    rolls, extra, result.damage_total = _option_damage(char, opts, result.is_critical, result.damage_total + opts.bonus)
    result.damage_bonus += opts.bonus
    result.option_result = option_result(opts, rolls, extra, previous=result.option_result, **second)
    result.notes = [*result.notes, *(n for n in opts.notes if n not in result.notes)]
    _set_pending_attack(char, None)
    remember_weapon_damage(char, result, opts, [*pending.get("option_dice", []), *opts.rolled_dice], opts.bonus)
    turn = get_turn(char)
    if turn.get("last_roll"):  # il danno dice che il colpo è andato a segno: niente più da rimborsare
        char.turn_state = {**turn, "last_roll": {**turn["last_roll"], "refundable": {}}}
    if opts.keys:
        _add_history(session, char.id, "attack_roll",
                     f"Danno {result.weapon_name} con {', '.join(opts.keys)}: {result.damage_total}")
    return result


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
    refuse_if_incapacitated(char)

    meta = json.loads(item.item_metadata) if item.item_metadata else {}
    damage_dice_str: str = meta.get("damage_dice", "1d4")
    properties: list[str] = meta.get("properties", [])
    magic_bonus = int(meta.get("magic_bonus") or 0)

    has_prop = lambda name: any(name in p.lower() for p in properties)  # noqa: E731
    grip = body.grip if body else "one"
    attack_mode = body.attack_mode if body else "melee"
    offhand = attack_mode == "offhand"

    # Validate the choices before consuming inspiration.
    if offhand:
        if not has_property(item, "light"):
            raise HTTPException(status_code=422, detail="offhand_not_light")
        if not any(i.id != item.id and i.item_type == "weapon" and i.is_equipped and has_property(i, "light")
                   for i in char.items):
            raise HTTPException(status_code=422, detail="offhand_needs_second_light_weapon")
    else:
        _check_attack_limit(char, body, item)
    if grip == "two" and has_prop("versatile") and meta.get("versatile_dice"):
        if any(
            i.is_equipped and i.equipment_slot == EquipmentSlot.OFF_HAND and i.id != item.id
            for i in char.items
        ):
            raise HTTPException(status_code=422, detail="off_hand_occupied")
        damage_dice_str = meta["versatile_dice"]
    if attack_mode == "thrown" and not has_prop("thrown"):
        raise HTTPException(status_code=422, detail="weapon_not_thrown")

    if body and body.with_inspiration:
        spend_inspiration_reroll(char)

    # Determine ability modifier (effective: equipped-item bonuses included)
    ability_mod, ability, resolved_mode = weapon_attack_profile(char, item, attack_mode, body.ability if body else None)
    if martial := martial_arts_level(char, item):
        damage_dice_str = best_damage_dice(damage_dice_str, martial_arts_die(martial, character_edition(char)))
    # L'attacco extra non somma la caratteristica al danno, salvo che sia negativa.
    damage_mod = min(ability_mod, 0) if offhand else ability_mod

    # Bonus di competenza solo con un'arma in cui si è competenti (core.rules.proficiencies).
    proficient = is_weapon_proficient(char, item)
    pb = char.proficiency_bonus if proficient else 0

    # To-hit roll
    applied = modifiers_for(char, "attack", ability=ability, item=item, attack_mode=resolved_mode)
    opts = use_options(session, char, "attack", body, ability=ability, item=item, attack_mode=resolved_mode, grip=grip,
                       offhand=offhand)
    merge_options(applied, opts)
    outcome = resolve_body(body, applied)
    to_hit_die = outcome.kept
    to_hit_bonus = (ability_mod + pb + magic_bonus + attack_bonus_total(char.items, item, "attack") + applied.flat
                    + opts.bonus)
    to_hit_total = to_hit_die + to_hit_bonus
    is_fumble = to_hit_die == 1
    is_critical = to_hit_die >= applied.crit_min or (opts.force_crit and not is_fumble)

    # Damage roll
    option_rolls: list[int] = []
    option_total = 0
    rerolled: list[list[int]] = []
    if is_fumble:
        damage_rolls = [0]
        damage_bonus = 0
        damage_total = 0
    else:
        damage_rolls, damage_bonus = _base_damage(
            char, item, damage_dice_str, ability, damage_mod, magic_bonus, is_critical, resolved_mode, grip, offhand,
            rerolled)
        option_rolls, option_total, damage_total = _option_damage(
            char, opts, is_critical, max(0, sum(damage_rolls) + damage_bonus))

    result_str = (
        f"Attacco {item.name}: colpire {d20_history_label(outcome)}+{to_hit_bonus}={to_hit_total}"
        + (" (CRITICO!)" if is_critical else " (FUMBLE!)" if is_fumble else "")
        + f" | Danno: {'+'.join(str(r) for r in damage_rolls)}+{damage_bonus}={damage_total}"
    )
    if body and body.with_inspiration:
        result_str = f"Reroll ispirazione (to-hit): {result_str}"
    _add_history(session, char.id, "attack_roll", result_str)
    end_hide(session, char)
    end_on_action(char, "attack")
    _record_attack_dice(char, outcome, damage_dice_str, damage_rolls, is_fumble)
    if not (body and body.with_inspiration):  # il rilancio con ispirazione è lo stesso attacco
        if not offhand:
            spend(char, "attack", own_slot=_own_slot_attack(char, body))
            _note_martial_attack(char, item, body)
        elif NICK_OPTION not in opts.keys:
            spend(char, "bonus")

    # Ammunition: scale one piece per attack (also on miss/fumble), never on a reroll.
    ammo_state: AmmoState | None = None
    ammo_missing = False
    if any("ammunition" in p.lower() for p in properties):
        source = next(
            (i for i in char.items if i.equipment_slot == EquipmentSlot.AMMUNITION), None
        )
        if source is None:
            ammo = [i for i in char.items if i.item_type == "ammunition"]
            quick_ids = {
                c.id for c in char.items if (m := container_meta(c)) and m.get("quick_access")
            }
            # Quick-access quiver first, then loose stacks; other containers don't count.
            for pool in (
                [i for i in ammo if i.container_id in quick_ids],
                [i for i in ammo if i.container_id is None],
            ):
                # One stack, or several stacks of the same ammo: use the first (lowest id).
                live = sorted((i for i in pool if i.quantity > 0), key=lambda i: i.id)
                if len(pool) == 1:
                    source = pool[0]
                    break
                if live and len({i.name.lower() for i in live}) == 1:
                    source = live[0]
                    break
        if source is None or source.quantity <= 0:
            ammo_missing = True
        elif not (body and body.with_inspiration):
            source.quantity -= 1
        if source is not None:
            ammo_state = (
                AmmoState(item_id=source.id, name=source.name, remaining=max(0, source.quantity))
                if not ammo_missing else None
            )

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

    return _settle_attack(char, body, WeaponAttackResult(
        ammo=ammo_state,
        ammo_missing=ammo_missing,
        magic_bonus=magic_bonus,
        proficiency_warning=not proficient,
        weapon_name=item.name,
        to_hit_die=to_hit_die,
        dice=outcome.dice,
        mode=outcome.mode,
        mode_applied=outcome.mode,
        notes=applied.notes,
        to_hit_bonus=to_hit_bonus,
        to_hit_total=to_hit_total,
        is_critical=is_critical,
        is_fumble=is_fumble,
        damage_dice=damage_dice_str,
        damage_rolls=damage_rolls,
        damage_bonus=damage_bonus if not is_fumble else 0,
        damage_total=damage_total,
        rerolled=rerolled or None,
        is_magic=True if applied.magic_weapon else None,
        homebrew_notifications=notifications if notifications else None,
        option_result=option_result(opts, option_rolls, option_total),
    ), item, ability, resolved_mode, grip, opts, offhand)


# ---------------------------------------------------------------------------
# Unarmed strike
# ---------------------------------------------------------------------------

def _unarmed_effect(session: AsyncSession, char: Character, effect: str, dc: int) -> WeaponAttackResult:
    """Afferrare o Spingere 2024: niente tiro per colpire, il bersaglio fa un TS su Forza o Destrezza contro ``dc``."""
    if character_edition(char) != "2024":
        raise HTTPException(status_code=422, detail="unarmed_effect_2024_only")
    use_options(session, char, "attack", None)  # è un tiro nuovo: il precedente non si ritocca più
    _set_pending_attack(char, None)
    spend(char, "attack")
    _add_history(session, char.id, "attack_roll", f"Colpo senz'armi ({effect}): CD {dc}")
    return WeaponAttackResult(
        weapon_name="Attacco a mano libera", to_hit_die=0, to_hit_bonus=0, to_hit_total=0, is_critical=False,
        is_fumble=False, damage_dice="", damage_rolls=[], damage_bonus=0, damage_total=0, effect=effect, save_dc=dc,
    )


@router.post("/{char_id}/attack/unarmed", response_model=WeaponAttackResult)
async def attack_unarmed(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    body: Annotated[AttackSubmission | None, Body()] = None,
) -> WeaponAttackResult:
    """Unarmed strike: 1+STR bludgeoning; Monk uses best of STR/DEX + Martial Arts die."""
    char = await _get_owned_full(char_id, user_id, session)
    refuse_if_incapacitated(char)
    _check_attack_limit(char, body)

    throw = bool(body and throws_unarmed(char, body.options or []))  # il proiettile afferrato: a distanza, con Destrezza
    mode = "ranged" if throw else "melee"
    ability_mod, damage_dice_str, ability = unarmed_attack_profile(char, throw)
    damage_mod, damage_ability = ability_mod, ability  # il danno resta con la caratteristica di prima
    if not throw and unarmored_unshielded(char) and any(spec.dex_unarmed for spec, _row in active_features(char)):
        dex_mod = roll_ability_mod(char, "dexterity")  # Passo Abbagliante: per colpire la Destrezza, se è migliore
        if dex_mod > ability_mod:
            ability_mod, ability = dex_mod, "dexterity"
    pb = char.proficiency_bonus
    if body and body.effect != "damage":
        return _unarmed_effect(session, char, body.effect, 8 + damage_mod + pb)  # la CD resta con la caratteristica di prima (Danza: non DES)

    if body and body.with_inspiration:
        spend_inspiration_reroll(char)

    applied = modifiers_for(char, "attack", ability=ability, attack_mode=mode)
    opts = use_options(session, char, "attack", body, ability=ability, attack_mode=mode, grip="one")
    merge_options(applied, opts)
    if opts.finesse_unarmed:  # Lama Psichica: Accurata, la migliore fra Forza e Destrezza anche per il danno
        str_mod, dex_mod = roll_ability_mod(char, "strength"), roll_ability_mod(char, "dexterity")
        ability_mod, ability = (dex_mod, "dexterity") if dex_mod >= str_mod else (str_mod, "strength")
        damage_mod, damage_ability = ability_mod, ability
    outcome = resolve_body(body, applied)
    to_hit_die = outcome.kept
    to_hit_bonus = ability_mod + pb + attack_bonus_total(char.items, None, "attack") + applied.flat + opts.bonus
    to_hit_total = to_hit_die + to_hit_bonus
    is_fumble = to_hit_die == 1
    is_critical = to_hit_die >= applied.crit_min or (opts.force_crit and not is_fumble)

    option_rolls: list[int] = []
    option_total = 0
    if is_fumble:
        damage_rolls = [0]
        damage_bonus = 0
        damage_total = 0
    else:
        if opts.unarmed_dice:  # Danno Bardico: il dado di Ispirazione più Destrezza, al posto del danno normale
            damage_dice_str = opts.unarmed_dice
            if not opts.finesse_unarmed:
                damage_mod, damage_ability = roll_ability_mod(char, "dexterity"), "dexterity"
        damage_rolls, damage_bonus = _base_damage(char, None, damage_dice_str, damage_ability, damage_mod, 0, is_critical, mode)
        option_rolls, option_total, damage_total = _option_damage(
            char, opts, is_critical, max(0, sum(damage_rolls) + damage_bonus))

    weapon_name = "Attacco a mano libera"
    result_str = (
        f"Attacco {weapon_name}: colpire {d20_history_label(outcome)}+{to_hit_bonus}={to_hit_total}"
        + (" (CRITICO!)" if is_critical else " (FUMBLE!)" if is_fumble else "")
        + f" | Danno: {'+'.join(str(r) for r in damage_rolls)}+{damage_bonus}={damage_total}"
    )
    if body and body.with_inspiration:
        result_str = f"Reroll ispirazione (to-hit): {result_str}"
    _add_history(session, char.id, "attack_roll", result_str)
    end_hide(session, char)  # il tiro per colpire rompe il nascondiglio, dopo aver contato il vantaggio
    end_on_action(char, "attack")
    _record_attack_dice(char, outcome, damage_dice_str, damage_rolls, is_fumble)
    if not (body and body.with_inspiration):
        spend(char, "attack", own_slot=_own_slot_attack(char, body))  # il rilancio con ispirazione è lo stesso attacco
        _note_martial_attack(char, None, body)

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

    return _settle_attack(char, body, WeaponAttackResult(
        weapon_name=weapon_name,
        to_hit_die=to_hit_die,
        dice=outcome.dice,
        mode=outcome.mode,
        mode_applied=outcome.mode,
        notes=applied.notes,
        to_hit_bonus=to_hit_bonus,
        to_hit_total=to_hit_total,
        is_critical=is_critical,
        is_fumble=is_fumble,
        damage_dice=damage_dice_str,
        damage_rolls=damage_rolls,
        damage_bonus=damage_bonus if not is_fumble else 0,
        damage_total=damage_total,
        # il proiettile afferrato non è un colpo senz'armi: né il tipo di danno (che il manuale non fissa) né «magico»
        damage_type=None if throw else opts.unarmed_damage_type or next(
            (s["data"]["unarmed_damage_type"] for s in char.active_states or [] if (s.get("data") or {}).get("unarmed_damage_type")),
            "bludgeoning"),
        is_magic=True if not throw and any(spec.magic_unarmed for spec, _row in active_features(char)) else None,
        homebrew_notifications=notifications if notifications else None,
        option_result=option_result(opts, option_rolls, option_total),
    ), None, ability, mode, "one", opts)


# ---------------------------------------------------------------------------
# Charges and spells cast from items
# ---------------------------------------------------------------------------

class ChargesDelta(BaseModel):
    delta: int = Field(ge=-100, le=100)


class ItemCast(BaseModel):
    spell_index: int = Field(ge=0)


async def _get_item(session: AsyncSession, char_id: int, item_id: int) -> Item:
    item = (await session.execute(
        select(Item).where(Item.id == item_id, Item.character_id == char_id)
    )).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.post("/{char_id}/items/{item_id}/charges", response_model=CharacterFull)
async def adjust_item_charges(
    char_id: int,
    item_id: int,
    body: ChargesDelta,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)
    item = await _get_item(session, char_id, item_id)
    ch = item_meta(item).get("charges")
    if not isinstance(ch, dict):
        raise HTTPException(status_code=409, detail="no_charges")
    old = int(ch.get("current") or 0)
    delta = body.delta + (1 if body.delta < 0 and not charges_spent(char) else 0)  # Usare Dispositivi Magici: con 6 su 1d6 resta
    new = max(0, min(int(ch.get("max") or 0), old + delta))
    set_item_charges(item, new)
    _add_history(session, char.id, "item_charges", f"Cariche {item.name}: {old} → {new}")
    await session.flush()
    await session.refresh(char, attribute_names=["items"])
    return await build_character_response(session, char)


@router.post("/{char_id}/items/{item_id}/cast", response_model=CharacterFull)
async def cast_from_item(
    char_id: int,
    item_id: int,
    body: ItemCast,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)
    item = await _get_item(session, char_id, item_id)
    meta = item_meta(item)
    granted = meta.get("granted_spells") or []
    if body.spell_index >= len(granted):
        raise HTTPException(status_code=422, detail="spell_index out of range")
    spell = granted[body.spell_index]
    if meta.get("requires_attunement") and not meta.get("attuned"):
        raise HTTPException(status_code=409, detail="attunement_required")
    cost = int(spell.get("charges_cost") or 0)
    ch = meta.get("charges") if isinstance(meta.get("charges"), dict) else None
    current = int(ch.get("current") or 0) if ch else 0
    if cost > current:
        raise HTTPException(status_code=409, detail="not_enough_charges")
    if cost and charges_spent(char):
        set_item_charges(item, current - cost)
    end_on_action(char, "cast")  # come ogni lancio: il Manto di Ombre finisce

    if spell.get("is_concentration"):
        # Match by srd_index (when both set), then by case-insensitive name.
        name = spell["name"].lower()
        idx = spell.get("srd_index")
        match = (
            next((s for s in char.spells if idx and s.srd_index == idx), None)
            or next((s for s in char.spells if s.name.lower() == name), None)
        )
        rounds = parse_duration_rounds(spell.get("duration"))
        if match:
            start_concentration(char, match.id, rounds)
        else:
            start_concentration(char, None, rounds, {"item_id": item.id, "name": spell["name"]})
        await release_concentration_effects(session, char)

    _add_history(session, char.id, "spell_cast",
                 f"Lanciato {spell['name']} da {item.name} ({cost} cariche)",
                 meta={"item_id": item.id})
    await session.flush()
    await session.refresh(char, attribute_names=["items"])
    return await build_character_response(session, char)


# ---------------------------------------------------------------------------
# Arma Vincolata (Cavaliere Mistico 2014)
# ---------------------------------------------------------------------------

class BondRequest(BaseModel):
    replace_item_id: int | None = None  # con due armi già vincolate, quella da spezzare per la nuova


async def _bond_response(session: AsyncSession, char: Character) -> CharacterFull:
    await session.flush()
    await session.refresh(char, attribute_names=["items"])
    return await build_character_response(session, char)


@router.post("/{char_id}/items/{item_id}/bond", response_model=CharacterFull)
async def bond_weapon(
    char_id: int, item_id: int, user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)], body: Annotated[BondRequest | None, Body()] = None,
) -> CharacterFull:
    """Il rituale di un'ora è concluso (l'app non lo cronometra): l'arma è vincolata. Al massimo due."""
    char = await _get_owned_full(char_id, user_id, session)
    item = await _get_item(session, char_id, item_id)
    weapon_bond.bond(char, item, body.replace_item_id if body else None)
    _add_history(session, char.id, "item_bond", f"Arma vincolata: {item.name}", meta={"item_id": item.id})
    return await _bond_response(session, char)


@router.delete("/{char_id}/items/{item_id}/bond", response_model=CharacterFull)
async def break_weapon_bond(
    char_id: int, item_id: int, user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)
    item = await _get_item(session, char_id, item_id)
    weapon_bond.break_bond(item)
    _add_history(session, char.id, "item_bond", f"Vincolo spezzato: {item.name}", meta={"item_id": item.id})
    return await _bond_response(session, char)


@router.post("/{char_id}/items/{item_id}/summon", response_model=CharacterFull)
async def summon_bonded_weapon(
    char_id: int, item_id: int, user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    """Evoca l'arma vincolata nella mano libera come azione bonus (stesso piano di esistenza: lo dichiara il giocatore)."""
    char = await _get_owned_full(char_id, user_id, session)
    refuse_if_incapacitated(char)
    item = await _get_item(session, char_id, item_id)
    slot = weapon_bond.summon(char, item)
    _add_history(session, char.id, "item_bond", f"Arma evocata: {item.name} ({slot})", meta={"item_id": item.id})
    return await _bond_response(session, char)
