"""Party message formatter — Italian MarkdownV2 output for the group party screen."""

from __future__ import annotations

from datetime import datetime, timezone

from bot.db.models import Character, PartySession


def _esc(text: str) -> str:
    """Escape MarkdownV2 special characters."""
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in str(text))


def _hp_bar(current: int, maximum: int, width: int = 8) -> str:
    """Return a compact HP bar string."""
    if maximum <= 0:
        return "░" * width
    filled = round((current / maximum) * width)
    filled = max(0, min(filled, width))
    return "█" * filled + "░" * (width - filled)


def _time_remaining(expires_at_iso: str) -> str:
    """Return a human-readable time-remaining string from an ISO timestamp."""
    try:
        expires = datetime.fromisoformat(expires_at_iso)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        delta = expires - now
        if delta.total_seconds() <= 0:
            return "scaduta"
        total_seconds = int(delta.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes = remainder // 60
        return f"{hours}h {minutes:02d}m"
    except Exception:
        return "N/D"


def format_party_message(
    characters: list[tuple[Character, str | None]],
    session: PartySession,
) -> str:
    """Format the full party status message.

    Args:
        characters: list of (Character, telegram_username_or_none) tuples,
                    already loaded with their ``classes`` relationship.
        session: the active :class:`PartySession` for time display.

    Returns:
        A MarkdownV2-escaped string ready to send via Telegram.
    """
    group_title = _esc(session.group_title or "Gruppo")
    remaining = _esc(_time_remaining(session.expires_at or ""))

    lines: list[str] = [
        f"🎯 *Sessione Party — {group_title}*",
        f"⏳ Scade tra: {remaining}",
    ]

    if not characters:
        lines.append("")
        lines.append("_Nessun personaggio attivo nel party\\._")
        return "\n".join(lines)

    for char, username in characters:
        hp_bar = _hp_bar(char.current_hit_points, char.hit_points)
        cls_summary = _esc(char.class_summary)
        char_name = _esc(char.name)
        user_label = f" \\(@{_esc(username)}\\)" if username else ""

        lines.append("")
        lines.append("─────────────────")
        lines.append(f"⚔️ *{char_name}*{user_label}")
        lines.append(f"🎭 {cls_summary}")
        lines.append(
            f"❤️ HP: {_esc(str(char.current_hit_points))}/{_esc(str(char.hit_points))} "
            f"{_esc(hp_bar)}"
        )
        lines.append(f"🛡️ CA: {_esc(str(char.ac))}")

    return "\n".join(lines)
