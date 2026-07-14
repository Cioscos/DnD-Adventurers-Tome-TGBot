"""Riscatto delle condivisioni (deep link ``shr_<token>``): anteprima + import.

Il token È la capability: chi lo possiede può vedere l'anteprima e importare
una copia in un PROPRIO personaggio. Nessun check di ownership sul contenuto
condiviso; l'auth Telegram resta obbligatoria.
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.database import get_db
from api.services import content_shares
from core.db.models import Character, ContentShare

router = APIRouter(prefix="/shares", tags=["share"])

_PREVIEW_MAX = 200


class SharePreview(BaseModel):
    kind: str
    title: str
    description: Optional[str] = None
    is_voice: bool = False
    item_type: Optional[str] = None
    quantity: Optional[int] = None
    sender_char_name: str


class ShareImportRequest(BaseModel):
    char_id: int


class ShareImportResult(BaseModel):
    ok: bool
    kind: str
    char_id: int
    title: str


def _truncate(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    return text if len(text) <= _PREVIEW_MAX else text[:_PREVIEW_MAX] + "…"


async def _get_valid_share(token: str, db: AsyncSession) -> ContentShare:
    share = (await db.execute(
        select(ContentShare).where(ContentShare.token == token)
    )).scalar_one_or_none()
    if share is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share not found")
    if content_shares.is_expired(share):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Share expired")
    return share


@router.get("/{token}", response_model=SharePreview)
async def get_share_preview(
    token: str,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SharePreview:
    share = await _get_valid_share(token, db)
    p = share.payload or {}
    if share.kind == "item":
        return SharePreview(
            kind="item",
            title=str(p.get("name") or "?"),
            description=_truncate(p.get("description")),
            item_type=p.get("item_type"),
            quantity=p.get("quantity"),
            sender_char_name=share.sender_char_name,
        )
    is_voice = share.voice_file_path is not None
    return SharePreview(
        kind="note",
        title=str(p.get("title") or "?"),
        description=None if is_voice else _truncate(str(p.get("body") or "")),
        is_voice=is_voice,
        sender_char_name=share.sender_char_name,
    )


@router.post("/{token}/import", response_model=ShareImportResult)
async def import_share(
    token: str,
    body: ShareImportRequest,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ShareImportResult:
    share = await _get_valid_share(token, db)
    char = (await db.execute(
        select(Character).where(Character.id == body.char_id)
    )).scalar_one_or_none()
    if char is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found")
    if char.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your character")

    if share.kind == "item":
        item = content_shares.import_item(share, char)
        db.add(item)
        await db.flush()
        return ShareImportResult(ok=True, kind="item", char_id=char.id, title=item.name)

    try:
        title = content_shares.import_note(share, char)
    except FileNotFoundError:
        # L'audio condiviso è sparito da disco: lo snapshot non è più riscattabile.
        # Commit esplicito: l'HTTPException farebbe altrimenti rollbackare la
        # delete nel teardown di get_db, lasciando lo snapshot orfano nel DB.
        await db.delete(share)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_410_GONE,
                            detail="Voice file no longer available")
    return ShareImportResult(ok=True, kind="note", char_id=char.id, title=title)
