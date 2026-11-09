from types import SimpleNamespace

from core.rules.catalog.spells import spell_effect
from core.rules.modifiers import effective_speed, modifiers_for, rule_hp_bonus


def fake_char(active_states, edition="2014"):
    return SimpleNamespace(
        rules_edition=edition, conditions={}, items=[], classes=[], settings={}, general_proficiencies={},
        active_states=active_states, hit_points=40, damage_modifiers={}, proficiency_bonus=2, skills={},
        saving_throws={}, shield_armor_class=0,
    )


def _state(key, slot, edition):
    return [{"key": f"spell:{key}", "data": {"slot_level": slot, "spell_key": key, "edition": edition}}]


def test_lookup_by_srd_index_and_by_italian_name():
    eff, var = spell_effect("2014", "shield-of-faith")
    assert eff.key == "shield_of_faith"
    assert spell_effect("2024", None, "Scudo della Fede")[0].key == "shield_of_faith"
    assert spell_effect("2014", None, "Palla di Fuoco") is None


def test_lookup_by_name_covers_both_editions_it_and_en():
    for edition, name in (("2014", "Passo Veloce"), ("2024", "Passo Lungo"), ("2014", "Longstrider"), ("2024", "longstrider")):
        assert spell_effect(edition, None, name)[0].key == "longstrider"


def test_shield_of_faith_state_gives_plus_two_ac():
    char = fake_char(_state("shield_of_faith", 1, "2014"))
    applied = modifiers_for(char, "ac")
    assert applied.flat == 2 and "spell:shield_of_faith" in applied.notes


def test_aid_scales_with_the_slot():
    assert rule_hp_bonus(fake_char(_state("aid", 4, "2024"))) == 15
    assert rule_hp_bonus(fake_char(_state("aid", 2, "2014"))) == 5


def test_longstrider_adds_ten_feet():
    assert effective_speed(fake_char(_state("longstrider", 1, "2014")), 30) == 40


def test_unknown_spell_key_yields_nothing():
    assert modifiers_for(fake_char(_state("nope", 1, "2014")), "ac").flat == 0


def test_new_defense_states_are_read_by_the_rules():
    assert modifiers_for(fake_char(_state("stoneskin", 4, "2024")), None).resistances == {"bludgeoning", "piercing", "slashing"}
    assert not modifiers_for(fake_char(_state("stoneskin", 4, "2014")), None).resistances  # 2014: solo con la conferma «non magico» al danno
    assert modifiers_for(fake_char(_state("fly", 3, "2014")), None).fly_speed_value == 60
    assert modifiers_for(fake_char(_state("foresight", 9, "2024")), "attack").advantage
    assert not modifiers_for(fake_char(_state("foresight", 9, "2024")), "passive").advantage
    assert modifiers_for(fake_char(_state("mind_blank", 8, "2014")), None).immunities == {"psychic"}
    assert modifiers_for(fake_char(_state("true_seeing", 6, "2024")), None).senses == {"truesight": 120}
