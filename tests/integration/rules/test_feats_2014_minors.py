"""Problemi minori della revisione finale della PR 3 talenti."""
from __future__ import annotations

from api.routers import items as items_router
from tests.integration.rules.test_2014_barbarian import _weapon
from tests.integration.rules.test_feats_2014_choices import _row
from tests.integration.rules.test_feats_2014_selection import _char14
from tests.integration.rules.test_feats_2024_selection import _char
from tests.integration.rules.test_feats_take_complete import _complete, _feat_rows, _spell, _take


async def test_savage_attacker_2014_not_on_thrown_attacks(client, monkeypatch):
    ch = await _char14(client, "fighter", strength=14)
    cid = ch["id"]
    assert (await _take(client, cid, "savage_attacker")).status_code == 201
    axe = await _weapon(client, cid, "Accetta", damage_dice="1d6", properties=["light", "thrown"])
    calls: list[str] = []
    real = items_router.roll_dice
    monkeypatch.setattr(items_router, "roll_dice", lambda notation: (calls.append(notation), real(notation))[1])
    r = await client.post(f"/characters/{cid}/items/{axe}/attack",
                          json={"die": 15, "confirm_extra_attack": True, "attack_mode": "thrown"})
    assert r.status_code == 200, r.text
    assert calls.count("1d6") == 1  # niente secondo tiro dei dadi dell'arma


async def test_dual_wielder_needs_two_melee_one_handed_weapons(client):
    ch = await _char14(client, "fighter")
    cid = ch["id"]
    assert (await _take(client, cid, "dual_wielder")).status_code == 201
    sword = await _weapon(client, cid, "Spada lunga", damage_dice="1d8")
    await _weapon(client, cid, "Balestra a mano", equip="off_hand", damage_dice="1d6", weapon_type="ranged")
    r = await client.post(f"/characters/{cid}/items/{sword}/attack", json={"die": 10, "attack_mode": "offhand"})
    assert r.status_code == 422 and "offhand_needs_second_weapon" in r.text
    great = await _weapon(client, cid, "Spadone", equip=None, damage_dice="2d6", properties=["two_handed"])
    r = await client.post(f"/characters/{cid}/items/{great}/attack", json={"die": 10, "attack_mode": "offhand"})
    assert r.status_code == 422 and "offhand_two_handed" in r.text


async def _reimport(client, cid: int, key: str, **options) -> dict:
    data = (await client.get(f"/characters/{cid}/export")).json()
    ab = next(a for a in data["abilities"] if a.get("feature_key") == f"feat.{key}")
    ab["options"] = {**ab["options"], **options}
    r = await client.post("/characters/import", json=data)
    assert r.status_code == 201, r.text
    return _feat_rows(r.json(), key)[0]


async def test_import_refuses_a_2014_list_for_2024_magic_initiate(client):
    ch = await _char(client, "wizard", 4)
    cid = ch["id"]
    r = await _take(client, cid, "2024_magic_initiate")
    row = _feat_rows(r.json(), "2024_magic_initiate")[0]
    spells = [_spell("Luce", 0, "light"), _spell("Mano magica", 0, "mage-hand"), _spell("Sonno", 1, "sleep")]
    assert (await _complete(client, cid, row["id"], {"list": "wizard", "ability": "intelligence"}, spells)).status_code == 200
    assert (await _reimport(client, cid, "2024_magic_initiate", list="bard"))["feat_status"] == "incomplete"


async def test_import_checks_the_saved_ability(client):
    ch = await _char14(client, "fighter")
    cid = ch["id"]
    row = await _row(client, cid, "magic_initiate")
    spells = [_spell("Luce", 0, "light"), _spell("Mano magica", 0, "mage-hand"), _spell("Sonno", 1, "sleep")]
    assert (await _complete(client, cid, row["id"], {"list": "wizard"}, spells)).status_code == 200
    assert (await _reimport(client, cid, "magic_initiate", ability="strength"))["feat_status"] == "incomplete"
    other = await _char14(client, "fighter")
    assert (await _take(client, other["id"], "athlete", "dexterity")).status_code == 201
    assert (await _reimport(client, other["id"], "athlete", ability="charisma"))["options"] in (None, {})


async def test_defensive_duelist_2014_needs_proficiency(client):
    ch = await _char14(client, "wizard")
    cid = ch["id"]
    assert (await _take(client, cid, "defensive_duelist")).status_code == 201
    await _weapon(client, cid, "Stocco", damage_dice="1d8", weapon_category="martial", properties=["finesse"])
    r = await client.post(f"/characters/{cid}/features/feat.defensive_duelist/use", json={})
    assert r.status_code >= 400, r.text
