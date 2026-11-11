"""Mago 2024, parte A (base della classe). Le sottoclassi (Abiuratore, Divinatore, Invocatore, Illusionista) sono la parte B, in
``wizard_subclasses.py``: le loro righe vanno in ``SUBCLASS_ROWS`` con ``subclass=`` (abjurer, diviner, evoker, illusionist).

Valori dalla scheda ``docs/superpowers/rules/2024/classes/wizard.md``; i testi sono nostri, mai quelli del manuale. Il Libro degli
Incantesimi è quello del 2014 (``Spell.in_spellbook``, ``core/rules/spellbook.py``, copia e libro perso in ``api/routers/spells.py``):
gli incantesimi del libro sono la scelta di livello ``spellbook`` (sei al 1°, due per livello). Recupero Arcano ha la chiave legacy del
2014 e passa da ``arcane_recovery`` in ``POST /rest``; Memorizzare Incantesimo da ``memorize_spell`` (``api/services/memorize.py``).
Per la parte B: ``BOOK_GROUP`` è il gruppo del libro; le righe «Sapiente» aggiungono incantesimi al libro.
"""
from __future__ import annotations

from core.game.actions import parse_casting_time
from core.rules.catalog._common import feature, skill_label
from core.rules.catalog.y2014.bard import _expertise_options
from core.rules.catalog.y2014.wizard import (
    BOOK_GROUP, MASTERY_GROUPS, SIGNATURE_GROUPS, _BOOK_LEVELS, _name_label, _no_options,
)
from core.rules.types import ChoiceSpec, RuleContext, Uses

ED, CK = "2024", "wizard"
SCHOLAR_SKILLS = ("arcana", "history", "investigation", "medicine", "nature", "religion")


def _scholar_options(ctx: RuleContext) -> list[str]:
    return [s for s in _expertise_options(ctx) if s in SCHOLAR_SKILLS]


def _book_spells(level: int, groups: tuple[str, ...], one_action: bool = False):
    """Incantesimi del libro di ``level`` non ancora scelti nei ``groups``; con ``one_action`` solo quelli di 1 azione (Maestria)."""
    def options(ctx: RuleContext) -> list[str]:
        from core.rules.spellbook import wizard_row  # import locale: spellbook usa il catalogo
        taken = {k for g in groups for k in (getattr(ctx.class_row, "options", None) or {}).get(g, [])}
        return sorted(s.name for s in ctx.char.spells or []
                      if s.level == level and s.in_spellbook and wizard_row(ctx.char, s) is ctx.class_row and s.name not in taken
                      and (not one_action or parse_casting_time(s.casting_time) == "action"))
    return options


def _mastery(n: int, level: int) -> ChoiceSpec:
    return ChoiceSpec(group=MASTERY_GROUPS[n], levels={18: 1}, options=_book_spells(level, (MASTERY_GROUPS[n],), one_action=True),
                      replaceable=True, replace_per_long_rest=True, label=_name_label, always_prepared=True)


def _signature(n: int) -> ChoiceSpec:
    return ChoiceSpec(group=SIGNATURE_GROUPS[n], levels={20: 1}, options=_book_spells(3, SIGNATURE_GROUPS), label=_name_label,
                      always_prepared=True)


_BOOK_ROWS = "core/rules/spellbook.py e api/routers/spells.py (copy_spell_to_book, lose_spellbook, spellbook_cost)"

BASE_ROWS = (
    feature("core_traits", CK, ED, 1, "Tratti Base del Mago / Core Wizard Traits (Mago 1, pag. 165)",
            ("Tratti Base del Mago", "Core Wizard Traits"),
            ("Dado vita d6, TS Intelligenza e Saggezza, 2 abilità su 7, armi semplici, nessuna armatura. Multiclasse: solo il dado vita.",
             "Hit die d6, Intelligence and Wisdom saves, 2 skills out of 7, simple weapons, no armor. Multiclass: the hit die only."),
            no_row=True, covered_by="core/rules/proficiencies.py (class_proficiencies, as_multiclass), api/routers/classes.py; "
                                    "test_hit_points_use_the_d6, test_class_and_multiclass_proficiencies; equipaggiamento di partenza: lavori-successivi"),
    feature("spellcasting", CK, ED, 1, "Incantesimi / Spellcasting (Mago 1, pag. 165)", ("Incantesimi", "Spellcasting"),
            ("Intelligenza; trucchetti 3 (4 al 4°, 5 al 10°); preparati dalla tabella (4 a 25) fra gli incantesimi del libro, di un livello con slot.",
             "Intelligence; cantrips 3 (4 at 4th, 5 at 10th); prepared from the table (4 to 25) among the book's spells, of a level with slots."),
            no_row=True, covered_by="core/rules/spellcasting.py (known_limits, prepared_limit, slots_for), core/rules/spellbook.py (prepare_refusal); "
                                    "test_slots_cantrips_and_prepared_follow_the_table"),
    feature("spellbook", CK, ED, 1, "Libro degli Incantesimi / Spellbook (Mago 1, pag. 165)", ("Libro degli Incantesimi", "Spellbook"),
            ("Sei incantesimi di 1° livello e due per livello da mago. Copiarne uno costa 2 ore e 50 mo per livello; da libro a libro 1 ora e 10 mo.",
             "Six 1st-level spells and two per wizard level. Copying one costs 2 hours and 50 gp per level; book to book 1 hour and 10 gp."),
            no_row=True, covered_by=f"{_BOOK_ROWS} e la ChoiceSpec spellbook di questa riga",
            choices=(ChoiceSpec(group=BOOK_GROUP, levels=_BOOK_LEVELS, options=_no_options, spell_pick="book", spell_list="wizard"),)),
    feature("expanding_spellbook", CK, ED, 1,
            "Espandere e Sostituire il Libro degli Incantesimi / Expanding and Replacing a Spellbook (Mago 1, pag. 167)",
            ("Espandere e Sostituire il Libro", "Expanding and Replacing a Spellbook"),
            ("Stessa trascrizione del libro: tempo e monete scalati dall'app. A libro perso si ritrascrivono gli incantesimi preparati.",
             "Same transcription as the book: time and coins handled by the app. With a lost book you transcribe the prepared spells again."),
            no_row=True, covered_by=f"{_BOOK_ROWS}; test_a_lost_book_is_rewritten_only_for_prepared_spells"),
    feature("ritual_adept", CK, ED, 1, "Adepto dei Rituali / Ritual Adept (Mago 1, pag. 166)", ("Adepto dei Rituali", "Ritual Adept"),
            ("Lanci come rituale ogni incantesimo rituale del libro, anche se non è preparato.",
             "You cast as a ritual any ritual spell in the book, even if it is not prepared."),
            no_row=True, covered_by="core/rules/spellcasting.py (can_ritual, _ritual_unprepared); "
                                    "test_a_book_ritual_is_cast_unprepared_but_one_outside_the_book_is_not"),
    feature("arcane_recovery", CK, ED, 1, "Recupero Arcano / Arcane Recovery (Mago 1, pag. 166)", ("Recupero Arcano", "Arcane Recovery"),
            ("A fine riposo breve recuperi slot spesi per un livello totale fino a metà del livello da mago (per eccesso), nessuno di 6° o più. Una volta.",
             "At the end of a short rest you regain spent slots totaling up to half your wizard level (rounded up), none of 6th or higher. Once."),
            "special", uses=Uses(table={1: 1}), restoration="long_rest", passive=False),  # si usa nel riposo breve (POST /rest)
    feature("scholar", CK, ED, 2, "Studioso / Scholar (Mago 2, pag. 166)", ("Studioso", "Scholar"),
            ("Maestria in una abilità fra Arcano, Storia, Indagare, Medicina, Natura e Religione in cui sei già competente.",
             "Expertise in one skill among Arcana, History, Investigation, Medicine, Nature and Religion that you are already proficient in."),
            no_row=True, covered_by="la ChoiceSpec scholar di questa riga (grants expert); test_scholar_offers_only_the_six_skills_the_wizard_is_proficient_in_and_sets_expertise",
            choices=(ChoiceSpec(group="scholar", levels={2: 1}, options=_scholar_options, label=skill_label, grants="expert"),)),
    feature("wizard_subclass", CK, ED, 3, "Sottoclasse del Mago / Wizard Subclass (Mago 3, pag. 167)", ("Sottoclasse del Mago", "Wizard Subclass"),
            ("Al 3° livello si sceglie Abiuratore, Divinatore, Invocatore o Illusionista: privilegi ai livelli 3, 6, 10 e 14.",
             "At level 3 you choose Abjurer, Diviner, Evoker or Illusionist: features at levels 3, 6, 10 and 14."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("ability_score_improvement", CK, ED, 4, "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Mago 4, pag. 167)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 12 e 16: il talento Aumento dei Punteggi o un altro talento di cui hai i requisiti.",
             "At levels 4, 8, 12 and 16: the Ability Score Improvement feat or another feat you qualify for."),
            no_row=True, covered_by="core/rules/level_choices.py (scelta asi); test_asi_at_4_8_12_16_and_the_19th_is_an_epic_boon"),
    feature("memorize_spell", CK, ED, 5, "Memorizzare Incantesimo / Memorize Spell (Mago 5, pag. 167)", ("Memorizzare Incantesimo", "Memorize Spell"),
            ("A fine riposo breve scambi un incantesimo preparato (di 1° livello o più) con un altro del libro. Non vale per i sempre preparati.",
             "At the end of a short rest you swap a prepared spell (1st level or higher) for another from the book. Not for always-prepared spells.")),
    feature("spell_mastery", CK, ED, 18, "Maestria negli Incantesimi / Spell Mastery (Mago 18, pag. 167)",
            ("Maestria negli Incantesimi", "Spell Mastery"),
            ("Un incantesimo di 1° e uno di 2° livello del libro, di 1 azione: sempre preparati, li lanci al livello base senza slot. Cambio al riposo lungo.",
             "A 1st- and a 2nd-level book spell cast in 1 action: always prepared, cast at base level with no slot. Swappable on a long rest."),
            no_row=True, mastery_groups=MASTERY_GROUPS, choices=(_mastery(0, 1), _mastery(1, 2)),
            covered_by="at_will in core/rules/spellcasting.py (mastery_groups) e le due ChoiceSpec spell_mastery_1/2 di questa riga"),
    feature("epic_boon", CK, ED, 19, "Dono Epico / Epic Boon (Mago 19, pag. 167)", ("Dono Epico", "Epic Boon"),
            ("Al 19° livello un talento Dono Epico o un altro talento di cui hai i requisiti; consigliato Dono del Richiamo degli Incantesimi.",
             "At 19th level an Epic Boon feat or another feat you qualify for; Boon of Spell Recall is recommended."),
            no_row=True, covered_by="core/rules/level_choices.py (scelta epic_boon); test_asi_at_4_8_12_16_and_the_19th_is_an_epic_boon"),
    *(feature(f"signature_spell_{n + 1}", CK, ED, 20, "Incantesimi Personali / Signature Spells (Mago 20, pag. 167)",
              (f"Incantesimo Personale {n + 1}", f"Signature Spell {n + 1}"),
              ("Un incantesimo di 3° livello del libro, sempre preparato: lo lanci una volta senza slot, poi un riposo breve o lungo.",
               "A 3rd-level book spell, always prepared: cast it once with no slot, then a short or long rest."),
              uses=Uses(table={20: 1}), restoration="short_rest", arcanum_group=SIGNATURE_GROUPS[n], choices=(_signature(n),))
      for n in (0, 1)),
    feature("multiclassing", CK, ED, 1, "Multiclasse: Mago / Multiclassing: Wizard (Mago, pag. 44)", ("Multiclasse: Mago", "Multiclassing: Wizard"),
            ("Requisito Intelligenza 13. Da multiclasse: solo il dado vita d6; libro e preparati per classe, slot dalla tabella multiclasse.",
             "Requires Intelligence 13. As a multiclass: only the d6 hit die; book and prepared spells per class, slots from the multiclass table."),
            no_row=True, covered_by="core/rules/proficiencies.py (as_multiclass), webapp/src/data/multiclassPrereqs.ts (D2), "
                                    "core/rules/spellbook.py (wizard_row) e api/services/spellcasting.py (_class_limits); "
                                    "test_multiclass_prepares_per_class_with_the_2024_table"),
)

from core.rules.catalog.y2024.wizard_subclasses import SUBCLASS_ROWS  # noqa: E402  (parte B, dopo le definizioni comuni)

FEATURES = BASE_ROWS + SUBCLASS_ROWS
