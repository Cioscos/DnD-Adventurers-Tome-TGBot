"""Campaign lore: GM-authored entries (drafts until revealed) with optional image/audio."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import DEV_USER_ID, get_current_user, verify_init_data
from api.database import get_db
from api.services.game_sessions import active_session_id, touch
from api.schemas.campaign import LoreRead
from api.services import campaigns as svc
from api.services.campaigns import unlink_file
from core.db.models import Campaign, CampaignLore, CampaignMember, GameSession, SessionMessage, SessionRole
from api.services.campaigns import campaign_access

router = APIRouter(prefix="/campaigns/{campaign_id}/lore", tags=["lore"])

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_AUDIO_EXTS = {".webm", ".ogg", ".mp3", ".wav", ".m4a", ".aac"}
_MAX_IMAGE = 10 * 1024 * 1024
_MAX_AUDIO = 5 * 1024 * 1024
_MEDIA = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
    ".gif": "image/gif", ".webm": "audio/webm", ".ogg": "audio/ogg", ".mp3": "audio/mpeg",
    ".wav": "audio/wav", ".m4a": "audio/mp4", ".aac": "audio/aac",
}


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")  # naive UTC, like sessions._now()


def _read(lore: CampaignLore) -> LoreRead:
    return LoreRead(
        id=lore.id, title=lore.title, body=lore.body, tags=list(lore.tags or []),
        has_image=bool(lore.image_path), has_audio=bool(lore.audio_path),
        revealed=lore.revealed_at is not None, revealed_at=lore.revealed_at,
        created_at=lore.created_at, updated_at=lore.updated_at,
    )


async def _lore(db: AsyncSession, campaign_id: int, lore_id: int) -> CampaignLore:
    lore = await db.get(CampaignLore, lore_id)
    if lore is None or lore.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail="lore_not_found")
    return lore


async def _gm_lore(db: AsyncSession, campaign_id: int, lore_id: int, user_id: int) -> CampaignLore:
    if not await campaign_access(db, campaign_id, user_id):
        raise HTTPException(status_code=403, detail="gm_only")
    return await _lore(db, campaign_id, lore_id)


def _title(raw: str) -> str:
    title = raw.strip()
    if not title:
        raise HTTPException(status_code=422, detail="invalid_title")
    return title


def _tags(raw: Optional[str]) -> list[str]:
    try:
        tags = json.loads(raw or "[]")
    except ValueError:
        tags = None
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise HTTPException(status_code=422, detail="invalid_tags")
    return tags


async def _save(campaign_id: int, file: UploadFile, exts: set[str], max_size: int) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in exts:
        raise HTTPException(status_code=400, detail=f"File format not allowed. Allowed: {', '.join(sorted(exts))}")
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail=f"File too large (max {max_size // (1024 * 1024)} MB)")
    folder = svc.LORE_DIR / str(campaign_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex}{suffix}"
    path.write_bytes(content)
    return str(path)


async def _save_both(
    campaign_id: int, image: Optional[UploadFile], audio: Optional[UploadFile]
) -> tuple[Optional[str], Optional[str]]:
    """Validate and store the optional uploads; no file is left behind if one is rejected."""
    new_image = new_audio = None
    try:
        if image is not None:
            new_image = await _save(campaign_id, image, _IMAGE_EXTS, _MAX_IMAGE)
        if audio is not None:
            new_audio = await _save(campaign_id, audio, _AUDIO_EXTS, _MAX_AUDIO)
    except HTTPException:
        unlink_file(new_image)
        raise
    return new_image, new_audio


@router.get("", response_model=list[LoreRead])
async def list_lore(
    campaign_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> list[LoreRead]:
    is_gm = await campaign_access(db, campaign_id, user_id)
    rows = (await db.execute(select(CampaignLore).where(CampaignLore.campaign_id == campaign_id))).scalars().all()
    if not is_gm:
        rows = [r for r in rows if r.revealed_at]
    rows.sort(key=lambda r: (r.revealed_at or r.created_at, r.id), reverse=True)
    return [_read(r) for r in rows]


@router.post("", response_model=LoreRead, status_code=201)
async def create_lore(
    campaign_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    title: str = Form(..., min_length=1, max_length=120),
    body: str = Form(""),
    tags: str = Form("[]"),
    image: UploadFile | None = File(None),
    audio: UploadFile | None = File(None),
) -> LoreRead:
    if not await campaign_access(db, campaign_id, user_id):
        raise HTTPException(status_code=403, detail="gm_only")
    tag_list, clean_title = _tags(tags), _title(title)  # validate before writing any file
    new_image, new_audio = await _save_both(campaign_id, image, audio)
    now = _now()
    lore = CampaignLore(
        campaign_id=campaign_id, title=clean_title, body=body, tags=tag_list,
        image_path=new_image, audio_path=new_audio, created_at=now, updated_at=now,
    )
    db.add(lore)
    await db.flush()
    return _read(lore)


@router.patch("/{lore_id}", response_model=LoreRead)
async def update_lore(
    campaign_id: int,
    lore_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    title: str | None = Form(None, min_length=1, max_length=120),
    body: str | None = Form(None),
    tags: str | None = Form(None),
    image: UploadFile | None = File(None),
    audio: UploadFile | None = File(None),
    remove_image: bool = Form(False),
    remove_audio: bool = Form(False),
) -> LoreRead:
    lore = await _gm_lore(db, campaign_id, lore_id, user_id)
    tag_list = _tags(tags) if tags is not None else None
    clean_title = _title(title) if title is not None else None  # validate before writing any file
    new_image, new_audio = await _save_both(campaign_id, image, audio)
    stale: list[Optional[str]] = []
    if new_image or remove_image:
        stale.append(lore.image_path)
        lore.image_path = new_image
    if new_audio or remove_audio:
        stale.append(lore.audio_path)
        lore.audio_path = new_audio
    if clean_title is not None:
        lore.title = clean_title
    if body is not None:
        lore.body = body
    if tag_list is not None:
        lore.tags = tag_list
    lore.updated_at = _now()
    await db.flush()
    for p in stale:
        unlink_file(p)
    return _read(lore)


@router.delete("/{lore_id}", status_code=204)
async def delete_lore(
    campaign_id: int,
    lore_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> Response:
    lore = await _gm_lore(db, campaign_id, lore_id, user_id)
    paths = [lore.image_path, lore.audio_path]
    await db.delete(lore)
    await db.flush()
    for p in paths:
        unlink_file(p)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{lore_id}/reveal", response_model=LoreRead)
async def reveal_lore(
    campaign_id: int,
    lore_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> LoreRead:
    lore = await _gm_lore(db, campaign_id, lore_id, user_id)
    if lore.revealed_at is None:
        lore.revealed_at = lore.updated_at = _now()
        session_id = await active_session_id(db, campaign_id)
        if session_id is not None:
            touch(await db.get(GameSession, session_id))
            db.add(SessionMessage(
                session_id=session_id, user_id=user_id, role=SessionRole.GAME_MASTER,
                body=f"Il master ha rivelato: {lore.title}", sent_at=lore.revealed_at,
                sender_display_name="__GM__",
                trade_payload=json.dumps({"kind": "lore_reveal", "lore_id": lore.id, "title": lore.title}),
            ))
        await db.flush()
    return _read(lore)


@router.post("/{lore_id}/hide", response_model=LoreRead)
async def hide_lore(
    campaign_id: int,
    lore_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> LoreRead:
    lore = await _gm_lore(db, campaign_id, lore_id, user_id)
    if lore.revealed_at is not None:
        lore.revealed_at = None
        lore.updated_at = _now()
        await db.flush()
    return _read(lore)


async def _serve(campaign_id: int, lore_id: int, db: AsyncSession, header: str, query: str, attr: str):
    # <img>/<audio> cannot set headers: accept init_data as query param fallback.
    if DEV_USER_ID is not None:
        user_id = DEV_USER_ID
    else:
        raw = header or query
        if not raw:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth")
        user_id = verify_init_data(raw)
    is_gm = await campaign_access(db, campaign_id, user_id)
    lore = await _lore(db, campaign_id, lore_id)
    stored = getattr(lore, attr)
    if (not is_gm and lore.revealed_at is None) or not stored or not Path(stored).exists():
        raise HTTPException(status_code=404, detail="file_not_found")
    path = Path(stored)
    if not path.resolve().is_relative_to(svc.LORE_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid path")
    return FileResponse(path, media_type=_MEDIA.get(path.suffix.lower(), "application/octet-stream"))


@router.get("/{lore_id}/image", response_model=None)
async def get_lore_image(
    campaign_id: int, lore_id: int, db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    x_telegram_init_data: str = Header("", alias="X-Telegram-Init-Data"),
    init_data: str = Query(""),
):
    return await _serve(campaign_id, lore_id, db, x_telegram_init_data, init_data, "image_path")


@router.get("/{lore_id}/audio", response_model=None)
async def get_lore_audio(
    campaign_id: int, lore_id: int, db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    x_telegram_init_data: str = Header("", alias="X-Telegram-Init-Data"),
    init_data: str = Query(""),
):
    return await _serve(campaign_id, lore_id, db, x_telegram_init_data, init_data, "audio_path")
