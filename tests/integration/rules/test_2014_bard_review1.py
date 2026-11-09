"""Bardo 2014, giro di correzione 1 (I4, I5, M1-M4). Il resto del giro sta negli altri file `test_2014_bard_*`."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from core.db.models import Character, SessionParticipant
from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard import (
    LORE, SONG, _add_spell, _bard, _choice, _full, _hurt, _spend, _states, _use,
)


async def _settings(test_session_factory, cid) -> dict:
    async with test_session_factory() as s:
        return dict((await s.get(Character, cid)).settings or {})


async def _seat(test_session_factory, cid, user=GM_ID) -> None:
    async with test_session_factory() as s:
        part = (await s.execute(select(SessionParticipant).where(SessionParticipant.user_id == user))).scalar_one()
        part.character_id = cid
        await s.commit()


# I4: il livello massimo di Segreti Magici segue la tabella del bardo, non la multiclasse

@pytest.mark.parametrize("other", [None, "wizard"])
async def test_magical_secrets_max_level_uses_the_bard_table_only(client, other):
    cid = await _bard(client, 10)
    if other:  # Bardo 10 + Mago 10: la tabella multiclasse arriva al 9°, quella del bardo al 5°
        r = await client.post(f"/characters/{cid}/classes", json={"class_name": other, "level": 10, "hit_die": 6})
        assert r.status_code == 201, r.text
    choice = _choice(await _full(client, cid), "magical_secrets")
    assert choice["spell_pick"]["max_level"] == 5
    too_high = await _add_spell(client, cid, "Desiderio", 6, pick_id=choice["id"])
    assert too_high.status_code == 422 and too_high.json()["detail"]["code"] == "spell_pick_level"


async def test_a_bard_at_18_picks_up_to_the_ninth_level(client):
    cid = await _bard(client, 18)
    assert _choice(await _full(client, cid), "magical_secrets")["spell_pick"]["max_level"] == 9


# I5: cancellare un incantesimo scelto restituisce la scelta e toglie l'id orfano

async def test_removing_an_additional_secret_gives_the_pick_back(client, test_session_factory):
    cid = await _bard(client, 6, LORE)
    choice = _choice(await _full(client, cid), "additional_secrets")
    spell = (await _add_spell(client, cid, "Palla di fuoco", 3, pick_id=choice["id"])).json()
    assert _choice(await _full(client, cid), "additional_secrets")["count"] == 1
    assert spell["id"] in (await _settings(test_session_factory, cid))["free_known_spells"]
    assert (await client.delete(f"/characters/{cid}/spells/{spell['id']}")).status_code == 204
    assert _choice(await _full(client, cid), "additional_secrets")["count"] == 2  # l'errore di battitura si recupera
    assert not (await _settings(test_session_factory, cid)).get("free_known_spells")


async def test_removing_a_magical_secret_gives_the_pick_back(client):
    cid = await _bard(client, 10)
    choice = _choice(await _full(client, cid), "magical_secrets")
    spell = (await _add_spell(client, cid, "Palla di fuoco", 3, pick_id=choice["id"])).json()
    assert _choice(await _full(client, cid), "magical_secrets")["count"] == 1
    await client.delete(f"/characters/{cid}/spells/{spell['id']}")
    assert _choice(await _full(client, cid), "magical_secrets")["count"] == 2


async def test_a_recycled_spell_id_does_not_leave_the_known_limit(client):
    cid = await _bard(client, 6, LORE)
    choice = _choice(await _full(client, cid), "additional_secrets")
    free = (await _add_spell(client, cid, "Palla di fuoco", 3, pick_id=choice["id"])).json()
    await client.delete(f"/characters/{cid}/spells/{free['id']}")
    bard_class = (await _full(client, cid))["classes"][0]["id"]
    await _add_spell(client, cid, "Incantesimo base", 1, class_id=bard_class)  # SQLite può riassegnare lo stesso id
    assert (await _full(client, cid))["spellcasting"]["limits"][0]["known_count"] == 1


# M2: una sola funzione per i `grants`, anche all'import

async def test_a_class_option_with_grants_applies_them_on_import(test_session_factory):
    from api.routers.transfer import _apply_class_options
    from api.services.ddb_import import ImportReport
    from core.rules.sample_characters import build_rules_character

    async with test_session_factory() as s:
        spec = {"name": "x", "edition": "2014", "classes": [("Bardo", 6, LORE, 8)]}
        char = await build_rules_character(s, spec, 1)
        char.skills = {"arcana": True}
        _apply_class_options(char, [{"class_index": 0, "name": "Arcana"}], ImportReport(), "it")
        assert char.classes[0].options.get("expertise") == ["arcana"]
        assert char.skills["arcana"] == "expert"  # un posto consumato porta anche la maestria


# M1: il segno interno del Canto di Riposo non si vede e non si chiude

async def test_the_internal_song_marker_cannot_be_ended_by_hand(client, test_session_factory):
    sid, hero = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    await client.post(f"/characters/{hero}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})
    await _hurt(test_session_factory, hero)
    as_user(GM_ID)
    bard = await _bard(client, 2)
    await _seat(test_session_factory, bard)
    await _use(client, bard, SONG)
    as_user(PLAYER_ID)
    await _spend(client, hero)
    marker = next(s for s in await _states(client, hero) if s["key"] == "song_of_rest_received")
    assert marker["data"].get("internal") is True
    gone = await client.delete(f"/characters/{hero}/active-states/song_of_rest_received")
    assert gone.status_code == 404  # terminarlo riaprirebbe un secondo dado nello stesso riposo


# M3: Controfascino non sopravvive ai riposi

@pytest.mark.parametrize("rest", ["short", "long"])
async def test_countercharm_ends_with_a_rest(client, rest):
    cid = await _bard(client, 6)
    await _use(client, cid, "bard.countercharm")
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": rest, "confirm_early": True})
    assert r.status_code == 200, r.text
    assert await _states(client, cid) == []


# M4: il Canto di Riposo guarda il personaggio seduto, non l'utente

async def test_song_of_rest_skips_a_second_character_of_the_same_player(client, test_session_factory):
    sid, hero = await seed_session(test_session_factory)
    as_user(PLAYER_ID)
    await client.post(f"/characters/{hero}/classes", json={"class_name": "fighter", "level": 5, "hit_die": 10})
    alt = await _bard(client, 3)  # secondo PG dello stesso giocatore, non seduto alla serata
    await _hurt(test_session_factory, hero)
    await _hurt(test_session_factory, alt)
    as_user(GM_ID)
    bard = await _bard(client, 2)
    await _seat(test_session_factory, bard)
    await _use(client, bard, SONG)
    as_user(PLAYER_ID)
    alt_class = (await _full(client, alt))["classes"][0]["id"]
    r = await client.post(f"/characters/{alt}/hit_dice/spend", json={"class_id": alt_class, "count": 1, "rolls": [3]})
    assert r.status_code == 200, r.text
    assert r.json()["song_rolls"] == []
    assert len((await _spend(client, hero))["song_rolls"]) == 1
