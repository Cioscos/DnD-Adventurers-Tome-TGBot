"""Unit test del sync delle feature di classe in Ability."""
from __future__ import annotations

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.db.models import Base, Character, CharacterClass, AbilityScore
from api.services.class_features import sync_class_feature_abilities


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def _make_monk(session: AsyncSession, level: int) -> tuple[Character, CharacterClass]:
    # Imposta TUTTE le relazioni prima del primo flush così restano in memoria
    # (caricate) e non scatenano un lazy-load in contesto async — stesso pattern
    # di api/routers/characters.create_character.
    char = Character(user_id=1, name="Mo")
    char.ability_scores = [AbilityScore(name="charisma", value=10)]
    char.abilities = []
    cls = CharacterClass(class_name="Monaco", level=level)
    char.classes = [cls]
    session.add(char)
    await session.flush()  # assegna char.id/cls.id, cascata ability_scores
    return char, cls


async def test_creates_ki_ability_at_level_2(session):
    char, cls = await _make_monk(session, 2)
    await sync_class_feature_abilities(session, char, cls, lang="it")
    await session.flush()
    ki = next(a for a in char.abilities if a.feature_key == "monk.ki")
    assert ki.is_class_feature is True
    assert ki.source_class_id == cls.id
    assert ki.max_uses == 2 and ki.uses == 2
    assert ki.is_active is True and ki.is_passive is False
    assert ki.description and "monaco" in ki.description.lower()


async def test_levelup_grows_max_and_keeps_spent(session):
    char, cls = await _make_monk(session, 2)
    await sync_class_feature_abilities(session, char, cls, lang="it")
    await session.flush()
    ki = next(a for a in char.abilities if a.feature_key == "monk.ki")
    ki.uses = 0  # tutto speso
    cls.level = 5
    await sync_class_feature_abilities(session, char, cls, lang="it")
    assert ki.max_uses == 5
    assert ki.uses == 3  # +3 guadagnati immediatamente disponibili


async def test_levelup_does_not_touch_description(session):
    char, cls = await _make_monk(session, 2)
    await sync_class_feature_abilities(session, char, cls, lang="it")
    await session.flush()
    ki = next(a for a in char.abilities if a.feature_key == "monk.ki")
    ki.description = "Testo personalizzato dall'utente"
    cls.level = 5
    await sync_class_feature_abilities(session, char, cls, lang="it")
    assert ki.description == "Testo personalizzato dall'utente"


async def test_english_lang_picks_en_description(session):
    char, cls = await _make_monk(session, 2)
    await sync_class_feature_abilities(session, char, cls, lang="en")
    await session.flush()
    ki = next(a for a in char.abilities if a.feature_key == "monk.ki")
    assert ki.description and "energy" in ki.description.lower()
