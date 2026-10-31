from core.data.labels import condition_label


def test_condition_label_known_slug() -> None:
    assert condition_label("poisoned") == "Avvelenato"


def test_condition_label_hides_custom_prefix() -> None:
    assert condition_label("custom:bleeding") == "Bleeding"
    assert condition_label("custom:sanguinamento") == "Sanguinamento"
