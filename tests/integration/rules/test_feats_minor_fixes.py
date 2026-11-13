"""Problemi minori della revisione finale della PR 1 talenti."""
from __future__ import annotations

from sqlalchemy import select

from api.services.catalog_migration import migrate_catalog
from core.db.models import Ability, AppMeta, RestorationType, Spell
from tests.integration.rules.test_2014_bard import _full, _spells
from tests.integration.rules.test_feats_2014_engine import _l4
from tests.integration.rules.test_feats_take_complete import _complete, _feat_rows, _hero, _spell, _take

MI = "2024_magic_initiate"
CLERIC = [_spell("Guida", 0, "guidance"), _spell("Taumaturgia", 0, "thaumaturgy"), _spell("Cura Ferite", 1, "cure-wounds")]
DRUID = [_spell("Guida", 0, "guidance"), _spell("Druidismo", 0, "druidcraft"), _spell("Cura Ferite", 1, "cure-wounds")]


async def _mi(client, cid, chosen: str, spells) -> dict:
    body = (await _take(client, cid, MI)).json()
    row = next(a for a in _feat_rows(body, MI) if a["feat_status"] == "incomplete")
    r = await _complete(client, cid, row["id"], {"list": chosen, "ability": "wisdom"}, spells)
    assert r.status_code == 200, r.text
    return row


async def test_import_drops_malformed_feat_options(client):
    cid = await _hero(client)
    await _mi(client, cid, "cleric", CLERIC)
    data = (await client.get(f"/characters/{cid}/export")).json()
    ab = next(a for a in data["abilities"] if a.get("feature_key") == f"feat.{MI}")
    ab["options"] = {**ab["options"], "spell": 5}
    r = await client.post("/characters/import", json=data)
    assert r.status_code == 201, r.text
    assert _feat_rows(r.json(), MI)[0]["feat_status"] == "incomplete"
    assert (await client.get(f"/characters/{r.json()['id']}/spells")).status_code == 200


async def test_remove_feat_keeps_spell_granted_by_another_feat(client):
    cid = await _hero(client)
    first = await _mi(client, cid, "cleric", CLERIC)
    await _mi(client, cid, "druid", DRUID)
    assert (await client.delete(f"/characters/{cid}/feats/{first['id']}")).status_code == 200
    spells = await _spells(client, cid)
    assert spells["Cura Ferite"]["always_prepared"] and spells["Guida"]["always_prepared"]
    assert not spells["Taumaturgia"]["always_prepared"]


async def test_remove_feat_keeps_spell_already_always_prepared(client, test_session_factory):
    cid = await _hero(client)
    async with test_session_factory() as s:
        s.add(Spell(character_id=cid, name="Cura Ferite", level=1, srd_index="cure-wounds",
                    always_prepared=True, is_prepared=True))
        await s.commit()
    row = await _mi(client, cid, "cleric", CLERIC)
    assert (await client.delete(f"/characters/{cid}/feats/{row['id']}")).status_code == 200
    assert (await _spells(client, cid))["Cura Ferite"]["always_prepared"]


async def test_magic_initiate_spells_must_be_on_the_list(client):
    cid = await _hero(client)
    row = _feat_rows((await _take(client, cid, MI)).json(), MI)[0]
    off_list = [_spell("Guida", 0, "guidance"), _spell("Taumaturgia", 0, "thaumaturgy"), _spell("Sonno", 1, "sleep")]
    r = await _complete(client, cid, row["id"], {"list": "cleric", "ability": "wisdom"}, off_list)
    assert r.status_code == 422, r.text
    wrong_level = [_spell("Guida", 0, "guidance"), _spell("Benedizione", 0, "bless"), _spell("Cura Ferite", 1, "cure-wounds")]
    r = await _complete(client, cid, row["id"], {"list": "cleric", "ability": "wisdom"}, wrong_level)
    assert r.status_code == 422, r.text
    no_index = [_spell("Guida", 0, "guidance"), _spell("Taumaturgia", 0, None), _spell("Cura Ferite", 1, "cure-wounds")]
    r = await _complete(client, cid, row["id"], {"list": "cleric", "ability": "wisdom"}, no_index)
    assert r.status_code == 422, r.text


async def test_free_cast_uses_the_row_with_uses_left(client):
    cid = await _hero(client)
    await _mi(client, cid, "cleric", CLERIC)
    await _mi(client, cid, "druid", DRUID)
    cure = (await _spells(client, cid))["Cura Ferite"]
    r = await client.post(f"/characters/{cid}/spells/{cure['id']}/use", json={"free_cast": True})
    assert r.status_code == 200, (r.text, cure["pact_cast"])
    again = (await _spells(client, cid))["Cura Ferite"]
    assert again["pact_cast"]["uses_left"] == 1
    assert (await client.post(f"/characters/{cid}/turn/new")).status_code == 200  # nuovo turno: l'azione torna
    r = await client.post(f"/characters/{cid}/spells/{cure['id']}/use", json={"free_cast": True})
    assert r.status_code == 200, r.text
    rows = _feat_rows(await _full(client, cid), MI)
    assert [a["uses"] for a in rows] == [0, 0]


async def test_migration_renames_old_lucky_row(client, test_session_factory):
    body = await _l4(client)
    cid = body["id"]
    async with test_session_factory() as s:
        s.add(Ability(character_id=cid, name="Punti fortuna", feature_key="feat.lucky", max_uses=3, uses=2,
                      description="3 punti fortuna per riposo lungo per ritirare un d20.",
                      restoration_type=RestorationType.LONG_REST))
        meta = await s.get(AppMeta, "catalog_version")
        if meta is None:
            s.add(AppMeta(key="catalog_version", value="0"))
        else:
            meta.value = "0"
        await s.commit()
    await migrate_catalog(test_session_factory)
    row = next(a for a in (await _full(client, cid))["abilities"] if a["feature_key"] == "feat.lucky")
    assert row["name"] == "Fortunato" and row["description"].startswith("3 punti fortuna per riposo lungo:")
