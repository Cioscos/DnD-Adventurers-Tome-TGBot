"""get_passive_modifiers tests — derived stat bonuses from homebrew rules."""
import json
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from core.db.models import Base, Character, HomebrewRule, Item


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SM = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SM() as s:
        yield s


@pytest.mark.asyncio
async def test_passive_modifier_sums_ac_bonus(db_session):
    char = Character(user_id=1, name="T")
    db_session.add(char)
    await db_session.flush()
    item = Item(
        character_id=char.id, name="Shield", item_type="shield",
        is_equipped=True, item_metadata="{}",
    )
    db_session.add(item)
    await db_session.flush()
    rule = HomebrewRule(
        character_id=char.id, name="Shield+1", dsl={
            "version": 1,
            "subject": {"type": "item", "filter": {"item_types": ["shield"]}},
            "passive_modifiers": [
                {"when": {"path": "$subject.is_equipped", "op": "eq", "value": True},
                 "target": "character.ac", "value": 1,
                 "label_i18n": {"it": "Scudo+1", "en": "Shield+1"}},
            ],
            "triggers": [],
        }, created_at="x", updated_at="x",
    )
    db_session.add(rule)
    await db_session.flush()

    from api.services.homebrew.passive import get_passive_modifiers
    total = await get_passive_modifiers(db_session, char, "character.ac")
    assert total == 1


@pytest.mark.asyncio
async def test_passive_modifier_when_filter_false_excludes(db_session):
    char = Character(user_id=1, name="T")
    db_session.add(char)
    await db_session.flush()
    item = Item(
        character_id=char.id, name="Shield", item_type="shield",
        is_equipped=False, item_metadata="{}",
    )
    db_session.add(item)
    await db_session.flush()
    rule = HomebrewRule(
        character_id=char.id, name="Shield+1", dsl={
            "version": 1,
            "subject": {"type": "item", "filter": {"item_types": ["shield"]}},
            "passive_modifiers": [
                {"when": {"path": "$subject.is_equipped", "op": "eq", "value": True},
                 "target": "character.ac", "value": 1,
                 "label_i18n": {"it": "x", "en": "y"}},
            ],
            "triggers": [],
        }, created_at="x", updated_at="x",
    )
    db_session.add(rule)
    await db_session.flush()

    from api.services.homebrew.passive import get_passive_modifiers
    total = await get_passive_modifiers(db_session, char, "character.ac")
    assert total == 0


@pytest.mark.asyncio
async def test_passive_modifier_disabled_rule_excluded(db_session):
    char = Character(user_id=1, name="T")
    db_session.add(char)
    await db_session.flush()
    item = Item(
        character_id=char.id, name="Shield", item_type="shield",
        is_equipped=True, item_metadata="{}",
    )
    db_session.add(item)
    await db_session.flush()
    rule = HomebrewRule(
        character_id=char.id, name="Shield+1", enabled=False, dsl={
            "version": 1,
            "subject": {"type": "item", "filter": {"item_types": ["shield"]}},
            "passive_modifiers": [
                {"when": {"path": "$subject.is_equipped", "op": "eq", "value": True},
                 "target": "character.ac", "value": 1,
                 "label_i18n": {"it": "x", "en": "y"}},
            ],
            "triggers": [],
        }, created_at="x", updated_at="x",
    )
    db_session.add(rule)
    await db_session.flush()

    from api.services.homebrew.passive import get_passive_modifiers
    total = await get_passive_modifiers(db_session, char, "character.ac")
    assert total == 0


@pytest.mark.asyncio
async def test_passive_modifier_wrong_target_excluded(db_session):
    char = Character(user_id=1, name="T")
    db_session.add(char)
    await db_session.flush()
    item = Item(
        character_id=char.id, name="Shield", item_type="shield",
        is_equipped=True, item_metadata="{}",
    )
    db_session.add(item)
    await db_session.flush()
    rule = HomebrewRule(
        character_id=char.id, name="Shield+1", dsl={
            "version": 1,
            "subject": {"type": "item", "filter": {"item_types": ["shield"]}},
            "passive_modifiers": [
                {"when": {"path": "$subject.is_equipped", "op": "eq", "value": True},
                 "target": "character.hit_points_max", "value": 5,
                 "label_i18n": {"it": "x", "en": "y"}},
            ],
            "triggers": [],
        }, created_at="x", updated_at="x",
    )
    db_session.add(rule)
    await db_session.flush()

    from api.services.homebrew.passive import get_passive_modifiers
    total = await get_passive_modifiers(db_session, char, "character.ac")
    assert total == 0  # different target
    total_hp = await get_passive_modifiers(db_session, char, "character.hit_points_max")
    assert total_hp == 5


@pytest.mark.asyncio
async def test_passive_modifier_sums_multiple_subjects(db_session):
    char = Character(user_id=1, name="T")
    db_session.add(char)
    await db_session.flush()
    s1 = Item(character_id=char.id, name="Sh1", item_type="shield",
              is_equipped=True, item_metadata="{}")
    s2 = Item(character_id=char.id, name="Sh2", item_type="shield",
              is_equipped=True, item_metadata="{}")
    db_session.add_all([s1, s2])
    await db_session.flush()
    rule = HomebrewRule(
        character_id=char.id, name="Shield+1", dsl={
            "version": 1,
            "subject": {"type": "item", "filter": {"item_types": ["shield"]}},
            "passive_modifiers": [
                {"when": {"path": "$subject.is_equipped", "op": "eq", "value": True},
                 "target": "character.ac", "value": 1,
                 "label_i18n": {"it": "x", "en": "y"}},
            ],
            "triggers": [],
        }, created_at="x", updated_at="x",
    )
    db_session.add(rule)
    await db_session.flush()

    from api.services.homebrew.passive import get_passive_modifiers
    total = await get_passive_modifiers(db_session, char, "character.ac")
    assert total == 2  # both shields contribute +1
