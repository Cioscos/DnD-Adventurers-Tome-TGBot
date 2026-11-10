"""Monaco 2024: base della classe (parte A) e sottoclassi (parte B: Guerriero della Misericordia, dell'Ombra, degli Elementi e
della Mano Aperta, ``SUBCLASS_ROWS`` con ``subclass=`` = chiavi di ``core/rules/subclasses.py``: mercy, shadow, elements,
open_hand).

Valori dalla scheda ``docs/superpowers/rules/2024/classes/monk.md``; i testi sono nostri, mai quelli del manuale.
La riserva dei Punti Concentrazione ha la chiave legacy ``monk.ki`` (R17): tutte le spese passano da lì
(``OnUse.spends``, ``Cost``). Le opzioni che le sottoclassi riusano (``monk.flurry_strike``, ``monk.martial_arts_bonus``)
hanno la stessa chiave del 2014.
"""
from __future__ import annotations

import random
from dataclasses import replace
from typing import Any

from core.data.damage_types import DAMAGE_TYPES
from core.game.attacks import martial_arts_die
from core.rules.catalog._common import feature, state_on
from core.rules.catalog.y2014.monk import (
    _LIGHT_CHOICE, DIAMOND_REROLL, EVASION_FAILED, EVASION_SAVE, EVASION_SUCCESS, FLURRY_STATE, FLURRY_STRIKE,
    SLOW_FALL_OPTION, STEP_ADVANTAGE, _bare, _can_act, _dc_say, _flurry_hit, _ki_dc, _ki_row, _lacks_save_proficiency, _mod,
    _movement_bonus, _save_proficiency, _say, _technique, _till_my_next_turn, _turn, _unarmed,
)
from core.rules.states import begin_state
from core.rules.condition_removal import ConditionRemoval
from core.rules.types import (
    Cost, KiSpell, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, UnarmoredAc, Uses, UseChoice,
)

ED, CK = "2024", "monk"
KI = f"{CK}.ki"
META, PERFECT = f"{CK}.uncanny_metabolism", f"{CK}.perfect_focus"
DEFLECT, REDIRECT = f"{CK}.deflect_attacks", f"{CK}.deflect_redirect"
PD_FOCUS, STEP_FOCUS = f"{CK}.patient_defense_focus", f"{CK}.step_of_the_wind_focus"
REDIRECT_STATE, SUPERIOR_STATE = "deflected_attack", "superior_defense"
PHYSICAL = ("bludgeoning", "piercing", "slashing")
_ROWS = "core/rules/proficiencies.py (class_proficiencies, as_multiclass), api/routers/classes.py create_class_for_character e add_class"


def _both(it: str, en: str) -> dict[str, str]:
    return {"it": it, "en": en}


def _die(ctx: RuleContext) -> str:
    """Il dado Arti Marziali del livello da monaco (d6, d8, d10, d12)."""
    return martial_arts_die(ctx.class_level, ED)


# ---------------------------------------------------------------------------
# Arti Marziali
# ---------------------------------------------------------------------------

def _bonus_strike_available(ctx: RuleContext) -> bool:
    from core.rules.weapons import martial_arts_level  # import locale: weapons usa stats, che usa il catalogo
    return _unarmed(ctx) and martial_arts_level(ctx.char) > 0


MARTIAL_BONUS = RollOptionSpec(
    key=f"{CK}.martial_arts_bonus", phase="before", rolls=("attack",), slot="bonus", available=_bonus_strike_available,
    label=_both("Arti Marziali: colpo senz'armi extra come azione bonus", "Martial Arts: extra unarmed strike as a bonus action"))

FORCE_STRIKE = RollOptionSpec(
    key=f"{CK}.empowered_strikes_force", phase="before", rolls=("attack",), unarmed_damage_type="force", available=_unarmed,
    group=f"{CK}.elemental_strike",  # un solo tipo di danno per colpo: non insieme ai Colpi Elementali
    label=_both("Colpi Potenziati: il colpo senz'armi infligge danni da Forza", "Empowered Strikes: the unarmed strike deals Force damage"))


# ---------------------------------------------------------------------------
# Raffica di Colpi, Difesa Paziente, Passo del Vento
# ---------------------------------------------------------------------------

def _flurry_state(ctx: RuleContext, _params: dict) -> StateSpec:
    """Due colpi senz'armi, tre dal 10° (Concentrazione Accresciuta)."""
    return StateSpec(FLURRY_STATE, rounds=1, ends_on=("new_turn", "manual"), data={"charges": 3 if ctx.class_level >= 10 else 2})


def _patient_state(focus: bool):
    def state(_ctx: RuleContext, _params: dict) -> StateSpec:
        data = {"mode": "disengage_dodge", "others": [PD_FOCUS]} if focus else {"mode": "disengage"}
        return StateSpec("patient_defense", rounds=1, ends_on=("new_turn", "incapacitated", "manual"), data=data)
    return state


def _patient_dice(ctx: RuleContext) -> str:
    """Dal 10° la versione a punto dà due dadi Arti Marziali di PF temporanei; prima nessun dado."""
    return f"2{_die(ctx)[1:]}" if ctx.class_level >= 10 else ""


def _step_state(focus: bool):
    def state(ctx: RuleContext, _params: dict) -> StateSpec:
        data: dict[str, Any] = {"mode": "disengage_dash", "jump_doubled": True} if focus else {"mode": "dash"}
        if focus and ctx.class_level >= 10:
            data["others"] = [STEP_FOCUS]  # la creatura portata con sé (D1): il testo lo dice al GM
        return StateSpec("step_of_the_wind", rounds=1, ends_on=("new_turn", "manual"), data=data)
    return state


# ---------------------------------------------------------------------------
# Metabolismo Prodigioso e Concentrazione Perfetta (al tiro di Iniziativa, in alternativa)
# ---------------------------------------------------------------------------

def _metabolism_heal(ctx: RuleContext, given: dict) -> int:
    """Livello da monaco più un tiro del dado Arti Marziali; il tiro resta in ``given`` per l'esito mostrato."""
    given["rolled"] = random.randint(1, int(_die(ctx)[2:]))
    return ctx.class_level + given["rolled"]


def _refill_focus(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    row = _ki_row(ctx)
    if row is not None and row.max_uses is not None:
        row.uses = row.max_uses


def _focus_to_four(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    row = _ki_row(ctx)
    if row is not None and row.max_uses is not None:
        row.uses = min(row.max_uses, 4)


def _three_or_less(ctx: RuleContext) -> bool:
    row = _ki_row(ctx)
    return row is not None and row.max_uses is not None and (row.uses or 0) <= 3


METABOLISM = RollOptionSpec(
    key=META, phase="before", rolls=("initiative",), cost=Cost(feature_key=META), group="initiative_focus",
    on_confirm=_refill_focus, self_heal=_metabolism_heal,
    label=_both("Metabolismo Prodigioso: recuperi tutti i Punti Concentrazione e PF pari al livello più un dado Arti Marziali",
                "Uncanny Metabolism: regain all Focus Points and hit points equal to your level plus a Martial Arts die"),
    effect=lambda ctx, given: _both(
        f"Metabolismo Prodigioso: recuperi tutti i Punti Concentrazione e {ctx.class_level + given.get('rolled', 0)} PF "
        f"(livello {ctx.class_level} + dado {given.get('rolled', 0)}).",
        f"Uncanny Metabolism: you regain all Focus Points and {ctx.class_level + given.get('rolled', 0)} hit points "
        f"(level {ctx.class_level} + die {given.get('rolled', 0)})."))

PERFECT_FOCUS = RollOptionSpec(
    key=PERFECT, phase="before", rolls=("initiative",), group="initiative_focus", available=_three_or_less,
    on_confirm=_focus_to_four,
    label=_both("Concentrazione Perfetta: non usi il Metabolismo e hai 3 punti o meno, torni a 4",
                "Perfect Focus: you skip Metabolism and have 3 points or fewer, back to 4"),
    effect=_say("Concentrazione Perfetta: i tuoi Punti Concentrazione tornano a 4.", "Perfect Focus: your Focus Points go back to 4."))


# ---------------------------------------------------------------------------
# Deviare Attacchi (e Deviare Energia), Caduta Lenta
# ---------------------------------------------------------------------------

def _covers_damage(ctx: RuleContext) -> bool:
    """Prima del 13° vale solo se il danno include contundente, perforante o tagliente. Senza tipo indicato lo dichiara il giocatore."""
    return ctx.class_level >= 13 or ctx.damage_type is None or ctx.damage_type in PHYSICAL


def _open_redirect(_session: Any, ctx: RuleContext) -> None:
    """Il danno è sceso a 0: l'energia dell'attacco si può rinviare (stesso turno, spendendo un punto)."""
    begin_state(ctx.char, StateSpec(REDIRECT_STATE, rounds=1, ends_on=("new_turn", "manual")), DEFLECT, "Deviare Attacchi")


DEFLECT_OPTION = RollOptionSpec(
    key=DEFLECT, phase="damage_in", rolls=("damage_taken",), slot="reaction", available=lambda c: _can_act(c) and _covers_damage(c),
    extra_dice=lambda _c, _i: "1d10", bonus=lambda c, _i: _mod(c, "dexterity") + c.class_level,
    offered_on_damage=False, on_zero_damage=_open_redirect,
    label=_both("Deviare Attacchi: un attacco ti ha colpito? Reazione, riduce il danno di 1d10 + Destrezza + livello",
                "Deflect Attacks: did an attack hit you? Reaction, reduces the damage by 1d10 + Dexterity + level"))


def _redirect_effect(ctx: RuleContext, _params: dict) -> TargetEffect:
    return TargetEffect(save_ability="dexterity", save_dc=_ki_dc(ctx), on_failure_only=False,
                        damage_dice=f"{_patient_dice_for(ctx, 2)}{_mod(ctx, 'dexterity'):+d}")


def _patient_dice_for(ctx: RuleContext, count: int) -> str:
    return f"{count}{_die(ctx)[1:]}"


# ---------------------------------------------------------------------------
# Colpo Stordente, Autoguarigione, Sopravvissuto Disciplinato
# ---------------------------------------------------------------------------

def _stun_available(ctx: RuleContext) -> bool:
    """Un colpo a segno con un'arma del Monaco o con il Colpo Senz'Armi (non a distanza)."""
    from core.rules.weapons import is_monk_weapon  # import locale
    if ctx.roll != "attack" or ctx.spell is not None:
        return False
    if ctx.item is None:
        return ctx.attack_mode == "melee"
    return ctx.attack_mode in ("melee", "offhand", "thrown") and is_monk_weapon(ctx.item, ED)


def _stun_effect(ctx: RuleContext, _inputs: dict) -> dict[str, str]:
    dc = _ki_dc(ctx)
    return _both(
        f"Il bersaglio fa un TS Costituzione CD {dc}: se fallisce è stordito fino all'inizio del tuo prossimo turno; se lo supera "
        "ha la velocità dimezzata e il prossimo attacco contro di lui prima di allora ha vantaggio.",
        f"The target makes a DC {dc} Constitution save: on a failure it is stunned until the start of your next turn; on a success "
        "its Speed is halved and the next attack against it before then has advantage.")


STUNNING_STRIKE = RollOptionSpec(
    key=f"{CK}.stunning_strike", phase="after_hit", rolls=("attack",), cost=Cost(feature_key=KI), once_per_turn=True,
    available=_stun_available, effect=_stun_effect,
    label=_both("Colpo Stordente: spendi 1 Punto Concentrazione, TS Costituzione o il bersaglio è stordito",
                "Stunning Strike: spend 1 Focus Point, Constitution save or the target is stunned"),
    target_effect=lambda ctx, _i: TargetEffect(condition="stunned", save_ability="constitution", save_dc=_ki_dc(ctx),
                                               ends_at={"anchor": "source", "edge": "start", "count": 1}))

_RESTORABLE = {"charmed": _both("Affascinato", "Charmed"), "frightened": _both("Spaventato", "Frightened"),
               "poisoned": _both("Avvelenato", "Poisoned")}


def _restorable(ctx: RuleContext) -> list[str]:
    return [c for c in _RESTORABLE if (ctx.char.conditions or {}).get(c)]


SURVIVOR_REROLL = replace(
    DIAMOND_REROLL, key=f"{CK}.disciplined_survivor",
    label=_both("Sopravvissuto Disciplinato: spendi 1 Punto Concentrazione e ripeti il tiro salvezza fallito (vale il nuovo risultato)",
                "Disciplined Survivor: spend 1 Focus Point and reroll the failed saving throw (the new result stands)"))


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

BASE_ROWS = (
    feature("hit_points", CK, ED, 1, "Punti Ferita / Hit Points (Monaco 1, pag. 101)", ("Punti Ferita", "Hit Points"),
            ("Dado vita d8 per livello da monaco.", "Hit die d8 per monk level."), no_row=True,
            covered_by="api/routers/classes.py create_class_for_character e total_base_hp; test_hit_points_use_the_d8"),
    feature("proficiencies", CK, ED, 1, "Competenze / Proficiencies (Monaco 1, pag. 101)", ("Competenze", "Proficiencies"),
            ("TS Forza e Destrezza, 2 abilità fra sei, armi semplici e da guerra con Leggera, uno strumento. Nessuna armatura; da seconda classe nulla.",
             "Strength and Dexterity saves, 2 skills from six, simple weapons and martial weapons with Light, one tool. No armor; none as a second class."),
            no_row=True, covered_by=f"{_ROWS}; lo strumento è in lavori-successivi (R40); "
                                    "test_proficiencies_come_from_the_2024_class_table_and_a_second_class_gets_none"),
    feature("equipment", CK, ED, 1, "Equipaggiamento / Equipment (Monaco 1, pag. 101)", ("Equipaggiamento", "Equipment"),
            ("Dotazione iniziale a scelta: lancia, 5 pugnali, uno strumento, zaino da esploratore e 11 mo, oppure 50 mo.",
             "Starting gear of your choice: spear, 5 daggers, a tool, explorer's pack and 11 gp, or 50 gp."),
            no_row=True, covered_by="lavori-successivi"),
    feature("martial_arts", CK, ED, 1, "Arti Marziali / Martial Arts (Monaco 1, pag. 101)", ("Arti Marziali", "Martial Arts"),
            ("Senza armatura né scudo, con armi del Monaco o a mani nude: colpo senz'armi extra in azione bonus, dado d6 (d8 al 5°, "
             "d10 all'11°, d12 al 17°) e Destrezza.",
             "With no armor or shield, using Monk weapons or bare hands: a bonus unarmed strike, die d6 (d8 at 5th, d10 at 11th, "
             "d12 at 17th) and Dexterity."),
            roll_options=(MARTIAL_BONUS,)),
    feature("unarmored_defense", CK, ED, 1, "Difesa Senza Armatura / Unarmored Defense (Monaco 1, pag. 101)",
            ("Difesa Senza Armatura", "Unarmored Defense"),
            ("Senza armatura né scudo la CA è 10 + Destrezza + Saggezza. Non si somma alla Difesa Senza Armatura di un'altra classe.",
             "With no armor and no shield your AC is 10 + Dexterity + Wisdom. It does not stack with another class's Unarmored Defense."),
            unarmored=UnarmoredAc(("dexterity", "wisdom"), no_shield=True)),
    feature("ki", CK, ED, 2, "Concentrazione del Monaco / Monk's Focus (Monaco 2, pag. 101)", ("Punti Concentrazione", "Focus Points"),
            ("Riserva pari al livello da monaco, torna con un riposo breve o lungo. CD 8 + competenza + Saggezza. "
             "Alimenta Raffica di Colpi, Difesa Paziente, Passo del Vento.",
             "Pool equal to your monk level, back after a short or long rest. DC 8 + proficiency + Wisdom. "
             "Fuels Flurry of Blows, Patient Defense, Step of the Wind."),
            uses=Uses(table={2: 0}, per_level=1), restoration="short_rest", dc_ability="wisdom"),
    feature("flurry_of_blows", CK, ED, 2, "Raffica di Colpi / Flurry of Blows (Monaco 2, pag. 102)", ("Raffica di Colpi", "Flurry of Blows"),
            ("Azione bonus e 1 punto: due colpi senz'armi, tre dal 10°, ognuno con il proprio tiro per colpire.",
             "Bonus action and 1 point: two unarmed strikes, three from 10th, each with its own attack roll."),
            "bonus_action", roll_options=(FLURRY_STRIKE,), on_use=OnUse(slot="bonus", spends=KI, state=_flurry_state)),
    feature("patient_defense", CK, ED, 2, "Difesa Paziente / Patient Defense (Monaco 2, pag. 102)", ("Difesa Paziente", "Patient Defense"),
            ("Azione bonus, gratis: Disimpegno.", "Bonus action, free: Disengage."),
            "bonus_action", on_use=OnUse(slot="bonus", state=_patient_state(False))),
    feature("patient_defense_focus", CK, ED, 2, "Difesa Paziente / Patient Defense (Monaco 2, pag. 102)",
            ("Difesa Paziente (1 punto)", "Patient Defense (1 point)"),
            ("Azione bonus e 1 punto: Disimpegno e Schivata insieme; chi ti attacca ha svantaggio. Dal 10° ottieni PF temporanei pari a due dadi Arti Marziali.",
             "Bonus action and 1 point: Disengage and Dodge together; attackers have disadvantage. From 10th you gain temporary hit points equal to two Martial Arts dice."),
            "bonus_action", on_use=OnUse(slot="bonus", spends=KI, state=_patient_state(True), rolls=_patient_dice,
                                         temp_hp=lambda _c, rolled: rolled)),
    feature("step_of_the_wind", CK, ED, 2, "Passo del Vento / Step of the Wind (Monaco 2, pag. 102)", ("Passo del Vento", "Step of the Wind"),
            ("Azione bonus, gratis: Scatto.", "Bonus action, free: Dash."),
            "bonus_action", on_use=OnUse(slot="bonus", state=_step_state(False))),
    feature("step_of_the_wind_focus", CK, ED, 2, "Passo del Vento / Step of the Wind (Monaco 2, pag. 102)",
            ("Passo del Vento (1 punto)", "Step of the Wind (1 point)"),
            ("Azione bonus e 1 punto: Disimpegno e Scatto, salto doppio per il turno. Dal 10° porti con te una creatura consenziente entro 1,5 m, senza attacchi di opportunità.",
             "Bonus action and 1 point: Disengage and Dash, double jump for the turn. From 10th you carry a willing creature within 5 ft, with no opportunity attacks."),
            "bonus_action", on_use=OnUse(slot="bonus", spends=KI, state=_step_state(True))),
    feature("unarmored_movement", CK, ED, 2, "Movimento Senza Armatura / Unarmored Movement (Monaco 2, pag. 102)",
            ("Movimento Senza Armatura", "Unarmored Movement"),
            ("Senza armatura né scudo la velocità cresce: +3 m dal 2°, +4,5 m al 6°, +6 m al 10°, +7,5 m al 14°, +9 m al 18°.",
             "With no armor and no shield your speed grows: +10 ft at 2nd, +15 ft at 6th, +20 ft at 10th, +25 ft at 14th, +30 ft at 18th."),
            modifiers=(Modifier("speed", _movement_bonus, when=_bare, source=f"feature:{CK}.unarmored_movement"),)),
    feature("uncanny_metabolism", CK, ED, 2, "Metabolismo Prodigioso / Uncanny Metabolism (Monaco 2, pag. 102)",
            ("Metabolismo Prodigioso", "Uncanny Metabolism"),
            ("Tirando l'Iniziativa, una volta per riposo lungo: recuperi tutti i Punti Concentrazione e PF pari al livello più un dado Arti Marziali.",
             "When you roll Initiative, once per long rest: you regain all Focus Points and hit points equal to your level plus a Martial Arts die."),
            uses=Uses(table={2: 1}), restoration="long_rest", roll_options=(METABOLISM,)),
    feature("deflect_attacks", CK, ED, 3, "Deviare Attacchi / Deflect Attacks (Monaco 3, pag. 102)", ("Deviare Attacchi", "Deflect Attacks"),
            ("Reazione a un attacco che ti colpisce con danno contundente, perforante o tagliente: il danno cala di 1d10 + Destrezza + livello. "
             "A 0, con 1 punto rinvii l'energia (vedi il rinvio).",
             "Reaction to an attack that hits you with bludgeoning, piercing or slashing damage: damage drops by 1d10 + Dexterity + level. "
             "At 0, spend 1 point to send the energy back (see the redirect)."),
            "reaction", roll_options=(DEFLECT_OPTION,)),
    feature("deflect_redirect", CK, ED, 3, "Deviare Attacchi / Deflect Attacks (Monaco 3, pag. 102)",
            ("Deviare Attacchi: rinvio", "Deflect Attacks: redirect"),
            ("Dopo aver ridotto il danno a 0, 1 punto: una creatura visibile entro 1,5 m (mischia) o 18 m (a distanza) fa un TS Destrezza "
             "o subisce due dadi Arti Marziali + Destrezza dello stesso tipo del danno.",
             "After reducing the damage to 0, 1 point: a creature you can see within 5 ft (melee) or 60 ft (ranged) makes a Dexterity save "
             "or takes two Martial Arts dice + Dexterity of the attack's damage type."),
            "special", on_use=OnUse(  # non "reaction": Deviare ha già speso la reazione e la sezione Reazione del Turno si richiude
                spends=KI, available=lambda c: state_on(c, REDIRECT_STATE), rolls=lambda c: _patient_dice_for(c, 2),
                ends_state=REDIRECT_STATE, target_effect=_redirect_effect,
                message=lambda c, _p: _both(
                    f"Una creatura entro 1,5 m (mischia) o 18 m (a distanza) fa un TS Destrezza CD {_ki_dc(c)}: se fallisce subisce i dadi "
                    "più Destrezza dello stesso tipo del danno dell'attacco; se lo supera, nulla.",
                    f"A creature within 5 ft (melee) or 60 ft (ranged) makes a DC {_ki_dc(c)} Dexterity save: on a failure it takes the dice "
                    "plus Dexterity of the attack's damage type; on a success, nothing."))),
    feature("subclass", CK, ED, 3, "Sottoclasse del Monaco / Monk Subclass (Monaco 3, pag. 103)", ("Sottoclasse del Monaco", "Monk Subclass"),
            ("Al 3° livello si sceglie Guerriero della Misericordia, dell'Ombra, degli Elementi o della Mano Aperta.",
             "At level 3 you choose Warrior of Mercy, of Shadow, of the Elements or of the Open Hand."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("ability_score_improvement", CK, ED, 4, "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Monaco 4, pag. 103)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 12 e 16: il talento Aumento dei Punteggi o un altro talento di cui hai i requisiti.",
             "At levels 4, 8, 12 and 16: the Ability Score Improvement feat or another feat you qualify for."),
            no_row=True, covered_by="core/rules/level_choices.py (scelta asi); test_asi_at_4_8_12_16_and_the_19th_is_an_epic_boon_not_an_asi"),
    feature("slow_fall", CK, ED, 4, "Caduta Lenta / Slow Fall (Monaco 4, pag. 103)", ("Caduta Lenta", "Slow Fall"),
            ("Reazione quando cadi: il danno da caduta cala di 5 volte il tuo livello da monaco.",
             "Reaction when you fall: fall damage drops by 5 times your monk level."),
            "reaction", roll_options=(SLOW_FALL_OPTION,)),
    feature("extra_attack", CK, ED, 5, "Attacco Extra / Extra Attack (Monaco 5, pag. 103)", ("Attacco Extra", "Extra Attack"),
            ("Con l'azione Attacco attacchi due volte. Non si somma all'Attacco Extra di altre classi.",
             "You attack twice with the Attack action. Does not stack with other classes' Extra Attack."), attacks_per_action=2),
    feature("stunning_strike", CK, ED, 5, "Colpo Stordente / Stunning Strike (Monaco 5, pag. 103)", ("Colpo Stordente", "Stunning Strike"),
            ("Dopo un colpo a segno, 1 punto, una volta per turno: TS Costituzione. Fallito: stordito; superato: velocità dimezzata e vantaggio al prossimo attacco.",
             "After a hit, 1 point, once per turn: Constitution save. Failed: stunned; passed: Speed halved and advantage on the next attack."),
            roll_options=(STUNNING_STRIKE,)),
    feature("empowered_strikes", CK, ED, 6, "Colpi Potenziati / Empowered Strikes (Monaco 6, pag. 103)", ("Colpi Potenziati", "Empowered Strikes"),
            ("Il colpo senz'armi può infliggere danni da Forza al posto del tipo normale, a tua scelta. Non vale per le armi del Monaco.",
             "Your unarmed strike can deal Force damage instead of its normal type, your choice. It does not apply to Monk weapons."),
            roll_options=(FORCE_STRIKE,)),
    feature("evasion", CK, ED, 7, "Elusione / Evasion (Monaco 7, pag. 103)", ("Elusione", "Evasion"),
            ("Con un TS Destrezza per metà danni: TS superato nessun danno, fallito metà. Non vale se sei incapacitato.",
             "On a Dexterity save for half damage: no damage on a success, half on a failure. Not while incapacitated."),
            roll_options=(EVASION_SAVE, EVASION_SUCCESS, EVASION_FAILED)),
    feature("acrobatic_movement", CK, ED, 9, "Movimento Acrobatico / Acrobatic Movement (Monaco 9, pag. 103)",
            ("Movimento Acrobatico", "Acrobatic Movement"),
            ("Senza armatura né scudo, nel tuo turno ti muovi su pareti e liquidi senza cadere; il DM decide i dettagli.",
             "With no armor and no shield, on your turn you move along walls and across liquids without falling; the DM rules the details."),
            passive=True),
    feature("heightened_focus", CK, ED, 10, "Concentrazione Accresciuta / Heightened Focus (Monaco 10, pag. 103)",
            ("Concentrazione Accresciuta", "Heightened Focus"),
            ("Raffica di Colpi: tre colpi. Difesa Paziente a punto: PF temporanei pari a due dadi Arti Marziali. Passo del Vento a punto: porti con te una creatura.",
             "Flurry of Blows: three strikes. Patient Defense with a point: temporary hit points equal to two Martial Arts dice. Step of the Wind with a point: you carry a creature."),
            passive=True),
    feature("self_restoration", CK, ED, 10, "Autoguarigione / Self-Restoration (Monaco 10, pag. 103)",
            ("Autoguarigione", "Self-Restoration"),
            ("Una volta alla fine del tuo turno togli a te stesso Affascinato, Spaventato o Avvelenato; digiuno e sete non ti danno Spossatezza.",
             "Once at the end of your turn you remove Charmed, Frightened or Poisoned from yourself; going hungry or thirsty gives you no Exhaustion."),
            on_use=OnUse(once_per_turn=True, available=lambda c: bool(_restorable(c)), removal=ConditionRemoval(tuple(_RESTORABLE), ally=False, allowed=lambda c: tuple(_restorable(c))))),
    feature("deflect_energy", CK, ED, 13, "Deviare Energia / Deflect Energy (Monaco 13, pag. 103)", ("Deviare Energia", "Deflect Energy"),
            ("Deviare Attacchi vale per attacchi di ogni tipo di danno.", "Deflect Attacks works against attacks of any damage type."),
            passive=True),
    feature("disciplined_survivor", CK, ED, 14, "Sopravvissuto Disciplinato / Disciplined Survivor (Monaco 14, pag. 103)",
            ("Sopravvissuto Disciplinato", "Disciplined Survivor"),
            ("Competenza in tutti i tiri salvezza. Dopo un TS fallito spendi 1 punto e lo ripeti: vale il nuovo risultato.",
             "Proficiency in all saving throws. After a failed save spend 1 point to reroll it: the new result stands."),
            roll_options=(SURVIVOR_REROLL,),
            modifiers=(Modifier("save", _save_proficiency, when=_lacks_save_proficiency, source=f"feature:{CK}.disciplined_survivor"),)),
    feature("perfect_focus", CK, ED, 15, "Concentrazione Perfetta / Perfect Focus (Monaco 15, pag. 103)",
            ("Concentrazione Perfetta", "Perfect Focus"),
            ("Tirando l'Iniziativa senza usare Metabolismo Prodigioso, con 3 punti o meno torni a 4.",
             "When you roll Initiative without using Uncanny Metabolism, with 3 points or fewer you go back to 4."),
            roll_options=(PERFECT_FOCUS,)),
    feature("superior_defense", CK, ED, 18, "Difesa Superiore / Superior Defense (Monaco 18, pag. 103)",
            ("Difesa Superiore", "Superior Defense"),
            ("A inizio turno, 3 punti: per 1 minuto resistenza a ogni danno tranne la forza. Finisce se sei incapacitato.",
             "At the start of your turn, 3 points: for 1 minute resistance to all damage except Force. It ends if you are incapacitated."),
            "special", on_use=OnUse(cost=3, spends=KI, state=StateSpec(SUPERIOR_STATE, rounds=10, ends_on=("incapacitated", "manual"))),
            modifiers=tuple(Modifier(f"resistance:{t}", 1, when=lambda c: state_on(c, SUPERIOR_STATE), source=f"feature:{CK}.superior_defense")
                            for t in DAMAGE_TYPES if t != "force")),
    feature("epic_boon", CK, ED, 19, "Dono Epico / Epic Boon (Monaco 19, pag. 103)", ("Dono Epico", "Epic Boon"),
            ("Al 19° livello un talento Dono Epico o un altro talento di cui hai i requisiti; consigliato Offesa Irresistibile.",
             "At 19th level an Epic Boon feat or another feat you qualify for; Irresistible Offense is recommended."),
            no_row=True, covered_by="core/rules/level_choices.py (scelta epic_boon); test_asi_at_4_8_12_16_and_the_19th_is_an_epic_boon_not_an_asi"),
    feature("body_and_mind", CK, ED, 20, "Corpo e Mente / Body and Mind (Monaco 20, pag. 103)", ("Corpo e Mente", "Body and Mind"),
            ("Destrezza e Saggezza aumentano di 4, fino a 25.", "Dexterity and Wisdom increase by 4, up to 25."),
            ability_bonus={"dexterity": 4, "wisdom": 4}, ability_cap=25),
    feature("multiclassing", CK, ED, 1, "Multiclasse: Monaco / Multiclassing: Monk (Capitolo 2, pag. 44)",
            ("Multiclasse: Monaco", "Multiclassing: Monk"),
            ("Requisiti Destrezza 13 e Saggezza 13. Da multiclasse: solo il dado vita d8 e i privilegi del 1° livello, nessuna competenza.",
             "Requires Dexterity 13 and Wisdom 13. As a multiclass: only the d8 hit die and the 1st-level features, no proficiencies."),
            no_row=True, covered_by=f"{_ROWS} e webapp/src/data/multiclassPrereqs.ts (D2)"),
)



# ===========================================================================
# Sottoclassi (parte B)
# ===========================================================================

SUBS = {"mercy": "Guerriero della Misericordia", "shadow": "Guerriero dell'Ombra", "elements": "Guerriero degli Elementi",
        "open_hand": "Guerriero della Mano Aperta"}
ELEMENTS = ("acid", "cold", "fire", "lightning", "thunder")
_ELEMENT_LABELS = {"acid": _both("Acido", "Acid"), "cold": _both("Freddo", "Cold"), "fire": _both("Fuoco", "Fire"),
                   "lightning": _both("Fulmine", "Lightning"), "thunder": _both("Tuono", "Thunder")}
_ELEMENT_CHOICE = UseChoice("element", _both("Tipo di danno", "Damage type"), lambda _c: list(ELEMENTS),
                            lambda k: _ELEMENT_LABELS[k])
MERCY_POOL, ULTIMATE_USED = f"{CK}.flurry_of_healing_and_harm", "hand_of_ultimate_mercy_used"
ATTUNE_STATE, SHADOW_STRIKE_STATE = "elemental_attunement", "shadow_step_strike"
CLOAK_STATE, PALM_STATE = "cloak_of_shadows", "quivering_palm"


def _sub_row(sub: str, key: str, level: int, it: str, en: str, page: int, summary: tuple[str, str], action_type: str | None = None,
             names: tuple[str, str] | None = None, **kw: Any):
    """Riga di sottoclasse: il titolo è quello della mappatura, ``names`` il nome mostrato se diverso dal titolo."""
    return feature(key, CK, ED, level, f"{it} / {en} ({SUBS[sub]} {level}, pag. {page})", names or (it, en), summary, action_type,
                   subclass=sub, **kw)


def _wis(ctx: RuleContext) -> int:
    return _mod(ctx, "wisdom")


def _is_attuned(ctx: RuleContext) -> bool:
    return state_on(ctx, ATTUNE_STATE)


# ---------------------------------------------------------------------------
# Guerriero della Misericordia
# ---------------------------------------------------------------------------

def _harm_option(key: str, *, poison: bool, free: bool) -> RollOptionSpec:
    """Mano del Danno: dopo un colpo senz'armi a segno, un dado Arti Marziali più Saggezza di danni necrotici, una volta per turno.
    La versione ``free`` (liv. 11) vale solo sui colpi della Raffica e spende un uso della riserva, non un punto."""
    tail_it, tail_en = ((" Il bersaglio è avvelenato fino alla fine del tuo prossimo turno.",
                         " The target is poisoned until the end of your next turn.") if poison else ("", ""))
    return RollOptionSpec(
        key=key, phase="after_hit", rolls=("attack",), once_per_turn=True, group=f"{CK}.hand_of_harm", crit_doubles=False,
        cost=Cost(feature_key=MERCY_POOL if free else KI),
        available=(lambda c: _unarmed(c) and _flurry_hit(c)) if free else _unarmed,
        extra_dice=lambda c, _i: _die(c), bonus=lambda c, _i: _wis(c),
        label=_both(f"Mano del Danno{' (avvelena)' if poison else ''}: {'senza punti, ' if free else 'spendi 1 punto, '}danni necrotici extra",
                    f"Hand of Harm{' (poisons)' if poison else ''}: {'no points, ' if free else 'spend 1 point, '}extra necrotic damage"),
        effect=_say("Mano del Danno: un dado Arti Marziali più Saggezza di danni necrotici extra, una volta per turno." + tail_it,
                    "Hand of Harm: a Martial Arts die plus Wisdom of extra necrotic damage, once per turn." + tail_en),
        target_effect=(lambda _c, _i: TargetEffect(condition="poisoned", ends_at=_till_my_next_turn())) if poison else None)


HARM = _harm_option(f"{CK}.hand_of_harm", poison=False, free=False)
HARM_POISON = _harm_option(f"{CK}.hand_of_harm_poisoned", poison=True, free=False)
HARM_FREE = _harm_option(f"{CK}.hand_of_harm_free", poison=False, free=True)
HARM_FREE_POISON = _harm_option(f"{CK}.hand_of_harm_free_poisoned", poison=True, free=True)

_HEAL_MODES = {"self": _both("Cura te", "Heal yourself"), "other": _both("Cura un'altra creatura", "Heal another creature")}
_CURABLE = {"blinded": _both("Accecato", "Blinded"), "deafened": _both("Assordato", "Deafened"),
            "paralyzed": _both("Paralizzato", "Paralyzed"), "poisoned": _both("Avvelenato", "Poisoned"),
            "stunned": _both("Stordito", "Stunned")}


def _heal_message(_ctx: RuleContext, params: dict) -> dict[str, str] | None:
    if params.get("mode") == "other" and params.get("ally_healed"):
        return None  # PF e condizione hanno già i loro toast (``received``, ``removal``)
    if params.get("mode") == "other":
        return _both("La creatura toccata recupera i PF indicati: se siede alla serata e l'hai scelta, è già curata; altrimenti riferiscili al GM."
                     + (" La condizione scelta è tolta se hai scelto un personaggio della serata; altrimenti riferiscilo al GM." if params.get("condition") else ""),
                     "The touched creature regains the shown hit points: if it sits at the evening and you picked it, it is already healed; "
                     "otherwise tell the GM." + (" The chosen condition is removed if you picked a character at the table; otherwise tell the GM." if params.get("condition") else ""))
    return _both("Recuperi i PF indicati.", "You regain the shown hit points.")


def _spend_flurry_strike(ctx: RuleContext, _params: dict) -> None:
    """Il colpo sostituito dalla guarigione è uno di quelli della Raffica: ne scala uno dallo stato."""
    from core.rules.roll_options import _spend_state_token  # import locale: roll_options usa il catalogo
    _spend_state_token(ctx.char, FLURRY_STATE)


def _healing_use(*, slot: str | None, spends: str | None = None, in_flurry: bool = False, once: bool = False) -> OnUse:
    """Mano della Guarigione: un dado Arti Marziali più Saggezza. Dal 6° livello termina anche una condizione, a scelta
    del giocatore: su di sé la toglie l'app, su un altro la dice al GM (D1)."""
    return OnUse(
        slot=slot, spends=spends, cost=1, rolls=_die, heal=lambda c, rolled: rolled + _wis(c),
        heal_when=lambda _c, p: p.get("mode") == "self", heal_ally_when=lambda _c, p: p.get("mode") == "other",
        ally_modes=("other",), once_per_turn=once,
        available=(lambda c: state_on(c, FLURRY_STATE)) if in_flurry else None,
        effect=_spend_flurry_strike if in_flurry else None, message=_heal_message,
        removal=ConditionRemoval(tuple(_CURABLE), allowed=lambda c: tuple(_CURABLE) if c.class_level >= 6 else (), bound=True, optional=True),
        choices=(UseChoice("mode", _both("Chi recupera i PF", "Who regains the HP"), lambda _c: list(_HEAL_MODES), lambda k: _HEAL_MODES[k]),))


def _ultimate_message(ctx: RuleContext, _params: dict) -> dict[str, str]:
    return _both(f"Una creatura morta da meno di 24 ore torna in vita con i PF indicati (4d10 + {_wis(ctx)}) e senza Accecato, Assordato, "
                 "Paralizzato, Avvelenato e Stordito: riferiscilo al GM, l'app non ha la sua scheda.",
                 f"A creature dead for less than 24 hours returns to life with the shown hit points (4d10 + {_wis(ctx)}) and without "
                 "Blinded, Deafened, Paralyzed, Poisoned and Stunned: tell the GM, the app has no sheet for it.")


MERCY_ROWS = (
    _sub_row("mercy", "hand_of_harm", 3, "Mano del Danno", "Hand of Harm", 104,
             ("Dopo un colpo senz'armi a segno, 1 punto: un dado Arti Marziali più Saggezza di danni necrotici extra, una volta per turno.",
              "After an unarmed hit, 1 point: a Martial Arts die plus Wisdom of extra necrotic damage, once per turn."),
             roll_options=(HARM,)),
    _sub_row("mercy", "hand_of_healing", 3, "Mano della Guarigione", "Hand of Healing", 104,
             ("Azione Magia e 1 punto: tocchi una creatura, che recupera un dado Arti Marziali più Saggezza di PF.",
              "Magic action and 1 point: you touch a creature, which regains a Martial Arts die plus Wisdom hit points."),
             "action", on_use=_healing_use(slot="action", spends=KI)),
    _sub_row("mercy", "hand_of_healing_flurry", 3, "Mano della Guarigione", "Hand of Healing", 104,
             ("Durante la Raffica di Colpi sostituisci un colpo con questa cura, senza il punto: una volta per turno.",
              "During Flurry of Blows you swap one strike for this healing, with no point: once per turn."),
             names=("Mano della Guarigione (in Raffica)", "Hand of Healing (in Flurry)"),
             on_use=_healing_use(slot=None, in_flurry=True, once=True)),
    _sub_row("mercy", "implements_of_mercy", 3, "Strumenti della Misericordia", "Implements of Mercy", 104,
             ("Competenza in Intuizione, Medicina e nella borsa da erborista.",
              "Proficiency in Insight, Medicine and the herbalism kit."),
             proficiency_grants={"skills": ("insight", "medicine"), "tools": ("herbalism_kit",)}, passive=True),
    _sub_row("mercy", "physicians_touch", 6, "Tocco del Medico", "Physician's Touch", 104,
             ("Mano del Danno può avvelenare il bersaglio fino alla fine del tuo prossimo turno; Mano della Guarigione termina anche una condizione.",
              "Hand of Harm can poison the target until the end of your next turn; Hand of Healing also ends a condition."),
             roll_options=(HARM_POISON,)),
    _sub_row("mercy", "flurry_of_healing_and_harm", 11, "Raffica di Guarigione e Danno", "Flurry of Healing and Harm", 104,
             ("Nella Raffica ogni colpo può diventare Mano della Guarigione, e Mano del Danno vale senza punti: usi pari a Saggezza, riposo lungo.",
              "In Flurry every strike can become Hand of Healing, and Hand of Harm works with no points: Wisdom uses, long rest."),
             "special", uses=Uses(ability="wisdom", minimum=1), restoration="long_rest",
             roll_options=(HARM_FREE, HARM_FREE_POISON), on_use=_healing_use(slot=None, in_flurry=True)),
    _sub_row("mercy", "hand_of_ultimate_mercy", 17, "Mano della Misericordia Suprema", "Hand of Ultimate Mercy", 105,
             ("Azione Magia e 5 punti, una volta per riposo lungo: un cadavere morto da meno di 24 ore torna in vita con 4d10 più Saggezza PF.",
              "Magic action and 5 points, once per long rest: a creature dead less than 24 hours returns with 4d10 plus Wisdom hit points."),
             "action", on_use=OnUse(
                 slot="action", spends=KI, cost=5, rolls="4d10", gives=lambda c, rolled: rolled + _wis(c), message=_ultimate_message,
                 available=lambda c: not state_on(c, ULTIMATE_USED), state=StateSpec(ULTIMATE_USED, ends_on=("rest_long",)))),
)


# ---------------------------------------------------------------------------
# Guerriero dell'Ombra
# ---------------------------------------------------------------------------

def _darkvision_range(ctx: RuleContext) -> int:
    """Scurovisione 18 m (60 piedi); se già posseduta, la portata cresce di altri 18 m."""
    have = max((int(s.get("range_ft") or 0) for s in (ctx.char.settings or {}).get("senses") or []
                if isinstance(s, dict) and s.get("type") == "darkvision"), default=0)
    return 60 + have


def _begin_shadow_strike(ctx: RuleContext, _params: dict) -> None:
    begin_state(ctx.char, StateSpec(SHADOW_STRIKE_STATE, rounds=1, ends_on=("new_turn", "manual")), SHADOW_STRIKE.key,
                "Colpo dopo il Passo dell'Ombra")  # feature_key senza riga: il nome non si fonde con quello dello stato del Passo


SHADOW_STRIKE = RollOptionSpec(
    key=f"{CK}.shadow_step_strike", phase="before", rolls=("attack",), outside_action=True, cost=Cost(state_key=SHADOW_STRIKE_STATE),
    available=lambda c: _unarmed(c) and state_on(c, SHADOW_STRIKE_STATE),
    label=_both("Passo dell'Ombra Migliorato: colpo senz'armi subito dopo il teletrasporto",
                "Improved Shadow Step: unarmed strike right after the teleport"))

_CLOAK_MESSAGE = _both(
    "Per 1 minuto sei invisibile e in parte incorporeo: attraversi gli spazi occupati come terreno difficile e, se finisci il turno in uno, "
    "torni nell'ultimo spazio libero. Finisce se sei incapacitato o chiudi il turno in luce intensa (Termina a mano).",
    "For 1 minute you are invisible and partly incorporeal: you pass through occupied spaces as difficult terrain and, if you end your turn "
    "in one, you go back to the last free space. It ends if you are incapacitated or end your turn in bright light (End it by hand).")

SHADOW_ROWS = (
    _sub_row("shadow", "shadow_arts", 3, "Arti dell'Ombra", "Shadow Arts", 105,
             ("Oscurità con 1 punto, senza componenti; Scurovisione 18 m (altri 18 m se già ce l'hai); conosci Illusione Minore con Saggezza.",
              "Darkness for 1 point, no components; Darkvision 18 m (another 18 m if you already have it); you know Minor Illusion with Wisdom."),
             "action", passive=True, granted_spells=("darkness", "minor-illusion"), ki_spells=(KiSpell("darkness", 1),),
             modifiers=(Modifier("sense:darkvision", _darkvision_range, source=f"feature:{CK}.shadow_arts"),)),
    _sub_row("shadow", "shadow_step", 6, "Passo dell'Ombra", "Shadow Step", 105,
             ("Azione bonus, da luce fioca o oscurità: ti teletrasporti fino a 18 m in uno spazio libero anch'esso in luce fioca; vantaggio al prossimo attacco in mischia.",
              "Bonus action, from dim light or darkness: teleport up to 60 ft to a free space also in dim light; advantage on your next melee attack."),
             "bonus_action", roll_options=(STEP_ADVANTAGE,),
             on_use=OnUse(slot="bonus", choices=(_LIGHT_CHOICE,), state=StateSpec("shadow_step", rounds=1, ends_on=("new_turn", "manual")))),
    _sub_row("shadow", "improved_shadow_step", 11, "Passo dell'Ombra Migliorato", "Improved Shadow Step", 105,
             ("Con 1 punto il Passo dell'Ombra ignora la luce di partenza e arrivo, e subito dopo il teletrasporto fai un colpo senz'armi.",
              "With 1 point Shadow Step ignores the light at start and arrival, and right after the teleport you make an unarmed strike."),
             "bonus_action", roll_options=(SHADOW_STRIKE,),
             on_use=OnUse(slot="bonus", spends=KI, effect=_begin_shadow_strike,
                          state=StateSpec("shadow_step", rounds=1, ends_on=("new_turn", "manual")))),
    _sub_row("shadow", "cloak_of_shadows", 17, "Manto di Ombre", "Cloak of Shadows", 105,
             ("Azione Magia e 3 punti, da luce fioca o oscurità: per 1 minuto invisibile e in parte incorporeo. Finisce se incapacitato.",
              "Magic action and 3 points, from dim light or darkness: for 1 minute invisible and partly incorporeal. Ends if incapacitated."),
             "action", on_use=OnUse(
                 slot="action", spends=KI, cost=3, choices=(_LIGHT_CHOICE,), message=lambda _c, _p: _CLOAK_MESSAGE,
                 state=StateSpec(CLOAK_STATE, rounds=10, ends_on=("incapacitated", "manual"), condition="invisible"))),
    _sub_row("shadow", "shadow_flurry", 17, "Manto di Ombre", "Cloak of Shadows", 105,
             ("Con il manto addosso la Raffica di Colpi non costa punti (Raffica d'Ombra).",
              "With the cloak on, Flurry of Blows costs no points (Shadow Flurry)."),
             "bonus_action", names=("Raffica d'Ombra", "Shadow Flurry"),
             on_use=OnUse(slot="bonus", available=lambda c: state_on(c, CLOAK_STATE), state=_flurry_state)),
)


# ---------------------------------------------------------------------------
# Guerriero degli Elementi
# ---------------------------------------------------------------------------

def _element_option(kind: str) -> RollOptionSpec:
    label = _ELEMENT_LABELS[kind]
    return RollOptionSpec(
        key=f"{CK}.elemental_strike_{kind}", phase="before", rolls=("attack",), group=f"{CK}.elemental_strike", unarmed_damage_type=kind,
        defers_damage=True,  # apre la spinta dopo il colpo
        available=lambda c: _unarmed(c) and _is_attuned(c),
        label=_both(f"Colpi Elementali: il colpo senz'armi infligge danni da {label['it'].lower()}",
                    f"Elemental Strikes: the unarmed strike deals {label['en'].lower()} damage"))


def _push_available(ctx: RuleContext) -> bool:
    return _unarmed(ctx) and _is_attuned(ctx) and any(f"{CK}.elemental_strike_{k}" in ctx.confirmed for k in ELEMENTS)


ELEMENT_OPTIONS = tuple(_element_option(k) for k in ELEMENTS)
ELEMENT_PUSH = RollOptionSpec(
    key=f"{CK}.elemental_push", phase="after_hit", rolls=("attack",), available=_push_available,
    label=_both("Colpi Elementali: TS Forza o il bersaglio è spostato di 3 m", "Elemental Strikes: Strength save or the target is moved 10 ft"),
    effect=_dc_say("Il bersaglio fa un TS Forza CD {dc}: se fallisce lo sposti fino a 3 m verso di te o lontano da te.",
                   "The target makes a DC {dc} Strength save: on a failure you move it up to 10 ft toward or away from you."),
    target_effect=lambda ctx, _i: TargetEffect(save_ability="strength", save_dc=_ki_dc(ctx)))


def _burst_dice(ctx: RuleContext) -> str:
    return f"3{_die(ctx)[1:]}"


def _burst_message(ctx: RuleContext, params: dict) -> dict[str, str]:
    kind = _ELEMENT_LABELS[params["element"]]
    return _both(f"Sfera di 6 m entro 36 m: TS Destrezza CD {_ki_dc(ctx)}, danni da {kind['it'].lower()} pari ai dadi tirati, la metà se supera.",
                 f"6 m sphere within 36 m: DC {_ki_dc(ctx)} Dexterity save, {kind['en'].lower()} damage equal to the dice rolled, half on a success.")


def _chosen_resistance(ctx: RuleContext) -> str | None:
    state = next((s for s in ctx.char.active_states or [] if s.get("key") == ATTUNE_STATE), None)
    return (state.get("data") or {}).get("resistance") if state else None


def _choose_resistance(ctx: RuleContext, params: dict) -> None:
    """La resistenza scelta sta nei dati dello stato di Sintonia: finisce con lui e si cambia a ogni turno."""
    ctx.char.active_states = [{**s, "data": {**(s.get("data") or {}), "resistance": params["element"]}}
                              if s.get("key") == ATTUNE_STATE else s for s in ctx.char.active_states or []]


def _epitome_message(_ctx: RuleContext, params: dict) -> dict[str, str]:
    kind = _ELEMENT_LABELS[params["element"]]
    return _both(f"Resistenza ai danni da {kind['it'].lower()} finché la Sintonia dura; la cambi a inizio di ogni turno.",
                 f"Resistance to {kind['en'].lower()} damage while the Attunement lasts; you change it at the start of each turn.")


EPITOME_STRIKE = RollOptionSpec(
    key=f"{CK}.elemental_epitome_strike", phase="after_hit", rolls=("attack",), once_per_turn=True, crit_doubles=False,
    extra_dice=lambda c, _i: _die(c), available=lambda c: _unarmed(c) and _is_attuned(c),
    label=_both("Epitome Elementale: un dado Arti Marziali di danni extra, una volta per turno",
                "Elemental Epitome: an extra Martial Arts die of damage, once per turn"),
    effect=_say("Epitome Elementale: danni extra pari a un dado Arti Marziali, dello stesso tipo del colpo.",
                "Elemental Epitome: extra damage equal to a Martial Arts die, of the strike's damage type."))

def _stride_available(ctx: RuleContext) -> bool:
    return _is_attuned(ctx) and state_on(ctx, "step_of_the_wind")


def _stride_message(ctx: RuleContext, params: dict) -> dict[str, str]:
    kind = _ELEMENT_LABELS[params["element"]]
    return _both(f"Ogni creatura a tua scelta entro 1,5 m dal tuo percorso subisce il dado tirato in danni da {kind['it'].lower()}, "
                 "una volta per turno per creatura; non costa punti.",
                 f"Each creature of your choice you pass within 5 ft of takes the rolled die in {kind['en'].lower()} damage, "
                 "once per turn per creature; it costs no points.")


ELEMENTS_ROWS = (
    _sub_row("elements", "elemental_attunement", 3, "Sintonia Elementale", "Elemental Attunement", 106,
             ("A inizio turno, 1 punto: per 10 minuti portata +3 m ai colpi senz'armi e danni elementali a scelta, con spinta di 3 m (TS Forza).",
              "At the start of your turn, 1 point: for 10 minutes +3 m reach on unarmed strikes and elemental damage of your choice, with a 3 m push (Strength save)."),
             "special", roll_options=(*ELEMENT_OPTIONS, ELEMENT_PUSH),
             on_use=OnUse(spends=KI, check=lambda c, _p: (409, "feature_unavailable") if _is_attuned(c) else None,
                          state=StateSpec(ATTUNE_STATE, rounds=100, ends_on=("incapacitated", "manual"),
                                                     data={"reach_bonus_ft": 10}))),
    _sub_row("elements", "manipulate_elements", 3, "Manipolare gli Elementi", "Manipulate Elements", 106,
             ("Conosci il trucchetto Elementalismo, con Saggezza come caratteristica da incantatore.",
              "You know the Elementalism cantrip, with Wisdom as your spellcasting ability."),
             granted_spells=("elementalism",), passive=True),
    _sub_row("elements", "elemental_burst", 6, "Esplosione Elementale", "Elemental Burst", 106,
             ("Azione Magia e 2 punti: sfera di 6 m entro 36 m, TS Destrezza, tre dadi Arti Marziali del tipo scelto, metà se riuscito.",
              "Magic action and 2 points: 6 m sphere within 36 m, Dexterity save, three Martial Arts dice of the chosen type, half on a success."),
             "action", on_use=OnUse(
                 slot="action", spends=KI, cost=2, rolls=_burst_dice, choices=(_ELEMENT_CHOICE,), message=_burst_message,
                 target_effect=lambda c, _p: TargetEffect(save_ability="dexterity", save_dc=_ki_dc(c), on_failure_only=False,
                                                          damage_dice=_burst_dice(c)))),
    _sub_row("elements", "stride_of_the_elements", 11, "Passo degli Elementi", "Stride of the Elements", 106,
             ("Con la Sintonia Elementale attiva hai Velocità di Volo e di Nuoto pari alla tua Velocità.",
              "While Elemental Attunement is active you have Fly and Swim Speeds equal to your Speed."),
             modifiers=(Modifier("fly_speed", 1, when=_is_attuned, source=f"feature:{CK}.stride_of_the_elements"),
                        Modifier("swim_speed", 1, when=_is_attuned, source=f"feature:{CK}.stride_of_the_elements"))),
    _sub_row("elements", "destructive_stride", 17, "Passo Distruttivo", "Destructive Stride", 106,
             ("Con Sintonia e Passo del Vento attivi: ogni creatura a tua scelta che sfiori (entro 1,5 m) subisce un dado Arti Marziali di un tipo elementale a scelta, una volta per turno per creatura.",
              "With Attunement and Step of the Wind active: each creature of your choice you pass within 5 ft takes a Martial Arts die of an elemental type you choose, once per turn per creature."),
             "special", on_use=OnUse(cost=0, available=_stride_available, rolls=_die, choices=(_ELEMENT_CHOICE,), message=_stride_message),
             no_row=True, covered_by="riga Epitome Elementale (Guerriero degli Elementi 17), di cui è un effetto"),
    _sub_row("elements", "elemental_epitome", 17, "Epitome Elementale", "Elemental Epitome", 106,
             ("Con la Sintonia attiva: resistenza a un elemento a scelta, +6 m col Passo del Vento (danno ai vicini) e un dado Arti Marziali extra al turno.",
              "While attuned: resistance to a chosen element, +6 m with Step of the Wind (damage to nearby creatures) and an extra Martial Arts die per turn."),
             "special", roll_options=(EPITOME_STRIKE,),
             on_use=OnUse(cost=0, available=_is_attuned, effect=_choose_resistance, choices=(_ELEMENT_CHOICE,), message=_epitome_message),
             modifiers=(*(Modifier(f"resistance:{t}", 1, when=lambda c, t=t: _is_attuned(c) and _chosen_resistance(c) == t,
                                   source=f"feature:{CK}.elemental_epitome") for t in ELEMENTS),
                        Modifier("speed", 20, when=lambda c: _is_attuned(c) and state_on(c, "step_of_the_wind"),
                                 source=f"feature:{CK}.elemental_epitome"))),
)


# ---------------------------------------------------------------------------
# Guerriero della Mano Aperta
# ---------------------------------------------------------------------------

ADDLE_OPTION = _technique(
    "addle", ("Distrarre: il bersaglio non può fare attacchi di opportunità", "Addle: the target cannot make opportunity attacks"),
    ("Il bersaglio non può fare attacchi di opportunità fino all'inizio del suo prossimo turno. Nessun tiro salvezza.",
     "The target cannot make opportunity attacks until the start of its next turn. No saving throw."),
    lambda _ctx, _i: TargetEffect(condition="custom:no_opportunity_attacks", ends_at={"anchor": "owner", "edge": "start", "count": 1}))
PUSH_OPTION = _technique(
    "push", ("Spingere: TS Forza o il bersaglio è spinto di 4,5 m", "Push: Strength save or the target is pushed 15 ft"),
    ("Il bersaglio fa un TS Forza CD {dc}: se fallisce lo spingi fino a 4,5 m lontano da te.",
     "The target makes a DC {dc} Strength save: on a failure you push it up to 15 ft away from you."),
    lambda ctx, _i: TargetEffect(save_ability="strength", save_dc=_ki_dc(ctx)))
TOPPLE_OPTION = _technique(
    "topple", ("Atterrare: TS Destrezza o il bersaglio cade prono", "Topple: Dexterity save or the target falls prone"),
    ("Il bersaglio fa un TS Destrezza CD {dc}: se fallisce cade prono.", "The target makes a DC {dc} Dexterity save: on a failure it falls prone."),
    lambda ctx, _i: TargetEffect(condition="prone", save_ability="dexterity", save_dc=_ki_dc(ctx)))


def _fleet_available(ctx: RuleContext) -> bool:
    """Dopo un'azione bonus che non sia il Passo del Vento (che apre lo stato): non si concatena a se stesso."""
    return bool(_turn(ctx).get("bonus_used")) and not state_on(ctx, "step_of_the_wind")


PALM_START = RollOptionSpec(
    key=f"{CK}.quivering_palm_start", phase="after_hit", rolls=("attack",), cost=Cost(feature_key=KI, amount=4),
    available=lambda c: _unarmed(c) and not state_on(c, PALM_STATE),
    on_confirm=lambda _s, ctx, _i: begin_state(ctx.char, StateSpec(PALM_STATE, rounds=ctx.class_level * 14400, ends_on=("manual",)),
                                               f"{CK}.quivering_palm", "Palmo Tremante"),
    label=_both("Palmo Tremante: spendi 4 punti e avvia le vibrazioni nel bersaglio",
                "Quivering Palm: spend 4 points and start the vibrations in the target"),
    effect=_say("Vibrazioni avviate: durano tanti giorni quanti i tuoi livelli da monaco, su una sola creatura per volta.",
                "Vibrations started: they last as many days as your monk levels, on a single creature at a time."))


def _palm_end(**kw: Any) -> OnUse:
    """Fine delle vibrazioni: TS Costituzione del bersaglio, 10d12 danni da Forza, metà se lo supera. Vale con l'azione o con un attacco rinunciato."""
    return OnUse(
        rolls="10d12", ends_state=PALM_STATE, available=lambda c: state_on(c, PALM_STATE),
        message=lambda c, _p: _both(
            f"TS Costituzione CD {_ki_dc(c)} del bersaglio: se fallisce subisce i danni da Forza tirati, la metà se supera. Le vibrazioni finiscono.",
            f"The target's DC {_ki_dc(c)} Constitution save: on a failure it takes the Force damage rolled, half on a success. The vibrations end."),
        target_effect=lambda c, _p: TargetEffect(save_ability="constitution", save_dc=_ki_dc(c), on_failure_only=False, damage_dice="10d12"),
        **kw)


OPEN_HAND_ROWS = (
    _sub_row("open_hand", "open_hand_technique", 3, "Tecnica della Mano Aperta", "Open Hand Technique", 107,
             ("Su un colpo della Raffica di Colpi scegli un effetto: Distrarre, Spingere o Atterrare. Uno per colpo, nessun punto.",
              "On a Flurry of Blows hit you pick one effect: Addle, Push or Topple. One per hit, no points."), passive=True),
    _sub_row("open_hand", "addle", 3, "Distrarre", "Addle", 107,
             ("Sul colpo della Raffica: il bersaglio non può fare attacchi di opportunità fino all'inizio del suo prossimo turno.",
              "On a Flurry hit: the target cannot make opportunity attacks until the start of its next turn."),
             roll_options=(ADDLE_OPTION,)),
    _sub_row("open_hand", "push", 3, "Spingere", "Push", 107,
             ("Sul colpo della Raffica: TS Forza (CD 8 + Saggezza + competenza) o il bersaglio è spinto di 4,5 m.",
              "On a Flurry hit: Strength save (DC 8 + Wisdom + proficiency) or the target is pushed 15 ft."),
             roll_options=(PUSH_OPTION,)),
    _sub_row("open_hand", "topple", 3, "Atterrare", "Topple", 107,
             ("Sul colpo della Raffica: TS Destrezza (CD 8 + Saggezza + competenza) o il bersaglio cade prono.",
              "On a Flurry hit: Dexterity save (DC 8 + Wisdom + proficiency) or the target falls prone."),
             roll_options=(TOPPLE_OPTION,)),
    _sub_row("open_hand", "wholeness_of_body", 6, "Integrità del Corpo", "Wholeness of Body", 107,
             ("Azione bonus: tiri il dado Arti Marziali e recuperi quel risultato più Saggezza in PF (minimo 1). Usi pari a Saggezza, riposo lungo.",
              "Bonus action: roll the Martial Arts die and regain that result plus Wisdom hit points (minimum 1). Wisdom uses, long rest."),
             "bonus_action", uses=Uses(ability="wisdom", minimum=1), restoration="long_rest",
             on_use=OnUse(slot="bonus", rolls=_die, heal=lambda c, rolled: max(1, rolled + _wis(c)))),
    _sub_row("open_hand", "fleet_step", 11, "Passo Rapido", "Fleet Step", 107,
             ("Dopo un'azione bonus diversa dal Passo del Vento usi subito il Passo del Vento gratis (Scatto), senza un'altra azione bonus.",
              "After a bonus action other than Step of the Wind you use Step of the Wind for free (Dash), with no other bonus action."),
             "special", on_use=OnUse(available=_fleet_available, state=_step_state(False))),
    _sub_row("open_hand", "fleet_step_focus", 11, "Passo Rapido", "Fleet Step", 107,
             ("Come sopra, ma con 1 punto: Passo del Vento con Disimpegno e Scatto e salto doppio.",
              "As above, but with 1 point: Step of the Wind with Disengage and Dash and a doubled jump."),
             "special", names=("Passo Rapido (1 punto)", "Fleet Step (1 point)"),
             on_use=OnUse(spends=KI, available=_fleet_available, state=_step_state(True))),
    _sub_row("open_hand", "quivering_palm", 17, "Palmo Tremante", "Quivering Palm", 107,
             ("Dopo un colpo senz'armi, 4 punti: vibrazioni per giorni pari al livello. Con un'azione le termini: TS Costituzione, 10d12 Forza, metà se riuscito.",
              "After an unarmed hit, 4 points: vibrations for days equal to your level. As an action you end them: Constitution save, 10d12 Force, half on a success."),
             "action", roll_options=(PALM_START,), on_use=_palm_end(slot="action")),
    _sub_row("open_hand", "quivering_palm_attack", 17, "Palmo Tremante", "Quivering Palm", 107,
             ("Le vibrazioni si possono terminare anche rinunciando a uno degli attacchi dell'azione Attacco; stesso esito.",
              "The vibrations can also end by giving up one attack of the Attack action; same outcome."),
             "special", names=("Palmo Tremante (attacco rinunciato)", "Quivering Palm (attack given up)"),
             on_use=_palm_end(forgoes_attack=True)),
)

SUBCLASS_ROWS = MERCY_ROWS + SHADOW_ROWS + ELEMENTS_ROWS + OPEN_HAND_ROWS

FEATURES = BASE_ROWS + SUBCLASS_ROWS
