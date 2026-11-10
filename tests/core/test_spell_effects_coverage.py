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
    for index in TABLE_D:
        effect, variant = spell_effect("2024" if "2024" in TABLE_D[index] else "2014", index)
        assert variant.text and variant.text["it"] and variant.text["en"], index
        assert not variant.modifiers({}), index


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
