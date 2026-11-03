"""Campaign helpers: invite codes and the hidden party-stash character."""
from __future__ import annotations

import secrets
import string
from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import Campaign, Character, Currency

STASH_USER_ID = 0  # owner of stash characters: never a real Telegram user
_ALPHABET = string.ascii_uppercase + string.digits


async def generate_campaign_code(db: AsyncSession) -> str:
    while True:
        code = "".join(secrets.choice(_ALPHABET) for _ in range(8))
        taken = (await db.execute(select(Campaign.id).where(Campaign.invite_code == code))).first()
        if taken is None:
            return code


async def create_campaign(db: AsyncSession, gm_user_id: int, name: str) -> Campaign:
    stash = Character(user_id=STASH_USER_ID, name=name, currency=Currency())
    db.add(stash)
    await db.flush()
    campaign = Campaign(
        name=name,
        invite_code=await generate_campaign_code(db),
        gm_user_id=gm_user_id,
        stash_character_id=stash.id,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    db.add(campaign)
    await db.flush()
    return campaign


def unlink_file(path: str | None) -> None:
    """Best-effort removal of an uploaded file."""
    if path:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass
