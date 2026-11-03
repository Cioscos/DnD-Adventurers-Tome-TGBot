"""Background task: Telegram reminders for planned campaign evenings.

Day reminder when 1h < delta <= 24h, hour reminder when delta <= 1h (it also sets the
day flag: the day reminder never fires after the hour one). Texts carry no clock time
(the server has no tz data; the app shows local time). Only with SEND_CAMPAIGN_MESSAGES=1.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta

from sqlalchemy import select

from api.database import AsyncSessionLocal
from api.services import telegram_notify
from api.services.campaigns import STASH_USER_ID
from api.services.recap import _lang
from core.db.models import BotUser, Campaign, CampaignMember, CampaignSchedule

logger = logging.getLogger(__name__)

_INTERVAL_SECONDS = 5 * 60

_T = {
    "it": {
        "day": "📅 Domani c'è una serata di {name}!",
        "hour": "⏰ Fra un'ora si gioca: {name}",
        "button": "Apri la campagna",
    },
    "en": {
        "day": "📅 Tomorrow there's a session of {name}!",
        "hour": "⏰ Playing in an hour: {name}",
        "button": "Open campaign",
    },
}


async def _remind_once(now: datetime | None = None, session_factory=None) -> int:
    """One sweep; returns the number of reminders marked (and attempted)."""
    if os.environ.get("SEND_CAMPAIGN_MESSAGES") != "1" or not telegram_notify.bot_token_configured():
        return 0
    now = now or datetime.utcnow()
    now_iso = now.isoformat(timespec="seconds")
    factory = session_factory or AsyncSessionLocal
    due: list[tuple[int, str, str | None]] = []  # (campaign_id, kind, note)
    async with factory() as db:
        rows = (await db.execute(
            select(CampaignSchedule).where(
                CampaignSchedule.session_id.is_(None), CampaignSchedule.starts_at > now_iso
            ).order_by(CampaignSchedule.starts_at)
        )).scalars().all()
        for r in rows:
            delta = datetime.fromisoformat(r.starts_at) - now
            if delta <= timedelta(hours=1) and r.reminded_hour_at is None:
                r.reminded_hour_at = now_iso
                r.reminded_day_at = r.reminded_day_at or now_iso
                due.append((r.campaign_id, "hour", r.note))
            elif timedelta(hours=1) < delta <= timedelta(hours=24) and r.reminded_day_at is None:
                r.reminded_day_at = now_iso
                due.append((r.campaign_id, "day", r.note))
        await db.commit()  # mark before sending: no duplicates after a restart
        for campaign_id, kind, note in due:
            try:
                await _send(db, campaign_id, kind, note)
            except Exception:  # noqa: BLE001 — best effort
                logger.exception("Reminder failed for campaign %s", campaign_id)
    return len(due)


async def _send(db, campaign_id: int, kind: str, note: str | None) -> None:
    camp = await db.get(Campaign, campaign_id)
    if camp is None:
        return
    owners = (await db.execute(
        select(CampaignMember.user_id).where(
            CampaignMember.campaign_id == campaign_id, CampaignMember.status != "dead"
        )
    )).scalars().all()
    recipients = [u for u in dict.fromkeys([camp.gm_user_id, *owners]) if u != STASH_USER_ID]
    langs = dict((await db.execute(
        select(BotUser.user_id, BotUser.language_code).where(BotUser.user_id.in_(recipients))
    )).all()) if recipients else {}
    for uid in recipients:
        t = _T[_lang(langs.get(uid))]
        text = t[kind].format(name=camp.name) + (f"\n{note}" if note else "")
        await telegram_notify.send_telegram_message(
            uid, text, button=(t["button"], telegram_notify.miniapp_url(f"/campaign/{campaign_id}"))
        )


async def run_campaign_reminders() -> None:
    """Forever loop — checks for due reminders every 5 minutes."""
    while True:
        try:
            await _remind_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Campaign reminders sweep failed")
        await asyncio.sleep(_INTERVAL_SECONDS)
