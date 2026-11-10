"""Ranger 2024, parte A (base della classe). Le sottoclassi (Signore delle Bestie, Viandante Fatato, Stalker delle Tenebre,
Cacciatore) sono la parte B: le loro righe vanno in ``SUBCLASS_ROWS`` con ``subclass=`` (chiavi di ``core/rules/subclasses.py``:
beast_master, fey_wanderer, gloom_stalker, hunter).

Valori dalla scheda ``docs/superpowers/rules/2024/classes/ranger.md``; i testi sono nostri, mai quelli del manuale.
Le sottoclassi sono in ``ranger_subclasses.py``. Per quelle: ``hunters_mark_active(ctx)`` dice se la concentrazione è su Hunter's Mark (Preda del Cacciatore Superiore, Furia
Bestiale, Cacciatore Terribile); ``MARK_DAMAGE`` è l'opzione del danno extra del marchio (d6, d10 al 20°) e ``MARK`` la sua chiave.
Il lancio gratuito del marchio è lo stato ``favored_enemy_free`` (R43), chiuso dal lancio.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from core.rules.catalog._common import FIGHTING_STYLE_GROUP, feature, heavy_armor, skill_label, style_options
from core.rules.catalog.y2014.bard import _expertise_options
from core.rules.catalog.y2014.cleric import LANGUAGES, _languages_owned, language_label
from core.rules.catalog.y2024.fighter import STYLE_ROWS as FIGHTER_STYLE_ROWS, STYLES as FIGHTER_STYLES
from core.rules.states import begin_state, has_state
from core.rules.types import ChoiceSpec, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, Uses
from core.rules.weapons import MASTERY_OPTIONS, mastery_choice

ED, CK = "2024", "ranger"
FAVORED_ENEMY = f"{CK}.favored_enemy"
MARK = f"{CK}.hunters_mark_damage"
MARK_SPELL = "hunters-mark"
FREE_STATE = "favored_enemy_free"
DRUIDIC_CANTRIPS = "druidic_warrior_cantrip"
STYLES = (*FIGHTER_STYLES, "druidic_warrior")
_ROWS = "core/rules/proficiencies.py (class_proficiencies, as_multiclass), api/routers/classes.py create_class_for_character e add_class"


def _both(it: str, en: str) -> dict[str, str]:
    return {"it": it, "en": en}


def _wis_mod(ctx: RuleContext) -> int:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return effective_ability_mod(ctx.char, "wisdom")


def hunters_mark_active(ctx: RuleContext) -> bool:
    """La concentrazione del personaggio è su Hunter's Mark: il marchio (e la creatura marcata) c'è in questo momento."""
    spell = next((s for s in ctx.char.spells or [] if s.id == ctx.char.concentrating_spell_id), None)
    return spell is not None and spell.srd_index == MARK_SPELL


# ---------------------------------------------------------------------------
# Nemico Prescelto: Hunter's Mark sempre preparato, lancio gratuito (azione bonus) e danno extra del marchio
# ---------------------------------------------------------------------------

def _free_check(ctx: RuleContext, _params: dict) -> tuple[int, str] | None:
    """Il lancio gratuito costa l'azione bonus: se è già spesa o l'autorizzazione è già data non si spende un uso a vuoto."""
    if (ctx.char.turn_state or {}).get("bonus_used"):
        return 409, "turn_slot_used"
    return (409, "feature_unavailable") if has_state(ctx.char, FREE_STATE) else None


def _free_effect(ctx: RuleContext, _params: dict) -> None:
    """Autorizza un lancio gratuito (R43) di Hunter's Mark: azione bonus, Concentrazione normale; il lancio chiude lo stato."""
    begin_state(ctx.char, StateSpec(FREE_STATE, ends_on=("manual", "rest_short", "rest_long"), data={
        "free_cast": MARK_SPELL, "free_cast_slot": "bonus", "spell": MARK_SPELL}), FAVORED_ENEMY, "Nemico Prescelto")


FREE_USE = OnUse(
    check=_free_check, effect=_free_effect,
    message=lambda _c, _p: _both("Lancia Hunter's Mark dalla pagina degli incantesimi, senza slot (azione bonus): resta la Concentrazione.",
                                 "Cast Hunter's Mark from the spells page with no slot (bonus action): Concentration still applies."))


def _mark_dice(ctx: RuleContext, _inputs: dict) -> str:
    """1d6 di danni da forza; Sterminatore di Nemici (20°) li porta a 1d10."""
    return "1d10" if ctx.class_level >= 20 else "1d6"


def _rangers_own_attack(ctx: RuleContext) -> bool:
    """Il marchio e il Vantaggio sono del ranger: non valgono sull'attacco della bestia o di un altro compagno."""
    return hunters_mark_active(ctx) and ctx.attack_mode not in ("beast", "companion")


MARK_DAMAGE = RollOptionSpec(
    key=MARK, phase="before", rolls=("attack",), extra_damage_type="force", extra_dice=_mark_dice, available=_rangers_own_attack,
    label=_both("Hunter's Mark: il bersaglio è la creatura marcata? +1d6 danni da forza (1d10 al 20°)",
                "Hunter's Mark: is the target the marked creature? Extra 1d6 force damage (1d10 at 20th)"),
    effect=lambda _c, _i: _both("Hunter's Mark: danni da forza in più, già nel totale.", "Hunter's Mark: extra force damage, already in the total."))

PRECISE_HUNTER = RollOptionSpec(
    key=f"{CK}.precise_hunter", phase="before", rolls=("attack",), mode="advantage", available=_rangers_own_attack,
    label=_both("Cacciatore Preciso: il bersaglio è la creatura marcata da Hunter's Mark? Vantaggio",
                "Precise Hunter: is the target the creature marked by Hunter's Mark? Advantage"))


# ---------------------------------------------------------------------------
# Stile di Combattimento: i dieci talenti del Guerriero (righe del Ranger) e Guerriero Druidico
# ---------------------------------------------------------------------------

def _ranger_style(spec: Any) -> Any:
    """Lo stesso talento, riga del Ranger: chiave, classe, livello 2 e fonte dei modificatori."""
    return replace(spec, key=spec.key.replace("fighter.", f"{CK}.", 1), class_key=CK, level=2,
                   modifiers=tuple(replace(m, source=m.source.replace("fighter.", f"{CK}.", 1)) for m in spec.modifiers))


STYLE_ROWS = tuple(_ranger_style(s) for s in FIGHTER_STYLE_ROWS)
DRUIDIC_WARRIOR = feature(
    "style_druidic_warrior", CK, ED, 2, "Guerriero Druidico / Druidic Warrior (Ranger 2, pag. 120)", ("Guerriero Druidico", "Druidic Warrior"),
    ("Due trucchetti da druido, fuori dal limite, con Saggezza come caratteristica; ogni livello da ranger puoi cambiarne uno.",
     "Two druid cantrips, outside the limit, with Wisdom as the ability; at each ranger level you can swap one."),
    option_group=FIGHTING_STYLE_GROUP, option_key="druidic_warrior",
    choices=(ChoiceSpec(group=DRUIDIC_CANTRIPS, levels={2: 2}, options=lambda _c: [], spell_pick="extra", spell_level=0, spell_list="druid"),))


# ---------------------------------------------------------------------------
# Esploratore Abile e Maestria
# ---------------------------------------------------------------------------

def _new_languages(ctx: RuleContext) -> list[str]:
    owned = set(_languages_owned(ctx))
    return [k for k in LANGUAGES if k not in owned]


# ---------------------------------------------------------------------------
# Instancabile e Velo della Natura
# ---------------------------------------------------------------------------

TIRELESS_USE = OnUse(
    slot="action", rolls="1d8", temp_hp=lambda c, rolled: max(1, rolled + _wis_mod(c)),
    message=lambda c, _p: _both(f"PF temporanei: 1d8 + Saggezza ({_wis_mod(c):+d}), minimo 1; non si sommano ai PF temporanei che hai già.",
                                f"Temporary HP: 1d8 + Wisdom ({_wis_mod(c):+d}), minimum 1; they do not stack with temporary HP you already have."))

# Fino alla fine del prossimo turno: lo schema di Colpo Mistico (``turn_end_counted``); Invisibile lo imposta lo stato
VEIL_USE = OnUse(slot="bonus", state=StateSpec(
    "natures_veil", condition="invisible", ends_on=("new_turn", "turn_end_counted", "rest_short", "rest_long", "manual"),
    data={"skip_new_turns": 1, "others": [f"{CK}.natures_veil"]}))


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

BASE_ROWS = (
    feature("core_traits", CK, ED, 1, "Tratti di Base e Competenze / Core Ranger Traits (Ranger 1, pag. 119)",
            ("Tratti Base del Ranger", "Core Ranger Traits"),
            ("d10 come dado vita, TS Forza e Destrezza, 3 abilità, armi semplici e da guerra, armature leggere e medie, scudi.",
             "d10 hit die, Strength and Dexterity saves, 3 skills, simple and martial weapons, light and medium armor, shields."),
            no_row=True, covered_by=f"{_ROWS}, total_base_hp; l'equipaggiamento di partenza è in lavori-successivi (2024-ranger)"),
    feature("spellcasting", CK, ED, 1, "Incantesimi / Spellcasting (Ranger 1, pag. 119)", ("Incantesimi", "Spellcasting"),
            ("Saggezza; slot da mezzo incantatore dal 1° livello, preparati da 2 a 15 da tabella, nessun trucchetto; focus druidico.",
             "Wisdom; half-caster slots from 1st level, prepared spells from 2 to 15 by table, no cantrips; a druidic focus."),
            no_row=True, covered_by="core/rules/spellcasting.py (prepared_limit, slots_for) e core/data/spell_slots.py (HALF_CASTER_SLOTS_2024, "
                                    "multiclasse per eccesso); test_prepared_spells_follow_the_2024_table_and_there_are_no_cantrips"),
    feature("favored_enemy", CK, ED, 1, "Nemico Prescelto / Favored Enemy (Ranger 1, pag. 119)", ("Nemico Prescelto", "Favored Enemy"),
            ("Hunter's Mark sempre preparato. Lanci gratuiti (azione bonus): 2 al 1°, 3 al 5°, 4 al 9°, 5 al 13°, 6 al 17°; riposo lungo.",
             "Hunter's Mark always prepared. Free casts (bonus action): 2 at 1st, 3 at 5th, 4 at 9th, 5 at 13th, 6 at 17th; long rest."),
            "special", uses=Uses(table={1: 2, 5: 3, 9: 4, 13: 5, 17: 6}), restoration="long_rest", granted_spells=(MARK_SPELL,),
            roll_options=(MARK_DAMAGE,), on_use=FREE_USE),
    feature("weapon_mastery", CK, ED, 1, "Maestria nelle Armi / Weapon Mastery (Ranger 1, pag. 120)", ("Maestria nelle Armi", "Weapon Mastery"),
            ("Usi le proprietà di maestria di 2 tipi di arma con cui sei competente; dopo un riposo lungo ne cambi uno.",
             "You use the mastery properties of 2 kinds of weapon you are proficient with; change one after a long rest."),
            choices=(mastery_choice({1: 2}),), roll_options=MASTERY_OPTIONS),
    feature("deft_explorer", CK, ED, 2, "Esploratore Abile / Deft Explorer (Ranger 2, pag. 120)", ("Esploratore Abile", "Deft Explorer"),
            ("Maestria in un'abilità in cui sei già competente e conosci due lingue a tua scelta.",
             "Expertise in one skill you are already proficient in, and you know two languages of your choice."),
            choices=(ChoiceSpec(group="deft_explorer_expertise", levels={2: 1}, options=_expertise_options, label=skill_label, grants="expert"),
                     ChoiceSpec(group="deft_explorer_languages", levels={2: 2}, options=_new_languages, label=language_label,
                                grants="language", owned=_languages_owned))),
    feature("fighting_style", CK, ED, 2, "Stile di Combattimento / Fighting Style (Ranger 2, pag. 120)",
            ("Stile di Combattimento", "Fighting Style"),
            ("Scegli un talento Stile di Combattimento, o Guerriero Druidico.",
             "You choose a Fighting Style feat, or Druidic Warrior."),
            no_row=True, choices=(ChoiceSpec(group=FIGHTING_STYLE_GROUP, levels={2: 1}, options=style_options(STYLES)),),
            covered_by="ChoiceSpec fighting_style di questa riga e le righe dei dieci stili e di Guerriero Druidico; "
                       "test_the_fighting_style_is_chosen_at_level_2_among_ten_styles_and_druidic_warrior"),
    *STYLE_ROWS,
    DRUIDIC_WARRIOR,
    feature("ranger_subclass", CK, ED, 3, "Sottoclasse del Ranger / Ranger Subclass (Ranger 3, pag. 120)",
            ("Sottoclasse del Ranger", "Ranger Subclass"),
            ("Al 3° livello si sceglie Signore delle Bestie, Viandante Fatato, Stalker delle Tenebre o Cacciatore.",
             "At level 3 you choose Beast Master, Fey Wanderer, Gloom Stalker or Hunter."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("ability_score_improvement", CK, ED, 4, "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Ranger 4, pag. 120)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 12 e 16: il talento Aumento dei Punteggi o un altro talento di cui hai i requisiti.",
             "At levels 4, 8, 12 and 16: the Ability Score Improvement feat or another feat you qualify for."),
            no_row=True, covered_by="core/rules/level_choices.py (scelta asi); test_asi_at_4_8_12_16_and_the_19th_is_an_epic_boon"),
    feature("extra_attack", CK, ED, 5, "Attacco Extra / Extra Attack (Ranger 5, pag. 120)", ("Attacco Extra", "Extra Attack"),
            ("Due attacchi con l'azione Attacco; non si somma all'Attacco Extra di altre classi.",
             "Two attacks with the Attack action; does not stack with other classes' Extra Attack."), attacks_per_action=2),
    feature("roving", CK, ED, 6, "Vagabondo / Roving (Ranger 6, pag. 121)", ("Vagabondo", "Roving"),
            ("Velocità +3 m senza armatura pesante; velocità di scalare e di nuotare pari alla Velocità.",
             "Speed +10 ft without heavy armor; climb and swim speeds equal to your Speed."),
            modifiers=(Modifier("speed", 10, when=lambda c: not heavy_armor(c.char), source=f"feature:{CK}.roving"),
                       Modifier("climb_speed", 1, source=f"feature:{CK}.roving"),
                       Modifier("swim_speed", 1, source=f"feature:{CK}.roving"))),
    feature("expertise", CK, ED, 9, "Maestria / Expertise (Ranger 9, pag. 121)", ("Maestria", "Expertise"),
            ("Due abilità in cui sei già competente, senza maestria, passano a maestria (doppia competenza).",
             "Two skills you are already proficient in, without expertise, gain expertise (double proficiency)."),
            choices=(ChoiceSpec(group="expertise", levels={9: 2}, options=_expertise_options, label=skill_label, grants="expert"),)),
    feature("tireless", CK, ED, 10, "Instancabile / Tireless (Ranger 10, pag. 121)", ("Instancabile", "Tireless"),
            ("Azione Magia: PF temporanei 1d8 + Saggezza (minimo 1), usi pari a Saggezza (minimo 1), riposo lungo. Ogni riposo breve: Sfinimento -1.",
             "Magic action: temporary HP 1d8 + Wisdom (minimum 1), uses equal to Wisdom (minimum 1), long rest. Each short rest: Exhaustion -1."),
            "action", uses=Uses(ability="wisdom", minimum=1), restoration="long_rest", on_use=TIRELESS_USE, short_rest_exhaustion=True),
    feature("relentless_hunter", CK, ED, 13, "Cacciatore Implacabile / Relentless Hunter (Ranger 13, pag. 121)",
            ("Cacciatore Implacabile", "Relentless Hunter"),
            ("Il danno subito non spezza la Concentrazione su Hunter's Mark: nessun TS di concentrazione. Solo su quell'incantesimo.",
             "Taking damage cannot break your Concentration on Hunter's Mark: no concentration save. Only on that spell."),
            passive=True, concentration_safe_spells=(MARK_SPELL,)),
    feature("natures_veil", CK, ED, 14, "Velo della Natura / Nature's Veil (Ranger 14, pag. 121)", ("Velo della Natura", "Nature's Veil"),
            ("Azione bonus: Invisibile fino alla fine del tuo prossimo turno. Usi pari a Saggezza (minimo 1), riposo lungo.",
             "Bonus action: Invisible until the end of your next turn. Uses equal to Wisdom (minimum 1), long rest."),
            "bonus_action", uses=Uses(ability="wisdom", minimum=1), restoration="long_rest", on_use=VEIL_USE),
    feature("precise_hunter", CK, ED, 17, "Cacciatore Preciso / Precise Hunter (Ranger 17, pag. 121)", ("Cacciatore Preciso", "Precise Hunter"),
            ("Vantaggio ai tiri per colpire contro la creatura marcata da Hunter's Mark in questo momento: lo confermi al tiro.",
             "Advantage on attack rolls against the creature Hunter's Mark currently marks: you confirm it at the roll."),
            roll_options=(PRECISE_HUNTER,), passive=True),
    feature("feral_senses", CK, ED, 18, "Sensi Ferini / Feral Senses (Ranger 18, pag. 121)", ("Sensi Ferini", "Feral Senses"),
            ("Visione cieca con raggio di 9 m.", "Blindsight with a 30 ft radius."),
            modifiers=(Modifier("sense:blindsight", 30, source=f"feature:{CK}.feral_senses"),)),
    feature("epic_boon", CK, ED, 19, "Dono Epico / Epic Boon (Ranger 19, pag. 121)", ("Dono Epico", "Epic Boon"),
            ("Al 19° livello un talento Dono Epico o un altro talento di cui hai i requisiti; consigliato Dono del Viaggio Dimensionale.",
             "At 19th level an Epic Boon feat or another feat you qualify for; Boon of Dimensional Travel is recommended."),
            no_row=True, covered_by="core/rules/level_choices.py (scelta epic_boon); test_asi_at_4_8_12_16_and_the_19th_is_an_epic_boon"),
    feature("foe_slayer", CK, ED, 20, "Sterminatore di Nemici / Foe Slayer (Ranger 20, pag. 121)", ("Sterminatore di Nemici", "Foe Slayer"),
            ("Il danno extra di Hunter's Mark passa da 1d6 a 1d10.", "Hunter's Mark's extra damage goes from 1d6 to 1d10."),
            no_row=True, covered_by=f"{MARK} (_mark_dice, dal livello 20); test_hunters_mark_adds_a_die_only_while_concentrating_on_it_d6_then_d10_at_level_20"),
    feature("multiclassing", CK, ED, 1, "Multiclasse: Ranger / Multiclassing: Ranger (Creare un Personaggio, pag. 44)",
            ("Multiclasse: Ranger", "Multiclassing: Ranger"),
            ("Requisito Destrezza 13 e Saggezza 13. Da multiclasse: d10, armi da guerra, una abilità, armature leggere e medie, scudi; slot a metà livelli per eccesso.",
             "Requires Dexterity 13 and Wisdom 13. As a multiclass: d10, martial weapons, one skill, light and medium armor, shields; half-level slots rounded up."),
            no_row=True, covered_by=f"{_ROWS} e webapp/src/data/multiclassPrereqs.ts (D2); test_multiclass_slots_count_half_the_ranger_levels_rounded_up"),
)

from core.rules.catalog.y2024.ranger_subclasses import SUBCLASS_ROWS  # noqa: E402  (parte B, dopo le definizioni comuni)

FEATURES = BASE_ROWS + SUBCLASS_ROWS
