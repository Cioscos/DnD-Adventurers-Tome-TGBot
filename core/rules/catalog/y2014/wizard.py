"""Mago 2014 e le sue otto scuole (Tradizione Arcana).

Valori dalla scheda ``docs/superpowers/rules/2014/classes/wizard.md``; i testi sono nostri, mai quelli del manuale.
Il Libro degli Incantesimi sta sugli incantesimi (``Spell.in_spellbook``, ``in_backup``): costi e rifiuti in
``core/rules/spellbook.py``, copia e libro perso in ``api/routers/spells.py``. Gli incantesimi del libro sono la scelta di
livello ``spellbook`` (due per livello); Maestria e Incantesimi Personali scelgono fra quelli del libro. Le scuole stanno
in ``wizard_schools.py``.
"""
from __future__ import annotations

from core.rules.catalog._common import feature
from core.rules.catalog.y2014 import wizard_schools, wizard_schools_b, wizard_schools_c, wizard_schools_d
from core.rules.types import ChoiceSpec, RuleContext, Uses

ED, CK = "2014", "wizard"
BOOK_GROUP = "spellbook"
MASTERY_GROUPS = ("spell_mastery_1", "spell_mastery_2")
SIGNATURE_GROUPS = ("signature_1", "signature_2")
RECOVERY = f"{CK}.arcane_recovery"  # chiave legacy di CLASS_RESOURCES (R17)


def _no_options(_ctx: RuleContext) -> list[str]:
    return []


def _book_spells(level: int, groups: tuple[str, ...]):
    """Nomi degli incantesimi del libro di ``level`` non ancora scelti in nessuno dei ``groups`` (Maestria, Personali)."""
    def options(ctx: RuleContext) -> list[str]:
        from core.rules.spellbook import wizard_row  # import locale: spellbook usa il catalogo
        taken = {k for g in groups for k in (getattr(ctx.class_row, "options", None) or {}).get(g, [])}
        return sorted(s.name for s in ctx.char.spells or []
                      if s.level == level and s.in_spellbook and wizard_row(ctx.char, s) is ctx.class_row and s.name not in taken)
    return options


def _name_label(key: str) -> dict:
    return {"name": {"it": key, "en": key}, "summary": {"it": "", "en": ""}}


def _mastery(n: int, level: int) -> ChoiceSpec:
    return ChoiceSpec(group=MASTERY_GROUPS[n], levels={18: 1}, options=_book_spells(level, (MASTERY_GROUPS[n],)), replaceable=True,
                      label=_name_label)


def _signature(n: int) -> ChoiceSpec:
    return ChoiceSpec(group=SIGNATURE_GROUPS[n], levels={20: 1}, options=_book_spells(3, SIGNATURE_GROUPS), label=_name_label,
                      always_prepared=True)


_BOOK_LEVELS = {1: 6, **{lv: 6 + 2 * (lv - 1) for lv in range(2, 21)}}  # sei al 1° livello, due per ogni livello da mago

FEATURES = (
    feature("hit_points", CK, ED, 1, "Punti Ferita e Competenze / Hit Points and Proficiencies (Mago 1, pag. 82)",
            ("Punti Ferita e Competenze", "Hit Points and Proficiencies"),
            ("Dado vita d6; TS Intelligenza e Saggezza; nessuna armatura; armi: balestre leggere, bastoni ferrati, dardi, fionde, pugnali.",
             "Hit die d6; Intelligence and Wisdom saves; no armor; weapons: light crossbows, quarterstaffs, darts, slings, daggers."),
            no_row=True, covered_by="core/data/classes.py (CLASS_HIT_DIE), core/rules/proficiencies.py (class_proficiencies) e la scelta "
                                    "ClassSkillChoice; total_base_hp in create_class_for_character"),
    feature("spellcasting", CK, ED, 1, "Incantesimi / Spellcasting (Mago 1, pag. 83)",
            ("Incantesimi", "Spellcasting"),
            ("Slot per livello dalla tabella del mago; Intelligenza è la caratteristica; si lancia con uno slot di livello pari o superiore.",
             "Spell slots by level from the wizard table; Intelligence is the ability; cast with a slot of the spell's level or higher."),
            no_row=True, covered_by="core/rules/spellcasting.py (slots_for, caster_stats) e api/routers/spells.py:_consume_cast"),
    feature("cantrips", CK, ED, 1, "Trucchetti / Cantrips (Mago 1, pag. 83)",
            ("Trucchetti", "Cantrips"),
            ("Conosci 3 trucchetti da mago, 4 al 4° livello e 5 al 10°. Non occupano il libro.",
             "You know 3 wizard cantrips, 4 at 4th level and 5 at 10th. They do not take up the book."),
            no_row=True, covered_by="core/rules/spellcasting.py (known_limits) e api/services/spellcasting.py (_class_limits)"),
    feature("spellbook", CK, ED, 1, "Libro degli Incantesimi / Spellbook (Mago 1, pag. 83)",
            ("Libro degli Incantesimi", "Spellbook"),
            ("Il libro contiene i tuoi incantesimi (non i trucchetti). Copiarne uno costa 2 ore e 50 mo per livello; la copia di riserva 1 ora e 10 mo.",
             "The book holds your spells (not cantrips). Copying one costs 2 hours and 50 gp per level; a backup copy 1 hour and 10 gp."),
            no_row=True, covered_by="core/rules/spellbook.py e api/routers/spells.py (copy_spell_to_book, lose_spellbook, spellbook_cost)"),
    feature("preparing_spells", CK, ED, 1, "Preparare e Lanciare Incantesimi / Preparing and Casting Spells (Mago 1, pag. 83)",
            ("Preparare e Lanciare Incantesimi", "Preparing and Casting Spells"),
            ("Prepari mod. Intelligenza + livello da mago incantesimi dal libro, di un livello per cui hai slot; la lista cambia dopo un riposo lungo.",
             "You prepare Intelligence modifier + wizard level spells from the book, of a level you have slots for; the list changes after a long rest."),
            no_row=True, covered_by="core/rules/spellbook.py (prepare_refusal), core/data/spellcasting.py (compute_prepared_cap) e "
                                    "api/routers/spells.py (update_spell)"),
    feature("spellcasting_ability", CK, ED, 1, "Caratteristica da Incantatore / Spellcasting Ability (Mago 1, pag. 83)",
            ("Caratteristica da Incantatore", "Spellcasting Ability"),
            ("CD dei TS = 8 + competenza + mod. Intelligenza; attacco con incantesimo = competenza + mod. Intelligenza.",
             "Save DC = 8 + proficiency + Intelligence modifier; spell attack = proficiency + Intelligence modifier."),
            no_row=True, covered_by="core/rules/spellcasting.py (caster_stats)"),
    feature("ritual_casting", CK, ED, 1, "Celebrare Rituali / Ritual Casting (Mago 1, pag. 83)",
            ("Celebrare Rituali", "Ritual Casting"),
            ("Lanci come rituale un incantesimo da mago del libro con il descrittore rituale, anche se non è preparato.",
             "You cast a wizard spell from the book that has the ritual tag as a ritual, even if it is not prepared."),
            no_row=True, covered_by="core/rules/spellcasting.py (can_ritual, _ritual_unprepared)"),
    feature("spellcasting_focus", CK, ED, 1, "Focus da Incantatore / Spellcasting Focus (Mago 1, pag. 83)",
            ("Focus da Incantatore", "Spellcasting Focus"),
            ("Puoi usare un focus arcano come focus da incantatore per i tuoi incantesimi da mago.",
             "You can use an arcane focus as a spellcasting focus for your wizard spells."),
            passive=True),
    feature("learning_spells", CK, ED, 1,
            "Imparare Incantesimi di 1° Livello e di Livello Superiore / Learning Spells of 1st Level and Higher (Mago 1, pag. 83)",
            ("Imparare Incantesimi", "Learning Spells"),
            ("Sei incantesimi nel libro al 1° livello e due gratis a ogni livello da mago, di un livello per cui hai slot.",
             "Six spells in the book at 1st level and two free at every wizard level, of a level you have slots for."),
            no_row=True, covered_by="ChoiceSpec spellbook di questa riga (spell_pick book)",
            choices=(ChoiceSpec(group=BOOK_GROUP, levels=_BOOK_LEVELS, options=_no_options, spell_pick="book", spell_list="wizard"),)),
    feature("arcane_recovery", CK, ED, 1, "Recupero Arcano / Arcane Recovery (Mago 1, pag. 84)",
            ("Recupero Arcano", "Arcane Recovery"),
            ("Durante un riposo breve recuperi slot spesi per un livello totale fino a metà del livello da mago (per eccesso), nessuno di 6° o più. Una volta al giorno.",
             "During a short rest you regain spent slots totaling up to half your wizard level (rounded up), none of 6th or higher. Once per day."),
            "special", uses=Uses(table={1: 1}), restoration="long_rest", passive=False),
    feature("arcane_tradition", CK, ED, 2, "Tradizione Arcana / Arcane Tradition (Mago 2, pag. 84)",
            ("Tradizione Arcana", "Arcane Tradition"),
            ("Al 2° livello scegli una delle otto scuole di magia; i suoi privilegi arrivano ai livelli 2, 6, 10 e 14.",
             "At 2nd level you choose one of the eight schools of magic; its features arrive at levels 2, 6, 10 and 14."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("ability_score_improvement", CK, ED, 4, "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Mago 4, pag. 84)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 12, 16 e 19: +2 a un punteggio o +1 a due, mai oltre 20.",
             "At levels 4, 8, 12, 16 and 19: +2 to one score or +1 to two, never above 20."),
            no_row=True, covered_by="core/rules/level_choices.py (sync_level_choices) e core/data/classes.py (ASI_LEVELS)"),
    feature("spell_mastery", CK, ED, 18, "Maestria negli Incantesimi / Spell Mastery (Mago 18, pag. 84)",
            ("Maestria negli Incantesimi", "Spell Mastery"),
            ("Scegli un incantesimo di 1° e uno di 2° livello dal libro: preparati, li lanci al livello base senza slot, a volontà.",
             "Pick a 1st-level and a 2nd-level spell from the book: while prepared, you cast them at base level with no slot, at will."),
            no_row=True, covered_by="at_will in core/rules/spellcasting.py (mastery_groups) e le due ChoiceSpec spell_mastery_1/2 di questa riga",
            mastery_groups=MASTERY_GROUPS, choices=(_mastery(0, 1), _mastery(1, 2))),
    *(feature(f"signature_spell_{n + 1}", CK, ED, 20, "Incantesimi Personali / Signature Spells (Mago 20, pag. 84)",
              (f"Incantesimo Personale {n + 1}", f"Signature Spell {n + 1}"),
              ("Un incantesimo di 3° livello del libro, sempre preparato e fuori dal limite: lo lanci una volta senza slot, poi un riposo breve o lungo.",
               "A 3rd-level spell from the book, always prepared and outside the limit: cast it once with no slot, then a short or long rest."),
              uses=Uses(table={20: 1}), restoration="short_rest", arcanum_group=SIGNATURE_GROUPS[n], choices=(_signature(n),))
      for n in (0, 1)),
    feature("multiclassing", CK, ED, 1, "Multiclasse: Mago / Multiclassing: Wizard (Manuale 2014, pag. 163)",
            ("Multiclasse: Mago", "Multiclassing: Wizard"),
            ("Requisito Intelligenza 13. Nessuna competenza. Libro e preparazione seguono i livelli da mago; gli slot sommano i livelli interi.",
             "Requires Intelligence 13. No proficiencies. Book and preparation follow wizard levels; spell slots add up full levels."),
            no_row=True, covered_by="core/rules/proficiencies.py (as_multiclass), webapp/src/data/multiclassPrereqs.ts (D2), "
                                    "core/rules/spellbook.py (wizard_row) e api/services/spellcasting.py (_class_limits)"),
    *wizard_schools.FEATURES,
    *wizard_schools_b.FEATURES,
    *wizard_schools_c.FEATURES,
    *wizard_schools_d.FEATURES,
)
