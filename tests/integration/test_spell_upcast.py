"""Upcast automatico: higher_levels_dice x (livello slot - livello incantesimo)."""
from __future__ import annotations


async def _spell(client, **kw):
    cid = (await client.post("/characters", json={"name": "Mago"})).json()["id"]
    body = {"name": "Palla di fuoco", "level": 3, "damage_dice": "8d6", "damage_type": "fire", **kw}
    r = await client.post(f"/characters/{cid}/spells", json=body)
    assert r.status_code == 201, r.text
    return cid, r.json()["id"]


async def _roll(client, cid, sid, level, rolls=None):
    body = {"casting_level": level}
    if rolls is not None:
        body["main_rolls"] = rolls
    return await client.post(f"/characters/{cid}/spells/{sid}/roll_damage", json=body)


async def test_upcast_adds_higher_levels_dice(client):
    cid, sid = await _spell(client, higher_levels_dice="1d6", school="evocation", srd_index="fireball")
    r = await _roll(client, cid, sid, 5, [1] * 10)
    assert r.status_code == 200, r.text
    assert r.json()["scaled_dice"] == "10d6" and len(r.json()["main_rolls"]) == 10
    assert (await _roll(client, cid, sid, 5, [1] * 8)).status_code == 400
    sp = next(s for s in (await client.get(f"/characters/{cid}")).json()["spells"] if s["id"] == sid)
    assert (sp["school"], sp["srd_index"], sp["higher_levels_dice"]) == ("evocation", "fireball", "1d6")


async def test_upcast_without_field_unchanged(client):
    cid, sid = await _spell(client)
    r = await _roll(client, cid, sid, 5, [1] * 8)
    assert r.status_code == 200 and r.json()["scaled_dice"] == "8d6"


async def test_upcast_at_base_level_unchanged(client):
    cid, sid = await _spell(client, higher_levels_dice="1d6")
    assert (await _roll(client, cid, sid, 3, [1] * 8)).status_code == 200


async def test_sleep_pool_upcast(client):
    # 2014 pag. 279: la riserva di PF di Sonno cresce di 2d8 per slot oltre il 1°, anche sulle righe salvate senza dadi di scalata
    for extra in ({"higher_levels_dice": "2d8"}, {}):
        cid, sid = await _spell(client, name="Sonno", level=1, damage_dice="5d8", damage_type=None, srd_index="sleep", **extra)
        r = await _roll(client, cid, sid, 3, [1] * 9)
        assert r.status_code == 200 and r.json()["scaled_dice"] == "9d8"


async def test_caster_modifier_added_only_where_the_card_says(client, monkeypatch):
    # Arma Spirituale (2014 pag. 215, 2024 pag. 319-320), Lama infuocata e Spada di Mordenkainen 2024 (pag. 275, 302):
    # dadi + modificatore da incantatore; Lama Infuocata 2014 (pag. 247) no.
    import random
    monkeypatch.setattr(random, "randint", lambda a, b: 1)
    for edition, index, level, dice, mod in [("2014", "spiritual-weapon", 2, "1d8", 3), ("2024", "spiritual-weapon", 2, "1d8", 3),
                                             ("2024", "flame-blade", 2, "3d6", 3), ("2024", "arcane-sword", 7, "4d12", 3),
                                             ("2014", "flame-blade", 2, "3d6", 0)]:
        r = await client.post("/characters", json={"name": "Chierico", "rules_edition": edition,
                                                   "initial_class": {"class_name": "cleric", "level": 13}})
        cid = r.json()["id"]
        assert (await client.patch(f"/characters/{cid}/ability_scores/wisdom", json={"value": 16})).status_code == 200
        r = await client.post(f"/characters/{cid}/spells", json={"name": index, "level": level, "damage_dice": dice,
                                                                 "damage_type": "force", "srd_index": index})
        r = await _roll(client, cid, r.json()["id"], level)
        assert r.status_code == 200, r.text
        assert r.json()["total"] == int(dice.split("d")[0]) + mod, (edition, index)


async def test_higher_levels_dice_validated(client):
    cid = (await client.post("/characters", json={"name": "Mago"})).json()["id"]
    r = await client.post(f"/characters/{cid}/spells", json={"name": "X", "higher_levels_dice": "lots"})
    assert r.status_code == 422


async def test_magic_missile_upcast_adds_a_dart_per_level(client):
    # Ogni livello oltre il 1° aggiunge un dardo da 1d4+1: dadi E bonus crescono insieme.
    cid, sid = await _spell(client, name="Dardo incantato", level=1, damage_dice="3d4+3",
                            damage_type="force", higher_levels_dice="1d4+1", srd_index="magic-missile")
    r = await _roll(client, cid, sid, 3, [1] * 5)
    assert r.status_code == 200, r.text
    assert r.json()["scaled_dice"] == "5d4"
    assert r.json()["total"] == 5 + 5
    r = await _roll(client, cid, sid, 1, [2] * 3)
    assert r.json()["total"] == 6 + 3
