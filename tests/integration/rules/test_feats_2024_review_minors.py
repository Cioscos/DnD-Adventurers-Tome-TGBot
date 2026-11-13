"""Problemi minori della revisione finale della PR 2 talenti."""
from __future__ import annotations

import pytest

from api.services import ally_reactions as svc
from tests.integration._encounter_helpers import as_user, seed_session
from tests.integration.rules.test_2014_bard import _full, _roll_keys
from tests.integration.rules.test_2014_barbarian import _armor
from tests.integration.rules.test_2014_fighter_styles import _item
from tests.integration.rules.test_feats_2024_general import STATS
from tests.integration.rules.test_feats_2024_selection import _char
from tests.integration.rules.test_feats_take_complete import _complete, _feat_rows, _take
from tests.integration.test_ally_reactions import _open, _poll, _seat

HAM = "feat.2024_heavy_armor_master"


@pytest.fixture(autouse=True)
def _clean_presence():
    svc._SEEN.clear()
    svc._LAST_SWEEP = None
    yield
    svc._SEEN.clear()
    svc._LAST_SWEEP = None


async def _row(client, cid: int, key: str, ability: str | None = None) -> dict:
    r = await _take(client, cid, f"2024_{key}", ability)
    assert r.status_code == 201, r.text
    return next(a for a in _feat_rows(r.json(), f"2024_{key}") if a["feat_status"] in ("incomplete", "active"))


async def test_heavy_armor_master_is_offered_not_forced(client):
    ch = await _char(client, "fighter", 4, **STATS)
    cid = ch["id"]
    await _row(client, cid, "heavy_armor_master", "strength")
    await _armor(client, cid, "heavy")
    hp = (await _full(client, cid))["current_hit_points"]
    assert HAM in await _roll_keys(client, cid, "damage_taken", damage_type="slashing")
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "bludgeoning"})
    assert r.json()["current_hit_points"] == hp - 10  # caduta: nessuna riduzione senza la scelta
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": hp})
    r = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "slashing", "options": [HAM]})
    assert r.status_code == 200, r.text
    assert r.json()["current_hit_points"] == hp - 8


async def test_interception_feat_answers_ally_damage(client, test_session_factory):
    sid, hero = await seed_session(test_session_factory)
    as_user(11)
    paladin = await _char(client, "paladin", 4, **STATS)
    assert (await _take(client, paladin["id"], "2024_fs_interception")).status_code == 201
    await _item(client, paladin["id"], "Spada", damage_dice="1d8", weapon_type="melee", properties=[], equip="main_hand")
    await _seat(test_session_factory, sid, 11, paladin["id"], "Paladino")
    await _poll(client, paladin["id"], 11)
    out = await _open(client, hero)
    assert ("feat.2024_fs_interception" in {w["feature_key"] for w in out["waiting"]}), out


async def test_keen_mind_refuses_a_skill_with_expertise(client):
    ch = await _char(client, "wizard", 4, **STATS)
    await client.patch(f"/characters/{ch['id']}/skills", json={"skills": {"arcana": "expert"}})
    row = await _row(client, ch["id"], "keen_mind", "intelligence")
    r = await _complete(client, ch["id"], row["id"], {"skill": "arcana"})
    assert r.status_code == 422 and "feat_options_invalid" in r.text


async def test_import_drops_feat_options_that_break_the_feat_rules(client):
    ch = await _char(client, "fighter", 19, **STATS)
    cid = ch["id"]
    row = await _row(client, cid, "boon_energy_resistance", "constitution")
    assert (await _complete(client, cid, row["id"], {"damage_types": ["fire", "cold"]})).status_code == 200
    data = (await client.get(f"/characters/{cid}/export")).json()
    ab = next(a for a in data["abilities"] if a.get("feature_key") == "feat.2024_boon_energy_resistance")
    ab["options"] = {**ab["options"], "damage_types": ["fire", "cold", "acid", "poison", "psychic", "radiant"]}
    r = await client.post("/characters/import", json=data)
    assert r.status_code == 201, r.text
    assert _feat_rows(r.json(), "2024_boon_energy_resistance")[0]["feat_status"] == "incomplete"
    assert "acid" not in r.json()["computed"]["resistances"]


async def test_removing_boon_of_skill_takes_back_the_granted_skills(client):
    ch = await _char(client, "fighter", 19, **STATS)
    cid = ch["id"]
    await client.patch(f"/characters/{cid}/skills", json={"skills": {"athletics": True}})
    row = await _row(client, cid, "boon_skill", "wisdom")
    out = (await _complete(client, cid, row["id"], {"expertise": "athletics"})).json()
    assert out["skills"]["arcana"] and out["skills"]["athletics"] == "expert"
    r = await client.delete(f"/characters/{cid}/feats/{row['id']}")
    assert r.status_code == 200, r.text
    skills = r.json()["skills"]
    assert not skills.get("arcana") and skills.get("athletics") is True


async def test_class_choice_skips_a_style_taken_as_feat(client):
    ch = await _char(client, "fighter", 4, **STATS)
    r = await _take(client, ch["id"], "2024_fs_archery")
    choice = next(c for c in r.json()["pending_choices"] if c.get("group") == "fighting_style")
    assert "archery" not in [o["key"] for o in choice["options"]]


async def test_2024_feat_on_a_2014_character_does_nothing(client, test_session_factory):
    from core.db.models import Character
    ch = await _char(client, "fighter", 4, **STATS)
    before = ch["computed"]["speed"]
    await _row(client, ch["id"], "speedy", "dexterity")
    async with test_session_factory() as s:
        (await s.get(Character, ch["id"])).rules_edition = "2014"
        await s.commit()
    out = await _full(client, ch["id"])
    assert out["computed"]["speed"] == before
    assert _feat_rows(out, "2024_speedy")[0]["feat_status"] == "other_edition"


async def test_removing_keen_mind_keeps_the_skill(client):
    ch = await _char(client, "wizard", 4, **STATS)
    row = await _row(client, ch["id"], "keen_mind", "intelligence")
    await _complete(client, ch["id"], row["id"], {"skill": "nature"})
    r = await client.delete(f"/characters/{ch['id']}/feats/{row['id']}")
    assert r.json()["skills"]["nature"] is True


async def test_removing_moderately_armored_keeps_shields_from_lightly_armored(client):
    ch = await _char(client, "wizard", 4, **STATS)
    await _row(client, ch["id"], "lightly_armored", "strength")
    mod = await _row(client, ch["id"], "moderately_armored", "strength")
    r = await client.delete(f"/characters/{ch['id']}/feats/{mod['id']}")
    armor = [a.lower() for a in r.json()["general_proficiencies"]["armor"]]
    assert any("scudi" in a for a in armor) and not any("medie" in a for a in armor)
