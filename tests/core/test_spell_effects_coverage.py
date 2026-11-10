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
