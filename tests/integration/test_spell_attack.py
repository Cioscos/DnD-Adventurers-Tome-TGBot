"""POST /characters/{id}/spells/{spell_id}/attack — tiro per colpire degli incantesimi."""
from __future__ import annotations

from api.schemas.character import SpellCasterStats
from api.services import spellcasting


async def _wizard(client) -> int:
    r = await client.post(
        "/characters",
        json={
            "name": "Mago",
            "initial_class": {
                "class_name": "wizard", "level": 5, "hit_die": 6,
                "spellcasting_ability": "intelligence",
            },
        },
    )
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.patch(f"/characters/{cid}/ability_scores/intelligence", json={"value": 18})
    assert r.status_code == 200, r.text
    return cid  # pb 3 + INT 4 = +7


async def _slot(client, cid: int, level: int, total: int, used: int = 0) -> None:
    # Il mago di livello 5 ha già gli slot auto-creati: li si porta ai valori voluti.
    slots = (await client.get(f"/characters/{cid}")).json()["spell_slots"]
    existing = next((s for s in slots if s["level"] == level), None)
    if existing is None:
        r = await client.post(
            f"/characters/{cid}/spell_slots", json={"level": level, "total": total, "used": used}
        )
        assert r.status_code == 201, r.text
    else:
        r = await client.patch(
            f"/characters/{cid}/spell_slots/{existing['id']}", json={"total": total, "used": used}
        )
        assert r.status_code == 200, r.text


async def _spell(client, cid: int, *, level=1, attack_save="ATK", **extra) -> int:
    r = await client.post(
        f"/characters/{cid}/spells",
        json={"name": "Raggio di Fuoco", "level": level, "attack_save": attack_save, **extra},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _avail(body: dict, level: int) -> int:
    return next(s for s in body["spell_slots"] if s["level"] == level)["available"]


async def test_spell_attack_rolls_and_consumes_slot(client):
    cid = await _wizard(client)
    await _slot(client, cid, 1, 2)
    sid = await _spell(client, cid)
    r = await client.post(
        f"/characters/{cid}/spells/{sid}/attack", json={"slot_level": 1, "die": 12}
    )
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["spell_name"] == "Raggio di Fuoco"
    assert b["to_hit_die"] == 12
    assert b["to_hit_bonus"] == 7
    assert b["to_hit_total"] == 19
    assert b["is_critical"] is False and b["is_fumble"] is False
    assert b["caster_class"] == "wizard"
    assert _avail(b["character"], 1) == 1
    hist = (await client.get(f"/characters/{cid}/history")).json()
    assert any("Attacco incantesimo Raggio di Fuoco: d20=12+7=19" in h["description"] for h in hist)
    stats = (await client.get(f"/characters/{cid}/dice/stats")).json()["stats"]
    assert stats["d20"] == {"12": 1}


async def test_spell_attack_cantrip_consumes_nothing(client):
    cid = await _wizard(client)
    await _slot(client, cid, 1, 2)
    sid = await _spell(client, cid, level=0, is_concentration=True)
    r = await client.post(f"/characters/{cid}/spells/{sid}/attack", json={"die": 5})
    assert r.status_code == 200, r.text
    b = r.json()
    assert _avail(b["character"], 1) == 2
    assert b["character"]["concentrating_spell_id"] == sid


async def test_spell_attack_rejects_non_attack_spell(client):
    cid = await _wizard(client)
    await _slot(client, cid, 1, 2)
    sid = await _spell(client, cid, attack_save="SAVE")
    r = await client.post(f"/characters/{cid}/spells/{sid}/attack", json={"slot_level": 1})
    assert r.status_code == 400


async def test_spell_attack_no_slot_is_400(client):
    cid = await _wizard(client)
    await _slot(client, cid, 1, 1, used=1)
    sid = await _spell(client, cid)
    r = await client.post(f"/characters/{cid}/spells/{sid}/attack", json={"slot_level": 1})
    assert r.status_code == 400


async def test_spell_attack_reroll_needs_no_slot(client):
    cid = await _wizard(client)
    await _slot(client, cid, 1, 1, used=1)
    sid = await _spell(client, cid)
    r = await client.patch(f"/characters/{cid}/inspiration", json={"heroic_inspiration": True})
    assert r.status_code == 200, r.text
    r = await client.post(
        f"/characters/{cid}/spells/{sid}/attack", json={"with_inspiration": True, "die": 9}
    )
    assert r.status_code == 200, r.text
    b = r.json()
    assert _avail(b["character"], 1) == 0
    assert b["character"]["heroic_inspiration"] is False
    hist = (await client.get(f"/characters/{cid}/history")).json()
    assert any(h["description"].startswith("Reroll ispirazione: Attacco incantesimo") for h in hist)


async def test_spell_attack_reroll_without_inspiration_409(client):
    cid = await _wizard(client)
    sid = await _spell(client, cid)
    r = await client.post(f"/characters/{cid}/spells/{sid}/attack", json={"with_inspiration": True})
    assert r.status_code == 409


async def test_spell_attack_natural_20_is_critical(client):
    cid = await _wizard(client)
    sid = await _spell(client, cid, level=0)
    r = await client.post(f"/characters/{cid}/spells/{sid}/attack", json={"die": 20})
    assert r.status_code == 200, r.text
    assert r.json()["is_critical"] is True
    r = await client.post(f"/characters/{cid}/spells/{sid}/attack", json={"die": 1})
    assert r.json()["is_fumble"] is True


async def test_spell_attack_invalid_die_is_422(client):
    cid = await _wizard(client)
    sid = await _spell(client, cid, level=0)
    r = await client.post(f"/characters/{cid}/spells/{sid}/attack", json={"die": 21})
    assert r.status_code == 422


async def test_use_spell_unchanged(client):
    cid = await _wizard(client)
    await _slot(client, cid, 1, 1)
    sid = await _spell(client, cid, is_concentration=True)
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={})
    assert r.status_code == 400 and r.json()["detail"] == "slot_level is required"
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": 9})
    assert r.status_code == 400 and r.json()["detail"] == "No slot configured for level 9"
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": 1})
    assert r.status_code == 200
    assert _avail(r.json(), 1) == 0 and r.json()["concentrating_spell_id"] == sid
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"slot_level": 1})
    assert r.status_code == 400 and r.json()["detail"] == "No slots available at level 1"
    r = await client.post(f"/characters/{cid}/spells/{sid}/use", json={"as_ritual": True})
    assert r.status_code == 400 and r.json()["detail"] == "Spell is not a ritual"


def test_best_caster_tie_returns_first(monkeypatch):
    a = SpellCasterStats(class_id=1, class_name="cleric", ability="wisdom", save_dc=13, attack_bonus=5)
    b = SpellCasterStats(class_id=2, class_name="wizard", ability="intelligence", save_dc=13, attack_bonus=5)
    monkeypatch.setattr(spellcasting, "_caster_stats", lambda _c: [a, b])
    assert spellcasting.best_caster(object()).class_name == "cleric"
    c = b.model_copy(update={"attack_bonus": 6})
    monkeypatch.setattr(spellcasting, "_caster_stats", lambda _c: [a, c])
    assert spellcasting.best_caster(object()).class_name == "wizard"
