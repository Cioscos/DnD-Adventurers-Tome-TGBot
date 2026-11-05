"""Motore puro dei modificatori: condizioni per edizione e modificatori dei privilegi (Task 11)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.rules import modifiers as mod_module
from core.rules.modifiers import (
    Applied,
    collect_modifiers,
    compute_condition_effects,
    damage_taken_mode,
    effective_hp_max,
    effective_speed,
    final_mode,
    has_state,
    is_incapacitated,
    modifiers_for,
    passive_adjustment,
)
from core.rules.types import Modifier, RuleContext


def _char(conditions=None, edition="2014", **kw):
    base = dict(
        rules_edition=edition, conditions=conditions or {}, items=[], classes=[], settings={},
        general_proficiencies={}, active_states=[], hit_points=40, damage_modifiers={},
        proficiency_bonus=2, skills={}, saving_throws={}, shield_armor_class=0,
    )
    return SimpleNamespace(**{**base, **kw})


def _ctx(char, roll, **kw):
    return RuleContext(char=char, edition=char.rules_edition, roll=roll, **kw)


def test_poisoned_disadvantage_on_attack_and_skill_not_save():
    c = _char({"poisoned": True})
    assert modifiers_for(c, "attack").disadvantage
    assert modifiers_for(c, "skill", skill="athletics", ability="strength").disadvantage
    assert modifiers_for(c, "initiative", ability="dexterity").disadvantage
    assert not modifiers_for(c, "save", ability="strength").disadvantage
    assert "condition:poisoned" in modifiers_for(c, "attack").notes
    assert modifiers_for(c, "save", ability="strength").notes == []


@pytest.mark.parametrize("cond", ["stunned", "paralyzed", "petrified", "unconscious"])
def test_stunned_auto_fails_str_dex_saves(cond):
    c = _char({cond: True})
    assert modifiers_for(c, "save", ability="strength").auto_fail
    assert modifiers_for(c, "save", ability="dexterity").auto_fail
    assert not modifiers_for(c, "save", ability="wisdom").auto_fail
    assert not modifiers_for(c, "death_save").auto_fail


def test_stunned_speed_zero_2014_unchanged_2024():
    assert effective_speed(_char({"stunned": True}), 30) == 0
    assert effective_speed(_char({"stunned": True}, edition="2024"), 30) == 30


@pytest.mark.parametrize("edition", ["2014", "2024"])
@pytest.mark.parametrize("cond", ["grappled", "restrained", "paralyzed", "petrified", "unconscious"])
def test_conditions_with_speed_zero_in_both_editions(edition, cond):
    assert effective_speed(_char({cond: True}, edition=edition), 40) == 0


def test_exhaustion_2014_levels():
    def c(level):
        return _char({"exhaustion": level})
    # 1: svantaggio alle prove, non ad attacchi e TS
    assert modifiers_for(c(1), "skill", skill="stealth", ability="dexterity").disadvantage
    assert not modifiers_for(c(1), "attack").disadvantage
    assert not modifiers_for(c(2), "save", ability="wisdom").disadvantage
    # 2: velocità dimezzata
    assert effective_speed(c(1), 30) == 30
    assert effective_speed(c(2), 30) == 15
    # 3: svantaggio ad attacchi e tiri salvezza, anche contro morte e concentrazione
    assert modifiers_for(c(3), "attack").disadvantage
    assert modifiers_for(c(3), "save", ability="wisdom").disadvantage
    assert modifiers_for(c(3), "death_save").disadvantage
    assert modifiers_for(c(3), "concentration", ability="constitution").disadvantage
    # 4: PF massimi dimezzati
    assert effective_hp_max(c(3)) == 40
    assert effective_hp_max(c(4)) == 20
    assert effective_hp_max(c(4), homebrew_bonus=4) == 22
    # 5: velocità 0
    assert effective_speed(c(5), 30) == 0
    # nessun meno fisso nel 2014
    assert modifiers_for(c(5), "attack").flat == 0


def test_exhaustion_2024_minus_two_per_level():
    c = _char({"exhaustion": 3}, edition="2024")
    assert modifiers_for(c, "attack").flat == -6
    assert modifiers_for(c, "save", ability="wisdom").flat == -6
    assert modifiers_for(c, "death_save").flat == -6
    assert modifiers_for(c, "concentration", ability="constitution").flat == -6
    assert modifiers_for(c, "skill", skill="stealth", ability="dexterity").flat == -6
    assert modifiers_for(c, "initiative", ability="dexterity").flat == -6
    assert effective_speed(c, 30) == 15
    assert modifiers_for(c, "attack").disadvantage is False
    assert effective_hp_max(_char({"exhaustion": 4}, edition="2024")) == 40
    assert effective_speed(_char({"exhaustion": 5}, edition="2024"), 20) == 0  # mai negativa


def test_advantage_and_disadvantage_cancel():
    assert final_mode("advantage", Applied(disadvantage=True)) == "normal"
    assert final_mode("disadvantage", Applied(advantage=True)) == "normal"
    assert final_mode("normal", Applied(advantage=True, disadvantage=True)) == "normal"
    assert final_mode("normal", Applied(disadvantage=True)) == "disadvantage"
    assert final_mode("normal", Applied(advantage=True)) == "advantage"
    assert final_mode("advantage", Applied()) == "advantage"
    assert final_mode("disadvantage", Applied(disadvantage=True)) == "disadvantage"
    # più fonti dello stesso tipo contano una volta
    assert final_mode("normal", modifiers_for(_char({"poisoned": True, "prone": True}), "attack")) == "disadvantage"
    # invisibile (vantaggio) e avvelenato (svantaggio) si annullano
    assert final_mode("normal", modifiers_for(_char({"poisoned": True, "invisible": True}), "attack")) == "normal"


def test_invisible_initiative_advantage_only_2024():
    assert not modifiers_for(_char({"invisible": True}), "initiative", ability="dexterity").advantage
    assert modifiers_for(_char({"invisible": True}, edition="2024"), "initiative", ability="dexterity").advantage
    assert modifiers_for(_char({"invisible": True}), "attack").advantage


@pytest.mark.parametrize("cond", ["incapacitated", "stunned", "paralyzed", "petrified", "unconscious"])
def test_incapacitated_initiative_disadvantage_only_2024(cond):
    assert not modifiers_for(_char({cond: True}), "initiative", ability="dexterity").disadvantage
    assert modifiers_for(_char({cond: True}, edition="2024"), "initiative", ability="dexterity").disadvantage


def test_petrified_resists_all_without_writing_damage_modifiers():
    stored = {"resistances": [], "immunities": [], "vulnerabilities": ["fire"]}
    c = _char({"petrified": True}, damage_modifiers=stored)
    assert "all" in modifiers_for(c, None).resistances
    assert damage_taken_mode(c, "slashing") == "half"
    assert damage_taken_mode(c, None) == "half"  # danno senza tipo: «tutti i danni»
    assert damage_taken_mode(c, "fire") == "half_double"  # prima la resistenza, poi la vulnerabilità
    assert damage_taken_mode(c, "poison") == "immune"  # 2014
    assert damage_taken_mode(_char({"petrified": True}, edition="2024"), "poison") == "half"
    assert stored == {"resistances": [], "immunities": [], "vulnerabilities": ["fire"]}
    assert c.damage_modifiers is stored
    assert damage_taken_mode(_char(), "slashing") == "none"
    assert damage_taken_mode(_char(), None) == "none"


def test_petrified_suspends_poisoned():
    c = _char({"petrified": True, "poisoned": True})
    assert not modifiers_for(c, "attack").disadvantage


def test_condition_list_depends_on_the_roll():
    c = _char({"poisoned": True})
    effects = compute_condition_effects(c, "2014", _ctx(c, "attack"))
    assert [(m.target, m.source) for m in effects] == [("disadvantage", "condition:poisoned")]
    assert compute_condition_effects(c, "2014", _ctx(c, "save", ability="wisdom")) == []


def test_blinded_and_frightened_and_restrained():
    assert modifiers_for(_char({"blinded": True}), "attack").disadvantage
    assert modifiers_for(_char({"prone": True}), "attack").disadvantage
    assert modifiers_for(_char({"restrained": True}), "attack").disadvantage
    assert modifiers_for(_char({"restrained": True}), "save", ability="dexterity").disadvantage
    assert not modifiers_for(_char({"restrained": True}), "save", ability="wisdom").disadvantage
    # Spaventato, Afferrato e i sensi passano dalla conferma al tiro: test_rules_roll_options
    assert not modifiers_for(_char({"grappled": True}), "attack").disadvantage
    assert not modifiers_for(_char({"grappled": True}, edition="2024"), "attack").disadvantage
    blind = modifiers_for(_char({"blinded": True}), "skill", skill="perception", ability="wisdom")
    assert blind.notes == [] and not blind.auto_fail


def test_falsy_and_custom_conditions_are_ignored():
    c = _char({"poisoned": False, "custom:bleeding": {"rule_id": 1}, "exhaustion": 0})
    a = modifiers_for(c, "attack")
    assert a == Applied()


def test_is_incapacitated():
    assert not is_incapacitated(_char({"poisoned": True}))
    for cond in ("incapacitated", "stunned", "paralyzed", "petrified", "unconscious"):
        assert is_incapacitated(_char({cond: 1}))


def test_passive_adjustment_plus_minus_five():
    assert passive_adjustment(_char(), "perception") == 0
    assert passive_adjustment(_char({"poisoned": True}), "perception") == -5
    assert passive_adjustment(_char({"exhaustion": 1}), "insight") == -5


# --- Modificatori dei privilegi ---------------------------------------------------------------------------------------

def _with_features(monkeypatch, *mods, key="fighter.prova"):
    spec = SimpleNamespace(key=key, modifiers=mods)
    row = SimpleNamespace(level=7)
    monkeypatch.setattr(mod_module, "active_features", lambda char: [(spec, row)])


def test_feature_flat_value_when_and_note(monkeypatch):
    _with_features(
        monkeypatch,
        Modifier("attack", 2),
        Modifier("attack", lambda ctx: ctx.class_level, when=lambda ctx: ctx.ability == "strength"),
        Modifier("damage", 3, source="feature:altro"),
    )
    c = _char()
    a = modifiers_for(c, "attack", ability="dexterity")
    assert a.flat == 2 and a.notes == ["feature:fighter.prova"]
    assert modifiers_for(c, "attack", ability="strength").flat == 9
    dmg = modifiers_for(c, "damage")
    assert dmg.flat == 3 and dmg.notes == ["feature:altro"]


def test_flat_targets_are_scoped_to_their_roll(monkeypatch):
    _with_features(
        monkeypatch,
        Modifier("save", 1), Modifier("skill", 2), Modifier("initiative", 4), Modifier("passive", 8),
        Modifier("ac", 16), Modifier("speed", 10), Modifier("hp_max", 6),
    )
    c = _char()
    assert modifiers_for(c, "save", ability="wisdom").flat == 1
    assert modifiers_for(c, "death_save").flat == 1
    assert modifiers_for(c, "concentration", ability="constitution").flat == 1
    assert modifiers_for(c, "skill", skill="stealth").flat == 2
    assert modifiers_for(c, "ability", ability="strength").flat == 2
    assert modifiers_for(c, "initiative").flat == 4
    assert modifiers_for(c, "passive", skill="insight").flat == 8
    assert modifiers_for(c, "ac").flat == 16
    assert effective_speed(c, 30) == 40
    assert effective_hp_max(c) == 46
    assert passive_adjustment(c, "insight") == 8


def test_flags_thresholds_and_damage_types(monkeypatch):
    _with_features(
        monkeypatch,
        Modifier("advantage", 1, when=lambda ctx: ctx.roll == "save"),
        Modifier("auto_fail", 1, when=lambda ctx: ctx.skill == "stealth"),
        Modifier("min_d20", 10), Modifier("min_d20", 8),
        Modifier("crit_min", 19), Modifier("crit_min", 18),
        Modifier("resistance:fire", 1), Modifier("immunity:poison", 1),
    )
    c = _char()
    a = modifiers_for(c, "save", ability="wisdom")
    assert a.advantage and not a.auto_fail
    assert a.min_d20 == 10 and a.crit_min == 18
    assert a.resistances == {"fire"} and a.immunities == {"poison"}
    assert not modifiers_for(c, "attack").advantage
    assert modifiers_for(c, "skill", skill="stealth").auto_fail
    assert damage_taken_mode(c, "fire") == "half"
    assert damage_taken_mode(c, "poison") == "immune"


def test_half_prof_counts_once_and_only_without_proficiency(monkeypatch):
    _with_features(monkeypatch, Modifier("half_prof", 1), Modifier("half_prof", 1))
    c = _char(proficiency_bonus=5, skills={"arcana": True, "history": "expert"}, saving_throws={"wisdom": True})
    assert modifiers_for(c, "skill", skill="stealth").flat == 2
    assert modifiers_for(c, "skill", skill="arcana").flat == 0
    assert modifiers_for(c, "skill", skill="history").flat == 0
    assert modifiers_for(c, "initiative").flat == 2
    assert modifiers_for(c, "save", ability="wisdom").flat == 0
    assert modifiers_for(c, "save", ability="strength").flat == 2


def test_modifier_can_read_active_states_through_helper(monkeypatch):
    _with_features(monkeypatch, Modifier("damage", 2, when=lambda ctx: has_state(ctx, "ira")))
    assert modifiers_for(_char(), "damage").flat == 0
    raging = _char(active_states=[{"key": "ira", "feature_key": "x", "rounds_left": 5, "ends_on": [], "data": {}}])
    assert modifiers_for(raging, "damage").flat == 2


def test_feature_context_has_class_row(monkeypatch):
    seen = {}

    def value(ctx):
        seen["row"] = ctx.class_row
        return 0
    _with_features(monkeypatch, Modifier("attack", value))
    collect_modifiers(_ctx(_char(), "attack"))
    assert seen["row"].level == 7


def test_speed_zero_beats_bonuses_and_half_applies_after_sum(monkeypatch):
    _with_features(monkeypatch, Modifier("speed", 10))
    assert effective_speed(_char({"grappled": True}), 30) == 0
    assert effective_speed(_char({"exhaustion": 2}), 30) == 20  # (30 + 10) / 2


# --- Armatura non addestrata (R21) ------------------------------------------------------------------------------------

def _armor(armor_type="heavy"):
    return SimpleNamespace(item_type="armor", is_equipped=True, item_metadata={"armor_type": armor_type}, name="Corazza")


def _shield():
    return SimpleNamespace(item_type="shield", is_equipped=True, item_metadata={}, name="Scudo")


def _seeded(items, edition="2014", armor=("Armature leggere",), **kw):
    return _char(edition=edition, items=items, settings={"proficiencies_seeded": True},
                 general_proficiencies={"armor": list(armor), "weapons": [], "tools": [], "other": []}, **kw)


@pytest.mark.parametrize("edition", ["2014", "2024"])
def test_untrained_armor_disadvantage_on_str_dex_rolls(edition):
    c = _seeded([_armor()], edition)
    for roll, kw in [("attack", {"ability": "strength"}), ("save", {"ability": "dexterity"}),
                     ("skill", {"skill": "stealth", "ability": "dexterity"}), ("initiative", {"ability": "dexterity"})]:
        a = modifiers_for(c, roll, **kw)
        assert a.disadvantage and a.notes == ["armor:untrained"], roll
    assert not modifiers_for(c, "attack").disadvantage  # attacco non basato su FOR/DES (incantesimo)
    assert not modifiers_for(c, "save", ability="wisdom").disadvantage


def test_trained_unequipped_and_unknown_armor_have_no_penalty():
    assert not modifiers_for(_seeded([_armor("light")]), "attack", ability="strength").disadvantage
    worn = _armor()
    worn.is_equipped = False
    assert not modifiers_for(_seeded([worn]), "attack", ability="strength").disadvantage
    # personaggio mai seminato con elenco vuoto: non si toglie nulla (Review Focus 3)
    assert not modifiers_for(_char(items=[_armor()]), "attack", ability="strength").disadvantage


def test_untrained_shield_2014_disadvantage_2024_loses_ac():
    c14 = _seeded([_shield()], "2014", shield_armor_class=2)
    assert modifiers_for(c14, "attack", ability="strength").disadvantage
    assert modifiers_for(c14, "ac").flat == 0
    c24 = _seeded([_shield()], "2024", shield_armor_class=2)
    assert not modifiers_for(c24, "attack", ability="strength").disadvantage
    assert modifiers_for(c24, "ac").flat == -2
    trained = _seeded([_shield()], "2024", armor=("Scudi",), shield_armor_class=2)
    assert modifiers_for(trained, "ac").flat == 0
