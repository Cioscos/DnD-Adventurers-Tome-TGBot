"""Forma selvatica: la forma attiva, il suo stato attivo (durata, fine) e i PF che assorbe (solo 2014)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.rules_states import get_states, remove_state, start_state
from core.db.models import Character, Companion
from core.game.stats import effective_ability_mod
from core.rules.edition import character_edition, class_key
from core.rules.forms import FormLimits, FormRules
from core.rules.types import StateSpec

STATE_KEY = "wild_shape"
_PHYSICAL = {"str": "strength", "dex": "dexterity", "con": "constitution"}


def form_limits(char: Character) -> FormLimits | None:
    """Limiti del druido; ``None`` se il personaggio non è un druido (forme senza regole di classe)."""
    rows = [c for c in char.classes if class_key(c) == "druid"]
    if not rows:
        return None
    return FormRules(character_edition(char), sum(c.level for c in rows), rows[0].subclass_key)


def form_own_hp(char: Character) -> bool:
    """La forma ha PF propri (2014, o chi non è druido): altrimenti sono i PF del personaggio con i temporanei."""
    state = next((s for s in get_states(char) if s["key"] == STATE_KEY), None)
    return state is None or state["data"].get("own_hp", True)


async def get_active_form(session: AsyncSession, char_id: int) -> Companion | None:
    """La forma attiva. Lo stato attivo è la verità: se è finito (durata, riposo, incapacitazione) la forma si chiude."""
    form = (await session.execute(
        select(Companion).where(
            Companion.character_id == char_id,
            Companion.kind == "wild_shape",
            Companion.is_active.is_(True),
        ).order_by(Companion.id)
    )).scalars().first()
    if form is None:
        return None
    char = await session.get(Character, char_id)
    if all(s["key"] != STATE_KEY for s in get_states(char)):
        form.is_active = False
        return None
    return form


async def deactivate_other_forms(session: AsyncSession, char_id: int, keep_id: int | None) -> None:
    """At most one active wild shape: activating one deactivates the others (no 409)."""
    res = await session.execute(
        select(Companion).where(Companion.character_id == char_id, Companion.is_active.is_(True))
    )
    for other in res.scalars():
        if other.id != keep_id:
            other.is_active = False


def end_form(char: Character, form: Companion) -> None:
    """Chiude la forma e il suo stato (ritorno volontario, 0 PF della forma)."""
    form.is_active = False
    if any(s["key"] == STATE_KEY for s in get_states(char)):
        remove_state(char, STATE_KEY)


def start_form(char: Character, form: Companion, grant: bool = True) -> None:
    """Avvia lo stato della forma: durata e fine per edizione; nel 2024 i PF temporanei e la CA del Circolo della Luna."""
    limits = form_limits(char)
    edition = character_edition(char)
    ends = ["rest_short", "rest_long", "unconscious", "manual", *(["incapacitated"] if edition == "2024" else [])]
    sb = form.statblock or {}
    abilities = {full: sb["abilities"][short] for short, full in _PHYSICAL.items()
                 if isinstance(sb.get("abilities"), dict) and short in sb["abilities"]}
    own_hp = limits is None or limits.own_hp
    start_state(char, StateSpec(
        key=STATE_KEY, rounds=limits.rounds or None if limits else None, ends_on=tuple(ends),
        data={"companion_id": form.id, "abilities": abilities, "mode": "replace" if own_hp else "max", "own_hp": own_hp},
    ), "druid.wild_shape")
    if grant and limits is not None and not limits.own_hp:
        char.temp_hp = max(char.temp_hp or 0, limits.temp_hp)  # i PF temporanei non si sommano: vale il maggiore
        if limits.ac_wisdom:
            form.armor_class = max(form.armor_class, 13 + effective_ability_mod(char, "wisdom"))


def absorb_damage(form: Companion, amount: int) -> int:
    """Apply `amount` to the form (temp HP first); return the overflow past 0 HP."""
    absorbed = min(form.temp_hp, amount)
    form.temp_hp -= absorbed
    rest = amount - absorbed
    lost = min(form.current_hp, rest)
    form.current_hp -= lost
    return rest - lost
