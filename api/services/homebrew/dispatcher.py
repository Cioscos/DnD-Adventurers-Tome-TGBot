"""Dispatch — entry point called by routers when an event fires."""
from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.homebrew.dsl import RuleDSL
from api.services.homebrew.engine import RuleEngine
from api.services.homebrew.exceptions import DSLValidationError
from api.services.homebrew.types import ExecutionContext, RuleFiringResult
from core.db.models import (
    Character, CharacterHistory, HomebrewRule, Item,
)

logger = logging.getLogger(__name__)

MAX_DEPTH = 8


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _char_to_ctx_dict(char: Character) -> dict:
    return {
        "id": char.id,
        "name": char.name,
        "current_hit_points": char.current_hit_points,
        "hit_points": char.hit_points,
        "temp_hp": char.temp_hp,
        "speed": char.speed,
        "total_level": char.total_level,
        # Conditions dict (JSON column) — keys queryable via $character.conditions
        # with `has_property` filter (e.g. custom homebrew conditions like "custom:bleeding").
        "conditions": dict(char.conditions or {}),
    }


def _item_to_ctx_dict(item: Item) -> dict:
    md = {}
    if item.item_metadata:
        try:
            md = json.loads(item.item_metadata)
        except Exception:
            pass
    return {
        "_kind": "item",
        "_id": item.id,
        "id": item.id,
        "name": item.name,
        "item_type": item.item_type,
        "is_equipped": item.is_equipped,
        "equipment_slot": item.equipment_slot,
        "metadata": md,
    }


async def _matching_items(
    session: AsyncSession, char: Character, filter_def: dict | None,
) -> list[Item]:
    stmt = select(Item).where(Item.character_id == char.id)
    if filter_def and filter_def.get("item_types"):
        stmt = stmt.where(Item.item_type.in_(filter_def["item_types"]))
    res = await session.execute(stmt)
    return list(res.scalars())


def _passes_subject_filter(item: Item, filter_def: dict | None) -> bool:
    """Check if a single item matches the rule's subject filter (item_types only in MVP)."""
    if not filter_def:
        return True
    item_types = filter_def.get("item_types")
    if item_types and item.item_type not in item_types:
        return False
    return True


async def dispatch(
    session: AsyncSession,
    char: Character,
    event_type: str,
    payload: dict,
    *,
    depth: int = 0,
    triggered_rule_stack: tuple[int, ...] = (),
) -> list[RuleFiringResult]:
    """Fire all enabled homebrew rules matching the event for this character.

    Flushes mutations to the session before returning, but does NOT commit.
    The caller (router) is responsible for `await session.commit()` after
    `dispatch` returns successfully. On exception, the caller should roll back.
    """
    if depth > MAX_DEPTH:
        session.add(CharacterHistory(
            character_id=char.id, timestamp=_now(),
            event_type="homebrew",
            description=f"⚠️ Recursion depth {depth} exceeded for event {event_type}",
        ))
        logger.warning("Depth %d exceeded on event %s", depth, event_type)
        await session.flush()
        return []

    # Preload classes so $character.total_level is accurate.
    if "classes" in inspect(char).unloaded:
        await session.refresh(char, attribute_names=["classes"])

    rules_res = await session.execute(
        select(HomebrewRule).where(
            HomebrewRule.character_id == char.id,
            HomebrewRule.enabled == True,  # noqa: E712
        ).order_by(HomebrewRule.id.asc())
    )
    rules = list(rules_res.scalars())

    engine = RuleEngine()
    all_results: list[RuleFiringResult] = []

    for rule in rules:
        if rule.id in triggered_rule_stack:
            logger.debug("Cycle detected, skipping rule %d", rule.id)
            continue

        # Validate DSL up-front so invalid rules get disabled even when no subject
        # matches (otherwise the engine would never run and we'd silently keep a
        # broken rule enabled).
        try:
            RuleDSL.model_validate(rule.dsl)
        except Exception as e:
            session.add(CharacterHistory(
                character_id=char.id, timestamp=_now(),
                event_type="homebrew",
                description=f"⚠️ Regola '{rule.name}' disattivata: DSL non valido ({e})",
            ))
            rule.enabled = False
            await session.flush()
            continue

        triggers = rule.dsl.get("triggers", [])
        subject_def = rule.dsl.get("subject", {})
        new_stack = triggered_rule_stack + (rule.id,)

        # Determine target subjects for THIS rule.
        if subject_def.get("type") == "item":
            item_id = payload.get("item_id")
            if item_id is not None:
                # Scope to this character — never let another character's item leak in.
                res = await session.execute(
                    select(Item).where(Item.id == item_id, Item.character_id == char.id)
                )
                obj = res.scalar_one_or_none()
                if obj is None or not _passes_subject_filter(obj, subject_def.get("filter")):
                    continue
                items: list[Item] = [obj]
            else:
                items = await _matching_items(session, char, subject_def.get("filter"))
            subjects = [_item_to_ctx_dict(i) for i in items]
        else:
            subjects = [{"_kind": subject_def.get("type", "character"), "_id": char.id}]

        for subject in subjects:
            for trigger in triggers:
                if trigger.get("event") != event_type:
                    continue
                ctx = ExecutionContext.new(
                    event_type=event_type,
                    event_payload=payload,
                    subject=subject,
                    character=_char_to_ctx_dict(char),
                )
                try:
                    rfr = await engine.execute_trigger(
                        rule, trigger, ctx, session, char,
                        depth=depth, stack=new_stack,
                    )
                except DSLValidationError as e:
                    session.add(CharacterHistory(
                        character_id=char.id, timestamp=_now(),
                        event_type="homebrew",
                        description=f"⚠️ Regola '{rule.name}' disattivata: DSL non valido ({e})",
                    ))
                    rule.enabled = False
                    await session.flush()
                    continue
                if rfr is not None:
                    all_results.append(rfr)
                    for h in rfr.history_entries:
                        session.add(CharacterHistory(
                            character_id=char.id, timestamp=_now(),
                            event_type="homebrew",
                            description=h.description, meta=h.meta,
                        ))
    await session.flush()
    return all_results
