"""Ladro 2024, parte A (base della classe). Le sottoclassi (Mistificatore Arcano, Assassino, Coltello dell'Anima, Furfante) sono la
parte B, in ``rogue_subclasses.py``: le loro righe vanno in ``SUBCLASS_ROWS`` con ``subclass=`` (arcane_trickster, assassin, soulknife, thief).

Valori dalla scheda ``docs/superpowers/rules/2024/classes/rogue.md``; i testi sono nostri, mai quelli del manuale.
Per la parte B: ``SNEAK``/``POISON``/``TRIP``/``CUNNING_OPTIONS`` sono le opzioni del Colpo Astuto (gruppo ``cunning_strike``, costo in
dadi tolto dall'Attacco Furtivo); ``steady_aim_keeps_speed(ctx)`` è il punto dove l'Assassino al 9° non perde la Velocità.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from core.rules.catalog._common import INCAPACITATING, feature, state_on
from core.rules.catalog.y2014.cleric import _languages_owned, language_label
from core.rules.catalog.y2014.rogue import (
    CUNNING_BASE, EXPERTISE, EVASION_FAILED, EVASION_SAVE, EVASION_SUCCESS, SNEAK_ATTACK, STROKE_OF_LUCK, UNCANNY_DODGE,
    _cunning_label, _dex_mod, _knows_mage_hand, _not_at_disadvantage, _permanent_note, _proficient_skill_check,
)
from core.rules.catalog.y2024.barbarian import _half_speed, _m
from core.rules.catalog.y2024.ranger import _new_languages
from core.rules.types import (
    ChoiceSpec, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, UseChoice, Uses, UseToggle,
)
from core.rules.weapons import MASTERY_OPTIONS, mastery_choice

ED, CK = "2024", "rogue"
SNEAK = f"{CK}.sneak_attack"
STEADY = "steady_aim"
CUNNING_GROUP = "cunning_strike"
_ROWS = "core/rules/proficiencies.py (class_proficiencies, as_multiclass), api/routers/classes.py create_class_for_character e add_class"


def _both(it: str, en: str) -> dict[str, str]:
    return {"it": it, "en": en}


# ---------------------------------------------------------------------------
# Attacco Furtivo
# ---------------------------------------------------------------------------

BLADE_KEYS = (f"{CK}.psychic_blade", f"{CK}.psychic_blade_bonus")


def _sneak_available(ctx: RuleContext) -> bool:
    """Arma Accurata o a distanza, oppure una Lama Psichica (Coltello dell'Anima: colpo senz'armi confermato nel primo tempo)."""
    blade = ctx.item is None and any(k in ctx.confirmed for k in BLADE_KEYS)
    return (SNEAK_ATTACK.available(ctx) or blade) and _not_at_disadvantage(ctx)


SNEAK_2024 = replace(SNEAK_ATTACK, available=_sneak_available, label=_both(
    "Attacco Furtivo: hai vantaggio sul tiro, o un alleato non incapacitato è entro 1,5 m dal bersaglio e non hai svantaggio? Danni extra (una volta per turno)",
    "Sneak Attack: do you have advantage on the roll, or is an ally who is not incapacitated within 5 ft of the target and you have no disadvantage? Extra damage (once per turn)"))


# ---------------------------------------------------------------------------
# Azione Scaltra e Mira Costante
# ---------------------------------------------------------------------------

CUNNING_ACTION_USE = OnUse(
    slot="bonus", notes=lambda _c, params: [f"cunning_{params['action']}"],
    choices=(UseChoice("action", _both("Azione bonus", "Bonus action"), lambda _c: list(CUNNING_BASE), _cunning_label),))


def _subclass_from(ctx: RuleContext, key: str, level: int) -> bool:
    return ctx.class_row is not None and ctx.class_row.subclass_key == key and ctx.class_level >= level


def steady_aim_keeps_speed(ctx: RuleContext) -> bool:
    """Mira Errante (Assassino 9): la Mira Costante non porta la Velocità a 0."""
    return _subclass_from(ctx, "assassin", 9)


def _steady_check(_ctx: RuleContext, params: dict) -> tuple[int, str] | None:
    return (409, "already_moved") if params.get("moved") else None


STEADY_AIM_USE = OnUse(
    slot="bonus", check=_steady_check,
    toggles=(UseToggle("moved", _both("Ti sei mosso in questo turno?", "Did you move this turn?")),),
    state=StateSpec(STEADY, ends_on=("new_turn", "turn_end", "manual")))

STEADY_AIM_ADVANTAGE = RollOptionSpec(
    key=f"{CK}.steady_aim_advantage", phase="before", rolls=("attack",), mode="advantage", once_per_turn=True,
    available=lambda c: state_on(c, STEADY),
    label=_both("Mira Costante: vantaggio al prossimo tiro per colpire di questo turno", "Steady Aim: advantage on the next attack roll this turn"))


# ---------------------------------------------------------------------------
# Colpo Astuto: ogni effetto toglie dadi all'Attacco Furtivo e il bersaglio fa un TS con CD 8 + Destrezza + competenza
# ---------------------------------------------------------------------------

def _dc(ctx: RuleContext) -> int:
    return 8 + ctx.char.proficiency_bonus + _dex_mod(ctx)


def _effects_allowed(ctx: RuleContext) -> int:
    return 2 if ctx.class_level >= 11 else 1  # Colpo Astuto Migliorato


def _has_poisoners_kit(ctx: RuleContext) -> bool:
    """L'Assassino 3 riceve il Kit da Avvelenatore con Strumenti dell'Assassino: nessun oggetto da aggiungere a mano."""
    return _subclass_from(ctx, "assassin", 3) or any(w in (i.name or "").lower() for i in ctx.char.items or [] for w in ("avvelenatore", "poisoner"))


def _save_text(name: tuple[str, str], ability: tuple[str, str], outcome: tuple[str, str]):
    def effect(ctx: RuleContext, _inputs: dict) -> dict[str, str]:
        dc = _dc(ctx)
        return _both(f"{name[0]}: TS {ability[0]} del bersaglio, CD {dc}. {outcome[0]}",
                     f"{name[1]}: the target's {ability[1]} save, DC {dc}. {outcome[1]}")
    return effect


def _cunning(key: str, cost: int, it: str, en: str, **kw: Any) -> RollOptionSpec:
    return RollOptionSpec(key=f"{CK}.{key}", phase="after_hit", rolls=("attack",), needs=SNEAK, group=CUNNING_GROUP,
                          group_max=_effects_allowed, dice_cost=cost, label=_both(it, en), **kw)


def _save_effect(condition: str, ability: str, **kw: Any):
    return lambda ctx, _i: TargetEffect(condition=condition, save_ability=ability, save_dc=_dc(ctx), **kw)


POISON = _cunning(
    "poison", 1, "Veleno (1d6): il bersaglio fa un TS Costituzione o è Avvelenato",
    "Poison (1d6): the target makes a Constitution save or is Poisoned",
    available=_has_poisoners_kit,
    effect=_save_text(("Veleno", "Poison"), ("Costituzione", "Constitution"),
                      ("Se fallisce è Avvelenato per 1 minuto e ripete il TS alla fine di ogni suo turno.",
                       "On a failure it is Poisoned for 1 minute and repeats the save at the end of each of its turns.")),
    target_effect=_save_effect("poisoned", "constitution", rounds=10, repeat_save="end"))
_TRIP_TEXT = _save_text(("Sgambetto", "Trip"), ("Destrezza", "Dexterity"),
                        ("Vale solo per un bersaglio Grande o più piccolo; se fallisce cade Prono.",
                         "Only for a Large or smaller target; on a failure it falls Prone."))


def _trip_effect(ctx: RuleContext, inputs: dict) -> dict[str, str]:
    """Ingannatore Versatile (Mistificatore Arcano 13): con Mano Magica il TS vale anche per una seconda creatura."""
    text = _TRIP_TEXT(ctx, inputs)
    if not (_subclass_from(ctx, "arcane_trickster", 13) and _knows_mage_hand(ctx)):
        return text
    return _both(f"{text['it']} Ingannatore Versatile: anche una seconda creatura entro 1,5 m dalla mano spettrale fa lo stesso TS, con la stessa CD.",
                 f"{text['en']} Versatile Trickster: a second creature within 5 ft of the spectral hand makes the same save, same DC.")


TRIP = _cunning(
    "trip", 1, "Sgambetto (1d6): il bersaglio Grande o più piccolo fa un TS Destrezza o cade Prono",
    "Trip (1d6): a Large or smaller target makes a Dexterity save or falls Prone",
    effect=_trip_effect,
    target_effect=_save_effect("prone", "dexterity"))


def _withdraw_effect(ctx: RuleContext, _inputs: dict) -> dict[str, str]:
    half = _half_speed(ctx)
    return _both(f"Ritirata: subito dopo l'attacco ti muovi fino a {_m(half)} (metà Velocità) senza provocare attacchi di opportunità.",
                 f"Withdraw: right after the attack you move up to {half} ft (half your Speed) without provoking opportunity attacks.")


WITHDRAW = _cunning("withdraw", 1, "Ritirata (1d6): dopo l'attacco ti muovi di metà Velocità senza attacchi di opportunità",
                    "Withdraw (1d6): after the attack you move half your Speed with no opportunity attacks", effect=_withdraw_effect)
DAZE = _cunning(
    "daze", 2, "Stordimento (2d6): il bersaglio fa un TS Costituzione o ha meno azioni",
    "Daze (2d6): the target makes a Constitution save or loses part of its turn",
    effect=_save_text(("Stordimento", "Daze"), ("Costituzione", "Constitution"),
                      ("Se fallisce, nel suo prossimo turno può fare solo una cosa fra muoversi, agire o usare un'azione bonus.",
                       "On a failure, on its next turn it can do only one thing: move, take an action or take a bonus action.")),
    target_effect=_save_effect("custom:dazed", "constitution", ends_at={"anchor": "owner", "edge": "end", "count": 1}, note="daze"))
KNOCK_OUT = _cunning(
    "knock_out", 6, "Mettere K.O. (6d6): il bersaglio fa un TS Costituzione o perde i sensi",
    "Knock Out (6d6): the target makes a Constitution save or falls Unconscious",
    effect=_save_text(("Mettere K.O.", "Knock Out"), ("Costituzione", "Constitution"),
                      ("Se fallisce è Privo di Sensi per 1 minuto o fino al primo danno subito; ripete il TS a ogni fine del suo turno.",
                       "On a failure it is Unconscious for 1 minute or until it takes damage; it repeats the save at the end of each of its turns.")),
    target_effect=_save_effect("unconscious", "constitution", rounds=10, repeat_save="end", note="knock_out"))
OBSCURE = _cunning(
    "obscure", 3, "Oscurare (3d6): il bersaglio fa un TS Destrezza o è Accecato",
    "Obscure (3d6): the target makes a Dexterity save or is Blinded",
    effect=_save_text(("Oscurare", "Obscure"), ("Destrezza", "Dexterity"),
                      ("Se fallisce è Accecato fino alla fine del suo prossimo turno.", "On a failure it is Blinded until the end of its next turn.")),
    target_effect=_save_effect("blinded", "dexterity", ends_at={"anchor": "owner", "edge": "end", "count": 1}))
CUNNING_OPTIONS = (POISON, TRIP, WITHDRAW, DAZE, KNOCK_OUT, OBSCURE)


# ---------------------------------------------------------------------------
# Elusione, Dote Affidabile, Mente Sfuggente, Colpo di Fortuna
# ---------------------------------------------------------------------------

def _can_act(ctx: RuleContext) -> bool:
    return not any((ctx.char.conditions or {}).get(c) for c in INCAPACITATING)


EVASION_2024 = replace(EVASION_SAVE, available=lambda c: c.ability == "dexterity" and _can_act(c))


def _lacks_save(ability: str):
    return lambda ctx: ctx.roll in ("save", "concentration") and ctx.ability == ability and not (ctx.char.saving_throws or {}).get(ability)


STROKE_2024 = replace(STROKE_OF_LUCK, after="twenty", rolls=("attack", "skill", "ability", "save", "death_save"), label=_both(
    "Colpo di Fortuna: il Test con d20 è fallito? Il d20 vale 20 (con un attacco è un colpo critico)",
    "Stroke of Luck: did the d20 Test fail? The d20 counts as 20 (on an attack, a critical hit)"))


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

BASE_ROWS = (
    feature("hit_points", CK, ED, 1, "Punti Ferita / Hit Points (Ladro 1, pag. 129)", ("Punti Ferita", "Hit Points"),
            ("Dado vita d8; al 1° livello 8 + Costituzione, poi d8 (o 5) + Costituzione; caratteristica primaria Destrezza.",
             "Hit die d8; level 1 gives 8 + Constitution, then d8 (or 5) + Constitution; primary ability Dexterity."), no_row=True,
            covered_by="api/routers/classes.py create_class_for_character e total_base_hp; test_hit_points_use_the_d8"),
    feature("proficiencies", CK, ED, 1, "Competenze / Proficiencies (Ladro 1, pag. 129)", ("Competenze", "Proficiencies"),
            ("TS Destrezza e Intelligenza, armature leggere, armi semplici e marziali Accurate o Leggere, arnesi da scasso, 4 abilità su 10.",
             "Dexterity and Intelligence saves, light armor, simple and martial weapons with Finesse or Light, thieves' tools, 4 skills out of 10."),
            no_row=True, covered_by=f"{_ROWS}; test_class_and_multiclass_proficiencies"),
    feature("equipment", CK, ED, 1, "Equipaggiamento di Partenza / Starting Equipment (Ladro 1, pag. 129)",
            ("Equipaggiamento di Partenza", "Starting Equipment"),
            ("Opzione A: armatura di cuoio, due pugnali, spada corta, arco corto con 20 frecce, arnesi da scasso, zaino, 8 mo. Opzione B: 100 mo.",
             "Option A: leather armor, two daggers, shortsword, shortbow with 20 arrows, thieves' tools, a pack, 8 gp. Option B: 100 gp."),
            no_row=True, covered_by="lavori-successivi"),
    feature("expertise", CK, ED, 1, "Maestria / Expertise (Ladro 1, pag. 129)", ("Maestria", "Expertise"),
            ("Al 1° e al 6° livello due abilità in cui sei competente hanno il bonus di competenza doppio.",
             "At 1st and 6th level two skills you are proficient in get double your proficiency bonus."), choices=(EXPERTISE,)),
    feature("sneak_attack", CK, ED, 1, "Attacco Furtivo / Sneak Attack (Ladro 1, pag. 129)", ("Attacco Furtivo", "Sneak Attack"),
            ("Una volta per turno, danni extra con arma Accurata o a distanza: 1d6, +1d6 ogni due livelli, 10d6 al 19°. Serve vantaggio o un alleato accanto.",
             "Once per turn, extra damage with a Finesse or ranged weapon: 1d6, +1d6 every two levels, 10d6 at 19th. Needs advantage or an ally next to the target."),
            roll_options=(SNEAK_2024,), passive=True),
    feature("thieves_cant", CK, ED, 1, "Gergo Ladresco / Thieves' Cant (Ladro 1, pag. 129)", ("Gergo Ladresco", "Thieves' Cant"),
            ("Conosci il Gergo Ladresco e un'altra lingua a tua scelta.", "You know Thieves' Cant and one other language of your choice."),
            choices=(ChoiceSpec(group="thieves_cant_language", levels={1: 1}, options=_new_languages, label=language_label,
                                grants="language", owned=_languages_owned),)),
    feature("weapon_mastery", CK, ED, 1, "Maestria nelle Armi / Weapon Mastery (Ladro 1, pag. 129)", ("Maestria nelle Armi", "Weapon Mastery"),
            ("Usi le proprietà di maestria di 2 tipi di arma con cui sei competente; dopo un riposo lungo ne cambi.",
             "You use the mastery properties of 2 kinds of weapon you are proficient with; change them after a long rest."),
            choices=(mastery_choice({1: 2}),), roll_options=MASTERY_OPTIONS),
    feature("cunning_action", CK, ED, 2, "Azione Scaltra / Cunning Action (Ladro 2, pag. 130)", ("Azione Scaltra", "Cunning Action"),
            ("Azione bonus nel tuo turno per Scatto, Disimpegno o Nascondersi.", "A bonus action on your turn for Dash, Disengage or Hide."),
            "bonus_action", on_use=CUNNING_ACTION_USE),
    feature("rogue_subclass", CK, ED, 3, "Sottoclasse Ladresca / Rogue Subclass (Ladro 3, pag. 130)",
            ("Sottoclasse Ladresca", "Rogue Subclass"),
            ("Al 3° livello si sceglie Mistificatore Arcano, Assassino, Coltello dell'Anima o Furfante.",
             "At level 3 you choose Arcane Trickster, Assassin, Soul Knife or Thief."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("steady_aim", CK, ED, 3, "Mira Costante / Steady Aim (Ladro 3, pag. 130)", ("Mira Costante", "Steady Aim"),
            ("Azione bonus, solo se non ti sei mosso: vantaggio al prossimo tiro per colpire del turno, Velocità 0 fino a fine turno.",
             "Bonus action, only if you have not moved: advantage on your next attack roll this turn, Speed 0 until the end of the turn."),
            "bonus_action", on_use=STEADY_AIM_USE, roll_options=(STEADY_AIM_ADVANTAGE,),
            modifiers=(Modifier("speed_zero", 1, when=lambda c: state_on(c, STEADY) and not steady_aim_keeps_speed(c),
                                source=f"feature:{CK}.steady_aim"),)),
    feature("ability_score_improvement", CK, ED, 4, "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Ladro 4, pag. 130)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 10, 12 e 16: il talento Aumento dei Punteggi o un altro talento di cui hai i requisiti.",
             "At levels 4, 8, 10, 12 and 16: the Ability Score Improvement feat or another feat you qualify for."),
            no_row=True, covered_by="core/rules/level_choices.py (scelta asi); test_asi_at_4_8_10_12_16_and_the_19th_is_an_epic_boon"),
    feature("cunning_strike", CK, ED, 5, "Colpo Astuto / Cunning Strike (Ladro 5, pag. 130)", ("Colpo Astuto", "Cunning Strike"),
            ("Con l'Attacco Furtivo scegli un effetto: ne paghi il costo in dadi, tolti dal danno. CD dei TS: 8 + Destrezza + competenza.",
             "With Sneak Attack you pick an effect: its dice cost is taken off the damage. Save DC: 8 + Dexterity + proficiency."), passive=True),
    feature("poison", CK, ED, 5, "Veleno / Poison (Colpo Astuto, Ladro 5, pag. 130)", ("Veleno", "Poison"),
            ("Costo 1d6, serve un Kit da Avvelenatore: TS Costituzione o Avvelenato 1 minuto, TS ripetuto a fine turno.",
             "Cost 1d6, needs a Poisoner's Kit: Constitution save or Poisoned for 1 minute, save repeated at turn end."),
            roll_options=(POISON,), passive=True),
    feature("trip", CK, ED, 5, "Sgambetto / Trip (Colpo Astuto, Ladro 5, pag. 130)", ("Sgambetto", "Trip"),
            ("Costo 1d6: un bersaglio Grande o più piccolo fa un TS Destrezza o cade Prono.",
             "Cost 1d6: a Large or smaller target makes a Dexterity save or falls Prone."), roll_options=(TRIP,), passive=True),
    feature("withdraw", CK, ED, 5, "Ritirata / Withdraw (Colpo Astuto, Ladro 5, pag. 131)", ("Ritirata", "Withdraw"),
            ("Costo 1d6: dopo l'attacco ti muovi fino a metà Velocità senza attacchi di opportunità.",
             "Cost 1d6: after the attack you move up to half your Speed with no opportunity attacks."), roll_options=(WITHDRAW,), passive=True),
    feature("uncanny_dodge", CK, ED, 5, "Schivata Prodigiosa / Uncanny Dodge (Ladro 5, pag. 131)", ("Schivata Prodigiosa", "Uncanny Dodge"),
            ("Reazione: un attaccante che vedi ti colpisce, dimezzi i danni di quell'attacco.",
             "Reaction: an attacker you can see hits you, you halve the damage of that attack."),
            "reaction", roll_options=(UNCANNY_DODGE,), passive=True),
    feature("evasion", CK, ED, 7, "Elusione / Evasion (Ladro 7, pag. 131)", ("Elusione", "Evasion"),
            ("Nei TS Destrezza per dimezzare i danni: nessun danno se superi, metà se fallisci. Non vale da incapacitato.",
             "On Dexterity saves for half damage: no damage on a success, half on a failure. Not while incapacitated."),
            roll_options=(EVASION_2024, EVASION_SUCCESS, EVASION_FAILED), passive=True),
    feature("reliable_talent", CK, ED, 7, "Dote Affidabile / Reliable Talent (Ladro 7, pag. 131)", ("Dote Affidabile", "Reliable Talent"),
            ("Nelle prove con una competenza, un d20 che dà 9 o meno conta come 10.", "On checks with a proficiency, a d20 roll of 9 or lower counts as 10."),
            modifiers=(Modifier("min_d20", 10, when=_proficient_skill_check, source=f"feature:{CK}.reliable_talent"),), passive=True),
    feature("improved_cunning_strike", CK, ED, 11, "Colpo Astuto Migliorato / Improved Cunning Strike (Ladro 11, pag. 131)",
            ("Colpo Astuto Migliorato", "Improved Cunning Strike"),
            ("Due effetti di Colpo Astuto per Attacco Furtivo, pagando il costo di ciascuno.",
             "Two Cunning Strike effects per Sneak Attack, paying the cost of each."), passive=True),
    feature("devious_strikes", CK, ED, 14, "Colpi Subdoli / Devious Strikes (Ladro 14, pag. 131)", ("Colpi Subdoli", "Devious Strikes"),
            ("Nuove opzioni di Colpo Astuto: Stordimento (2d6), Mettere K.O. (6d6), Oscurare (3d6).",
             "New Cunning Strike options: Daze (2d6), Knock Out (6d6), Obscure (3d6)."), passive=True),
    feature("daze", CK, ED, 14, "Stordimento / Daze (Colpo Astuto, Ladro 14, pag. 131)", ("Stordimento", "Daze"),
            ("Costo 2d6: TS Costituzione o, nel suo prossimo turno, solo una cosa fra muoversi, agire o azione bonus.",
             "Cost 2d6: Constitution save or, on its next turn, only one thing: move, action or bonus action."),
            roll_options=(DAZE,), passive=True),
    feature("knock_out", CK, ED, 14, "Mettere K.O. / Knock Out (Colpo Astuto, Ladro 14, pag. 131)", ("Mettere K.O.", "Knock Out"),
            ("Costo 6d6: TS Costituzione o Privo di Sensi 1 minuto, TS ripetuto a fine turno; finisce al primo danno.",
             "Cost 6d6: Constitution save or Unconscious for 1 minute, save repeated at turn end; ends on damage."),
            roll_options=(KNOCK_OUT,), passive=True),
    feature("obscure", CK, ED, 14, "Oscurare / Obscure (Colpo Astuto, Ladro 14, pag. 131)", ("Oscurare", "Obscure"),
            ("Costo 3d6: TS Destrezza o Accecato fino alla fine del suo prossimo turno.",
             "Cost 3d6: Dexterity save or Blinded until the end of its next turn."), roll_options=(OBSCURE,), passive=True),
    feature("slippery_mind", CK, ED, 15, "Mente Sfuggente / Slippery Mind (Ladro 15, pag. 131)", ("Mente Sfuggente", "Slippery Mind"),
            ("Competenza nei tiri salvezza su Saggezza e Carisma.", "Proficiency in Wisdom and Charisma saving throws."),
            modifiers=tuple(Modifier("save", lambda c: c.char.proficiency_bonus, when=_lacks_save(a), source=f"feature:{CK}.slippery_mind")
                            for a in ("wisdom", "charisma")), passive=True),
    feature("elusive", CK, ED, 18, "Inafferrabile / Elusive (Ladro 18, pag. 131)", ("Inafferrabile", "Elusive"),
            ("Nessun tiro per colpire contro di te ha vantaggio, finché non sei incapacitato.",
             "No attack roll against you has advantage while you are not incapacitated."),
            passive=True, permanent_state=_permanent_note("elusive"), suspended_when_incapacitated=True),
    feature("epic_boon", CK, ED, 19, "Dono Epico / Epic Boon (Ladro 19, pag. 131)", ("Dono Epico", "Epic Boon"),
            ("Al 19° livello un talento Dono Epico o un altro talento di cui hai i requisiti; consigliato Dono dello Spirito Notturno.",
             "At 19th level an Epic Boon feat or another feat you qualify for; Boon of the Night Spirit is recommended."),
            no_row=True, covered_by="core/rules/level_choices.py (scelta epic_boon); test_asi_at_4_8_10_12_16_and_the_19th_is_an_epic_boon"),
    feature("stroke_of_luck", CK, ED, 20, "Colpo di Fortuna / Stroke of Luck (Ladro 20, pag. 131)", ("Colpo di Fortuna", "Stroke of Luck"),
            ("Un Test con d20 fallito diventa un 20. Un uso fra riposi brevi o lunghi.",
             "A failed d20 Test becomes a 20. One use between short or long rests."),
            uses=Uses(table={20: 1}), restoration="short_rest", roll_options=(STROKE_2024,)),
    feature("multiclassing", CK, ED, 1, "Multiclasse: Ladro / Multiclassing: Rogue (Manuale del Giocatore, pag. 44)",
            ("Multiclasse: Ladro", "Multiclassing: Rogue"),
            ("Requisito Destrezza 13. Da multiclasse: d8, una abilità, arnesi da scasso, armature leggere; nessun TS né arma.",
             "Requires Dexterity 13. As a multiclass: d8, one skill, thieves' tools, light armor; no saves or weapons."),
            no_row=True, covered_by=f"{_ROWS} e webapp/src/data/multiclassPrereqs.ts (D2); test_class_and_multiclass_proficiencies"),
)

from core.rules.catalog.y2024.rogue_subclasses import SUBCLASS_ROWS  # noqa: E402  (parte B, dopo le definizioni comuni)

FEATURES = BASE_ROWS + SUBCLASS_ROWS
