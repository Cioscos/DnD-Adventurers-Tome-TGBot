"""Pure unit tests for the ORM model properties/methods and enums.

These exercise the D&D 5e math that lives directly on ``core/db/models.py``
(``Character.proficiency_bonus``, ``SpellSlot.use_slot``, ``Currency.convert``,
``Ability.use``, ``AbilityScore.modifier``) plus the integrity of the SQLAlchemy
enums. Everything here is **pure**: models are instantiated transiently (no DB
session, no async), so the tests are fast and free of fixtures.

See ``[[reference_sqlalchemy_enum_passthrough]]`` for why the enum members and
their string values are asserted explicitly.
"""

import pytest

from core.db.models import (
    Ability,
    AbilityScore,
    Character,
    CharacterClass,
    Currency,
    EquipmentSlot,
    FileType,
    RestorationType,
    SessionRole,
    SessionStatus,
    SpellSlot,
    SpellSlotsMode,
)


# ---------------------------------------------------------------------------
# Character
# ---------------------------------------------------------------------------

class TestCharacter:
    def test_ac_is_sum_of_three_components(self):
        c = Character(base_armor_class=14, shield_armor_class=2, magic_armor=1)
        assert c.ac == 17

    def test_total_level_empty(self):
        c = Character()
        c.classes = []
        assert c.total_level == 0

    def test_total_level_multiclass_sums_levels(self):
        c = Character()
        c.classes = [
            CharacterClass(class_name="fighter", level=3),
            CharacterClass(class_name="wizard", level=2),
        ]
        assert c.total_level == 5

    @pytest.mark.parametrize(
        "level,expected",
        [
            (0, 2),   # no class yet → +2
            (1, 2),
            (4, 2),
            (5, 3),   # boundary into +3
            (8, 3),
            (9, 4),
            (12, 4),
            (13, 5),
            (16, 5),
            (17, 6),
            (20, 6),  # cap
        ],
    )
    def test_proficiency_bonus_5e_table(self, level, expected):
        c = Character()
        c.classes = [CharacterClass(class_name="fighter", level=level)] if level else []
        assert c.proficiency_bonus == expected

    def test_class_summary_no_classes(self):
        c = Character()
        c.classes = []
        assert c.class_summary == "Nessuna classe"

    def test_class_summary_single_class_with_subclass(self):
        c = Character()
        c.classes = [CharacterClass(class_name="wizard", level=3, subclass="Evocazione")]
        assert c.class_summary == "wizard 3 (Evocazione)"

    def test_class_summary_multiclass_joined(self):
        c = Character()
        c.classes = [
            CharacterClass(class_name="fighter", level=3),
            CharacterClass(class_name="rogue", level=2),
        ]
        assert c.class_summary == "fighter 3 / rogue 2"

    def test_recalculate_encumbrance_sums_weight_times_quantity(self):
        from core.db.models import Item

        c = Character()
        c.items = [
            Item(name="Spada", weight=3.0, quantity=1),
            Item(name="Razioni", weight=2.0, quantity=5),
        ]
        c.recalculate_encumbrance()
        assert c.encumbrance == 13.0

    def test_recalculate_carry_capacity_is_strength_times_15(self):
        c = Character()
        c.carry_capacity_override = False
        c.ability_scores = [AbilityScore(name="strength", value=16)]
        c.recalculate_carry_capacity()
        assert c.carry_capacity == 240

    def test_recalculate_carry_capacity_defaults_to_10_when_no_strength(self):
        c = Character()
        c.carry_capacity_override = False
        c.ability_scores = []
        c.recalculate_carry_capacity()
        assert c.carry_capacity == 150  # 10 * 15

    def test_recalculate_carry_capacity_respects_override(self):
        c = Character()
        c.carry_capacity_override = True
        c.carry_capacity = 999
        c.ability_scores = [AbilityScore(name="strength", value=20)]
        c.recalculate_carry_capacity()
        assert c.carry_capacity == 999  # untouched


# ---------------------------------------------------------------------------
# AbilityScore
# ---------------------------------------------------------------------------

class TestAbilityScore:
    @pytest.mark.parametrize(
        "value,modifier",
        [
            (1, -5),   # floor division, not round-toward-zero
            (7, -2),
            (8, -1),
            (10, 0),
            (11, 0),
            (15, 2),
            (16, 3),
            (20, 5),
            (30, 10),
        ],
    )
    def test_modifier_uses_floor_division(self, value, modifier):
        assert AbilityScore(name="strength", value=value).modifier == modifier


# ---------------------------------------------------------------------------
# SpellSlot
# ---------------------------------------------------------------------------

class TestSpellSlot:
    def test_available_is_total_minus_used(self):
        assert SpellSlot(level=1, total=3, used=1).available == 2

    def test_available_never_negative(self):
        assert SpellSlot(level=1, total=2, used=5).available == 0

    def test_use_slot_increments_used(self):
        s = SpellSlot(level=1, total=2, used=0)
        s.use_slot()
        assert s.used == 1
        assert s.available == 1

    def test_use_slot_raises_when_exhausted(self):
        s = SpellSlot(level=1, total=1, used=1)
        with pytest.raises(ValueError):
            s.use_slot()
        assert s.used == 1  # unchanged

    def test_restore_slot_decrements_floor_at_zero(self):
        s = SpellSlot(level=1, total=2, used=1)
        s.restore_slot()
        assert s.used == 0
        s.restore_slot()  # already 0 → no-op, no underflow
        assert s.used == 0

    def test_restore_all_zeroes_used(self):
        s = SpellSlot(level=3, total=4, used=3)
        s.restore_all()
        assert s.used == 0


# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------

class TestCurrency:
    def test_rates_are_the_official_5e_table(self):
        assert Currency.RATES == {
            "copper": 1,
            "silver": 10,
            "electrum": 50,
            "gold": 100,
            "platinum": 1000,
        }

    def test_total_in_copper(self):
        c = Currency(copper=5, silver=2, electrum=1, gold=1, platinum=1)
        # 5 + 20 + 50 + 100 + 1000 = 1175
        assert c.total_in_copper() == 1175

    def test_convert_down_succeeds_exact(self):
        c = Currency(copper=0, silver=0, electrum=0, gold=1, platinum=0)
        assert c.convert("gold", "silver", 1) is True
        assert c.gold == 0
        assert c.silver == 10  # 100 copper / 10 = 10 sp, no remainder
        assert c.copper == 0

    def test_convert_up_returns_remainder_in_copper(self):
        # 5 sp = 50 copper → 0 gp (needs 100) + 50 cp remainder. No value lost.
        c = Currency(copper=0, silver=5, electrum=0, gold=0, platinum=0)
        before = c.total_in_copper()
        assert c.convert("silver", "gold", 5) is True
        assert c.silver == 0
        assert c.gold == 0
        assert c.copper == 50
        assert c.total_in_copper() == before  # value-preserving

    def test_convert_insufficient_funds_is_noop(self):
        c = Currency(copper=0, silver=0, electrum=0, gold=0, platinum=0)
        assert c.convert("gold", "silver", 1) is False
        assert c.gold == 0
        assert c.silver == 0
        assert c.copper == 0


# ---------------------------------------------------------------------------
# Ability
# ---------------------------------------------------------------------------

class TestAbility:
    def test_use_decrements_uses(self):
        a = Ability(name="Furia", max_uses=3, uses=2)
        a.use()
        assert a.uses == 1

    def test_use_raises_when_no_uses_left(self):
        a = Ability(name="Furia", max_uses=3, uses=0)
        with pytest.raises(ValueError):
            a.use()
        assert a.uses == 0

    def test_use_is_noop_for_passive_without_max_uses(self):
        a = Ability(name="Visione del buio", max_uses=None, uses=None)
        a.use()  # must not raise
        assert a.uses is None

    def test_restore_resets_uses_to_max(self):
        a = Ability(name="Punti Ki", max_uses=5, uses=0)
        a.restore()
        assert a.uses == 5

    def test_restore_is_noop_without_max_uses(self):
        a = Ability(name="Tratto", max_uses=None, uses=None)
        a.restore()
        assert a.uses is None


# ---------------------------------------------------------------------------
# Enums — members + string values + str-mixin (LookupError-proof, see memory)
# ---------------------------------------------------------------------------

class TestEnums:
    def test_spell_slots_mode(self):
        assert {m.name: m.value for m in SpellSlotsMode} == {
            "AUTOMATIC": "automatic",
            "MANUAL": "manual",
        }

    def test_restoration_type(self):
        assert {m.name: m.value for m in RestorationType} == {
            "LONG_REST": "long_rest",
            "SHORT_REST": "short_rest",
            "NONE": "none",
            "MANUAL": "manual",
        }

    def test_file_type(self):
        assert {m.name: m.value for m in FileType} == {
            "PHOTO": "photo",
            "DOCUMENT": "document",
        }

    def test_session_role(self):
        assert {m.name: m.value for m in SessionRole} == {
            "GAME_MASTER": "game_master",
            "PLAYER": "player",
        }

    def test_session_status(self):
        assert {m.name: m.value for m in SessionStatus} == {
            "ACTIVE": "active",
            "CLOSED": "closed",
        }

    def test_equipment_slot_all_eleven_5e_slots(self):
        assert {m.name: m.value for m in EquipmentSlot} == {
            "HEAD": "head",
            "NECK": "neck",
            "CLOAK": "cloak",
            "BODY": "body",
            "HANDS": "hands",
            "RING1": "ring1",
            "RING2": "ring2",
            "FEET": "feet",
            "MAIN_HAND": "main_hand",
            "OFF_HAND": "off_hand",
            "AMMUNITION": "ammunition",
        }

    def test_enums_are_str_mixins(self):
        # str-mixin: members compare equal to their string value (used for
        # JSON serialization and DB passthrough). See the enum-passthrough memo.
        assert isinstance(EquipmentSlot.HEAD, str)
        assert EquipmentSlot.MAIN_HAND == "main_hand"
        assert RestorationType.SHORT_REST == "short_rest"
        assert SessionStatus.ACTIVE == "active"
