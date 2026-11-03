"""Annuncio Telegram della nuova versione, lanciato all'avvio dell'API.

Confronta ``entries[0].version`` di ``changelog.json`` con
``app_meta.last_announced_version``: se è nuova la segna PRIMA di inviare
(un riavvio non manda mai doppioni; un crash a metà invio perde qualche
annuncio) e la manda a chi ha premuto /start o ha un personaggio, meno chi si
è disiscritto con /unsubscribe.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.services.campaigns import STASH_USER_ID
from api.services.telegram_notify import bot_token_configured, miniapp_url, send_telegram_message
from core.db.models import AppMeta, BotUser, Character

logger = logging.getLogger(__name__)

CHANGELOG_PATH = Path(__file__).resolve().parents[2] / "webapp" / "src" / "data" / "changelog.json"
_META_KEY = "last_announced_version"

_TEXT = {
    "it": {
        "title": "Novità v{version}",
        "added": "Novità",
        "improved": "Miglioramenti",
        "fixed": "Correzioni",
        "footer": "Non vuoi più questi messaggi? /unsubscribe",
        "button": "Apri le novità",
    },
    "en": {
        "title": "What's new in v{version}",
        "added": "Added",
        "improved": "Improved",
        "fixed": "Fixed",
        "footer": "Don't want these messages? /unsubscribe",
        "button": "Open release notes",
    },
}


def announcements_enabled() -> bool:
    """Solo con ANNOUNCE_RELEASES=1 (il .env del Pi): API locali e test non scrivono mai agli utenti."""
    return os.environ.get("ANNOUNCE_RELEASES") == "1" and bot_token_configured()


def format_announcement(entry: dict, lang: str) -> str:
    t = _TEXT[lang]
    parts = [t["title"].format(version=entry["version"])]
    for section in ("added", "improved", "fixed"):
        items = (entry.get(section) or {}).get(lang) or []
        if items:
            parts.append(t[section] + "\n" + "\n".join(f"• {i}" for i in items))
    parts.append(t["footer"])
    return "\n\n".join(parts)


async def recipients(session: AsyncSession) -> dict[int, str]:
    """user_id → "it"/"en": chi ha premuto /start o ha un PG, meno i disiscritti."""
    users = (await session.execute(select(BotUser))).scalars().all()
    opted_out = {u.user_id for u in users if not u.announcements}
    langs = {u.user_id: u.language_code for u in users if u.announcements}
    owners = (await session.execute(select(Character.user_id).where(Character.user_id != STASH_USER_ID).distinct())).scalars().all()
    for uid in owners:
        if uid not in opted_out:
            langs.setdefault(uid, None)
    return {
        uid: "en" if (lc or "").lower().startswith("en") else "it"
        for uid, lc in langs.items()
    }


async def announce_latest_release(
    session_factory: async_sessionmaker,
    changelog_path: Path = CHANGELOG_PATH,
    delay: float = 0.05,
) -> int:
    """Invia l'annuncio se la versione non è già stata annunciata. Mai solleva."""
    try:
        entry = json.loads(changelog_path.read_text(encoding="utf-8"))["entries"][0]
        version = entry["version"]
        async with session_factory() as session:
            meta = await session.get(AppMeta, _META_KEY)
            if meta is not None and meta.value == version:
                return 0
            if meta is None:
                session.add(AppMeta(key=_META_KEY, value=version))
            else:
                meta.value = version
            await session.commit()
            targets = await recipients(session)
    except Exception:
        logger.exception("Annuncio release: preparazione fallita")
        return 0

    sent = 0
    for uid, lang in targets.items():
        ok = await send_telegram_message(
            uid,
            format_announcement(entry, lang),
            button=(_TEXT[lang]["button"], miniapp_url("/changelog")),
        )
        sent += ok
        await asyncio.sleep(delay)
    logger.info("Annuncio v%s inviato a %d/%d utenti", version, sent, len(targets))
    return sent
