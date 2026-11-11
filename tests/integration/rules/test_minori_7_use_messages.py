"""Punto 35: gli usi che prima non dicevano nulla ora hanno un testo nelle due lingue."""
from types import SimpleNamespace

import pytest

from core.rules.catalog.y2014 import cleric as cleric14
from core.rules.catalog.y2024 import bard, cleric as cleric24, druid


def _use(module, key):
    return next(f.on_use for f in module.FEATURES if f.key.endswith(f".{key}") and f.on_use)


@pytest.mark.parametrize("on_use,params", [
    (bard.FONT_USE, {"slot_level": 2}),
    (_use(druid, "natures_sanctuary_move"), {}),
    (_use(druid, "twinkling_constellations"), {"constellation": "dragon"}),
    (_use(cleric24, "invoke_duplicity_move"), {}),
    (_use(cleric14, "invoke_duplicity_move"), {}),
])
def test_minori_35_the_use_says_what_happened_in_both_languages(on_use, params):
    text = on_use.message(SimpleNamespace(), params)
    assert text["it"] and text["en"] and text["it"] != text["en"]


def test_minori_36_bastion_of_law_option_is_singular_for_one_point():
    from core.rules.catalog.y2024.sorcerer_subclasses import BASTION_USE
    label = BASTION_USE.choices[0].option_label
    assert label("1") == {"it": "1 punto, 1d8", "en": "1 point, 1d8"}
    assert label("3")["it"] == "3 punti, 3d8"


def test_minori_36_skill_labels_of_the_server_match_the_skills_page():
    from core.data.labels import skill_label
    assert skill_label("animal_handling") == "Addestrare Animali" and skill_label("intimidation") == "Intimidire"
