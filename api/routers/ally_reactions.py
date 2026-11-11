"""Reazioni degli alleati a un danno: richiesta del ricevente, popup e risposta del donatore."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.database import get_db
from api.schemas.ally_reactions import (
    AllyReactionOpen, AllyReactionOpened, AllyReactionRead, ReactionAnswerBody, ReactionAnswerResult, ReactionPrompt,
)
from api.services import ally_reactions as svc
from api.services.character_load import get_owned, get_owned_full_with_resources
from core.db.models import AllyReactionRequest

router = APIRouter(prefix="/characters", tags=["ally-reactions"])


async def _own_request(db: AsyncSession, char_id: int, request_id: int) -> AllyReactionRequest:
    req = await db.get(AllyReactionRequest, request_id)
    if req is None or req.receiver_id != char_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "request_not_found"})
    return req


@router.post("/{char_id}/ally-reactions", response_model=AllyReactionOpened)
async def open_reaction(char_id: int, body: AllyReactionOpen, user_id: Annotated[int, Depends(get_current_user)],
                        db: Annotated[AsyncSession, Depends(get_db, scope="function")]) -> dict:
    receiver = await get_owned(char_id, user_id, db)
    req = await svc.open_request(db, receiver, body.damage, body.damage_type)
    if req is None:
        return {"request_id": None, "waiting": [], "expires_in": 0}
    await db.commit()
    return {"request_id": req.id, "waiting": (await svc.describe(db, req))["waiting"], "expires_in": svc.OPEN_SECONDS}


@router.get("/{char_id}/ally-reactions/{request_id}", response_model=AllyReactionRead)
async def read_reaction(char_id: int, request_id: int, user_id: Annotated[int, Depends(get_current_user)],
                        db: Annotated[AsyncSession, Depends(get_db, scope="function")]) -> dict:
    await get_owned(char_id, user_id, db)
    req = await _own_request(db, char_id, request_id)
    await svc.close_if_due(db, req)
    await db.commit()
    return await svc.describe(db, req)


@router.post("/{char_id}/ally-reactions/{request_id}/close", response_model=AllyReactionRead)
async def close_reaction(char_id: int, request_id: int, user_id: Annotated[int, Depends(get_current_user)],
                         db: Annotated[AsyncSession, Depends(get_db, scope="function")]) -> dict:
    await get_owned(char_id, user_id, db)
    req = await _own_request(db, char_id, request_id)
    await svc.close_now(db, req)
    await db.commit()
    return await svc.describe(db, req)


@router.get("/{char_id}/reaction-prompts", response_model=list[ReactionPrompt])
async def reaction_prompts(char_id: int, user_id: Annotated[int, Depends(get_current_user)],
                           db: Annotated[AsyncSession, Depends(get_db, scope="function")]) -> list[dict]:
    donor = await get_owned_full_with_resources(char_id, user_id, db)
    svc.mark_seen(char_id)
    return await svc.prompts_for(db, donor)


@router.post("/{char_id}/reaction-prompts/{request_id}", response_model=ReactionAnswerResult)
async def answer_prompt(char_id: int, request_id: int, body: ReactionAnswerBody, user_id: Annotated[int, Depends(get_current_user)],
                        db: Annotated[AsyncSession, Depends(get_db, scope="function")]) -> dict:
    donor = await get_owned_full_with_resources(char_id, user_id, db)
    out = await svc.answer(db, donor, request_id, body.use)
    await db.commit()
    return out
