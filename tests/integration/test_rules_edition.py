from __future__ import annotations

from core.rules.edition import character_edition


async def _new(client) -> int:
    r = await client.post("/characters", json={"name": "Edi"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


async def test_new_character_defaults_to_2014(client):
    cid = await _new(client)
    assert (await client.get(f"/characters/{cid}")).json()["rules_edition"] == "2014"


async def test_patch_rules_edition(client):
    cid = await _new(client)
    r = await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})
    assert r.status_code == 200 and r.json()["rules_edition"] == "2024"
    assert (await client.get(f"/characters/{cid}")).json()["rules_edition"] == "2024"


async def test_patch_rejects_unknown_edition(client):
    cid = await _new(client)
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2020"})).status_code == 422


async def test_export_import_keeps_edition(client):
    cid = await _new(client)
    await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})
    data = (await client.get(f"/characters/{cid}/export")).json()
    assert data["character"]["rules_edition"] == "2024"
    r = await client.post("/characters/import", json=data)
    assert r.status_code == 201 and r.json()["rules_edition"] == "2024"


async def test_old_export_without_field_imports_as_2014(client):
    d = {"exported_at": "x", "character": {"name": "Vecchio"}}
    r = await client.post("/characters/import", json=d)
    assert r.status_code == 201 and r.json()["rules_edition"] == "2014"


def test_character_edition_falls_back_to_2014():
    class C:
        rules_edition = None
    assert character_edition(C()) == "2014"
    C.rules_edition = "1999"
    assert character_edition(C()) == "2014"
    C.rules_edition = "2024"
    assert character_edition(C()) == "2024"
