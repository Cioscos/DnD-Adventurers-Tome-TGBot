"""Primitive delle scelte di strumenti nelle opzioni di classe (chiavi ``tool:<chiave>``)."""
from __future__ import annotations

from types import SimpleNamespace

from core.data.tools import TOOLS
from core.rules.catalog._common import first_class, skill_label, tool_choice_label
from core.rules.level_choices import apply_grants
from core.rules.types import ChoiceSpec, RuleContext


def _char(**kw):
    return SimpleNamespace(skills={}, tool_proficiencies={}, languages=[], saving_throws={}, **kw)


def _spec(grants):
    return ChoiceSpec(group="g", levels={1: 1}, options=lambda _c: [], grants=grants)


def test_apply_grants_adds_tool_keys_to_the_column():
    char = _char()
    apply_grants(char, _spec("proficient"), ["tool:lute", "athletics"])
    assert char.tool_proficiencies == {"lute": True}
    assert char.skills == {"athletics": True}


def test_apply_grants_expert_tool_never_lowers():
    char = _char()
    char.tool_proficiencies = {"thieves_tools": True, "lute": "expert"}
    apply_grants(char, _spec("expert"), ["tool:thieves_tools"])
    apply_grants(char, _spec("proficient"), ["tool:lute"])
    assert char.tool_proficiencies == {"thieves_tools": "expert", "lute": "expert"}


def test_tool_choice_label_names_and_category():
    label = tool_choice_label("tool:lute")
    assert label["name"] == {"it": TOOLS["lute"].it, "en": TOOLS["lute"].en}
    assert label["summary"] == {"it": "Strumento musicale", "en": "Musical instrument"}
    assert tool_choice_label("stealth") == skill_label("stealth")


def test_first_class_by_lowest_id_new_row_last():
    a, b, new = SimpleNamespace(id=5), SimpleNamespace(id=3), SimpleNamespace(id=None)
    char = SimpleNamespace(classes=[a, b, new])
    ctx = lambda row: RuleContext(char=char, edition="2014", class_row=row, class_level=1)  # noqa: E731
    assert [first_class(ctx(r)) for r in (a, b, new)] == [False, True, False]
    alone = SimpleNamespace(id=None)
    assert first_class(RuleContext(char=SimpleNamespace(classes=[alone]), edition="2014", class_row=alone, class_level=1))
