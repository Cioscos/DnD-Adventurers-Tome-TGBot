"""Punti ferita e riposi secondo l'edizione (Task 7, D8)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest


async def _char(client, *, edition="2014", cls="fighter", level=1, die=10) -> tuple[int, int]:
    r = await client.post("/characters", json={
        "name": "Riposo", "rules_edition": edition,
        "initial_class": {"class_name": cls, "level": level, "hit_die": die}})
    assert r.status_code == 201, r.text
    body = r.json()
    if edition != "2014":
        r = await client.patch(f"/characters/{body['id']}", json={"rules_edition": edition})
        assert r.status_code == 200, r.text
    return body["id"], body["classes"][0]["id"]


async def _hp(client, cid, maximum, current):
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_max", "value": maximum})
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": current})


async def _get(client, cid):
    return (await client.get(f"/characters/{cid}")).json()


async def _concentrate(client, cid):
    sp = (await client.post(f"/characters/{cid}/spells", json={
        "name": "Benedizione", "level": 1, "is_concentration": True})).json()["id"]
    await client.patch(f"/characters/{cid}/concentration", json={"spell_id": sp})


async def test_class_born_at_level_5_hp_equals_total_base_hp(client):
    cid, _ = await _char(client, level=5)
    assert (await _get(client, cid))["hit_points"] == 10 + 4 * 6


async def test_add_class_recalculates_hp(client):
    cid, _ = await _char(client)
    r = await client.post(f"/characters/{cid}/classes",
                          json={"class_name": "wizard", "level": 2, "hit_die": 6})
    assert r.status_code == 201, r.text
    # 10 (1° liv. guerriero) + 2 livelli da mago d6 (4 ciascuno)
    assert r.json()["hit_points"] == 18


async def test_update_xp_uses_effective_con(client):
    cid, _ = await _char(client)
    meta = {"ability_modifiers": [{"ability": "constitution", "kind": "absolute", "value": 14}]}
    await client.post(f"/characters/{cid}/items", json={
        "name": "Amuleto", "item_type": "accessory", "item_metadata": meta})
    iid = (await client.get(f"/characters/{cid}/items")).json()[0]["id"]
    await client.patch(f"/characters/{cid}/items/{iid}", json={"is_equipped": True})
    before = (await _get(client, cid))["hit_points"]
    r = await client.patch(f"/characters/{cid}/xp", json={"set": 300})  # liv. 2
    assert r.status_code == 200, r.text
    assert r.json()["hit_points"] - before == 6 + 2  # d10 fisso + COS effettiva +2


async def test_custom_class_without_hit_die_does_not_crash(client):
    cid, _ = await _char(client)
    r = await client.post(f"/characters/{cid}/classes",
                          json={"class_name": "Artefice Strano", "level": 1})
    assert r.status_code == 201, r.text
    custom = next(c["id"] for c in r.json()["classes"] if c["class_name"] == "Artefice Strano")
    r = await client.patch(f"/characters/{cid}/classes/{custom}", json={"level": 2})
    assert r.status_code == 200, r.text


async def test_short_rest_keeps_concentration(client):  # D8
    cid, _ = await _char(client)
    await _concentrate(client, cid)
    p = (await client.get(f"/characters/{cid}/rest/preview", params={"rest_type": "short"})).json()
    assert p["ends_concentration"] is False
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert r.json()["concentrating_spell_id"] is not None


async def test_long_rest_ends_concentration(client):  # D8
    cid, _ = await _char(client)
    await _concentrate(client, cid)
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})
    assert r.json()["concentrating_spell_id"] is None


@pytest.mark.parametrize("edition,expected", [("2014", 0), ("2024", 1)])
async def test_hit_die_minimum_zero_2014_one_2024(client, edition, expected):
    cid, cls = await _char(client, edition=edition, level=2)
    await client.patch(f"/characters/{cid}/ability_scores/constitution", json={"value": 6})  # mod -2
    await _hp(client, cid, 30, 1)
    r = await client.post(f"/characters/{cid}/hit_dice/spend",
                          json={"class_id": cls, "count": 1, "rolls": [1]})
    assert r.status_code == 200, r.text
    assert r.json()["healed"] == expected


@pytest.mark.parametrize("edition,left", [("2014", 3), ("2024", 0)])
async def test_long_rest_hit_dice_half_2014_all_2024(client, edition, left):
    cid, cls = await _char(client, edition=edition, level=6)
    await _hp(client, cid, 60, 1)
    await client.post(f"/characters/{cid}/hit_dice/spend",
                      json={"class_id": cls, "count": 6, "rolls": [1] * 6})
    p = (await client.get(f"/characters/{cid}/rest/preview", params={"rest_type": "long"})).json()
    assert p["hit_dice_regain"] == {str(cls): 6 - left}
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})
    assert r.json()["classes"][0]["hit_dice_used"] == left


async def test_long_rest_at_zero_hp_refused(client):
    cid, _ = await _char(client)
    await _hp(client, cid, 20, 0)
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})
    assert r.status_code == 409
    assert r.json()["detail"] == "rest_needs_hp"
    assert (await _get(client, cid))["current_hit_points"] == 0


@pytest.mark.parametrize("edition,hours,needs_confirm", [
    ("2014", 20, True), ("2014", 25, False), ("2024", 10, True), ("2024", 20, False)])
async def test_early_long_rest_needs_confirm(client, monkeypatch, edition, hours, needs_confirm):
    from api.routers import hp
    cid, _ = await _char(client, edition=edition)
    t0 = datetime.utcnow()
    monkeypatch.setattr(hp, "_utcnow", lambda: t0)
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})).status_code == 200
    monkeypatch.setattr(hp, "_utcnow", lambda: t0 + timedelta(hours=hours))
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})
    if needs_confirm:
        assert r.status_code == 409 and r.json()["detail"] == "long_rest_too_soon"
        r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "confirm_early": True})
    assert r.status_code == 200, r.text


async def _interrupt_setup(client, edition):
    cid, _ = await _char(client, edition=edition)
    await _hp(client, cid, 40, 5)
    await client.post(f"/characters/{cid}/abilities", json={
        "name": "Fiato", "max_uses": 1, "uses": 0, "restoration_type": "short_rest"})
    await client.post(f"/characters/{cid}/abilities", json={
        "name": "Lungo", "max_uses": 1, "uses": 0, "restoration_type": "long_rest"})
    return cid


def _uses(body, name):
    return next(a["uses"] for a in body["abilities"] if a["name"] == name)


async def test_interrupted_rest_by_edition(client):
    # 2014: riposo lungo interrotto, nessun beneficio.
    cid = await _interrupt_setup(client, "2014")
    b = (await client.post(f"/characters/{cid}/rest",
                           json={"rest_type": "long", "interrupted": True})).json()
    assert b["current_hit_points"] == 5 and _uses(b, "Fiato") == 0 and _uses(b, "Lungo") == 0
    # 2024: lungo interrotto, solo i benefici del riposo breve.
    cid = await _interrupt_setup(client, "2024")
    b = (await client.post(f"/characters/{cid}/rest",
                           json={"rest_type": "long", "interrupted": True})).json()
    assert b["current_hit_points"] == 5 and _uses(b, "Fiato") == 1 and _uses(b, "Lungo") == 0
    # 2024: breve interrotto, nessun beneficio.
    cid = await _interrupt_setup(client, "2024")
    b = (await client.post(f"/characters/{cid}/rest",
                           json={"rest_type": "short", "interrupted": True})).json()
    assert _uses(b, "Fiato") == 0
    # 2014: il breve non ha regole di interruzione.
    cid = await _interrupt_setup(client, "2014")
    b = (await client.post(f"/characters/{cid}/rest",
                           json={"rest_type": "short", "interrupted": True})).json()
    assert _uses(b, "Fiato") == 1


async def test_interrupted_long_rest_does_not_start_the_24h_clock(client):
    cid = await _interrupt_setup(client, "2024")
    await client.post(f"/characters/{cid}/rest", json={"rest_type": "long", "interrupted": True})
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})
    assert r.status_code == 200, r.text


async def test_ate_and_drank_gates_exhaustion_2014(client):
    cid, _ = await _char(client, edition="2014")
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"exhaustion": 2}})
    b = (await client.post(f"/characters/{cid}/rest",
                           json={"rest_type": "long", "ate_and_drank": False})).json()
    assert b["conditions"]["exhaustion"] == 2
    cid, _ = await _char(client, edition="2024")
    await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"exhaustion": 2}})
    b = (await client.post(f"/characters/{cid}/rest",
                           json={"rest_type": "long", "ate_and_drank": False})).json()
    assert b["conditions"]["exhaustion"] == 1


async def test_hit_die_healing_resets_death_saves(client):
    cid, cls = await _char(client, level=2)
    await _hp(client, cid, 30, 0)
    await client.patch(f"/characters/{cid}/death_saves", json={"action": "failure"})
    r = await client.post(f"/characters/{cid}/hit_dice/spend",
                          json={"class_id": cls, "count": 1, "rolls": [6]})
    assert r.status_code == 200, r.text
    body = await _get(client, cid)
    assert body["current_hit_points"] == 6
    assert body["death_saves"]["failures"] == 0


async def test_short_rest_at_zero_hp_refused_2024_allowed_2014(client):
    cid, _ = await _char(client, edition="2024")
    await _hp(client, cid, 20, 0)
    r = await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})
    assert r.status_code == 409 and r.json()["detail"] == "rest_needs_hp"
    cid, _ = await _char(client, edition="2014")
    await _hp(client, cid, 20, 0)
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})).status_code == 200


async def test_hit_die_spend_returns_homebrew_notifications(client):
    from tests.integration.homebrew.conftest import notify_rule
    cid, cls = await _char(client, level=2)
    await _hp(client, cid, 30, 1)
    r = await client.post(f"/characters/{cid}/homebrew/rules",
                          json=notify_rule("hp_healed", "Curato!", name="Cura"))
    assert r.status_code == 201, r.text
    r = await client.post(f"/characters/{cid}/hit_dice/spend",
                          json={"class_id": cls, "count": 1, "rolls": [6]})
    assert any("Curato!" in n["message"] for n in r.json()["homebrew_notifications"])


async def test_class_without_hit_die_adds_no_hp(client):
    cid, _ = await _char(client)
    r = await client.post(f"/characters/{cid}/classes",
                          json={"class_name": "Artefice Strano", "level": 3})
    assert r.status_code == 201, r.text
    assert r.json()["hit_points"] == 10


async def test_add_class_keeps_saved_hp_rolls(client):
    cid, _ = await _char(client)
    r = await client.patch(f"/characters/{cid}/xp", json={"set": 300, "hp_rolls": [10]})
    assert r.status_code == 200, r.text
    assert r.json()["hit_points"] == 20  # 10 + tiro salvato 10
    r = await client.post(f"/characters/{cid}/classes",
                          json={"class_name": "wizard", "level": 1, "hit_die": 6})
    assert r.json()["hit_points"] == 24  # il tiro salvato resta, +4 del mago
