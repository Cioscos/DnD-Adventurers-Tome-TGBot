"""Motore della conferma al tiro: opzioni disponibili, condizioni confermate, costi e casi dei privilegi reali."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.db.models import SpellSlot
from core.rules import catalog
from core.rules.modifiers import modifiers_for
from core.rules.roll_options import (
    OptionUnavailable, apply_options, refund_spent, roll_extra, roll_options_for, scale_damage,
)
from core.rules.types import Cost, FeatureSpec, RollOptionSpec, RuleContext

_FINESSE = '{"properties": ["finesse"], "weapon_type": "melee"}'


class _Session:
    def __init__(self) -> None:
        self.added: list = []

    def add(self, row) -> None:
        self.added.append(row)


def _char(conditions=None, edition="2014", class_key="rogue", level=5, **kw):
    base = dict(
        id=1, rules_edition=edition, conditions=conditions or {}, items=[], settings={}, active_states=[],
        classes=[SimpleNamespace(class_name=class_key, level=level, subclass_key=None, options={})],
        hit_points=40, damage_modifiers={}, proficiency_bonus=3, skills={}, saving_throws={}, shield_armor_class=0,
        general_proficiencies={}, turn_state={}, abilities=[], spell_slots=[],
    )
    return SimpleNamespace(**{**base, **kw})


def _ctx(char, roll, **kw):
    return RuleContext(char=char, edition=char.rules_edition, roll=roll, **kw)


def _keys(ctx):
    return [o.spec.key for o in roll_options_for(ctx)]


def _feature(*options, class_key="rogue", edition="2014", key="prova"):
    return FeatureSpec(
        key=key, class_key=class_key, edition=edition, level=1, source_title="Prova",
        name={"it": "Prova", "en": "Test"}, summary={"it": "x", "en": "x"}, action_type=None, roll_options=options,
    )


@pytest.fixture
def registry(monkeypatch):
    reg: dict = {}
    monkeypatch.setattr(catalog, "_REGISTRY", reg)

    def register(*options, class_key="rogue", edition="2014"):
        reg[(edition, class_key)] = (_feature(*options, class_key=class_key, edition=edition),)
    return register


def _slot(level, total=2, used=0, is_pact=False):
    return SpellSlot(level=level, total=total, used=used, is_pact=is_pact)


_LABEL = {"it": "Prova?", "en": "Test?"}


# --- I casi delle schede (2014/rogue.md, 2014/paladin.md, 2024/monk.md) --------------------------------------------

def _is_finesse_or_ranged(ctx):
    return ctx.item is not None and ("finesse" in ctx.item.item_metadata or '"ranged"' in ctx.item.item_metadata)


SNEAK = RollOptionSpec(
    key="sneak", phase="after_hit", rolls=("attack",), label=_LABEL, available=_is_finesse_or_ranged,
    extra_dice=lambda ctx, _i: f"{(ctx.class_level + 1) // 2}d6", once_per_turn=True,
)
SMITE = RollOptionSpec(
    key="smite", phase="after_hit", rolls=("attack",), label=_LABEL, requires_input="slot",
    cost=Cost(spell_slot_min=1), extra_dice=lambda _c, i: f"{min(5, i['slot_level'] + 1)}d8",
)
SMITE_UNDEAD = RollOptionSpec(
    key="smite_undead", phase="after_hit", rolls=("attack",), label=_LABEL, needs="smite",
    extra_dice=lambda _c, _i: "1d8",
)
UNCANNY = RollOptionSpec(
    key="uncanny", phase="damage_in", rolls=("damage_taken",), label=_LABEL, slot="reaction", multiplier=0.5,
)


def test_sneak_attack_dice_from_level_only_with_finesse_and_once_per_turn(registry):
    registry(SNEAK)
    char = _char()
    finesse = SimpleNamespace(item_metadata=_FINESSE)
    heavy = SimpleNamespace(item_metadata='{"properties": []}')
    assert _keys(_ctx(char, "attack", item=heavy)) == []
    assert _keys(_ctx(char, "attack")) == []
    ctx = _ctx(char, "attack", item=finesse)
    assert _keys(ctx) == ["sneak"]
    # il livello arriva dalla classe che possiede il privilegio
    applied = apply_options(_Session(), ctx, ["sneak"], {}, phase="after_hit")
    assert applied.extra_dice == ["3d6"] and applied.notes == ["feature:prova"]
    assert char.turn_state["once_per_turn"] == ["sneak"]
    assert _keys(ctx) == []
    with pytest.raises(OptionUnavailable):
        apply_options(_Session(), ctx, ["sneak"], {}, phase="after_hit")


def test_smite_spends_the_chosen_slot_and_scales_dice(registry):
    registry(SMITE, SMITE_UNDEAD, class_key="paladin")
    slots = [_slot(1, used=2), _slot(2), _slot(3)]
    char = _char(class_key="paladin", spell_slots=slots)
    ctx = _ctx(char, "attack")
    applied = apply_options(_Session(), ctx, ["smite", "smite_undead"], {"smite": {"slot_level": 2}}, phase="after_hit")
    assert applied.extra_dice == ["3d8", "1d8"]
    assert slots[1].used == 1 and slots[2].used == 0
    assert applied.spent == ["slot:2"]


@pytest.mark.parametrize("inputs", [{}, {"smite": {}}, {"smite": {"slot_level": 1}}, {"smite": {"slot_level": 9}},
                                    {"smite": {"slot_level": "2"}}])
def test_smite_needs_a_real_free_slot(registry, inputs):
    registry(SMITE, class_key="paladin")
    char = _char(class_key="paladin", spell_slots=[_slot(1, used=2), _slot(2)])
    with pytest.raises(OptionUnavailable):
        apply_options(_Session(), _ctx(char, "attack"), ["smite"], inputs, phase="after_hit")


def test_option_with_needs_alone_is_rejected(registry):
    registry(SMITE, SMITE_UNDEAD, class_key="paladin")
    char = _char(class_key="paladin", spell_slots=[_slot(1)])
    with pytest.raises(OptionUnavailable):
        apply_options(_Session(), _ctx(char, "attack"), ["smite_undead"], {}, phase="after_hit")


def test_slot_option_hidden_without_a_slot_at_the_minimum(registry):
    registry(RollOptionSpec(key="high", phase="after_hit", rolls=("attack",), label=_LABEL, requires_input="slot",
                            cost=Cost(spell_slot_min=2)))
    assert _keys(_ctx(_char(spell_slots=[_slot(1)]), "attack")) == []
    assert _keys(_ctx(_char(spell_slots=[_slot(2, used=2)]), "attack")) == []
    assert _keys(_ctx(_char(spell_slots=[_slot(2), _slot(1)]), "attack")) == ["high"]


def test_stunning_strike_spends_focus_once_per_turn(registry):
    registry(RollOptionSpec(key="stun", phase="after_hit", rolls=("attack",), label=_LABEL, once_per_turn=True,
                            cost=Cost(feature_key="monk.ki")), class_key="monk", edition="2024")
    ki = SimpleNamespace(feature_key="monk.ki", uses=1, max_uses=5)
    char = _char(class_key="monk", edition="2024", abilities=[ki])
    ctx = _ctx(char, "attack")
    assert _keys(ctx) == ["stun"]
    applied = apply_options(_Session(), ctx, ["stun"], {}, phase="after_hit")
    assert ki.uses == 0 and applied.spent == ["once:stun", "feature:monk.ki:1"]


def test_no_uses_or_missing_row_hides_the_option(registry):
    registry(RollOptionSpec(key="stun", phase="after_hit", rolls=("attack",), label=_LABEL,
                            cost=Cost(feature_key="monk.ki", amount=2)))
    assert _keys(_ctx(_char(), "attack")) == []
    low = SimpleNamespace(feature_key="monk.ki", uses=1, max_uses=5)
    assert _keys(_ctx(_char(abilities=[low]), "attack")) == []
    # senza massimo il contatore è illimitato, come in use_feature
    free = SimpleNamespace(feature_key="monk.ki", uses=None, max_uses=None)
    assert _keys(_ctx(_char(abilities=[free]), "attack")) == ["stun"]


def test_two_options_cannot_share_the_last_resource(registry):
    cost = Cost(feature_key="monk.ki")
    registry(RollOptionSpec(key="a", phase="after_hit", rolls=("attack",), label=_LABEL, cost=cost),
             RollOptionSpec(key="b", phase="after_hit", rolls=("attack",), label=_LABEL, cost=cost))
    ki = SimpleNamespace(feature_key="monk.ki", uses=1, max_uses=5)
    with pytest.raises(OptionUnavailable):
        apply_options(_Session(), _ctx(_char(abilities=[ki]), "attack"), ["a", "b"], {}, phase="after_hit")


def test_supreme_sneak_mode_only_on_stealth(registry):
    registry(RollOptionSpec(key="supreme", phase="before", rolls=("skill",), label=_LABEL, mode="advantage",
                            available=lambda ctx: ctx.skill == "stealth"))
    char = _char()
    assert _keys(_ctx(char, "skill", skill="arcana")) == []
    ctx = _ctx(char, "skill", skill="stealth")
    assert apply_options(_Session(), ctx, ["supreme"]).mode == "advantage"


def test_uncanny_dodge_halves_and_spends_the_reaction(registry):
    registry(UNCANNY)
    char = _char()
    ctx = _ctx(char, "damage_taken")
    applied = apply_options(_Session(), ctx, ["uncanny"], {}, phase="damage_in")
    assert applied.multiplier == 0.5 and char.turn_state["reaction_used"] is True
    assert applied.spent == ["turn:reaction"]
    assert scale_damage(15, applied.multiplier) == 7
    assert _keys(ctx) == []


def test_deflect_reduces_with_dice_and_filters_the_damage_type(registry):
    registry(RollOptionSpec(
        key="deflect", phase="damage_in", rolls=("damage_taken",), label=_LABEL, slot="reaction",
        available=lambda ctx: ctx.damage_type in ("bludgeoning", "piercing", "slashing"),
        extra_dice=lambda _c, _i: "1d10", bonus=lambda ctx, _i: ctx.class_level + 2,
    ))
    char = _char()
    assert _keys(_ctx(char, "damage_taken", damage_type="fire")) == []
    applied = apply_options(_Session(), _ctx(char, "damage_taken", damage_type="piercing"), ["deflect"], {},
                            phase="damage_in")
    assert applied.extra_dice == ["1d10"] and applied.bonus == 7


def test_assassinate_forces_the_critical(registry):
    registry(RollOptionSpec(key="assassinate", phase="before", rolls=("attack",), label=_LABEL, force_crit=True))
    assert apply_options(_Session(), _ctx(_char(), "attack"), ["assassinate"]).force_crit is True


def test_force_crit_after_the_hit_is_a_catalog_error():
    with pytest.raises(ValueError):
        RollOptionSpec(key="x", phase="after_hit", rolls=("attack",), label=_LABEL, force_crit=True)


def test_option_of_another_phase_is_rejected(registry):
    registry(SNEAK)
    ctx = _ctx(_char(), "attack", item=SimpleNamespace(item_metadata=_FINESSE))
    with pytest.raises(OptionUnavailable):
        apply_options(_Session(), ctx, ["sneak"], {}, phase="before")


def test_spend_leaves_a_history_row_only_when_something_is_spent(registry):
    registry(UNCANNY, RollOptionSpec(key="free", phase="damage_in", rolls=("damage_taken",), label=_LABEL, multiplier=0))
    session = _Session()
    apply_options(session, _ctx(_char(), "damage_taken"), ["free"], {}, phase="damage_in")
    assert session.added == []
    apply_options(session, _ctx(_char(), "damage_taken"), ["uncanny"], {}, phase="damage_in")
    assert len(session.added) == 1 and session.added[0].event_type == "roll_option"


def test_multiplier_zero_and_double_round_down():
    assert scale_damage(15, 0) == 0
    assert scale_damage(15, 2) == 30
    assert scale_damage(1, 0.5) == 0


# --- Condizioni: R25 e R25 bis ----------------------------------------------------------------------------------

@pytest.mark.parametrize("edition", ["2014", "2024"])
@pytest.mark.parametrize("roll,kw", [("attack", {}), ("skill", {"skill": "stealth"}), ("initiative", {})])
def test_frightened_is_a_confirmation_not_an_automatic_disadvantage(registry, edition, roll, kw):
    char = _char({"frightened": True}, edition=edition)
    assert not modifiers_for(char, roll, ability="dexterity", **kw).disadvantage
    ctx = _ctx(char, roll, **kw)
    assert _keys(ctx) == ["condition:frightened"]
    applied = apply_options(_Session(), ctx, ["condition:frightened"])
    assert applied.mode == "disadvantage" and applied.notes == ["condition:frightened"]


def test_frightened_does_not_touch_saves_or_passives(registry):
    char = _char({"frightened": True})
    assert _keys(_ctx(char, "save", ability="wisdom")) == []
    assert not modifiers_for(char, "passive", skill="perception").disadvantage


def test_grappled_asks_on_attacks_only_in_2024(registry):
    assert _keys(_ctx(_char({"grappled": True}), "attack")) == []
    assert _keys(_ctx(_char({"grappled": True}, edition="2024"), "skill", skill="arcana")) == []
    char = _char({"grappled": True}, edition="2024")
    assert not modifiers_for(char, "attack").disadvantage
    assert _keys(_ctx(char, "attack")) == ["condition:grappled"]
    assert apply_options(_Session(), _ctx(char, "attack"), ["condition:grappled"]).mode == "disadvantage"


@pytest.mark.parametrize("condition", ["blinded", "deafened"])
@pytest.mark.parametrize("edition", ["2014", "2024"])
def test_senses_confirmed_auto_fail_on_checks(registry, condition, edition):
    char = _char({condition: True}, edition=edition)
    ctx = _ctx(char, "skill", skill="perception")
    assert _keys(ctx) == [f"condition:{condition}"]
    assert apply_options(_Session(), ctx, [f"condition:{condition}"]).auto_fail is True
    assert not modifiers_for(char, "skill", skill="perception", ability="wisdom").auto_fail
    assert modifiers_for(char, "skill", skill="perception", ability="wisdom").notes == []
    assert _keys(_ctx(char, "save", ability="wisdom")) == []
    assert _keys(_ctx(char, "attack")) == []


def test_opposite_confirmed_modes_cancel_out(registry):
    registry(RollOptionSpec(key="adv", phase="before", rolls=("skill",), label=_LABEL, mode="advantage"))
    ctx = _ctx(_char({"frightened": True}), "skill", skill="stealth")
    assert apply_options(_Session(), ctx, ["adv", "condition:frightened"]).mode == "normal"


# --- Dadi --------------------------------------------------------------------------------------------------------

def test_roll_extra_doubles_dice_not_the_flat_bonus():
    rolled, flat = roll_extra(["2d6+3"], critical=True)
    assert len(rolled) == 4 and flat == 3 and all(kind == "d6" and 1 <= v <= 6 for kind, v in rolled)
    rolled, flat = roll_extra(["2d6+3", "1d8"])
    assert [kind for kind, _ in rolled] == ["d6", "d6", "d8"] and flat == 3


# --- Forme del catalogo (revisione del Task 12) ---------------------------------------------------------------------

def _opt(key, **kw):
    return RollOptionSpec(key=key, phase=kw.pop("phase", "after_hit"), rolls=("attack",), label=_LABEL, **kw)


def test_group_allows_one_option_per_request(registry):
    registry(_opt("a", group="maneuver"), _opt("b", group="maneuver"), _opt("c"))
    ctx = _ctx(_char(), "attack")
    assert apply_options(_Session(), ctx, ["a", "c"], {}, phase="after_hit").keys == ["a", "c"]
    with pytest.raises(OptionUnavailable):
        apply_options(_Session(), ctx, ["a", "b"], {}, phase="after_hit")


def test_once_per_turn_registers_the_group(registry):
    registry(_opt("a", group="wrath", once_per_turn=True), _opt("b", group="wrath", once_per_turn=True))
    char = _char()
    ctx = _ctx(char, "attack")
    assert apply_options(_Session(), ctx, ["a"], {}, phase="after_hit").spent == ["once:wrath"]
    assert char.turn_state["once_per_turn"] == ["wrath"]
    assert _keys(ctx) == []


def test_dice_cost_takes_dice_from_the_needed_option(registry):
    sneak = _opt("sneak", extra_dice=lambda _c, _i: "3d6")
    registry(sneak, _opt("poison", needs="sneak", dice_cost=1), _opt("trip", needs="sneak", dice_cost=2))
    ctx = _ctx(_char(), "attack")
    assert apply_options(_Session(), ctx, ["poison", "sneak"], {}, phase="after_hit").extra_dice == ["2d6"]
    assert apply_options(_Session(), ctx, ["sneak", "poison", "trip"], {}, phase="after_hit").extra_dice == []


def test_dice_cost_above_the_dice_left_is_rejected(registry):
    registry(_opt("sneak", extra_dice=lambda _c, _i: "1d6"), _opt("ko", needs="sneak", dice_cost=2),
             _opt("plain"), _opt("bad", needs="plain", dice_cost=1))
    ctx = _ctx(_char(), "attack")
    with pytest.raises(OptionUnavailable):
        apply_options(_Session(), ctx, ["sneak", "ko"], {}, phase="after_hit")
    with pytest.raises(OptionUnavailable):
        apply_options(_Session(), ctx, ["plain", "bad"], {}, phase="after_hit")


def test_dice_cost_without_needs_is_a_catalog_error():
    with pytest.raises(ValueError):
        _opt("x", dice_cost=1)


def test_needs_is_satisfied_by_an_option_confirmed_in_an_earlier_phase(registry):
    registry(_opt("reckless", phase="before"), _opt("brutal", needs="reckless", extra_dice=lambda _c, _i: "1d10"))
    char = _char()
    with pytest.raises(OptionUnavailable):
        apply_options(_Session(), _ctx(char, "attack"), ["brutal"], {}, phase="after_hit")
    ctx = _ctx(char, "attack", confirmed=("reckless",))
    assert apply_options(_Session(), ctx, ["brutal"], {}, phase="after_hit").extra_dice == ["1d10"]


def test_confirmed_does_not_satisfy_needs_before_the_roll(registry):
    registry(_opt("x", phase="before"), _opt("y", phase="before", needs="x"))
    ctx = _ctx(_char(), "attack", confirmed=("x",))
    with pytest.raises(OptionUnavailable):
        apply_options(_Session(), ctx, ["y"])


def test_dice_that_do_not_double_and_separate_dice_have_their_own_lists(registry):
    registry(_opt("hellish", extra_dice=lambda _c, _i: "2d6", crit_doubles=False),
             _opt("sweep", extra_dice=lambda _c, _i: "1d8", crit_doubles=False, separate_damage=True),
             _opt("sneak", extra_dice=lambda _c, _i: "1d6"))
    applied = apply_options(_Session(), _ctx(_char(), "attack"), ["hellish", "sweep", "sneak"], {}, phase="after_hit")
    assert applied.extra_dice == ["1d6"] and applied.fixed_dice == ["2d6"] and applied.separate_dice == [["1d8", False]]


def test_on_confirm_receives_the_owner_context_and_inputs(registry):
    calls = []
    registry(_opt("smite", requires_input="slot", cost=Cost(spell_slot_min=1),
                  on_confirm=lambda session, ctx, inputs: calls.append((session, ctx.class_level, inputs))))
    session = _Session()
    apply_options(session, _ctx(_char(spell_slots=[_slot(1)]), "attack"), ["smite"], {"smite": {"slot_level": 1}},
                  phase="after_hit")
    assert calls == [(session, 5, {"slot_level": 1})]


def test_on_confirm_is_not_called_when_the_option_cannot_be_paid(registry):
    calls = []
    registry(_opt("smite", requires_input="slot", cost=Cost(spell_slot_min=1), on_confirm=lambda *a: calls.append(a)))
    with pytest.raises(OptionUnavailable):
        apply_options(_Session(), _ctx(_char(spell_slots=[_slot(1)]), "attack"), ["smite"], {"smite": {"slot_level": 3}},
                      phase="after_hit")
    assert calls == []


def test_refund_spent_gives_back_every_token(registry):
    registry(_opt("all", once_per_turn=True, slot="reaction", requires_input="slot",
                  cost=Cost(feature_key="monk.ki", amount=2, spell_slot_min=1)))
    ki = SimpleNamespace(feature_key="monk.ki", uses=3, max_uses=5)
    regular, pact = _slot(2, used=2), _slot(2, is_pact=True)
    char = _char(abilities=[ki], spell_slots=[regular, pact])
    spent = apply_options(_Session(), _ctx(char, "attack"), ["all"], {"all": {"slot_level": 2}}, phase="after_hit").spent
    assert spent == ["once:all", "turn:reaction", "feature:monk.ki:2", "slot:2:pact"]
    assert (ki.uses, pact.used, char.turn_state["reaction_used"]) == (1, 1, True)
    refund_spent(char, spent)
    assert (ki.uses, pact.used, regular.used) == (3, 0, 2)
    assert char.turn_state["reaction_used"] is False and char.turn_state["once_per_turn"] == []


def test_refund_gives_back_the_extra_action_not_the_action(registry):
    registry(_opt("act", slot="action"))
    char = _char(turn_state={"action_used": True, "extra_actions": 1})
    spent = apply_options(_Session(), _ctx(char, "attack"), ["act"], {}, phase="after_hit").spent
    assert spent == ["turn:extra_action"] and char.turn_state["extra_actions"] == 0
    refund_spent(char, spent)
    assert char.turn_state == {"action_used": True, "extra_actions": 1}


def test_refund_never_exceeds_the_maximum():
    ki = SimpleNamespace(feature_key="monk.ki", uses=5, max_uses=5)
    char = _char(abilities=[ki])
    refund_spent(char, ["feature:monk.ki:2"])
    assert ki.uses == 5
