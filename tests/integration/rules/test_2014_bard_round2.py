"""Bardo 2014, giro 2: N2, N3, N7, N8 (N5 e N9 sono dell'interfaccia)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.db.models import AppMeta, Character
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user
from tests.integration.rules.test_2014_bard import LORE, _bard, _choice, _full, _roll_keys
from tests.integration.rules.test_2014_bard_inspiration import STATE, _give, _states_of, _table


async def test_the_received_die_is_offered_on_a_death_save(client, test_session_factory):  # N2
    sid, bard, hero = await _table(client, test_session_factory)
    await _give(client, bard, hero)
    as_user(PLAYER_ID)
    assert "bardic_die:add" in await _roll_keys(client, hero, "death_save")


async def test_an_incapacitated_creature_cannot_add_the_die_to_its_armor_class(client, test_session_factory):  # N3
    sid, bard, hero = await _table(client, test_session_factory, level=3, subclass="Collegio del Valore")
    await _give(client, bard, hero)
    as_user(PLAYER_ID)
    await client.patch(f"/characters/{hero}/conditions", json={"conditions": {"stunned": True}})
    r = await client.post(f"/characters/{hero}/bardic-die/ac")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "incapacitated"
    assert len(_states_of(await _full(client, hero))) == 1  # il dado resta
    assert (await client.get(f"/characters/{hero}/turn-state")).json()["turn"]["reaction_used"] is False


async def test_the_ally_list_says_who_already_holds_a_die(client, test_session_factory):  # N8
    sid, bard, hero = await _table(client, test_session_factory, level=10)
    as_user(GM_ID)
    assert [a["die"] for a in (await client.get(f"/characters/{bard}/session-allies")).json()] == [None]
    await _give(client, bard, hero)
    allies = (await client.get(f"/characters/{bard}/session-allies")).json()
    assert [(a["id"], a["die"]) for a in allies] == [(hero, 10)]


# N7: il retrofit vale una volta per classe, non a ogni versione del catalogo

async def _bump(test_session_factory, version="0") -> None:
    async with test_session_factory() as s:
        meta = await s.get(AppMeta, "catalog_version")
        if meta is None:
            s.add(AppMeta(key="catalog_version", value=version))
        else:
            meta.value = version
        await s.commit()


async def _drop_marks(test_session_factory, cid, keep=()) -> None:
    async with test_session_factory() as s:
        char = await s.get(Character, cid)
        char.settings = {**(char.settings or {}), "retrofit_done": list(keep)}
        await s.commit()


async def test_a_class_is_retrofitted_once_not_at_every_catalog_version(client, test_session_factory):
    from api.services.catalog_migration import migrate_catalog

    cid = await _bard(client, 3, LORE)  # nato dopo il catalogo: scelta di Sapienza in sospeso, niente retrofit
    assert not _choice(await _full(client, cid), "lore_skills").get("retrofit")
    await _bump(test_session_factory)
    assert await migrate_catalog(test_session_factory) >= 1
    assert not _choice(await _full(client, cid), "lore_skills").get("retrofit")  # secondo giro: ancora no
    await _bump(test_session_factory)
    await migrate_catalog(test_session_factory)
    assert not _choice(await _full(client, cid), "lore_skills").get("retrofit")


async def test_a_class_that_enters_with_a_later_catalog_is_retrofitted_for_that_catalog_only(client, test_session_factory):
    from api.services.catalog_migration import migrate_catalog

    cid = await _bard(client, 3, LORE)
    await client.post(f"/characters/{cid}/classes", json={"class_name": "barbarian", "level": 3, "hit_die": 12})
    async with test_session_factory() as s:  # il Barbaro non aveva ancora il catalogo: nessun segno, e una scelta salvata
        char = (await s.execute(select(Character).options(selectinload(Character.classes)).where(Character.id == cid))).scalar_one()
        marks = [m for m in (char.settings or {}).get("retrofit_done", []) if m != "barbarian"]
        assert "bard" in marks  # il Bardo è segnato dal sync che l'ha creato
        char.settings = {**char.settings, "retrofit_done": marks}
        await s.commit()
    await _bump(test_session_factory)
    await migrate_catalog(test_session_factory)
    full = await _full(client, cid)
    assert not _choice(full, "lore_skills").get("retrofit")  # il Bardo non torna retrofit
    async with test_session_factory() as s:
        done = (await s.get(Character, cid)).settings["retrofit_done"]
    assert set(done) == {"bard", "barbarian"}  # ora segnati entrambi


async def test_the_retrofit_mark_is_server_owned(client):
    cid = await _bard(client, 3, LORE)
    full = await _full(client, cid)
    assert "bard" in full["settings"]["retrofit_done"]
    await client.patch(f"/characters/{cid}", json={"settings": {**full["settings"], "retrofit_done": []}})
    assert "bard" in (await _full(client, cid))["settings"]["retrofit_done"]


async def test_an_imported_character_is_retrofitted_again(client):
    cid = await _bard(client, 3, LORE)
    exported = (await client.get(f"/characters/{cid}/export")).json()
    r = await client.post("/characters/import", json=exported)
    assert r.status_code == 201, r.text
    assert _choice(await _full(client, r.json()["id"]), "lore_skills")["retrofit"] is True
