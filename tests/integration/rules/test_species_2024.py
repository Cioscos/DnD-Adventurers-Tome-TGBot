"""Specie 2024 come sorgente di privilegi del motore (Task 1: registro e filtri)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.rules.catalog import active_features
from core.rules.catalog.species_2024 import SPECIES_TRAITS, owned_species, trait


def _char(edition: str, species_key: str | None, level: int = 3, options: dict | None = None):
    return SimpleNamespace(rules_edition=edition, species_key=species_key, species_options=options,
                           classes=[SimpleNamespace(level=level)], abilities=[])


def test_owned_species_empty_without_key_and_for_2014():
    assert owned_species(_char("2024", None)) == []
    assert owned_species(_char("2014", "2024_dwarf")) == []
    assert owned_species(_char("2024", "2024_sconosciuta")) == []


def test_owned_species_filters_level_and_lineage(monkeypatch):
    monkeypatch.setitem(SPECIES_TRAITS, "2024_test", (
        trait("test", "base", 1, "T", ("Base", "Base"), ("a", "a")),
        trait("test", "late", 5, "T", ("Tardo", "Late"), ("b", "b")),
        trait("test", "drow", 1, "T", ("Drow", "Drow"), ("c", "c"), option_group="lineage", option_key="drow"),
        trait("test", "elf", 1, "T", ("Elfo", "Elf"), ("d", "d"), option_group="lineage", option_key="high"),
    ))
    char = _char("2024", "2024_test", 3, {"lineage": "drow"})
    owned = owned_species(char)
    assert [s.key for s, _ in owned] == ["species.2024_test_base", "species.2024_test_drow"]
    assert owned[0][1].class_name == "species" and owned[0][1].level == 3 and owned[0][1].ability is None
    assert [s.key for s, _ in active_features(char)] == [s.key for s, _ in owned]


# --- Task 2: righe dei tratti dal sync ---------------------------------------------------------------------------
from sqlalchemy import select  # noqa: E402

from api.services.character_load import get_owned_full  # noqa: E402
from core.db.models import Ability, Character  # noqa: E402
from core.rules.feature_sync import sync_cataloged_features  # noqa: E402
from core.rules.types import Uses  # noqa: E402
from tests.integration.conftest import TEST_USER_ID  # noqa: E402


@pytest.fixture
def registry(monkeypatch):
    monkeypatch.setitem(SPECIES_TRAITS, "2024_test", (
        trait("test", "base", 1, "T", ("Base", "Base"), ("a", "a"), uses=Uses(proficiency=True), restoration="long_rest"),
        trait("test", "late", 5, "T", ("Tardo", "Late"), ("b", "b")),
        trait("test", "text", 1, "T", ("Testo", "Text"), ("c", "c"), no_row=True),
    ))
    monkeypatch.setitem(SPECIES_TRAITS, "2024_other", (trait("other", "x", 1, "T", ("X", "X"), ("x", "x")),))


async def _hero(client, level=3, edition="2024") -> tuple[int, int]:
    r = await client.post("/characters", json={"name": "Specie", "rules_edition": edition,
                                               "initial_class": {"class_name": "fighter", "level": level}})
    assert r.status_code == 201, r.text
    return r.json()["id"], r.json()["classes"][0]["id"]


async def _sync(factory, cid, **fields) -> None:
    async with factory() as s:
        char = await get_owned_full(cid, TEST_USER_ID, s)
        for k, v in fields.items():
            setattr(char, k, v)
        await sync_cataloged_features(s, char)
        await s.commit()


async def _rows(factory, cid) -> dict[str, Ability]:
    async with factory() as s:
        rows = (await s.execute(select(Ability).where(Ability.character_id == cid,
                                                     Ability.feature_key.like("species.%")))).scalars().all()
        return {a.feature_key: a for a in rows}


async def test_species_rows_created_and_scaled(client, test_session_factory, registry):
    cid, class_id = await _hero(client, 3)
    await _sync(test_session_factory, cid, species_key="2024_test")
    rows = await _rows(test_session_factory, cid)
    assert set(rows) == {"species.2024_test_base"}  # `late` è di livello 5, `text` non ha riga
    base = rows["species.2024_test_base"]
    assert (base.max_uses, base.uses, base.restoration_type.value) == (2, 2, "long_rest")
    assert (base.is_class_feature, base.source_class_id, base.name, base.description) == (True, None, "Base", "a")

    r = await client.patch(f"/characters/{cid}/classes/{class_id}", json={"level": 5, "hp_rolls": [5, 5]})
    assert r.status_code == 200, r.text
    rows = await _rows(test_session_factory, cid)
    assert set(rows) == {"species.2024_test_base", "species.2024_test_late"}
    assert rows["species.2024_test_base"].max_uses == 3  # competenza 3 al livello 5


async def test_species_rows_archived_on_change_keep_spent(client, test_session_factory, registry):
    cid, _ = await _hero(client, 3)
    await _sync(test_session_factory, cid, species_key="2024_test")
    async with test_session_factory() as s:
        (await s.execute(select(Ability).where(Ability.feature_key == "species.2024_test_base"))).scalar_one().uses = 1
        await s.commit()

    await _sync(test_session_factory, cid, species_key="2024_other")
    assert set(await _rows(test_session_factory, cid)) == {"species.2024_other_x"}
    async with test_session_factory() as s:
        assert (await s.get(Character, cid)).settings["archived_features"]["species.2024_test_base"] == {"spent": 1}

    await _sync(test_session_factory, cid, species_key="2024_test")
    rows = await _rows(test_session_factory, cid)
    assert set(rows) == {"species.2024_test_base"}
    assert (rows["species.2024_test_base"].max_uses, rows["species.2024_test_base"].uses) == (2, 1)

    await _sync(test_session_factory, cid, rules_edition="2014")  # tornato al 2014: nessun tratto, usi spesi in archivio
    assert await _rows(test_session_factory, cid) == {}


async def test_existing_2024_without_species_untouched(client, test_session_factory, registry):
    cid, _ = await _hero(client, 3)
    async with test_session_factory() as s:
        char = await s.get(Character, cid)
        char.settings = {**(char.settings or {}), "senses": [{"name": "darkvision", "range": 60}]}
        s.add(Ability(character_id=cid, name="Scurovisione", description="Vedi al buio", is_passive=True))
        await s.commit()

    async def snapshot():
        async with test_session_factory() as s:
            char = await s.get(Character, cid)
            names = (await s.execute(select(Ability.name, Ability.feature_key).where(Ability.character_id == cid))).all()
            return sorted(names, key=str), char.speed, char.settings

    before = await snapshot()
    await _sync(test_session_factory, cid)
    assert await snapshot() == before


async def test_species_rows_survive_class_removal(client, test_session_factory, registry):
    """R3: `source_class_id` nullo, quindi il cascade della FK sulla classe non le tocca e il sync non le duplica."""
    cid, class_id = await _hero(client, 3)
    r = await client.post(f"/characters/{cid}/classes", json={"class_name": "wizard", "level": 1})
    assert r.status_code in (200, 201), r.text
    await _sync(test_session_factory, cid, species_key="2024_test")
    first = (await _rows(test_session_factory, cid))["species.2024_test_base"].id

    r = await client.delete(f"/characters/{cid}/classes/{class_id}")
    assert r.status_code == 200, r.text
    rows = await _rows(test_session_factory, cid)
    assert [a.id for a in rows.values()] == [first]  # la stessa riga, una sola
