"""Guerriero 2024, parte B: Maestro di Battaglia, Campione, Cavaliere Mistico e Guerriero Psionico.

Valori dalla scheda ``docs/superpowers/rules/2024/classes/fighter.md``; i testi sono nostri, mai quelli del manuale.
Le manovre che non cambiano rispetto al 2014 riusano le sue conferme al tiro (``y2014.fighter``) con il costo e il dado
di Implacabile; quelle che cambiano (Affondo, Scarto Elusivo, Parata, Incoraggiamento, Colpo del Comandante) o nascono
nel 2024 (Imboscata, Scambio Ingannevole, Presenza Imponente, Valutazione Tattica) sono scritte qui.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from core.rules.catalog._common import INCAPACITATING, feature, skill_label, state_on, style_options
from core.rules.catalog.y2014.fighter import (
    DISARMING, DISTRACTING, ELDRITCH_STRIKE, ELDRITCH_STRIKE_CAST, FEINT_STRIKE, GOADING, MANEUVER_KEYS, MANEUVERING, MENACING,
    ONE_MANEUVER, PARRY, PRECISION, PUSHING, RIPOSTE, SWEEPING, TRIP, _evasive_bonus, _evasive_state,
    _survivor_heal, _weapon_attack, _die_sides,
)
from core.rules.catalog.y2024.bard_colleges import _LONG_CASTING, _action_cantrip, _attacks_left, _cantrip_for_an_attack
from core.rules.catalog.y2024.fighter import CK, ED, STYLES
from core.rules.states import has_state
from core.rules.types import (
    ChoiceSpec, Cost, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, Uses, UseToggle,
)

SD, PSI = f"{CK}.superiority_dice", f"{CK}.psionic_power"
MANEUVER_GROUP = "maneuvers"
CLASS_SKILLS = ("acrobatics", "animal_handling", "athletics", "history", "insight", "intimidation", "perception", "persuasion",
                "survival")
LUNGING_STRIKE_KEY = f"{CK}.maneuver_lunging_strike"
MANEUVER_KEYS_24 = MANEUVER_KEYS | {LUNGING_STRIKE_KEY}


def _both(it: str, en: str) -> dict[str, str]:
    return {"it": it, "en": en}


def _m(ft: int) -> str:
    return f"{ft * 3 / 10:g}".replace(".", ",") + " m"


def _int_mod(ctx: RuleContext) -> int:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return effective_ability_mod(ctx.char, "intelligence")


def _restore_toggle(pool: str) -> UseToggle:
    return UseToggle("restore", _both(f"Ripristina spendendo un {pool}", f"Restore by spending a {pool}"))


# ---------------------------------------------------------------------------
# Implacabile: la manovra successiva costa 1d8 e nessun dado (il pulsante arma, la conferma consuma)
# ---------------------------------------------------------------------------

def _armed(ctx: RuleContext) -> bool:
    return (ctx.char.turn_state or {}).get("relentless") is True


def _sd_cost(ctx: RuleContext) -> int:
    return 0 if _armed(ctx) else 1


def _sd_dice(ctx: RuleContext, _inputs: dict | None = None) -> str:
    return "1d8" if _armed(ctx) else f"1d{_die_sides(ctx.class_level)}"


def _clear_relentless(*args: Any) -> None:
    """Chiamata come ``on_confirm(session, ctx, inputs)`` o ``effect(ctx, params)``: il contesto è l'ultimo o il penultimo."""
    ctx = args[1] if len(args) == 3 else args[0]
    ctx.char.turn_state = {k: v for k, v in (ctx.char.turn_state or {}).items() if k != "relentless"}


def _arm_relentless(ctx: RuleContext, _params: dict) -> None:
    ctx.char.turn_state = {**(ctx.char.turn_state or {}), "relentless": True}


SD_COST = Cost(feature_key=SD, amount_by=_sd_cost)


def _chain(first: Any, second: Any) -> Any:
    def run(session: Any, ctx: RuleContext, inputs: dict) -> None:
        if first is not None:
            first(session, ctx, inputs)
        second(session, ctx, inputs)
    return run


def _sd_use(**kw: Any) -> OnUse:
    """Un uso di manovra a dado: spende un dado (o niente, con Implacabile) e tira il dado del livello."""
    return OnUse(spends=SD, cost_by=lambda c, _p: _sd_cost(c), rolls=lambda c: _sd_dice(c), effect=_clear_relentless, **kw)


def _paid(spec: RollOptionSpec, **over: Any) -> RollOptionSpec:
    """Una conferma del 2014 con il costo, il dado e la fine di Implacabile del 2024."""
    return replace(spec, cost=SD_COST, extra_dice=_sd_dice, on_confirm=_chain(spec.on_confirm, _clear_relentless), **over)


def _other_maneuver_used(ctx: RuleContext) -> bool:
    return bool(set(ctx.confirmed) & MANEUVER_KEYS_24)


def _after(ctx: RuleContext) -> bool:
    """Un colpo con un'arma o un Colpo Senz'Armi (non un incantesimo), senza un'altra manovra su questo attacco."""
    return _weapon_attack(ctx) and not _other_maneuver_used(ctx)


def _melee(ctx: RuleContext) -> bool:
    return ctx.attack_mode in ("melee", "offhand")


# ---------------------------------------------------------------------------
# Manovre
# ---------------------------------------------------------------------------

def _best_mod(ctx: RuleContext, _inputs: dict) -> int:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return max(effective_ability_mod(ctx.char, a) for a in ("strength", "dexterity"))


def _no_incapacity(ctx: RuleContext) -> bool:
    return not any((ctx.char.conditions or {}).get(c) for c in INCAPACITATING)


def _check(name: str, rolls: tuple[str, ...], available: Any, label: tuple[str, str]) -> RollOptionSpec:
    return RollOptionSpec(key=f"{CK}.maneuver_{name}", phase="before", rolls=rolls, cost=SD_COST, extra_dice=_sd_dice,
                          on_confirm=_clear_relentless, available=available, label=_both(*label))


AMBUSH = _check("ambush", ("skill", "initiative"),
                lambda c: _no_incapacity(c) and (c.roll == "initiative" or c.skill == "stealth"),
                ("Imboscata: somma il dado di superiorità al tiro", "Ambush: add the superiority die to the roll"))
PRESENCE = _check("commanding_presence", ("skill",), lambda c: c.skill in ("intimidation", "performance", "persuasion"),
                  ("Presenza Imponente: somma il dado di superiorità alla prova", "Commanding Presence: add the superiority die to the check"))
ASSESSMENT = _check("tactical_assessment", ("skill",), lambda c: c.skill in ("history", "investigation", "insight"),
                    ("Valutazione Tattica: somma il dado di superiorità alla prova", "Tactical Assessment: add the superiority die to the check"))

LUNGING_STRIKE = RollOptionSpec(
    key=LUNGING_STRIKE_KEY, phase="before", rolls=("attack",), group=ONE_MANEUVER, extra_dice=lambda c, _i: f"1d{_die_sides(c.class_level)}",
    cost=Cost(state_key="lunging_attack"), available=lambda c: _weapon_attack(c) and _melee(c) and state_on(c, "lunging_attack"),
    label=_both("Affondo: ti sei mosso di almeno 1,5 m in linea retta prima di colpire? (+dado al danno)",
                "Lunging: did you move at least 5 ft straight before the hit? (+die to damage)"))

PARRY_24 = _paid(PARRY, bonus=_best_mod, label=_both(
    "Parata: il danno viene da un attacco in mischia di un'altra creatura? Reazione, riduce il danno di dado + Forza o Destrezza",
    "Parry: is the damage from another creature's melee attack? Reaction, reduces the damage by die + Strength or Dexterity"))


def _bait_state(_ctx: RuleContext, params: dict) -> StateSpec:
    rolled = int(params.get("rolled") or 0)
    data = {"ac": rolled, "self": True} if params.get("self") else {"ac": rolled, "others": [f"{CK}.maneuver_bait_and_switch"]}
    return StateSpec("bait_and_switch", rounds=1, ends_on=("new_turn", "manual"), data=data)


def _bait_bonus(ctx: RuleContext) -> int:
    data = next(((s.get("data") or {}) for s in ctx.char.active_states or [] if s.get("key") == "bait_and_switch"), {})
    return int(data.get("ac") or 0) if data.get("self") else 0


def _maneuver(key: str, it: str, en: str, page: int, summary: tuple[str, str], action_type: str | None = None, **kw: Any):
    return feature(f"maneuver_{key}", CK, ED, 3, f"{it} / {en} (Manovra, Maestro di Battaglia 3, pag. {page})", (it, en), summary,
                   action_type, subclass="battle_master", option_group=MANEUVER_GROUP, option_key=key, **kw)


MANEUVER_ROWS = (
    _maneuver("ambush", "Imboscata", "Ambush", 94,
              ("In una prova di Furtività o in un tiro di Iniziativa spendi un dado e lo somma; non con Incapacitato.",
               "On a Stealth check or an Initiative roll, spend a die and add it; not while Incapacitated."), roll_options=(AMBUSH,)),
    _maneuver("bait_and_switch", "Scambio Ingannevole", "Bait and Switch", 94,
              ("Nel tuo turno scambi posto con una creatura consenziente entro 1,5 m; il dado è un bonus alla CA, tuo o suo, fino al tuo prossimo turno.",
               "On your turn you swap places with a willing creature within 5 ft; the die is an AC bonus, yours or theirs, until your next turn."),
              "special", modifiers=(Modifier("ac", _bait_bonus, when=lambda c: c.roll == "ac" and has_state(c.char, "bait_and_switch"),
                                             source=f"feature:{CK}.maneuver_bait_and_switch"),),
              on_use=_sd_use(state=_bait_state, toggles=(UseToggle("self", _both("Il bonus alla CA è tuo", "The AC bonus is yours")),),
                             message=lambda _c, _p: _both("Scambio di posto senza attacchi di opportunità: il dado tirato è il bonus alla CA fino al tuo prossimo turno.",
                                                          "Swap places with no opportunity attacks: the die rolled is the AC bonus until your next turn."))),
    _maneuver("commanders_strike", "Colpo del Comandante", "Commander's Strike", 94,
              ("Rinunci a un attacco dell'azione Attacco: un alleato che vede o sente attacca in reazione con il dado nel danno.",
               "Give up one attack of the Attack action: an ally who sees or hears you attacks as a reaction with the die added to damage."),
              "special", on_use=_sd_use(forgoes_attack=True, gives=lambda _c, rolled: rolled)),
    _maneuver("commanding_presence", "Presenza Imponente", "Commanding Presence", 95,
              ("Su una prova di Intimidire, Intrattenere o Persuasione spendi un dado e lo somma.",
               "On an Intimidation, Performance or Persuasion check, spend a die and add it."), roll_options=(PRESENCE,)),
    _maneuver("disarming", "Attacco Disarmante", "Disarming Attack", 95,
              ("Dopo un colpo, +dado al danno; TS Forza o il bersaglio lascia cadere un oggetto.",
               "After a hit, +die to damage; Strength save or the target drops an item."), roll_options=(_paid(DISARMING, available=_after),)),
    _maneuver("distracting", "Colpo Distraente", "Distracting Strike", 95,
              ("Dopo un colpo, +dado al danno; il prossimo attacco di un altro contro il bersaglio ha vantaggio fino al tuo turno.",
               "After a hit, +die to damage; the next attack by someone else against the target has advantage until your turn."),
              roll_options=(_paid(DISTRACTING, available=_after),)),
    _maneuver("evasive_footwork", "Scarto Elusivo", "Evasive Footwork", 95,
              ("Azione bonus: Disimpegno; il dado tirato si somma alla CA fino all'inizio del tuo prossimo turno.",
               "Bonus action: Disengage; the die rolled is added to your AC until the start of your next turn."),
              "bonus_action", modifiers=(Modifier("ac", _evasive_bonus, when=lambda c: c.roll == "ac" and has_state(c.char, "evasive_footwork"),
                                                  source=f"feature:{CK}.maneuver_evasive_footwork"),),
              on_use=_sd_use(slot="bonus", state=_evasive_state,
                             message=lambda _c, _p: _both("Disimpegno con questa azione bonus: il dado tirato è il bonus alla CA fino al tuo prossimo turno.",
                                                          "Disengage with this bonus action: the die rolled is the AC bonus until your next turn."))),
    _maneuver("feinting", "Attacco con Finta", "Feinting Attack", 95,
              ("Azione bonus e un dado: vantaggio al prossimo attacco del turno contro una creatura entro 1,5 m, +dado al danno se colpisce.",
               "Bonus action and a die: advantage on your next attack this turn against a creature within 5 ft, +die to damage on a hit."),
              "bonus_action", roll_options=(replace(FEINT_STRIKE, available=lambda c: _weapon_attack(c) and state_on(c, "feinting_attack")),),
              on_use=OnUse(slot="bonus", spends=SD, cost_by=lambda c, _p: _sd_cost(c), effect=_clear_relentless,
                           state=StateSpec("feinting_attack", rounds=1, ends_on=("new_turn", "manual")))),
    _maneuver("goading", "Attacco Adescante", "Goading Attack", 95,
              ("Dopo un colpo, +dado al danno; TS Saggezza o il bersaglio ha svantaggio contro chi non sei tu fino al tuo prossimo turno.",
               "After a hit, +die to damage; Wisdom save or the target has disadvantage against anyone but you until your next turn."),
              roll_options=(_paid(GOADING, available=_after),)),
    _maneuver("lunging", "Attacco con Affondo", "Lunging Attack", 95,
              ("Azione bonus: Scatto; se ti sei mosso in linea retta di 1,5 m prima di colpire in mischia, +dado al danno.",
               "Bonus action: Dash; if you moved 5 ft in a straight line before a melee hit, +die to damage."),
              "bonus_action", roll_options=(LUNGING_STRIKE,),
              on_use=_sd_use(slot="bonus", state=StateSpec("lunging_attack", rounds=1, ends_on=("new_turn", "manual")),
                             message=lambda _c, _p: _both("Scatto con questa azione bonus: poi il primo colpo in mischia del turno può portare il dado.",
                                                          "Dash with this bonus action: the first melee hit of the turn can carry the die."))),
    _maneuver("maneuvering", "Attacco con Manovra", "Maneuvering Attack", 95,
              ("Dopo un colpo, +dado al danno; un alleato usa la reazione per muoversi di metà velocità senza provocare.",
               "After a hit, +die to damage; an ally uses their reaction to move half speed without provoking."),
              roll_options=(_paid(MANEUVERING, available=_after),)),
    _maneuver("menacing", "Attacco Minaccioso", "Menacing Attack", 95,
              ("Dopo un colpo, +dado al danno; TS Saggezza o il bersaglio è spaventato fino alla fine del tuo prossimo turno.",
               "After a hit, +die to damage; Wisdom save or the target is frightened until the end of your next turn."),
              roll_options=(_paid(MENACING, available=_after),)),
    _maneuver("parry", "Parata", "Parry", 95,
              ("Reazione: un attacco in mischia ti ferisce, il danno scende del dado + Forza o Destrezza.",
               "Reaction: a melee attack hurts you, the damage drops by the die + Strength or Dexterity."), "reaction", roll_options=(PARRY_24,)),
    _maneuver("precision", "Attacco Preciso", "Precision Attack", 95,
              ("Dopo un tiro per colpire mancato, somma il dado al tiro e può diventare un colpo.",
               "After a missed attack roll, add the die to the roll; it may turn into a hit."),
              roll_options=(_paid(PRECISION, available=lambda c: _weapon_attack(c) and not _other_maneuver_used(c)),)),
    _maneuver("pushing", "Attacco con Spinta", "Pushing Attack", 95,
              ("Dopo un colpo, +dado al danno; TS Forza o il bersaglio Grande o più piccolo è spinto fino a 4,5 m.",
               "After a hit, +die to damage; Strength save or a Large or smaller target is pushed up to 15 ft."),
              roll_options=(_paid(PUSHING, available=_after),)),
    _maneuver("rally", "Incoraggiamento", "Rally", 95,
              ("Azione bonus: un alleato entro 9 m che vede o sente guadagna PF temporanei pari al dado + metà del tuo livello da guerriero.",
               "Bonus action: an ally within 30 ft who sees or hears you gains temporary hit points equal to the die + half your fighter level."),
              "bonus_action", on_use=_sd_use(slot="bonus", gives=lambda c, rolled: rolled + c.class_level // 2)),
    _maneuver("riposte", "Replica", "Riposte", 95,
              ("Reazione: una creatura ti manca in mischia, la attacchi con un'arma o un Colpo Senz'Armi in mischia e se colpisci +dado al danno.",
               "Reaction: a creature misses you in melee, you attack it in melee with a weapon or Unarmed Strike and add the die to damage on a hit."),
              "reaction", roll_options=(_paid(RIPOSTE, available=lambda c: _weapon_attack(c) and _melee(c)),)),
    _maneuver("sweeping", "Attacco con Spazzata", "Sweeping Attack", 95,
              ("Dopo un colpo in mischia, il dado danneggia una seconda creatura vicina se il tiro per colpire la colpirebbe.",
               "After a melee hit, the die damages a second nearby creature if the attack roll would hit it."),
              roll_options=(_paid(SWEEPING, available=lambda c: _after(c) and _melee(c)),)),
    _maneuver("tactical_assessment", "Valutazione Tattica", "Tactical Assessment", 95,
              ("Su una prova di Storia, Indagare o Intuizione spendi un dado e lo somma.",
               "On a History, Investigation or Insight check, spend a die and add it."), roll_options=(ASSESSMENT,)),
    _maneuver("trip", "Attacco Sbilanciante", "Trip Attack", 95,
              ("Dopo un colpo, +dado al danno; TS Forza o il bersaglio Grande o più piccolo cade prono.",
               "After a hit, +die to damage; Strength save or a Large or smaller target falls prone."), roll_options=(_paid(TRIP, available=_after),)),
)
ALL_MANEUVERS = [spec.option_key for spec in MANEUVER_ROWS]


def _student_options(ctx: RuleContext) -> list[str]:
    skills = ctx.char.skills or {}
    return [s for s in CLASS_SKILLS if not skills.get(s)]


def _student_owned(ctx: RuleContext) -> list[str]:
    skills = ctx.char.skills or {}
    return [s for s in CLASS_SKILLS if skills.get(s)]


def _bm(key: str, level: int, it: str, en: str, page: int, summary: tuple[str, str], action_type: str | None = None, **kw: Any):
    return feature(key, CK, ED, level, f"{it} / {en} (Maestro di Battaglia {level}, pag. {page})", (it, en), summary, action_type,
                   subclass="battle_master", **kw)


BATTLE_MASTER = (
    _bm("superiority_dice", 3, "Superiorità in Combattimento", "Combat Superiority", 93,
        ("Dadi di superiorità: 4 (5 al 7°, 6 al 15°), d8 (d10 al 10°, d12 al 18°). Manovre 3 (5, 7, 9 ai livelli 7, 10, 15). CD 8 + competenza + Forza o Destrezza.",
         "Superiority dice: 4 (5 at 7th, 6 at 15th), d8 (d10 at 10th, d12 at 18th). Maneuvers 3 (5, 7, 9 at 7th, 10th, 15th). DC 8 + proficiency + Strength or Dexterity."),
        uses=Uses(table={3: 4, 7: 5, 15: 6}), restoration="short_rest",
        choices=(ChoiceSpec(group=MANEUVER_GROUP, levels={3: 3, 7: 5, 10: 7, 15: 9}, replaceable=True, options=lambda _c: ALL_MANEUVERS),)),
    _bm("student_of_war", 3, "Studioso di Guerra", "Student of War", 94,
        ("Competenza in un'abilità della lista del guerriero e in un tipo di strumenti da artigiano a tua scelta.",
         "Proficiency in a skill from the fighter list and in one type of artisan's tools of your choice."),
        choices=(ChoiceSpec(group="student_of_war", levels={3: 1}, options=_student_options, label=skill_label, grants="proficient",
                            owned=_student_owned),)),  # gli strumenti: lavori-successivi (R40)
    _bm("know_your_enemy", 7, "Conosci il Tuo Nemico", "Know Your Enemy", 94,
        ("Azione bonus: di una creatura visibile entro 9 m scopri Immunità, Resistenze e Vulnerabilità. Un uso per riposo lungo, o un dado.",
         "Bonus action: learn the Immunities, Resistances and Vulnerabilities of a creature you see within 30 ft. One use per long rest, or a die."),
        "bonus_action", uses=Uses(table={7: 1}), restoration="long_rest",
        on_use=OnUse(slot="bonus", alt_spends=SD, toggles=(_restore_toggle("Dado di Superiorità"),),
                     message=lambda _c, _p: _both("Una creatura che vedi entro 9 m: il GM ti dice se ha Immunità, Resistenze o Vulnerabilità e quali.",
                                                  "A creature you see within 30 ft: the GM tells you whether it has Immunities, Resistances or Vulnerabilities and which."))),
    _bm("improved_combat_superiority", 10, "Superiorità in Combattimento Migliorata", "Improved Combat Superiority", 94,
        ("I dadi di superiorità diventano d10; le manovre tirano il dado del tuo livello.",
         "Superiority dice become d10; maneuvers roll the die of your level.")),
    _bm("relentless", 15, "Implacabile", "Relentless", 94,
        ("Una volta per turno, con una manovra tiri 1d8 invece di spendere un dado: tocca Usa, poi la manovra successiva non costa nulla.",
         "Once per turn, with a maneuver you roll 1d8 instead of spending a die: tap Use, then the next maneuver costs nothing."),
        "special", on_use=OnUse(once_per_turn=True, effect=_arm_relentless,
                                message=lambda _c, _p: _both("La prossima manovra di questo turno usa 1d8 e non spende dadi.",
                                                             "The next maneuver this turn uses 1d8 and spends no dice."))),
    _bm("ultimate_combat_superiority", 18, "Superiorità in Combattimento Suprema", "Ultimate Combat Superiority", 94,
        ("I dadi di superiorità diventano d12; le manovre tirano il dado del tuo livello.",
         "Superiority dice become d12; maneuvers roll the die of your level.")),
    *MANEUVER_ROWS,
)


# ---------------------------------------------------------------------------
# Campione
# ---------------------------------------------------------------------------

def _athlete_advantage(ctx: RuleContext) -> bool:
    return ctx.roll == "initiative" or (ctx.roll in ("skill", "ability") and ctx.skill == "athletics")


def _crit_pending(ctx: RuleContext) -> bool:
    pending = (ctx.char.turn_state or {}).get("pending_attack") or {}
    return bool((pending.get("result") or {}).get("is_critical"))


def _athlete_move(ctx: RuleContext, _inputs: dict) -> dict[str, str]:
    from core.rules.modifiers import effective_speed  # import locale: modifiers usa il catalogo
    half = effective_speed(ctx.char, ctx.char.speed) // 2
    return _both(f"Colpo critico: ti muovi fino a {_m(half)} (metà velocità) senza provocare attacchi di opportunità.",
                 f"Critical hit: you move up to {half} ft (half your Speed) without provoking opportunity attacks.")


ATHLETE_MOVE = RollOptionSpec(
    key=f"{CK}.remarkable_athlete_move", phase="after_hit", rolls=("attack",), available=lambda c: _weapon_attack(c) and _crit_pending(c),
    label=_both("Atleta Straordinario: hai messo a segno un critico, ti muovi di metà velocità",
                "Remarkable Athlete: you scored a critical hit, move half your Speed"), effect=_athlete_move)


def _champ(key: str, level: int, it: str, en: str, summary: tuple[str, str], action_type: str | None = None, **kw: Any):
    return feature(key, CK, ED, level, f"{it} / {en} (Campione {level}, pag. 96)", (it, en), summary, action_type, subclass="champion", **kw)


def _crit(value: int):
    return (Modifier("crit_min", value, when=_weapon_attack, source=f"feature:{CK}.{'improved' if value == 19 else 'superior'}_critical"),)


CHAMPION = (
    _champ("improved_critical", 3, "Critico Migliorato", "Improved Critical",
           ("Armi e Colpi Senz'Armi mettono a segno un critico con 19 o 20 al d20.", "Weapons and Unarmed Strikes score a critical hit on a 19 or 20."),
           modifiers=_crit(19)),
    _champ("remarkable_athlete", 3, "Atleta Straordinario", "Remarkable Athlete",
           ("Vantaggio a Iniziativa e Atletica; dopo un critico ti muovi di metà velocità senza provocare attacchi di opportunità.",
            "Advantage on Initiative and Athletics; after a critical hit you move half your Speed without provoking opportunity attacks."),
           modifiers=(Modifier("advantage", 1, when=_athlete_advantage, source=f"feature:{CK}.remarkable_athlete"),), roll_options=(ATHLETE_MOVE,)),
    _champ("additional_fighting_style", 7, "Stile di Combattimento Aggiuntivo", "Additional Fighting Style",
           ("Al 7° livello scegli un secondo talento Stile di Combattimento, diverso dal primo.",
            "At 7th level you choose a second Fighting Style feat, different from the first."),
           no_row=True, choices=(ChoiceSpec(group="fighting_style", levels={7: 2}, options=style_options(STYLES), replaceable=True),),
           covered_by="ChoiceSpec fighting_style di questa riga e le righe dei dieci stili; test_the_champion_chooses_a_second_style_at_level_7"),
    _champ("heroic_warrior", 10, "Guerriero Eroico", "Heroic Warrior",
           ("In combattimento, all'inizio di ogni tuo turno ottieni l'Ispirazione Eroica se non l'hai già.",
            "In combat, at the start of each of your turns you gain Heroic Inspiration if you don't have it."), turn_start_inspiration=True),
    _champ("superior_critical", 15, "Critico Superiore", "Superior Critical",
           ("Armi e Colpi Senz'Armi mettono a segno un critico con 18, 19 o 20 al d20.", "Weapons and Unarmed Strikes score a critical hit on an 18, 19 or 20."),
           modifiers=_crit(18)),
    _champ("survivor", 18, "Sopravvissuto", "Survivor",
           ("Due benefici: Sfidare la Morte e Rimonta Eroica.", "Two benefits: Defy Death and Heroic Rally.")),
    feature("defy_death", CK, ED, 18, "Sfidare la Morte / Defy Death (Sopravvissuto, Campione 18, pag. 96)", ("Sfidare la Morte", "Defy Death"),
            ("Vantaggio ai tiri salvezza contro la Morte; con 18-20 sul d20 valgono come un 20.",
             "Advantage on Death Saving Throws; a 18-20 on the d20 counts as a 20."), subclass="champion",
            modifiers=(Modifier("advantage", 1, when=lambda c: c.roll == "death_save", source=f"feature:{CK}.defy_death"),
                       Modifier("crit_min", 18, when=lambda c: c.roll == "death_save", source=f"feature:{CK}.defy_death"))),
    feature("heroic_rally", CK, ED, 18, "Rimonta Eroica / Heroic Rally (Sopravvissuto, Campione 18, pag. 96)", ("Rimonta Eroica", "Heroic Rally"),
            ("All'inizio di ogni tuo turno, se sei Sanguinante e hai almeno 1 PF, recuperi 5 + Costituzione PF.",
             "At the start of each of your turns, if you are Bloodied and have at least 1 HP, you regain 5 + Constitution HP."),
            subclass="champion", turn_start_heal=_survivor_heal),
)


# ---------------------------------------------------------------------------
# Cavaliere Mistico
# ---------------------------------------------------------------------------

def _two_attack_spell(ctx: RuleContext) -> bool:
    """Un incantesimo di livello 1 o 2 con tempo di lancio di un'azione, mentre restano due attacchi dell'azione Attacco."""
    spell = ctx.spell
    if spell is None or spell.level not in (1, 2) or _attacks_left(ctx) < 2:
        return False
    from core.rules.spellcasting import casting_kind  # import locale
    return casting_kind(spell) == "action" and not _LONG_CASTING.search(spell.casting_time or "")


def _spell_for_two_attacks(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    turn = dict(ctx.char.turn_state or {})
    turn["action_attacks"] = turn.get("action_attacks", 0) + 2
    ctx.char.turn_state = turn


WAR_MAGIC = RollOptionSpec(
    key=f"{CK}.war_magic", phase="before", rolls=("cast",), available=_action_cantrip, on_confirm=_cantrip_for_an_attack,
    label=_both("Magia da Guerra: il trucchetto prende il posto di uno degli attacchi dell'azione Attacco",
                "War Magic: the cantrip takes the place of one of the Attack action's attacks"))
IMPROVED_WAR_MAGIC = RollOptionSpec(
    key=f"{CK}.improved_war_magic", phase="before", rolls=("cast",), available=_two_attack_spell, on_confirm=_spell_for_two_attacks,
    label=_both("Magia da Guerra Migliorata: l'incantesimo di livello 1 o 2 prende il posto di due attacchi",
                "Improved War Magic: the level 1 or 2 spell takes the place of two attacks"))


def _ek(key: str, level: int, it: str, en: str, page: int, summary: tuple[str, str], action_type: str | None = None, **kw: Any):
    return feature(key, CK, ED, level, f"{it} / {en} (Cavaliere Mistico {level}, pag. {page})", (it, en), summary, action_type,
                   subclass="eldritch_knight", **kw)


ELDRITCH_KNIGHT = (
    _ek("eldritch_knight_spellcasting", 3, "Incantesimi", "Spellcasting", 97,
        ("Terzo di incantatore con Intelligenza, lista del Mago. Trucchetti 2 (3 al 10°); preparati da 3 a 13, slot ripristinati a riposo lungo.",
         "Third-caster with Intelligence, Wizard list. Cantrips 2 (3 at 10th); prepared spells 3 to 13, slots restored on a long rest."),
        no_row=True, covered_by="core/rules/spellcasting.py (known_limits, prepared_limit, slots_for, caster_stats); "
                                "test_eldritch_knight_slots_cantrips_and_prepared_spells_follow_the_2024_table"),
    _ek("weapon_bond", 3, "Legame di Guerra", "War Bond", 98,
        ("Rituale di 1 ora che lega fino a due armi: nessun disarmo, e ne richiami una per volta in mano con un'azione bonus.",
         "A 1-hour ritual bonds up to two weapons: they cannot be disarmed, and you summon one at a time to your hand as a bonus action."),
        "bonus_action", on_use=OnUse(panel="weapon_bond")),
    _ek("war_magic", 7, "Magia da Guerra", "War Magic", 98,
        ("Con l'azione Attacco, un trucchetto del Mago da un'azione sostituisce uno degli attacchi.",
         "With the Attack action, a one-action Wizard cantrip replaces one of the attacks."), roll_options=(WAR_MAGIC,)),
    _ek("eldritch_strike", 10, "Colpo Mistico", "Eldritch Strike", 98,
        ("La creatura che colpisci con un'arma ha svantaggio al prossimo TS contro un tuo incantesimo, fino alla fine del tuo turno seguente.",
         "A creature you hit with a weapon has disadvantage on its next saving throw against a spell of yours, until the end of your next turn."),
        roll_options=(ELDRITCH_STRIKE, ELDRITCH_STRIKE_CAST)),
    _ek("arcane_charge", 15, "Carica Arcana", "Arcane Charge", 98,
        ("Usando Azione Impetuosa ti teletrasporti fino a 9 m in uno spazio libero che vedi, prima o dopo l'azione in più.",
         "When you use Action Surge you teleport up to 30 ft to an unoccupied space you can see, before or after the extra action."),
        passive=True),
    _ek("improved_war_magic", 18, "Magia da Guerra Migliorata", "Improved War Magic", 98,
        ("Con l'azione Attacco, un incantesimo del Mago di livello 1 o 2 da un'azione sostituisce due attacchi.",
         "With the Attack action, a one-action level 1 or 2 Wizard spell replaces two attacks."), roll_options=(IMPROVED_WAR_MAGIC,)),
)


# ---------------------------------------------------------------------------
# Guerriero Psionico
# ---------------------------------------------------------------------------

def _psi_sides(level: int) -> int:
    return 6 if level < 5 else 8 if level < 11 else 10 if level < 17 else 12


def _psi_die(ctx: RuleContext) -> str:
    return f"1d{_psi_sides(ctx.class_level)}"


PROTECTIVE_FIELD = RollOptionSpec(
    key=f"{CK}.protective_field", phase="damage_in", rolls=("damage_taken",), slot="reaction", cost=Cost(feature_key=PSI),
    extra_dice=lambda c, _i: _psi_die(c), bonus=lambda c, _i: max(0, _int_mod(c)),  # shortcut: Intelligenza negativa vale 0, il minimo 1 non si impone
    label=_both("Campo Protettivo: riduci il danno di un dado psionico + Intelligenza",
                "Protective Field: reduce the damage by a psionic die + Intelligence"))


def _strike_dice(ctx: RuleContext, _inputs: dict) -> str:
    return f"{_psi_die(ctx)}{_int_mod(ctx):+d}"


PSIONIC_STRIKE = RollOptionSpec(
    key=f"{CK}.psionic_strike", phase="after_hit", rolls=("attack",), once_per_turn=True, cost=Cost(feature_key=PSI), extra_dice=_strike_dice,
    available=_weapon_attack,
    label=_both("Colpo Psionico: spendi un dado psionico per danno da Forza (dado + Intelligenza), una volta per turno",
                "Psionic Strike: spend a psionic die for Force damage (die + Intelligence), once per turn"),
    effect=lambda c, _i: _both(f"Danno da Forza: dado psionico + Intelligenza ({_int_mod(c):+d}), già nel totale; il bersaglio entro 9 m.",
                               f"Force damage: psionic die + Intelligence ({_int_mod(c):+d}), already in the total; the target within 30 ft."))


def _thrust_dc(ctx: RuleContext) -> int:
    return 8 + ctx.char.proficiency_bonus + _int_mod(ctx)


THRUST = RollOptionSpec(
    key=f"{CK}.telekinetic_thrust", phase="after_hit", rolls=("attack",), needs=PSIONIC_STRIKE.key, available=_weapon_attack,
    label=_both("Spinta Telecinetica: il bersaglio fa un TS Forza o cade prono o è spinto di 3 m",
                "Telekinetic Thrust: the target makes a Strength save or falls prone or is moved 10 ft"),
    effect=lambda c, _i: _both(f"TS Forza CD {_thrust_dc(c)}: se fallisce è prono oppure lo sposti fino a 3 m in orizzontale.",
                               f"DC {_thrust_dc(c)} Strength save: on a failure it falls prone or you move it up to 10 ft horizontally."),
    target_effect=lambda c, _i: TargetEffect(condition="prone", save_ability="strength", save_dc=_thrust_dc(c)))

MASTER_ATTACK = RollOptionSpec(
    key=f"{CK}.telekinetic_master_attack", phase="before", rolls=("attack",), slot="bonus",
    available=lambda c: _weapon_attack(c) and _concentrating_on_telekinesis(c),
    label=_both("Maestro Telecinetico: attacco con arma come azione bonus mentre ti concentri su Telecinesi",
                "Telekinetic Master: weapon attack as a bonus action while you concentrate on Telekinesis"))


def _concentrating_on_telekinesis(ctx: RuleContext) -> bool:
    sid = ctx.char.concentrating_spell_id
    return sid is not None and any(
        s.id == sid and ((s.srd_index or "") == "telekinesis" or (s.name or "").lower() in ("telecinesi", "telekinesis"))
        for s in ctx.char.spells or [])


def _regain_cast(ctx: RuleContext, _params: dict) -> None:
    row = next((a for a in ctx.char.abilities if a.feature_key == f"{CK}.telekinetic_master" and a.source_class_id == ctx.class_row.id), None)
    if row is not None and row.max_uses is not None:
        row.uses = min(row.max_uses, (row.uses or 0) + 1)


def _own_use_spent(ctx: RuleContext) -> bool:
    row = next((a for a in ctx.char.abilities if a.feature_key == f"{CK}.telekinetic_master" and a.source_class_id == ctx.class_row.id), None)
    return row is not None and row.max_uses is not None and (row.uses or 0) < row.max_uses


def _fly_double(ctx: RuleContext) -> int:
    return 2 * ctx.char.speed  # shortcut: la velocità base, senza i modificatori (effective_speed rientrerebbe qui); da correggere se serve


def _clearable(ctx: RuleContext) -> bool:
    return any((ctx.char.conditions or {}).get(c) for c in ("charmed", "frightened"))


def _psi(key: str, level: int, it: str, en: str, page: int, summary: tuple[str, str], action_type: str | None = None,
         group: str = "Guerriero Psionico", **kw: Any):
    parent = "" if group == "Guerriero Psionico" else f"{group}, "
    return feature(key, CK, ED, level, f"{it} / {en} ({parent}Guerriero Psionico {level}, pag. {page})", (it, en), summary, action_type,
                   subclass="psi_warrior", **kw)


PSI_WARRIOR = (
    _psi("psionic_power", 3, "Potere Psionico", "Psionic Power", 98,
         ("Dadi di Energia Psionica: 4d6 (3), 6d8 (5), 8d8 (9), 8d10 (11), 10d10 (13), 12d12 (17). Riposo breve: un dado, lungo: tutti.",
          "Psionic Energy Dice: 4d6 (3), 6d8 (5), 8d8 (9), 8d10 (11), 10d10 (13), 12d12 (17). Short rest: one die, long rest: all."),
         uses=Uses(table={3: 4, 5: 6, 9: 8, 11: 8, 13: 10, 17: 12}), restoration="long_rest", short_rest_recovers=1),
    _psi("protective_field", 3, "Campo Protettivo", "Protective Field", 98,
         ("Reazione: tu o una creatura visibile entro 9 m subite danno, lo riduci di un dado psionico + Intelligenza (minimo 1).",
          "Reaction: when you or a creature you see within 30 ft takes damage, reduce it by a psionic die + Intelligence (minimum 1)."),
         "reaction", group="Potere Psionico", roll_options=(PROTECTIVE_FIELD,),
         on_use=OnUse(slot="reaction", spends=PSI, rolls=_psi_die, gives=lambda c, rolled: max(1, rolled + _int_mod(c)))),
    _psi("psionic_strike", 3, "Colpo Psionico", "Psionic Strike", 98,
         ("Dopo aver colpito con un'arma un bersaglio entro 9 m: un dado psionico, danno da Forza = dado + Intelligenza. Una volta per turno.",
          "After hitting a target within 30 ft with a weapon: a psionic die, Force damage = die + Intelligence. Once per turn."),
         group="Potere Psionico", roll_options=(PSIONIC_STRIKE,)),
    _psi("telekinetic_movement", 3, "Movimento Telecinetico", "Telekinetic Movement", 98,
         ("Azione Magia: sposti di 9 m un oggetto Grande o una creatura consenziente entro 9 m. Un uso per riposo, o un dado.",
          "Magic action: move a Large object or a willing creature within 30 ft up to 30 ft. One use per rest, or a die."),
         "action", group="Potere Psionico", uses=Uses(table={3: 1}), restoration="short_rest",
         on_use=OnUse(slot="action", alt_spends=PSI, toggles=(_restore_toggle("Dado di Energia Psionica"),),
                      message=lambda _c, _p: _both("Sposti l'oggetto o la creatura consenziente fino a 9 m in uno spazio libero che vedi.",
                                                   "You move the object or willing creature up to 30 ft to an unoccupied space you can see."))),
    _psi("telekinetic_adept", 7, "Adepto Telecinetico", "Telekinetic Adept", 99,
         ("Due poteri: Salto Potenziato dalla Psiche e Spinta Telecinetica.", "Two powers: Psi-Powered Leap and Telekinetic Thrust.")),
    _psi("psi_powered_leap", 7, "Salto Potenziato dalla Psiche", "Psi-Powered Leap", 99,
         ("Azione bonus: Velocità di Volo pari al doppio della velocità fino alla fine del turno. Un uso per riposo, o un dado.",
          "Bonus action: until the end of the turn you fly at double your Speed. One use per rest, or a die."),
         "bonus_action", group="Telekinetic Adept", uses=Uses(table={7: 1}), restoration="short_rest",
         modifiers=(Modifier("fly_speed_value", _fly_double, when=lambda c: has_state(c.char, "psi_powered_leap"),
                             source=f"feature:{CK}.psi_powered_leap"),),
         on_use=OnUse(slot="bonus", alt_spends=PSI, toggles=(_restore_toggle("Dado di Energia Psionica"),),
                      state=StateSpec("psi_powered_leap", ends_on=("new_turn", "turn_end", "manual")))),
    _psi("telekinetic_thrust", 7, "Spinta Telecinetica", "Telekinetic Thrust", 99,
         ("Quando il Colpo Psionico fa danno, TS Forza (CD 8 + Intelligenza + competenza): se fallisce, prono o spinto di 3 m.",
          "When Psionic Strike deals damage, Strength save (DC 8 + Intelligence + proficiency): on a failure, prone or moved 10 ft."),
         group="Telekinetic Adept", roll_options=(THRUST,), dc_ability="intelligence"),
    _psi("guarded_mind", 10, "Mente Protetta", "Guarded Mind", 99,
         ("Resistenza ai danni psichici; se inizi il turno Affascinato o Spaventato, spendi un dado e quegli effetti terminano.",
          "Resistance to Psychic damage; if you start your turn Charmed or Frightened, spend a die and those effects end."),
         modifiers=(Modifier("resistance:psychic", 1, source=f"feature:{CK}.guarded_mind"),),
         on_use=OnUse(spends=PSI, available=_clearable,
                      clears=lambda c, _p: [x for x in ("charmed", "frightened") if (c.char.conditions or {}).get(x)])),
    _psi("bulwark_of_force", 15, "Baluardo di Forza", "Bulwark of Force", 99,
         ("Azione bonus: fino a Intelligenza creature entro 9 m (tu compreso) hanno Mezza Copertura per 1 minuto. Un uso per riposo lungo, o un dado.",
          "Bonus action: up to Intelligence creatures within 30 ft (you included) have Half Cover for 1 minute. One use per long rest, or a die."),
         "bonus_action", uses=Uses(table={15: 1}), restoration="long_rest",
         on_use=OnUse(slot="bonus", alt_spends=PSI, toggles=(_restore_toggle("Dado di Energia Psionica"),),
                      state=StateSpec("bulwark_of_force", rounds=10, ends_on=("incapacitated", "manual"),
                                      data={"others": [f"{CK}.bulwark_of_force"]}),
                      message=lambda c, _p: _both(f"Mezza Copertura per 1 minuto a fino a {max(1, _int_mod(c))} creature entro 9 m, te compreso.",
                                                  f"Half Cover for 1 minute to up to {max(1, _int_mod(c))} creatures within 30 ft, you included."))),
    _psi("telekinetic_master", 18, "Maestro Telecinetico", "Telekinetic Master", 99,
         ("Telecinesi sempre preparato: un lancio gratuito per riposo lungo con Intelligenza (o un dado); in concentrazione, attacco come azione bonus.",
          "Telekinesis always prepared: one free cast per long rest using Intelligence (or a die); while concentrating, a bonus action attack."),
         uses=Uses(table={18: 1}), restoration="long_rest", granted_spells=("telekinesis",), free_spell="telekinesis",
         roll_options=(MASTER_ATTACK,), dc_ability="intelligence",
         on_use=OnUse(spends=PSI, available=_own_use_spent, effect=_regain_cast,
                      message=lambda _c, _p: _both("Spendi un dado psionico: il lancio gratuito di Telecinesi è di nuovo disponibile.",
                                                   "You spend a psionic die: the free cast of Telekinesis is available again."))),
)

SUBCLASS_ROWS = (*BATTLE_MASTER, *CHAMPION, *ELDRITCH_KNIGHT, *PSI_WARRIOR)
