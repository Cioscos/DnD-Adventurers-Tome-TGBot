"""Homebrew-specific fixtures for integration tests.

The base ``test_session_factory`` and ``client`` fixtures live one level up in
``tests/integration/conftest.py`` (pytest discovers them automatically via the
nested conftest mechanism). This file only contains fixtures that are specific
to the homebrew router test suite.
"""
from __future__ import annotations

from typing import Sequence, Union

import pytest
import pytest_asyncio

from core.db.models import Character

# Re-exported so test modules that historically imported it from here
# (e.g. ``from tests.integration.homebrew.conftest import TEST_USER_ID``)
# keep working. The single source of truth is the parent conftest.
from tests.integration.conftest import TEST_USER_ID  # noqa: F401


@pytest_asyncio.fixture
async def char_id(test_session_factory) -> int:
    """Create a Character owned by TEST_USER_ID and return its id."""
    async with test_session_factory() as session:
        char = Character(user_id=TEST_USER_ID, name="Test")
        session.add(char)
        await session.commit()
        await session.refresh(char)
        return char.id


def notify_rule(event: str, message: str, name: str = "Test Lifecycle Rule") -> dict:
    """Build a HomebrewRule create body with a single notify trigger on `event`.

    Shared across integration tests for lifecycle events (long_rest_taken,
    short_rest_taken, spell_cast, ability_used, item_equipped/unequipped,
    level_up, ...). Importable as a plain function — keep it side-effect-free.
    """
    return {
        "name": name,
        "description": "Integration test rule",
        "enabled": True,
        "dsl": {
            "version": 1,
            "subject": {"type": "character"},
            "triggers": [
                {
                    "event": event,
                    "filters": [],
                    "effects": [
                        {"action": "notify", "severity": "info", "message": message}
                    ],
                }
            ],
        },
    }


@pytest.fixture
def patch_random_roll(monkeypatch):
    """Patch ``random.randint`` on the shared module object for deterministic rolls.

    Both ``api/routers/items.py`` and ``api/services/homebrew/actions.py`` do
    ``import random``, so they reference the same module object — patching the
    module's ``randint`` attribute covers both call sites with a single patch.

    Returns a callable with two forms:

    - ``patch_random_roll(value)`` where ``value`` is an ``int``: every call to
      ``random.randint`` returns ``value`` (constant).
    - ``patch_random_roll(rolls, fallback=10)`` where ``rolls`` is a sequence of
      ``int``: each call consumes the next value from the iterator; once the
      sequence is exhausted, ``fallback`` is returned for all subsequent calls.

    Calling the returned callable more than once within a single test resets the
    patch (replaces the previous lambda) — useful for staged scenarios.
    """
    def _patch(rolls: Union[int, Sequence[int]], fallback: int = 10) -> None:
        import random as _random
        if isinstance(rolls, int):
            value = rolls
            monkeypatch.setattr(_random, "randint", lambda lo, hi: value)
        else:
            it = iter(rolls)
            monkeypatch.setattr(_random, "randint", lambda lo, hi: next(it, fallback))

    return _patch
