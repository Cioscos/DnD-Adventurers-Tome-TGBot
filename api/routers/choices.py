"""Level-up choices: resolve an ASI / feat, remove a feat."""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_lang, get_current_user
from api.database import get_db
from api.routers.classes import _get_owned_full, _refresh_char_full
from api.schemas.character import CharacterFull
from api.services.character_response import build_character_response
from api.services.choices import resolve_asi, resolve_feat
from core.db.models import Ability, HomebrewRule

router = APIRouter(prefix="/characters", tags=["choices"])


class AsiResolve(BaseModel):
    kind: Literal["asi"]
    increases: dict[str, Annotated[int, Field(ge=1, le=2)]]


class FeatResolve(BaseModel):
    kind: Literal["feat"]
    feat_key: str = Field(max_length=50)
    ability: Optional[str] = Field(None, max_length=20)
    custom_name: Optional[str] = Field(None, max_length=200)
    custom_text: Optional[str] = Field(None, max_length=2000)


@router.post("/{char_id}/choices/{choice_id}/resolve", response_model=CharacterFull)
async def resolve_choice(
    char_id: int,
    choice_id: str,
    body: Annotated[Union[AsiResolve, FeatResolve], Field(discriminator="kind")],
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)
    choices = list(char.pending_choices or [])
    if not any(c["id"] == choice_id for c in choices):
        raise HTTPException(404, "Choice not found")
    if isinstance(body, AsiResolve):
        resolve_asi(session, char, body.increases)
    else:
        resolve_feat(session, char, body.feat_key, body.ability,
                     body.custom_name, body.custom_text, lang)
    char.pending_choices = [c for c in choices if c["id"] != choice_id]
    char = await _refresh_char_full(char_id, user_id, session)
    return await build_character_response(session, char)


@router.delete("/{char_id}/feats/{rule_id}", response_model=CharacterFull)
async def delete_feat(
    char_id: int,
    rule_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CharacterFull:
    char = await _get_owned_full(char_id, user_id, session)
    rule = (await session.execute(select(HomebrewRule).where(
        HomebrewRule.id == rule_id, HomebrewRule.character_id == char_id,
        HomebrewRule.template_id.like("feat:%")))).scalar_one_or_none()
    if rule is None:
        raise HTTPException(404, "Feat not found")
    key = rule.template_id.split(":", 1)[1]
    await session.delete(rule)
    await session.execute(delete(Ability).where(
        Ability.character_id == char_id, Ability.feature_key == f"feat.{key}"))
    char = await _refresh_char_full(char_id, user_id, session)
    return await build_character_response(session, char)
