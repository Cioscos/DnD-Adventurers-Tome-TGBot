"""Guerriero 2024, parte A (base della classe). Le sottoclassi (Maestro di Battaglia, Campione, Cavaliere Mistico, Guerriero
Psionico) sono la parte B, in ``fighter_subclasses.py``.

Valori dalla scheda ``docs/superpowers/rules/2024/classes/fighter.md``; i testi sono nostri, mai quelli del manuale.
Le chiavi di Recuperare Energie, Azione Impetuosa e Indomito sono quelle legacy di ``CLASS_RESOURCES`` (R17).
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from core.rules.catalog._common import feature, style_options, FIGHTING_STYLE_GROUP
from core.rules.catalog.y2014.fighter import (
    _arcane_charge_notes, _arcane_charge_toggle, _dueling, _great_weapon, _is_ranged_weapon, _off_hand_modifier,
    _weapon_in_hand, _wears_armor, _wields_shield,
)
from core.rules.types import ChoiceSpec, TargetEffect, Cost, Modifier, OnUse, RollOptionSpec, RuleContext, Uses, UseToggle
from core.rules.weapons import MASTERY_OPTIONS, _graze_available, _knows, _modifier, mastery_choice, weapon_mastery

ED, CK = "2024", "fighter"
SW, AS, IND = f"{CK}.second_wind", f"{CK}.action_surge", f"{CK}.indomitable"
MIND = f"{CK}.tactical_mind"
STUDIED = f"{CK}.studied_attacks"
STYLES = ("archery", "blind_fighting", "defense", "dueling", "great_weapon", "interception", "protection", "thrown_weapon",
          "two_weapon", "unarmed")
_ROWS = "core/rules/proficiencies.py (class_proficiencies, as_multiclass), api/routers/classes.py create_class_for_character e add_class"


def _protection_effect(_ctx: RuleContext, _params: dict) -> TargetEffect:
    """Protezione 2024: Svantaggio a tutti gli attacchi contro il bersaglio fino all'inizio del prossimo turno di chi protegge."""
    return TargetEffect(condition="custom:protection", ends_at={"anchor": "source", "edge": "start", "count": 1})


def _both(it: str, en: str) -> dict[str, str]:
    return {"it": it, "en": en}


def _m(ft: int) -> str:
    """Piedi in metri come nei testi italiani (1,5 m ogni 5 ft)."""
    return f"{ft * 3 / 10:g}".replace(".", ",") + " m"


# ---------------------------------------------------------------------------
# Stile di Combattimento (dieci talenti)
# ---------------------------------------------------------------------------

def _style(key: str, title: str, name: tuple[str, str], summary: tuple[str, str], action_type: str | None = None, **kw: Any):
    return feature(f"style_{key}", CK, ED, 1, f"{title} (Stile di Combattimento, pag. 209)", name, summary, action_type,
                   option_group=FIGHTING_STYLE_GROUP, option_key=key, **kw)


def _thrown(ctx: RuleContext) -> bool:
    return ctx.roll == "damage" and _weapon_in_hand(ctx) and ctx.attack_mode == "thrown"


def _armed(ctx: RuleContext) -> bool:
    return any(i.is_equipped and i.item_type in ("weapon", "shield") for i in ctx.char.items or [])


def _interception_given(ctx: RuleContext, rolled: int) -> int:
    return rolled + ctx.char.proficiency_bonus


STYLE_ROWS = (
    _style("archery", "Tiro con l'arco / Archery", ("Tiro con l'Arco", "Archery"),
           ("+2 ai tiri per colpire con armi a distanza.", "+2 to attack rolls with ranged weapons."),
           modifiers=(Modifier("attack", 2, when=lambda c: c.roll == "attack" and _is_ranged_weapon(c), source=f"feature:{CK}.style_archery"),)),
    _style("blind_fighting", "Combattere alla cieca / Blind Fighting", ("Combattere alla Cieca", "Blind Fighting"),
           ("Vista cieca entro 3 m (10 ft).", "Blindsight out to 10 ft."),
           modifiers=(Modifier("sense:blindsight", 10, source=f"feature:{CK}.style_blind_fighting"),)),
    _style("defense", "Difesa / Defense", ("Difesa", "Defense"),
           ("+1 alla CA finché indossi un'armatura (lo scudo da solo non basta).", "+1 to AC while you wear armor (a shield alone does not count)."),
           modifiers=(Modifier("ac", 1, when=lambda c: c.roll == "ac" and _wears_armor(c), source=f"feature:{CK}.style_defense"),)),
    _style("dueling", "Duello / Dueling", ("Duello", "Dueling"),
           ("+2 al danno con un'arma da mischia impugnata a una mano, se non impugni altre armi (lo scudo va bene).",
            "+2 damage with a melee weapon held in one hand when you hold no other weapon (a shield is fine)."),
           modifiers=(Modifier("damage", 2, when=_dueling, source=f"feature:{CK}.style_dueling"),)),
    _style("great_weapon", "Combattere con armi a due mani / Great Weapon Fighting", ("Combattere con Armi a Due Mani", "Great Weapon Fighting"),
           ("Con un'arma da mischia impugnata a due mani, ogni 1 o 2 sui dadi di danno dell'arma conta come 3.",
            "With a melee weapon held in two hands, any 1 or 2 on a weapon damage die counts as a 3."),
           modifiers=(Modifier("damage_min_die", 3, when=_great_weapon, source=f"feature:{CK}.style_great_weapon"),)),
    _style("interception", "Intercettazione / Interception", ("Intercettazione", "Interception"),
           ("Reazione, con scudo o arma: riduci il danno subito da un alleato vicino di 1d10 + competenza. L'app mostra il valore.",
            "Reaction, with a shield or weapon: reduce the damage an ally next to you takes by 1d10 + proficiency. The app shows the value."),
           "reaction", on_use=OnUse(slot="reaction", rolls="1d10", gives=_interception_given, available=_armed)),
    _style("protection", "Protezione / Protection", ("Protezione", "Protection"),
           ("Reazione, con uno scudo: una creatura che vedi attacca un altro bersaglio entro 1,5 m da te; quel tiro e tutti gli altri tiri per colpire contro "
            "quel bersaglio hanno svantaggio fino all'inizio del tuo prossimo turno, se resti entro 1,5 m da lui.",
            "Reaction, with a shield: a creature you see attacks a target other than you within 5 ft of you; that roll and all other attack rolls "
            "against that target have disadvantage until the start of your next turn, if you stay within 5 ft of it."),
           "reaction", on_use=OnUse(slot="reaction", available=_wields_shield, target_effect=_protection_effect)),
    _style("thrown_weapon", "Combattere con armi da lancio / Thrown Weapon Fighting", ("Combattere con Armi da Lancio", "Thrown Weapon Fighting"),
           ("+2 al danno degli attacchi con un'arma lanciata.", "+2 damage on attacks made by throwing a weapon."),
           modifiers=(Modifier("damage", 2, when=_thrown, source=f"feature:{CK}.style_thrown_weapon"),)),
    _style("two_weapon", "Combattere con due armi / Two-Weapon Fighting", ("Combattere con Due Armi", "Two-Weapon Fighting"),
           ("Il danno dell'attacco con la seconda arma include il modificatore di caratteristica.",
            "The damage of the attack with the second weapon includes the ability modifier."),
           modifiers=(Modifier("damage", _off_hand_modifier, when=lambda c: c.roll == "damage" and c.offhand and _weapon_in_hand(c),
                               source=f"feature:{CK}.style_two_weapon"),)),
    _style("unarmed", "Combattere senz'armi / Unarmed Fighting", ("Combattere Senz'Armi", "Unarmed Fighting"),
           ("Colpo senz'armi 1d6 + Forza (1d8 senza armi né scudo in mano); a inizio turno 1d4 a una creatura che stai afferrando.",
            "Unarmed Strike 1d6 + Strength (1d8 with no weapons or shield in hand); at the start of your turn 1d4 to a creature you grapple."),
           passive=True),
)


# ---------------------------------------------------------------------------
# Recuperare Energie, Azione Impetuosa, Mente Tattica, Indomito
# ---------------------------------------------------------------------------

def _second_wind_heal(ctx: RuleContext, rolled: int) -> int:
    return rolled + ctx.class_level


def _tactical_shift(ctx: RuleContext, _params: dict) -> dict[str, str] | None:
    """Spostamento Tattico: il movimento che Recuperare Energie concede, in metà della velocità (D1)."""
    if ctx.class_level < 5:
        return None
    from core.rules.modifiers import effective_speed  # import locale: modifiers usa il catalogo
    half = effective_speed(ctx.char, ctx.char.speed) // 2
    return _both(f"Spostamento Tattico: puoi muoverti fino a {_m(half)} (metà velocità) senza provocare attacchi di opportunità.",
                 f"Tactical Shift: you can move up to {half} ft (half your Speed) without provoking opportunity attacks.")


TACTICAL_MIND = RollOptionSpec(
    key=MIND, phase="after_roll", after="add", rolls=("skill", "ability"), cost=Cost(feature_key=SW), pay_if_success=True,
    extra_dice=lambda _c, _i: "1d10",
    label=_both("Mente Tattica: spendi un uso di Recuperare Energie e somma 1d10 (l'uso torna se la prova fallisce comunque)",
                "Tactical Mind: spend a Second Wind use and add 1d10 (the use comes back if the check still fails)"))

INDOMITABLE_REROLL = RollOptionSpec(
    key=IND, phase="after_roll", after="reroll", rolls=("save",), cost=Cost(feature_key=IND), bonus=lambda c, _i: c.class_level,
    label=_both("Indomito: ripeti il tiro salvezza fallito con bonus pari al livello da guerriero (vale il nuovo risultato)",
                "Indomitable: reroll the failed saving throw with a bonus equal to your fighter level (the new result stands)"))


# ---------------------------------------------------------------------------
# Maestro Tattico e Attacchi Studiati
# ---------------------------------------------------------------------------

def _master(prop: str) -> RollOptionSpec:
    """Push, Sap o Slow al posto della proprietà dell'arma: stesso gruppo ``mastery``, quindi una sola per attacco."""
    base = next(o for o in MASTERY_OPTIONS if o.key == f"mastery_{prop}")
    return replace(base, key=f"{CK}.tactical_master_{prop}",
                   label=_both(f"Maestro Tattico: {prop.capitalize()} al posto della proprietà dell'arma",
                               f"Tactical Master: {prop.capitalize()} instead of the weapon's property"),
                   available=lambda c: c.edition == "2024" and _knows(c) and weapon_mastery(c.item) != prop)


def _studied_available(ctx: RuleContext) -> bool:
    pending = (ctx.char.turn_state or {}).get("pending_attack") or {}
    return not pending.get("result", {}).get("is_critical")  # un 20 naturale colpisce sempre: non c'è un mancato


def _arm_studied(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    ctx.char.turn_state = {**(ctx.char.turn_state or {}), "studied": 2}  # fino alla fine del turno seguente, come Vex


def _use_studied(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    ctx.char.turn_state = {k: v for k, v in (ctx.char.turn_state or {}).items() if k != "studied"}


STUDIED_MISS = RollOptionSpec(
    key=f"{STUDIED}_miss", phase="after_roll", after="miss", rolls=("attack",), on_miss=True,
    miss_damage=lambda c: _modifier(c) if _graze_available(c) else 0,  # ogni mancato vale anche Graze, se l'arma lo ha
    available=_studied_available, on_confirm=_arm_studied,
    label=_both("Attacchi Studiati: hai mancato? Vantaggio sul prossimo attacco contro la stessa creatura",
                "Studied Attacks: did you miss? Advantage on your next attack against the same creature"))
STUDIED_ADVANTAGE = RollOptionSpec(
    key=f"{STUDIED}_advantage", phase="before", rolls=("attack",), mode="advantage", on_confirm=_use_studied,
    available=lambda c: bool((c.char.turn_state or {}).get("studied")),
    label=_both("Attacchi Studiati: attacchi la creatura che hai mancato?", "Studied Attacks: attacking the creature you missed?"))


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

BASE_ROWS = (
    feature("core_traits", CK, ED, 1, "Tratti Fondamentali / Core Fighter Traits (Guerriero 1, pag. 91)",
            ("Tratti Fondamentali del Guerriero", "Core Fighter Traits"),
            ("d10 come dado vita, TS Forza e Costituzione, 2 abilità, armi semplici e da guerra, tutte le armature e gli scudi.",
             "d10 hit die, Strength and Constitution saves, 2 skills, simple and martial weapons, all armor and shields."),
            no_row=True, covered_by=f"{_ROWS}, total_base_hp; l'equipaggiamento di partenza è in lavori-successivi (2024-fighter)"),
    feature("fighting_style", CK, ED, 1, "Stile di Combattimento / Fighting Style (Guerriero 1, pag. 91)",
            ("Stile di Combattimento", "Fighting Style"),
            ("Scegli un talento Stile di Combattimento (consigliato Difesa); a ogni livello da guerriero puoi cambiarlo.",
             "You choose a Fighting Style feat (Defense is recommended); you can change it at every fighter level."),
            no_row=True, choices=(ChoiceSpec(group=FIGHTING_STYLE_GROUP, levels={1: 1}, options=style_options(STYLES), replaceable=True),),
            covered_by="ChoiceSpec fighting_style di questa riga e le righe dei dieci stili; test_the_style_is_one_of_ten_feats_chosen_at_level_1_and_can_be_replaced"),
    *STYLE_ROWS,
    feature("second_wind", CK, ED, 1, "Recuperare Energie / Second Wind (Guerriero 1, pag. 91)", ("Recuperare Energie", "Second Wind"),
            ("Azione bonus: recuperi 1d10 + livello da guerriero in PF. Usi 2 (3 dal 4°, 4 dal 10°): un uso torna con un riposo breve, tutti con uno lungo.",
             "Bonus action: you regain 1d10 + your fighter level in hit points. Uses 2 (3 from 4th, 4 from 10th): a short rest gives one back, a long rest all."),
            "bonus_action", uses=Uses(table={1: 2, 4: 3, 10: 4}), restoration="long_rest", short_rest_recovers=1,
            on_use=OnUse(slot="bonus", rolls="1d10", heal=_second_wind_heal, message=_tactical_shift)),
    feature("weapon_mastery", CK, ED, 1, "Maestria nelle Armi / Weapon Mastery (Guerriero 1, pag. 91)", ("Maestria nelle Armi", "Weapon Mastery"),
            ("Usi le proprietà di maestria di 3 tipi di arma (4 dal 4°, 5 dal 10°, 6 dal 16°); dopo un riposo lungo ne cambi uno.",
             "You use the mastery properties of 3 kinds of weapon (4 from 4th, 5 from 10th, 6 from 16th); change one after a long rest."),
            choices=(mastery_choice({1: 3, 4: 4, 10: 5, 16: 6}),), roll_options=MASTERY_OPTIONS),
    feature("action_surge", CK, ED, 2, "Azione Impetuosa / Action Surge (Guerriero 2, pag. 91)", ("Azione Impetuosa", "Action Surge"),
            ("Nel tuo turno compi un'azione in più, mai Magia. Un uso (due dal 17°, ma uno per turno); torna con un riposo breve o lungo.",
             "On your turn you take one extra action, never Magic. One use (two from 17th, but one per turn); back after a short or long rest."),
            "special", uses=Uses(table={2: 1, 17: 2}), restoration="short_rest",
            on_use=OnUse(grants_action=True, once_per_turn=True, notes=_arcane_charge_notes, toggles=(UseToggle(
                "arcane_charge", _both("Carica Arcana: ti teletrasporti fino a 9 m", "Arcane Charge: teleport up to 30 ft"),
                available=_arcane_charge_toggle),))),
    feature("tactical_mind", CK, ED, 2, "Mente Tattica / Tactical Mind (Guerriero 2, pag. 91)", ("Mente Tattica", "Tactical Mind"),
            ("Dopo una prova fallita spendi un uso di Recuperare Energie e somma 1d10, senza curarti; se fallisce ancora, l'uso non si spende.",
             "After a failed check you spend a Second Wind use and add 1d10, with no healing; if it still fails the use is not spent."),
            roll_options=(TACTICAL_MIND,)),
    feature("subclass", CK, ED, 3, "Sottoclasse del Guerriero / Fighter Subclass (Guerriero 3, pag. 92)",
            ("Sottoclasse del Guerriero", "Fighter Subclass"),
            ("Al 3° livello si sceglie Maestro di Battaglia, Campione, Cavaliere Mistico o Guerriero Psionico.",
             "At level 3 you choose Battle Master, Champion, Eldritch Knight or Psi Warrior."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("ability_score_improvement", CK, ED, 4, "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Guerriero 4, pag. 92)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 6, 8, 12, 14 e 16: il talento Aumento dei Punteggi o un altro talento di cui hai i requisiti.",
             "At levels 4, 6, 8, 12, 14 and 16: the Ability Score Improvement feat or another feat you qualify for."),
            no_row=True, covered_by="core/rules/level_choices.py (scelta asi); test_asi_at_4_6_8_12_14_16_and_the_19th_is_an_epic_boon_not_an_asi"),
    feature("extra_attack", CK, ED, 5, "Attacco Extra / Extra Attack (Guerriero 5, pag. 92)", ("Attacco Extra", "Extra Attack"),
            ("Due attacchi con l'azione Attacco; non si somma all'Attacco Extra di altre classi.",
             "Two attacks with the Attack action; does not stack with other classes' Extra Attack."), attacks_per_action=2),
    feature("tactical_shift", CK, ED, 5, "Spostamento Tattico / Tactical Shift (Guerriero 5, pag. 92)", ("Spostamento Tattico", "Tactical Shift"),
            ("Usando Recuperare Energie ti muovi fino a metà velocità senza provocare attacchi di opportunità; l'esito dell'uso lo ricorda.",
             "When you use Second Wind you move up to half your Speed without provoking opportunity attacks; the use result tells you.")),
    feature("indomitable", CK, ED, 9, "Indomito / Indomitable (Guerriero 9, pag. 92)", ("Indomito", "Indomitable"),
            ("Dopo un TS fallito lo ripeti con bonus pari al livello da guerriero e vale il nuovo risultato. Un uso (due dal 13°, tre dal 17°), torna con un riposo lungo.",
             "After a failed save you reroll it with a bonus equal to your fighter level and the new result stands. One use (two from 13th, three from 17th), back after a long rest."),
            "special", uses=Uses(table={9: 1, 13: 2, 17: 3}), restoration="long_rest", roll_options=(INDOMITABLE_REROLL,)),
    feature("tactical_master", CK, ED, 9, "Maestro Tattico / Tactical Master (Guerriero 9, pag. 92)", ("Maestro Tattico", "Tactical Master"),
            ("Attaccando con un'arma di cui hai la maestria, sostituisci la sua proprietà con Push, Sap o Slow.",
             "When you attack with a weapon whose mastery you have, you replace its property with Push, Sap or Slow."),
            roll_options=(_master("push"), _master("sap"), _master("slow"))),
    feature("two_extra_attacks", CK, ED, 11, "Due Attacchi Extra / Two Extra Attacks (Guerriero 11, pag. 92)",
            ("Due Attacchi Extra", "Two Extra Attacks"), ("Tre attacchi con l'azione Attacco.", "Three attacks with the Attack action."),
            attacks_per_action=3),
    feature("studied_attacks", CK, ED, 13, "Attacchi Studiati / Studied Attacks (Guerriero 13, pag. 92)", ("Attacchi Studiati", "Studied Attacks"),
            ("Se manchi una creatura, dillo all'app: il prossimo attacco contro di lei ha vantaggio fino alla fine del tuo turno seguente.",
             "If you miss a creature, tell the app: your next attack against it has advantage until the end of your next turn."),
            roll_options=(STUDIED_MISS, STUDIED_ADVANTAGE)),
    feature("epic_boon", CK, ED, 19, "Dono Epico / Epic Boon (Guerriero 19, pag. 92)", ("Dono Epico", "Epic Boon"),
            ("Al 19° livello un talento Dono Epico o un altro talento di cui hai i requisiti; consigliato Dono dell'Abilità in Combattimento.",
             "At 19th level an Epic Boon feat or another feat you qualify for; Boon of Combat Prowess is recommended."),
            no_row=True, covered_by="core/rules/level_choices.py (scelta epic_boon); test_asi_at_4_6_8_12_14_16_and_the_19th_is_an_epic_boon_not_an_asi"),
    feature("three_extra_attacks", CK, ED, 20, "Tre Attacchi Extra / Three Extra Attacks (Guerriero 20, pag. 92)",
            ("Tre Attacchi Extra", "Three Extra Attacks"), ("Quattro attacchi con l'azione Attacco.", "Four attacks with the Attack action."),
            attacks_per_action=4),
    feature("multiclassing", CK, ED, 1, "Multiclasse: Guerriero / Multiclassing: Fighter (Regole del multiclasse, pag. 44)",
            ("Multiclasse: Guerriero", "Multiclassing: Fighter"),
            ("Requisito Forza o Destrezza 13. Da multiclasse: d10, armi da guerra, armature leggere e medie, scudi; Attacco Extra non si somma.",
             "Requires Strength or Dexterity 13. As a multiclass: d10, martial weapons, light and medium armor, shields; Extra Attack does not stack."),
            no_row=True, covered_by=f"{_ROWS} e webapp/src/data/multiclassPrereqs.ts (D2)"),
)

from core.rules.catalog.y2024.fighter_subclasses import SUBCLASS_ROWS  # noqa: E402  (parte B, dopo le definizioni comuni)

FEATURES = BASE_ROWS + SUBCLASS_ROWS
