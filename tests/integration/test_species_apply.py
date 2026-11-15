"""Scelta e cambio della specie 2024 sulla scheda (Task 5): POST /species/preview, PUT /species."""
from __future__ import annotations

from sqlalchemy import select

from api.services.character_load import get_owned_full
from core.db.models import Ability
from tests.integration.conftest import TEST_USER_ID
from tests.integration.rules.test_2014_bard import _full
from tests.integration.rules.test_species_2024 import _hero


async def _set(factory, cid, settings=None, **fields) -> None:
    async with factory() as s:
        char = await get_owned_full(cid, TEST_USER_ID, s)
        for k, v in fields.items():
            setattr(char, k, v)
        if settings is not None:
            char.settings = {**(char.settings or {}), **settings}
        await s.commit()


async def _old_race_hero(client, factory) -> int:
    """Un 2024 creato col vecchio wizard: Nano di collina con velocità, sensi, note e tratti scritti a mano."""
    cid, _ = await _hero(client, 4)
    await _set(factory, cid, race="Nano delle colline", speed=25,
               settings={"senses": [{"type": "darkvision", "range_ft": 60}], "roll_notes": {"save_constitution": "Vantaggio vs veleno"}})
    async with factory() as s:
        s.add(Ability(character_id=cid, name="Scurovisione", description="60 piedi", is_passive=True))
        s.add(Ability(character_id=cid, name="robustezza nanica", is_passive=True))
        s.add(Ability(character_id=cid, name="Il mio tratto", is_passive=True))
        await s.commit()
    return cid


async def _put(client, cid, key, options=None):
    return await client.put(f"/characters/{cid}/species", json={"key": key, "options": options or {}})


async def _preview(client, cid, key, options=None):
    return await client.post(f"/characters/{cid}/species/preview", json={"key": key, "options": options or {}})


def _row(full, name=None, key=None):
    return [a for a in full["abilities"] if (name is None or a["name"] == name) and (key is None or a["feature_key"] == key)]


async def test_preview_lists_changes_without_writing(client, test_session_factory):
    cid = await _old_race_hero(client, test_session_factory)
    before = await _full(client, cid)
    r = await _preview(client, cid, "2024_dwarf")
    assert r.status_code == 200, r.text
    assert set(r.json()["changes"]) == {"speed_reset", "senses_removed", "roll_notes_removed", "traits_archived:2",
                                        "hp_check", "scores_check"}
    after = await _full(client, cid)
    assert after["abilities"] == before["abilities"] and after["speed"] == 25 and after["race"] == "Nano delle colline"
    assert after["species_key"] is None


async def test_apply_cleans_old_race_values(client, test_session_factory):
    cid = await _old_race_hero(client, test_session_factory)
    r = await _put(client, cid, "2024_dwarf")
    assert r.status_code == 200, r.text
    full = r.json()
    assert (full["speed"], full["race"], full["species_key"]) == (30, "Nano", "2024_dwarf")
    assert "senses" not in full["settings"] and "roll_notes" not in full["settings"]
    assert [a["name"] for a in full["abilities"] if not a["feature_key"]] == ["Il mio tratto"]
    assert [a["feature_key"] for a in full["abilities"] if a["name"] == "Scurovisione"] == ["species.2024_dwarf_darkvision"]
    assert [s for s in full["computed"]["senses"] if s["type"] == "darkvision"] == [{"type": "darkvision", "range_ft": 120}]


async def test_apply_rejects_missing_choice_422_and_writes_nothing(client, test_session_factory):
    cid = await _old_race_hero(client, test_session_factory)
    before = await _full(client, cid)
    for key, options in (("2024_elf", {"lineage": "drow", "spell_ability": "wisdom"}),  # manca skill
                         ("2024_elf", {"lineage": "nessuno", "spell_ability": "wisdom", "skill": "perception"}),
                         ("2024_dwarf", {"_feat_ability_id": "1"}),
                         ("2024_human", {"size": "medium", "skill": "athletics", "origin_feat": "2024_actor"})):
        r = await _put(client, cid, key, options)
        assert (r.status_code, r.json()["detail"]) == (422, "species_options_invalid"), (key, options, r.text)
    r = await _put(client, cid, "2024_inesistente")
    assert (r.status_code, r.json()["detail"]) == (422, "species_unknown")
    after = await _full(client, cid)
    assert after["abilities"] == before["abilities"] and after["speed"] == 25 and after["species_key"] is None


async def test_apply_rejects_2014_422(client, test_session_factory):
    cid, _ = await _hero(client, 3, "2014")
    for r in (await _put(client, cid, "2024_dwarf"), await _preview(client, cid, "2024_dwarf")):
        assert (r.status_code, r.json()["detail"]) == (422, "species_edition")
    assert (await _full(client, cid))["species_key"] is None


async def test_change_human_to_elf_removes_skill_and_feat(client, test_session_factory):
    cid, _ = await _hero(client, 3)
    r = await _put(client, cid, "2024_human", {"size": "medium", "skill": "athletics", "origin_feat": "2024_alert"})
    assert r.status_code == 200, r.text
    full = r.json()
    assert full["skills"].get("athletics") is True and _row(full, key="feat.2024_alert")
    assert full["race"] == "Umano"

    elf = {"lineage": "high", "spell_ability": "intelligence", "skill": "perception"}
    preview = (await _preview(client, cid, "2024_elf", elf)).json()["changes"]
    assert set(preview) == {"skill_removed:athletics", "feat_removed:2024_alert", "skill_added:perception"}
    r = await _put(client, cid, "2024_elf", elf)
    assert r.status_code == 200, r.text
    full = r.json()
    assert not full["skills"].get("athletics") and full["skills"].get("perception") is True
    assert not _row(full, key="feat.2024_alert")
    assert full["race"] == "Elfo (Elfo alto)"
    assert full["species_options"]["_granted_skill"] == "perception" and "_feat_ability_id" not in full["species_options"]


async def test_lineage_change_keeps_shared_trait_row(client, test_session_factory):
    cid, _ = await _hero(client, 3)
    r = await _put(client, cid, "2024_elf", {"lineage": "drow", "spell_ability": "wisdom", "skill": "insight"})
    assert r.status_code == 200, r.text
    fey = _row(r.json(), key="species.2024_elf_fey_ancestry")[0]["id"]
    assert {"type": "darkvision", "range_ft": 120} in r.json()["computed"]["senses"]
    r = await _put(client, cid, "2024_elf", {"lineage": "high", "spell_ability": "wisdom", "skill": "insight"})
    assert r.status_code == 200, r.text
    full = r.json()
    assert _row(full, key="species.2024_elf_fey_ancestry")[0]["id"] == fey
    assert [s for s in full["computed"]["senses"] if s["type"] == "darkvision"] == [{"type": "darkvision", "range_ft": 60}]
    assert full["skills"].get("insight") is True


async def test_export_import_keeps_species_without_duplicate_rows(client, test_session_factory):
    cid, _ = await _hero(client, 3)
    assert (await _put(client, cid, "2024_dwarf")).status_code == 200
    exported = (await client.get(f"/characters/{cid}/export")).json()
    assert exported["character"]["species_key"] == "2024_dwarf"
    r = await client.post("/characters/import", json=exported)
    assert r.status_code == 201, r.text
    new = r.json()
    assert new["species_key"] == "2024_dwarf"
    keys = [a["feature_key"] for a in new["abilities"] if a["feature_key"].startswith("species.")]
    assert sorted(keys) == sorted(set(keys)) and "species.2024_dwarf_darkvision" in keys
    async with test_session_factory() as s:
        rows = (await s.execute(select(Ability).where(Ability.character_id == new["id"],
                                                     Ability.feature_key.like("species.%")))).scalars().all()
    assert len(rows) == len(set(a.feature_key for a in rows))
