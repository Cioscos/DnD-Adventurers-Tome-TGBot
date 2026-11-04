import pytest

from core.rules.edition import CLASS_KEYS
from core.rules.sample_characters import FIRST_SUBCLASS
from core.rules.subclasses import match_subclass, subclasses_for


def test_catalog_counts():
    assert sum(len(subclasses_for("2014", k)) for k in CLASS_KEYS) == 40
    assert sum(len(subclasses_for("2024", k)) for k in CLASS_KEYS) == 48


def test_match_variants():
    assert match_subclass("cammino del berserker", "barbarian", "2014") == "berserker"
    assert match_subclass("Path of the Berserker", "barbarian", "2014") == "berserker"
    assert match_subclass("Dominio dell'Inganno", "cleric", "2014") == "trickery"
    assert match_subclass("Trickery Domain", "cleric", "2024") == "trickery"
    assert match_subclass("Via dell'Ombra", "monk", "2014") == "shadow"
    assert match_subclass("Il Signore Fatato", "warlock", "2014") == "archfey"


def test_unknown_text_stays_unmatched():
    assert match_subclass("Ladro Acrobata", "rogue", "2014") is None
    assert match_subclass("Berserk", "barbarian", "2014") is None  # nessuna corrispondenza approssimata
    assert match_subclass("Campione", None, "2014") is None


def test_subclass_missing_from_other_edition_is_unmatched():
    assert match_subclass("Cammino del Combattente Totemico", "barbarian", "2024") is None


def test_names_are_unique_after_normalisation():
    for ed in ("2014", "2024"):
        for k in CLASS_KEYS:
            for s in subclasses_for(ed, k):
                assert match_subclass(s.name["it"], k, ed) == s.key == match_subclass(s.name["en"], k, ed)


@pytest.mark.parametrize("ed", ["2014", "2024"])
def test_seed_sample_texts_are_recognised(ed):
    for k, text in FIRST_SUBCLASS[ed].items():
        assert match_subclass(text, k, ed) is not None, (ed, k, text)
