"""Homebrew engine custom exceptions."""


class HomebrewError(Exception):
    """Base for all homebrew engine errors."""


class DepthExceeded(HomebrewError):
    """Recursion depth limit reached during dispatch."""


class CycleDetected(HomebrewError):
    """A rule attempted to fire while already in execution stack."""


class DSLValidationError(HomebrewError):
    """Stored DSL fails Pydantic validation at runtime."""


class ActionExecutionError(HomebrewError):
    """A specific action's execution failed."""
