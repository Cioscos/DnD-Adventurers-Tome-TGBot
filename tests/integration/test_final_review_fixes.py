"""Rilievi della revisione finale di feat/regole-classi: settings del server, commit prima della risposta."""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest
from sqlalchemy import select

from api.database import get_db
from api.main import app
from core.db.models import Character
from core.rules.proficiencies import seed_character
from core.rules.roll_options import _slot_free
from core.rules.states import begin_state
from core.rules.types import StateSpec
from core.rules.weapons import small_race

SERVER_KEYS = {"saved_dice": {"portent": [7]}, "knocked_out": True, "hiding": {"roll": 14},
               "inspiration_extra": True, "ac_migrated": True, "proficiencies_seeded": True,
               "feature_proficiencies_granted": ["x"]}


async def test_patch_settings_keeps_server_written_keys(client, test_session_factory):
    char_id = (await client.post("/characters", json={"name": "Eroe"})).json()["id"]
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == char_id))).scalar_one()
        char.settings = dict(SERVER_KEYS)
        await s.commit()
    r = await client.patch(f"/characters/{char_id}", json={"settings": {"quick_actions": ["a"]}})
    assert r.status_code == 200, r.text
    async with test_session_factory() as s:
        saved = (await s.execute(select(Character).where(Character.id == char_id))).scalar_one().settings
    assert {k: saved.get(k) for k in SERVER_KEYS} == SERVER_KEYS
    assert saved["quick_actions"] == ["a"]


def test_every_route_commits_before_the_response():
    """get_db con scope "function": il commit avviene prima dell'invio, non dopo (chiude la finestra di rilettura)."""
    def walk(dep):
        for sub in dep.dependencies:
            yield sub
            yield from walk(sub)

    bad = [r.path for r in app.routes if getattr(r, "dependant", None)
           for sub in walk(r.dependant) if sub.call is get_db and sub.scope != "function"]
    assert not bad, bad


def _item(name, item_type, **meta):
    return NS(name=name, item_type=item_type, item_metadata=meta, is_equipped=False)


def test_seed_keeps_weapons_and_armor_already_in_inventory():
    items = [_item("Spada lunga", "weapon", weapon_category="martial", properties=[]),
             _item("Cotta di maglia", "armor", armor_type="heavy")]
    char = NS(general_proficiencies={"weapons": ["Spade lunghe"]}, settings={}, classes=[
        NS(id=1, class_name="wizard", class_key="wizard", level=3)], items=items, rules_edition="2014",
        saving_throws={}, skills={}, languages=[])
    seed_character(char)
    from core.rules.proficiencies import is_armor_proficient, is_weapon_proficient
    assert is_weapon_proficient(char, items[0])
    assert is_armor_proficient(char, items[1])


@pytest.mark.parametrize("race,expected", [("Hobgoblin", False), ("Goblin", True), ("Gnomo", True)])
def test_small_race_goblin_is_whole_word(race, expected):
    assert small_race(NS(race=race)) is expected


def test_begin_state_tolerates_stored_state_without_keys():
    char = NS(active_states=[{"condition": "invisible"}, {"key": "x", "condition": "invisible"}],
              conditions={})
    begin_state(char, StateSpec(key="x", condition="invisible", rounds=1), "f")
    assert [s.get("key") for s in char.active_states][-1] == "x"


def test_null_extra_actions_is_not_a_typeerror():
    char = NS(turn_state={"action_used": True, "extra_actions": None})
    assert _slot_free(char, "action") is False


async def test_character_list_exposes_classes_for_translation(client):
    r = await client.post("/characters", json={"name": "Eroe"})
    char_id = r.json()["id"]
    await client.post(f"/characters/{char_id}/classes", json={"class_name": "wizard", "level": 3})
    item = next(c for c in (await client.get("/characters")).json() if c["id"] == char_id)
    assert item["classes"] == [{"class_name": "wizard", "level": 3, "subclass": None}]
