"""Passive modifier computation for derived stats."""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.homebrew.dsl import Filter
from api.services.homebrew.filters import evaluate_filter
from core.db.models import Character, HomebrewRule, Item


async def get_passive_modifiers(
    session: AsyncSession, char: Character, target_path: str,
) -> int:
    """Sum all passive modifiers matching target_path across enabled rules."""
    rules_res = await session.execute(
        select(HomebrewRule).where(
            HomebrewRule.character_id == char.id,
            HomebrewRule.enabled == True,  # noqa: E712
        )
    )
    rules = list(rules_res.scalars())

    items_res = await session.execute(
        select(Item).where(Item.character_id == char.id)
    )
    all_items = list(items_res.scalars())

    total = 0
    for rule in rules:
        modifiers = rule.dsl.get("passive_modifiers", [])
        subject_def = rule.dsl.get("subject", {})
        for mod in modifiers:
            if mod.get("target") != target_path:
                continue
            # Determine subjects to evaluate against.
            if subject_def.get("type") == "item":
                filt = subject_def.get("filter") or {}
                allowed_types = filt.get("item_types")
                name_contains = filt.get("name_contains")
                candidates = [
                    i for i in all_items
                    if (not allowed_types or i.item_type in allowed_types)
                    and (not name_contains
                         or name_contains.lower() in (i.name or "").lower())
                ]
            else:
                candidates = [None]  # single subject = char itself
            for subj in candidates:
                if subj is not None:
                    md = json.loads(subj.item_metadata or "{}")
                    ctx_subject = {
                        "_kind": "item", "_id": subj.id, "name": subj.name,
                        "is_equipped": subj.is_equipped, "item_type": subj.item_type,
                        "metadata": md,
                    }
                else:
                    ctx_subject = {"_kind": "character", "_id": char.id}
                ctx = {
                    "event": {},
                    "subject": ctx_subject,
                    "character": {"id": char.id, "name": char.name},
                    "vars": {},
                }
                cond = Filter.model_validate(mod["when"])
                if evaluate_filter(cond, ctx):
                    val = mod["value"]
                    if isinstance(val, int):
                        total += val
                    # dice notation in MVP is treated as static 0 (deferred)
    return total
