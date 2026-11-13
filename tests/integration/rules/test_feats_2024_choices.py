"""Talenti generali 2024 con scelte: abilità, tipo di danno, incantesimi, padronanza (PR 2 talenti, Task 3)."""
from __future__ import annotations

from tests.integration.rules.test_2014_bard import _full, _spells
from tests.integration.rules.test_2014_barbarian import _weapon
from tests.integration.rules.test_feats_2024_general import STATS
from tests.integration.rules.test_feats_2024_selection import _char
from tests.integration.rules.test_feats_take_complete import _complete, _feat_rows, _spell, _take


async def _row(client, cid: int, key: str, ability: str | None = None) -> dict:
    r = await _take(client, cid, f"2024_{key}", ability)
    assert r.status_code == 201, r.text
    return next(a for a in _feat_rows(r.json(), f"2024_{key}") if a["feat_status"] == "incomplete")


async def test_keen_mind_proficiency_then_expertise(client):
    ch = await _char(client, "wizard", 4, **STATS)
    row = await _row(client, ch["id"], "keen_mind", "intelligence")
    assert (await _complete(client, ch["id"], row["id"], {"skill": "athletics"})).status_code == 422
    r = await _complete(client, ch["id"], row["id"], {"skill": "nature"})
    assert r.status_code == 200, r.text
    assert r.json()["skills"]["nature"] is True
    other = await _char(client, "wizard", 4, **STATS)
    await client.patch(f"/characters/{other['id']}/skills", json={"skills": {"arcana": True}})
    row = await _row(client, other["id"], "keen_mind", "intelligence")
    r = await _complete(client, other["id"], row["id"], {"skill": "arcana"})
    assert r.json()["skills"]["arcana"] == "expert"


async def test_observant_skills(client):
    ch = await _char(client, "fighter", 4, **STATS)
    row = await _row(client, ch["id"], "observant", "wisdom")
    assert (await _complete(client, ch["id"], row["id"], {"skill": "nature"})).status_code == 422
    assert (await _complete(client, ch["id"], row["id"], {"skill": "perception"})).json()["skills"]["perception"]


async def test_skill_expert(client):
    ch = await _char(client, "fighter", 4, **STATS)
    row = await _row(client, ch["id"], "skill_expert", "strength")
    r = await _complete(client, ch["id"], row["id"], {"skill": "stealth", "expertise": "stealth"})
    assert r.status_code == 200, r.text
    assert r.json()["skills"]["stealth"] == "expert"


async def test_elemental_adept_spell_dice(client):
    ch = await _char(client, "wizard", 4, **STATS)
    cid = ch["id"]
    row = await _row(client, cid, "elemental_adept", "intelligence")
    assert (await _complete(client, cid, row["id"], {"damage_type": "necrotic"})).status_code == 422
    assert (await _complete(client, cid, row["id"], {"damage_type": "fire"})).status_code == 200
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Dardo di fuoco", "level": 0, "damage_dice": "1d10",
                                                             "damage_type": "fire", "attack_save": "ATK"})
    assert r.status_code == 201, r.text
    out = await client.post(f"/characters/{cid}/spells/{r.json()['id']}/roll_damage", json={"main_rolls": [1]})
    assert out.status_code == 200, out.text
    assert out.json()["total"] == 2


async def test_elemental_adept_same_type_twice_refused(client):
    ch = await _char(client, "wizard", 4, **STATS)
    first = await _row(client, ch["id"], "elemental_adept", "intelligence")
    assert (await _complete(client, ch["id"], first["id"], {"damage_type": "cold"})).status_code == 200
    second = await _row(client, ch["id"], "elemental_adept", "intelligence")
    r = await _complete(client, ch["id"], second["id"], {"damage_type": "cold"})
    assert r.status_code == 422 and "feat_type_taken" in r.text


async def test_fey_touched_spells_and_free_casts(client):
    ch = await _char(client, "fighter", 4, **STATS)
    cid = ch["id"]
    row = await _row(client, cid, "fey_touched", "wisdom")
    bad = await _complete(client, cid, row["id"], {}, [_spell("Dardo incantato", 1, "magic-missile")])
    assert bad.status_code == 422
    r = await _complete(client, cid, row["id"], {}, [_spell("Comando", 1, "command")])
    assert r.status_code == 200, r.text
    spells = await _spells(client, cid)
    assert spells["Passo velato"]["always_prepared"] and spells["Comando"]["always_prepared"]
    assert spells["Comando"]["pact_cast"]["uses_left"] == 2
    assert spells["Comando"]["save_dc"] == 8 + 2 + 2  # Saggezza 13 + 1 = 14


async def test_shadow_touched_school(client):
    ch = await _char(client, "fighter", 4, **STATS)
    row = await _row(client, ch["id"], "shadow_touched", "intelligence")
    assert (await _complete(client, ch["id"], row["id"], {}, [_spell("Comando", 1, "command")])).status_code == 422
    r = await _complete(client, ch["id"], row["id"], {}, [_spell("Raggio di infermità", 1, "ray-of-sickness")])
    assert r.status_code == 200, r.text
    assert "Invisibilità" in await _spells(client, ch["id"])


async def test_ritual_caster(client):
    ch = await _char(client, "wizard", 4, **STATS)
    cid = ch["id"]
    row = await _row(client, cid, "ritual_caster", "intelligence")
    one = [_spell("Allarme", 1, "alarm")]
    assert (await _complete(client, cid, row["id"], {}, one)).status_code == 422  # competenza 2: due rituali
    no_ritual = [_spell("Allarme", 1, "alarm"), _spell("Dardo incantato", 1, "magic-missile")]
    assert (await _complete(client, cid, row["id"], {}, no_ritual)).status_code == 422
    r = await _complete(client, cid, row["id"], {}, [_spell("Allarme", 1, "alarm"), _spell("Trova famiglio", 1, "find-familiar")])
    assert r.status_code == 200, r.text
    assert (await _spells(client, cid))["Allarme"]["always_prepared"]


async def test_weapon_master_mastery(client):
    ch = await _char(client, "wizard", 4, **STATS)
    cid = ch["id"]
    row = await _row(client, cid, "weapon_master", "strength")
    assert (await _complete(client, cid, row["id"], {"weapon_mastery": ["laser"]})).status_code == 422
    assert (await _complete(client, cid, row["id"], {"weapon_mastery": ["mace"]})).status_code == 200
    wid = await _weapon(client, cid, "Mazza", base_weapon="mace", damage_dice="1d6")
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": "attack", "item_id": wid})
    assert r.status_code == 200, r.text
    assert "mastery_sap" in [o["key"] for o in r.json()]


async def test_import_keeps_new_feat_options(client):
    ch = await _char(client, "wizard", 4, **STATS)
    row = await _row(client, ch["id"], "elemental_adept", "intelligence")
    assert (await _complete(client, ch["id"], row["id"], {"damage_type": "fire"})).status_code == 200
    data = (await client.get(f"/characters/{ch['id']}/export")).json()
    r = await client.post("/characters/import", json=data)
    assert r.status_code == 201, r.text
    assert _feat_rows(r.json(), "2024_elemental_adept")[0]["feat_status"] == "active"
