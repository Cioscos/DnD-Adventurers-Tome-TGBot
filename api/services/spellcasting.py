"""Costruzione del blocco ``CharacterFull.spellcasting``.

Funzione sincrona e senza query: richiede ``char.classes``,
``char.ability_scores`` e ``char.spells`` già caricati — vero per ogni chiamante
di ``build_character_response`` (le stesse relazioni sono serializzate da
``CharacterFull.model_validate``). Le regole sono in ``core.rules.spellcasting``.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

from api.schemas.character import ClassSpellLimits, SpellCasterStats, SpellcastingInfo
from api.schemas.spell import SpellRead
from core.data.spell_slots import caster_kind
from core.data.spellcasting import has_wizard
from core.db.models import Character, Spell
from core.game.stats import effective_ability_mod
from core.rules.edition import character_edition, class_key
from core.rules.level_choices import FREE_KNOWN_KEY
from core.rules.spellcasting import (
    at_will, caster_stats, can_ritual, granted_ritual_only, ki_cast_info, known_limits, normalize_school, prepared_limit,
    prepares, school_limit, spell_stats,
)


def fill_spell_stats(char: Character, spells: Iterable[SpellRead]) -> None:
    for spell in spells:
        stats = spell_stats(char, spell)
        if stats:
            spell.save_dc, spell.attack_bonus = stats.save_dc, stats.attack_bonus
        spell.at_will = at_will(char, spell)
        ki = ki_cast_info(char, spell)
        if ki is not None:
            spell.ki_cast = {"cost": ki.cost, "max_extra": ki.max_extra, "ki_left": ki.ki_left, "feature_key": ki.feature_key}
            if not stats:  # chi lancia solo col ki ha la CD del ki, non quella di un incantatore
                spell.save_dc, spell.attack_bonus = ki.dc, char.proficiency_bonus + effective_ability_mod(char, "wisdom")


def _class_limits(char: Character, manual_cap: bool) -> list[ClassSpellLimits]:
    edition = character_edition(char)
    casters = [c for c in char.classes if class_key(c) and caster_kind(c, edition)]
    out: list[ClassSpellLimits] = []
    free = set((char.settings or {}).get(FREE_KNOWN_KEY) or [])  # Segreti Magici Aggiuntivi: fuori dai conosciuti
    for cls in casters:
        key = class_key(cls)
        limits = known_limits(edition, key, cls.level)
        # Non assegnati: appartengono all'unica classe che lancia incantesimi, altrimenti solo al totale.
        mine = [s for s in char.spells if not s.always_prepared and s.id not in free
                and (s.class_id == cls.id or (s.class_id is None and len(casters) == 1))]
        leveled = [s for s in mine if s.level >= 1]
        cap = prepared_limit(edition, key, cls.level, char)
        school = school_limit(edition, cls)
        # senza scuola salvata non si sa: non conta come fuori scuola
        outside = sum(1 for s in leveled if school and (found := normalize_school(s.school)) and found not in school.names)
        out.append(ClassSpellLimits(
            school_names=list(school.names) if school else None, school_free_limit=school.free if school else None,
            school_outside_count=outside,
            class_id=cls.id, class_name=cls.class_name,
            cantrips_count=len(mine) - len(leveled), cantrips_limit=limits.cantrips or None,
            known_count=len(leveled), known_limit=limits.spells,
            prepared_count=sum(1 for s in leveled if s.is_prepared),
            prepared_limit=cap if cap and not manual_cap else None,
        ))
    return out


def prepared_class_room(char: Character, class_id: int) -> tuple[int, int] | None:
    """(preparati, limite) di una classe; ``None`` se il limite per classe non vale (classe assente, tetto a mano)."""
    manual = (char.settings or {}).get("prepared_cap_mode") == "manual"
    row = next((x for x in _class_limits(char, manual) if x.class_id == class_id), None)
    if row is None or row.prepared_limit is None:
        return None
    count = sum(1 for s in char.spells if s.class_id == class_id and s.level >= 1 and s.is_prepared and not s.always_prepared)
    return count, row.prepared_limit


def build_spellcasting_info(char: Character) -> SpellcastingInfo:
    classes = char.classes
    settings = char.settings or {}
    edition = character_edition(char)
    preparing_rows = [c for c in classes if prepares(edition, c, char)]
    preparing = bool(preparing_rows)
    cap_mode = settings.get("prepared_cap_mode") or "auto"

    cap: int | None = None
    if preparing:
        if cap_mode == "manual":
            cap = max(0, int(settings.get("prepared_cap_value") or 0))
        else:
            cap = sum(prepared_limit(edition, class_key(c), c.level, char) for c in preparing_rows)

    count = sum(1 for s in char.spells if counts_as_prepared(s))

    return SpellcastingInfo(
        has_preparing_class=preparing,
        prepared_cap=cap,
        prepared_count=count,
        cap_mode=cap_mode if preparing else "auto",
        has_ritual_caster=can_ritual(char),
        ritual_only_spell_ids=[sp.id for sp in char.spells if granted_ritual_only(char, sp)],
        has_wizard=has_wizard(classes),
        casters=[SpellCasterStats(**asdict(c)) for c in caster_stats(char)],
        limits=_class_limits(char, cap_mode == "manual"),
    )


def counts_as_prepared(spell: Spell) -> bool:
    return spell.level >= 1 and bool(spell.is_prepared) and not spell.always_prepared
