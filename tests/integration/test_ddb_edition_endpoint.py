"""POST /characters/import/ddb: edizione reale, scelta richiesta per le classi miste, opzioni di classe."""
from __future__ import annotations

import json
from pathlib import Path

import api.routers.transfer as transfer
from core.rules.types import ChoiceSpec, FeatureSpec, Uses

_DIR = Path(__file__).parents[1] / "fixtures" / "ddb"
URL = "https://www.dndbeyond.com/characters/95893448"


def _serve(monkeypatch, name: str, edit=None) -> None:
    async def fake(char_id: int) -> dict:
        raw = json.loads((_DIR / name).read_text(encoding="utf-8"))
        if edit:
            edit(raw["data"])
        return raw
    monkeypatch.setattr(transfer, "fetch_ddb", fake)


async def _post(client, **extra):
    return await client.post("/characters/import/ddb", json={"url": URL, **extra})


async def test_2024_character_imported_as_2024(client, monkeypatch):
    _serve(monkeypatch, "fighter20_2024.json")
    r = await _post(client)
    assert r.status_code == 201, r.text
    ch = r.json()["character"]
    assert ch["rules_edition"] == "2024" and ch["classes"][0]["subclass_key"] == "champion"


async def test_2014_character_imported_as_2014(client, monkeypatch):
    _serve(monkeypatch, "cleric19.json")
    ch = (await _post(client)).json()["character"]
    assert ch["rules_edition"] == "2014" and ch["classes"][0]["subclass_key"] == "tempest"


async def test_mixed_import_requires_choice(client, monkeypatch):
    _serve(monkeypatch, "wizard17_warlock3_multi.json")
    r = await _post(client)
    assert r.status_code == 409 and r.json()["detail"] == {"code": "edition_required"}
    assert (await client.get("/characters")).json() == []
    r = await _post(client, rules_edition="2024")
    assert r.status_code == 201, r.text
    ch = r.json()["character"]
    assert ch["rules_edition"] == "2024"
    # la Necromanzia esiste solo nel 2014: nel 2024 resta testo, com'è su DDB
    assert [(c["subclass_key"], c["subclass"]) for c in ch["classes"]] == [
        (None, "School of Necromancy (PHB)"), ("fiend", "The Fiend")]
    r = await _post(client, rules_edition="2014")
    ch = r.json()["character"]
    assert ch["rules_edition"] == "2014"
    assert [(c["subclass_key"], c["subclass"]) for c in ch["classes"]] == [
        ("necromancy", "School of Necromancy"), ("fiend", "The Fiend")]


async def test_bad_edition_value_rejected(client, monkeypatch):
    _serve(monkeypatch, "cleric19.json")
    assert (await _post(client, rules_edition="2020")).status_code == 422


async def test_2024_import_has_no_2014_approximations(client, monkeypatch, rules_catalog):
    """Classe a catalogo 2024: la riga nasce con la chiave 2024 (non «Ki»), il massimo è del motore, gli usi spesi di
    DDB si riportano su quella riga."""
    rules_catalog(FeatureSpec(
        key="monk.focus_points", class_key="monk", edition="2024", level=2, source_title="Focus Points",
        name={"it": "Punti Focus", "en": "Focus Points"}, summary={"it": "x", "en": "x"}, action_type=None,
        uses=Uses(table={2: 18}), restoration="short_rest"))

    def spend(data):
        for a in data["actions"]["class"]:
            if a["name"] == "Focus Points":
                a["limitedUse"]["numberUsed"] = 5
    _serve(monkeypatch, "monk20_2024.json", spend)
    ch = (await _post(client)).json()["character"]
    rows = [a for a in ch["abilities"] if a["is_class_feature"]]
    assert [a["feature_key"] for a in rows] == ["monk.focus_points"]
    assert rows[0]["max_uses"] == 18 and rows[0]["uses"] == 13  # 18 del motore, DDB dice 20 con 5 spesi
    assert not [a for a in ch["abilities"] if a["name"] == "Focus Points" and not a["is_class_feature"]]


async def test_class_outside_catalog_keeps_ddb_max(client, monkeypatch, rules_catalog):
    # registro vuoto: il Monaco 2024 è a catalogo dal Task 36, ma qui serve una classe fuori catalogo
    def spend(data):
        for a in data["actions"]["class"]:
            if a["name"] == "Focus Points":
                a["limitedUse"]["numberUsed"] = 5
    _serve(monkeypatch, "monk20_2024.json", spend)
    ch = (await _post(client)).json()["character"]
    ki = [a for a in ch["abilities"] if a["is_class_feature"] and a["feature_key"] == "monk.ki"]
    assert ki and ki[0]["max_uses"] == 20 and ki[0]["uses"] == 15


async def test_unknown_subclass_stays_text(client, monkeypatch):
    def edit(data):
        data["classes"][0]["subclassDefinition"]["name"] = "Dread Knight"
    _serve(monkeypatch, "fighter20_2024.json", edit)
    cls = (await _post(client)).json()["character"]["classes"][0]
    assert cls["subclass"] == "Dread Knight" and cls["subclass_key"] is None


async def test_monk_with_shield_ac_has_no_wisdom(client, monkeypatch):
    def edit(data):
        data["inventory"].append({"id": 7, "equipped": True, "quantity": 1, "definition": {
            "id": 7, "name": "Shield", "filterType": "Armor", "armorTypeId": 4, "armorClass": 2}})
    _serve(monkeypatch, "monk20_2024.json", edit)
    ch = (await _post(client)).json()["character"]
    assert ch["ac_breakdown"]["base"] == 16 and ch["ac_breakdown"]["shield"] == 2  # 10 + DES 6; niente SAG


async def test_class_options_follow_the_catalog(client, monkeypatch, rules_catalog):
    rules_catalog(FeatureSpec(
        key="sorcerer.metamagic", class_key="sorcerer", edition="2024", level=2, source_title="Metamagic",
        name={"it": "Metamagia", "en": "Metamagic"}, summary={"it": "x", "en": "x"}, action_type=None,
        choices=(ChoiceSpec("metamagic", {2: 2}, lambda ctx: ["quickened", "extended", "twinned"],
                            label=lambda k: {"name": f"{k.capitalize()} Spell", "summary": ""}),)))
    _serve(monkeypatch, "sorcerer5_2024.json")
    r = await _post(client)
    assert r.status_code == 201, r.text
    cls = r.json()["character"]["classes"][0]
    assert sorted(cls["options"]["metamagic"]) == ["extended", "quickened"]
    assert not [e for e in r.json()["report"]["approximated"] if e["section"] == "options"]


async def test_unmatched_options_stay_in_report(client, monkeypatch):
    _serve(monkeypatch, "sorcerer5_2024.json")  # catalogo vuoto: nessun gruppo le riconosce
    rep = (await _post(client)).json()["report"]
    names = {e["name"] for e in rep["approximated"] if e["section"] == "options"}
    assert names == {"Quickened Spell", "Extended Spell"}


def _strip_sources(data: dict, sources) -> None:
    for cl in data["classes"]:
        cl["definition"]["sources"] = sources
        cl["definition"]["sourceId"] = None


async def test_unknown_or_missing_source_id_asks_for_the_edition_not_500(client, monkeypatch):
    for sources in ([{"sourceId": 9999}], [], None):
        _serve(monkeypatch, "fighter20_2024.json", lambda d, s=sources: _strip_sources(d, s))
        r = await _post(client)
        assert r.status_code == 409 and r.json()["detail"] == {"code": "edition_required"}, (sources, r.text)
    r = await _post(client, rules_edition="2024")
    assert r.status_code == 201 and r.json()["character"]["rules_edition"] == "2024"


async def test_null_rules_edition_means_detect_it(client, monkeypatch):
    _serve(monkeypatch, "fighter20_2024.json")
    r = await _post(client, rules_edition=None)
    assert r.status_code == 201, r.text
    assert r.json()["character"]["rules_edition"] == "2024"
    _serve(monkeypatch, "wizard17_warlock3_multi.json")
    assert (await _post(client, rules_edition=None)).status_code == 409
