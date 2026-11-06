"""Ladro 2014, Furfante (Task 27): Mani Veloci, Lavoro al Secondo Piano, Furtività Suprema, Usare Oggetto Magico e
Riflessi da Furfante."""
from __future__ import annotations

import pytest

from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard import _ability, _full, _keys_of, _roll_keys, _use
from tests.integration.rules.test_2014_paladin import _turn
from tests.integration.rules.test_2014_rogue import CUNNING, _rogue, _skill_roll

FAST_HANDS, SECOND_STORY, SUPREME, MAGIC_DEVICE, REFLEXES = (
    "rogue.fast_hands", "rogue.second_story_work", "rogue.supreme_sneak", "rogue.use_magic_device", "rogue.thiefs_reflexes")
SUPREME_ADV = "rogue.supreme_sneak_advantage"
THREE = ["dash", "disengage", "hide"]
SIX = [*THREE, "sleight_of_hand", "thieves_tools", "use_object"]


async def test_the_thief_features_come_at_their_levels(client):
    for level, keys in ((3, {FAST_HANDS, SECOND_STORY}), (9, {SUPREME}), (13, {MAGIC_DEVICE}), (17, {REFLEXES})):
        before = await _keys_of(client, await _rogue(client, level - 1 if level > 3 else 2, "thief"))
        after = await _keys_of(client, await _rogue(client, level, "thief"))
        assert not before & keys and keys <= after, level


async def test_a_rogue_of_another_archetype_has_no_thief_features(client):
    keys = await _keys_of(client, await _rogue(client, 17, "assassin"))
    assert not keys & {FAST_HANDS, SECOND_STORY, SUPREME, MAGIC_DEVICE, REFLEXES}


# ---------------------------------------------------------------------------
# Mani Veloci
# ---------------------------------------------------------------------------

async def test_fast_hands_adds_three_bonus_actions_to_cunning_action(client):
    cid = await _rogue(client, 3, "thief")
    options = [o["key"] for o in (await _ability(client, cid, CUNNING))["use_choices"][0]["options"]]
    assert options == SIX
    for action in ("sleight_of_hand", "thieves_tools", "use_object"):
        r = await _use(client, cid, CUNNING, params={"action": action})
        assert r.status_code == 200, r.text
        assert f"cunning_{action}" in r.json()["notes"] and (await _turn(client, cid))["bonus_used"] is True
        await client.post(f"/characters/{cid}/turn/new")


@pytest.mark.parametrize("archetype", [None, "assassin", "arcane_trickster"])
async def test_without_fast_hands_cunning_action_keeps_the_three_actions(client, archetype):
    cid = await _rogue(client, 3, archetype)
    assert [o["key"] for o in (await _ability(client, cid, CUNNING))["use_choices"][0]["options"]] == THREE
    refused = await _use(client, cid, CUNNING, params={"action": "use_object"})
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "invalid_choice"


# ---------------------------------------------------------------------------
# Lavoro al Secondo Piano
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("dexterity,bonus", [(8, 0), (10, 0), (14, 2), (16, 3), (20, 5)])
async def test_second_story_work_adds_one_foot_per_dexterity_modifier_to_the_long_jump(client, dexterity, bonus):
    cid = await _rogue(client, 3, "thief", dexterity=dexterity)
    assert (await _full(client, cid))["computed"]["long_jump_bonus_ft"] == bonus


async def test_the_long_jump_bonus_is_absent_without_the_feature(client):
    assert not (await _full(client, await _rogue(client, 3, "assassin", dexterity=16)))["computed"].get("long_jump_bonus_ft")
    assert not (await _full(client, await _rogue(client, 2, dexterity=16)))["computed"].get("long_jump_bonus_ft")


# ---------------------------------------------------------------------------
# Furtività Suprema
# ---------------------------------------------------------------------------

async def test_supreme_sneak_offers_advantage_on_stealth_only(client):
    cid = await _rogue(client, 9, "thief")
    assert SUPREME_ADV in await _roll_keys(client, cid, "skill", skill="stealth")
    assert SUPREME_ADV not in await _roll_keys(client, cid, "skill", skill="perception")
    body = await _skill_roll(client, cid, "stealth", SUPREME_ADV, dice=[4, 15])
    assert body["mode_applied"] == "advantage" and body["die"] == 15
    assert "feature:rogue.supreme_sneak" in body["notes"]


async def test_supreme_sneak_needs_the_thief_at_level_9(client):
    assert SUPREME_ADV not in await _roll_keys(client, await _rogue(client, 8, "thief"), "skill", skill="stealth")
    assert SUPREME_ADV not in await _roll_keys(client, await _rogue(client, 9, "assassin"), "skill", skill="stealth")


# ---------------------------------------------------------------------------
# Usare Oggetto Magico
# ---------------------------------------------------------------------------

async def test_use_magic_device_is_a_passive_row_of_the_thief(client):
    row = await _ability(client, await _rogue(client, 13, "thief"), MAGIC_DEVICE)
    assert row["action_type"] is None or row["action_type"] == "passive"
    assert (await _ability(client, await _rogue(client, 13, "assassin"), MAGIC_DEVICE)) is None


# ---------------------------------------------------------------------------
# Riflessi da Furfante
# ---------------------------------------------------------------------------

async def _reflexes_encounter(client, factory, *, surprised=False, level=17, subclass="Furfante"):
    sid, cid = await seed_session(factory)
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "rogue", "level": level, "hit_die": 8, "subclass": subclass})
    assert r.status_code == 201, r.text
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    assert r.status_code == 201, r.text
    enc = (await client.post(f"/sessions/{sid}/encounter/combatants",
                             json={"name": "Goblin", "count": 1, "initiative_mod": 0, "max_hp": 7, "ac": 15})).json()
    pc, goblin = (next(c for c in enc["combatants"] if c["kind"] == k)["id"] for k in ("pc", "monster"))
    as_user(PLAYER_ID)
    await client.post(f"/sessions/{sid}/encounter/combatants/{pc}/initiative", json={"die": 20})
    as_user(GM_ID)
    await client.post(f"/sessions/{sid}/encounter/combatants/{goblin}/initiative", json={"die": 1})
    if surprised:
        r = await client.patch(f"/sessions/{sid}/encounter/combatants/{pc}", json={"surprised": True})
        assert r.status_code == 200, r.text
    r = await client.post(f"/sessions/{sid}/encounter/start", json={})
    assert r.status_code == 200, r.text
    return sid, cid, r.json()


def _order(live: dict) -> list[tuple[str, int | None]]:
    rows = sorted((c for c in live["combatants"] if c["sort_order"] is not None), key=lambda c: c["sort_order"])
    return [(c["name"], c["initiative"]) for c in rows]


async def _next(client, sid) -> dict:
    r = await client.post(f"/sessions/{sid}/encounter/next-turn")
    assert r.status_code == 200, r.text
    return r.json()


def _active(live: dict) -> dict:
    return next(c for c in live["combatants"] if c["id"] == live["active_combatant_id"])


async def test_thiefs_reflexes_adds_a_second_turn_at_initiative_minus_10(client, test_session_factory):
    _sid, _cid, live = await _reflexes_encounter(client, test_session_factory)
    order = _order(live)
    assert [i for _n, i in order] == [23, 13, 1]  # Destrezza 16: 20 + 3, poi meno 10, poi il goblin
    assert order[0][0] == "Eroe" and "Riflessi" in order[1][0] and order[2][0].startswith("Goblin")


async def test_the_second_turn_belongs_to_the_same_player_and_only_lasts_the_first_round(client, test_session_factory):
    sid, _cid, live = await _reflexes_encounter(client, test_session_factory)
    extra = next(c for c in live["combatants"] if "Riflessi" in c["name"])
    assert extra["kind"] == "pc" and extra["owner_user_id"] == PLAYER_ID and extra["character_id"] is None
    seen = []
    for _ in range(5):
        live = await _next(client, sid)
        seen.append((live["round"], _active(live)["name"].split(" ")[0]))
    # secondo turno del round 1, goblin, round 2 (PG), goblin (nessun secondo turno), round 3 (PG)
    assert seen == [(1, "Eroe"), (1, "Goblin"), (2, "Eroe"), (2, "Goblin"), (3, "Eroe")]
    assert [r for r, _ in seen] == [1, 1, 2, 2, 3]


async def test_the_second_turn_gives_the_rogue_a_fresh_turn(client, test_session_factory):
    sid, cid, _live = await _reflexes_encounter(client, test_session_factory)
    as_user(PLAYER_ID)
    assert (await _use(client, cid, CUNNING, params={"action": "dash"})).status_code == 200
    assert (await _turn(client, cid))["bonus_used"] is True
    as_user(GM_ID)
    await _next(client, sid)  # il secondo turno
    as_user(PLAYER_ID)
    assert (await _turn(client, cid))["bonus_used"] is False


async def test_a_surprised_rogue_has_no_second_turn(client, test_session_factory):
    _sid, _cid, live = await _reflexes_encounter(client, test_session_factory, surprised=True)
    assert len(_order(live)) == 2 and not [c for c in live["combatants"] if "Riflessi" in c["name"]]


@pytest.mark.parametrize("level,subclass", [(16, "Furfante"), (17, "Assassino")])
async def test_only_a_thief_of_level_17_has_a_second_turn(client, test_session_factory, level, subclass):
    _sid, _cid, live = await _reflexes_encounter(client, test_session_factory, level=level, subclass=subclass)
    assert not [c for c in live["combatants"] if "Riflessi" in c["name"]]


async def test_going_back_a_turn_at_the_end_of_round_1_keeps_the_second_turn(client, test_session_factory):
    sid, _cid, _live = await _reflexes_encounter(client, test_session_factory)
    for _ in range(3):
        await _next(client, sid)  # round 2, di nuovo il PG
    r = await client.post(f"/sessions/{sid}/encounter/prev-turn")
    assert r.status_code == 200, r.text
    live = r.json()
    assert live["round"] == 1 and _active(live)["name"].startswith("Goblin")
