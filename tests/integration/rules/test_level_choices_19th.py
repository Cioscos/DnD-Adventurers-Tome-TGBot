"""Il 19° livello (ASI nel 2014, Dono Epico nel 2024): lo scambio scatta solo su un vero cambio di edizione (Task 31, C2)."""
from __future__ import annotations

from api.services.catalog_migration import migrate_catalog
from core.db.models import Character

BODY = {"name": "Guerriero", "initial_class": {"class_name": "fighter", "level": 20}}


def _at_19(full: dict) -> list[tuple[str, int]]:
    return sorted((c["kind"], c["level"]) for c in full["pending_choices"] if c["level"] == 19)


async def _wipe_choices(factory, cid: int) -> None:
    """Il personaggio di prima dei segni: nessuna scelta in sospeso e nessun `asi:19` fra le risolte."""
    async with factory() as s:
        char = await s.get(Character, cid)
        char.pending_choices = []
        char.settings = {k: v for k, v in (char.settings or {}).items() if k != "resolved_choices"}
        await s.commit()


async def test_an_imported_2014_character_at_level_20_gets_no_19th_choice(client, monkeypatch):
    from tests.integration.rules.test_2014_monk import _import_fixture
    _import_fixture(monkeypatch, "barbarian20_2024.json")
    r = await client.post("/characters/import/ddb", json={"url": "https://www.dndbeyond.com/characters/1", "rules_edition": "2014"})
    assert r.status_code == 201, r.text
    assert _at_19(r.json()["character"]) == []
    cid = r.json()["character"]["id"]  # e un PATCH di un punteggio (un sync) non lo crea
    assert (await client.patch(f"/characters/{cid}/ability_scores/strength", json={"value": 20})).status_code == 200
    assert _at_19((await client.get(f"/characters/{cid}")).json()) == []


async def test_an_existing_2014_character_without_the_mark_gets_no_19th_choice_from_a_sync_or_the_migration(client, test_session_factory):
    cid = (await client.post("/characters", json=BODY)).json()["id"]
    await _wipe_choices(test_session_factory, cid)
    assert (await client.patch(f"/characters/{cid}/ability_scores/strength", json={"value": 14})).status_code == 200
    assert _at_19((await client.get(f"/characters/{cid}")).json()) == []
    await _wipe_choices(test_session_factory, cid)
    await migrate_catalog(test_session_factory)
    assert _at_19((await client.get(f"/characters/{cid}")).json()) == []


async def test_a_2024_character_swaps_to_the_asi_and_back_only_on_the_edition_change(client):
    cid = (await client.post("/characters", json=BODY)).json()["id"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    assert _at_19((await client.get(f"/characters/{cid}")).json()) == [("epic_boon", 19)]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2014"})).status_code == 200
    assert _at_19((await client.get(f"/characters/{cid}")).json()) == [("asi", 19)]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    assert _at_19((await client.get(f"/characters/{cid}")).json()) == [("epic_boon", 19)]
