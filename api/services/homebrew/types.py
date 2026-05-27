"""Runtime types: execution context + firing results."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Severity = Literal["info", "warning", "success", "error"]


@dataclass
class Notification:
    severity: Severity
    message: str
    rule_id: int | None = None
    rule_name: str | None = None


@dataclass
class HistoryEntry:
    description: str
    meta: dict | None = None


@dataclass
class ExecutionContext:
    """Mutable runtime state during one trigger execution."""
    event_type: str
    event_payload: dict
    subject: dict  # _kind in {item, character, ability}
    character: dict
    vars: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(
        cls, event_type: str, event_payload: dict,
        subject: dict | None = None, character: dict | None = None,
    ) -> "ExecutionContext":
        return cls(
            event_type=event_type,
            event_payload=event_payload or {},
            subject=subject or {},
            character=character or {},
            vars={},
        )

    def set_var(self, name: str, value: Any) -> None:
        self.vars[name] = value

    def to_dict(self) -> dict:
        return {
            "event": self.event_payload,
            "subject": self.subject,
            "character": self.character,
            "vars": self.vars,
        }


@dataclass
class RuleFiringResult:
    rule_id: int
    rule_name: str
    notifications: list[Notification] = field(default_factory=list)
    history_entries: list[HistoryEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def add_notification(self, n: Notification) -> None:
        if n.rule_id is None:
            n.rule_id = self.rule_id
        if n.rule_name is None:
            n.rule_name = self.rule_name
        self.notifications.append(n)

    def add_history_entry(self, description: str, meta: dict | None = None) -> None:
        self.history_entries.append(HistoryEntry(description=description, meta=meta))
