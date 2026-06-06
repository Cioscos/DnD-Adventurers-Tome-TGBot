"""Idempotent data backfills run at API startup (after schema migrations).

Unlike the ALTER-TABLE migrations in engine.py, these rewrite row *data*
(JSON columns), so they need a real session rather than a sync DDL connection.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Item

logger = logging.getLogger(__name__)


async def backfill_consumable_types(session: AsyncSession) -> int:
    """Convert legacy `potion`/`scroll` items to `consumable` and stamp the
    matching `subtype` into item_metadata. Idempotent: once converted, no rows
    match `item_type IN ('potion','scroll')`, so reruns are no-ops.

    Returns the number of rows converted.
    """
    result = await session.execute(
        select(Item).where(Item.item_type.in_(["potion", "scroll"]))
    )
    rows = result.scalars().all()
    for item in rows:
        subtype = item.item_type  # 'potion' or 'scroll'
        meta: dict = {}
        if item.item_metadata:
            try:
                meta = json.loads(item.item_metadata)
            except (ValueError, TypeError):
                meta = {}
        meta.setdefault("subtype", subtype)
        item.item_type = "consumable"
        item.item_metadata = json.dumps(meta)
    if rows:
        await session.commit()
        logger.info("Backfilled %d legacy potion/scroll item(s) -> consumable", len(rows))
    return len(rows)
