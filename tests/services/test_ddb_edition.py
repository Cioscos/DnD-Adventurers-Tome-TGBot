"""Import da D&D Beyond: edizione reale dal manuale delle classi, sottoclasse, CA del Monaco e competenze."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.services.ddb_import import DdbImportError, class_option_names, convert, detect_edition

_DIR = Path(__file__).parents[1] / "fixtures" / "ddb"


def load(name: str) -> dict:
    return json.loads((_DIR / name).read_text(encoding="utf-8"))


def test_fixture_2024_detected():
    assert detect_edition(load("fighter20_2024.json")) == "2024"


def test_fixture_2014_detected():
    assert detect_edition(load("cleric19.json")) == "2014"


def test_mixed_fixture():
    assert detect_edition(load("wizard17_warlock3_multi.json")) == "mixed"


@pytest.mark.parametrize("name", ["barbarian20_2024.json", "bard20_2024.json", "monk20_2024.json",
                                  "sorcerer5_2024.json"])
def test_other_2024_fixtures(name):
    assert detect_edition(load(name)) == "2024"


def test_bare_data_and_garbage():
    assert detect_edition(load("cleric19.json")["data"]) == "2014"
    assert detect_edition({}) == "mixed"
    assert detect_edition(None) == "mixed"
    assert detect_edition({"classes": [{"definition": {"sources": [{"sourceId": 999}]}}]}) == "mixed"


def test_convert_carries_detected_edition():
    assert convert(load("fighter20_2024.json"))[0].character.rules_edition == "2024"
    assert convert(load("cleric19.json"))[0].character.rules_edition == "2014"


def test_convert_mixed_needs_choice_and_accepts_one():
    raw = load("wizard17_warlock3_multi.json")
    with pytest.raises(DdbImportError) as e:
        convert(raw)
    assert e.value.code == "edition_required"
    assert convert(raw, edition="2024")[0].character.rules_edition == "2024"
    assert convert(raw, edition="2014")[0].character.rules_edition == "2014"


def test_chosen_edition_overrides_detected():
    assert convert(load("fighter20_2024.json"), edition="2014")[0].character.rules_edition == "2014"


def test_invalid_edition_rejected():
    with pytest.raises(DdbImportError):
        convert(load("cleric19.json"), edition="2020")


def test_subclass_label_stripped_only_when_it_matches():
    raw = load("wizard17_warlock3_multi.json")
    assert [c.subclass for c in convert(raw, edition="2014")[0].classes] == ["School of Necromancy", "The Fiend"]
    # la Necromanzia non esiste nel 2024: il testo di DDB resta intero
    assert [c.subclass for c in convert(raw, edition="2024")[0].classes] == [
        "School of Necromancy (PHB)", "The Fiend"]


def test_unknown_subclass_stays_text():
    raw = load("fighter20_2024.json")
    raw["data"]["classes"][0]["subclassDefinition"]["name"] = "Dread Knight (Homebrew)"
    assert convert(raw)[0].classes[0].subclass == "Dread Knight (Homebrew)"


def test_ddb_proficiencies_are_final():
    assert convert(load("cleric19.json"))[0].character.settings["proficiencies_seeded"] is True


def test_specific_weapons_use_the_app_label():
    raw = load("cleric19.json")
    raw["data"]["modifiers"]["class"].append(
        {"type": "proficiency", "subType": "hand-crossbows", "friendlySubtypeName": "Hand Crossbows"})
    profs = convert(raw)[0].character.general_proficiencies  # DDB le mette fra le «altre»: is_weapon_proficient le legge
    assert "Hand crossbow" in profs["other"] and "Hand Crossbows" not in profs["other"]


def test_monk_with_shield_has_no_wisdom_in_ac():
    raw = load("monk20_2024.json")["data"]
    raw["inventory"].append({"id": 7, "equipped": True, "quantity": 1,
                             "definition": {"id": 7, "name": "Shield", "filterType": "Armor", "armorTypeId": 4,
                                            "armorClass": 2}})
    ch = convert(raw)[0].character
    assert ch.shield_armor_class == 2
    assert ch.base_armor_class == 10 + 6  # 10 + DES, senza SAG
    assert ch.unarmored_defense_ability == "wisdom"  # tolto lo scudo, la formula torna


def test_class_option_names_by_class_index():
    assert class_option_names(load("sorcerer5_2024.json")) == [
        {"class_index": 0, "name": "Quickened Spell"}, {"class_index": 0, "name": "Extended Spell"}]
    assert class_option_names(load("cleric19.json")) == []
    assert class_option_names(None) == []
