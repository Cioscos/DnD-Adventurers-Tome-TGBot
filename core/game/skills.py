"""Pure skill math (proficiency, Jack of All Trades); totals with homebrew live in api.services.skills."""
from __future__ import annotations

from core.data.spell_slots import normalize_class_name
from core.db.models import Character
from core.game.stats import roll_ability_mod

PASSIVE_SKILLS = ("perception", "insight", "investigation")


def has_jack_of_all_trades(char: Character) -> bool:
    """Bard level 2+ (computed, never stored)."""
    return any(
        normalize_class_name(c.class_name) == "bard" and c.level >= 2
        for c in char.classes
    )


def jack_of_all_trades_part(char: Character) -> int:
    """Factotum: metà del bonus di competenza su ogni prova in cui non si è competenti (abilità o prova pura)."""
    return char.proficiency_bonus // 2 if has_jack_of_all_trades(char) else 0


def _form_proficiencies(char: Character, kind: str) -> dict:
    """Competenze della bestia salvate con la Forma Selvatica (2014): ``kind`` = ``skills`` o ``saves``. Vuoto se mancano."""
    form = next((s for s in char.active_states or [] if s.get("key") == "wild_shape"), None)
    found = ((form or {}).get("data") or {}).get(kind)
    return found if isinstance(found, dict) else {}


def skill_roll_part(char: Character, skill: str, ability: str) -> int:
    """Modificatore più competenza di un'abilità. In Forma Selvatica il druido acquisisce le competenze della bestia e,
    se la bestia ha un bonus più alto del suo, vale quello della bestia."""
    mod, own = roll_ability_mod(char, ability), skill_proficiency_part(char, skill)
    beast = _form_proficiencies(char, "skills").get(skill)
    if type(beast) is not int:
        return mod + own
    return max(mod + max(own, char.proficiency_bonus), beast)


def save_roll_part(char: Character, ability: str) -> int:
    """Modificatore più competenza di un TS, con le stesse regole delle abilità per le competenze della bestia."""
    mod = roll_ability_mod(char, ability)
    own = char.proficiency_bonus if (char.saving_throws or {}).get(ability, False) else 0
    beast = _form_proficiencies(char, "saves").get(ability)
    if type(beast) is not int:
        return mod + own
    return max(mod + max(own, char.proficiency_bonus), beast)


def skill_proficiency_part(char: Character, skill: str) -> int:
    """PB x {expert 2, proficient 1}; Jack of All Trades adds floor(PB/2) when not proficient."""
    level = (char.skills or {}).get(skill)
    pb = char.proficiency_bonus
    if level == "expert":
        return 2 * pb
    if level is True or level == 1:
        return pb
    return jack_of_all_trades_part(char)
