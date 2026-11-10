"""Copertura del catalogo degli incantesimi: ogni riga delle tabelle A, B, C e D dell'inventario ha una voce per le edizioni indicate."""
import pytest

from core.rules.catalog.spells import SPELL_EFFECTS, spell_effect

BOTH, Y14, Y24 = ("2014", "2024"), ("2014",), ("2024",)

TABLE_A = {  # A01..A59
    "aid": BOTH, "armor-of-agathys": BOTH, "aura-of-life": BOTH, "aura-of-purity": BOTH, "aura-of-vitality": BOTH, "barkskin": BOTH,
    "beacon-of-hope": BOTH, "bless": BOTH, "blur": BOTH, "blade-ward": BOTH, "crusaders-mantle": BOTH, "death-ward": BOTH,
    "divine-favor": BOTH, "dragons-breath": Y24, "elemental-weapon": BOTH, "enhance-ability": BOTH, "expeditious-retreat": BOTH,
    "false-life": BOTH, "feather-fall": BOTH, "feign-death": BOTH, "fire-shield": BOTH, "fly": BOTH, "foresight": BOTH,
    "freedom-of-movement": BOTH, "greater-invisibility": BOTH, "invisibility": BOTH, "guidance": BOTH, "haste": BOTH,
    "heroism": BOTH, "holy-aura": BOTH, "jump": BOTH, "longstrider": BOTH, "mage-armor": BOTH, "magic-weapon": BOTH,
    "mind-blank": BOTH, "pass-without-trace": BOTH, "protection-from-energy": BOTH, "protection-from-evil-and-good": BOTH,
    "protection-from-poison": BOTH, "regenerate": BOTH, "resistance": BOTH, "shield": BOTH, "shield-of-faith": BOTH,
    "shillelagh": BOTH, "stoneskin": BOTH, "warding-bond": BOTH, "water-breathing": BOTH, "water-walk": BOTH, "darkvision": BOTH,
    "true-seeing": BOTH, "see-invisibility": BOTH, "levitate": BOTH, "fount-of-moonlight": Y24, "heroes-feast": BOTH,
    "power-word-fortify": Y24, "circle-of-power": BOTH, "dispel-evil-and-good": BOTH, "conjure-minor-elementals": Y24,
    "swift-quiver": BOTH,
}
# Punizione Divina 2024 resta il privilegio del Paladino (test_spell_effects_marks): nessuna voce di incantesimo, o la punizione si conterebbe due volte
TABLE_B = {
    "hex": BOTH, "hunters-mark": BOTH, "blinding-smite": BOTH, "branding-smite": Y14, "shining-smite": Y24,
    "searing-smite": BOTH, "wrathful-smite": BOTH, "thunderous-smite": BOTH, "banishing-smite": BOTH, "staggering-smite": BOTH,
    "ensnaring-strike": BOTH, "hail-of-thorns": BOTH, "lightning-arrow": BOTH, "true-strike": BOTH,
}
TABLE_C = {
    "chromatic-orb": BOTH, "dragons-breath": Y24, "elemental-weapon": BOTH, "protection-from-energy": BOTH, "resistance": Y24,
    "fire-shield": BOTH, "glyph-of-warding": BOTH, "destructive-wave": BOTH, "sorcerous-burst": Y24, "conjure-minor-elementals": Y24,
    "conjure-elemental": Y24, "alter-self": Y24, "flame-strike": Y14, "hunger-of-hadar": Y24, "conjure-barrage": Y14,
    "conjure-volley": Y14, "hallow": BOTH, "wish": BOTH,
}
# D: solo testo con nome e durata (Calmare Emozioni resta alla rimozione delle condizioni, vedi condition_removal)
TABLE_D = {
    "enlarge-reduce": BOTH, "polymorph": BOTH, "animal-shapes": BOTH, "shapechange": BOTH, "true-polymorph": BOTH, "alter-self": BOTH,
    "gaseous-form": BOTH, "wind-walk": BOTH, "mirror-image": BOTH, "sanctuary": BOTH, "blink": BOTH, "glibness": BOTH,
    "conjure-celestial": Y24, "antilife-shell": BOTH, "antimagic-field": BOTH, "globe-of-invulnerability": BOTH,
    "magic-circle": BOTH, "leomunds-tiny-hut": BOTH, "hallow": BOTH,
}

CASES = sorted({(i, ed) for t in (TABLE_A, TABLE_B, TABLE_C, TABLE_D) for i, eds in t.items() for ed in eds})


@pytest.mark.parametrize("index,edition", CASES)
def test_every_inventory_spell_has_a_catalog_entry(index, edition):
    assert spell_effect(edition, index) is not None, f"{index} ({edition}) manca nel catalogo"


def test_text_only_entries_have_italian_and_english_text():
    for index, editions in TABLE_D.items():  # ogni edizione indicata, non una sola
        for edition in editions:
            variant = spell_effect(edition, index)[1]
            assert variant.text and variant.text["it"] and variant.text["en"], (index, edition)
            assert not variant.modifiers({}), (index, edition)


def test_99_an_instant_text_entry_is_not_tracked_and_a_lasting_one_is():
    from core.rules.catalog.spells.texts import _instant, _text
    instant = _instant("Subito.", "Now.")
    assert instant.track is False and instant.rounds is None and not instant.concentration and instant.text == {"it": "Subito.", "en": "Now."}
    assert _text("Dura.", "Lasts.", 10).track is True
    for index, edition in (("wish", "2014"), ("wish", "2024"), ("destructive-wave", "2014"), ("destructive-wave", "2024"), ("flame-strike", "2014"), ("conjure-barrage", "2014"), ("conjure-volley", "2014")):
        assert spell_effect(edition, index)[1].track is False, (index, edition)


def test_registry_has_no_duplicate_srd_index():
    seen = [i for e in SPELL_EFFECTS.values() for i in e.srd_index]
    assert len(seen) == len(set(seen))


def _v(edition, index):
    return spell_effect(edition, index)[1]


def test_mirror_image_2014_thresholds_follow_the_manual():
    it = _v("2014", "mirror-image").text["it"]
    assert "6+ con 3 duplicati, 8+ con 2, 11+ con 1" in it
    assert "6+ with 3, 8+ with 2, 11+ with 1" in _v("2014", "mirror-image").text["en"]
    assert "3 o più" in _v("2024", "mirror-image").text["it"]


def test_animal_shapes_differs_by_edition():
    old, new = _v("2014", "animal-shapes"), _v("2024", "animal-shapes")
    assert old.concentration and not new.concentration
    assert new.rounds == old.rounds
    assert "PF temporanei" in new.text["it"] and "temporary HP" in new.text["en"]


@pytest.mark.parametrize("index", ["gaseous-form", "wind-walk"])
def test_gaseous_resistance_follows_edition(index):
    old, new = _v("2014", index), _v("2024", index)
    assert "non magic" in old.text["it"] and "nonmagical" in old.text["en"]
    for lang, words in (("it", ("contundenti", "perforanti", "taglienti", "Prono")), ("en", ("bludgeoning", "piercing", "slashing", "Prone"))):
        assert all(w in new.text[lang] for w in words)
        assert "nonmagical" not in new.text[lang] and "non magic" not in new.text[lang]


def test_other_rule_texts_match_the_manual():
    assert "incapacitati" in _v("2014", "wind-walk").text["it"]
    assert "Prono" in _v("2014", "destructive-wave").text["it"] and "Prone" in _v("2024", "destructive-wave").text["en"]
    assert "infligge danni" in _v("2024", "sanctuary").text["it"] and "deals damage" in _v("2024", "sanctuary").text["en"]


@pytest.mark.parametrize("edition,index,types", [("2014", "flame-strike", ["fire", "radiant"]), ("2024", "hunger-of-hadar", ["cold", "acid"])])
def test_t10_75_the_two_upcast_choices_of_table_c_ask_their_damage_type(edition, index, types):
    (choice,) = _v(edition, index).choices
    assert choice.key == "upcast_type" and choice.options(edition) == types


# 80: testi e alias verificati sul manuale (2014/spells.md, 2024/spells.md)
def test_t10_80_the_two_italian_2024_names_are_recognised_without_an_srd_index():
    assert spell_effect("2024", None, "Metamorfosi Suprema")[0].key == "shapechange"
    assert spell_effect("2024", None, "Parlantina")[0].key == "glibness"


def test_t10_80_animal_shapes_is_not_capped_at_ten_creatures():
    effect, _ = spell_effect("2014", "animal-shapes")
    assert effect.max_targets("2014", 8) > 10


def test_t10_80_shapechange_and_alter_self_follow_each_edition():
    old, new = _v("2014", "shapechange"), _v("2024", "shapechange")
    assert "PF temporanei" not in old.text["it"] and "PF temporanei" in new.text["it"] and "temporary HP" in new.text["en"]
    old, new = _v("2014", "alter-self"), _v("2024", "alter-self")
    assert "+1 a colpire" in old.text["it"] and "+1 to attack" in old.text["en"]
    assert "modificatore da incantatore" in new.text["it"] and "spellcasting modifier" in new.text["en"] and "+1" not in new.text["it"]


def test_t10_80_conjure_celestial_2024_offers_both_lights():
    text = _v("2024", "conjure-celestial").text
    assert "Luce Ardente" in text["it"] and "6d12" in text["it"] and "Searing Light" in text["en"] and "Healing Light" in text["en"]
