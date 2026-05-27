"""Pydantic strict validation of the homebrew DSL."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.services.homebrew.dsl import Filter, Property, FilterOp


def test_filter_eq_accepts_string():
    f = Filter(path="$subject.quality", op=FilterOp.EQ, value="pessima")
    assert f.path == "$subject.quality"
    assert f.op == FilterOp.EQ
    assert f.value == "pessima"


def test_filter_invalid_op_rejected():
    with pytest.raises(ValidationError):
        Filter(path="$subject.x", op="banana", value=1)


def test_property_enum_requires_values():
    p = Property(
        key="quality", type="enum",
        values=["pessima", "ordinaria"], default="ordinaria",
        label_i18n={"it": "Qualità", "en": "Quality"},
    )
    assert p.default in p.values


def test_property_enum_default_must_be_in_values():
    with pytest.raises(ValidationError) as exc:
        Property(
            key="quality", type="enum",
            values=["pessima", "buona"], default="straordinaria",
            label_i18n={"it": "Qualità", "en": "Q"},
        )
    assert "default" in str(exc.value)


def test_property_key_lowercase_snake_case():
    with pytest.raises(ValidationError):
        Property(
            key="Bad Key!", type="enum", values=["a"], default="a",
            label_i18n={"it": "Test", "en": "Test"},
        )
