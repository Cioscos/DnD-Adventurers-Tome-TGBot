"""Rule execution engine — runs a single trigger's effects."""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.services.homebrew.actions import execute_action
from api.services.homebrew.dsl import RuleDSL, Trigger
from api.services.homebrew.exceptions import (
    ActionExecutionError, DSLValidationError,
)
from api.services.homebrew.filters import evaluate_filters
from api.services.homebrew.types import ExecutionContext, RuleFiringResult
from core.db.models import Character, HomebrewRule

logger = logging.getLogger(__name__)


class RuleEngine:
    """Stateless engine — instance per request, not per rule."""

    async def execute_trigger(
        self,
        rule: HomebrewRule,
        trigger: dict,
        ctx: ExecutionContext,
        session: AsyncSession,
        char: Character,
    ) -> Optional[RuleFiringResult]:
        # Parse the rule DSL once (fail fast if invalid).
        try:
            rule_dsl = RuleDSL.model_validate(rule.dsl)
        except Exception as e:
            logger.warning("Rule %d DSL invalid, skipping: %s", rule.id, e)
            raise DSLValidationError(str(e)) from e

        # Parse the trigger to access filters as Filter objects.
        trigger_obj = Trigger.model_validate(trigger)

        if not evaluate_filters(trigger_obj.filters, ctx.to_dict()):
            return None

        rfr = RuleFiringResult(rule_id=rule.id, rule_name=rule.name)

        for effect in trigger.get("effects", []):
            try:
                await execute_action(effect, ctx, rfr, session, char, rule=rule_dsl)
            except ActionExecutionError as e:
                rfr.errors.append(str(e))
                logger.warning(
                    "Rule %d effect %s failed: %s", rule.id, effect.get("action"), e,
                )
                # continue with remaining effects
        return rfr
