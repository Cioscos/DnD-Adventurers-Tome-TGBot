"""Paladino 2014, giro di correzione 1 (I6): lo stesso stile di combattimento non si prende due volte fra classi."""
from __future__ import annotations

import pytest

from core.db.models import CharacterClass
from tests.integration.rules.test_2014_bard import _full
from tests.integration.rules.test_2014_fighter import _fighter
from tests.integration.rules.test_2014_fighter_styles import _choose, _pending
from tests.integration.rules.test_2014_paladin import _paladin
from tests.integration.rules.test_2014_paladin_round1 import _add_class

PALADIN_STYLES = {"great_weapon", "defense", "dueling", "protection"}
FIGHTER_STYLES = {"archery", "defense", "dueling", "great_weapon", "two_weapon", "protection"}


def _offered(full: dict) -> set[str]:
    return {o["key"] for o in _pending(full)["options"]}


async def _damage_bonus(client, cid) -> int:
    return (await _full(client, cid)).get("damage_bonus", 0)


@pytest.mark.parametrize("style", ["dueling", "defense", "protection", "great_weapon"])
async def test_a_second_class_cannot_take_the_style_the_paladin_already_has(client, style):
    cid = await _paladin(client, 2)
    assert (await _choose(client, cid, style)).status_code == 200
    await _add_class(client, cid, "fighter", 1, hit_die=10)
    assert _offered(await _full(client, cid)) == FIGHTER_STYLES - {style}
    refused = await _choose(client, cid, style)
    assert refused.status_code >= 400
    assert _pending(await _full(client, cid)) is not None  # la scelta resta in sospeso
    other = sorted(FIGHTER_STYLES - {style})[0]
    assert (await _choose(client, cid, other)).status_code == 200


@pytest.mark.parametrize("style", ["dueling", "defense", "protection", "great_weapon"])
async def test_the_paladin_cannot_take_the_style_a_fighter_already_has(client, style):
    cid = await _fighter(client, 1)
    assert (await _choose(client, cid, style)).status_code == 200
    await _add_class(client, cid, "paladin", 2, hit_die=10)
    assert _offered(await _full(client, cid)) == PALADIN_STYLES - {style}
    assert (await _choose(client, cid, style)).status_code >= 400
    assert _pending(await _full(client, cid)) is not None
    other = sorted(PALADIN_STYLES - {style})[0]
    assert (await _choose(client, cid, other)).status_code == 200


async def test_a_style_only_the_fighter_has_is_not_offered_to_the_paladin_and_the_other_way_round(client):
    cid = await _fighter(client, 1)
    assert (await _choose(client, cid, "archery")).status_code == 200
    await _add_class(client, cid, "paladin", 2, hit_die=10)
    assert _offered(await _full(client, cid)) == PALADIN_STYLES  # Tiro con l'Arco non c'è comunque fra i suoi


async def test_a_character_that_already_has_the_same_style_twice_keeps_loading_and_nothing_is_rewritten(client, test_session_factory):
    from sqlalchemy import select
    cid = await _paladin(client, 2)
    await _add_class(client, cid, "fighter", 1, hit_die=10)
    async with test_session_factory() as s:
        rows = (await s.execute(select(CharacterClass).where(CharacterClass.character_id == cid))).scalars().all()
        for row in rows:
            row.options = {"fighting_style": ["defense"]}
        await s.commit()
    full = await _full(client, cid)
    assert [c["options"] for c in full["classes"]] == [{"fighting_style": ["defense"]}] * 2
