"""Homebrew rules CRUD + templates + resources."""
from __future__ import annotations

import json as _json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


async def _materialize_resources(
    session: AsyncSession, char: Character, rule: HomebrewRule,
) -> None:
    """Create one HomebrewResource row per ResourceDef declared in the DSL.

    Pre-checks the UNIQUE(character_id, key) constraint by SELECTing the
    character's existing resource keys and raises HTTP 409 on collision —
    simpler and more diagnostic than relying on IntegrityError after the fact.

    Scope: only called from install_template and create_rule. Editing a rule's
    DSL via PATCH /homebrew/rules/{id} does NOT materialize / un-materialize
    resources (deferred to a v2 concern).
    """
    resources = rule.dsl.get("resources") or []
    if not resources:
        return
    new_keys = [r["key"] for r in resources]
    existing_res = await session.execute(
        select(HomebrewResource.key).where(
            HomebrewResource.character_id == char.id,
            HomebrewResource.key.in_(new_keys),
        )
    )
    existing = set(existing_res.scalars())
    for key in new_keys:
        if key in existing:
            raise HTTPException(409, f"Resource key '{key}' already exists for character")
    for res_def in resources:
        session.add(HomebrewResource(
            rule_id=rule.id,
            character_id=char.id,
            key=res_def["key"],
            name=res_def["name"],
            current=res_def["max"],
            max=res_def["max"],
            restoration_type=res_def["restoration_type"],
        ))
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
    if body.dsl.get("subject", {}).get("type") == "item":
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
    if body.name is not None:
        rule.name = body.name
    if body.description is not None:
        rule.description = body.description
    if body.dsl is not None:
        rule.dsl = body.dsl
        rule.version += 1
    if body.enabled is not None:
        rule.enabled = body.enabled
    rule.updated_at = _now()
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
