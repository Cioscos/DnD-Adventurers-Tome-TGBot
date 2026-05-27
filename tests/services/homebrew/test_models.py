"""Smoke tests on HomebrewRule / HomebrewResource ORM models."""
from __future__ import annotations

from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from core.db.models import Base, Character, HomebrewRule


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as s:
        yield s


@pytest.mark.asyncio
async def test_homebrew_rule_create_and_relationship(session):
    char = Character(user_id=42, name="Aragorn")
    session.add(char)
    await session.flush()

    rule = HomebrewRule(
        character_id=char.id,
        name="Quality & Wear",
        description="Master house rule",
        enabled=True,
        dsl={"version": 1, "subject": {"type": "item"}, "triggers": []},
        version=1,
        template_id=None,
        created_at=datetime.utcnow().isoformat(timespec="seconds"),
        updated_at=datetime.utcnow().isoformat(timespec="seconds"),
    )
    session.add(rule)
    await session.flush()
    await session.refresh(char, attribute_names=["homebrew_rules"])

    assert rule.id is not None
    assert rule.character_id == char.id
    assert rule.dsl["version"] == 1
    assert len(char.homebrew_rules) == 1
    assert char.homebrew_rules[0].name == "Quality & Wear"
