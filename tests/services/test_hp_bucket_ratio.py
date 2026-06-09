"""Unit test per hp_bucket_from_ratio (core/utils/session_view.py).

Scala identica a hp_bucket(char) per gli HP positivi; a 0 un mostro è
"dead" (niente death saves). Input None tollerati (colonne nullable).
"""
from core.utils.session_view import hp_bucket_from_ratio


def test_zero_or_negative_is_dead():
    assert hp_bucket_from_ratio(0, 10) == "dead"
    assert hp_bucket_from_ratio(-3, 10) == "dead"
    assert hp_bucket_from_ratio(None, 10) == "dead"


def test_missing_total_is_healthy():
    assert hp_bucket_from_ratio(5, None) == "healthy"
    assert hp_bucket_from_ratio(5, 0) == "healthy"


def test_ratio_thresholds():
    assert hp_bucket_from_ratio(10, 10) == "healthy"          # 100%
    assert hp_bucket_from_ratio(76, 100) == "healthy"         # 76%
    assert hp_bucket_from_ratio(75, 100) == "lightly_wounded" # 75%
    assert hp_bucket_from_ratio(51, 100) == "lightly_wounded" # 51%
    assert hp_bucket_from_ratio(50, 100) == "badly_wounded"   # 50%
    assert hp_bucket_from_ratio(1, 100) == "badly_wounded"    # 1%
