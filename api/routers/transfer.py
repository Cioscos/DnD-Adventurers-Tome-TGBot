"""Esportazione del personaggio: download JSON e invio come documento in chat."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.database import get_db
from api.schemas.transfer import CharacterExport
from api.services.character_transfer import build_export, load_for_export
from api.services.telegram_notify import bot_token_configured, send_telegram_document

router = APIRouter(prefix="/characters", tags=["transfer"])


async def _get_owned(char_id: int, user_id: int, session: AsyncSession):
    char = await load_for_export(session, char_id)
    if char is None:
        raise HTTPException(status_code=404, detail="Character not found")
    if char.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your character")
    return char


def _filename(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-") or "personaggio"
    return f"{slug}-{datetime.now(timezone.utc):%Y%m%d}.json"


@router.get("/{char_id}/export", response_model=CharacterExport)
async def export_character(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    char = await _get_owned(char_id, user_id, session)
    data = await build_export(session, char)
    return Response(
        content=data.model_dump_json(),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{_filename(char.name)}"'},
    )


@router.post("/{char_id}/export/send")
async def send_export(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    char = await _get_owned(char_id, user_id, session)
    if not bot_token_configured():
        raise HTTPException(status_code=503, detail="Bot not configured")
    data = await build_export(session, char)
    ok = await send_telegram_document(
        user_id, _filename(char.name), data.model_dump_json().encode("utf-8"), caption=char.name
    )
    if not ok:
        raise HTTPException(status_code=502, detail="Telegram delivery failed")
    return {"ok": True}
