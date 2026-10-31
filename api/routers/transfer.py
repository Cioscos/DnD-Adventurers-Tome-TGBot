"""Esportazione del personaggio: download JSON e invio come documento in chat."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_lang, get_current_user
from api.database import get_db
from api.routers.characters import _refresh_char_full
from api.schemas.character import CharacterFull
from api.schemas.transfer import CharacterExport
from api.services.character_response import build_character_response
from api.services.character_transfer import build_export, import_character, load_for_export
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


_MAX_IMPORT_BYTES = 1_000_000
_SUFFIX = {"it": {"import": " (importato)", "dup": " (copia)"}, "en": {"import": " (imported)", "dup": " (copy)"}}


async def _import_body(request: Request) -> bytes:
    limit = _MAX_IMPORT_BYTES + 4096  # margine per l'envelope multipart
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise HTTPException(status_code=413, detail="File too large")
    raw = b""
    async for chunk in request.stream():
        raw += chunk
        if len(raw) > limit:
            raise HTTPException(status_code=413, detail="File too large")
    if request.headers.get("content-type", "").startswith("multipart/form-data"):
        sent = False

        async def replay():  # il body e' gia' stato consumato: lo riproponiamo a form()
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": raw, "more_body": False}

        upload = (await Request(request.scope, replay).form()).get("file")
        if upload is None or isinstance(upload, str):
            raise HTTPException(status_code=422, detail="Missing 'file' field")
        raw = await upload.read()
    if len(raw) > _MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="File too large")
    return raw


async def _create_from(session: AsyncSession, user_id: int, data: CharacterExport, suffix: str) -> CharacterFull:
    char = await import_character(session, user_id, data, name_suffix=suffix)
    char = await _refresh_char_full(session, char.id, user_id)
    return await build_character_response(session, char)


@router.post("/import", response_model=CharacterFull, status_code=status.HTTP_201_CREATED)
async def import_character_endpoint(
    request: Request,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    raw = await _import_body(request)
    try:
        data = CharacterExport.model_validate_json(raw)
    except ValidationError as e:
        raise HTTPException(
            status_code=422, detail=e.errors(include_url=False, include_context=False, include_input=False)
        )
    return await _create_from(session, user_id, data, _SUFFIX.get(lang, _SUFFIX["it"])["import"])


@router.post("/{char_id}/duplicate", response_model=CharacterFull, status_code=status.HTTP_201_CREATED)
async def duplicate_character(
    char_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    lang: Annotated[str, Depends(get_current_lang)],
) -> CharacterFull:
    char = await _get_owned(char_id, user_id, session)
    data = await build_export(session, char)
    return await _create_from(session, user_id, data, _SUFFIX.get(lang, _SUFFIX["it"])["dup"])
