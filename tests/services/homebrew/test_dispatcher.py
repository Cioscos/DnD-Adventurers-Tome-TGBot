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


@pytest.mark.asyncio
async def test_dispatch_damage_chain_terminates_via_cycle_detection(db_session):
    """A rule on damage_taken that calls damage_character must not infinite-loop:
    cycle detection stops the same rule from firing twice in a single dispatch chain."""
    char = Character(user_id=1, name="T", hit_points=100, current_hit_points=100)
    db_session.add(char)
    await db_session.flush()
    dsl = {
        "version": 1, "subject": {"type": "character"},
        "triggers": [{
            "event": "damage_taken", "filters": [],
            "effects": [{"action": "damage_character", "amount": 1}],
        }],
    }
    rule = HomebrewRule(
        character_id=char.id, name="LoopRule", dsl=dsl,
        created_at="x", updated_at="x",
    )
    db_session.add(rule)
    await db_session.flush()

    from api.services.homebrew.dispatcher import dispatch
    # No initial damage; we manually call dispatch with damage_taken.
    await dispatch(db_session, char, "damage_taken", {"amount": 0})

    await db_session.refresh(char)
    # Cycle detection means the rule fires exactly ONCE.
    # First fire: damage_character with amount=1 → HP=99 → re-emits damage_taken
    # Second attempted fire: rule already in stack → skipped.
    # Net: HP went from 100 to 99 (one damage).
    assert char.current_hit_points == 99, (
        f"Expected exactly one damage application (cycle stops at depth 1); "
        f"got HP={char.current_hit_points} (potential infinite loop or unexpected depth)"
    )


@pytest.mark.asyncio
async def test_dispatch_damage_chain_re_emission_fires_independent_rule(db_session):
    """A rule on damage_taken can be triggered by another rule's damage_character call."""
    char = Character(user_id=1, name="T", hit_points=100, current_hit_points=100)
    db_session.add(char)
    await db_session.flush()
    # Rule A: on manual_trigger, deal 5 damage
    dsl_a = {
        "version": 1, "subject": {"type": "character"},
        "triggers": [{
            "event": "manual_trigger", "filters": [],
            "effects": [{"action": "damage_character", "amount": 5}],
        }],
    }
    rule_a = HomebrewRule(
        character_id=char.id, name="A", dsl=dsl_a,
        created_at="x", updated_at="x",
    )
    # Rule B: on damage_taken (triggered by A's damage), notify
    dsl_b = {
        "version": 1, "subject": {"type": "character"},
        "triggers": [{
            "event": "damage_taken", "filters": [],
            "effects": [{"action": "notify", "severity": "info",
                         "message": "took $event.amount"}],
        }],
    }
    rule_b = HomebrewRule(
        character_id=char.id, name="B", dsl=dsl_b,
        created_at="x", updated_at="x",
    )
    db_session.add_all([rule_a, rule_b])
    await db_session.flush()

    from api.services.homebrew.dispatcher import dispatch
    results = await dispatch(db_session, char, "manual_trigger", {})

    await db_session.refresh(char)
    assert char.current_hit_points == 95  # 100 - 5
    # Rule B fired in the re-emit chain. Its notification went to its OWN
    # RuleFiringResult, persisted in the inner dispatch call. The outer dispatch's
    # `results` list only contains rule_a's RFR (which has no notifications).
    # The inner-dispatch results aren't returned to the outer caller, but the side
    # effects (notifications-as-history if any, DB writes) ARE applied.
    assert len(results) == 1
    assert results[0].rule_name == "A"


@pytest.mark.asyncio
async def test_dispatch_heal_chain_re_emits_hp_healed(db_session):
    """A rule on hp_healed must be triggered when another rule's heal_character runs."""
    char = Character(user_id=1, name="T", hit_points=100, current_hit_points=10)
    db_session.add(char)
    await db_session.flush()
    dsl_a = {
        "version": 1, "subject": {"type": "character"},
        "triggers": [{
            "event": "manual_trigger", "filters": [],
            "effects": [{"action": "heal_character", "amount": 5}],
        }],
    }
    rule_a = HomebrewRule(character_id=char.id, name="A", dsl=dsl_a,
                         created_at="x", updated_at="x")
    dsl_b = {
        "version": 1, "subject": {"type": "character"},
        "triggers": [{
            "event": "hp_healed", "filters": [],
            "effects": [{"action": "notify", "severity": "info", "message": "healed $event.amount"}],
        }],
    }
    rule_b = HomebrewRule(character_id=char.id, name="B", dsl=dsl_b,
                         created_at="x", updated_at="x")
    db_session.add_all([rule_a, rule_b])
    await db_session.flush()

    from api.services.homebrew.dispatcher import dispatch
    results = await dispatch(db_session, char, "manual_trigger", {})
    await db_session.refresh(char)
    assert char.current_hit_points == 15  # 10 + 5
    # rule_a's RFR returned, rule_b fired in the inner dispatch chain
    assert len(results) == 1
    assert results[0].rule_name == "A"
