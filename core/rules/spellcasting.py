"""Incantesimi per edizione e per classe: slot, limiti, CD e conferme al lancio. Valori dalle schede delle classi."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from core.data.spell_slots import (
    THIRD_SUBCLASSES, caster_kind, compute_pact_slots, compute_regular_slots, normalize_class_name,
)
from core.data.spellcasting import PREPARING_CLASSES, compute_prepared_cap, has_ritual_caster, has_wizard
from core.game.item_bonuses import item_bonus_total
from core.game.stats import effective_ability_mod
from core.rules.catalog import active_features
from core.rules.edition import character_edition, class_key as row_class_key
from core.rules.catalog.granted_spells import GRANTED_SPELLS
from core.rules.proficiencies import is_armor_proficient
from core.rules.schools import normalize_school  # noqa: F401  (ri-esportata: la usano i chiamanti storici)
from core.rules.states import casting_blocked_by, free_cast_state, has_state
from core.rules.types import Edition


@dataclass(frozen=True)
class SlotTable:
    regular: dict[int, int] = field(default_factory=dict)  # livello -> slot
    pact: dict[int, int] = field(default_factory=dict)


@dataclass(frozen=True)
class KnownLimits:
    cantrips: int
    spells: int | None  # None: la classe non ha un numero di incantesimi conosciuti


@dataclass(frozen=True)
class CasterStats:
    class_id: int
    class_name: str
    ability: str
    save_dc: int
    attack_bonus: int


def slots_for(edition: Edition, classes: Iterable[Any]) -> SlotTable:
    classes = list(classes)
    return SlotTable(compute_regular_slots(classes, edition), compute_pact_slots(classes))


# Trucchetti: livello minimo -> numero, uguali nelle due edizioni.
_CANTRIPS: dict[str, dict[int, int]] = {
    "bard": {1: 2, 4: 3, 10: 4}, "cleric": {1: 3, 4: 4, 10: 5}, "druid": {1: 2, 4: 3, 10: 4},
    "sorcerer": {1: 4, 4: 5, 10: 6}, "warlock": {1: 2, 4: 3, 10: 4}, "wizard": {1: 3, 4: 4, 10: 5},
    "fighter": {3: 2, 10: 3}, "rogue": {3: 3, 10: 4},
}
# Terzi incantatori, dal 3° livello: stessa colonna, «conosciuti» nel 2014 e «preparati» nel 2024.
_THIRD = (0, 0, 3, 4, 4, 4, 5, 6, 6, 7, 8, 8, 9, 10, 10, 11, 11, 11, 12, 13)
_WARLOCK = (2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 11, 11, 12, 12, 13, 13, 14, 14, 15, 15)
_KNOWN_2014: dict[str, tuple[int, ...]] = {
    "bard": (4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 15, 16, 18, 19, 19, 20, 22, 22, 22),
    "ranger": (0, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11),
    "sorcerer": (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 12, 13, 13, 14, 14, 15, 15, 15, 15),
    "warlock": _WARLOCK, "fighter": _THIRD, "rogue": _THIRD,
}
_FULL_2024 = (4, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16, 16, 17, 17, 18, 18, 19, 20, 21, 22)
_HALF_2024 = (2, 3, 4, 5, 6, 6, 7, 7, 9, 9, 10, 10, 11, 11, 12, 12, 14, 14, 15, 15)
_PREPARED_2024: dict[str, tuple[int, ...]] = {
    "bard": _FULL_2024, "cleric": _FULL_2024, "druid": _FULL_2024,
    "paladin": _HALF_2024, "ranger": _HALF_2024,
    "sorcerer": (2, 4, 6, 7, *_FULL_2024[4:]),
    "warlock": _WARLOCK,
    "wizard": (4, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16, 16, 17, 18, 19, 21, 22, 23, 24, 25),
    "fighter": _THIRD, "rogue": _THIRD,
}


def _at_level(table: tuple[int, ...], level: int) -> int:
    return table[max(1, min(level, 20)) - 1]


def known_limits(edition: Edition, class_key: str | None, level: int) -> KnownLimits:
    """Per Guerriero e Ladro vale per i terzi incantatori: chi chiama sa se lo sono."""
    steps = _CANTRIPS.get(class_key, {})
    reached = [lv for lv in steps if lv <= level]
    spells = _KNOWN_2014.get(class_key) if edition == "2014" else None
    return KnownLimits(steps[max(reached)] if reached else 0, _at_level(spells, level) if spells else None)


@dataclass(frozen=True)
class _Row:
    class_name: str
    level: int
    spellcasting_ability: str


def prepared_limit(edition: Edition, class_key: str | None, level: int, char: Any) -> int:
    """Incantesimi preparabili dalla classe; 0 se non ne prepara. I sempre preparati sono fuori da questo numero."""
    row = next((c for c in char.classes if row_class_key(c) == class_key), None)
    if edition == "2024":
        if class_key in ("fighter", "rogue") and getattr(row, "subclass_key", None) not in THIRD_SUBCLASSES:
            return 0
        table = _PREPARED_2024.get(class_key)
        return _at_level(table, level) if table else 0
    if class_key not in PREPARING_CLASSES:
        return 0
    ability = getattr(row, "spellcasting_ability", None) or PREPARING_CLASSES[class_key][0]
    return compute_prepared_cap([_Row(class_key, level, ability)], {ability: effective_ability_mod(char, ability)}) or 0


# sottoclasse -> (scuole ammesse, livelli di classe a cui un incantesimo conosciuto può essere di qualsiasi scuola)
_SCHOOL_RESTRICTED: dict[str, tuple[tuple[str, ...], tuple[int, ...]]] = {
    "eldritch_knight": (("abjuration", "evocation"), (3, 8, 14, 20)),
    "arcane_trickster": (("enchantment", "illusion"), (3, 8, 14, 20)),
}
@dataclass(frozen=True)
class SchoolLimit:
    names: tuple[str, ...]  # scuole ammesse
    free: int  # incantesimi conosciuti che possono essere di un'altra scuola


def school_limit(edition: Edition, row: Any) -> SchoolLimit | None:
    """Limite di scuola degli incantesimi conosciuti (Cavaliere Mistico e Mistificatore Arcano 2014): quasi tutti di due
    scuole, e uno in più ai livelli 3, 8, 14 e 20 di qualsiasi scuola. Solo informativo, come gli altri limiti. ``None``: la classe non ne ha."""
    rule = _SCHOOL_RESTRICTED.get(getattr(row, "subclass_key", None)) if edition == "2014" else None
    if rule is None or row.level < min(rule[1]):
        return None
    return SchoolLimit(rule[0], sum(1 for level in rule[1] if row.level >= level))


def prepares(edition: Edition, row: Any, char: Any) -> bool:
    return prepared_limit(edition, row_class_key(row), row.level, char) > 0


def caster_ability(row: Any) -> str:
    """Caratteristica da incantatore; il terzo incantatore scelto dal catalogo non l'ha salvata: Intelligenza."""
    stored = (row.spellcasting_ability or "").strip().lower()
    return stored or ("intelligence" if getattr(row, "subclass_key", None) in THIRD_SUBCLASSES else "")


def caster_stats(char: Any) -> list[CasterStats]:
    out: list[CasterStats] = []
    edition = character_edition(char)
    pb = char.proficiency_bonus
    for row in char.classes:
        ability = caster_ability(row)
        if not ability:
            continue
        # Una classe del catalogo che nella sua edizione non lancia (Guerriero 2024 Campione) non è un incantatore,
        # anche con una caratteristica salvata; una classe custom conserva la propria.
        if normalize_class_name(row.class_name) is not None and caster_kind(row, edition) is None:
            continue
        mod = effective_ability_mod(char, ability)
        innate = 1 if edition == "2024" and row_class_key(row) == "sorcerer" and has_state(char, "innate_sorcery") else 0  # Stregoneria Innata
        out.append(CasterStats(row.id, row.class_name, ability, 8 + pb + mod + innate + item_bonus_total(char.items, "spell_dc"),
                               pb + mod + item_bonus_total(char.items, "spell_attack")))
    return out


def best_caster(char: Any) -> CasterStats | None:
    """Bonus di attacco più alto, il primo in caso di parità."""
    best: CasterStats | None = None
    for stats in caster_stats(char):
        if best is None or stats.attack_bonus > best.attack_bonus:
            best = stats
    return best


def spell_stats(char: Any, spell: Any) -> CasterStats | None:
    """CD e attacco della classe dell'incantesimo; non assegnato (personaggi esistenti): la classe migliore."""
    own = next((s for s in caster_stats(char) if s.class_id == spell.class_id), None)
    return own or best_caster(char)


def concentration_dc(edition: Edition, damage: int) -> int:
    dc = max(10, damage // 2)
    return min(dc, 30) if edition == "2024" else dc


# shortcut: il talento 2014 non è nel catalogo, si riconosce dal nome anche se scritto a mano; da togliere se ci entra.
_RITUAL_FEAT_NAMES = {"incantatore rituale", "ritual caster"}


def _has_ritual_feat(char: Any) -> bool:
    return any(a.feature_key == "feat.ritual_caster" or (a.name or "").strip().lower() in _RITUAL_FEAT_NAMES
               for a in char.abilities)


def granted_ritual_only(char: Any, spell: Any) -> bool:
    """L'incantesimo è stato concesso da un privilegio che lo permette solo come rituale (Cercatore di Spiriti), alla
    classe a cui è assegnato: chi lo ha da un'altra fonte (o da un'altra classe) lo lancia come tutti gli altri."""
    return any(spell.srd_index == key and spec.granted_ritual_only and spell.class_id == row.id
               for spec, row in active_features(char) for key in spec.granted_spells if key in GRANTED_SPELLS)


def _book_rituals(char: Any, spell: Any) -> bool:
    """Libro degli Antichi Segreti: i rituali della classe (quelli del Libro e quelli conosciuti) si lanciano come rituale.
    Senza incantesimo: la classe ha il privilegio."""
    return any(spec.ritual_casting and (spell is None or spell.class_id in (None, row.id))
               for spec, row in active_features(char))


def spell_range_override(char: Any, spell: Any) -> str | None:
    """Gittata che un privilegio dà a questo incantesimo (Lancia Occulta: 90 m per deflagrazione occulta)."""
    names = {str(getattr(spell, "srd_index", None) or "").lower(), str(getattr(spell, "name", None) or "").strip().lower()} - {""}
    fixed = next((spec.spell_range[1] for spec, _row in active_features(char)
                  if spec.spell_range and names & set(spec.spell_range[0])), None)
    if fixed is not None:
        return fixed
    return _per_level_range(char, spell, names) or _cantrip_range_bonus(char, spell) or _school_range(char, spell)


def school_boost_range(spell: Any, school: str, metres: int) -> str | None:
    """Illusioni Migliorate: la gittata di 3 m (10 ft) o più di un incantesimo della scuola cresce di ``metres`` (60 ft per 18 m)."""
    if normalize_school(getattr(spell, "school", None)) != school:
        return None
    found = _RANGE.match(getattr(spell, "range_area", None) or "")
    if not found:
        return None
    amount, unit = float(found.group(1).replace(",", ".")), found.group(2).lower()
    if amount < (3 if unit == "m" else 10):
        return None
    return f"{amount + (metres if unit == 'm' else metres * 10 / 3):g} {unit}{found.group(3)}"


def _school_range(char: Any, spell: Any) -> str | None:
    return next((r for spec, _row in active_features(char) if spec.school_boost
                 and (r := school_boost_range(spell, *spec.school_boost))), None)


def no_verbal(char: Any, spell: Any) -> bool:
    """Illusioni Migliorate: gli incantesimi di Illusione si lanciano senza componente Verbale."""
    school = normalize_school(getattr(spell, "school", None))
    return school is not None and any(spec.school_boost and spec.school_boost[0] == school for spec, _row in active_features(char))


_RANGE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*(m|ft)(?![a-z])(.*)$", re.IGNORECASE | re.DOTALL)


def _per_level_range(char: Any, spell: Any, names: set[str]) -> str | None:
    """Lancia Occulta 2024: 9 m (30 ft) per livello da warlock alla gittata di 3 m (10 ft) o piu del trucchetto scelto."""
    found = _RANGE.match(getattr(spell, "range_area", None) or "")
    if not found:
        return None
    amount, unit = float(found.group(1).replace(",", ".")), found.group(2).lower()
    for spec, row in active_features(char):
        if spec.spell_range_per_level and names & set(spec.spell_range_per_level[0]) and amount >= (3 if unit == "m" else 10):
            bonus = spec.spell_range_per_level[1] * row.level * (1 if unit == "m" else 10 / 3)
            return f"{amount + bonus:g} {unit}{found.group(3)}"
    return None


def _cantrip_range_bonus(char: Any, spell: Any) -> str | None:
    """Incantesimi Potenti (Druido 2024, 15°): un trucchetto della classe con gittata di 3 m (10 ft) o più guadagna 90 m (300 ft).
    Vale con le due unità e conserva ciò che segue la gittata (``18 m (sfera di 6 m)``)."""
    if getattr(spell, "level", None) != 0:
        return None
    found = _RANGE.match(getattr(spell, "range_area", None) or "")
    if not found:
        return None
    amount, unit = float(found.group(1).replace(",", ".")), found.group(2).lower()
    if amount < (3 if unit == "m" else 10):
        return None
    for spec, row in active_features(char):
        if spec.cantrip_range_bonus and (getattr(spell, "class_id", None) == row.id
                                         or (getattr(spell, "class_id", None) is None and len(char.classes) == 1)):
            bonus = spec.cantrip_range_bonus if unit == "m" else spec.cantrip_range_bonus * 10 // 3
            return f"{amount + bonus:g} {unit}{found.group(3)}"
    return None


def can_ritual(char: Any, spell: Any = None) -> bool:
    """2014: Lancio Rituale di classe o talento. 2024: chiunque abbia incantesimi preparati. Un incantesimo concesso
    come rituale si lancia anche senza."""
    edition = character_edition(char)
    if spell is not None and granted_ritual_only(char, spell):
        return True
    if _has_ritual_feat(char) or _book_rituals(char, spell):
        return True
    if edition == "2014":  # il Lancio Rituale è della classe a cui appartiene l'incantesimo, non di tutto il personaggio
        return has_ritual_caster(_spell_rows(char, spell))
    return any(caster_kind(c, edition) for c in char.classes)


def _spell_rows(char: Any, spell: Any) -> list[Any]:
    """Le classi a cui appartiene l'incantesimo; non assegnato (personaggi salvati prima): tutte."""
    return [c for c in char.classes if spell is not None and c.id == spell.class_id] or list(char.classes)


def _ritual_unprepared(char: Any, spell: Any) -> bool:
    if spell.is_prepared or spell.always_prepared:
        return False
    rows = _spell_rows(char, spell)
    if has_wizard(rows):  # dal libro (Lancio Rituale 2014, Adepto dei Rituali 2024)
        return not spell.in_spellbook
    if character_edition(char) == "2024":
        return True
    # 2014: chi non prepara li conosce, il talento ha un suo libro.
    return not _has_ritual_feat(char) and any(row_class_key(c) in ("cleric", "druid") for c in rows)


def bonus_cast(char: Any, spell: Any) -> bool:
    """Un privilegio fa lanciare questo incantesimo con un'azione bonus (Rompi-Incantesimi: Dissolvi Magie)."""
    key = getattr(spell, "srd_index", None)
    return bool(key) and any(key in spec.bonus_cast_spells for spec, _row in active_features(char))


def casting_kind(spell: Any) -> str:
    text = (spell.casting_time or "").lower()
    if "bonus" in text:
        return "bonus"
    return "reaction" if "reazion" in text or "reaction" in text else "action"


def _armor_block(char: Any) -> bool:
    kinds = ("armor", "shield") if character_edition(char) == "2014" else ("armor",)  # 2024: lo scudo toglie solo la CA
    return any(i.is_equipped and i.item_type in kinds and not is_armor_proficient(char, i) for i in char.items)


def _form_block(char: Any, spell: Any = None) -> bool:
    """In Forma Selvatica non si lanciano incantesimi, salvo un privilegio che lo consente (Incantesimi Bestiali) o che
    concede proprio questo (Incantesimi del Circolo della Luna)."""
    index = getattr(spell, "srd_index", None)
    return (any(s.get("key") == "wild_shape" for s in char.active_states or [])
            and not any(spec.cast_in_form or (index and index in spec.cast_in_form_spells) for spec, _row in active_features(char)))


def at_will(char: Any, spell: Any) -> bool:
    """Un privilegio attivo concede l'incantesimo a volontà: si lancia senza slot, tutte le volte che si vuole. La Maestria
    negli Incantesimi lo concede per quelli scelti, finché sono preparati."""
    key = getattr(spell, "srd_index", None)
    if key and any(key in spec.at_will_spells for spec, _row in active_features(char)):
        return True
    names = {n for n in (key, getattr(spell, "name", None)) if n}
    return bool(getattr(spell, "is_prepared", False)) and any(
        names & set((row.options or {}).get(group) or []) for spec, row in active_features(char) for group in spec.mastery_groups)


_MATERIAL = re.compile(r"^M(?![A-Za-z])", re.IGNORECASE)


def _form_materials(char: Any, spell: Any) -> str | None:
    """Incantesimi Bestiali: in forma bestiale non si forniscono materiali. L'Arcidruido ignora quelli senza costo, ma l'app
    non sa se il materiale ne ha uno: glielo chiede."""
    if not any(s.get("key") == "wild_shape" for s in char.active_states or []):
        return None
    specs = [spec for spec, _row in active_features(char)]
    if not any(s.cast_in_form for s in specs):
        return None
    tokens = [t.strip() for t in (spell.components or "").replace(";", ",").split(",")]
    if not any(_MATERIAL.match(t) for t in tokens):
        return None
    return "form_materials_cost" if any(s.ignores_components for s in specs) else "form_materials"


def _turn_warning(char: Any, spell: Any) -> str | None:
    kind = casting_kind(spell)
    if kind == "reaction":  # può cadere nel turno di un altro: il turno salvato non dice nulla
        return None
    turn = char.turn_state or {}
    if character_edition(char) == "2024":
        free = free_cast_state(char, spell)  # lancio senza slot che fa parte di un'altra azione (Magia Stregata): niente secondo slot
        if free is not None and (free.get("data") or {}).get("free_cast_slot", "action") is None:
            return None
        return "one_slot_per_turn" if spell.level > 0 and turn.get("spell_slot_cast") else None
    if kind == "bonus":
        return "bonus_spell" if turn.get("spell_slot_cast") or turn.get("bonus_spell_cast") else None
    return "bonus_spell" if spell.level > 0 and turn.get("bonus_spell_cast") else None


def cast_warnings(char: Any, spell: Any, ritual: bool) -> list[str]:
    """Regole che il lancio viola: il giocatore le conferma, perché l'app non vede eccezioni e privilegi futuri."""
    out = ["armor"] if _armor_block(char) else []
    if _form_block(char, spell):
        out.append("wild_shape")
    elif (materials := _form_materials(char, spell)) is not None:
        out.append(materials)
    if casting_blocked_by(char):
        out.append("state_blocks_casting")
    if not ritual and spell.level > 0 and granted_ritual_only(char, spell):
        out.append("ritual_only")
    if ritual:
        return [*out, "ritual_unprepared"] if _ritual_unprepared(char, spell) else out
    warning = _turn_warning(char, spell)
    return [*out, warning] if warning else out


# --- Lanci col ki (Arti dell'Ombra, discipline dei Quattro Elementi) ------------------------------------------------

def ki_spell_cap(level: int) -> int | None:
    """Massimo di punti ki per un solo incantesimo, costo base incluso: 3 dal 5° livello di monaco, 4 al 9°, 5 al 13°, 6 al 17°."""
    caps = [(17, 6), (13, 5), (9, 4), (5, 3)]
    return next((cap for lv, cap in caps if level >= lv), None)


@dataclass(frozen=True)
class KiCast:
    """Come un incantesimo si lancia coi punti: costo base, punti in più ammessi (0 se l'incantesimo non si alza), punti rimasti
    nella riserva, la riga ``Ability`` della riserva e la CD del ki."""
    feature_key: str
    pool: str
    cost: int
    max_extra: int
    ki_left: int
    dc: int
    upcast: bool
    self_only: bool = False


def ki_cast_info(char: Any, spell: Any) -> KiCast | None:
    key = getattr(spell, "srd_index", None)
    if not key:
        return None
    for spec, row in active_features(char):
        for ks in spec.ki_spells:
            if ks.spell != key:
                continue
            pool = next((a for a in char.abilities if a.feature_key == ks.pool), None)
            if pool is None or pool.max_uses is None:
                return None
            left = pool.uses or 0
            cap = ki_spell_cap(row.level) if ks.upcast else None
            extra = max(0, min(cap - ks.cost, left - ks.cost)) if cap is not None else 0
            dc = 8 + char.proficiency_bonus + effective_ability_mod(char, "wisdom")
            return KiCast(spec.key, ks.pool, ks.cost, extra, left, dc, ks.upcast, ks.self_only)
    return None
