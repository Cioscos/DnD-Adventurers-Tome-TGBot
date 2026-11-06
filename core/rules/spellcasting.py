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
from core.rules.states import casting_blocked_by
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
# nomi italiani delle scuole (la scuola salvata è di solito lo slug inglese del compendio)
_SCHOOL_IT = {"abiurazione": "abjuration", "ammaliamento": "enchantment", "divinazione": "divination",
              "evocazione": "conjuration", "illusione": "illusion", "invocazione": "evocation",
              "necromanzia": "necromancy", "trasmutazione": "transmutation"}


@dataclass(frozen=True)
class SchoolLimit:
    names: tuple[str, ...]  # scuole ammesse
    free: int  # incantesimi conosciuti che possono essere di un'altra scuola


def normalize_school(value: str | None) -> str | None:
    text = (value or "").strip().lower()
    return _SCHOOL_IT.get(text, text) or None


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
        out.append(CasterStats(row.id, row.class_name, ability, 8 + pb + mod + item_bonus_total(char.items, "spell_dc"),
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


def can_ritual(char: Any, spell: Any = None) -> bool:
    """2014: Lancio Rituale di classe o talento. 2024: chiunque abbia incantesimi preparati. Un incantesimo concesso
    come rituale si lancia anche senza."""
    edition = character_edition(char)
    if spell is not None and granted_ritual_only(char, spell):
        return True
    if _has_ritual_feat(char):
        return True
    if edition == "2014":
        return has_ritual_caster(char.classes)
    return any(caster_kind(c, edition) for c in char.classes)


def _ritual_unprepared(char: Any, spell: Any) -> bool:
    if spell.is_prepared or spell.always_prepared:
        return False
    rows = [c for c in char.classes if c.id == spell.class_id] or list(char.classes)
    if has_wizard(rows):  # dal libro
        return False
    if character_edition(char) == "2024":
        return True
    # 2014: chi non prepara li conosce, il talento ha un suo libro.
    return not _has_ritual_feat(char) and any(row_class_key(c) in ("cleric", "druid") for c in rows)


def casting_kind(spell: Any) -> str:
    text = (spell.casting_time or "").lower()
    if "bonus" in text:
        return "bonus"
    return "reaction" if "reazion" in text or "reaction" in text else "action"


def _armor_block(char: Any) -> bool:
    kinds = ("armor", "shield") if character_edition(char) == "2014" else ("armor",)  # 2024: lo scudo toglie solo la CA
    return any(i.is_equipped and i.item_type in kinds and not is_armor_proficient(char, i) for i in char.items)


def _form_block(char: Any) -> bool:
    """In Forma Selvatica non si lanciano incantesimi, salvo un privilegio che lo consente (Incantesimi Bestiali)."""
    return (any(s.get("key") == "wild_shape" for s in char.active_states or [])
            and not any(spec.cast_in_form for spec, _row in active_features(char)))


def at_will(char: Any, spell: Any) -> bool:
    """Un privilegio attivo concede l'incantesimo a volontà: si lancia senza slot, tutte le volte che si vuole."""
    key = getattr(spell, "srd_index", None)
    return bool(key) and any(key in spec.at_will_spells for spec, _row in active_features(char))


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
        return "one_slot_per_turn" if spell.level > 0 and turn.get("spell_slot_cast") else None
    if kind == "bonus":
        return "bonus_spell" if turn.get("spell_slot_cast") or turn.get("bonus_spell_cast") else None
    return "bonus_spell" if spell.level > 0 and turn.get("bonus_spell_cast") else None


def cast_warnings(char: Any, spell: Any, ritual: bool) -> list[str]:
    """Regole che il lancio viola: il giocatore le conferma, perché l'app non vede eccezioni e privilegi futuri."""
    out = ["armor"] if _armor_block(char) else []
    if _form_block(char):
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
