"""Prendere un talento fuori dalle scelte di livello, completarne le scelte e rimuoverlo (PR 1 talenti, Task 6)."""
from __future__ import annotations

from tests.integration.rules.test_2014_bard import _ability, _full, _spells
from tests.integration.test_rules_choices import _resolve

SCORES = {"strength": 10, "dexterity": 14, "constitution": 12, "intelligence": 10, "wisdom": 16, "charisma": 12}


async def _hero(client, level=1, charisma=12) -> int:
    r = await client.post("/characters", json={
        "name": "Talenti", "rules_edition": "2024", "ability_scores": {**SCORES, "charisma": charisma},
        "initial_class": {"class_name": "fighter", "level": level}})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _take(client, cid, key, ability=None):
    return await client.post(f"/characters/{cid}/feats", json={"feat_key": key, "ability": ability})


def _feat_rows(body, key):
    return [a for a in body["abilities"] if a["feature_key"] == f"feat.{key}"]


async def _complete(client, cid, ability_id, options, spells=()):
    return await client.put(f"/characters/{cid}/feats/{ability_id}/options",
                            json={"options": options, "spells": list(spells)})


def _spell(name, level, index):
    return {"name": name, "level": level, "srd_index": index, "casting_time": "1 azione"}


async def test_add_general_feat_manually_applies_plus_one(client):
    cid = await _hero(client, charisma=13)
    r = await _take(client, cid, "2024_actor", "charisma")
    assert r.status_code == 201, r.text
    assert next(s for s in r.json()["ability_scores"] if s["name"] == "charisma")["value"] == 14
    low = await _hero(client, charisma=12)
    r = await _take(client, low, "2024_actor", "charisma")
    assert r.status_code == 422 and "feat_prerequisite_ability" in r.text


async def test_origin_feat_in_level_choice_2024(client):
    cid = await _hero(client, 1)
    await client.patch(f"/characters/{cid}/xp", json={"set": 2700})
    body = await _full(client, cid)
    r = await _resolve(client, body, "asi", {"kind": "feat", "feat_key": "2024_alert"})
    assert r.status_code == 200, r.text
    assert _feat_rows(r.json(), "2024_alert")


async def test_skilled_complete_grants_skills_and_tools(client):
    cid = await _hero(client)
    body = (await _take(client, cid, "2024_skilled")).json()
    row = _feat_rows(body, "2024_skilled")[0]
    assert row["feat_status"] == "incomplete"
    r = await _complete(client, cid, row["id"], {"picks": ["stealth", "arcana", "tool:Arnesi da scasso"]})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["skills"]["stealth"] and out["skills"]["arcana"]
    assert "Arnesi da scasso" in out["general_proficiencies"]["tools"]
    assert _feat_rows(out, "2024_skilled")[0]["feat_status"] == "active"
    bad = (await _take(client, cid, "2024_skilled")).json()
    row2 = next(a for a in _feat_rows(bad, "2024_skilled") if a["feat_status"] == "incomplete")
    r = await _complete(client, cid, row2["id"], {"picks": ["stealth", "stealth", "arcana"]})
    assert r.status_code == 422


async def test_skilled_repeatable_and_alert_not(client):
    cid = await _hero(client)
    assert (await _take(client, cid, "2024_skilled")).status_code == 201
    assert (await _take(client, cid, "2024_skilled")).status_code == 201
    assert (await _take(client, cid, "2024_alert")).status_code == 201
    r = await _take(client, cid, "2024_alert")
    assert r.status_code == 422 and "feat_already_taken" in r.text


async def test_magic_initiate_spells_free_cast_and_dc(client):
    cid = await _hero(client, 1)
    row = _feat_rows((await _take(client, cid, "2024_magic_initiate")).json(), "2024_magic_initiate")[0]
    r = await _complete(client, cid, row["id"], {"list": "wizard", "ability": "wisdom"},
                        [_spell("Luce", 0, "light"), _spell("Mano Magica", 0, "mage-hand"),
                         _spell("Charme su Persone", 1, "charm-person")])
    assert r.status_code == 200, r.text
    spells = await _spells(client, cid)
    assert {"Luce", "Mano Magica", "Charme su Persone"} <= set(spells)
    assert all(spells[n]["always_prepared"] for n in ("Luce", "Mano Magica", "Charme su Persone"))
    charm = spells["Charme su Persone"]
    assert charm["pact_cast"]["kind"] == "arcanum" and charm["pact_cast"]["uses_left"] == 1
    assert charm["save_dc"] == 8 + 2 + 3  # competenza + Saggezza 16
    r = await client.post(f"/characters/{cid}/spells/{charm['id']}/use", json={"free_cast": True})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, "feat.2024_magic_initiate"))["uses"] == 0
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert r.status_code == 200, r.text
    assert (await _ability(client, cid, "feat.2024_magic_initiate"))["uses"] == 1


async def test_magic_initiate_second_needs_other_list(client):
    cid = await _hero(client)
    first = _feat_rows((await _take(client, cid, "2024_magic_initiate")).json(), "2024_magic_initiate")[0]
    spells = [_spell("Luce", 0, "light"), _spell("Mano Magica", 0, "mage-hand"), _spell("Sonno", 1, "sleep")]
    assert (await _complete(client, cid, first["id"], {"list": "wizard", "ability": "intelligence"}, spells)).status_code == 200
    body = (await _take(client, cid, "2024_magic_initiate")).json()
    second = next(a for a in _feat_rows(body, "2024_magic_initiate") if a["feat_status"] == "incomplete")
    r = await _complete(client, cid, second["id"], {"list": "wizard", "ability": "intelligence"}, spells)
    assert r.status_code == 422 and "feat_list_taken" in r.text


async def test_remove_magic_initiate_unprepares_spells(client):
    cid = await _hero(client)
    row = _feat_rows((await _take(client, cid, "2024_magic_initiate")).json(), "2024_magic_initiate")[0]
    await _complete(client, cid, row["id"], {"list": "cleric", "ability": "wisdom"},
                    [_spell("Luce", 0, "light"), _spell("Taumaturgia", 0, "thaumaturgy"), _spell("Benedizione", 1, "bless")])
    r = await client.delete(f"/characters/{cid}/feats/{row['id']}")
    assert r.status_code == 200, r.text
    spells = await _spells(client, cid)
    assert "Benedizione" in spells and not spells["Benedizione"]["always_prepared"]


async def test_remove_one_instance_of_a_repeatable_feat(client):
    cid = await _hero(client)
    await _take(client, cid, "2024_skilled")
    body = (await _take(client, cid, "2024_skilled")).json()
    first = _feat_rows(body, "2024_skilled")[0]
    r = await client.delete(f"/characters/{cid}/feats/{first['id']}")
    assert r.status_code == 200 and len(_feat_rows(r.json(), "2024_skilled")) == 1


async def test_options_once(client):
    cid = await _hero(client)
    row = _feat_rows((await _take(client, cid, "2024_skilled")).json(), "2024_skilled")[0]
    assert (await _complete(client, cid, row["id"], {"picks": ["stealth", "arcana", "history"]})).status_code == 200
    r = await _complete(client, cid, row["id"], {"picks": ["nature", "arcana", "history"]})
    assert r.status_code == 409
