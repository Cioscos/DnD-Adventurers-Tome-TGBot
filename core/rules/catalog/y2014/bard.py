"""Bardo 2014 e i suoi collegi: Collegio della Sapienza e Collegio del Valore.

Valori dalla scheda ``docs/superpowers/rules/2014/classes/bard.md``; i testi sono nostri, mai quelli del manuale.
"""
from __future__ import annotations

from typing import Any

from core.data.skills import SKILLS
from core.rules.catalog._common import feature, skill_label, state_on
from core.rules.types import (
    BARDIC_DIE, ChoiceSpec, Cost, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, Uses,
)

ED, CK = "2014", "bard"
BI = f"{CK}.bardic_inspiration"
COMBAT_INSPIRATION = f"{CK}.combat_inspiration"
COUNTERCHARM = f"{CK}.countercharm"
ALL_SKILLS = [slug for slug, _ability in SKILLS]


def inspiration_die(level: int) -> int:
    """Taglia del dado di Ispirazione Bardica (anche di Parole Taglienti e Abilità Impareggiabile)."""
    return 6 if level < 5 else 8 if level < 10 else 10 if level < 15 else 12


def song_die(level: int) -> int:
    return 6 if level < 9 else 8 if level < 13 else 10 if level < 17 else 12


def _inspiration_formula(ctx: RuleContext) -> str:
    return f"1d{inspiration_die(ctx.class_level)}"


def _inspiration_state(ctx: RuleContext, params: dict) -> StateSpec:
    """Il dado dato a un'altra creatura: dieci minuti, uno solo per creatura (R38). Con un alleato della serata lo stato
    ``bardic_die`` sta sul ricevente, che lo spende dalla propria scheda; senza, resta sul bardo come promemoria per il
    gruppo (D1). Il Collegio del Valore aggiunge l'uso in combattimento."""
    valor = ctx.class_row.subclass_key == "valor" and ctx.class_level >= 3
    others = [BI, COMBAT_INSPIRATION] if valor else [BI]
    data = {"die": inspiration_die(ctx.class_level), "others": others}
    if params.get("target_character_id") is None:
        return StateSpec("bardic_inspiration", rounds=100, ends_on=("rest_short", "rest_long", "manual"), data=data)
    return StateSpec(BARDIC_DIE, rounds=100, ends_on=("rest_short", "rest_long", "manual"), data={**data, "combat": valor})


def _song_state(ctx: RuleContext, _params: dict) -> StateSpec:
    """Il Canto di Riposo dura finché il bardo si esibisce. Il riposo breve del bardo non lo chiude, altrimenti chi spende
    Dadi Vita dopo di lui perderebbe il dado: finisce al riposo lungo, a mano o al prossimo «Nuovo turno». Il dado extra
    lo legge `hit_dice/spend`."""
    return StateSpec("song_of_rest", ends_on=("rest_long", "new_turn", "manual"), data={"die": song_die(ctx.class_level)})


def _inspiration_row(char: Any) -> Any:
    return next((a for a in char.abilities if a.feature_key == BI), None)


def _superior_available(ctx: RuleContext) -> bool:
    row = _inspiration_row(ctx.char)
    return row is not None and row.max_uses is not None and (row.uses or 0) == 0


def _superior_confirmed(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    row = _inspiration_row(ctx.char)
    if row is not None and row.max_uses is not None:
        row.uses = min(row.max_uses, (row.uses or 0) + 1)


def _skill_proficient(ctx: RuleContext, skill: str) -> bool:
    return bool((ctx.char.skills or {}).get(skill))


def _expertise_options(ctx: RuleContext) -> list[str]:
    return [s for s in ALL_SKILLS if _skill_proficient(ctx, s) and (ctx.char.skills or {}).get(s) != "expert"]


def _untrained_skills(ctx: RuleContext) -> list[str]:
    return [s for s in ALL_SKILLS if not _skill_proficient(ctx, s)]


def _proficient_skills(ctx: RuleContext) -> list[str]:
    """Abilità già competenti: un Bardo salvato prima del catalogo le dichiara «già sulla scheda» (R39)."""
    return [s for s in ALL_SKILLS if _skill_proficient(ctx, s)]


def _no_options(_ctx: RuleContext) -> list[str]:
    return []


def _after_bard_action_spell(ctx: RuleContext) -> bool:
    """Un incantesimo da bardo lanciato con l'azione in questo turno (segnato dal lancio) e l'attacco non è un incantesimo."""
    return ctx.spell is None and (ctx.turn or {}).get("action_spell_class") == ctx.class_row.id


COUNTERCHARM_SAVE = RollOptionSpec(
    key=COUNTERCHARM, phase="before", rolls=("save",), mode="advantage",
    label={"it": "Controfascino: il TS è contro affascinato o spaventato?",
           "en": "Countercharm: is the save against being charmed or frightened?"},
    available=lambda c: state_on(c, "countercharm"),
)

SUPERIOR_INSPIRATION = RollOptionSpec(
    key=f"{CK}.superior_inspiration", phase="before", rolls=("initiative",),
    label={"it": "Ispirazione Superiore: recupera un uso di Ispirazione Bardica",
           "en": "Superior Inspiration: regain one use of Bardic Inspiration"},
    available=_superior_available, on_confirm=_superior_confirmed,
)

PEERLESS_SKILL = RollOptionSpec(
    key=f"{CK}.peerless_skill", phase="after_roll", after="add", rolls=("skill", "ability", "initiative"),
    cost=Cost(feature_key=BI), extra_dice=lambda c, _i: _inspiration_formula(c),
    label={"it": "Abilità Impareggiabile: spendi Ispirazione Bardica e somma il dado",
           "en": "Peerless Skill: spend Bardic Inspiration and add the die"},
)

def _can_react(ctx: RuleContext) -> bool:
    from core.rules.modifiers import is_incapacitated  # import locale: modifiers usa il catalogo
    return not is_incapacitated(ctx.char)


# Il bardo colpito si risponde da sé; per gli alleati c'è il popup (api/services/ally_reactions.py)
CUTTING_WORDS_SELF = RollOptionSpec(
    key=f"{CK}.cutting_words_self", phase="damage_in", rolls=("damage_taken",), slot="reaction",
    cost=Cost(feature_key=BI), extra_dice=lambda c, _i: _inspiration_formula(c),
    label={"it": "Parole Taglienti: spendi Ispirazione Bardica, reazione, il dado riduce il danno",
           "en": "Cutting Words: spend Bardic Inspiration, reaction, the die reduces the damage"},
    available=_can_react,
)

BATTLE_MAGIC = RollOptionSpec(
    key=f"{CK}.battle_magic", phase="before", rolls=("attack",), slot="bonus",
    label={"it": "Magia da Battaglia: attacco con arma come azione bonus",
           "en": "Battle Magic: weapon attack as a bonus action"},
    available=_after_bard_action_spell,
)


FEATURES = (
    feature("hit_points", CK, ED, 1, "Punti Ferita / Hit Points (Bardo 1, pag. 52)", ("Punti Ferita", "Hit Points"),
            ("Dado vita d8; al 1° livello 8 + Costituzione, poi d8 (o 5) + Costituzione.",
             "Hit die d8; level 1 gives 8 + Constitution, then d8 (or 5) + Constitution."), no_row=True,
            covered_by="api/routers/classes.py create_class_for_character e total_base_hp; test_hit_points_use_the_d8_and_follow_constitution"),
    feature("proficiencies", CK, ED, 1, "Competenze / Proficiencies (Bardo 1, pag. 52)", ("Competenze", "Proficiencies"),
            ("Armature leggere, armi semplici, balestra a mano, spada corta, spada lunga, stocco, TS Destrezza e Carisma, 3 abilità.",
             "Light armor, simple weapons, hand crossbow, shortsword, longsword, rapier, Dexterity and Charisma saves, 3 skills."),
            # Armi, armature, TS e abilità: core/rules/proficiencies.py (class_proficiencies) e ClassSkillChoice. I 3 strumenti
            # musicali a scelta no: l'app non ha prove con strumento (R40), restano in lavori-successivi.
            no_row=True, covered_by="lavori-successivi"),
    feature("equipment", CK, ED, 1, "Equipaggiamento / Equipment (Bardo 1, pag. 52)", ("Equipaggiamento", "Equipment"),
            ("Dotazione iniziale: arma a scelta, dotazione da diplomatico o intrattenitore, strumento, armatura di cuoio e pugnale.",
             "Starting gear: a weapon, a diplomat's or entertainer's pack, an instrument, leather armor and a dagger."),
            no_row=True, covered_by="lavori-successivi"),
    feature("spellcasting", CK, ED, 1, "Incantesimi / Spellcasting (Bardo 1, pag. 52)", ("Incantesimi", "Spellcasting"),
            ("Carisma; CD 8 + competenza + Carisma. Trucchetti 2/3/4, conosciuti e slot da tabella, rituali; strumento musicale come focus.",
             "Charisma; DC 8 + proficiency + Charisma. Cantrips 2/3/4, known spells and slots by table, rituals; an instrument as focus."),
            no_row=True, covered_by="core/rules/spellcasting.py (known_limits, slots_for, caster_stats); "
                                    "test_cantrips_and_known_spells_follow_the_class_table"),
    feature("bardic_inspiration", CK, ED, 1, "Ispirazione Bardica / Bardic Inspiration (Bardo 1, pag. 53)",
            ("Ispirazione Bardica", "Bardic Inspiration"),
            ("Azione bonus: un'altra creatura che ti sente riceve un dado (d6, d8, d10, d12) da sommare una volta a una prova, "
             "un attacco o un TS entro 10 minuti.",
             "Bonus action: another creature that hears you gets a die (d6, d8, d10, d12) to add once to a check, attack or save "
             "within 10 minutes."),
            "bonus_action", uses=Uses(ability="charisma", minimum=1), restoration={1: "long_rest", 5: "short_rest"},
            on_use=OnUse(slot="bonus", state=_inspiration_state, ally_state=True)),
    feature("jack_of_all_trades", CK, ED, 2, "Factotum / Jack of All Trades (Bardo 2, pag. 54)",
            ("Factotum", "Jack of All Trades"),
            ("Metà competenza (per difetto) a ogni prova di caratteristica senza competenza: abilità, iniziativa, prove pure.",
             "Half proficiency (rounded down) on every ability check without proficiency: skills, initiative, plain checks."),
            # Abilità, passive e prove pure le somma `skill_proficiency_part` (core/game/skills.py): qui solo l'iniziativa,
            # così la metà competenza non si conta due volte (R26).
            modifiers=(Modifier("half_prof", 1, when=lambda c: c.roll == "initiative",
                                source=f"feature:{CK}.jack_of_all_trades"),)),
    feature("song_of_rest", CK, ED, 2, "Canto di Riposo / Song of Rest (Bardo 2, pag. 54)", ("Canto di Riposo", "Song of Rest"),
            ("Riposo breve: chi spende Dadi Vita tra te e gli amici al tavolo recupera un dado extra (d6, d8, d10, d12) di PF, una volta.",
             "Short rest: you and the friends at the table who spend Hit Dice regain one extra die (d6, d8, d10, d12) of HP, once."),
            on_use=OnUse(state=_song_state)),
    feature("bard_college", CK, ED, 3, "Collegio Bardico / Bard College (Bardo 3, pag. 54)", ("Collegio Bardico", "Bard College"),
            ("Al 3° livello si sceglie il Collegio della Sapienza o del Valore.",
             "At level 3 you choose the College of Lore or the College of Valor."), no_row=True,
            covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    # Prima di Maestria (R39): le tre abilità di Sapienza sono quelle che la rendono scegliibile a chi nasce al 10°
    feature("lore_bonus_proficiencies", CK, ED, 3, "Competenze Bonus / Bonus Proficiencies (Collegio della Sapienza 3, pag. 54)",
            ("Competenze Bonus (Sapienza)", "Bonus Proficiencies (Lore)"),
            ("Tre abilità a tua scelta, non ancora competenti, diventano competenti.",
             "Three skills of your choice that you are not proficient in become proficient."),
            subclass="lore",
            choices=(ChoiceSpec(group="lore_skills", levels={3: 3}, options=_untrained_skills, label=skill_label,
                                grants="proficient", owned=_proficient_skills),)),
    feature("expertise", CK, ED, 3, "Maestria / Expertise (Bardo 3, pag. 54)", ("Maestria", "Expertise"),
            ("Al 3° e al 10° livello due abilità già competenti passano a maestria (doppia competenza).",
             "At levels 3 and 10 two skills you are already proficient in gain expertise (double proficiency)."),
            choices=(ChoiceSpec(group="expertise", levels={3: 2, 10: 4}, options=_expertise_options,
                                label=skill_label, grants="expert"),)),
    feature("ability_score_improvement", CK, ED, 4,
            "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Bardo 4, pag. 54)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 12, 16 e 19: +2 a un punteggio o +1 a due, oppure un talento; massimo 20.",
             "At levels 4, 8, 12, 16 and 19: +2 to one score or +1 to two, or a feat; maximum 20."), no_row=True,
            covered_by="core/rules/level_choices.py (scelta asi); test_asi_choice_is_pending_at_each_asi_level"),
    feature("font_of_inspiration", CK, ED, 5, "Fonte di Ispirazione / Font of Inspiration (Bardo 5, pag. 54)",
            ("Fonte di Ispirazione", "Font of Inspiration"),
            ("Dal 5° livello gli usi di Ispirazione Bardica tornano a ogni riposo breve o lungo.",
             "From level 5 your Bardic Inspiration uses return after every short or long rest.")),
    feature("countercharm", CK, ED, 6, "Controfascino / Countercharm (Bardo 6, pag. 54)", ("Controfascino", "Countercharm"),
            ("Azione: fino alla fine del tuo prossimo turno tu e gli amici entro 9 m che ti sentono avete vantaggio ai TS contro "
             "affascinato e spaventato.",
             "Action: until the end of your next turn you and friends within 30 ft who hear you have advantage on saves against "
             "being charmed or frightened."),
            "action", roll_options=(COUNTERCHARM_SAVE,),
            on_use=OnUse(slot="action", state=StateSpec(
                "countercharm", rounds=2, ends_on=("incapacitated", "rest_short", "rest_long", "manual"), data={"others": [COUNTERCHARM]}))),
    feature("magical_secrets", CK, ED, 10, "Segreti Magici / Magical Secrets (Bardo 10, pag. 54)",
            ("Segreti Magici", "Magical Secrets"),
            ("Al 10°, 14° e 18° livello due incantesimi di qualsiasi classe (o trucchetti) contano come da bardo e fra i conosciuti.",
             "At levels 10, 14 and 18 two spells from any class (or cantrips) count as bard spells and as known spells."),
            choices=(ChoiceSpec(group="magical_secrets", levels={10: 2, 14: 4, 18: 6}, options=_no_options,
                                spell_pick="known"),)),
    feature("superior_inspiration", CK, ED, 20, "Ispirazione Superiore / Superior Inspiration (Bardo 20, pag. 54)",
            ("Ispirazione Superiore", "Superior Inspiration"),
            ("All'iniziativa, se hai finito gli usi di Ispirazione Bardica, ne recuperi uno.",
             "At initiative, if you have no Bardic Inspiration uses left, you regain one."),
            roll_options=(SUPERIOR_INSPIRATION,)),

    # Collegio della Sapienza
    feature("cutting_words", CK, ED, 3, "Parole Taglienti / Cutting Words (Collegio della Sapienza 3, pag. 54)",
            ("Parole Taglienti", "Cutting Words"),
            ("Reazione: spendi un uso di Ispirazione Bardica e tiri il dado da sottrarre al tiro di una creatura entro 18 m.",
             "Reaction: spend a Bardic Inspiration use and roll the die to subtract from a creature's roll within 60 ft."),
            "reaction", subclass="lore",
            on_use=OnUse(slot="reaction", rolls=_inspiration_formula, spends=BI), roll_options=(CUTTING_WORDS_SELF,)),
    feature("additional_magical_secrets", CK, ED, 6,
            "Segreti Magici Aggiuntivi / Additional Magical Secrets (Collegio della Sapienza 6, pag. 55)",
            ("Segreti Magici Aggiuntivi", "Additional Magical Secrets"),
            ("Due incantesimi di qualsiasi classe (o trucchetti) contano come da bardo, ma non fra i conosciuti.",
             "Two spells from any class (or cantrips) count as bard spells, but not among the known spells."),
            subclass="lore",
            choices=(ChoiceSpec(group="additional_secrets", levels={6: 2}, options=_no_options, spell_pick="extra"),)),
    feature("peerless_skill", CK, ED, 14, "Abilità Impareggiabile / Peerless Skill (Collegio della Sapienza 14, pag. 55)",
            ("Abilità Impareggiabile", "Peerless Skill"),
            ("Dopo un tuo tiro per una prova, spendi un uso di Ispirazione Bardica e sommi il dado al totale.",
             "After one of your ability checks, spend a Bardic Inspiration use and add the die to the total."),
            subclass="lore", roll_options=(PEERLESS_SKILL,)),

    # Collegio del Valore
    feature("valor_bonus_proficiencies", CK, ED, 3, "Competenze Bonus / Bonus Proficiencies (Collegio del Valore 3, pag. 55)",
            ("Competenze Bonus (Valore)", "Bonus Proficiencies (Valor)"),
            ("Competenza in armature medie, scudi e armi da guerra.", "Proficiency with medium armor, shields and martial weapons."),
            subclass="valor", proficiency_grants={"armor": ("medium", "shields"), "weapons": ("martial",)}),
    feature("combat_inspiration", CK, ED, 3, "Ispirazione in Combattimento / Combat Inspiration (Collegio del Valore 3, pag. 55)",
            ("Ispirazione in Combattimento", "Combat Inspiration"),
            ("Chi ha il tuo dado può sommarlo al danno di un'arma o, in reazione, alla CA contro un attacco.",
             "A creature holding your die can add it to a weapon damage roll or, as a reaction, to its AC against an attack."),
            subclass="valor"),
    feature("extra_attack", CK, ED, 6, "Attacco Extra / Extra Attack (Collegio del Valore 6, pag. 55)",
            ("Attacco Extra", "Extra Attack"),
            ("Due attacchi con l'azione Attacco; non si somma ad altri Attacco Extra.",
             "Two attacks with the Attack action; does not stack with other Extra Attack."),
            subclass="valor", attacks_per_action=2),
    feature("battle_magic", CK, ED, 14, "Magia da Battaglia / Battle Magic (Collegio del Valore 14, pag. 55)",
            ("Magia da Battaglia", "Battle Magic"),
            ("Dopo un incantesimo da bardo lanciato con l'azione, un attacco con arma come azione bonus.",
             "After casting a bard spell with your action, make one weapon attack as a bonus action."),
            subclass="valor", roll_options=(BATTLE_MAGIC,)),

    feature("multiclassing", CK, ED, 1, "Multiclasse: Bardo / Multiclassing: Bard (Regole opzionali, pag. 163)",
            ("Multiclasse: Bardo", "Multiclassing: Bard"),
            ("Requisito Carisma 13. Da multiclasse: armature leggere, 1 abilità e 1 strumento; gli slot sommano i livelli interi.",
             "Requires Charisma 13. As a multiclass: light armor, 1 skill and 1 tool; spell slots add up full levels."),
            # Armatura leggera, 1 abilità e requisito Carisma 13: core/rules/proficiencies.py (as_multiclass) e
            # webapp/src/data/multiclassPrereqs.ts (D2). Lo strumento musicale a scelta no (R40): lavori-successivi.
            no_row=True, covered_by="lavori-successivi"),
)
