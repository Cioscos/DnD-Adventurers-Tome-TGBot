"""Round-based durations for conditions and concentration (settings JSON)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.data.labels import condition_label
from core.db.models import Character
from api.services.effects import _add_history, apply_conditions


def is_concentrating(char: Character) -> bool:
    return char.concentrating_spell_id is not None or bool(
        (char.settings or {}).get("concentration_item_spell"))


def end_concentration(char: Character) -> None:
    """Single place that drops concentration (spell id, item spell, round counter)."""
    char.concentrating_spell_id = None
    s = dict(char.settings or {})
    if any([s.pop("concentration_rounds_left", None) is not None,
            s.pop("concentration_item_spell", None) is not None]):
        char.settings = s


def start_concentration(char: Character, spell_id: int | None, rounds: int | None,
                        item_spell: dict | None = None) -> None:
    """Begin concentrating, properly ending any previous one first."""
    end_concentration(char)
    char.concentrating_spell_id = spell_id
    s = dict(char.settings or {})
    if item_spell is not None:
        s["concentration_item_spell"] = item_spell
    if rounds is not None:
        s["concentration_rounds_left"] = rounds
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


def _is_int(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


async def tick_rounds(session: AsyncSession, char: Character) -> list[str]:
    """Decrement every duration by one round; expire effects reaching 0."""
    s = dict(char.settings or {})
    raw_cd = s.get("condition_durations")
    cd = dict(raw_cd) if isinstance(raw_cd, dict) else {}
    expired: list[str] = []
    to_clear: dict[str, bool] = {}
    for slug, left in list(cd.items()):
        if not _is_int(left):  # malformed (hand-edited/imported) entry: drop it, never 500
            del cd[slug]
            continue
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
    if conc is not None and not _is_int(conc):
        s.pop("concentration_rounds_left")
    elif conc is not None:
        if conc - 1 > 0:
            s["concentration_rounds_left"] = conc - 1
        else:
            s.pop("concentration_rounds_left")
            s.pop("concentration_item_spell", None)
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
