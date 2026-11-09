"""Task 47: equipaggiamento di partenza per classe ed edizione, oggetti inerti.

`EXPECTED` e' la trascrizione delle schede «Equipaggiamento» in `docs/superpowers/rules/<anno>/classes/`
(non leggibili qui: `docs/superpowers` e' fuori dal repo). Una alternativa = {chiave: quantita}, `gold` per le monete.
"""
from __future__ import annotations

import pytest

from core.rules.edition import CLASS_KEYS
from core.rules.starting_equipment import GENERIC, _parse, _srd, describe, resolve, starting_groups

P = {"simple-weapon": 1}
SM = {"simple-melee": 1}
M = {"martial-weapon": 1}
MM = {"martial-melee": 1}
EXP = {"explorer-pack": 1}
DUN = {"dungeoneer-pack": 1}
XB = {"crossbow-light": 1, "bolts": 20}

EXPECTED: dict[tuple[str, str], list[list[dict]]] = {
    # Barbaro 1: ascia bipenne o guerra mischia; due asce o semplice; esploratore + 4 giavellotti.
    ("2014", "barbarian"): [[{"greataxe": 1}, MM], [{"handaxe": 2}, SM], [EXP], [{"javelin": 4}]],
    ("2014", "bard"): [[{"rapier": 1}, {"longsword": 1}, P], [{"diplomat-pack": 1}, {"entertainer-pack": 1}],
                       [{"lute": 1}, {"instrument": 1}], [{"leather-armor": 1}], [{"dagger": 1}]],
    ("2014", "cleric"): [[{"mace": 1}, {"warhammer": 1}], [{"scale-mail": 1}, {"leather-armor": 1}, {"chain-mail": 1}],
                         [XB, P], [{"priest-pack": 1}, EXP], [{"shield": 1, "holy-symbol": 1}]],
    ("2014", "druid"): [[{"wooden-shield": 1}, P], [{"scimitar": 1}, SM],
                        [{"leather-armor": 1, "explorer-pack": 1, "druidic-focus": 1}]],
    ("2014", "fighter"): [[{"chain-mail": 1}, {"leather-armor": 1, "longbow": 1, "arrows": 20}],
                          [{**M, "shield": 1}, {"martial-weapon": 2}], [XB, {"handaxe": 2}], [DUN, EXP]],
    ("2014", "monk"): [[{"shortsword": 1}, P], [DUN, EXP], [{"dart": 10}]],
    ("2014", "paladin"): [[{**M, "shield": 1}, {"martial-weapon": 2}], [{"javelin": 5}, SM], [{"priest-pack": 1}, EXP],
                          [{"chain-mail": 1, "holy-symbol": 1}]],
    ("2014", "ranger"): [[{"scale-mail": 1}, {"leather-armor": 1}], [{"shortsword": 2}, {"simple-melee": 2}], [DUN, EXP],
                         [{"longbow": 1, "quiver": 1, "arrows": 20}]],
    ("2014", "rogue"): [[{"rapier": 1}, {"shortsword": 1}], [{"shortbow": 1, "quiver": 1, "arrows": 20}, {"shortsword": 1}],
                        [{"burglar-pack": 1}, DUN, EXP], [{"leather-armor": 1, "dagger": 2, "thieves-tools": 1}]],
    ("2014", "sorcerer"): [[XB, P], [{"component-pouch": 1}, {"arcane-focus": 1}], [DUN, EXP], [{"dagger": 2}]],
    ("2014", "warlock"): [[XB, P], [{"component-pouch": 1}, {"arcane-focus": 1}], [{"scholar-pack": 1}, DUN],
                          [{"leather-armor": 1, "simple-weapon": 1, "dagger": 2}]],
    ("2014", "wizard"): [[{"quarterstaff": 1}, {"dagger": 1}], [{"component-pouch": 1}, {"arcane-focus": 1}],
                         [{"scholar-pack": 1}, EXP], [{"spellbook": 1}]],
    # 2024: opzione A, opzione B in monete (Guerriero anche C).
    ("2024", "barbarian"): [[{"greataxe": 1, "handaxe": 4, "explorer-pack": 1, "gold": 15}, {"gold": 75}]],
    ("2024", "bard"): [[{"leather-armor": 1, "dagger": 2, "instrument": 1, "entertainer-pack": 1, "gold": 19}, {"gold": 90}]],
    ("2024", "cleric"): [[{"chain-shirt": 1, "shield": 1, "mace": 1, "holy-symbol": 1, "priest-pack": 1, "gold": 7},
                          {"gold": 110}]],
    ("2024", "druid"): [[{"leather-armor": 1, "shield": 1, "sickle": 1, "druidic-focus": 1, "explorer-pack": 1,
                          "herbalism-kit": 1, "gold": 9}, {"gold": 50}]],
    ("2024", "fighter"): [[{"chain-mail": 1, "greatsword": 1, "flail": 1, "javelin": 8, "dungeoneer-pack": 1, "gold": 4},
                           {"studded-leather-armor": 1, "scimitar": 1, "shortsword": 1, "longbow": 1, "arrows": 20,
                            "quiver": 1, "dungeoneer-pack": 1, "gold": 11}, {"gold": 155}]],
    ("2024", "monk"): [[{"spear": 1, "dagger": 5, "artisan-or-instrument": 1, "explorer-pack": 1, "gold": 11}, {"gold": 50}]],
    ("2024", "paladin"): [[{"chain-mail": 1, "shield": 1, "longsword": 1, "javelin": 6, "holy-symbol": 1, "priest-pack": 1,
                            "gold": 9}, {"gold": 150}]],
    ("2024", "ranger"): [[{"studded-leather-armor": 1, "scimitar": 1, "shortsword": 1, "longbow": 1, "arrows": 20, "quiver": 1,
                           "druidic-focus": 1, "explorer-pack": 1, "gold": 7}, {"gold": 150}]],
    ("2024", "rogue"): [[{"leather-armor": 1, "dagger": 2, "shortsword": 1, "shortbow": 1, "arrows": 20, "quiver": 1,
                          "thieves-tools": 1, "burglar-pack": 1, "gold": 8}, {"gold": 100}]],
    ("2024", "sorcerer"): [[{"spear": 1, "dagger": 2, "arcane-focus": 1, "dungeoneer-pack": 1, "gold": 28}, {"gold": 50}]],
    ("2024", "warlock"): [[{"leather-armor": 1, "sickle": 1, "dagger": 2, "arcane-focus": 1, "occult-book": 1,
                            "scholar-pack": 1, "gold": 15}, {"gold": 100}]],
    ("2024", "wizard"): [[{"dagger": 2, "quarterstaff": 1, "robe": 1, "spellbook": 1, "scholar-pack": 1, "gold": 5},
                          {"gold": 55}]],
}


def _as_dict(alt: str) -> dict:
    items, gold = _parse(alt)
    out = dict(items)
    if gold:
        out["gold"] = gold
    return out


@pytest.mark.parametrize("edition", ["2014", "2024"])
@pytest.mark.parametrize("class_key", CLASS_KEYS)
def test_table_matches_sheet(edition, class_key):
    got = [[_as_dict(a) for a in g] for g in starting_groups(edition, class_key)]
    assert got == EXPECTED[(edition, class_key)]
    for labels in describe(edition, class_key, "it") + describe(edition, class_key, "en"):
        assert all(labels)  # ogni alternativa ha un'etichetta
    for pick in (0, -1):  # prima e ultima alternativa di ogni gruppo si risolvono
        picks = [0 if pick == 0 else len(g) - 1 for g in starting_groups(edition, class_key)]
        rows, gold = resolve(edition, class_key, picks, "it")
        assert all(r["item_type"] != "armor" or r["item_metadata"]["ac_value"] for r in rows)


def test_every_key_is_known():
    assert set(EXPECTED) == {(e, c) for e in ("2014", "2024") for c in CLASS_KEYS}
    assert GENERIC.keys().isdisjoint(_srd().keys())


def test_resolve_validates_and_merges():
    with pytest.raises(ValueError):
        resolve("2014", "wizard", [0], "it")  # gruppi sbagliati
    with pytest.raises(ValueError):
        resolve("2024", "fighter", [3], "it")
    with pytest.raises(ValueError):
        resolve("2014", "custom", [], "it")
    rows, gold = resolve("2024", "fighter", [1], "en")
    assert gold == 11
    bow = next(r for r in rows if r["name"] == "Longbow")
    assert bow["item_type"] == "weapon" and bow["item_metadata"]["srd_index"] == "longbow"
    assert next(r for r in rows if r["name"] == "Arrows")["quantity"] == 20
    assert next(r for r in rows if r["name"] == "Studded Leather Armor")["item_type"] == "armor"
    rows, _ = resolve("2014", "sorcerer", [1, 0, 0, 0], "it")  # pugnali: una riga sola, quantita' 2
    assert next(r for r in rows if r["name"] == "Pugnale")["quantity"] == 2


async def _create(client, cls, **extra):
    return await client.post("/characters", json={
        "name": "Eroe", "initial_class": {"class_name": cls, "level": 1}, **extra})


async def test_creation_adds_inert_items_and_gold(client):
    r = await _create(client, "Guerriero", starting_equipment=[0, 0, 0, 0])
    assert r.status_code == 201, r.text
    body = r.json()
    names = {i["name"]: i for i in body["items"]}
    assert "Cotta di maglia" in names and "Balestra leggera" in names
    assert all(not i["is_equipped"] and i["equipment_slot"] is None for i in body["items"])
    assert body["ac_breakdown"]["base"] == 10  # niente CA ricalcolata
    assert names["Dotazione da avventuriero"]["item_type"] == "generic"
    assert body["currency"]["gold"] == 0


async def test_creation_2024_gold_and_items(client):
    r = await _create(client, "wizard", rules_edition="2024", starting_equipment=[0])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["currency"]["gold"] == 5
    assert {"Libro degli incantesimi", "Veste"} <= {i["name"] for i in body["items"]}
    r = await _create(client, "wizard", rules_edition="2024", starting_equipment=[1])
    assert r.json()["currency"]["gold"] == 55 and r.json()["items"] == []


async def test_creation_without_choice_or_invalid(client):
    r = await _create(client, "Mago")
    assert r.status_code == 201 and r.json()["items"] == []
    assert (await _create(client, "Mago", starting_equipment=[9, 9, 9, 9])).status_code == 422
    assert (await client.post("/characters", json={"name": "x", "starting_equipment": [0]})).status_code == 422


async def test_options_endpoint(client):
    r = await client.get("/rules/starting-equipment", params={"edition": "2024", "class_key": "Guerriero"})
    assert r.status_code == 200, r.text
    groups = r.json()["groups"]
    assert len(groups) == 1 and len(groups[0]) == 3 and groups[0][2].startswith("155")
    r = await client.get("/rules/starting-equipment", params={"edition": "2014", "class_key": "custom"})
    assert r.json()["groups"] == []
