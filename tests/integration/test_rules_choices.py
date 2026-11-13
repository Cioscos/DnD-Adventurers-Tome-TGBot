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


def _trick(ctx_options=("a", "b", "c", "d"), replaceable=False) -> tuple[FeatureSpec, ...]:
    def spec(key, **kw):
        return FeatureSpec(key=f"barbarian.{key}", class_key="barbarian", edition="2014", level=3,
                           source_title=key, name={"it": key, "en": key}, summary={"it": key, "en": key},
                           action_type=None, **kw)
    return (spec("trick", choices=(ChoiceSpec("trick", {3: 2, 5: 3}, lambda ctx: list(ctx_options), replaceable),)),
            *(spec(f"trick_{o}", option_group="trick", option_key=o) for o in ctx_options))


async def test_asi_created_when_class_born_above_level_1(client):
    body = await _char(client)
    r = await client.post(f"/characters/{body['id']}/classes", json={"class_name": "Barbaro", "level": 8, "hit_die": 12})
    assert r.status_code in (200, 201), r.text
    assert _pending(r.json(), "asi") == [("asi", 4), ("asi", 8)]


async def test_level_down_removes_pending_above_level(client):
    body = await _char(client, xp=14000)  # guerriero livello 6: ASI a 4 e 6
    assert _pending(body, "asi") == [("asi", 4), ("asi", 6)]
    r = await client.patch(f"/characters/{body['id']}/xp", json={"set": 2700})
    assert _pending(r.json(), "asi") == [("asi", 4)]


async def test_resolved_level_is_not_offered_again(client):
    body = await _char(client, xp=2700)
    r = await _resolve(client, body, "asi", {"increases": {"strength": 2}})
    assert r.status_code == 200 and _pending(r.json(), "asi") == []
    await client.patch(f"/characters/{body['id']}/xp", json={"set": 300})  # livello 2
    r = await client.patch(f"/characters/{body['id']}/xp", json={"set": 2700})
    assert _pending(r.json(), "asi") == []


async def test_2024_level_19_creates_epic_boon_not_asi(client):
    body = await _char(client, edition="2024", xp=305000)
    # il Guerriero 2024 ha anche scelte di classe (stile, maestria): qui contano ASI e Dono Epico
    assert [p for p in _pending(body) if p[0] in ("asi", "epic_boon")] == [("asi", 4), ("asi", 6), ("asi", 8), ("asi", 12), ("asi", 14), ("asi", 16),
                              ("epic_boon", 19)]
    mage = await _char(client, "Mago", edition="2024", xp=305000)
    # il Mago 2024 ha anche le scelte di classe (libro, Studioso)
    assert [p for p in _pending(mage) if p[0] in ("asi", "epic_boon")] == [("asi", 4), ("asi", 8), ("asi", 12), ("asi", 16), ("epic_boon", 19)]
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


def _groups(body: dict) -> list[tuple]:
    return [(c["group"], c["count"], c["level"]) for c in body["pending_choices"] if c["kind"] == "class_option"]


async def test_existing_character_gets_options_when_catalog_arrives(client, rules_catalog):
    body = await _char(client, "Barbaro", xp=900)  # catalogo ancora vuoto: nessuna scelta
    assert _groups(body) == []
    rules_catalog(*_trick())
    cls_id = body["classes"][0]["id"]
    r = await client.patch(f"/characters/{body['id']}/classes/{cls_id}", json={})  # nessun cambio di livello
    assert _groups(r.json()) == [("trick", 2, 3)]
    r = await client.patch(f"/characters/{body['id']}/classes/{cls_id}", json={})
    assert _groups(r.json()) == [("trick", 2, 3)]  # idempotente


async def test_subclass_choice_appears_when_subclass_is_set_and_is_pruned_when_lost(client, rules_catalog):
    def spec(**kw):
        return FeatureSpec(key="barbarian.sub", class_key="barbarian", edition="2014", level=3, source_title="s",
                           name={"it": "s", "en": "s"}, summary={"it": "s", "en": "s"}, action_type=None,
                           subclass="berserker", choices=(ChoiceSpec("sub", {3: 1}, lambda ctx: ["x", "y"]),), **kw)
    rules_catalog(spec())
    body = await _char(client, "Barbaro", xp=900)
    assert _groups(body) == []
    cls_id = body["classes"][0]["id"]
    r = await client.patch(f"/characters/{body['id']}/classes/{cls_id}", json={"subclass": "Cammino del Berserker"})
    assert _groups(r.json()) == [("sub", 1, 3)]
    r = await client.patch(f"/characters/{body['id']}/classes/{cls_id}", json={"subclass": "Cammino del Combattente Totemico"})
    assert _groups(r.json()) == []  # senza spec attiva la scelta non resta irrisolvibile


async def test_class_option_level_down_shrinks_pending(client, rules_catalog):
    rules_catalog(*_trick())
    body = await _char(client, "Barbaro", xp=6500)  # livello 5: 3 opzioni
    assert _groups(body) == [("trick", 3, 5)]
    r = await client.patch(f"/characters/{body['id']}/xp", json={"set": 900})
    assert _groups(r.json()) == [("trick", 2, 3)]
    r = await client.patch(f"/characters/{body['id']}/xp", json={"set": 300})  # livello 2
    assert _groups(r.json()) == []


async def test_edition_change_reconciles_choices(client, rules_catalog):
    rules_catalog(*_trick())
    body = await _char(client, "Barbaro", xp=900)
    assert _groups(body) == [("trick", 2, 3)]
    r = await client.patch(f"/characters/{body['id']}", json={"rules_edition": "2024"})
    assert _groups(r.json()) == []  # il catalogo di prova esiste solo per il 2014
    r = await client.patch(f"/characters/{body['id']}", json={"rules_edition": "2014"})
    assert _groups(r.json()) == [("trick", 2, 3)]
    old = await _char(client, xp=305000)  # guerriero 2014 a 19: nessun Dono
    r = await client.patch(f"/characters/{old['id']}", json={"rules_edition": "2024"})
    assert ("epic_boon", 19) in _pending(r.json())
    r = await client.patch(f"/characters/{old['id']}", json={"rules_edition": "2014"})
    assert ("epic_boon", 19) not in _pending(r.json())


async def test_replace_class_option(client, rules_catalog):
    rules_catalog(*_trick(replaceable=True))
    body = await _char(client, "Barbaro", xp=900)
    cid = body["classes"][0]["id"]
    await _resolve(client, body, "class_option", {"options": ["a", "b"]})
    url = f"/characters/{body['id']}/classes/{cid}/options"
    state = (await client.get(f"{url}/trick")).json()
    assert state["replaceable"] and [o["key"] for o in state["chosen"]] == ["a", "b"]
    assert [o["key"] for o in state["available"]] == ["c", "d"]
    for bad in ({"old_key": "c", "new_key": "d"}, {"old_key": "a", "new_key": "b"}, {"old_key": "a", "new_key": "zzz"}):
        assert (await client.post(f"{url}/replace", json={"group": "trick", **bad})).status_code == 422
    r = await client.post(f"{url}/replace", json={"group": "trick", "old_key": "a", "new_key": "d"})
    assert r.status_code == 200, r.text
    assert r.json()["classes"][0]["options"] == {"trick": ["d", "b"]}
    keys = {a["feature_key"] for a in r.json()["abilities"]}
    assert "barbarian.trick_d" in keys and "barbarian.trick_a" not in keys


async def test_replace_refused_when_not_replaceable(client, rules_catalog):
    rules_catalog(*_trick())
    body = await _char(client, "Barbaro", xp=900)
    await _resolve(client, body, "class_option", {"options": ["a", "b"]})
    r = await client.post(f"/characters/{body['id']}/classes/{body['classes'][0]['id']}/options/replace",
                          json={"group": "trick", "old_key": "a", "new_key": "c"})
    assert r.status_code == 422


async def test_import_drops_incomplete_class_option(client):
    body = await _char(client)
    exported = (await client.get(f"/characters/{body['id']}/export")).json()
    exported["character"]["pending_choices"] = [
        {"id": "p1", "kind": "class_option", "class_key": "Guerriero", "level": 3},
        {"id": "p2", "kind": "asi", "class_key": "Guerriero", "level": 4}]
    r = await client.post("/characters/import", json=exported)
    assert r.status_code in (200, 201), r.text
    ids = [c["id"] for c in r.json()["pending_choices"]]
    assert "p2" in ids and "p1" not in ids  # la scelta incompleta cade; lo stile del Guerriero è una scelta del catalogo, ricreata


def test_2024_feat_catalog_is_text_only_and_bounded():
    assert len(FEATS_2024) == 74 and len({f.key for f in FEATS_2024}) == 74  # 10 d'Origine, 42 generali, 10 Stili, 12 Doni
    for f in FEATS_2024:
        assert f.edition == "2024"
        assert all(len(t) <= 200 for t in f.summary.values()) and f.name["it"] and f.name["en"]
    assert sum(f.category == "epic_boon" for f in FEATS_2024) == 12
    assert sum(f.category == "origin" for f in FEATS_2024) == 10
    assert sum(f.category == "fighting_style" for f in FEATS_2024) == 10


def test_frontend_feat_mirror_is_up_to_date():
    import json
    from scripts.export_feats_2024 import TARGET, build
    assert json.loads(TARGET.read_text(encoding="utf-8")) == build(), "uv run python -m scripts.export_feats_2024"
