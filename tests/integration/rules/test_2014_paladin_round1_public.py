"""Paladino 2014, giro di correzione 1 (I9): le aure di Coraggio e Devozione dicono al GM e al gruppo cosa danno agli alleati."""
from __future__ import annotations

import pytest

from core.db.models import Character
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID
from tests.integration.rules.test_2014_barbarian_round1 import _combatant_states, _in_encounter
from tests.integration.rules.test_2014_bard import _full
from tests.integration.rules.test_2014_paladin import OATHS, _paladin
from tests.integration.rules.test_2014_paladin_round1 import _add_class

COURAGE, DEVOTION = "aura_of_courage", "aura_of_devotion"


async def _paladin_at_the_table(client, factory, monkeypatch, level, oath="devotion"):
    sid, cid = await _in_encounter(client, factory, monkeypatch)
    await _add_class(client, cid, "paladin", level, OATHS[oath], hit_die=10)
    return sid, cid


@pytest.mark.parametrize("viewer", [GM_ID, PLAYER_ID])
async def test_courage_and_devotion_are_listed_for_the_gm_and_the_group_with_their_text(client, test_session_factory, monkeypatch, viewer):
    sid, cid = await _paladin_at_the_table(client, test_session_factory, monkeypatch, 10)
    states = {s["key"]: s for s in await _combatant_states(client, sid, viewer)}
    assert {COURAGE, DEVOTION} <= set(states)
    [courage] = states[COURAGE]["others"]
    assert courage["key"] == "paladin.aura_of_courage" and "spaventati" in courage["text"]
    assert "affascinati" in states[DEVOTION]["others"][0]["text"] and states[COURAGE]["rounds_left"] is None


async def test_the_text_is_not_published_before_the_level_or_for_the_wrong_oath(client, test_session_factory, monkeypatch):
    sid, cid = await _paladin_at_the_table(client, test_session_factory, monkeypatch, 9, "ancients")
    assert not {COURAGE, DEVOTION} & {s["key"] for s in await _combatant_states(client, sid, GM_ID)}
    other = await _paladin(client, 10, "vengeance")  # il Coraggio è di ogni paladino, la Devozione solo dell'omonimo giuramento
    assert {s["key"] for s in (await _full(client, other))["active_states"] or []} == {COURAGE}


async def test_the_text_goes_away_while_the_paladin_is_unconscious_and_comes_back_when_he_wakes(client, test_session_factory, monkeypatch):
    sid, cid = await _paladin_at_the_table(client, test_session_factory, monkeypatch, 10)
    async with test_session_factory() as s:
        char = await s.get(Character, cid)
        char.hit_points, char.current_hit_points, char.conditions = 30, 0, {"unconscious": True}
        await s.commit()
    assert not {COURAGE, DEVOTION} & {s["key"] for s in await _combatant_states(client, sid, GM_ID)}
    async with test_session_factory() as s:
        char = await s.get(Character, cid)
        char.current_hit_points, char.conditions = 12, {}
        await s.commit()
    assert {COURAGE, DEVOTION} <= {s["key"] for s in await _combatant_states(client, sid, GM_ID)}


async def test_the_paladin_sheet_keeps_the_permanent_states_and_no_one_can_leave_the_aura_off(client, test_session_factory, monkeypatch):
    sid, cid = await _paladin_at_the_table(client, test_session_factory, monkeypatch, 10)
    keys = {s["key"] for s in (await _full(client, cid))["active_states"] or []}
    assert {COURAGE, DEVOTION} <= keys
