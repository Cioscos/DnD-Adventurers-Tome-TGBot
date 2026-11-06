"""Libro degli Incantesimi del Mago 2014: di chi è un incantesimo, quanto costa copiarlo, cosa si può preparare.

Funzioni pure sul personaggio, senza scrivere nulla: chi copia (``api/routers/spellbook.py``) controlla e spende.
Costi dalla scheda ``docs/superpowers/rules/2014/classes/wizard.md``: copia nel libro 2 ore e 50 mo per livello
dell'incantesimo, copia di riserva e ritrascrizione 1 ora e 10 mo per livello; i «Sapienti» dimezzano solo la copia nel libro.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.rules.catalog import active_features
from core.rules.edition import character_edition, class_key
from core.rules.schools import normalize_school
from core.rules.spellcasting import slots_for

MODES = ("copy", "backup", "retranscribe")  # retranscribe: il libro è andato perso, si ritrascrive un incantesimo preparato
_HOURS = {"copy": 2, "retranscribe": 1, "backup": 1}
_GOLD = {"copy": 50, "retranscribe": 10, "backup": 10}


@dataclass(frozen=True)
class CopyCost:
    hours: float
    gold: int
    halved: bool


def wizard_row(char: Any, spell: Any) -> Any | None:
    """La classe Mago a cui appartiene l'incantesimo: quella assegnata, o l'unico incantatore se non è assegnato
    (personaggi salvati prima delle classi sugli incantesimi). ``None``: non è un incantesimo da mago, o il personaggio
    non segue le regole 2014."""
    if character_edition(char) != "2014":
        return None
    wizards = [c for c in char.classes if class_key(c) == "wizard"]
    if spell.class_id is not None:
        return next((c for c in wizards if c.id == spell.class_id), None)
    casters = [c for c in char.classes if c.spellcasting_ability]
    return wizards[0] if len(wizards) == 1 and len(casters) <= 1 else None


def copy_halved(char: Any, school: str | None) -> bool:
    """Un «Sapiente» della scuola dell'incantesimo dimezza tempo e costo."""
    wanted = normalize_school(school)
    return wanted is not None and any(normalize_school(spec.copy_school) == wanted for spec, _row in active_features(char))


def copy_cost(char: Any, level: int, school: str | None, mode: str = "copy") -> CopyCost:
    halved = mode == "copy" and copy_halved(char, school)  # «vale solo per la copia nel libro»
    hours, gold = _HOURS[mode] * level, _GOLD[mode] * level
    return CopyCost(hours / 2 if halved else float(hours), gold // 2 if halved else gold, halved)


def top_slot_level(char: Any, row: Any) -> int:
    """Livello più alto che la classe lancia secondo la sua tabella: un incantesimo si prepara o si copia solo fino a lì."""
    regular = slots_for(character_edition(char), [row]).regular
    return max((level for level, total in regular.items() if total > 0), default=0)


def book_refusal(char: Any, spell: Any, mode: str) -> tuple[int, str] | None:
    """Perché ``spell`` non si copia nel libro con ``mode``: ``(codice_http, nome)``, ``None`` se si può."""
    row = wizard_row(char, spell)
    if row is None or spell.level < 1:
        return 422, "not_a_wizard_spell"  # i trucchetti non occupano il libro
    if mode not in MODES:
        return 422, "bad_copy_mode"
    if mode == "backup":
        if not spell.in_spellbook:
            return 409, "not_in_spellbook"
        if spell.in_backup:
            return 409, "already_in_backup"
        return None
    if spell.in_spellbook:
        return 409, "already_in_spellbook"
    if spell.level > top_slot_level(char, row):
        return 422, "spell_above_slots"
    if mode == "retranscribe" and not spell.is_prepared:
        return 409, "not_prepared"  # a libro perso si ritrascrivono solo gli incantesimi preparati
    return None


def prepare_refusal(char: Any, spell: Any) -> tuple[int, str] | None:
    """Perché un incantesimo del Mago non si può preparare: fuori dal libro, o di un livello per cui non ha slot."""
    row = wizard_row(char, spell)
    if row is None or spell.level < 1 or spell.always_prepared:
        return None
    if not spell.in_spellbook:
        return 409, "not_in_spellbook"
    if spell.level > top_slot_level(char, row):
        return 422, "spell_above_slots"
    return None
