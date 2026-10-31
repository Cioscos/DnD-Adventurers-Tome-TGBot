"""Round-based durations for conditions and concentration (settings JSON)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.data.labels import condition_label
from core.db.models import Character
from api.services.effects import _add_history, apply_conditions


def end_concentration(char: Character) -> None:
    """Single place that drops concentration (spell id + round counter)."""
    char.concentrating_spell_id = None
    if (char.settings or {}).get("concentration_rounds_left") is not None:
        s = dict(char.settings)
        s.pop("concentration_rounds_left")
        char.settings = s


def set_concentration_rounds(char: Character, rounds: int | None) -> None:
    s = dict(char.settings or {})
    if rounds is None:
        s.pop("concentration_rounds_left", None)
    else:
        s["concentration_rounds_left"] = rounds
    char.settings = s


def set_condition_durations(char: Character, durations: dict[str, int | None]) -> None:
    """None (or <= 0) removes the duration for that condition."""
    s = dict(char.settings or {})
    cd = dict(s.get("condition_durations") or {})
    for slug, rounds in durations.items():
        if rounds is None or rounds <= 0:
            cd.pop(slug, None)
        else:
            cd[slug] = rounds
    s["condition_durations"] = cd
    char.settings = s


async def tick_rounds(session: AsyncSession, char: Character) -> list[str]:
    """Decrement every duration by one round; expire effects reaching 0."""
    s = dict(char.settings or {})
    cd = dict(s.get("condition_durations") or {})
    expired: list[str] = []
    to_clear: dict[str, bool] = {}
    for slug, left in list(cd.items()):
        left -= 1
        if left > 0:
            cd[slug] = left
            continue
        del cd[slug]
        label = condition_label(slug)
        expired.append(label)
        to_clear[slug] = False
        _add_history(session, char.id, "condition_change", f"Durata scaduta: {label}")
    s["condition_durations"] = cd

    conc = s.get("concentration_rounds_left")
    ended_conc = False
    if conc is not None:
        if conc - 1 > 0:
            s["concentration_rounds_left"] = conc - 1
        else:
            s.pop("concentration_rounds_left")
            ended_conc = True
    char.settings = s
    if ended_conc:
        char.concentrating_spell_id = None
        expired.append("Concentrazione")
        _add_history(session, char.id, "concentration",
                     "Concentrazione terminata: durata scaduta")
    if to_clear:
        await apply_conditions(session, char, to_clear)
    return expired
