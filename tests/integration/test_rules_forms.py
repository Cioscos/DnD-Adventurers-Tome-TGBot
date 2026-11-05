"""Forme selvatiche e compagni per edizione: limiti, PF, durata, statistiche della bestia, incantesimi, compagni di privilegio."""
from __future__ import annotations

from sqlalchemy import select

from core.db.models import Character
from core.rules.forms import FormRules
from core.rules.types import FeatureSpec


def beast(cr=0.25, fly=0, swim=0, type_="beast", **abil) -> dict:
    speed = {"walk_ft": 40, **({"fly_ft": fly} if fly else {}), **({"swim_ft": swim} if swim else {})}
    return {"size": "Medium", "type": type_, "challenge_rating": cr, "speed": speed,
            "abilities": {"str": 10, "dex": 10, "con": 10, **abil},
            "actions": [{"name": "Morso", "attack_bonus": 4, "damage_dice": "1d6+2", "damage_type": "piercing"}]}


async def _druid(client, level, edition="2014", subclass=None, **scores) -> int:
    cls = {"class_name": "Druido", "level": level, **({"subclass": subclass} if subclass else {})}
    r = await client.post("/characters", json={"name": "[prova] Druido", "initial_class": cls})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    if edition != "2014":
        assert (await client.patch(f"/characters/{cid}", json={"rules_edition": edition})).status_code == 200
    for op, value in (("set_max", 30), ("set_current", 30)):
        assert (await client.patch(f"/characters/{cid}/hp", json={"op": op, "value": value})).status_code == 200
    for ability, value in scores.items():
        r = await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
        assert r.status_code == 200, r.text
    return cid


async def _form(client, cid, name="Lupo", hp=11, **sb) -> int:
    r = await client.post(f"/characters/{cid}/companions", json={
        "kind": "wild_shape", "name": name, "statblock": beast(**sb), "max_hp": hp, "armor_class": 13})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _activate(client, cid, comp_id, **body):
    return await client.post(f"/characters/{cid}/companions/{comp_id}/activate", json=body)


async def _full(client, cid) -> dict:
    return (await client.get(f"/characters/{cid}")).json()


def test_form_rules_tables():
    low = FormRules("2014", 2, None)
    assert (low.max_cr, low.fly, low.swim, low.known_forms, low.rounds, low.temp_hp) == (0.25, False, False, None, 600, 0)
    assert (FormRules("2014", 4, None).max_cr, FormRules("2014", 4, None).swim) == (0.5, True)
    assert (FormRules("2014", 8, None).max_cr, FormRules("2014", 8, None).fly) == (1, True)
    assert FormRules("2014", 2, "moon").max_cr == 1 and FormRules("2014", 5, "moon").max_cr == 1
    assert FormRules("2014", 6, "moon").max_cr == 2 and FormRules("2014", 14, "moon").max_cr == 4
    assert FormRules("2014", 5, "moon").swim and not FormRules("2014", 5, "moon").fly
    assert FormRules("2014", 1, None).max_cr is None
    new = FormRules("2024", 2, None)
    assert (new.max_cr, new.swim, new.known_forms, new.temp_hp) == (0.25, True, 4, 2)
    assert FormRules("2024", 4, None).known_forms == 6 and FormRules("2024", 8, None).known_forms == 8
    assert FormRules("2024", 7, None).fly is False and FormRules("2024", 8, None).fly is True
    assert FormRules("2024", 6, "moon").max_cr == 2 and FormRules("2024", 6, "moon").temp_hp == 18


async def test_2014_form_limits_block_with_force_option(client):
    cid = await _druid(client, 2)
    for kw, reason in (({"cr": 1}, "cr"), ({"fly": 30}, "fly"), ({"swim": 30}, "swim"), ({"type_": "dragon"}, "not_beast")):
        r = await _activate(client, cid, await _form(client, cid, **kw))
        assert r.status_code == 409, (kw, r.text)
        assert r.json()["detail"]["code"] == "form_not_allowed" and reason in r.json()["detail"]["reasons"]
    assert (await _full(client, cid))["active_form"] is None
    ok = await _form(client, cid, name="Gatto")
    assert (await _activate(client, cid, ok)).status_code == 200
    bear = await _form(client, cid, name="Orso", cr=1)
    forced = await _activate(client, cid, bear, force=True)
    assert forced.status_code == 200 and forced.json()["is_active"] is True
    moon = await _druid(client, 2, subclass="Circolo della Luna")
    assert (await _activate(client, moon, await _form(client, moon, cr=1))).status_code == 200


async def test_2014_form_keeps_its_own_hp(client):
    cid = await _druid(client, 4)
    await _activate(client, cid, await _form(client, cid, hp=11))
    body = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 4})).json()
    assert body["current_hit_points"] == 30 and body["active_form"]["current_hp"] == 7
    assert body["active_form"]["own_hp"] is True and body["temp_hp"] == 0


async def test_2024_form_gives_temp_hp_and_keeps_hp(client):
    cid = await _druid(client, 5, edition="2024")
    comp = await _form(client, cid, hp=11, cr=0.5)
    r = await _activate(client, cid, comp)
    assert r.status_code == 200, r.text
    full = await _full(client, cid)
    assert full["temp_hp"] == 5 and full["current_hit_points"] == 30 and full["active_form"]["own_hp"] is False
    body = (await client.patch(f"/characters/{cid}/hp", json={"op": "damage", "value": 8})).json()
    assert body["temp_hp"] == 0 and body["current_hit_points"] == 27  # la forma non assorbe: i PF sono quelli del druido
    assert body["active_form"] is not None  # i PF temporanei finiti non la chiudono
    moon = await _druid(client, 6, edition="2024", subclass="Circolo della Luna")
    await _activate(client, moon, await _form(client, moon, cr=2, fly=0, swim=40))
    assert (await _full(client, moon))["temp_hp"] == 18


async def test_2024_known_forms_limit(client):
    cid = await _druid(client, 2, edition="2024")
    for i in range(4):
        await _form(client, cid, name=f"F{i}")
    r = await client.post(f"/characters/{cid}/companions", json={"kind": "wild_shape", "name": "F5", "statblock": beast()})
    assert r.status_code == 422 and r.json()["detail"] == "known_forms_limit"
    first = (await client.get(f"/characters/{cid}/companions")).json()[0]["id"]
    assert (await client.delete(f"/characters/{cid}/companions/{first}")).status_code == 204  # si sostituisce una forma
    assert (await client.post(f"/characters/{cid}/companions",
                              json={"kind": "wild_shape", "name": "F5", "statblock": beast()})).status_code == 201
    old = await _druid(client, 2)  # 2014: nessun limite alle forme conosciute
    for i in range(5):
        await _form(client, old, name=f"F{i}")


async def test_form_expires_and_ends_on_rest(client, test_session_factory):
    cid = await _druid(client, 4)
    comp = await _form(client, cid)
    await _activate(client, cid, comp)
    state = next(s for s in (await _full(client, cid))["active_states"] if s["key"] == "wild_shape")
    assert state["rounds_left"] == 1200 and "rest_short" in state["ends_on"] and "unconscious" in state["ends_on"]
    assert (await client.post(f"/characters/{cid}/rounds/tick")).status_code == 200
    assert next(s for s in (await _full(client, cid))["active_states"] if s["key"] == "wild_shape")["rounds_left"] == 1199
    async with test_session_factory() as s:
        char = (await s.execute(select(Character).where(Character.id == cid))).scalar_one()
        char.active_states = [{**char.active_states[0], "rounds_left": 1}]
        await s.commit()
    await client.post(f"/characters/{cid}/rounds/tick")
    full = await _full(client, cid)
    assert full["active_form"] is None and not full["active_states"]
    assert [c["is_active"] for c in (await client.get(f"/characters/{cid}/companions")).json()] == [False]
    await _activate(client, cid, comp)
    assert (await _full(client, cid))["active_form"] is not None
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "short"})).status_code == 200
    assert (await _full(client, cid))["active_form"] is None
    await _activate(client, cid, comp)
    assert (await client.post(f"/characters/{cid}/rest", json={"rest_type": "long"})).status_code == 200
    assert (await _full(client, cid))["active_form"] is None


async def test_2024_form_ends_when_incapacitated_2014_does_not(client):
    new, old = await _druid(client, 4, edition="2024"), await _druid(client, 4)
    for cid in (new, old):
        await _activate(client, cid, await _form(client, cid))
        r = await client.patch(f"/characters/{cid}/conditions", json={"conditions": {"incapacitated": True}})
        assert r.status_code == 200, r.text
    assert (await _full(client, new))["active_form"] is None
    assert (await _full(client, old))["active_form"] is not None


async def test_form_uses_beast_stats_for_physical_rolls(client):
    cid = await _druid(client, 4, strength=10, dexterity=10)
    base = await _full(client, cid)
    assert base["skill_bonuses"]["athletics"] == 0
    await _activate(client, cid, await _form(client, cid, **{"str": 18, "dex": 14}))
    full = await _full(client, cid)
    assert full["skill_bonuses"]["athletics"] == 4 and full["skill_bonuses"]["acrobatics"] == 2  # 2014: sostituisce
    assert full["initiative_bonus"] == base["initiative_bonus"] + 2
    assert full["skill_bonuses"]["perception"] == base["skill_bonuses"]["perception"]  # SAG resta del druido
    # 2024: vale il modificatore più alto fra druido e bestia
    new = await _druid(client, 4, edition="2024", strength=18, dexterity=10)
    await _activate(client, new, await _form(client, new, **{"str": 8, "dex": 16}))
    full = await _full(client, new)
    assert full["skill_bonuses"]["athletics"] == 4 and full["skill_bonuses"]["acrobatics"] == 3
    # 2014: la forma con FOR 8 abbassa anche chi ha 18
    low = await _druid(client, 4, strength=18)
    await _activate(client, low, await _form(client, low, **{"str": 8}))
    assert (await _full(client, low))["skill_bonuses"]["athletics"] == -1


async def test_spell_blocked_in_form_unless_feature(client, rules_catalog):
    cid = await _druid(client, 2)
    spell = (await client.post(f"/characters/{cid}/spells", json={"name": "Prova", "level": 0})).json()["id"]
    assert (await client.post(f"/characters/{cid}/spells/{spell}/use", json={})).status_code == 200  # fuori forma
    await _activate(client, cid, await _form(client, cid))
    r = await client.post(f"/characters/{cid}/spells/{spell}/use", json={})
    assert r.status_code == 409 and r.json()["detail"] == {"code": "cast_confirm", "warnings": ["wild_shape"]}
    assert (await client.get(f"/characters/{cid}/spells/{spell}/cast-check")).json() == ["wild_shape"]
    ok = await client.post(f"/characters/{cid}/spells/{spell}/use", json={"confirm": ["wild_shape"]})
    assert ok.status_code == 200
    rules_catalog(FeatureSpec(
        key="druid.beast_spells", class_key="druid", edition="2014", level=1, source_title="Prova",
        name={"it": "Incantesimi Bestiali", "en": "Beast Spells"}, summary={"it": "x", "en": "x"},
        action_type=None, passive=True, cast_in_form=True))
    assert (await client.get(f"/characters/{cid}/spells/{spell}/cast-check")).json() == []
    assert (await client.post(f"/characters/{cid}/spells/{spell}/use", json={})).status_code == 200


async def _ranger(client, level, edition, **scores) -> int:
    r = await client.post("/characters", json={"name": "[prova] Ranger", "initial_class": {"class_name": "Ranger", "level": level}})
    cid = r.json()["id"]
    if edition != "2014":
        await client.patch(f"/characters/{cid}", json={"rules_edition": edition})
    for ability, value in scores.items():
        await client.patch(f"/characters/{cid}/ability_scores/{ability}", json={"value": value})
    return cid


async def _companion(client, cid, key, **kw) -> dict:
    body = {"kind": "companion", "name": "Falco", "feature_key": key, "max_hp": 3, "armor_class": 13,
            "statblock": beast(), **kw}
    r = await client.post(f"/characters/{cid}/companions", json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def _read(client, cid, comp_id) -> dict:
    return next(c for c in (await client.get(f"/characters/{cid}/companions")).json() if c["id"] == comp_id)


async def test_companion_from_feature_scales_with_pb(client):
    cid = await _ranger(client, 3, "2014")  # PB +2
    comp = await _companion(client, cid, "ranger.rangers_companion")
    read = await _read(client, cid, comp["id"])
    assert read["max_hp"] == 12 and read["armor_class"] == 15 and read["attack_bonus_extra"] == 2
    assert read["damage_bonus_extra"] == 2 and read["feature_key"] == "ranger.rangers_companion"
    atk = await client.post(f"/characters/{cid}/companions/{comp['id']}/attack",
                            json={"action_index": 0, "mode": "normal", "dice": [10], "damage_rolls": [3]})
    assert atk.status_code == 200, atk.text
    assert atk.json()["to_hit_bonus"] == 6 and atk.json()["damage_total"] == 3 + 2 + 2  # dado + 2 dello statblock + PB
    class_id = (await _full(client, cid))["classes"][0]["id"]
    assert (await client.patch(f"/characters/{cid}/classes/{class_id}", json={"level": 5})).status_code == 200  # PB +3
    read = await _read(client, cid, comp["id"])
    assert read["max_hp"] == 20 and read["armor_class"] == 16 and read["attack_bonus_extra"] == 3
    # senza privilegio i valori restano quelli scritti
    plain = await _companion(client, cid, None)
    assert (await _read(client, cid, plain["id"]))["max_hp"] == 3
    assert (await client.post(f"/characters/{cid}/companions", json={
        "kind": "companion", "name": "X", "feature_key": "boh.boh", "statblock": {}})).status_code == 422


async def test_primal_companion_2024_uses_wisdom_and_level(client):
    cid = await _ranger(client, 3, "2024", wisdom=16)  # PB +2, SAG +3
    sb = beast()
    sb["actions"] = [{"name": "Colpo", "attack_bonus": 0, "damage_dice": "1d8+2", "damage_type": "slashing"}]
    comp = await _companion(client, cid, "ranger.primal_companion", statblock=sb)
    read = await _read(client, cid, comp["id"])
    assert read["max_hp"] == 20 and read["armor_class"] == 16 and read["attack_bonus_extra"] == 5  # PB + SAG, lo statblock tiene 0
    assert read["damage_bonus_extra"] == 3
