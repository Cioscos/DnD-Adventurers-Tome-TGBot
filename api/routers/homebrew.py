"""Homebrew rules CRUD + templates + resources."""
from __future__ import annotations

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
from core.db.models import Character, HomebrewRule

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
