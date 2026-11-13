"""Level-up choices: resolve an ASI / feat, remove a feat."""
from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_lang, get_current_user
from api.database import get_db
from api.routers._helpers import effective_con_mod
from api.services.character_load import get_owned_full, refresh_char_full
from api.routers.stats import apply_ability_change
from api.schemas.character import CharacterFull
from api.services.character_response import build_character_response
from api.services.class_features import sync_cataloged_features
from api.services.choices import (
    complete_feat, take_feat,
    class_options_state, mark_resolved, remove_feat, replace_class_option, resolve_asi, resolve_class_option,
    resolve_feat)
from api.schemas.spell import SpellCreate
from core.db.models import HomebrewRule

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


class EpicBoonResolve(BaseModel):
    kind: Literal["epic_boon"]
    feat_key: str = Field(max_length=50)
    ability: Optional[str] = Field(None, max_length=20)


class ClassOptionResolve(BaseModel):
    kind: Literal["class_option"]
    options: list[Annotated[str, Field(max_length=50)]] = Field(max_length=20)


# kind della scelta in sospeso -> kind di risposta ammessi
_ALLOWED = {"asi": ("asi", "feat"), "epic_boon": ("epic_boon",), "class_option": ("class_option",)}


@router.post("/{char_id}/choices/{choice_id}/resolve", response_model=CharacterFull)
async def resolve_choice(
    char_id: int,
    choice_id: str,
    body: Annotated[Union[AsiResolve, FeatResolve, EpicBoonResolve, ClassOptionResolve], Field(discriminator="kind")],
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    char = await get_owned_full(char_id, user_id, session)
    choices = list(char.pending_choices or [])
    choice = next((c for c in choices if c["id"] == choice_id), None)
    if choice is None:
        raise HTTPException(404, "Choice not found")
    if body.kind not in _ALLOWED.get(choice.get("kind", "asi"), ()):
        raise HTTPException(422, "choice_kind_mismatch")
    old_con_mod = effective_con_mod(char)
    if isinstance(body, AsiResolve):
        resolve_asi(session, char, body.increases)
        changed = list(body.increases)
    elif isinstance(body, ClassOptionResolve):
        resolve_class_option(session, char, choice, body.options)
        changed = []
        await sync_cataloged_features(session, char, lang)
    elif isinstance(body, EpicBoonResolve):
        resolve_feat(session, char, body.feat_key, body.ability, None, None, lang, boon=True)
        changed = [body.ability] if body.ability else []
    else:
        resolve_feat(session, char, body.feat_key, body.ability,
                     body.custom_name, body.custom_text, lang)
        changed = [body.ability] if body.ability else []
    for ability in changed:  # same side effects as PATCH /ability_scores (CON HP, STR carry, AC)
        await apply_ability_change(session, char, ability, old_con_mod)
    if changed or isinstance(body, (FeatResolve, EpicBoonResolve)):  # i talenti agiscono dal motore: usi e testi al sync
        await sync_cataloged_features(session, char, lang)
    if not isinstance(body, ClassOptionResolve):  # le scelte di opzioni le riconcilia il sync, anche il resto che aspetta
        mark_resolved(char, choice)
        char.pending_choices = [c for c in choices if c["id"] != choice_id]
    char = await refresh_char_full(session, char_id, user_id)
    return await build_character_response(session, char)


async def _remove(char_id: int, user_id: int, session: AsyncSession, ability_id: int | None,
                  rule_id: int | None = None) -> CharacterFull:
    char = await get_owned_full(char_id, user_id, session)
    if rule_id is not None:
        rule = (await session.execute(select(HomebrewRule).where(
            HomebrewRule.id == rule_id, HomebrewRule.character_id == char_id,
            HomebrewRule.template_id.like("feat:%")))).scalar_one_or_none()
        key = f"feat.{rule.template_id.split(':', 1)[1]}" if rule else None
        ab = next((a for a in char.abilities if a.feature_key == key), None) if key else None
    else:
        ab = next((a for a in char.abilities
                   if a.id == ability_id and (a.feature_key or "").startswith("feat.")), None)
    if ab is None:
        raise HTTPException(404, "Feat not found")
    await remove_feat(session, char, ab)
    char = await refresh_char_full(session, char_id, user_id)
    return await build_character_response(session, char)


class FeatTake(BaseModel):
    feat_key: str = Field(max_length=50)
    ability: Optional[str] = Field(default=None, max_length=20)


class FeatOptions(BaseModel):
    options: dict[str, Union[str, list[str]]] = Field(default_factory=dict)
    spells: list[SpellCreate] = Field(default_factory=list, max_length=3)


@router.post("/{char_id}/feats", response_model=CharacterFull, status_code=201)
async def add_feat(
    char_id: int, body: FeatTake,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    """«Aggiungi talento»: fuori dalle scelte di livello (talento d'Origine, dono del GM, privilegi che ne concedono)."""
    char = await get_owned_full(char_id, user_id, session)
    old_con_mod = effective_con_mod(char)
    take_feat(session, char, body.feat_key, body.ability, lang, "manual")
    if body.ability:
        await apply_ability_change(session, char, body.ability, old_con_mod)
    await sync_cataloged_features(session, char, lang)
    char = await refresh_char_full(session, char_id, user_id)
    return await build_character_response(session, char)


@router.put("/{char_id}/feats/{ability_id}/options", response_model=CharacterFull)
async def set_feat_options(
    char_id: int, ability_id: int, body: FeatOptions,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    """«Completa talento»: le scelte proprie del talento, una volta sola."""
    char = await get_owned_full(char_id, user_id, session)
    ab = next((a for a in char.abilities if a.id == ability_id and (a.feature_key or "").startswith("feat.")), None)
    if ab is None:
        raise HTTPException(404, "Feat not found")
    complete_feat(session, char, ab, body.options, body.spells)
    await sync_cataloged_features(session, char, lang)
    char = await refresh_char_full(session, char_id, user_id)
    return await build_character_response(session, char)


@router.delete("/{char_id}/feats/by-rule/{rule_id}", response_model=CharacterFull)
async def delete_feat_by_rule(
    char_id: int, rule_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CharacterFull:
    return await _remove(char_id, user_id, session, None, rule_id)


@router.delete("/{char_id}/feats/{ability_id}", response_model=CharacterFull)
async def delete_feat(
    char_id: int, ability_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> CharacterFull:
    return await _remove(char_id, user_id, session, ability_id)


class OptionReplace(BaseModel):
    group: str = Field(max_length=50)
    old_key: str = Field(max_length=50)
    new_key: str = Field(max_length=50)


def _class_of(char, class_id: int):
    cls = next((c for c in char.classes if c.id == class_id), None)
    if cls is None:
        raise HTTPException(404, "Class not found")
    return cls


@router.get("/{char_id}/classes/{class_id}/options/{group}")
async def class_options(
    char_id: int, class_id: int, group: str,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> dict:
    char = await get_owned_full(char_id, user_id, session)
    return class_options_state(char, _class_of(char, class_id), group)


@router.post("/{char_id}/classes/{class_id}/options/replace", response_model=CharacterFull)
async def replace_option(
    char_id: int, class_id: int, body: OptionReplace,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    char = await get_owned_full(char_id, user_id, session)
    replace_class_option(session, char, _class_of(char, class_id), body.group, body.old_key, body.new_key)
    await sync_cataloged_features(session, char, lang)
    char = await refresh_char_full(session, char_id, user_id)
    return await build_character_response(session, char)
