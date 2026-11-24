"""Passive modifier computation for derived stats."""
from __future__ import annotations

import json
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.homebrew.dsl import Filter
from api.services.homebrew.filters import evaluate_filter
from api.services.homebrew.path_resolver import PathResolutionError
from core.db.models import Character, CharacterClass, HomebrewRule, Item

logger = logging.getLogger(__name__)


async def load_snapshot(session: AsyncSession, char: Character, items=None) -> tuple[list[HomebrewRule], list[Item]]:
    """Regole attive e oggetti fuori dai contenitori, letti una volta: chi calcola molti bonus di fila li passa come ``snapshot``.
    ``items``: gli oggetti già caricati della scheda, per non rileggerli."""
    rules = list((await session.execute(select(HomebrewRule).where(
        HomebrewRule.character_id == char.id, HomebrewRule.enabled == True))).scalars())  # noqa: E712
    if items is None:
        items = (await session.execute(select(Item).where(Item.character_id == char.id))).scalars()
    return rules, [i for i in items if i.container_id is None]  # contained items give no bonus


async def passive_modifier(session: AsyncSession, char: Character, skill: str, snapshot=None) -> int:
    """Homebrew bonus to the passive score of `skill` (e.g. "perception")."""
    return await get_passive_modifiers(session, char, f"character.passive.{skill}", snapshot)


async def get_passive_modifiers(
    session: AsyncSession, char: Character, target_path: str, snapshot=None,
) -> int:
    """Sum all passive modifiers matching target_path across enabled rules.

    `character.hit_points_max` also includes `character.hit_points_max_per_level`
    times the total class level, so every max-HP consumer stays consistent.
    """
    if target_path == "character.hit_points_max":
        snapshot = snapshot or await load_snapshot(session, char)
        total = _sum_modifiers(snapshot, char, target_path)
        per_level = _sum_modifiers(snapshot, char, "character.hit_points_max_per_level")
        if per_level:  # il livello si legge solo se una regola lo usa
            lv = (await session.execute(
                select(func.coalesce(func.sum(CharacterClass.level), 0))
                .where(CharacterClass.character_id == char.id)
            )).scalar_one()
            total += int(lv) * per_level
        return total
    return _sum_modifiers(snapshot or await load_snapshot(session, char), char, target_path)


def _sum_modifiers(snapshot: tuple[list[HomebrewRule], list[Item]], char: Character, target_path: str) -> int:
    rules, all_items = snapshot

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
                try:
                    applies = evaluate_filter(Filter.model_validate(mod["when"]), ctx)
                except (PathResolutionError, KeyError, TypeError, ValueError) as exc:  # percorso inesistente o condizione illeggibile: la regola non si applica, la scheda resta leggibile
                    logger.warning("homebrew rule %s skipped: %s", rule.id, exc)
                    continue
                if applies:
                    val = mod.get("value")
                    if isinstance(val, int):
                        total += val
                    # dice notation in MVP is treated as static 0 (deferred)
    return total
