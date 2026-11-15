"""Specie 2024 sulla scheda: anteprima dei cambiamenti e applicazione (solo personaggi 2024)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_lang, get_current_user
from api.database import get_db
from api.schemas.character import CharacterFull, SpeciesChoiceIn
from api.services.character_load import get_owned_full, refresh_char_full
from api.services.character_response import build_character_response
from api.services.species_apply import apply_species, plan_species

router = APIRouter(prefix="/characters", tags=["species"])


@router.post("/{char_id}/species/preview")
async def preview_species(
    char_id: int, body: SpeciesChoiceIn,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> dict[str, list[str]]:
    char = await get_owned_full(char_id, user_id, session)
    return {"changes": plan_species(char, body.key, body.options).changes}


@router.put("/{char_id}/species", response_model=CharacterFull)
async def put_species(
    char_id: int, body: SpeciesChoiceIn,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db, scope="function")],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    char = await get_owned_full(char_id, user_id, session)
    await apply_species(session, char, body.key, body.options, lang)
    char = await refresh_char_full(session, char_id, user_id)
    return await build_character_response(session, char)
