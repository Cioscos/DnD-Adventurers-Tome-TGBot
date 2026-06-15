"""Homebrew rules CRUD + templates + resources."""
from __future__ import annotations

import json as _json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.auth import get_current_user
from api.database import get_db
from api.routers._helpers import collect_homebrew_notifications
from api.schemas.homebrew import (
    HomebrewResourceRead,
    HomebrewResourceUpdate,
    HomebrewRuleCreate,
    HomebrewRuleRead,
    HomebrewRuleUpdate,
    TemplateDetailRead,
    TemplateRead,
)
from api.services.homebrew.dispatcher import dispatch
from api.services.homebrew.templates import TEMPLATES, get_template
from core.db.models import Character, HomebrewResource, HomebrewRule, Item

router = APIRouter(tags=["homebrew"])


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


async def _get_owned_char(
    char_id: int, user_id: int, session: AsyncSession,
) -> Character:
    res = await session.execute(select(Character).where(Character.id == char_id))
    char = res.scalar_one_or_none()
    if char is None:
        raise HTTPException(404, "Character not found")
    if char.user_id != user_id:
        raise HTTPException(403, "Not your character")
    return char


async def _get_owned_rule(
    char_id: int, rule_id: int, user_id: int, session: AsyncSession,
) -> HomebrewRule:
    char = await _get_owned_char(char_id, user_id, session)
    res = await session.execute(
        select(HomebrewRule).where(
            HomebrewRule.id == rule_id,
            HomebrewRule.character_id == char.id,
        )
    )
    rule = res.scalar_one_or_none()
    if rule is None:
        raise HTTPException(404, "Rule not found")
    return rule


# ─── Templates ──────────────────────────────────────────────────────────────


# Templates are a public read-only catalogue — no auth required.
@router.get("/homebrew/templates", response_model=list[TemplateRead])
async def list_templates() -> list[dict]:
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "description": t["description"],
            "icon": t["icon"],
        }
        for t in TEMPLATES
    ]


@router.get("/homebrew/templates/{template_id}", response_model=TemplateDetailRead)
async def get_template_detail(template_id: str) -> dict:
    t = get_template(template_id)
    if t is None:
        raise HTTPException(404, "Template not found")
    return t


# ─── Rules read endpoints ───────────────────────────────────────────────────


@router.get(
    "/characters/{char_id}/homebrew/rules",
    response_model=list[HomebrewRuleRead],
)
async def list_rules(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[HomebrewRule]:
    char = await _get_owned_char(char_id, user_id, session)
    res = await session.execute(
        select(HomebrewRule)
        .where(HomebrewRule.character_id == char.id)
        .order_by(HomebrewRule.id.asc())
    )
    return list(res.scalars())


@router.get(
    "/characters/{char_id}/homebrew/rules/{rule_id}",
    response_model=HomebrewRuleRead,
)
async def get_rule(
    char_id: int, rule_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HomebrewRule:
    return await _get_owned_rule(char_id, rule_id, user_id, session)


# ─── Install template + Delete rule ─────────────────────────────────────────


async def _materialize_property_defaults(
    session: AsyncSession, char: Character, rule: HomebrewRule,
) -> None:
    """Write default values for each rule property into matching items' metadata.

    Only sets keys that are missing — does not overwrite existing values.
    """
    dsl = rule.dsl
    subject_def = dsl.get("subject", {})
    properties = dsl.get("properties", [])
    if not properties or subject_def.get("type") != "item":
        return
    item_types = (subject_def.get("filter") or {}).get("item_types")
    res = await session.execute(select(Item).where(Item.character_id == char.id))
    for item in res.scalars():
        if item_types and item.item_type not in item_types:
            continue
        md = _json.loads(item.item_metadata or "{}")
        changed = False
        for prop in properties:
            key = f"hb_{prop['key']}"
            if key not in md:
                md[key] = prop["default"]
                changed = True
        if changed:
            item.item_metadata = _json.dumps(md)


def _collect_referenced_resource_keys(dsl: dict) -> set[str]:
    """Walk every trigger → effects list (and nested if/match branches) and
    collect the resource keys referenced by ``change_resource`` and
    ``restore_resource`` actions.

    The traversal is purely structural — it does not validate the DSL; unknown
    action types are silently ignored so the function stays forward-compatible.
    """
    keys: set[str] = set()

    def _scan_effects(effects: list) -> None:
        for action in effects:
            if not isinstance(action, dict):
                continue
            action_type = action.get("action")
            if action_type in ("change_resource", "restore_resource"):
                key = action.get("key")
                if key and isinstance(key, str):
                    keys.add(key)
            # Recurse into `if` branches.
            elif action_type == "if":
                _scan_effects(action.get("then") or [])
                _scan_effects(action.get("else") or [])
            # Recurse into every `match` case list.
            elif action_type == "match":
                for case_effects in (action.get("cases") or {}).values():
                    if isinstance(case_effects, list):
                        _scan_effects(case_effects)

    for trigger in dsl.get("triggers") or []:
        if isinstance(trigger, dict):
            _scan_effects(trigger.get("effects") or [])

    return keys


async def _materialize_resources(
    session: AsyncSession, char: Character, rule: HomebrewRule,
) -> None:
    """Create HomebrewResource rows for a rule, covering two sources:

    1. **Explicit ResourceDefs** — declared in ``dsl["resources"]``.
       Raises HTTP 409 if a key already exists for this character (same
       behaviour as before, keeps the error loud so the author knows about the
       collision).

    2. **Inferred keys** — resource keys referenced by ``change_resource`` /
       ``restore_resource`` actions anywhere in the trigger graph but NOT
       covered by an explicit ResourceDef.  If such a key is NOT already owned
       as a resource, we reject the save with HTTP 422 (#14): the author must
       declare it in ``dsl["resources"]`` with explicit max/name/restoration_type
       (the editor's Resources section).  Keys already owned are accepted as-is
       (the action operates on the existing row).

    Idempotent: safe to call multiple times (update_rule calls it after every
    DSL change).  Rows are only ever ADDED, never removed — removing rows would
    lose the player's current resource value, which is unacceptable.
    """
    dsl = rule.dsl

    # ── 1. Explicit ResourceDefs ─────────────────────────────────────────────
    explicit_defs: list[dict] = dsl.get("resources") or []
    explicit_keys: set[str] = {r["key"] for r in explicit_defs}

    if explicit_keys:
        existing_res = await session.execute(
            select(HomebrewResource.key, HomebrewResource.rule_id).where(
                HomebrewResource.character_id == char.id,
                HomebrewResource.key.in_(list(explicit_keys)),
            )
        )
        # Map key → rule_id for existing rows.
        existing_explicit: dict[str, int] = {row[0]: row[1] for row in existing_res}
        for key in explicit_keys:
            if key in existing_explicit:
                # 409 only when the collision is with a *different* rule.
                # If the key is already owned by this rule (idempotent re-call),
                # skip silently.  If it belongs to another rule it is a real
                # collision and we keep the loud error.
                if existing_explicit[key] != rule.id:
                    raise HTTPException(409, f"Resource key '{key}' already exists for character")
                # else: already materialised by a previous call — skip.
        for res_def in explicit_defs:
            key = res_def["key"]
            if key in existing_explicit:
                # Already exists (owned by this rule) — nothing to insert.
                continue
            session.add(HomebrewResource(
                rule_id=rule.id,
                character_id=char.id,
                key=key,
                name=res_def["name"],
                current=res_def["max"],
                max=res_def["max"],
                restoration_type=res_def["restoration_type"],
            ))

    # ── 2. Inferred keys from change_resource / restore_resource actions ─────
    referenced_keys = _collect_referenced_resource_keys(dsl)
    # Only process keys not already handled as explicit ResourceDefs.
    inferred_keys = referenced_keys - explicit_keys

    if inferred_keys:
        existing_res2 = await session.execute(
            select(HomebrewResource.key).where(
                HomebrewResource.character_id == char.id,
                HomebrewResource.key.in_(list(inferred_keys)),
            )
        )
        already_exist: set[str] = set(existing_res2.scalars())
        # Keys referenced by change_resource/restore_resource but neither declared
        # in dsl["resources"] nor already owned as a resource are an authoring
        # mistake: reject with 422 instead of silently materializing an unusable
        # max=1/restoration_type=none placeholder (#14). The editor's Resources
        # section (D3 / F3-9) is where the author declares max/name/restoration.
        undeclared = sorted(inferred_keys - already_exist)
        if undeclared:
            raise HTTPException(
                422,
                "Resource key(s) referenced by change_resource/restore_resource "
                "but not declared: " + ", ".join(undeclared)
                + ". Declare them in the rule's resources (key, max, restoration_type).",
            )

    if explicit_keys or inferred_keys:
        await session.flush()


@router.post(
    "/characters/{char_id}/homebrew/templates/{template_id}/install",
    response_model=HomebrewRuleRead,
    status_code=201,
)
async def install_template(
    char_id: int, template_id: str,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HomebrewRule:
    char = await _get_owned_char(char_id, user_id, session)
    template = get_template(template_id)
    if template is None:
        raise HTTPException(404, "Template not found")
    now = _now()
    rule = HomebrewRule(
        character_id=char.id,
        name=template["name"],
        description=template["description"],
        enabled=True,
        dsl=template["dsl"],
        version=1,
        template_id=template_id,
        created_at=now,
        updated_at=now,
    )
    session.add(rule)
    await session.flush()
    await _materialize_property_defaults(session, char, rule)
    await _materialize_resources(session, char, rule)
    return rule


@router.delete(
    "/characters/{char_id}/homebrew/rules/{rule_id}",
    status_code=204,
)
async def delete_rule(
    char_id: int, rule_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    rule = await _get_owned_rule(char_id, rule_id, user_id, session)
    char = await _get_owned_char(char_id, user_id, session)
    # Custom conditions applied by this rule live in char.conditions (a JSON blob,
    # outside the relational graph), so deleting the rule cannot cascade them away —
    # they would linger as orphans pointing at a now-deleted rule. Remove only the
    # custom:* entries this rule owns; standard conditions (bool/int) and other
    # rules' custom conditions stay untouched. (HomebrewResource rows ARE removed
    # by the ORM cascade on HomebrewRule.resources.)
    conditions = dict(char.conditions or {})
    orphaned = [
        key for key, value in conditions.items()
        if isinstance(value, dict) and value.get("rule_id") == rule.id
    ]
    if orphaned:
        for key in orphaned:
            conditions.pop(key, None)
        char.conditions = conditions
        flag_modified(char, "conditions")
    await session.delete(rule)


# ─── Write-side rule endpoints ───────────────────────────────────────────────


class EnableBody(BaseModel):
    enabled: bool


@router.post(
    "/characters/{char_id}/homebrew/rules",
    response_model=HomebrewRuleRead,
    status_code=201,
)
async def create_rule(
    char_id: int,
    body: HomebrewRuleCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HomebrewRule:
    char = await _get_owned_char(char_id, user_id, session)
    now = _now()
    rule = HomebrewRule(
        character_id=char.id,
        name=body.name,
        description=body.description,
        enabled=body.enabled,
        dsl=body.dsl,
        version=1,
        template_id=body.template_id,
        created_at=now,
        updated_at=now,
    )
    session.add(rule)
    await session.flush()
    # _materialize_property_defaults already early-returns when the subject isn't an
    # item, so call it unconditionally — same as install_template (#43: removed the
    # redundant outer guard that duplicated the internal check).
    await _materialize_property_defaults(session, char, rule)
    await _materialize_resources(session, char, rule)
    return rule


@router.patch(
    "/characters/{char_id}/homebrew/rules/{rule_id}",
    response_model=HomebrewRuleRead,
)
async def update_rule(
    char_id: int, rule_id: int,
    body: HomebrewRuleUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HomebrewRule:
    rule = await _get_owned_rule(char_id, rule_id, user_id, session)
    char = await _get_owned_char(char_id, user_id, session)
    if body.name is not None:
        rule.name = body.name
    if body.description is not None:
        rule.description = body.description
    dsl_changed = body.dsl is not None
    if dsl_changed:
        rule.dsl = body.dsl
        rule.version += 1
    if body.enabled is not None:
        rule.enabled = body.enabled
    rule.updated_at = _now()
    # Sync resources whenever the DSL changes.  _materialize_resources is
    # idempotent: it only adds missing rows and never removes existing ones.
    # We intentionally do NOT delete resources that are no longer referenced
    # after a DSL edit, because the player may already have a non-zero current
    # value on that resource and wiping it would be a silent data-loss.
    if dsl_changed:
        await _materialize_resources(session, char, rule)
    return rule


@router.post(
    "/characters/{char_id}/homebrew/rules/{rule_id}/enable",
    response_model=HomebrewRuleRead,
)
async def toggle_enabled(
    char_id: int, rule_id: int,
    body: EnableBody,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HomebrewRule:
    rule = await _get_owned_rule(char_id, rule_id, user_id, session)
    rule.enabled = body.enabled
    rule.updated_at = _now()
    return rule


# ─── Resource endpoints ─────────────────────────────────────────────────────


@router.get(
    "/characters/{char_id}/homebrew/resources",
    response_model=list[HomebrewResourceRead],
)
async def list_resources(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[HomebrewResource]:
    char = await _get_owned_char(char_id, user_id, session)
    res = await session.execute(
        select(HomebrewResource)
        .where(HomebrewResource.character_id == char.id)
        .order_by(HomebrewResource.id.asc())
    )
    return list(res.scalars())


@router.patch(
    "/characters/{char_id}/homebrew/resources/{resource_id}",
    response_model=HomebrewResourceRead,
)
async def patch_resource(
    char_id: int, resource_id: int,
    body: HomebrewResourceUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HomebrewResourceRead:
    """Update a homebrew resource's current value with clamp + event dispatch.

    - Clamps `body.current` to [0, resource.max].
    - Fires `resource_changed` only when `before != after` (no-op PATCH does
      not emit any event — matches the spell_cast / item_equipped pattern).
    - Fires `resource_depleted` additionally on the transition
      `before > 0 and after == 0`.
    """
    char = await _get_owned_char(char_id, user_id, session)
    res = await session.execute(
        select(HomebrewResource).where(
            HomebrewResource.id == resource_id,
            HomebrewResource.character_id == char.id,
        )
    )
    resource = res.scalar_one_or_none()
    if resource is None:
        raise HTTPException(404, "Resource not found")

    before = resource.current
    after = max(0, min(resource.max, body.current))
    resource.current = after
    await session.flush()

    notifications: list[dict] = []
    if before != after:
        firing = await dispatch(
            session, char, "resource_changed",
            {
                "key": resource.key,
                "before": before,
                "after": after,
                "rule_id": resource.rule_id,
            },
        )
        notifications.extend(collect_homebrew_notifications(firing))
        if before > 0 and after == 0:
            firing2 = await dispatch(
                session, char, "resource_depleted",
                {"key": resource.key, "rule_id": resource.rule_id},
            )
            notifications.extend(collect_homebrew_notifications(firing2))

    result = HomebrewResourceRead.model_validate(resource)
    if notifications:
        result.homebrew_notifications = notifications
    return result


@router.delete(
    "/characters/{char_id}/homebrew/resources/{resource_id}",
    status_code=204,
)
async def delete_resource(
    char_id: int, resource_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a homebrew resource — manual orphan cleanup (#31).

    Resource materialization is additive: editing a rule's DSL never removes a
    resource row, so a key that is no longer referenced lingers and keeps holding
    the UNIQUE(character_id, key) slot, blocking another rule from using that key.
    This endpoint lets the owner remove such an orphan explicitly.

    Returns 404 if the resource doesn't exist or belongs to another character,
    403 if the URL's character is owned by another user.
    """
    char = await _get_owned_char(char_id, user_id, session)
    res = await session.execute(
        select(HomebrewResource).where(
            HomebrewResource.id == resource_id,
            HomebrewResource.character_id == char.id,
        )
    )
    resource = res.scalar_one_or_none()
    if resource is None:
        raise HTTPException(404, "Resource not found")
    await session.delete(resource)


# ─── Manual trigger endpoints ───────────────────────────────────────────────


@router.post(
    "/characters/{char_id}/homebrew/turn-start",
    status_code=200,
)
async def turn_start(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Fire the `turn_started` event for the character.

    Returns a flat list of notifications produced by all enabled rules whose
    triggers match `turn_started`. Empty list if no matching rules exist.
    """
    char = await _get_owned_char(char_id, user_id, session)
    firing = await dispatch(session, char, "turn_started", {})
    return {"notifications": collect_homebrew_notifications(firing)}


@router.post(
    "/characters/{char_id}/homebrew/manual-trigger/{rule_id}",
    status_code=200,
)
async def manual_trigger(
    char_id: int, rule_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Fire the `manual_trigger` event for the targeted rule only.

    The dispatch is scoped to `rule_id` (``only_rule_id``): tapping a rule's
    "activate manually" button fires THAT rule only, never every enabled rule
    that also listens on `manual_trigger` (#19 — e.g. a luck_points rule without
    a `$event.rule_id` self-filter must not be drained by an unrelated manual tap).
    `rule_id` is still passed in the payload, so existing rules that self-filter
    on ``$event.rule_id`` keep working unchanged.

    Returns 404 if the rule is missing, 403 if it belongs to another user,
    409 if the rule is disabled.
    """
    char = await _get_owned_char(char_id, user_id, session)
    rule = await _get_owned_rule(char_id, rule_id, user_id, session)
    if not rule.enabled:
        raise HTTPException(409, "Rule is disabled")
    firing = await dispatch(
        session, char, "manual_trigger", {"rule_id": rule_id}, only_rule_id=rule_id,
    )
    return {"notifications": collect_homebrew_notifications(firing)}
