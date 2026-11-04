"""Task 5: scelte di livello (ASI, talento, Dono Epico) e opzioni di classe."""
from __future__ import annotations

from core.data.feats_2024 import FEATS_2024
from core.rules.types import ChoiceSpec, FeatureSpec

SCORES = {"strength": 16, "dexterity": 14, "constitution": 12, "intelligence": 10, "wisdom": 10, "charisma": 10}


async def _char(client, cls="Guerriero", level=1, edition="2014", xp=None) -> dict:
    r = await client.post("/characters", json={
        "name": "Eroe", "ability_scores": SCORES,
        "initial_class": {"class_name": cls, "level": level, "hit_die": 10}})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    if edition != "2014":
        await client.patch(f"/characters/{cid}", json={"rules_edition": edition})
    if xp is not None:
        r = await client.patch(f"/characters/{cid}/xp", json={"set": xp})
        assert r.status_code == 200, r.text
        return r.json()
    return (await client.get(f"/characters/{cid}")).json()


def _pending(body: dict, kind: str | None = None) -> list[tuple]:
    return [(c["kind"], c["level"]) for c in body["pending_choices"] if kind in (None, c["kind"])]


async def _resolve(client, body: dict, kind: str, payload: dict):
    cid = next(c["id"] for c in body["pending_choices"] if c["kind"] == kind)
    return await client.post(f"/characters/{body['id']}/choices/{cid}/resolve", json={"kind": kind, **payload})


def _trick(ctx_options=("a", "b", "c", "d")) -> tuple[FeatureSpec, ...]:
    def spec(key, **kw):
        return FeatureSpec(key=f"barbarian.{key}", class_key="barbarian", edition="2014", level=3,
                           source_title=key, name={"it": key, "en": key}, summary={"it": key, "en": key},
                           action_type=None, **kw)
    return (spec("trick", choices=(ChoiceSpec("trick", {3: 2, 5: 3}, lambda ctx: list(ctx_options)),)),
            *(spec(f"trick_{o}", option_group="trick", option_key=o) for o in ctx_options))


async def test_asi_created_when_class_born_above_level_1(client):
    body = await _char(client)
    r = await client.post(f"/characters/{body['id']}/classes", json={"class_name": "Barbaro", "level": 8, "hit_die": 12})
    assert r.status_code in (200, 201), r.text
    assert _pending(r.json(), "asi") == [("asi", 4), ("asi", 8)]


async def test_level_down_removes_pending_above_level(client):
    body = await _char(client, xp=14000)  # guerriero livello 6: ASI a 4 e 6
    assert _pending(body) == [("asi", 4), ("asi", 6)]
    r = await client.patch(f"/characters/{body['id']}/xp", json={"set": 2700})
    assert _pending(r.json()) == [("asi", 4)]


async def test_resolved_level_is_not_offered_again(client):
    body = await _char(client, xp=2700)
    r = await _resolve(client, body, "asi", {"increases": {"strength": 2}})
    assert r.status_code == 200 and r.json()["pending_choices"] == []
    await client.patch(f"/characters/{body['id']}/xp", json={"set": 300})  # livello 2
    r = await client.patch(f"/characters/{body['id']}/xp", json={"set": 2700})
    assert r.json()["pending_choices"] == []


async def test_2024_level_19_creates_epic_boon_not_asi(client):
    body = await _char(client, edition="2024", xp=305000)
    assert _pending(body) == [("asi", 4), ("asi", 6), ("asi", 8), ("asi", 12), ("asi", 14), ("asi", 16),
                              ("epic_boon", 19)]
    mage = await _char(client, "Mago", edition="2024", xp=305000)
    assert _pending(mage) == [("asi", 4), ("asi", 8), ("asi", 12), ("asi", 16), ("epic_boon", 19)]
    old = await _char(client, xp=305000)  # 2014: l'ASI a 19 resta
    assert ("asi", 19) in _pending(old) and ("epic_boon", 19) not in _pending(old)


async def test_epic_boon_checks_prerequisites_and_is_text_only(client):  # D3
    body = await _char(client, edition="2024", xp=305000)
    hp = body["hit_points"]
    # prerequisito di incantatore: il Fighter non lancia incantesimi
    r = await _resolve(client, body, "epic_boon", {"feat_key": "2024_boon_spell_recall", "ability": "intelligence"})
    assert r.status_code == 422
    # un Dono Epico non si prende come talento da ASI
    r = await _resolve(client, body, "asi", {"increases": {"strength": 2}})
    assert r.status_code == 200
    body = r.json()
    r = await client.post(f"/characters/{body['id']}/choices/{body['pending_choices'][0]['id']}/resolve",
                          json={"kind": "feat", "feat_key": "2024_boon_fate", "ability": "strength"})
    assert r.status_code == 422
    # un talento generale non si prende come Dono Epico
    r = await _resolve(client, body, "epic_boon", {"feat_key": "2024_actor", "ability": "charisma"})
    assert r.status_code == 422
    # Dono di un'altra edizione
    r = await _resolve(client, body, "epic_boon", {"feat_key": "lucky", "ability": None})
    assert r.status_code == 422
    r = await _resolve(client, body, "epic_boon", {"feat_key": "2024_boon_fortitude", "ability": "strength"})
    assert r.status_code == 200, r.text
    done = r.json()
    assert ("epic_boon", 19) not in _pending(done)
    assert next(s for s in done["ability_scores"] if s["name"] == "strength")["value"] == 19
    assert done["hit_points"] == hp  # nessun effetto: +40 PF restano testo
    feat = next(a for a in done["abilities"] if a["feature_key"] == "feat.2024_boon_fortitude")
    assert feat["is_passive"] and feat["description"]
    assert done.get("homebrew_rules", []) == []


async def test_general_feat_checks_ability_prerequisite(client):
    body = await _char(client, edition="2024", xp=2700)
    pick = {"feat_key": "2024_actor", "ability": "charisma"}  # Carisma 10 < 13
    cid = body["pending_choices"][0]["id"]
    r = await client.post(f"/characters/{body['id']}/choices/{cid}/resolve", json={"kind": "feat", **pick})
    assert r.status_code == 422
    r = await client.post(f"/characters/{body['id']}/choices/{cid}/resolve",
                          json={"kind": "feat", "feat_key": "2024_athlete", "ability": "strength"})
    assert r.status_code == 200, r.text


async def test_class_option_rejects_unknown_key_and_wrong_count(client, rules_catalog):
    rules_catalog(*_trick())
    body = await _char(client, "Barbaro", xp=900)
    assert [(c["group"], c["count"], c["level"]) for c in body["pending_choices"] if c["kind"] == "class_option"] \
        == [("trick", 2, 3)]
    opt = next(c for c in body["pending_choices"] if c["kind"] == "class_option")
    assert [o["key"] for o in opt["options"]] == ["a", "b", "c", "d"]
    for picked in (["a"], ["a", "b", "c"], ["a", "zzz"], ["a", "a"]):
        assert (await _resolve(client, body, "class_option", {"options": picked})).status_code == 422
    r = await _resolve(client, body, "class_option", {"options": ["a", "b"]})
    assert r.status_code == 200, r.text
    done = r.json()
    assert done["classes"][0]["options"] == {"trick": ["a", "b"]}
    keys = {a["feature_key"] for a in done["abilities"]}
    assert {"barbarian.trick_a", "barbarian.trick_b"} <= keys and "barbarian.trick_c" not in keys
    # al livello 5 ne arriva una sola in più, fra quelle non ancora scelte
    r = await client.patch(f"/characters/{body['id']}/xp", json={"set": 6500})
    nxt = next(c for c in r.json()["pending_choices"] if c["kind"] == "class_option")
    assert nxt["count"] == 1 and [o["key"] for o in nxt["options"]] == ["c", "d"]
    assert (await _resolve(client, r.json(), "class_option", {"options": ["a"]})).status_code == 422


async def test_class_option_survives_export_import(client, rules_catalog):
    rules_catalog(*_trick())
    body = await _char(client, "Barbaro", xp=900)
    r = await _resolve(client, body, "class_option", {"options": ["b", "d"]})
    assert r.status_code == 200
    exported = (await client.get(f"/characters/{body['id']}/export")).json()
    assert exported["classes"][0]["options"] == {"trick": ["b", "d"]}
    r = await client.post("/characters/import", json=exported)
    assert r.status_code in (200, 201), r.text
    assert r.json()["classes"][0]["options"] == {"trick": ["b", "d"]}
    exported["classes"][0]["options"] = {"trick": ["b"] * 500, "x" * 80: "no"}  # file artefatto
    assert (await client.post("/characters/import", json=exported)).status_code == 422
    # i nuovi tipi di scelta passano la validazione dell'export
    pending = {"id": "p1", "kind": "epic_boon", "class_key": "Guerriero", "level": 19}
    exported["classes"][0]["options"] = {}
    exported["character"]["pending_choices"] = [pending, {**pending, "id": "p2", "kind": "class_option",
                                                          "group": "trick", "count": 2}]
    assert (await client.post("/characters/import", json=exported)).status_code in (200, 201)


def test_2024_feat_catalog_is_text_only_and_bounded():
    assert len(FEATS_2024) == 54 and len({f.key for f in FEATS_2024}) == 54
    for f in FEATS_2024:
        assert f.edition == "2024" and f.passive_modifiers == [] and f.counter is None and f.setting is None
        assert all(len(t) <= 200 for t in f.summary.values()) and f.name["it"] and f.name["en"]
    assert sum(f.category == "epic_boon" for f in FEATS_2024) == 12


def test_frontend_feat_mirror_is_up_to_date():
    import json
    from scripts.export_feats_2024 import TARGET, build
    assert json.loads(TARGET.read_text(encoding="utf-8")) == build(), "uv run python -m scripts.export_feats_2024"
