"""Homebrew rules CRUD + templates + resources."""
from __future__ import annotations

import json as _json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.database import get_db
from api.schemas.homebrew import (
    HomebrewRuleRead,
    TemplateDetailRead,
    TemplateRead,
)
from api.services.homebrew.templates import TEMPLATES, get_template
from core.db.models import Character, HomebrewRule, Item

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
