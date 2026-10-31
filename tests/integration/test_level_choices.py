"""Level-up choices (ASI / feat): creation rules, resolve endpoint, feat effects."""
from __future__ import annotations

from tests.integration.conftest import TEST_USER_ID


async def _fighter(client, level: int = 1, scores: dict | None = None) -> dict:
    body = {"name": "Eroe", "initial_class": {"class_name": "Guerriero", "level": level, "hit_die": 10}}
    if scores:
        body["ability_scores"] = scores
    r = await client.post("/characters", json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def _to_level_4(client) -> dict:
    ch = await _fighter(client, scores={"strength": 19, "dexterity": 14, "constitution": 12,
                                        "intelligence": 10, "wisdom": 10, "charisma": 10})
    r = await client.patch(f"/characters/{ch['id']}/xp", json={"set": 2700})
    assert r.status_code == 200, r.text
    return r.json()


def _score(body: dict, name: str) -> int:
    return next(s for s in body["ability_scores"] if s["name"] == name)["value"]


async def _resolve(client, body: dict, payload: dict):
    cid = body["pending_choices"][0]["id"]
    return await client.post(f"/characters/{body['id']}/choices/{cid}/resolve", json=payload)


async def test_level_up_to_4_creates_choice_via_xp(client):
    body = await _to_level_4(client)
    assert len(body["pending_choices"]) == 1
    c = body["pending_choices"][0]
    assert c["kind"] == "asi" and c["level"] == 4 and c["class_key"] == "Guerriero" and c["id"]
    # idempotent: same level again does not duplicate
    r = await client.patch(f"/characters/{body['id']}/xp", json={"set": 2700})
    assert len(r.json()["pending_choices"]) == 1


async def test_level_up_creates_choice_via_distribute(client):
    ch = await _fighter(client)
    r = await client.post(f"/characters/{ch['id']}/classes",
                          json={"class_name": "Ladro", "level": 1, "hit_die": 8})
    rogue = next(c["id"] for c in r.json()["classes"] if c["class_name"] == "Ladro")
    await client.patch(f"/characters/{ch['id']}/xp", json={"set": 6500})
    r = await client.patch(f"/characters/{ch['id']}/classes/distribute", json={"classes": [
        {"class_id": ch["classes"][0]["id"], "level": 4}, {"class_id": rogue, "level": 1}]})
    assert r.status_code == 200, r.text
    assert [(c["class_key"], c["level"]) for c in r.json()["pending_choices"]] == [("Guerriero", 4)]


async def test_fighter_has_extra_asi_at_6(client):
    ch = await _fighter(client)
    r = await client.patch(f"/characters/{ch['id']}/xp", json={"set": 14000})  # level 6
    assert [c["level"] for c in r.json()["pending_choices"]] == [4, 6]


async def test_no_choice_on_creation_or_add_class(client):
    ch = await _fighter(client, level=8)
    assert ch["pending_choices"] == []
    r = await client.post(f"/characters/{ch['id']}/classes",
                          json={"class_name": "Ladro", "level": 8, "hit_die": 8})
    assert r.json()["pending_choices"] == []


async def test_resolve_asi_caps_20(client):
    body = await _to_level_4(client)  # STR 19
    r = await _resolve(client, body, {"kind": "asi", "increases": {"strength": 2}})
    assert r.status_code == 422
    r = await _resolve(client, body, {"kind": "asi", "increases": {"strength": 1, "dexterity": 2}})
    assert r.status_code == 422  # sum must be 2
    r = await _resolve(client, body, {"kind": "asi", "increases": {"strength": 1, "dexterity": 1}})
    assert r.status_code == 200, r.text
    out = r.json()
    assert _score(out, "strength") == 20 and _score(out, "dexterity") == 15
    assert out["pending_choices"] == []
    h = await client.get(f"/characters/{body['id']}/history")
    assert any("Scelta di livello" in e["description"] for e in h.json())


async def test_resolve_feat_alert_adds_initiative(client):
    body = await _to_level_4(client)
    before = body["initiative_bonus"]
    r = await _resolve(client, body, {"kind": "feat", "feat_key": "alert"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["initiative_bonus"] == before + 5
    assert out["pending_choices"] == []
    h = await client.get(f"/characters/{body['id']}/homebrew/rules")
    assert [x["template_id"] for x in h.json()] == ["feat:alert"]
    assert any(a["feature_key"] == "feat.alert" for a in out["abilities"])


async def test_resolve_feat_tough_scales_with_level(client):
    body = await _to_level_4(client)
    r = await _resolve(client, body, {"kind": "feat", "feat_key": "tough"})
    assert r.json()["hp_max_homebrew_modifier"] == 2 * 4
    r = await client.patch(f"/characters/{body['id']}/xp", json={"set": 6500})
    assert r.json()["hp_max_homebrew_modifier"] == 2 * 5


async def test_resolve_feat_observant_passives(client):
    body = await _to_level_4(client)
    r = await _resolve(client, body, {"kind": "feat", "feat_key": "observant", "ability": "wisdom"})
    assert r.status_code == 200, r.text
    assert _score(r.json(), "wisdom") == 11
    rules = (await client.get(f"/characters/{body['id']}/homebrew/rules")).json()
    targets = {m["target"] for m in rules[0]["dsl"]["passive_modifiers"]}
    assert targets == {"character.passive.perception", "character.passive.investigation"}


async def test_observant_requires_valid_ability(client):
    body = await _to_level_4(client)
    r = await _resolve(client, body, {"kind": "feat", "feat_key": "observant", "ability": "strength"})
    assert r.status_code == 422
    r = await _resolve(client, body, {"kind": "feat", "feat_key": "observant"})
    assert r.status_code == 422


async def test_resolve_resilient_sets_save_proficiency(client):
    body = await _to_level_4(client)
    r = await _resolve(client, body, {"kind": "feat", "feat_key": "resilient", "ability": "dexterity"})
    out = r.json()
    assert out["saving_throws"]["dexterity"] is True and _score(out, "dexterity") == 15


async def test_feat_lucky_counter_war_caster_setting(client):
    body = await _to_level_4(client)
    await client.patch(f"/characters/{body['id']}", json={"settings": {"keep": 1}})
    r = await _resolve(client, body, {"kind": "feat", "feat_key": "lucky"})
    ab = next(a for a in r.json()["abilities"] if a["feature_key"] == "feat.lucky")
    assert ab["max_uses"] == 3 and ab["restoration_type"] == "long_rest"
    r = await client.patch(f"/characters/{body['id']}/xp", json={"set": 23000})  # level 8
    r = await _resolve(client, r.json(), {"kind": "feat", "feat_key": "war_caster"})
    assert r.json()["settings"]["war_caster"] is True and r.json()["settings"]["keep"] == 1


def _feat_ab(body: dict, key: str) -> dict:
    return next(a for a in body["abilities"] if a["feature_key"] == f"feat.{key}")


async def _take(client, body: dict, key: str, **extra) -> dict:
    r = await _resolve(client, body, {"kind": "feat", "feat_key": key, **extra})
    assert r.status_code == 200, r.text
    return r.json()


async def test_delete_feat_removes_rule_and_ability(client):
    body = await _to_level_4(client)
    out = await _take(client, body, "alert")
    assert out["initiative_bonus"] == body["initiative_bonus"] + 5
    r = await client.delete(f"/characters/{body['id']}/feats/{_feat_ab(out, 'alert')['id']}")
    assert r.status_code == 200, r.text
    assert r.json()["initiative_bonus"] == body["initiative_bonus"]
    assert not [a for a in r.json()["abilities"] if a["feature_key"] == "feat.alert"]
    assert (await client.get(f"/characters/{body['id']}/homebrew/rules")).json() == []
    h = await client.get(f"/characters/{body['id']}/history")
    assert any("Talento rimosso" in e["description"] for e in h.json())


async def test_delete_feat_by_rule(client):
    body = await _to_level_4(client)
    await _take(client, body, "alert")
    rid = (await client.get(f"/characters/{body['id']}/homebrew/rules")).json()[0]["id"]
    r = await client.delete(f"/characters/{body['id']}/feats/by-rule/{rid}")
    assert r.status_code == 200 and r.json()["initiative_bonus"] == body["initiative_bonus"]


async def test_remove_war_caster_clears_setting(client):
    body = await _to_level_4(client)
    out = await _take(client, body, "war_caster")
    assert out["settings"]["war_caster"] is True
    r = await client.delete(f"/characters/{body['id']}/feats/{_feat_ab(out, 'war_caster')['id']}")
    assert "war_caster" not in (r.json()["settings"] or {})


async def test_remove_lucky_deletes_counter(client):
    body = await _to_level_4(client)
    out = await _take(client, body, "lucky")
    r = await client.delete(f"/characters/{body['id']}/feats/{_feat_ab(out, 'lucky')['id']}")
    assert r.status_code == 200
    assert not [a for a in r.json()["abilities"] if a["feature_key"] == "feat.lucky"]


async def test_remove_feat_other_user_403(client, test_session_factory):
    from core.db.models import Character
    body = await _to_level_4(client)
    out = await _take(client, body, "grappler")
    async with test_session_factory() as s:
        (await s.get(Character, body["id"])).user_id = TEST_USER_ID + 1
        await s.commit()
    r = await client.delete(f"/characters/{body['id']}/feats/{_feat_ab(out, 'grappler')['id']}")
    assert r.status_code == 403


async def test_same_feat_twice_422(client):
    body = await _to_level_4(client)
    await _take(client, body, "alert")
    out = (await client.patch(f"/characters/{body['id']}/xp", json={"set": 23000})).json()
    r = await _resolve(client, out, {"kind": "feat", "feat_key": "alert"})
    assert r.status_code == 422 and "feat_already_taken" in r.text


async def test_custom_feat(client):
    body = await _to_level_4(client)
    r = await _resolve(client, body, {"kind": "feat", "feat_key": "custom",
                                      "custom_name": "Mio talento", "custom_text": "Fa cose."})
    assert r.status_code == 200, r.text
    assert any(a["name"] == "Mio talento" and a["is_passive"] for a in r.json()["abilities"])
    body2 = await _to_level_4(client)
    r = await _resolve(client, body2, {"kind": "feat", "feat_key": "custom"})
    assert r.status_code == 422


async def test_choice_other_user_403(client, test_session_factory):
    from core.db.models import Character
    body = await _to_level_4(client)
    async with test_session_factory() as s:
        c = await s.get(Character, body["id"])
        c.user_id = TEST_USER_ID + 1
        await s.commit()
    cid = body["pending_choices"][0]["id"]
    r = await client.post(f"/characters/{body['id']}/choices/{cid}/resolve",
                          json={"kind": "asi", "increases": {"strength": 1, "dexterity": 1}})
    assert r.status_code == 403


async def test_unknown_choice_404(client):
    body = await _to_level_4(client)
    r = await client.post(f"/characters/{body['id']}/choices/nope/resolve",
                          json={"kind": "asi", "increases": {"strength": 1, "dexterity": 1}})
    assert r.status_code == 404


async def test_pending_choices_roundtrip_export_import(client):
    body = await _to_level_4(client)
    exp = (await client.get(f"/characters/{body['id']}/export")).json()
    assert exp["character"]["pending_choices"] == body["pending_choices"]
    r = await client.post("/characters/import", json=exp)
    assert r.status_code in (200, 201), r.text
    assert r.json()["pending_choices"] == body["pending_choices"]
