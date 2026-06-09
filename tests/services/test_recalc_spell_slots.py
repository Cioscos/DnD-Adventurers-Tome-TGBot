"""Unit test della ricomputazione automatica degli spell slot.

``recalc_spell_slots`` riconcilia ``char.spell_slots`` con le tabelle D&D 5e
(``core.data.spell_slots``) quando la modalità è automatica (``settings`` driven,
default on), preservando ``used`` (clampato al nuovo ``total``) così un level-up
non rimborsa mai slot già spesi.
"""
from __future__ import annotations

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.db.models import Base, Character, CharacterClass, SpellSlot
from api.services.spell_slots import recalc_spell_slots


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def _make_char(
    session: AsyncSession,
    classes: list[CharacterClass],
    slots: list[SpellSlot] | None = None,
    settings: dict | None = None,
) -> Character:
    # Imposta TUTTE le relazioni toccate da recalc prima del primo flush così
    # restano caricate e non scatenano lazy-load in contesto async.
    char = Character(user_id=1, name="Caster")
    char.settings = settings
    char.classes = classes
    char.spell_slots = slots or []
    session.add(char)
    await session.flush()
    return char


def _by_key(char: Character) -> dict[tuple[int, bool], SpellSlot]:
    return {(s.level, bool(s.is_pact)): s for s in char.spell_slots}


async def test_automatic_wizard_l5_creates_full_caster_slots(session):
    char = await _make_char(session, [CharacterClass(class_name="wizard", level=5)])
    await recalc_spell_slots(session, char)
    slots = _by_key(char)
    # Full caster L5 ⇒ 4×1° / 3×2° / 2×3°.
    assert {k[0]: v.total for k, v in slots.items()} == {1: 4, 2: 3, 3: 2}
    assert all(s.used == 0 and s.is_pact is False for s in char.spell_slots)


async def test_levelup_preserves_spent_slots(session):
    # Mago L3 con uno slot di 1° già speso una volta.
    existing = SpellSlot(level=1, total=2, used=1, is_pact=False)
    char = await _make_char(
        session, [CharacterClass(class_name="wizard", level=3)], slots=[existing]
    )
    await recalc_spell_slots(session, char)
    slots = _by_key(char)
    # Target L3 ⇒ {1:4, 2:2}; lo slot di 1° cresce a 4 ma mantiene used=1.
    assert slots[(1, False)].total == 4
    assert slots[(1, False)].used == 1
    assert slots[(2, False)].total == 2
    assert slots[(2, False)].used == 0


async def test_used_is_clamped_when_total_shrinks(session):
    # Slot sovradimensionato (4/4 usati) ma la classe ne concede solo 2.
    oversized = SpellSlot(level=1, total=4, used=4, is_pact=False)
    char = await _make_char(
        session, [CharacterClass(class_name="wizard", level=1)], slots=[oversized]
    )
    await recalc_spell_slots(session, char)
    slots = _by_key(char)
    assert slots[(1, False)].total == 2
    assert slots[(1, False)].used == 2  # clampato a total


async def test_manual_mode_is_a_noop(session):
    char = await _make_char(
        session,
        [CharacterClass(class_name="wizard", level=5)],
        settings={"spell_slots_mode": "manual"},
    )
    await recalc_spell_slots(session, char)
    assert list(char.spell_slots) == []


async def test_drops_slots_the_rules_no_longer_grant(session):
    # Mago L1 concede solo {1:2}; uno slot di 5° spurio va rimosso.
    char = await _make_char(
        session,
        [CharacterClass(class_name="wizard", level=1)],
        slots=[
            SpellSlot(level=1, total=2, used=0, is_pact=False),
            SpellSlot(level=5, total=1, used=0, is_pact=False),
        ],
    )
    await recalc_spell_slots(session, char)
    slots = _by_key(char)
    assert set(slots.keys()) == {(1, False)}
    assert slots[(1, False)].total == 2


async def test_warlock_gets_a_separate_pact_pool(session):
    char = await _make_char(session, [CharacterClass(class_name="warlock", level=3)])
    await recalc_spell_slots(session, char)
    slots = _by_key(char)
    # Warlock L3 Pact Magic ⇒ 2 slot di livello 2, pool pact separato.
    assert set(slots.keys()) == {(2, True)}
    assert slots[(2, True)].total == 2
    assert slots[(2, True)].is_pact is True
