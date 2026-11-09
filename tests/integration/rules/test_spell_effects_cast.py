"""Effetti degli incantesimi: bersagli al lancio, orologio sul lanciatore e fine degli effetti con la concentrazione."""
from __future__ import annotations

import random

from sqlalchemy import select

from core.db.models import AbilityScore, Character, SessionParticipant, SessionRole
from core.rules.catalog.spells import spell_effect
from core.rules.spell_effects import SPELL_STATE_PREFIX
from tests.integration._encounter_helpers import GM_ID, NOW, PLAYER_ID, as_user, seed_session
from tests.integration.rules.test_2014_bard_inspiration import _seat
from tests.integration.test_magic_items import _item

SOF = "shield-of-faith"
STATE = f"{SPELL_STATE_PREFIX}shield_of_faith"
SOF_ROUNDS = spell_effect("2014", SOF)[1].rounds  # dal catalogo, mai a mano


async def _full(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def _ac(client, cid, user) -> int:
    as_user(user)
    return (await _full(client, cid))["ac"]


async def _states(client, cid, user, key=STATE) -> list[dict]:
    as_user(user)
    return [s for s in (await _full(client, cid))["active_states"] or [] if s["key"] == key]


async def _caster(client, factory, name="Chierico", user=GM_ID, seat=True) -> tuple[int, int]:
    """Un incantatore con Scudo della Fede e uno slot di 1° livello: `(personaggio, id dell'incantesimo)`."""
    as_user(user)
    cid = (await client.post("/characters", json={"name": name})).json()["id"]
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": 30})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 30})
    r = await client.post(f"/characters/{cid}/spells", json={
        "name": "Shield of Faith", "srd_index": SOF, "level": 1, "is_concentration": True})
    assert r.status_code == 201, r.text
    assert (await client.post(f"/characters/{cid}/spell_slots", json={"level": 1, "total": 2})).status_code == 201
    if seat:
        await _seat(factory, cid, user)
    return cid, r.json()["id"]


async def _cast(client, caster, spell, targets, user=GM_ID, **extra):
    as_user(user)
    return await client.post(f"/characters/{caster}/spells/{spell}/use", json={"slot_level": 1, "targets": targets, **extra})


async def _table(client, factory):
    sid, hero = await seed_session(factory)
    caster, spell = await _caster(client, factory)
    return sid, hero, caster, spell


async def _slots_used(client, cid) -> int:
    return sum(s["used"] for s in (await _full(client, cid))["spell_slots"])


async def test_shield_of_faith_on_a_seated_ally_raises_their_ac_by_two(client, test_session_factory):
    _, hero, caster, spell = await _table(client, test_session_factory)
    base = await _ac(client, hero, PLAYER_ID)
    r = await _cast(client, caster, spell, [hero])
    assert r.status_code == 200, r.text
    assert r.json()["spell_effects"]["applied"] == [{"id": hero, "name": "Eroe"}]
    assert await _ac(client, hero, PLAYER_ID) == base + 2
    [state] = await _states(client, hero, PLAYER_ID)
    assert state["rounds_left"] is None and state["data"]["caster_id"] == caster and state["name"] == "Shield of Faith"
    [clock] = await _states(client, caster, GM_ID, f"spell_cast:shield_of_faith")
    assert clock["rounds_left"] == SOF_ROUNDS and "concentration_end" in clock["ends_on"]


async def test_ending_concentration_removes_the_effect_from_the_ally(client, test_session_factory):
    _, hero, caster, spell = await _table(client, test_session_factory)
    base = await _ac(client, hero, PLAYER_ID)
    await _cast(client, caster, spell, [hero])
    as_user(GM_ID)
    r = await client.patch(f"/characters/{caster}/concentration", json={"spell_id": None})
    assert r.status_code == 200, r.text
    assert await _ac(client, hero, PLAYER_ID) == base
    assert await _states(client, hero, PLAYER_ID) == []


async def test_failed_concentration_save_on_damage_removes_the_effect(client, test_session_factory, monkeypatch):
    _, hero, caster, spell = await _table(client, test_session_factory)
    base = await _ac(client, hero, PLAYER_ID)
    await _cast(client, caster, spell, [hero])
    monkeypatch.setattr(random, "randint", lambda a, b: 1)
    as_user(GM_ID)
    r = await client.patch(f"/characters/{caster}/hp", json={"op": "damage", "value": 5})
    assert r.status_code == 200 and r.json()["concentrating_spell_id"] is None, r.text
    assert await _ac(client, hero, PLAYER_ID) == base


async def test_rounds_count_on_the_casters_clock(client, test_session_factory):
    _, hero, caster, spell = await _table(client, test_session_factory)
    await _cast(client, caster, spell, [hero])
    as_user(PLAYER_ID)
    for _ in range(5):  # i round dell'alleato non accorciano l'effetto
        await client.post(f"/characters/{hero}/rounds/tick")
    assert len(await _states(client, hero, PLAYER_ID)) == 1
    as_user(GM_ID)
    for _ in range(SOF_ROUNDS - 1):
        await client.post(f"/characters/{caster}/rounds/tick")
    assert len(await _states(client, hero, PLAYER_ID)) == 1
    as_user(GM_ID)
    await client.post(f"/characters/{caster}/rounds/tick")
    assert await _states(client, hero, PLAYER_ID) == []


async def test_same_spell_twice_does_not_stack(client, test_session_factory):
    sid, hero, first, spell1 = await _table(client, test_session_factory)
    base = await _ac(client, hero, PLAYER_ID)
    async with test_session_factory() as s:  # un secondo chierico seduto alla stessa serata
        other = Character(user_id=9001, name="Secondo")
        s.add(other)
        await s.flush()
        s.add(AbilityScore(character_id=other.id, name="dexterity", value=12))
        s.add(SessionParticipant(session_id=sid, user_id=9001, character_id=other.id, role=SessionRole.PLAYER,
                                 display_name="Secondo", joined_at=NOW))
        await s.commit()
    second, spell2 = await _caster(client, test_session_factory, "Secondo", user=9001, seat=False)
    async with test_session_factory() as s:  # il personaggio creato qui prende il posto di quello seedato
        part = (await s.execute(select(SessionParticipant).where(SessionParticipant.user_id == 9001))).scalar_one()
        part.character_id = second
        await s.commit()
    await _cast(client, first, spell1, [hero])
    assert (await _cast(client, second, spell2, [hero], user=9001)).status_code == 200
    assert await _ac(client, hero, PLAYER_ID) == base + 2
    as_user(GM_ID)
    await client.patch(f"/characters/{first}/concentration", json={"spell_id": None})
    assert await _ac(client, hero, PLAYER_ID) == base + 2  # resta quello del secondo
    as_user(9001)
    await client.patch(f"/characters/{second}/concentration", json={"spell_id": None})
    assert await _ac(client, hero, PLAYER_ID) == base


async def test_dead_or_unseated_target_is_refused_without_spending_the_slot(client, test_session_factory):
    _, hero, caster, spell = await _table(client, test_session_factory)
    async with test_session_factory() as s:
        stranger = Character(user_id=PLAYER_ID, name="Estraneo")
        s.add(stranger)
        await s.commit()
        stranger_id = stranger.id
    r = await _cast(client, caster, spell, [stranger_id])
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_target", r.text
    r = await _cast(client, caster, spell, [hero, hero])
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_target", r.text
    async with test_session_factory() as s:
        (await s.get(Character, hero)).is_dead = True
        await s.commit()
    r = await _cast(client, caster, spell, [hero])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "target_dead", r.text
    as_user(GM_ID)
    assert await _slots_used(client, caster) == 0
    assert (await _full(client, caster))["concentrating_spell_id"] is None


async def test_out_of_the_evening_returns_text_and_no_state(client, test_session_factory):
    caster, spell = await _caster(client, test_session_factory, seat=False)
    async with test_session_factory() as s:
        other = Character(user_id=GM_ID, name="Altro")
        s.add(other)
        await s.commit()
        other_id = other.id
    r = await _cast(client, caster, spell, [other_id])
    assert r.status_code == 200, r.text
    fx = r.json()["spell_effects"]
    assert fx["applied"] == [] and fx["text"] and fx["text"]["it"] and fx["text"]["en"]
    assert await _states(client, other_id, GM_ID) == []


async def test_item_cast_applies_the_same_effects(client, test_session_factory):
    _, hero, caster, _ = await _table(client, test_session_factory)
    base = await _ac(client, hero, PLAYER_ID)
    spell = {"name": "Shield of Faith", "srd_index": SOF, "level": 1, "charges_cost": 1, "is_concentration": True}
    as_user(GM_ID)
    iid = await _item(client, caster, charges={"current": 3, "max": 3}, granted_spells=[spell])
    r = await client.post(f"/characters/{caster}/items/{iid}/cast", json={"spell_index": 0, "targets": [hero]})
    assert r.status_code == 200, r.text
    assert r.json()["spell_effects"]["applied"] == [{"id": hero, "name": "Eroe"}]
    assert await _ac(client, hero, PLAYER_ID) == base + 2


async def test_deleted_ally_does_not_break_the_release(client, test_session_factory):
    _, hero, caster, spell = await _table(client, test_session_factory)
    await _cast(client, caster, spell, [hero])
    async with test_session_factory() as s:
        await s.delete(await s.get(Character, hero))
        await s.commit()
    as_user(GM_ID)
    r = await client.patch(f"/characters/{caster}/concentration", json={"spell_id": None})
    assert r.status_code == 200, r.text


async def test_transfer_clears_spell_given(client, test_session_factory):
    _, hero, caster, spell = await _table(client, test_session_factory)
    await _cast(client, caster, spell, [hero])
    as_user(GM_ID)
    exported = (await client.get(f"/characters/{caster}/export")).json()
    assert exported["character"]["settings"].get("spell_given")  # nel file ci sono gli id di questo database
    r = await client.post("/characters/import", json=exported)
    assert r.status_code in (200, 201), r.text
    async with test_session_factory() as s:
        copy = await s.get(Character, r.json()["id"])
        assert "spell_given" not in (copy.settings or {})


async def _fail_concentration(client, caster, monkeypatch) -> dict:
    monkeypatch.setattr(random, "randint", lambda a, b: 1)
    as_user(GM_ID)
    r = await client.patch(f"/characters/{caster}/hp", json={"op": "damage", "value": 5})
    assert r.status_code == 200 and r.json()["concentrating_spell_id"] is None, r.text
    return r.json()


async def test_hp_undo_gives_the_effect_back_to_the_ally(client, test_session_factory, monkeypatch):
    _, hero, caster, spell = await _table(client, test_session_factory)
    base = await _ac(client, hero, PLAYER_ID)
    await _cast(client, caster, spell, [hero])
    dmg = await _fail_concentration(client, caster, monkeypatch)
    assert await _ac(client, hero, PLAYER_ID) == base
    as_user(GM_ID)
    r = await client.post(f"/characters/{caster}/hp/undo", json={"op_id": dmg["hp_undo_id"]})
    assert r.status_code == 200, r.text
    assert await _ac(client, hero, PLAYER_ID) == base + 2 and len(await _states(client, hero, PLAYER_ID)) == 1
    as_user(GM_ID)
    await client.patch(f"/characters/{caster}/concentration", json={"spell_id": None})
    assert await _ac(client, hero, PLAYER_ID) == base


async def test_hp_undo_on_self_leaves_no_permanent_bonus(client, test_session_factory, monkeypatch):
    _, _, caster, spell = await _table(client, test_session_factory)
    base = await _ac(client, caster, GM_ID)
    await _cast(client, caster, spell, None)
    dmg = await _fail_concentration(client, caster, monkeypatch)
    as_user(GM_ID)
    assert (await client.post(f"/characters/{caster}/hp/undo", json={"op_id": dmg["hp_undo_id"]})).status_code == 200
    assert await _ac(client, caster, GM_ID) == base + 2
    await client.patch(f"/characters/{caster}/concentration", json={"spell_id": None})
    assert await _ac(client, caster, GM_ID) == base


async def test_deleted_caster_releases_the_ally(client, test_session_factory):
    _, hero, caster, spell = await _table(client, test_session_factory)
    base = await _ac(client, hero, PLAYER_ID)
    await _cast(client, caster, spell, [hero])
    as_user(GM_ID)
    assert (await client.delete(f"/characters/{caster}")).status_code == 204
    assert await _ac(client, hero, PLAYER_ID) == base
    assert await _states(client, hero, PLAYER_ID) == []


async def _spell_for(client, cid) -> int:
    as_user(PLAYER_ID)
    r = await client.post(f"/characters/{cid}/spells", json={
        "name": "Shield of Faith", "srd_index": SOF, "level": 1, "is_concentration": True})
    assert r.status_code == 201, r.text
    assert (await client.post(f"/characters/{cid}/spell_slots", json={"level": 1, "total": 2})).status_code == 201
    return r.json()["id"]


async def test_encounter_undo_gives_the_effect_back(client, test_session_factory, monkeypatch):
    from tests.integration._encounter_helpers import setup_full_encounter
    from tests.integration._telegram_stub import install_fake_telegram
    install_fake_telegram(monkeypatch)
    sid, _ = await setup_full_encounter(client, test_session_factory)
    r = await client.post(f"/sessions/{sid}/encounter/start", json={})
    assert r.status_code == 200, r.text
    async with test_session_factory() as s:
        hero = (await s.execute(select(Character).where(Character.name == "Eroe"))).scalar_one().id
    spell = await _spell_for(client, hero)
    base = await _ac(client, hero, PLAYER_ID)
    assert (await _cast(client, hero, spell, None, user=PLAYER_ID)).status_code == 200
    async with test_session_factory() as s:  # ultimo round: scade all'inizio del prossimo turno del PG
        ch = await s.get(Character, hero)
        ch.active_states = [{**st, "rounds_left": 1} if st["key"].startswith("spell_cast:") else st for st in ch.active_states]
        await s.commit()
    as_user(GM_ID)
    for _ in range(3):  # PG -> goblin -> goblin -> PG
        assert (await client.post(f"/sessions/{sid}/encounter/next-turn")).status_code == 200
    assert await _ac(client, hero, PLAYER_ID) == base
    as_user(GM_ID)
    assert (await client.post(f"/sessions/{sid}/encounter/prev-turn")).status_code == 200
    assert await _ac(client, hero, PLAYER_ID) == base + 2
    as_user(PLAYER_ID)
    await client.patch(f"/characters/{hero}/concentration", json={"spell_id": None})
    assert await _ac(client, hero, PLAYER_ID) == base


async def test_outside_the_evening_the_caster_still_gets_their_own_effect(client, test_session_factory):
    caster, _ = await _caster(client, test_session_factory, seat=False)
    as_user(GM_ID)
    aid = (await client.post(f"/characters/{caster}/spells", json={"name": "Aid", "srd_index": "aid", "level": 2})).json()["id"]
    await client.post(f"/characters/{caster}/spell_slots", json={"level": 2, "total": 1})
    async with test_session_factory() as s:
        other = Character(user_id=GM_ID, name="Altro")
        s.add(other)
        await s.commit()
        other_id = other.id
    r = await _cast(client, caster, aid, [caster, other_id], slot_level=2)
    assert r.status_code == 200, r.text
    fx = r.json()["spell_effects"]
    assert fx["applied"] == [{"id": caster, "name": "Chierico"}] and fx["text"]["it"]
    assert len(await _states(client, caster, GM_ID, f"{SPELL_STATE_PREFIX}aid")) == 1
    assert await _states(client, other_id, GM_ID, f"{SPELL_STATE_PREFIX}aid") == []


async def test_item_cast_concentration_comes_from_the_catalog_variant(client, test_session_factory):
    _, hero, caster, _ = await _table(client, test_session_factory)
    base = await _ac(client, hero, PLAYER_ID)
    spell = {"name": "Shield of Faith", "srd_index": SOF, "level": 1, "charges_cost": 1}  # senza is_concentration
    as_user(GM_ID)
    iid = await _item(client, caster, charges={"current": 3, "max": 3}, granted_spells=[spell])
    r = await client.post(f"/characters/{caster}/items/{iid}/cast", json={"spell_index": 0, "targets": [hero]})
    assert r.status_code == 200, r.text
    assert r.json()["concentrating_spell_id"] is not None  # l'orologio cade con la concentrazione: deve esserci
    assert await _ac(client, hero, PLAYER_ID) == base + 2
    as_user(GM_ID)
    await client.patch(f"/characters/{caster}/concentration", json={"spell_id": None})
    assert await _ac(client, hero, PLAYER_ID) == base


async def test_spell_list_exposes_the_effect_for_the_client(client, test_session_factory):
    caster, _ = await _caster(client, test_session_factory, seat=False)
    as_user(GM_ID)
    await client.post(f"/characters/{caster}/spells", json={"name": "Aid", "srd_index": "aid", "level": 2})
    await client.post(f"/characters/{caster}/spells", json={"name": "Fireball", "srd_index": "fireball", "level": 3})
    spells = {s["srd_index"]: s for s in (await client.get(f"/characters/{caster}/spells")).json()}
    assert spells[SOF]["effect"]["target_kind"] == "ally" and spells[SOF]["effect"]["max_targets_by_slot"]["1"] == 1
    aid = spells["aid"]["effect"]
    assert aid["target_kind"] == "allies" and aid["max_targets_by_slot"]["3"] == 3 and aid["choices"] == []
    assert spells["fireball"]["effect"] is None
