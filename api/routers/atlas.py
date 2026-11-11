"""Campaign atlas: GM-uploaded maps (hidden until revealed) with player/GM markers on top."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import DEV_USER_ID, get_current_user, verify_init_data
from api.database import get_db
from api.services.game_sessions import active_session_id, touch
from api.schemas.atlas import (
    AtlasMapDeleted, AtlasMapRead, AtlasMapRename, MarkerCreate, MarkerRead, MarkerTypeCreate,
    MarkerTypeRead, MarkerUpdate, MarkerVisibility,
)
from api.services import campaigns as svc
from api.services.atlas import BUILTIN_TYPES, map_visible, marker_clause, marker_visible
from api.services.campaigns import unlink_file
from core.db.models import (
    Campaign, CampaignMap, CampaignMapMarker, CampaignMarkerType, CampaignMember, Character, GameSession,
    SessionMessage, SessionRole,
)
from api.services.campaigns import campaign_access

router = APIRouter(prefix="/campaigns/{campaign_id}/atlas", tags=["atlas"])

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
_MAX_IMAGE = 10 * 1024 * 1024
_MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")  # naive UTC, like lore._now()


async def _read(db: AsyncSession, m: CampaignMap, user_id: int, is_gm: bool) -> AtlasMapRead:
    # GM: total (a bare count, no content, matches deleted_markers); players: only what they can see.
    q = select(func.count()).select_from(CampaignMapMarker).where(CampaignMapMarker.map_id == m.id)
    if not is_gm:
        q = q.where(marker_clause(user_id))
    count = (await db.execute(q)).scalar_one()
    return AtlasMapRead(
        id=m.id, name=m.name, revealed=m.revealed_at is not None, revealed_at=m.revealed_at,
        updated_at=m.updated_at, marker_count=count,
    )


async def _feed_reveal(
    db: AsyncSession, campaign_id: int, user_id: int, map_id: int, marker_id: int | None, title: str, now: str,
) -> None:
    """GM reveal row in the campaign's active session feed (no-op without one)."""
    session_id = await active_session_id(db, campaign_id)
    if session_id is None:
        return
    touch(await db.get(GameSession, session_id))
    db.add(SessionMessage(
        session_id=session_id, user_id=user_id, role=SessionRole.GAME_MASTER,
        body=f"Il master ha rivelato: {title}", sent_at=now, sender_display_name="__GM__",
        trade_payload=json.dumps(
            {"kind": "atlas_reveal", "map_id": map_id, "marker_id": marker_id, "title": title}),
    ))


async def _map(db: AsyncSession, campaign_id: int, map_id: int, is_gm: bool) -> CampaignMap:
    m = await db.get(CampaignMap, map_id)
    if m is None or m.campaign_id != campaign_id or not map_visible(m, is_gm):
        raise HTTPException(status_code=404, detail="map_not_found")
    return m


async def _gm_map(db: AsyncSession, campaign_id: int, map_id: int, user_id: int) -> CampaignMap:
    if not await campaign_access(db, campaign_id, user_id):
        raise HTTPException(status_code=403, detail="gm_only")
    return await _map(db, campaign_id, map_id, True)


async def _save(campaign_id: int, file: UploadFile) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _IMAGE_EXTS:
        raise HTTPException(status_code=400, detail=f"File format not allowed. Allowed: {', '.join(sorted(_IMAGE_EXTS))}")
    content = await file.read()
    if len(content) > _MAX_IMAGE:
        raise HTTPException(status_code=400, detail=f"File too large (max {_MAX_IMAGE // (1024 * 1024)} MB)")
    folder = svc.ATLAS_DIR / str(campaign_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex}{suffix}"
    path.write_bytes(content)
    return str(path)


@router.get("/maps", response_model=list[AtlasMapRead])
async def list_maps(
    campaign_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> list[AtlasMapRead]:
    is_gm = await campaign_access(db, campaign_id, user_id)
    rows = (await db.execute(
        select(CampaignMap).where(CampaignMap.campaign_id == campaign_id)
        .order_by(CampaignMap.created_at, CampaignMap.id)
    )).scalars().all()
    return [await _read(db, m, user_id, is_gm) for m in rows if map_visible(m, is_gm)]


@router.post("/maps", response_model=AtlasMapRead, status_code=201)
async def create_map(
    campaign_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    name: str = Form(..., min_length=1, max_length=80),
    file: UploadFile = File(...),
) -> AtlasMapRead:
    if not await campaign_access(db, campaign_id, user_id):
        raise HTTPException(status_code=403, detail="gm_only")
    clean = name.strip()
    if not clean:  # validated before any file is written
        raise HTTPException(status_code=422, detail="invalid_name")
    now = _now()
    m = CampaignMap(campaign_id=campaign_id, name=clean, image_path=await _save(campaign_id, file),
                    created_at=now, updated_at=now)
    db.add(m)
    await db.flush()
    return await _read(db, m, user_id, True)


@router.patch("/maps/{map_id}", response_model=AtlasMapRead)
async def rename_map(
    campaign_id: int, map_id: int, body: AtlasMapRename,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> AtlasMapRead:
    m = await _gm_map(db, campaign_id, map_id, user_id)
    m.name, m.updated_at = body.name.strip(), _now()
    await db.flush()
    return await _read(db, m, user_id, True)


@router.put("/maps/{map_id}/image", response_model=AtlasMapRead)
async def replace_image(
    campaign_id: int, map_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    file: UploadFile = File(...),
) -> AtlasMapRead:
    m = await _gm_map(db, campaign_id, map_id, user_id)
    old, m.image_path = m.image_path, await _save(campaign_id, file)
    m.updated_at = _now()
    await db.flush()
    unlink_file(old)
    return await _read(db, m, user_id, True)


@router.post("/maps/{map_id}/reveal", response_model=AtlasMapRead)
async def reveal_map(
    campaign_id: int, map_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> AtlasMapRead:
    m = await _gm_map(db, campaign_id, map_id, user_id)
    if m.revealed_at is None:
        m.revealed_at = m.updated_at = _now()
        await _feed_reveal(db, campaign_id, user_id, m.id, None, m.name, m.revealed_at)
        await db.flush()
    return await _read(db, m, user_id, True)


@router.post("/maps/{map_id}/hide", response_model=AtlasMapRead)
async def hide_map(
    campaign_id: int, map_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> AtlasMapRead:
    m = await _gm_map(db, campaign_id, map_id, user_id)
    if m.revealed_at is not None:
        m.revealed_at, m.updated_at = None, _now()
        await db.flush()
    return await _read(db, m, user_id, True)


@router.delete("/maps/{map_id}", response_model=AtlasMapDeleted)
async def delete_map(
    campaign_id: int, map_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> AtlasMapDeleted:
    m = await _gm_map(db, campaign_id, map_id, user_id)
    path = m.image_path
    # Explicit delete: SQLite FK cascades are not guaranteed on, and the count is in the response.
    await db.execute(update(CampaignMapMarker).where(CampaignMapMarker.link_map_id == map_id).values(link_map_id=None))
    removed = (await db.execute(delete(CampaignMapMarker).where(CampaignMapMarker.map_id == map_id))).rowcount
    await db.delete(m)
    await db.flush()
    unlink_file(path)
    return AtlasMapDeleted(deleted_markers=removed)


@router.get("/maps/{map_id}/image", response_model=None)
async def get_map_image(
    campaign_id: int, map_id: int, db: Annotated[AsyncSession, Depends(get_db, scope="function")],
    x_telegram_init_data: str = Header("", alias="X-Telegram-Init-Data"),
    init_data: str = Query(""),
):
    # <img> cannot set headers: accept init_data as query param fallback.
    if DEV_USER_ID is not None:
        user_id = DEV_USER_ID
    else:
        raw = x_telegram_init_data or init_data
        if not raw:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth")
        user_id = verify_init_data(raw)
    is_gm = await campaign_access(db, campaign_id, user_id)
    try:
        m = await _map(db, campaign_id, map_id, is_gm)
    except HTTPException:
        raise HTTPException(status_code=404, detail="file_not_found")
    path = Path(m.image_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="file_not_found")
    if not path.resolve().is_relative_to(svc.ATLAS_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid path")
    return FileResponse(path, media_type=_MEDIA.get(path.suffix.lower(), "application/octet-stream"))


# -- markers -----------------------------------------------------------------

async def _types(db: AsyncSession, campaign_id: int) -> dict[int, CampaignMarkerType]:
    rows = (await db.execute(
        select(CampaignMarkerType).where(CampaignMarkerType.campaign_id == campaign_id)
        .order_by(CampaignMarkerType.id))).scalars().all()
    return {t.id: t for t in rows}


def _type_read(key: str | None, custom: CampaignMarkerType | None, user_id: int, is_gm: bool) -> MarkerTypeRead:
    if custom is not None:
        return MarkerTypeRead(id=custom.id, key=None, name=custom.name, icon=custom.icon, color=custom.color,
                              builtin=False, can_delete=is_gm or custom.created_by == user_id)
    key = key if key in BUILTIN_TYPES else "poi"
    icon, color = BUILTIN_TYPES[key]
    return MarkerTypeRead(id=None, key=key, name=key, icon=icon, color=color, builtin=True, can_delete=False)


async def _marker_reads(
    db: AsyncSession, campaign_id: int, mks: list[CampaignMapMarker], user_id: int, is_gm: bool,
) -> list[MarkerRead]:
    types = await _types(db, campaign_id)
    gm_id = (await db.get(Campaign, campaign_id)).gm_user_id
    visible_maps = {
        m.id for m in (await db.execute(select(CampaignMap).where(CampaignMap.campaign_id == campaign_id))).scalars()
        if map_visible(m, is_gm)}
    out = []
    for mk in mks:
        mine = mk.author_user_id == user_id
        out.append(MarkerRead(
            id=mk.id, map_id=mk.map_id, name=mk.name, description=mk.description, x=mk.x, y=mk.y,
            visibility=mk.visibility, type=_type_read(mk.type_key, types.get(mk.custom_type_id), user_id, is_gm),
            author_role="gm" if mk.author_user_id == gm_id else "player", author_name=mk.author_name, mine=mine,
            link_map_id=mk.link_map_id if mk.link_map_id in visible_maps else None,
            can_edit=mine, can_delete=mine or (is_gm and mk.visibility == "public"), updated_at=mk.updated_at,
        ))
    return out


async def _one_read(db: AsyncSession, mk: CampaignMapMarker, user_id: int, is_gm: bool) -> MarkerRead:
    return (await _marker_reads(db, mk.campaign_id, [mk], user_id, is_gm))[0]


async def _marker(db: AsyncSession, campaign_id: int, marker_id: int, user_id: int, is_gm: bool) -> CampaignMapMarker:
    mk = await db.get(CampaignMapMarker, marker_id)
    if mk is None or mk.campaign_id != campaign_id or not marker_visible(mk, user_id):
        raise HTTPException(status_code=404, detail="marker_not_found")
    try:
        await _map(db, campaign_id, mk.map_id, is_gm)
    except HTTPException:
        # Player on a hidden map: same answer as a missing id, so the error can't probe existence.
        raise HTTPException(status_code=404, detail="marker_not_found") from None
    return mk


def _owned(mk: CampaignMapMarker, user_id: int) -> None:
    if mk.author_user_id != user_id:
        raise HTTPException(status_code=403, detail="not_owner")


async def _check_type(db: AsyncSession, campaign_id: int, key: str | None, custom_id: int | None) -> None:
    if key is not None:
        ok = key in BUILTIN_TYPES
    else:
        t = await db.get(CampaignMarkerType, custom_id)
        ok = t is not None and t.campaign_id == campaign_id
    if not ok:
        raise HTTPException(status_code=422, detail="invalid_type")


async def _check_link(db: AsyncSession, campaign_id: int, map_id: int, link: int | None, is_gm: bool) -> None:
    if link is None:
        return
    if not is_gm:
        raise HTTPException(status_code=403, detail="link_gm_only")
    target = await db.get(CampaignMap, link)
    if link == map_id or target is None or target.campaign_id != campaign_id:
        raise HTTPException(status_code=422, detail="invalid_link")


async def _author(db: AsyncSession, campaign_id: int, user_id: int) -> tuple[int | None, str | None]:
    member = (await db.execute(
        select(CampaignMember).where(CampaignMember.campaign_id == campaign_id, CampaignMember.user_id == user_id)
        .order_by((CampaignMember.status != "active"), CampaignMember.joined_at, CampaignMember.id).limit(1)
    )).scalar_one_or_none()
    if member is None:
        return None, None
    char = await db.get(Character, member.character_id)
    return member.character_id, char.name if char else None


@router.get("/maps/{map_id}/markers", response_model=list[MarkerRead])
async def list_markers(
    campaign_id: int, map_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> list[MarkerRead]:
    is_gm = await campaign_access(db, campaign_id, user_id)
    await _map(db, campaign_id, map_id, is_gm)
    rows = (await db.execute(
        select(CampaignMapMarker).where(CampaignMapMarker.map_id == map_id, marker_clause(user_id))
        .order_by(CampaignMapMarker.id))).scalars().all()
    return await _marker_reads(db, campaign_id, list(rows), user_id, is_gm)


@router.post("/maps/{map_id}/markers", response_model=MarkerRead, status_code=201)
async def create_marker(
    campaign_id: int, map_id: int, body: MarkerCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> MarkerRead:
    is_gm = await campaign_access(db, campaign_id, user_id)
    m = await _map(db, campaign_id, map_id, is_gm)
    await _check_link(db, campaign_id, map_id, body.link_map_id, is_gm)
    await _check_type(db, campaign_id, body.type_key, body.custom_type_id)
    char_id, author_name = (None, None) if is_gm else await _author(db, campaign_id, user_id)
    now = _now()
    public_gm = is_gm and body.visibility == "public"
    mk = CampaignMapMarker(
        campaign_id=campaign_id, map_id=map_id, author_user_id=user_id, author_character_id=char_id,
        author_name=author_name, type_key=body.type_key, custom_type_id=body.custom_type_id, name=body.name,
        description=body.description, x=body.x, y=body.y, visibility=body.visibility,
        link_map_id=body.link_map_id, revealed_at=now if public_gm else None, created_at=now, updated_at=now)
    db.add(mk)
    await db.flush()
    if public_gm and m.revealed_at is not None:
        await _feed_reveal(db, campaign_id, user_id, map_id, mk.id, mk.name, now)
        await db.flush()
    return await _one_read(db, mk, user_id, is_gm)


@router.patch("/markers/{marker_id}", response_model=MarkerRead)
async def update_marker(
    campaign_id: int, marker_id: int, body: MarkerUpdate,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> MarkerRead:
    is_gm = await campaign_access(db, campaign_id, user_id)
    mk = await _marker(db, campaign_id, marker_id, user_id, is_gm)
    _owned(mk, user_id)
    fields = body.model_dump(exclude_unset=True)
    if "link_map_id" in fields:
        await _check_link(db, campaign_id, mk.map_id, fields["link_map_id"], is_gm)
        mk.link_map_id = fields["link_map_id"]  # explicit null clears
    if "type_key" in fields or "custom_type_id" in fields:
        await _check_type(db, campaign_id, body.type_key, body.custom_type_id)
        mk.type_key, mk.custom_type_id = body.type_key, body.custom_type_id
    for f in ("name", "description", "x", "y"):
        if fields.get(f) is not None:
            setattr(mk, f, fields[f])
    mk.updated_at = _now()
    await db.flush()
    return await _one_read(db, mk, user_id, is_gm)


@router.post("/markers/{marker_id}/visibility", response_model=MarkerRead)
async def set_marker_visibility(
    campaign_id: int, marker_id: int, body: MarkerVisibility,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> MarkerRead:
    is_gm = await campaign_access(db, campaign_id, user_id)
    mk = await _marker(db, campaign_id, marker_id, user_id, is_gm)
    _owned(mk, user_id)
    if mk.visibility != body.visibility:
        now = mk.updated_at = _now()
        mk.visibility = body.visibility
        if is_gm and body.visibility == "public":
            mk.revealed_at = now
            if (await db.get(CampaignMap, mk.map_id)).revealed_at is not None:
                await _feed_reveal(db, campaign_id, user_id, mk.map_id, mk.id, mk.name, now)
        await db.flush()
    return await _one_read(db, mk, user_id, is_gm)


@router.delete("/markers/{marker_id}", status_code=204)
async def delete_marker(
    campaign_id: int, marker_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> None:
    is_gm = await campaign_access(db, campaign_id, user_id)
    mk = await _marker(db, campaign_id, marker_id, user_id, is_gm)
    if not (mk.author_user_id == user_id or (is_gm and mk.visibility == "public")):
        raise HTTPException(status_code=403, detail="not_owner")
    await db.delete(mk)
    await db.flush()


@router.get("/marker-types", response_model=list[MarkerTypeRead])
async def list_marker_types(
    campaign_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> list[MarkerTypeRead]:
    is_gm = await campaign_access(db, campaign_id, user_id)
    custom = (await _types(db, campaign_id)).values()
    return [_type_read(k, None, user_id, is_gm) for k in BUILTIN_TYPES] + [
        _type_read(None, t, user_id, is_gm) for t in custom]


@router.post("/marker-types", response_model=MarkerTypeRead, status_code=201)
async def create_marker_type(
    campaign_id: int, body: MarkerTypeCreate,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> MarkerTypeRead:
    is_gm = await campaign_access(db, campaign_id, user_id)
    t = CampaignMarkerType(campaign_id=campaign_id, name=body.name, icon=body.icon, color=body.color,
                           created_by=user_id, created_at=_now())
    db.add(t)
    await db.flush()
    return _type_read(None, t, user_id, is_gm)


@router.delete("/marker-types/{type_id}", status_code=204)
async def delete_marker_type(
    campaign_id: int, type_id: int,
    user_id: Annotated[int, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db, scope="function")],
) -> None:
    is_gm = await campaign_access(db, campaign_id, user_id)
    t = await db.get(CampaignMarkerType, type_id)
    if t is None or t.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail="type_not_found")
    if not (is_gm or t.created_by == user_id):
        raise HTTPException(status_code=403, detail="not_owner")
    # Explicit fallback: SQLite FK actions are not guaranteed on.
    await db.execute(update(CampaignMapMarker).where(CampaignMapMarker.custom_type_id == type_id)
                     .values(type_key="poi", custom_type_id=None))
    await db.delete(t)
    await db.flush()
