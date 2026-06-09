"""POST /characters/{id}/spells/{spell_id}/use con as_ritual=true.

Regole pinnate (spec 2026-06-10):
- Rituale: nessuno slot consumato; lanciabile anche a slot esauriti/assenti.
- Concentrazione attivata come per il lancio normale.
- 400 se l'incantesimo non è is_ritual o il PG non ha classi con Ritual Casting.
- Lancio normale: slot_level obbligatorio (400 se assente).
- Voce di history event_type='spell_ritual_cast'.
"""
from __future__ import annotations


async def _wizard(client) -> int:
    r = await client.post(
        "/characters",
        json={"name": "Ritualista", "initial_class": {
            "class_name": "Mago", "level": 3, "hit_die": 6,
            "spellcasting_ability": "intelligence",
        }},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _fighter(client) -> int:
    r = await client.post(
        "/characters",
        json={"name": "Marziale", "initial_class": {
            "class_name": "Guerriero", "level": 3, "hit_die": 10,
        }},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _add_spell(client, cid: int, *, name="Rito", level=1,
                     is_ritual=True, is_concentration=False) -> int:
    r = await client.post(
        f"/characters/{cid}/spells",
        json={"name": name, "level": level, "is_ritual": is_ritual,
              "is_concentration": is_concentration},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_ritual_cast_leaves_slots_untouched(client):
    # Il Mago L3 ha già slot auto-calcolati (modalità auto di default).
    cid = await _wizard(client)
    sid = await _add_spell(client, cid)

    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"as_ritual": True})
    assert r.status_code == 200, r.text
    slots = r.json()["spell_slots"]
    assert slots, "il Mago L3 deve avere slot auto"
    assert all(s["used"] == 0 for s in slots)


async def test_ritual_cast_works_without_matching_slot(client):
    # Rituale di 5° su un Mago L3 (nessuno slot di 5°): lanciabile comunque.
    cid = await _wizard(client)
    sid = await _add_spell(client, cid, level=5)
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"as_ritual": True})
    assert r.status_code == 200, r.text


async def test_ritual_cast_sets_concentration(client):
    cid = await _wizard(client)
    sid = await _add_spell(client, cid, is_concentration=True)
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"as_ritual": True})
    assert r.status_code == 200, r.text
    assert r.json()["concentrating_spell_id"] == sid


async def test_non_ritual_spell_is_400(client):
    cid = await _wizard(client)
    sid = await _add_spell(client, cid, is_ritual=False)
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"as_ritual": True})
    assert r.status_code == 400, r.text


async def test_no_ritual_casting_class_is_400(client):
    cid = await _fighter(client)
    sid = await _add_spell(client, cid)
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"as_ritual": True})
    assert r.status_code == 400, r.text


async def test_normal_cast_without_slot_level_is_400(client):
    cid = await _wizard(client)
    sid = await _add_spell(client, cid)
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={})
    assert r.status_code == 400, r.text


async def test_ritual_cast_writes_history(client):
    cid = await _wizard(client)
    sid = await _add_spell(client, cid, name="Individuazione del Magico")
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"as_ritual": True})
    assert r.status_code == 200, r.text
    h = await client.get(f"/characters/{cid}/history")
    assert h.status_code == 200, h.text
    assert any(e["event_type"] == "spell_ritual_cast" for e in h.json())
