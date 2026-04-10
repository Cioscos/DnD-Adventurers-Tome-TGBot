"""Party message formatter — localised MarkdownV2 output for the group party screen."""

from __future__ import annotations

from datetime import datetime, timezone

from bot.db.models import Character, PartySession
from bot.utils.i18n import translator


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


def _time_remaining(expires_at_iso: str, lang: str = "it") -> str:
    """Return a human-readable time-remaining string from an ISO timestamp."""
    try:
        expires = datetime.fromisoformat(expires_at_iso)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        delta = expires - now
        if delta.total_seconds() <= 0:
            return translator.t("party.time_expired", lang=lang)
        total_seconds = int(delta.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes = remainder // 60
        return translator.t("party.time_format", lang=lang, hours=hours, minutes=f"{minutes:02d}")
    except Exception:
        return translator.t("party.time_unknown", lang=lang)


def _get_active_conditions(char: Character, lang: str = "it") -> str:
    """Return a compact comma-separated string of active conditions, or '' if none."""
    from bot.utils.formatting import CONDITIONS_ORDER
    if not char.conditions:
        return ""
    conditions = char.conditions
    parts: list[str] = []
    for slug in CONDITIONS_ORDER:
        if slug == "exhaustion":
            level = int(conditions.get("exhaustion", 0))
            if level > 0:
                name = translator.t("character.conditions.names.exhaustion", lang=lang)
                parts.append(_esc(f"{name} {level}/6"))
        else:
            if bool(conditions.get(slug, False)):
                name = translator.t(f"character.conditions.names.{slug}", lang=lang)
                parts.append(_esc(name))
    return ", ".join(parts)


def _get_last_roll(char: Character) -> str:
    """Return the last dice roll as a compact escaped string, or '' if no history."""
    if not char.rolls_history:
        return ""
    last = char.rolls_history[-1]
    if not isinstance(last, (list, tuple)) or len(last) < 2:
        return ""
    dice_str = str(last[0])        # e.g. "2d6"
    results = last[1]              # e.g. [3, 4]
    if not isinstance(results, (list, tuple)) or not results:
        return ""
    total = sum(int(r) for r in results)
    if len(results) == 1:
        return _esc(f"{dice_str} → {total}")
    results_str = ", ".join(str(r) for r in results)
    return _esc(f"{dice_str} → {total} ({results_str})")


def format_party_message(
    characters: list[tuple[Character, str | None]],
    session: PartySession,
    lang: str = "it",
) -> str:
    """Format the full party status message.

    Args:
        characters: list of (Character, telegram_username_or_none) tuples,
                    already loaded with their ``classes`` relationship.
        session: the active :class:`PartySession` for time display.
        lang: BCP-47 language code for localisation (default ``"it"``).

    Returns:
        A MarkdownV2-escaped string ready to send via Telegram.
    """
    group_title = _esc(session.group_title or "Gruppo")
    remaining = _esc(_time_remaining(session.expires_at or "", lang=lang))

    lines: list[str] = [
        translator.t("party.msg_title", lang=lang, group_title=group_title),
        translator.t("party.msg_expires", lang=lang, remaining=remaining),
    ]

    if not characters:
        lines.append("")
        lines.append(translator.t("party.msg_no_active", lang=lang))
        return "\n".join(lines)

    sep = translator.t("party.msg_separator", lang=lang)
    ac_label = translator.t("character.common.ac_label", lang=lang)

    for char, username in characters:
        hp_bar = _hp_bar(char.current_hit_points, char.hit_points)
        cls_summary = _esc(char.class_summary)
        char_name = _esc(char.name)
        user_label = (
            translator.t("party.user_label", lang=lang, username=_esc(username))
            if username else ""
        )

        lines.append("")
        lines.append(sep)
        lines.append(translator.t("party.msg_char_name", lang=lang, name=char_name, user_label=user_label))
        lines.append(translator.t("party.msg_char_class", lang=lang, classes=cls_summary))
        lines.append(
            translator.t(
                "party.msg_char_hp", lang=lang,
                current=_esc(str(char.current_hit_points)),
                max=_esc(str(char.hit_points)),
                bar=_esc(hp_bar),
            )
        )
        lines.append(translator.t("party.msg_char_ac", lang=lang, ac=_esc(str(char.ac))))

        from bot.utils.formatting import death_state_label
        death_label = death_state_label(char, lang=lang)
        if death_label:
            lines.append(translator.t("party.msg_char_death_state", lang=lang, state=death_label))

        active_conditions = _get_active_conditions(char, lang=lang)
        if active_conditions:
            lines.append(translator.t("party.msg_char_conditions", lang=lang, conditions=active_conditions))

        last_roll = _get_last_roll(char)
        if last_roll:
            lines.append(translator.t("party.msg_char_last_roll", lang=lang, roll=last_roll))

    return "\n".join(lines)
