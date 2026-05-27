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


def test_lt_with_none_lhs_returns_false():
    f = Filter(path="$vars.a", op=FilterOp.LT, value=5)
    ctx = {**_BASE_CTX, "vars": {"a": None}}
    assert evaluate_filter(f, ctx) is False


def test_gte_with_none_lhs_returns_false():
    f = Filter(path="$vars.a", op=FilterOp.GTE, value=0)
    ctx = {**_BASE_CTX, "vars": {"a": None}}
    assert evaluate_filter(f, ctx) is False


def test_in_with_string_rhs_returns_false():
    # Guard against substring matching footgun
    f = Filter(path="$vars.a", op=FilterOp.IN, value="abc")
    ctx = {**_BASE_CTX, "vars": {"a": "a"}}
    assert evaluate_filter(f, ctx) is False


def test_in_with_non_iterable_rhs_returns_false():
    f = Filter(path="$vars.a", op=FilterOp.IN, value=42)
    ctx = {**_BASE_CTX, "vars": {"a": 42}}
    assert evaluate_filter(f, ctx) is False


def test_has_property_returns_false_when_metadata_is_str():
    # Defensive guard: metadata should be a dict, but if somehow it's still a JSON string,
    # HAS_PROPERTY must not silently substring-match.
    f = Filter(path="$subject", op=FilterOp.HAS_PROPERTY, value="quality")
    ctx = {**_BASE_CTX, "subject": {"_kind": "item", "metadata": '{"hb_quality":"x"}'}}
    assert evaluate_filter(f, ctx) is False
