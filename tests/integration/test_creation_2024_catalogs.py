"""Creazione 2024 con specie e background dai cataloghi (Task 6, cataloghi 2024)."""
from __future__ import annotations

from core.data.backgrounds_2024 import BACKGROUNDS_2024
from core.data.skills import SKILL_ABILITY_MAP
from core.data.feats_2024 import ALL_FEATS
from core.data.tools import TOOLS
from core.rules.starting_equipment import resolve_package

SCORES = {"strength": 15, "dexterity": 14, "constitution": 13, "intelligence": 12, "wisdom": 10, "charisma": 8}


def _body(**extra) -> dict:
    return {"name": "Thorin", "rules_edition": "2024", "ability_scores": SCORES,
            "initial_class": {"class_name": "fighter", "level": 1}, **extra}


async def _count(client) -> int:
    return len((await client.get("/characters")).json())


def test_backgrounds_catalog_is_coherent():
    assert len(BACKGROUNDS_2024) == 16
    for bg in BACKGROUNDS_2024.values():
        assert len(set(bg.abilities)) == 3 and all(s in SKILL_ABILITY_MAP for s in bg.skills)
        assert ALL_FEATS[bg.origin_feat].category == "origin"
        tools = bg.tool if isinstance(bg.tool, tuple) else (bg.tool,)
        assert tools and all(t in TOOLS for t in tools)
        alt = bg.equipment.replace("{tool}", tools[0])
        rows, gold = resolve_package(alt, "it")  # ogni chiave esiste (KeyError altrimenti)
        assert rows and gold > 0


async def test_create_2024_with_species_and_background(client):
    r = await client.post("/characters", json=_body(
        species_2024={"key": "2024_dwarf"},
        background_2024={"key": "soldier", "increases": {"strength": 2, "constitution": 1}, "tool": "dice_set"},
        origin_feat="2024_alert"))  # ignorato: vale quello del background
    assert r.status_code == 201, r.text
    b = r.json()
    scores = {a["name"]: a["value"] for a in b["ability_scores"]}
    assert (scores["strength"], scores["constitution"], scores["dexterity"]) == (17, 14, 14)
    assert b["skills"].get("athletics") and b["skills"].get("intimidation")
    assert b["tool_proficiencies"].get("dice_set")
    feats = [a["feature_key"] for a in b["abilities"] if (a["feature_key"] or "").startswith("feat.")]
    assert feats == ["feat.2024_savage_attacker"]
    names = {i["name"] for i in b["items"]}
    assert {"Lancia", "Arco corto", "Dadi"} <= names
    assert b["currency"]["gold"] == 14
    assert b["background"] == "Soldato" and b["race"] == "Nano" and b["species_key"] == "2024_dwarf"
    assert b["speed"] == 30
    assert b["current_hit_points"] == b["computed"]["hp_max_effective"]  # nasce a PF pieni con la Robustezza nanica
    assert [s for s in b["computed"]["senses"] if s["type"] == "darkvision"] == [{"type": "darkvision", "range_ft": 120}]


async def test_background_gold_option_50(client):
    r = await client.post("/characters", json=_body(background_2024={
        "key": "sage", "increases": {"constitution": 1, "intelligence": 1, "wisdom": 1}, "equipment": "gold"}))
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["currency"]["gold"] == 50
    assert not any(i["name"] in ("Veste", "Robe") for i in b["items"])
    assert b["tool_proficiencies"].get("calligraphers_supplies")
    assert any(a["feature_key"] == "feat.2024_magic_initiate" for a in b["abilities"])


async def test_background_increases_invalid_422(client):
    before = await _count(client)
    bad = [
        {"strength": 2, "intelligence": 1},          # Intelligenza non è del Soldato
        {"strength": 2, "dexterity": 2},
        {"strength": 1, "dexterity": 1},
        {"strength": 2, "dexterity": 1, "constitution": 1},
    ]
    for inc in bad:
        r = await client.post("/characters", json=_body(
            background_2024={"key": "soldier", "increases": inc, "tool": "dice_set"}))
        assert (r.status_code, r.json()["detail"]) == (422, "background_increases_invalid"), (inc, r.text)
    over = await client.post("/characters", json=_body(ability_scores={**SCORES, "strength": 19}, background_2024={
        "key": "soldier", "increases": {"strength": 2, "dexterity": 1}, "tool": "dice_set"}))
    assert (over.status_code, over.json()["detail"]) == (422, "background_increases_invalid")
    for bg, code in (({"key": "nope", "increases": {}}, "background_unknown"),
                     ({"key": "soldier", "increases": {"strength": 2, "dexterity": 1}}, "background_tool_invalid"),
                     ({"key": "soldier", "increases": {"strength": 2, "dexterity": 1}, "tool": "lute"},
                      "background_tool_invalid"),
                     ({"key": "acolyte", "increases": {"wisdom": 2, "charisma": 1}, "tool": "lute"},
                      "background_tool_invalid")):
        r = await client.post("/characters", json=_body(background_2024=bg))
        assert (r.status_code, r.json()["detail"]) == (422, code), (bg, r.text)
    assert await _count(client) == before


async def test_species_2024_on_2014_422(client):
    before = await _count(client)
    r = await client.post("/characters", json={**_body(species_2024={"key": "2024_dwarf"}), "rules_edition": "2014"})
    assert (r.status_code, r.json()["detail"]) == (422, "species_edition")
    r = await client.post("/characters", json={**_body(background_2024={
        "key": "sage", "increases": {"wisdom": 1, "intelligence": 1, "constitution": 1}}), "rules_edition": "2014"})
    assert (r.status_code, r.json()["detail"]) == (422, "background_edition")
    r = await client.post("/characters", json=_body(species_2024={"key": "2024_dwarf"}, species={"name": "Nano"}))
    assert (r.status_code, r.json()["detail"]) == (422, "species_conflict")
    assert await _count(client) == before


async def test_dragonborn_without_ancestry_422_creates_nothing(client):
    before = await _count(client)
    r = await client.post("/characters", json=_body(species_2024={"key": "2024_dragonborn"}))
    assert (r.status_code, r.json()["detail"]) == (422, "species_options_invalid")
    assert await _count(client) == before


async def test_acolyte_magic_initiate_list_fixed(client):
    from tests.integration.rules.test_feats_take_complete import _complete, _feat_rows, _spell
    assert {BACKGROUNDS_2024[k].feat_list for k in ("acolyte", "guide", "sage")} == {"cleric", "druid", "wizard"}
    assert all(b.feat_list is None for b in BACKGROUNDS_2024.values() if b.origin_feat != "2024_magic_initiate")
    r = await client.post("/characters", json=_body(
        species_2024={"key": "2024_human", "options": {"size": "medium", "skill": "arcana",
                                                         "origin_feat": "2024_magic_initiate"}},
        background_2024={"key": "acolyte", "increases": {"wisdom": 2, "charisma": 1}}))
    assert r.status_code == 201, r.text
    rows = _feat_rows(r.json(), "2024_magic_initiate")
    fixed = next(a for a in rows if (a["options"] or {}).get("list"))
    versatile = next(a for a in rows if a is not fixed)
    assert fixed["options"]["list"] == "cleric" and fixed["feat_status"] == "incomplete"
    wizard = [_spell("Luce", 0, "light"), _spell("Mano Magica", 0, "mage-hand"), _spell("Charme su Persone", 1, "charm-person")]
    bad = await _complete(client, r.json()["id"], fixed["id"], {"list": "wizard", "ability": "wisdom"}, wizard)
    assert (bad.status_code, bad.json()["detail"]) == (422, "feat_options_invalid")
    # Versatile dell'Umano: la lista del background è già presa
    taken = await _complete(client, r.json()["id"], versatile["id"], {"list": "cleric", "ability": "wisdom"},
                            [_spell("Luce", 0, "light"), _spell("Taumaturgia", 0, "thaumaturgy"),
                             _spell("Benedizione", 1, "bless")])
    assert (taken.status_code, taken.json()["detail"]) == (422, "feat_list_taken")
    ok = await _complete(client, r.json()["id"], versatile["id"], {"list": "wizard", "ability": "wisdom"}, wizard)
    assert ok.status_code == 200, ok.text


async def test_human_versatile_feat_same_as_background_422_creates_nothing(client):
    before = await _count(client)
    r = await client.post("/characters", json=_body(
        species_2024={"key": "2024_human", "options": {"size": "medium", "skill": "arcana","origin_feat": "2024_alert"}},
        background_2024={"key": "criminal", "increases": {"dexterity": 2, "constitution": 1}}))
    assert (r.status_code, r.json()["detail"]) == (422, "species_options_invalid")
    assert await _count(client) == before
