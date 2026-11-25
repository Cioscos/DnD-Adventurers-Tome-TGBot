"""Ciò che un privilegio delle scuole del Mago 2014 fa quando si lancia un incantesimo della sua scuola.

``after_cast`` gira dentro il lancio (sincrono, sulla scheda già caricata): crea o ricarica l'Interdizione Arcana, ricarica
la Trasposizione Benevola e apre le finestre di Alterare Ricordi, Illusioni Duttili, Realtà Illusoria e Pietra del
Trasmutatore, che i rispettivi usi controllano, e segna il lancio per la Saturazione Magica (un uso per lancio).
"""
from __future__ import annotations

from typing import Any, Callable

from core.game.actions import parse_duration_rounds
from core.rules import arcane_ward
from core.rules.catalog import active_features
from core.rules.edition import character_edition
from core.rules.schools import (
    WINDOW_ENCHANTMENT, WINDOW_ILLUSION, WINDOW_ILLUSION_TURN, WINDOW_TRANSMUTATION, normalize_school,
)
from core.rules.slot_concentration import slot_concentration
from core.rules.states import begin_state
from core.rules.types import FeatureSpec, StateSpec

def _ward(char: Any, row: Any, spec: FeatureSpec, spell: Any, school: str | None, level: int | None) -> None:
    if school != "abjuration" or not level:
        return

    def begin(hp: int, maximum: int) -> None:
        begin_state(char, StateSpec(arcane_ward.KEY, ends_on=("rest_long",), data={"hp": hp, "max": maximum, "locked": True}), spec.key, spec.name["it"])
    arcane_ward.on_abjuration(char, row, level, begin)


def _transposition(char: Any, row: Any, spec: FeatureSpec, spell: Any, school: str | None, level: int | None) -> None:
    """Un'evocazione di 1° livello o superiore ricarica la Trasposizione Benevola."""
    if school != "conjuration" or not level:
        return
    ability = next((a for a in char.abilities if a.feature_key == spec.key and a.source_class_id == row.id), None)
    if ability is not None and ability.max_uses is not None:
        ability.uses = ability.max_uses


def _window(key: str, school: str, rounds_of: Callable[[Any], int | None] | None = None, ends_on: tuple[str, ...] = ("cast", "rest_long")):
    def hook(char: Any, row: Any, spec: FeatureSpec, spell: Any, found: str | None, level: int | None) -> None:
        if found != school or not level:
            return
        rounds = rounds_of(spell) if rounds_of else None
        begin_state(char, StateSpec(key, rounds=rounds, ends_on=ends_on, data={"internal": True, "spell": spell.name}), spec.key, spec.name["it"])
    return hook


def _enchantment_window(char: Any, row: Any, spec: FeatureSpec, spell: Any, found: str | None, level: int | None) -> None:
    """Alterare Ricordi: l'oblio si usa «prima che l'incantesimo termini» (2014 pag. 85), quindi la finestra dura quanto
    l'ammaliamento e un altro lancio non la chiude."""
    if found != "enchantment" or not level:
        return
    # shortcut: senza una durata in round/minuti/ore (istantanea, giorni) resta fino al riposo lungo; da legare alla fine reale se serve
    rounds, concentrates = _spell_lasts(char, spell, level)
    ends_on = ("rest_long", *(("concentration_end",) if concentrates else ()))
    begin_state(char, StateSpec(WINDOW_ENCHANTMENT, rounds=rounds, ends_on=ends_on,
                                data={"internal": True, "spell": spell.name}), spec.key, spec.name["it"])


def _reality_window(char: Any, row: Any, spec: FeatureSpec, spell: Any, found: str | None, level: int | None) -> None:
    """Realtà Illusoria: la finestra dura quanto l'incantesimo (anche nei turni seguenti); senza una durata in round, solo il turno."""
    if found != "illusion" or not level:
        return
    long, rounds = _long_illusion(char, spell, level)
    ends_on = (("rest_long", *(("concentration_end",) if _spell_lasts(char, spell, level)[1] else ())) if long
               else ("new_turn", "turn_end", "rest_long"))
    begin_state(char, StateSpec(WINDOW_ILLUSION_TURN, rounds=rounds, ends_on=ends_on, data={"internal": True, "spell": spell.name}),
                spec.key, spec.name["it"])


def _spell_lasts(char: Any, spell: Any, level: int | None) -> tuple[int | None, bool]:
    """Round dell'incantesimo lanciato a questo livello e se li tiene la concentrazione."""
    if spell.is_concentration:
        concentrates, rounds = slot_concentration(char, spell, level or spell.level)
        return rounds, concentrates
    return parse_duration_rounds(spell.duration), False


def _long_illusion(char: Any, spell: Any, level: int | None) -> tuple[bool, int | None]:
    """Se l'illusione dura almeno 1 minuto (10 round) e per quanti round: ``None`` quando lo slot la fa durare finché non è
    dissolta (Immagine Maggiore)."""
    rounds, concentrates = _spell_lasts(char, spell, level)
    if spell.is_concentration and not concentrates:
        return True, None
    return (True, rounds) if rounds and rounds >= 10 else (False, None)


def _overchannel_cast(char: Any, row: Any, spec: FeatureSpec, spell: Any, school: str | None, level: int | None) -> None:
    """Saturazione Magica: ogni lancio è un lancio nuovo, che conterà il suo uso (``level``: nel 2024 lo slot, ``None`` senza)."""
    from core.rules.catalog.y2014.wizard_schools_c import OVERCHANNEL_CAST  # import locale: il catalogo importa questo modulo
    char.turn_state = {**(char.turn_state or {}), OVERCHANNEL_CAST: {"spell": spell.id, "slot": level}}


def _illusion_window(char: Any, row: Any, spec: FeatureSpec, spell: Any, school: str | None, level: int | None) -> None:
    long, rounds = _long_illusion(char, spell, level)
    if school == "illusion" and long:
        begin_state(char, StateSpec(WINDOW_ILLUSION, rounds=rounds, ends_on=("rest_long",), data={"internal": True, "spell": spell.name}),
                    spec.key, spec.name["it"])


HOOKS: dict[str, Callable[..., None]] = {
    "wizard.arcane_ward": _ward,
    "wizard.benign_transposition": _transposition,
    "wizard.alter_memories": _enchantment_window,
    "wizard.malleable_illusions": _illusion_window,
    "wizard.illusory_reality": _reality_window,
    "wizard.transmuters_stone": _window(WINDOW_TRANSMUTATION, "transmutation"),
    "wizard.overchannel": _overchannel_cast,
}


def concentration_safe(char: Any) -> bool:
    """Il danno non fa tirare la concentrazione: l'incantesimo su cui il mago si concentra è di una scuola che un privilegio protegge
    (Evocazione Focalizzata)."""
    spell = next((s for s in char.spells or [] if s.id == char.concentrating_spell_id), None)
    school = normalize_school(spell.school) if spell is not None else None
    features = active_features(char)
    return (school is not None and any(school in spec.concentration_safe_schools for spec, _row in features)) or (
        spell is not None and any(spell.srd_index in spec.concentration_safe_spells for spec, _row in features))


def after_cast(char: Any, spell: Any, slot_level: int | None = None) -> None:
    """Hook dei privilegi attivi dopo un lancio; ognuno controlla il livello che gli serve (un trucchetto di illusione apre
    Illusioni Duttili, ma non crea un'interdizione). Il livello che conta è quello a cui si lancia nel 2014 (con uno slot
    superiore l'incantesimo ne assume il livello, pag. 201; il proprio se è un rituale o gratuito) e quello dello slot speso
    nel 2024 (``None`` se il lancio è un rituale o gratuito: «con uno slot»)."""
    from core.rules.spellcasting import spell_school  # import locale: spellcasting importa il catalogo come questo modulo
    school = spell_school(char, spell)
    level = max(spell.level, slot_level or 0) if character_edition(char) != "2024" else slot_level
    for spec, row in active_features(char):
        hook = HOOKS.get(spec.key)
        if hook is not None:
            hook(char, row, spec, spell, school, level)
