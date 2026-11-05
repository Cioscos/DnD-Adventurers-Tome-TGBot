"""Passaggio al catalogo dei personaggi esistenti (R33).

Un personaggio salvato prima di un catalogo di classe ha ancora le righe del vecchio schema (``CLASS_RESOURCES``) fino al
primo sync, che arriva solo quando qualcosa lo provoca. All'avvio dell'API, se la versione dei cataloghi salvata in
``app_meta`` è diversa da ``CATALOG_VERSION``, ogni personaggio con una classe a catalogo passa una volta dal sync, con
``retrofit``: i bonus ai punteggi si segnano già applicati senza toccarli (R34). L'errore di un personaggio è registrato e
non ferma gli altri né l'avvio; la versione si segna solo se nessuno ha fallito, così il prossimo avvio riprova.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from core.db.models import AppMeta, BotUser, Character
from core.rules.catalog import CATALOG_VERSION, features_for
from core.rules.edition import character_edition, class_key
from core.rules.feature_sync import sync_cataloged_features
from api.services.spell_slots import recalc_spell_slots

logger = logging.getLogger(__name__)

META_KEY = "catalog_version"


def _has_catalog(char: Character) -> bool:
    edition = character_edition(char)
    return any(features_for(edition, class_key(cls)) for cls in char.classes)


async def _lang(session: AsyncSession, user_id: int) -> str:
    code = (await session.execute(select(BotUser.language_code).where(BotUser.user_id == user_id))).scalar_one_or_none()
    return "en" if (code or "").lower().startswith("en") else "it"


async def migrate_catalog(session_factory: async_sessionmaker) -> int:
    """Sincronizza i personaggi a catalogo se la versione è cambiata. Restituisce quanti ne ha sincronizzati."""
    async with session_factory() as session:
        meta = await session.get(AppMeta, META_KEY)
        if meta is not None and meta.value == str(CATALOG_VERSION):
            return 0
        ids = list((await session.execute(select(Character.id).order_by(Character.id))).scalars())

    synced, failed = 0, 0
    for char_id in ids:
        try:
            async with session_factory() as session:
                char = (await session.execute(
                    select(Character).options(
                        selectinload(Character.classes), selectinload(Character.ability_scores),
                        selectinload(Character.spells), selectinload(Character.spell_slots),
                        selectinload(Character.items), selectinload(Character.currency),
                        selectinload(Character.abilities),
                    ).where(Character.id == char_id))).scalar_one_or_none()
                if char is None or not _has_catalog(char):
                    continue
                await sync_cataloged_features(session, char, await _lang(session, char.user_id), retrofit=True)
                await recalc_spell_slots(session, char)
                await session.commit()
                synced += 1
        except Exception:  # un personaggio rotto non ferma gli altri né l'avvio
            failed += 1
            logger.exception("Passaggio al catalogo: personaggio %s non sincronizzato", char_id)

    if not failed:
        async with session_factory() as session:
            meta = await session.get(AppMeta, META_KEY)
            if meta is None:
                session.add(AppMeta(key=META_KEY, value=str(CATALOG_VERSION)))
            else:
                meta.value = str(CATALOG_VERSION)
            await session.commit()
    return synced
