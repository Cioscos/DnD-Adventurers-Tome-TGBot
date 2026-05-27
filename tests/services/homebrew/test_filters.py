import pytest
from api.services.homebrew.dsl import Filter, FilterOp
from api.services.homebrew.filters import evaluate_filter, evaluate_filters


_BASE_CTX = {
    "event": {"is_fumble": True, "to_hit_die": 1, "damage_total": 0},
    "subject": {"_kind": "item", "metadata": {"hb_quality": "pessima"}, "name": "Spada"},
    "character": {"current_hit_points": 5},
    "vars": {},
}


@pytest.mark.parametrize("op,a,b,expected", [
    (FilterOp.EQ, 1, 1, True),
    (FilterOp.EQ, "x", "y", False),
    (FilterOp.NEQ, 1, 2, True),
    (FilterOp.LT, 1, 2, True),
    (FilterOp.LTE, 2, 2, True),
    (FilterOp.GT, 3, 2, True),
    (FilterOp.GTE, 2, 2, True),
])
def test_simple_operators(op, a, b, expected):
    f = Filter(path="$vars.a", op=op, value=b)
    ctx = {**_BASE_CTX, "vars": {"a": a}}
    assert evaluate_filter(f, ctx) is expected


def test_in_operator():
    f = Filter(path="$event.to_hit_die", op=FilterOp.IN, value=[1, 2, 3])
    assert evaluate_filter(f, _BASE_CTX) is True


def test_has_property_true():
    f = Filter(path="$subject", op=FilterOp.HAS_PROPERTY, value="quality")
    assert evaluate_filter(f, _BASE_CTX) is True


def test_has_property_false_when_absent():
    f = Filter(path="$subject", op=FilterOp.HAS_PROPERTY, value="enchanted")
    assert evaluate_filter(f, _BASE_CTX) is False


def test_evaluate_filters_all_and():
    filters = [
        Filter(path="$event.is_fumble", op=FilterOp.EQ, value=True),
        Filter(path="$subject", op=FilterOp.HAS_PROPERTY, value="quality"),
    ]
    assert evaluate_filters(filters, _BASE_CTX) is True


def test_evaluate_filters_short_circuits_false():
    filters = [
        Filter(path="$event.is_fumble", op=FilterOp.EQ, value=False),  # fails
        Filter(path="$subject", op=FilterOp.HAS_PROPERTY, value="quality"),
    ]
    assert evaluate_filters(filters, _BASE_CTX) is False
