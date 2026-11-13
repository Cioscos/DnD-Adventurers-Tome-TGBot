"""Talenti 2014 con scelte (PR 3 talenti, Task 4)."""
from __future__ import annotations

from tests.integration.rules.test_2014_bard import _full, _spells
from tests.integration.rules.test_2014_barbarian import _weapon
from tests.integration.rules.test_feats_2014_selection import _char14
from tests.integration.rules.test_feats_take_complete import _complete, _feat_rows, _spell, _take


async def _row(client, cid: int, key: str, ability: str | None = None) -> dict:
    r = await _take(client, cid, key, ability)
    assert r.status_code == 201, r.text
    return next(a for a in _feat_rows(r.json(), key) if a["feat_status"] == "incomplete")


async def test_skilled_2014_picks(client):
    ch = await _char14(client, "fighter")
    row = await _row(client, ch["id"], "skilled")
    r = await _complete(client, ch["id"], row["id"], {"picks": ["arcana", "history", "tool:Arnesi da scasso"]})
    assert r.status_code == 200, r.text
    assert r.json()["skills"]["arcana"] and r.json()["skills"]["history"]


async def test_elemental_adept_2014_types_differ(client):
    ch = await _char14(client, "wizard")
    first = await _row(client, ch["id"], "elemental_adept")
    assert (await _complete(client, ch["id"], first["id"], {"damage_type": "fire"})).status_code == 200
    second = await _row(client, ch["id"], "elemental_adept")
    r = await _complete(client, ch["id"], second["id"], {"damage_type": "fire"})
    assert r.status_code == 422 and "feat_type_taken" in r.text


async def test_martial_adept_maneuvers_and_die(client):
    ch = await _char14(client, "fighter")
    cid = ch["id"]
    row = await _row(client, cid, "martial_adept")
    assert (await _complete(client, cid, row["id"], {"maneuvers": ["trip", "nonsense"]})).status_code == 422
    assert (await _complete(client, cid, row["id"], {"maneuvers": ["trip", "trip"]})).status_code == 422
    r = await _complete(client, cid, row["id"], {"maneuvers": ["trip", "parry"]})
    assert r.status_code == 200, r.text
    done = _feat_rows(r.json(), "martial_adept")[0]
    assert (done["max_uses"], done["restoration_type"]) == (1, "short_rest")
    used = await client.post(f"/characters/{cid}/features/feat.martial_adept/use", json={})
    assert used.status_code == 200, used.text
    assert _feat_rows(await _full(client, cid), "martial_adept")[0]["uses"] == 0


async def test_linguist_adds_three_languages(client):
    ch = await _char14(client, "wizard")
    row = await _row(client, ch["id"], "linguist", "intelligence")
    assert (await _complete(client, ch["id"], row["id"], {"languages": ["Elfico", "Nanico"]})).status_code == 422
    r = await _complete(client, ch["id"], row["id"], {"languages": ["Elfico", "Nanico", "Draconico"]})
    assert r.status_code == 200, r.text
    assert {"Elfico", "Nanico", "Draconico"} <= set(r.json()["languages"])


async def test_weapon_master_2014_grants_four_weapons(client):
    ch = await _char14(client, "wizard")
    cid = ch["id"]
    row = await _row(client, cid, "weapon_master", "dexterity")
    assert (await _complete(client, cid, row["id"], {"weapons": ["rapier", "longsword", "rapier", "whip"]})).status_code == 422
    r = await _complete(client, cid, row["id"], {"weapons": ["rapier", "longsword", "whip", "longbow"]})
    assert r.status_code == 200, r.text
    wid = await _weapon(client, cid, "Stocco", damage_dice="1d8", weapon_category="martial", properties=["finesse"])
    hit = await client.post(f"/characters/{cid}/items/{wid}/attack", json={"die": 10, "confirm_extra_attack": True})
    pb = r.json()["proficiency_bonus"]
    dex = 2  # Destrezza 14 -> 15: modificatore +2
    assert hit.json()["to_hit_total"] == 10 + dex + pb


async def test_magic_initiate_2014_bard_uses_charisma(client):
    ch = await _char14(client, "fighter", charisma=16)
    cid = ch["id"]
    row = await _row(client, cid, "magic_initiate")
    spells = [_spell("Beffa crudele", 0, "vicious-mockery"), _spell("Mano magica", 0, "mage-hand"),
              _spell("Parola guaritrice", 1, "healing-word")]
    assert (await _complete(client, cid, row["id"], {"list": "paladin"}, spells)).status_code == 422
    bad = [*spells[:2], _spell("Dardo incantato", 1, "magic-missile")]
    assert (await _complete(client, cid, row["id"], {"list": "bard"}, bad)).status_code == 422
    r = await _complete(client, cid, row["id"], {"list": "bard"}, spells)
    assert r.status_code == 200, r.text
    assert _feat_rows(r.json(), "magic_initiate")[0]["options"]["ability"] == "charisma"
    mockery = (await _spells(client, cid))["Beffa crudele"]
    assert mockery["save_dc"] == 8 + r.json()["proficiency_bonus"] + 3


async def test_spell_sniper_needs_an_attack_cantrip(client):
    ch = await _char14(client, "wizard")
    row = await _row(client, ch["id"], "spell_sniper")
    light = [_spell("Luce", 0, "light")]
    assert (await _complete(client, ch["id"], row["id"], {"list": "wizard"}, light)).status_code == 422
    r = await _complete(client, ch["id"], row["id"], {"list": "wizard"}, [_spell("Dardo di fuoco", 0, "fire-bolt")])
    assert r.status_code == 200, r.text
    assert "Dardo di fuoco" in await _spells(client, ch["id"])


async def test_ritual_caster_2014_two_rituals_of_the_list(client):
    ch = await _char14(client, "fighter", intelligence=13)
    cid = ch["id"]
    row = await _row(client, cid, "ritual_caster")
    three = [_spell("Individuazione del magico", 1, "detect-magic"), _spell("Identificare", 1, "identify"),
             _spell("Allarme", 1, "alarm")]
    assert (await _complete(client, cid, row["id"], {"list": "wizard"}, three)).status_code == 422
    assert (await _complete(client, cid, row["id"], {"list": "bard"}, [three[0], three[2]])).status_code == 422  # Allarme non è da bardo
    r = await _complete(client, cid, row["id"], {"list": "wizard"}, three[:2])
    assert r.status_code == 200, r.text
    assert _feat_rows(r.json(), "ritual_caster")[0]["options"]["ability"] == "intelligence"


async def test_import_drops_bad_2014_options(client):
    ch = await _char14(client, "wizard")
    cid = ch["id"]
    row = await _row(client, cid, "linguist", "intelligence")
    assert (await _complete(client, cid, row["id"], {"languages": ["Elfico", "Nanico", "Draconico"]})).status_code == 200
    data = (await client.get(f"/characters/{cid}/export")).json()
    ab = next(a for a in data["abilities"] if a.get("feature_key") == "feat.linguist")
    ab["options"] = {**ab["options"], "languages": ["A", "B", "C", "D", "E"]}
    r = await client.post("/characters/import", json=data)
    assert r.status_code == 201, r.text
    assert _feat_rows(r.json(), "linguist")[0]["feat_status"] == "incomplete"
