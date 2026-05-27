"""Path resolver: maps $event.X / $subject.X / $character.X / $<var> to values."""
import pytest
from api.services.homebrew.path_resolver import resolve_path, PathResolutionError


def test_resolve_literal_returns_self():
    ctx = {"event": {}, "subject": {}, "character": {}, "vars": {}}
    assert resolve_path("hello", ctx) == "hello"
    assert resolve_path(42, ctx) == 42


def test_resolve_event_path():
    ctx = {"event": {"is_fumble": True, "to_hit_die": 1}, "subject": {}, "character": {}, "vars": {}}
    assert resolve_path("$event.is_fumble", ctx) is True
    assert resolve_path("$event.to_hit_die", ctx) == 1


def test_resolve_subject_property_from_metadata():
    item_metadata = {"hb_quality": "pessima"}
    ctx = {
        "event": {},
        "subject": {"_kind": "item", "metadata": item_metadata, "name": "Spada"},
        "character": {}, "vars": {},
    }
    assert resolve_path("$subject.quality", ctx) == "pessima"
    assert resolve_path("$subject.name", ctx) == "Spada"


def test_resolve_subject_alone_is_dict():
    ctx = {"event": {}, "subject": {"_kind": "item", "metadata": {"hb_quality": "buona"}}, "character": {}, "vars": {}}
    result = resolve_path("$subject", ctx)
    assert result["_kind"] == "item"


def test_resolve_character_property():
    ctx = {"event": {}, "subject": {}, "character": {"current_hit_points": 14, "name": "X"}, "vars": {}}
    assert resolve_path("$character.current_hit_points", ctx) == 14


def test_resolve_var():
    ctx = {"event": {}, "subject": {}, "character": {}, "vars": {"wear_roll": 7, "wear_result": "D"}}
    assert resolve_path("$wear_roll", ctx) == 7
    assert resolve_path("$wear_result", ctx) == "D"


def test_resolve_unknown_path_raises():
    ctx = {"event": {}, "subject": {}, "character": {}, "vars": {}}
    with pytest.raises(PathResolutionError):
        resolve_path("$banana", ctx)


def test_resolve_unknown_event_field_raises():
    ctx = {"event": {"a": 1}, "subject": {}, "character": {}, "vars": {}}
    with pytest.raises(PathResolutionError):
        resolve_path("$event.b", ctx)
