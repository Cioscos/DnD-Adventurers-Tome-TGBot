"""Bardo 2024 e i suoi quattro Collegi: Danza, Incanto, Sapienza, Valore.

Valori dalla scheda ``docs/superpowers/rules/2024/classes/bard.md``; i testi sono nostri, mai quelli del manuale.
Il dado di Ispirazione e i meccanismi dell'alleato sono quelli del 2014 (R38): cambia la durata (un'ora) e la ricarica.
"""
from __future__ import annotations

from typing import Any

from core.rules.catalog._common import INCAPACITATING, feature, skill_label
from core.rules.catalog.y2024.bard_colleges import FEATURES as COLLEGE_FEATURES, note_inspiration_spent
from core.rules.catalog.y2014.bard import (
    BI, COMBAT_INSPIRATION, _expertise_options, _inspiration_row, _no_options, inspiration_die,
)
from core.rules.types import (
    BARDIC_DIE, ChoiceSpec, OnUse, RollOptionSpec, RuleContext, StateSpec, Uses, UseChoice,
)

ED, CK = "2024", "bard"
POWER_WORDS = ("power-word-heal", "power-word-kill")


def _both(it: str, en: str):
    return lambda _ctx, _params=None: {"it": it, "en": en}


def _subclass(ctx: RuleContext, key: str) -> bool:
    return getattr(ctx.class_row, "subclass_key", None) == key and ctx.class_level >= 3


def _incapacitated(char: Any) -> bool:
    return any((char.conditions or {}).get(c) for c in INCAPACITATING)


# ---------------------------------------------------------------------------
# Ispirazione Bardica e Fonte di Ispirazione
# ---------------------------------------------------------------------------

def _inspiration_state(ctx: RuleContext, params: dict) -> StateSpec:
    """Il dado dura un'ora (600 round): a un alleato della serata lo stato sta sul ricevente (R38), altrimenti resta sul
    bardo come promemoria per il gruppo (D1). Il Collegio del Valore aggiunge l'uso in combattimento."""
    valor = _subclass(ctx, "valor")
    data = {"die": inspiration_die(ctx.class_level), "others": [BI, COMBAT_INSPIRATION] if valor else [BI]}
    if params.get("target_character_id") is None:
        return StateSpec("bardic_inspiration", rounds=600, data=data)
    return StateSpec(BARDIC_DIE, rounds=600, data={**data, "combat": valor})


def _inspiration_spent(ctx: RuleContext, _params: dict) -> None:
    """Un uso di Ispirazione speso in un'azione, azione bonus o reazione: il Collegio della Danza ne ricava un Colpo
    Senz'Armi (Colpi Agili)."""
    note_inspiration_spent(ctx)


def _font_levels(ctx: RuleContext) -> list[str]:
    return [str(level) for level in sorted({s.level for s in ctx.char.spell_slots or [] if s.available > 0})]


def _font_available(ctx: RuleContext) -> bool:
    row = _inspiration_row(ctx.char)
    return row is not None and row.max_uses is not None and (row.uses or 0) < row.max_uses


def _font_regain(ctx: RuleContext, _params: dict) -> None:
    """Lo slot è già stato speso dal server (``spends_slot``): torna un uso di Ispirazione Bardica."""
    row = _inspiration_row(ctx.char)
    if row is not None and row.max_uses is not None:
        row.uses = min(row.max_uses, (row.uses or 0) + 1)


FONT_USE = OnUse(
    cost=0, spends_slot="slot_level", available=_font_available, effect=_font_regain,
    message=lambda _c, p: {"it": f"Slot di {p.get('slot_level')}° livello speso: recuperi un uso di Ispirazione Bardica.",
                           "en": f"Level {p.get('slot_level')} slot spent: you regain one use of Bardic Inspiration."},
    choices=(UseChoice("slot_level", {"it": "Slot da spendere", "en": "Slot to spend"}, _font_levels,
                       lambda level: {"it": f"Slot di {level}° livello", "en": f"Level {level} slot"}),))


# ---------------------------------------------------------------------------
# Controfascino, Ispirazione Superiore, Parole della Creazione
# ---------------------------------------------------------------------------

COUNTERCHARM_REROLL = RollOptionSpec(
    key=f"{CK}.countercharm", phase="after_roll", after="reroll", rolls=("save",), mode="advantage", slot="reaction",
    available=lambda c: not _incapacitated(c.char),
    label={"it": "Controfascino: il TS era contro Affascinato o Spaventato? Reazione, ripeti il TS con Vantaggio",
           "en": "Countercharm: was the save against being Charmed or Frightened? Reaction, repeat the save with Advantage"})

COUNTERCHARM_USE = OnUse(slot="reaction", message=_both(
    "Una creatura entro 9 m ha fallito il TS contro Affascinato o Spaventato: lo ripete con Vantaggio.",
    "A creature within 30 ft failed its save against Charmed or Frightened: it repeats the save with Advantage."))


def _superior_available(ctx: RuleContext) -> bool:
    row = _inspiration_row(ctx.char)
    return row is not None and row.max_uses is not None and (row.uses or 0) < min(2, row.max_uses)


def _superior_confirmed(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    row = _inspiration_row(ctx.char)
    if row is not None and row.max_uses is not None:
        row.uses = max(row.uses or 0, min(2, row.max_uses))


SUPERIOR_INSPIRATION = RollOptionSpec(
    key=f"{CK}.superior_inspiration", phase="before", rolls=("initiative",), automatic=True,
    label={"it": "Ispirazione Superiore: gli usi di Ispirazione Bardica salgono a due",
           "en": "Superior Inspiration: Bardic Inspiration uses come back up to two"},
    available=_superior_available, on_confirm=_superior_confirmed)

WORDS_OF_CREATION = RollOptionSpec(
    key=f"{CK}.words_of_creation", phase="before", rolls=("cast",), automatic=True,
    available=lambda c: c.spell is not None and c.spell.srd_index in POWER_WORDS,
    label={"it": "Parole della Creazione: un secondo bersaglio", "en": "Words of Creation: a second target"},
    effect=_both("Puoi bersagliare anche una seconda creatura entro 3 m dal primo bersaglio.",
                 "You can also target a second creature within 10 ft of the first target."))


CLASS_FEATURES = (
    feature("core_traits", CK, ED, 1, "Tratti Base del Bardo / Core Bard Traits (Bardo 1, pag. 59)",
            ("Tratti Base del Bardo", "Core Bard Traits"),
            ("Dado Vita d8, TS Destrezza e Carisma, 3 abilità, armi semplici, armature leggere, 3 strumenti musicali.",
             "Hit die d8, Dexterity and Charisma saves, 3 skills, simple weapons, light armor, 3 musical instruments."),
            # PF, TS, armi, armature e abilità: api/routers/classes.py e core/rules/proficiencies.py; gli strumenti
            # musicali a scelta e l'equipaggiamento A/B no (R32, R40)
            no_row=True, covered_by="lavori-successivi"),
    feature("bardic_inspiration", CK, ED, 1, "Ispirazione Bardica / Bardic Inspiration (Bardo 1, pag. 59)",
            ("Ispirazione Bardica", "Bardic Inspiration"),
            ("Azione bonus: una creatura entro 18 m riceve un dado (d6, d8, d10, d12) per 1 ora; se fallisce un Test d20 lo tira e lo somma.",
             "Bonus action: a creature within 60 ft gets a die (d6, d8, d10, d12) for 1 hour; if it fails a d20 Test it rolls and adds it."),
            "bonus_action", uses=Uses(ability="charisma", minimum=1), restoration={1: "long_rest", 5: "short_rest"},
            on_use=OnUse(slot="bonus", state=_inspiration_state, ally_state=True, effect=_inspiration_spent)),
    feature("spellcasting", CK, ED, 1, "Incantesimi / Spellcasting (Bardo 1, pag. 59)", ("Incantesimi", "Spellcasting"),
            ("Carisma; trucchetti 2/3/4 e incantesimi preparati da 4 a 22; slot da tabella; strumento musicale come focus.",
             "Charisma; cantrips 2/3/4 and prepared spells from 4 to 22; slots by table; an instrument as focus."),
            no_row=True, covered_by="core/rules/spellcasting.py (prepared_limit, known_limits, slots_for); "
                                    "test_cantrips_and_prepared_spells_follow_the_2024_table"),
    feature("expertise", CK, ED, 2, "Maestria / Expertise (Bardo 2, pag. 60)", ("Maestria", "Expertise"),
            ("Al 2° e al 9° livello due abilità già competenti passano a maestria (doppia competenza).",
             "At levels 2 and 9 two skills you are already proficient in gain expertise (double proficiency)."),
            choices=(ChoiceSpec(group="expertise", levels={2: 2, 9: 4}, options=_expertise_options,
                                label=skill_label, grants="expert"),)),
    feature("jack_of_all_trades", CK, ED, 2, "Factotum / Jack of All Trades (Bardo 2, pag. 60)",
            ("Factotum", "Jack of All Trades"),
            ("Metà competenza (per difetto) alle prove con un'abilità senza competenza; non alle prove pure né all'iniziativa.",
             "Half proficiency (rounded down) on checks with a skill you lack; not on plain checks or initiative."),
            # Le abilità e le passive le somma `skill_proficiency_part` (core/game/skills.py), una volta sola (R26)
            ),
    feature("bard_subclass", CK, ED, 3, "Sottoclasse del Bardo / Bard Subclass (Bardo 3, pag. 60)",
            ("Sottoclasse del Bardo", "Bard Subclass"),
            ("Al 3° livello si sceglie il Collegio della Danza, dell'Incanto, della Sapienza o del Valore.",
             "At level 3 you choose the College of Dance, Glamour, Lore or Valor."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("ability_score_improvement", CK, ED, 4,
            "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Bardo 4, pag. 61)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 12 e 16 il talento Aumento dei Punteggi o un altro talento di cui hai i requisiti.",
             "At levels 4, 8, 12 and 16 the Ability Score Improvement feat or another feat you qualify for."),
            no_row=True, covered_by="core/rules/level_choices.py (scelta asi); test_asi_choice_is_pending_at_each_asi_level_and_the_19th_is_an_epic_boon"),
    feature("font_of_inspiration", CK, ED, 5, "Fonte di Ispirazione / Font of Inspiration (Bardo 5, pag. 61)",
            ("Fonte di Ispirazione", "Font of Inspiration"),
            ("Gli usi di Ispirazione Bardica tornano anche con un riposo breve. Senza azione, spendi uno slot per recuperare un uso.",
             "Bardic Inspiration uses also return on a short rest. With no action, spend a slot to regain one use."),
            on_use=FONT_USE),
    feature("countercharm", CK, ED, 7, "Controfascino / Countercharm (Bardo 7, pag. 61)", ("Controfascino", "Countercharm"),
            ("Reazione: tu o una creatura entro 9 m fallite un TS contro Affascinato o Spaventato; il TS si ripete con Vantaggio.",
             "Reaction: you or a creature within 30 ft fail a save against Charmed or Frightened; the save is repeated with Advantage."),
            "reaction", roll_options=(COUNTERCHARM_REROLL,), on_use=COUNTERCHARM_USE),
    feature("magical_secrets", CK, ED, 10, "Segreti Magici / Magical Secrets (Bardo 10, pag. 61)",
            ("Segreti Magici", "Magical Secrets"),
            ("I nuovi incantesimi preparati dal 10° livello possono venire dalle liste di Bardo, Chierico, Druido e Mago e contano da bardo.",
             "From level 10 the new prepared spells can come from the Bard, Cleric, Druid and Wizard lists and count as bard spells."),
            choices=(ChoiceSpec(group="magical_secrets", levels={10: 1, 11: 2, 13: 3, 15: 4, 17: 5, 18: 6, 19: 7, 20: 8},
                                options=_no_options, spell_pick="known"),)),
    feature("superior_inspiration", CK, ED, 18, "Ispirazione Superiore / Superior Inspiration (Bardo 18, pag. 61)",
            ("Ispirazione Superiore", "Superior Inspiration"),
            ("Quando tiri l'Iniziativa, se hai meno di due usi di Ispirazione Bardica ne recuperi fino ad averne due.",
             "When you roll Initiative, if you have fewer than two Bardic Inspiration uses you regain uses up to two."),
            roll_options=(SUPERIOR_INSPIRATION,), passive=True),
    feature("epic_boon", CK, ED, 19, "Dono Epico / Epic Boon (Bardo 19, pag. 61)", ("Dono Epico", "Epic Boon"),
            ("Al 19° livello un talento Dono Epico o un altro talento di cui hai i requisiti.",
             "At level 19 an Epic Boon feat or another feat you qualify for."),
            no_row=True, covered_by="core/rules/level_choices.py (reconcile_choices, scelta epic_boon)"),
    feature("words_of_creation", CK, ED, 20, "Parole della Creazione / Words of Creation (Bardo 20, pag. 61)",
            ("Parole della Creazione", "Words of Creation"),
            ("Parola del Potere: Guarigione e Uccisione sono sempre preparate; puoi bersagliare una seconda creatura entro 3 m.",
             "Power Word Heal and Power Word Kill are always prepared; you can target a second creature within 10 ft."),
            granted_spells=POWER_WORDS, roll_options=(WORDS_OF_CREATION,), passive=True),
    feature("multiclassing", CK, ED, 1, "Multiclasse: Bardo / Multiclassing: Bard (Capitolo 2, pag. 44)",
            ("Multiclasse: Bardo", "Multiclassing: Bard"),
            ("Requisito Carisma 13. Da multiclasse: 1 abilità, 1 strumento musicale, armature leggere.",
             "Requires Charisma 13. As a multiclass: 1 skill, 1 musical instrument, light armor."),
            # Armatura leggera, 1 abilità e requisito Carisma 13: core/rules/proficiencies.py (as_multiclass) e
            # webapp/src/data/multiclassPrereqs.ts (D2). Lo strumento a scelta no (R40).
            no_row=True, covered_by="lavori-successivi"),
)

# I privilegi dei Collegi vengono prima: le abilità di Competenze Bonus (Sapienza) servono a Maestria (R39)
FEATURES = COLLEGE_FEATURES + CLASS_FEATURES
