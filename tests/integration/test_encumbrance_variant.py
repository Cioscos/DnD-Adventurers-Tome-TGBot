"""Ingombro dettagliato: peso delle monete e variante a soglie FOR x5 / FOR x10."""
from __future__ import annotations


async def _setup(client, strength: int = 10) -> int:
    r = await client.post("/characters", json={"name": "Portatore"})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    r = await client.patch(f"/characters/{cid}/ability_scores/strength", json={"value": strength})
    assert r.status_code == 200, r.text
    return cid


async def _add_weight(client, cid: int, weight: float) -> None:
    r = await client.post(
        f"/characters/{cid}/items",
        json={"name": "Zavorra", "item_type": "generic", "weight": weight},
    )
    assert r.status_code == 201, r.text


async def _settings(client, cid: int, **kw) -> None:
    r = await client.patch(f"/characters/{cid}", json={"settings": kw})
    assert r.status_code == 200, r.text


async def _get(client, cid: int) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


async def test_coin_weight_counts_when_enabled(client):
    cid = await _setup(client)
    await _add_weight(client, cid, 10)
    r = await client.patch(f"/characters/{cid}/currency", json={"gold": 60, "copper": 40})
    assert r.status_code == 200, r.text
    assert (await _get(client, cid))["encumbrance_total"] == 10
    await _settings(client, cid, coin_weight=True)
    body = await _get(client, cid)
    assert body["encumbrance_total"] == 12  # 10 + 100 monete / 50
    assert body["encumbrance"] == 10  # resta solo oggetti


async def test_variant_thresholds_and_speed_penalty(client):
    cid = await _setup(client, strength=10)  # soglie 50 / 100
    await _settings(client, cid, encumbrance_variant=True)
    body = await _get(client, cid)
    assert (body["encumbrance_level"], body["speed_encumbrance_penalty_ft"]) == ("none", 0)
    await _add_weight(client, cid, 51)
    body = await _get(client, cid)
    assert (body["encumbrance_level"], body["speed_encumbrance_penalty_ft"]) == ("encumbered", 10)
    await _add_weight(client, cid, 50)
    body = await _get(client, cid)
    assert (body["encumbrance_level"], body["speed_encumbrance_penalty_ft"]) == ("heavily", 20)


async def _weapon(client, cid: int) -> int:
    r = await client.post(f"/characters/{cid}/items", json={
        "name": "Spada", "item_type": "weapon",
        "item_metadata": {"damage_dice": "1d8", "weapon_type": "melee", "properties": []}})
    assert r.status_code == 201, r.text
    return next(i["id"] for i in r.json()["items"] if i["name"] == "Spada")


async def _rolls(client, cid: int) -> dict[str, dict]:
    """Prova di For, TS di Cos e attacco con arma di Forza; prova di Int e TS di Sag per confronto."""
    weapon = await _weapon(client, cid)
    posts = {
        "athletics": f"/characters/{cid}/skills/athletics/roll",
        "save_con": f"/characters/{cid}/saving_throws/constitution/roll",
        "attack": f"/characters/{cid}/items/{weapon}/attack",
        "arcana": f"/characters/{cid}/skills/arcana/roll",
        "save_wis": f"/characters/{cid}/saving_throws/wisdom/roll",
    }
    out = {}
    for name, url in posts.items():
        r = await client.post(url)
        assert r.status_code == 200, (name, r.text)
        out[name] = r.json()
    return out


async def test_heavily_encumbered_disadvantage_on_str_dex_con_rolls(client):
    cid = await _setup(client, strength=10)  # soglie 50 / 100
    await _settings(client, cid, encumbrance_variant=True)
    await _add_weight(client, cid, 101)
    rolls = await _rolls(client, cid)
    for name in ("athletics", "save_con", "attack"):  # 2014 p.176: prove, TS e attacchi con For, Des o Cos
        assert rolls[name]["mode_applied"] == "disadvantage" and "encumbrance:heavily" in rolls[name]["notes"], name
    for name in ("arcana", "save_wis"):
        assert rolls[name]["mode_applied"] == "normal" and "encumbrance:heavily" not in rolls[name]["notes"], name


async def test_heavily_encumbered_disadvantage_on_initiative(client, test_session_factory):
    from core.db.models import Character, Item
    from tests.integration._encounter_helpers import GM_ID, PLAYER_ID, as_user, seed_session
    sid, cid = await seed_session(test_session_factory)
    async with test_session_factory() as s:
        (await s.get(Character, cid)).settings = {"encumbrance_variant": True}
        s.add(Item(character_id=cid, name="Zavorra", item_type="generic", weight=101, quantity=1))
        await s.commit()
    as_user(GM_ID)
    r = await client.post(f"/sessions/{sid}/encounter", json={"mode": "full"})
    assert r.status_code == 201, r.text
    pc = next(c for c in r.json()["combatants"] if c["kind"] == "pc")
    as_user(PLAYER_ID)
    r = await client.post(f"/sessions/{sid}/encounter/combatants/{pc['id']}/initiative", json={"die": 3})
    assert r.status_code == 200, r.text
    assert r.json()["initiative_roll"]["mode_applied"] == "disadvantage"
    assert "encumbrance:heavily" in r.json()["initiative_roll"]["notes"]


async def test_encumbered_only_speed(client):
    cid = await _setup(client, strength=10)
    await _settings(client, cid, encumbrance_variant=True)
    await _add_weight(client, cid, 60)  # fra x5 e x10: solo la velocità
    for roll in (await _rolls(client, cid)).values():
        assert roll["mode_applied"] == "normal" and "encumbrance:heavily" not in roll["notes"]


async def test_variant_off_no_disadvantage(client):
    cid = await _setup(client, strength=10)
    await _add_weight(client, cid, 101)
    for roll in (await _rolls(client, cid)).values():
        assert roll["mode_applied"] == "normal" and "encumbrance:heavily" not in roll["notes"]


async def test_coin_weight_counts_in_roll_routes(client):
    cid = await _setup(client, strength=10)
    await _settings(client, cid, encumbrance_variant=True, coin_weight=True)
    await _add_weight(client, cid, 90)
    assert (await client.patch(f"/characters/{cid}/currency", json={"gold": 600})).status_code == 200  # +12 lb: 102 > 100
    rolls = await _rolls(client, cid)  # 200 su tutte (nessun caricamento pigro mancante)
    assert all("encumbrance:heavily" in rolls[n]["notes"] for n in ("athletics", "save_con", "attack"))


async def test_other_d20_routes_load_what_encumbrance_needs(client, test_session_factory):
    """Variante e peso delle monete accesi, oltre For x10: concentrazione, TS in sospeso, iniziativa fuori incontro,
    attacco di un compagno in forma e attacco con incantesimo non devono dare 500 (nessun caricamento pigro)."""
    from core.db.models import PendingSave
    from api.services.condition_effects import SaveSpec, upsert_effect
    cid = await _setup(client, strength=10)
    assert (await client.post(f"/characters/{cid}/classes", json={"class_name": "fighter", "level": 1, "hit_die": 10})).status_code == 201  # PF > 0
    await _settings(client, cid, encumbrance_variant=True, coin_weight=True)
    await _add_weight(client, cid, 90)
    assert (await client.patch(f"/characters/{cid}/currency", json={"gold": 600})).status_code == 200
    heavy = "encumbrance:heavily"

    body = (await client.post(f"/characters/{cid}/concentration/save", json={"damage": 10})).json()
    assert body["mode_applied"] == "disadvantage" and heavy in body["notes"]  # TS di Costituzione

    r = await client.post(f"/characters/{cid}/dice/initiative")
    assert r.status_code == 200, r.text
    assert r.json()["mode_applied"] == "disadvantage" and heavy in r.json()["notes"]

    r = await client.post(f"/characters/{cid}/companions", json={
        "kind": "wild_shape", "name": "Lupo", "max_hp": 10, "armor_class": 13,
        "statblock": {"actions": [{"name": "Morso", "attack_bonus": 4, "damage_dice": "1d6"}]}})
    comp = r.json()["id"]
    r = await client.post(f"/characters/{cid}/companions/{comp}/activate")
    assert r.status_code == 200, r.text
    r = await client.post(f"/characters/{cid}/companions/{comp}/attack", json={"action_index": 0})
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "disadvantage" and heavy in r.json()["notes"]

    assert (await client.post(f"/characters/{cid}/companions/{comp}/deactivate")).status_code == 200  # in forma non si lancia
    r = await client.post(f"/characters/{cid}/spells", json={"name": "Dardo", "level": 0, "attack_save": "ATK"})
    sid = r.json()["id"]
    r = await client.post(f"/characters/{cid}/spells/{sid}/attack", json={"slot_level": None})
    assert r.status_code == 200, r.text  # senza caratteristica nel tiro: nessun svantaggio

    assert (await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"stunned": True}})).status_code == 200
    async with test_session_factory() as s:
        eff = await upsert_effect(s, ("character", cid), "stunned", save=SaveSpec("dexterity", 10, "end"))
        ps = PendingSave(effect_id=eff.id, character_id=cid, ability="dexterity", dc=10, status="pending",
                         created_at="2026-11-04T00:00:00")
        s.add(ps)
        await s.commit()
        psid = ps.id
    r = await client.post(f"/characters/{cid}/pending-saves/{psid}/roll", json={"die": 15})
    assert r.status_code == 200, r.text
    assert heavy in r.json()["roll"]["notes"]



async def test_defaults_unchanged(client):
    cid = await _setup(client, strength=10)
    await _add_weight(client, cid, 120)
    await client.patch(f"/characters/{cid}/currency", json={"gold": 500})
    body = await _get(client, cid)
    assert body["encumbrance_total"] == body["encumbrance"] == 120
    assert body["encumbrance_level"] == "none"
    assert body["speed_encumbrance_penalty_ft"] == 0
