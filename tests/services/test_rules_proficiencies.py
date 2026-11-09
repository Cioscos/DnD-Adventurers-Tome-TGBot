"""Tabelle delle competenze di classe per edizione (valori dalle schede in docs/superpowers/rules)."""
from __future__ import annotations

from types import SimpleNamespace as NS

from core.rules.proficiencies import (
    ALL_SKILLS, class_proficiencies, is_armor_proficient, is_weapon_proficient, merge_grant, validate_skill_choices,
)

SEEDED = {"proficiencies_seeded": True}


def test_rogue_2014_multiclass_grant():
    g = class_proficiencies("2014", "rogue", as_multiclass=True)
    assert g.armor == ("light",) and g.tools == ("thieves_tools",)
    assert g.weapons == () and g.saves == ()
    assert g.skills_count == 1 and "stealth" in g.skills_from


def test_first_class_has_saves_and_multiclass_never():
    first = class_proficiencies("2014", "fighter", as_multiclass=False)
    assert first.saves == ("strength", "constitution") and first.skills_count == 2
    assert class_proficiencies("2014", "fighter", as_multiclass=True).saves == ()


def test_editions_differ_and_custom_class_is_empty():
    assert class_proficiencies("2014", "monk", False).weapons == ("simple", "shortsword")
    assert class_proficiencies("2024", "monk", False).weapons == ("simple", "martial_light")
    assert class_proficiencies("2024", "barbarian", True).weapons == ("martial",)
    assert class_proficiencies("2014", "wizard", True) == class_proficiencies("2024", "sorcerer", True)
    assert class_proficiencies("2014", None, False) == class_proficiencies("2014", "cacciatore", False)
    assert len(class_proficiencies("2014", "bard", True).skills_from) == len(ALL_SKILLS)


def test_skill_choice_validation():
    g = class_proficiencies("2014", "rogue", as_multiclass=True)
    assert validate_skill_choices(g, ["stealth"]) is None
    assert validate_skill_choices(g, ["arcana"]) is not None
    assert validate_skill_choices(g, ["stealth", "athletics"]) is not None
    assert validate_skill_choices(class_proficiencies("2014", "wizard", True), ["arcana"]) is not None


def test_merge_is_additive_and_bilingual_dedup():
    char = NS(general_proficiencies=["Liuto"], saving_throws={"wisdom": False}, languages=[], skills={"stealth": "expert"})
    g = class_proficiencies("2014", "rogue", as_multiclass=False)
    merge_grant(char, g, "it", ("stealth", "athletics"))
    merge_grant(char, g, "en")  # stessa concessione in un'altra lingua: nessun doppione
    assert char.general_proficiencies["other"] == ["Liuto"]
    assert char.general_proficiencies["armor"] == ["Armature leggere"]
    assert char.saving_throws == {"wisdom": False, "dexterity": True, "intelligence": True}
    assert char.skills == {"stealth": "expert", "athletics": True}
    assert char.languages == ["Gergo Ladresco"]


def test_item_without_category_counts_as_proficient():
    char = NS(general_proficiencies={"weapons": ["Armi semplici"]}, settings=SEEDED)
    assert is_weapon_proficient(char, NS(name="Strana", item_metadata={}))
    assert is_weapon_proficient(char, NS(name="Strana", item_metadata=None))
    assert not is_weapon_proficient(char, NS(name="Spadone", item_metadata={"weapon_category": "martial"}))
    assert is_weapon_proficient(char, NS(name="Pugnale", item_metadata='{"weapon_category": "simple"}'))


def test_unseeded_empty_list_is_lenient_but_seeded_empty_is_not():
    martial = NS(name="Spadone", item_metadata={"weapon_category": "martial"})
    assert is_weapon_proficient(NS(general_proficiencies=[], settings={}), martial)
    assert not is_weapon_proficient(NS(general_proficiencies=[], settings=SEEDED), martial)


def test_specific_weapon_and_light_martial():
    wiz = NS(general_proficiencies={"weapons": ["Stocco"]}, settings=SEEDED)
    assert is_weapon_proficient(wiz, NS(name="stocco", item_metadata={"weapon_category": "martial"}))
    monk = NS(general_proficiencies={"weapons": ["Armi semplici", "Armi da guerra con proprietà Leggera"]}, settings=SEEDED)
    light = NS(name="Scimitarra", item_metadata={"weapon_category": "martial", "properties": ["Leggera"]})
    heavy = NS(name="Spadone", item_metadata={"weapon_category": "martial", "properties": ["Pesante"]})
    assert is_weapon_proficient(monk, light)
    assert not is_weapon_proficient(monk, heavy)


def test_armor_and_shield():
    char = NS(general_proficiencies={"armor": ["Armature leggere", "Scudi"]}, settings=SEEDED)
    assert is_armor_proficient(char, NS(item_type="armor", item_metadata={"armor_type": "light"}))
    assert not is_armor_proficient(char, NS(item_type="armor", item_metadata={"armor_type": "heavy"}))
    assert is_armor_proficient(char, NS(item_type="shield", item_metadata={}))
    assert is_armor_proficient(char, NS(item_type="armor", item_metadata={}))
    char.general_proficiencies = {"armor": ["Armature leggere"]}
    assert not is_armor_proficient(char, NS(item_type="shield", item_metadata={}))


def test_custom_class_keeps_bonus_even_when_seeded_and_empty():
    martial = NS(name="Spadone", item_metadata={"weapon_category": "martial"})
    custom = NS(class_name="Cacciatore di Taglie")
    wizard = NS(class_name="Mago")
    only = NS(general_proficiencies={}, settings=SEEDED, classes=[custom])
    mixed = NS(general_proficiencies={"weapons": ["Pugnale"]}, settings=SEEDED, classes=[custom, wizard])
    assert is_weapon_proficient(only, martial) and is_weapon_proficient(mixed, martial)
    assert is_armor_proficient(mixed, NS(item_type="armor", item_metadata={"armor_type": "heavy"}))
    assert not is_weapon_proficient(NS(general_proficiencies={}, settings=SEEDED, classes=[wizard]), martial)
