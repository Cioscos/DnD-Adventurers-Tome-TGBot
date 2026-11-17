"""B2 (playtest 16/11): i trucchetti della tabella della classe sono una scelta di livello; quelli già sulla scheda la
riempiono, così si chiede solo quello che manca."""
from __future__ import annotations


async def _char(client, class_name, level, subclass=None) -> int:
    r = await client.post("/characters", json={"name": "T", "initial_class": {"class_name": class_name, "level": level,
                                                                                "subclass": subclass}})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _cantrip_choice(client, cid) -> dict | None:
    full = (await client.get(f"/characters/{cid}")).json()
    return next((c for c in full["pending_choices"] if c.get("group") == "class_cantrips"), None)


async def _add(client, cid, name, **extra):
    r = await client.post(f"/characters/{cid}/spells", json={"name": name, "level": 0, **extra})
    assert r.status_code == 201, r.text
    return r.json()


async def test_a_level_5_cleric_without_cantrips_is_asked_for_four(client):
    cid = await _char(client, "cleric", 5)
    choice = await _cantrip_choice(client, cid)
    assert choice and choice["count"] == 4
    assert choice["spell_pick"]["max_level"] == 0 and choice["spell_pick"]["list"] == "cleric"


async def test_picking_and_adding_by_hand_both_fill_the_choice(client):
    cid = await _char(client, "wizard", 1)
    choice = await _cantrip_choice(client, cid)
    assert choice["count"] == 3
    await _add(client, cid, "Luce", pick_id=choice["id"])
    await _add(client, cid, "Mano magica")  # senza la scelta: conta lo stesso
    assert (await _cantrip_choice(client, cid))["count"] == 1
    last = await _add(client, cid, "Raggio di gelo", pick_id=(await _cantrip_choice(client, cid))["id"])
    assert await _cantrip_choice(client, cid) is None
    assert (await client.delete(f"/characters/{cid}/spells/{last['id']}")).status_code == 204
    assert (await _cantrip_choice(client, cid))["count"] == 1  # cancellato: la scelta torna


async def test_cantrips_already_on_the_sheet_count_when_leveling(client):
    cid = await _char(client, "bard", 3)
    choice = await _cantrip_choice(client, cid)
    for name in ("Beffa crudele", "Luce"):
        await _add(client, cid, name)
    assert await _cantrip_choice(client, cid) is None
    cls = (await client.get(f"/characters/{cid}")).json()["classes"][0]["id"]
    r = await client.patch(f"/characters/{cid}/classes/{cls}", json={"level": 4})
    assert r.status_code == 200, r.text
    assert (await _cantrip_choice(client, cid))["count"] == 1  # 4° livello: un trucchetto in più
    assert choice is not None


async def test_classes_without_cantrips_are_not_asked(client):
    assert await _cantrip_choice(client, await _char(client, "paladin", 5)) is None
    assert await _cantrip_choice(client, await _char(client, "fighter", 3)) is None  # non Cavaliere Mistico


async def test_a_choice_says_which_feature_it_belongs_to(client):
    """U2/U4: la scelta porta il privilegio da cui nasce (titolo del modale, privilegio «da scegliere»)."""
    cid = await _char(client, "cleric", 1)
    assert (await client.patch(f"/characters/{cid}", json={"rules_edition": "2024"})).status_code == 200
    pending = (await client.get(f"/characters/{cid}")).json()["pending_choices"]
    order = next(c for c in pending if c.get("group") == "divine_order")
    assert order["feature_key"] == "cleric.divine_order" and order["title"]["it"] == "Ordine Divino"
    assert "title" not in await _cantrip_choice(client, cid)  # i trucchetti non nascono da un privilegio
