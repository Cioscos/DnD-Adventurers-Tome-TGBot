"""Dispatcher tests — entry point with depth + cycle + ordering."""
import json
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from core.db.models import Base, Character, CharacterHistory, HomebrewRule, Item


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SM = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SM() as s:
        yield s


@pytest.mark.asyncio
async def test_dispatch_no_rules_returns_empty(db_session):
    char = Character(user_id=1, name="T")
    db_session.add(char)
    await db_session.flush()

    from api.services.homebrew.dispatcher import dispatch
    results = await dispatch(db_session, char, "attack_rolled", {})
    assert results == []


@pytest.mark.asyncio
async def test_dispatch_depth_exceeded_returns_empty_and_logs(db_session):
    char = Character(user_id=1, name="T")
    db_session.add(char)
    await db_session.flush()

    from api.services.homebrew.dispatcher import dispatch
    results = await dispatch(db_session, char, "attack_rolled", {}, depth=9)
    assert results == []

    history = await db_session.execute(
        select(CharacterHistory).where(CharacterHistory.character_id == char.id)
    )
    descs = [r.description for r in history.scalars()]
    assert any("Recursion" in d or "exceeded" in d.lower() for d in descs)


@pytest.mark.asyncio
async def test_dispatch_runs_rule_for_matching_event(db_session):
    char = Character(user_id=1, name="T")
    db_session.add(char)
    await db_session.flush()
    item = Item(
        character_id=char.id, name="Sword", item_type="weapon",
        item_metadata='{"hb_quality": "pessima"}', is_equipped=True,
    )
    db_session.add(item)
    await db_session.flush()

    dsl = {
        "version": 1,
        "subject": {"type": "item", "filter": {"item_types": ["weapon"]}},
        "triggers": [{
            "event": "attack_rolled",
            "filters": [{"path": "$event.is_fumble", "op": "eq", "value": True}],
            "effects": [{"action": "notify", "severity": "warning", "message": "ow!"}],
        }],
    }
    rule = HomebrewRule(
        character_id=char.id, name="r", dsl=dsl,
        created_at="x", updated_at="x",
    )
    db_session.add(rule)
    await db_session.flush()

    from api.services.homebrew.dispatcher import dispatch
    results = await dispatch(
        db_session, char, "attack_rolled",
        {"is_fumble": True, "item_id": item.id},
    )
    assert len(results) == 1
    assert "ow!" in results[0].notifications[0].message


@pytest.mark.asyncio
async def test_dispatch_skips_disabled_rule(db_session):
    char = Character(user_id=1, name="T")
    db_session.add(char)
    await db_session.flush()
    dsl = {
        "version": 1, "subject": {"type": "character"},
        "triggers": [{
            "event": "manual_trigger", "filters": [],
            "effects": [{"action": "notify", "severity": "info", "message": "should not fire"}],
        }],
    }
    rule = HomebrewRule(
        character_id=char.id, name="r", dsl=dsl, enabled=False,
        created_at="x", updated_at="x",
    )
    db_session.add(rule)
    await db_session.flush()

    from api.services.homebrew.dispatcher import dispatch
    results = await dispatch(db_session, char, "manual_trigger", {})
    assert results == []


@pytest.mark.asyncio
async def test_dispatch_cycle_detection(db_session):
    char = Character(user_id=1, name="T")
    db_session.add(char)
    await db_session.flush()
    dsl = {
        "version": 1, "subject": {"type": "character"},
        "triggers": [{"event": "manual_trigger", "filters": [],
                      "effects": [{"action": "notify", "severity": "info", "message": "x"}]}],
    }
    rule = HomebrewRule(
        character_id=char.id, name="r", dsl=dsl,
        created_at="x", updated_at="x",
    )
    db_session.add(rule)
    await db_session.flush()

    from api.services.homebrew.dispatcher import dispatch
    results = await dispatch(
        db_session, char, "manual_trigger", {},
        triggered_rule_stack=(rule.id,),
    )
    # rule in stack → skipped
    assert results == []


@pytest.mark.asyncio
async def test_dispatch_history_entries_persisted(db_session):
    char = Character(user_id=1, name="T")
    db_session.add(char)
    await db_session.flush()
    dsl = {
        "version": 1, "subject": {"type": "character"},
        "triggers": [{
            "event": "manual_trigger", "filters": [],
            "effects": [
                {"action": "add_history", "description": "Test entry from rule"},
            ],
        }],
    }
    rule = HomebrewRule(
        character_id=char.id, name="r", dsl=dsl,
        created_at="x", updated_at="x",
    )
    db_session.add(rule)
    await db_session.flush()

    from api.services.homebrew.dispatcher import dispatch
    results = await dispatch(db_session, char, "manual_trigger", {})
    assert len(results) == 1

    history = await db_session.execute(
        select(CharacterHistory).where(
            CharacterHistory.character_id == char.id,
            CharacterHistory.event_type == "homebrew",
        )
    )
    rows = list(history.scalars())
    assert any("Test entry from rule" in r.description for r in rows)


@pytest.mark.asyncio
async def test_dispatch_item_filter_bypass_via_item_id(db_session):
    """A rule scoped to weapons must NOT fire when payload.item_id points to armor."""
    char = Character(user_id=1, name="T")
    db_session.add(char); await db_session.flush()
    armor = Item(character_id=char.id, name="Mail", item_type="armor",
                 item_metadata='{"hb_quality":"pessima"}', is_equipped=True)
    db_session.add(armor); await db_session.flush()

    dsl = {
        "version": 1,
        "subject": {"type": "item", "filter": {"item_types": ["weapon"]}},
        "triggers": [{
            "event": "attack_rolled", "filters": [],
            "effects": [{"action": "notify", "severity": "info", "message": "should not fire"}],
        }],
    }
    rule = HomebrewRule(character_id=char.id, name="r", dsl=dsl,
                       created_at="x", updated_at="x")
    db_session.add(rule); await db_session.flush()

    from api.services.homebrew.dispatcher import dispatch
    results = await dispatch(
        db_session, char, "attack_rolled",
        {"is_fumble": True, "item_id": armor.id},
    )
    assert results == []


@pytest.mark.asyncio
async def test_dispatch_rejects_cross_character_item(db_session):
    """A rule on char A must NOT fire when payload.item_id points to char B's item."""
    char_a = Character(user_id=1, name="A")
    char_b = Character(user_id=2, name="B")
    db_session.add_all([char_a, char_b]); await db_session.flush()
    item_b = Item(character_id=char_b.id, name="Sword B", item_type="weapon",
                  item_metadata='{"hb_quality":"pessima"}', is_equipped=True)
    db_session.add(item_b); await db_session.flush()

    dsl = {
        "version": 1,
        "subject": {"type": "item", "filter": {"item_types": ["weapon"]}},
        "triggers": [{
            "event": "attack_rolled", "filters": [],
            "effects": [{"action": "notify", "severity": "warning", "message": "ow"}],
        }],
    }
    rule_a = HomebrewRule(character_id=char_a.id, name="r", dsl=dsl,
                         created_at="x", updated_at="x")
    db_session.add(rule_a); await db_session.flush()

    from api.services.homebrew.dispatcher import dispatch
    results = await dispatch(
        db_session, char_a, "attack_rolled",
        {"item_id": item_b.id},
    )
    assert results == []  # rule_a must NOT see char_b's item


@pytest.mark.asyncio
async def test_dispatch_total_level_resolves_correctly(db_session):
    """A filter on $character.total_level must see the real level, not 0."""
    from core.db.models import CharacterClass
    char = Character(user_id=1, name="T")
    db_session.add(char); await db_session.flush()
    cls = CharacterClass(character_id=char.id, class_name="fighter", level=5)
    db_session.add(cls); await db_session.flush()
    # DO NOT refresh char with classes — dispatch should preload.

    dsl = {
        "version": 1, "subject": {"type": "character"},
        "triggers": [{
            "event": "manual_trigger",
            "filters": [{"path": "$character.total_level", "op": "gte", "value": 5}],
            "effects": [{"action": "notify", "severity": "info", "message": "lvl5+"}],
        }],
    }
    rule = HomebrewRule(character_id=char.id, name="r", dsl=dsl,
                       created_at="x", updated_at="x")
    db_session.add(rule); await db_session.flush()

    from api.services.homebrew.dispatcher import dispatch
    results = await dispatch(db_session, char, "manual_trigger", {})
    assert len(results) == 1
    assert results[0].notifications[0].message == "lvl5+"


@pytest.mark.asyncio
async def test_dispatch_invalid_dsl_disables_rule(db_session):
    char = Character(user_id=1, name="T")
    db_session.add(char)
    await db_session.flush()
    # Pass invalid DSL directly via dict (model accepts JSON dict)
    rule = HomebrewRule(
        character_id=char.id, name="r",
        dsl={"version": 99, "subject": {"type": "item"}, "triggers": [
            {"event": "manual_trigger", "filters": [], "effects": []}
        ]},
        created_at="x", updated_at="x", enabled=True,
    )
    db_session.add(rule)
    await db_session.flush()

    from api.services.homebrew.dispatcher import dispatch
    results = await dispatch(db_session, char, "manual_trigger", {})
    assert results == []
    await db_session.refresh(rule)
    assert rule.enabled is False
    history = await db_session.execute(
        select(CharacterHistory).where(
            CharacterHistory.character_id == char.id,
            CharacterHistory.event_type == "homebrew",
        )
    )
    descs = [r.description for r in history.scalars()]
    assert any("disattivata" in d.lower() or "disabled" in d.lower() for d in descs)
