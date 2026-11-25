"""Doni Epici 2024 dal motore (PR 2 talenti, Task 5)."""
from __future__ import annotations

from tests.integration.rules.test_2014_bard import _full, _roll_keys
from tests.integration.rules.test_feats_2024_general import STATS
from tests.integration.rules.test_feats_2024_selection import _char
from tests.integration.rules.test_feats_take_complete import _complete, _feat_rows, _take


async def _boon(client, key: str, ability: str = "constitution", class_name: str = "fighter") -> dict:
    ch = await _char(client, class_name, 19, **STATS)
    r = await _take(client, ch["id"], f"2024_boon_{key}", ability)
    assert r.status_code == 201, r.text
    return {"before": ch, "after": r.json(), "id": ch["id"]}


async def test_fortitude_hp(client):
    b = await _boon(client, "fortitude")
    assert b["after"]["computed"]["hp_max_effective"] == b["before"]["computed"]["hp_max_effective"] + 40  # Costituzione 14 -> 15: modificatore invariato


async def test_speed_and_truesight(client):
    b = await _boon(client, "speed", "dexterity")
    assert b["after"]["computed"]["speed"] == b["before"]["computed"]["speed"] + 30
    t = await _boon(client, "truesight", "wisdom")
    assert {"type": "truesight", "range_ft": 60} in t["after"]["computed"]["senses"]


async def test_energy_resistance_choice(client):
    b = await _boon(client, "energy_resistance")
    row = _feat_rows(b["after"], "2024_boon_energy_resistance")[0]
    assert row["feat_status"] == "incomplete"
    assert (await _complete(client, b["id"], row["id"], {"damage_types": ["fire", "fire"]})).status_code == 422
    assert (await _complete(client, b["id"], row["id"], {"damage_types": ["fire", "slashing"]})).status_code == 422
    r = await _complete(client, b["id"], row["id"], {"damage_types": ["fire", "cold"]})
    assert r.status_code == 200, r.text
    assert {"fire", "cold"} <= set(r.json()["computed"]["resistances"])


async def test_fate_and_combat_prowess_options(client):
    fate = await _boon(client, "fate", "charisma")
    assert "feat.2024_boon_fate" in await _roll_keys(client, fate["id"], "save", ability="wisdom")
    row = _feat_rows(fate["after"], "2024_boon_fate")[0]
    assert (row["max_uses"], row["restoration_type"]) == (1, "short_rest")
    prowess = await _boon(client, "combat_prowess", "strength")
    assert "feat.2024_boon_combat_prowess" in await _roll_keys(client, prowess["id"], "attack")


async def test_recovery_pool(client):
    b = await _boon(client, "recovery")
    row = _feat_rows(b["after"], "2024_boon_recovery")[0]
    assert (row["max_uses"], row["restoration_type"]) == (10, "long_rest")
    await client.patch(f"/characters/{b['id']}/hp", json={"op": "set_current", "value": 10})
    r = await client.post(f"/characters/{b['id']}/features/feat.2024_boon_recovery/use", json={"amount": 3})
    assert r.status_code == 200, r.text
    assert len(r.json()["rolls"]) == 3
    assert _feat_rows(await _full(client, b["id"]), "2024_boon_recovery")[0]["uses"] == 7


async def test_skill_boon(client):
    b = await _boon(client, "skill", "wisdom")
    row = _feat_rows(b["after"], "2024_boon_skill")[0]
    r = await _complete(client, b["id"], row["id"], {"expertise": "stealth"})
    assert r.status_code == 200, r.text
    skills = r.json()["skills"]
    assert skills["stealth"] == "expert" and skills["arcana"] and skills["survival"]


async def test_night_spirit_state_resistances(client):
    # PHB 2024 pag. 211: l'azione Bonus dà Invisibile (Fondersi con le ombre) e niente resistenze; Forma d'ombra è un
    # interruttore senza azione (luce dichiarata dal giocatore), resistenze tranne psichico e radioso
    b = await _boon(client, "night_spirit", "dexterity")
    r = await client.post(f"/characters/{b['id']}/features/feat.2024_boon_night_spirit/use", json={"params": {"mode": "blend"}})
    assert r.status_code == 200, r.text
    full = await _full(client, b["id"])
    assert full["conditions"].get("invisible") and not full["computed"]["resistances"]
    r = await client.post(f"/characters/{b['id']}/features/feat.2024_boon_night_spirit/use", json={"params": {"mode": "form"}})
    assert r.status_code == 200, r.text
    res = set((await _full(client, b["id"]))["computed"]["resistances"])
    assert {"fire", "slashing", "necrotic"} <= res and "psychic" not in res and "radiant" not in res


# --- Ultima resistenza, Cure extra, Reindirizzamento, Colpo travolgente -------------------------------------------------

LAST_STAND = "feat.2024_boon_recovery_last_stand"


async def _hp_now(client, cid) -> int:
    return (await _full(client, cid))["current_hit_points"]


async def _hurt(client, cid, value, *options):
    return await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": value, "options": list(options)})


async def test_boon_of_recovery_last_stand(client):
    from tests.integration.rules.test_2014_paladin import _rest
    b = await _boon(client, "recovery")
    cid = b["id"]
    top = (await _full(client, cid))["computed"]["hp_max_effective"]
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": top})
    assert LAST_STAND in await _roll_keys(client, cid, "damage_taken")  # subito dopo il Dono, senza riposo
    r = await _hurt(client, cid, top + 5, LAST_STAND)  # sotto la soglia del danno massiccio: resta a 1 PF e cura metà del massimo
    assert r.status_code == 200, r.text
    assert await _hp_now(client, cid) == 1 + top // 2
    assert LAST_STAND not in await _roll_keys(client, cid, "damage_taken")  # una volta per riposo lungo
    assert (await _hurt(client, cid, 1, LAST_STAND)).status_code == 409
    await _rest(client, cid, "long")
    assert LAST_STAND in await _roll_keys(client, cid, "damage_taken")


async def test_boon_of_recovery_last_stand_is_not_spent_if_the_damage_does_not_reach_zero(client):
    b = await _boon(client, "recovery")
    cid = b["id"]
    top = (await _full(client, cid))["computed"]["hp_max_effective"]
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": top})
    assert (await _hurt(client, cid, 3, LAST_STAND)).status_code == 200
    assert await _hp_now(client, cid) == top - 3
    assert LAST_STAND in await _roll_keys(client, cid, "damage_taken")


async def test_boon_of_fortitude_extra_healing_button(client):
    b = await _boon(client, "fortitude")
    cid = b["id"]
    row = _feat_rows(await _full(client, cid), "2024_boon_fortitude")[0]
    assert row["has_on_use"] and not row["is_passive"]
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": 10})
    r = await client.post(f"/characters/{cid}/features/feat.2024_boon_fortitude/use", json={})
    assert r.status_code == 200, r.text
    con = next(s for s in (await _full(client, cid))["ability_scores"] if s["name"] == "constitution")["modifier"]
    assert await _hp_now(client, cid) == 10 + con
    again = await client.post(f"/characters/{cid}/features/feat.2024_boon_fortitude/use", json={})
    assert again.status_code == 409 and "once_per_turn" in again.text


async def test_boon_of_energy_resistance_redirect(client):
    b = await _boon(client, "energy_resistance")
    cid = b["id"]
    row = _feat_rows(b["after"], "2024_boon_energy_resistance")[0]
    assert (await _complete(client, cid, row["id"], {"damage_types": ["fire", "cold"]})).status_code == 200
    key = "feat.2024_boon_energy_resistance_redirect"
    assert key in await _roll_keys(client, cid, "damage_taken", damage_type="fire")
    assert key not in await _roll_keys(client, cid, "damage_taken", damage_type="acid")
    r = await client.get(f"/characters/{cid}/roll-options", params={"roll": "damage_taken", "damage_type": "fire"})
    assert next(o for o in r.json() if o["key"] == key)["slot"] == "reaction"
    top = (await _full(client, cid))["computed"]["hp_max_effective"]
    await client.patch(f"/characters/{cid}/hp", json={"op": "set_current", "value": top})
    hit = await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 10, "damage_type": "fire", "options": [key]})
    assert hit.status_code == 200, hit.text
    con = next(s for s in (await _full(client, cid))["ability_scores"] if s["name"] == "constitution")["modifier"]
    effect = hit.json()["option_result"]["effects"][0]["it"]
    assert f"CD {8 + con + 6}" in effect and "2d12" in effect  # competenza +6 al 19°


async def test_boon_of_irresistible_offense_on_natural_20(client):
    from tests.integration.rules.test_2014_fighter_styles import _item
    from tests.integration.rules.test_2014_rogue import _damage, _hit
    b = await _boon(client, "irresistible_offense", "strength")
    cid = b["id"]
    wid = await _item(client, cid, "Spada", damage_dice="1d8", weapon_type="melee", properties=[], equip="main_hand")
    key = "feat.2024_boon_irresistible_offense_strike"
    score = next(s for s in (await _full(client, cid))["ability_scores"] if s["name"] == "strength")["value"]
    plain = await _hit(client, cid, wid, die=20)
    with_boon = await _damage(client, cid, plain, key)
    assert with_boon.status_code == 200, with_boon.text
    other = await _hit(client, cid, wid, die=20)
    without = await _damage(client, cid, other)
    assert with_boon.json()["damage_bonus"] - without.json()["damage_bonus"] == score
    miss = await _hit(client, cid, wid, die=15)
    assert (await _damage(client, cid, miss, key)).status_code == 409
