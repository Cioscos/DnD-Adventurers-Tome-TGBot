from api.services.homebrew.types import ExecutionContext, RuleFiringResult, Notification


def test_execution_context_builds_initial_dict():
    ctx = ExecutionContext.new(
        event_type="attack_rolled",
        event_payload={"is_fumble": True},
        subject={"_kind": "item", "metadata": {}},
        character={"current_hit_points": 10},
    )
    d = ctx.to_dict()
    assert d["event"]["is_fumble"] is True
    assert d["vars"] == {}
    ctx.set_var("wear_roll", 7)
    assert ctx.to_dict()["vars"]["wear_roll"] == 7


def test_rule_firing_result_collects_notifications_and_history():
    rfr = RuleFiringResult(rule_id=42, rule_name="Quality & Wear")
    rfr.add_notification(Notification(severity="warning", message="Damaged!"))
    rfr.add_history_entry("Weapon damaged via Quality & Wear rule")
    assert len(rfr.notifications) == 1
    assert len(rfr.history_entries) == 1
