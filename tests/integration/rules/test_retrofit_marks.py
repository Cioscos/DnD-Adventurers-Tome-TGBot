"""Task 21, correzioni comuni (R1, R2 della ri-revisione del Task 20): segno del retrofit e file senza edizione."""
from __future__ import annotations

from dataclasses import replace

from api.services.catalog_migration import migrate_catalog
from tests.integration.rules.test_2014_bard import LORE, _bard, _choice, _full
from tests.integration.rules.test_2014_bard_round2 import _bump
from tests.integration.rules.test_class_mechanisms import KEY, _fighter, _spec
from tests.integration.rules.test_class_mechanisms_round1 import BONUS, _scores


async def test_the_retrofit_mark_tells_the_editions_apart(client, rules_catalog, test_session_factory):  # R1
    rules_catalog(_spec(**BONUS))
    cid = await _fighter(client, 4, strength=10)  # 2014: al 5° il +4, qui non ancora
    assert (await _full(client, cid))["settings"]["retrofit_done"] == ["2014:fighter"]
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    rules_catalog(replace(_spec(level=1, ability_bonus={"strength": 4}, ability_cap=24), edition="2024"))
    await _bump(test_session_factory)  # il catalogo 2024 arriva dopo: per lui il personaggio esisteva già
    assert await migrate_catalog(test_session_factory) >= 1
    full = await _full(client, cid)
    assert (await _scores(client, cid))["strength"] == 10
    assert full["settings"]["feature_ability_bonus"][KEY] == {}
    assert set(full["settings"]["retrofit_done"]) == {"2014:fighter", "2024:fighter"}


async def test_an_old_file_without_edition_goes_through_the_choice_retrofit(client):  # R2
    cid = await _bard(client, 3, LORE)
    exported = (await client.get(f"/characters/{cid}/export")).json()
    exported["character"].pop("rules_edition", None)  # un file di prima delle edizioni
    r = await client.post("/characters/import", json=exported)
    assert r.status_code == 201, r.text
    new = r.json()["id"]
    assert _choice(await _full(client, new), "lore_skills")["retrofit"] is True
    assert _choice(await _full(client, new), "expertise")["retrofit"] is True
    await client.patch(f"/characters/{new}/ability_scores/dexterity", json={"value": 12})  # un sync normale non lo cambia
    assert _choice(await _full(client, new), "lore_skills")["retrofit"] is True
