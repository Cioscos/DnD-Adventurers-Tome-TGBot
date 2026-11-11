"""Punto d'ingresso API del sync delle feature di classe: la logica è in core, usata anche dal seed."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.services.effects import cap_current_hp
from core.db.models import Character
from core.rules import feature_sync

__all__ = ["sync_cataloged_features", "sync_class_feature_abilities"]


async def sync_cataloged_features(session: AsyncSession, char: Character, *args, **kw) -> None:
    await feature_sync.sync_cataloged_features(session, char, *args, **kw)
    await cap_current_hp(session, char)  # il core non taglia i PF correnti: il tetto effettivo lo mette questo


async def sync_class_feature_abilities(session: AsyncSession, char: Character, *args, **kw) -> None:
    await feature_sync.sync_class_feature_abilities(session, char, *args, **kw)
    await cap_current_hp(session, char)
