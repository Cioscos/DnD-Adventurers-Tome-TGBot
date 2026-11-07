"""Monaco 2024, parte A (base della classe). Le sottoclassi (Guerriero della Misericordia, dell'Ombra, degli Elementi e della
Mano Aperta) sono la parte B: aggiungono le loro righe a ``SUBCLASS_ROWS`` con ``subclass=`` (chiavi di
``core/rules/subclasses.py``: mercy, shadow, elements, open_hand).

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
    DIAMOND_REROLL, EVASION_FAILED, EVASION_SAVE, EVASION_SUCCESS, FLURRY_STATE, FLURRY_STRIKE, SLOW_FALL_OPTION, _bare,
    _can_act, _ki_dc, _ki_row, _lacks_save_proficiency, _mod, _movement_bonus, _save_proficiency, _say, _unarmed,
)
from core.rules.states import begin_state
from core.rules.types import (
    Cost, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, UnarmoredAc, Uses, UseChoice,
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
            "reaction", on_use=OnUse(
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
            on_use=OnUse(once_per_turn=True, available=lambda c: bool(_restorable(c)), clears_condition="condition",
                         choices=(UseChoice("condition", _both("Condizione", "Condition"), _restorable, lambda k: _RESTORABLE[k]),))),
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

SUBCLASS_ROWS: tuple = ()  # parte B

FEATURES = BASE_ROWS + SUBCLASS_ROWS
