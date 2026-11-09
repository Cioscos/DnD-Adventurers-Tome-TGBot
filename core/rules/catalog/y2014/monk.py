"""Monaco 2014 e le sue tradizioni: Mano Aperta, Ombra e Quattro Elementi.

Valori dalla scheda ``docs/superpowers/rules/2014/classes/monk.md``; i testi sono nostri, mai quelli del manuale.
Tutte le spese di ki passano da una sola riga (``monk.ki``): ``OnUse.spends`` per i privilegi con un pulsante, ``Cost``
per le conferme al tiro, ``KiSpell`` per i lanci.
"""
from __future__ import annotations

from typing import Any

from core.data.damage_types import DAMAGE_TYPES
from core.rules.catalog._common import feature, state_on
from core.rules.states import begin_state
from core.rules.condition_removal import ConditionRemoval
from core.rules.types import (
    ChoiceSpec, Cost, KiSpell, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, UnarmoredAc, Uses,
    UseChoice,
)

ED, CK = "2014", "monk"
KI = f"{CK}.ki"
PD = f"{CK}.patient_defense"
FLURRY_STATE, MISSILE_STATE, EVASION_STATE = "flurry_of_blows", "deflected_missile", "evasion"


# ---------------------------------------------------------------------------
# Predicati comuni
# ---------------------------------------------------------------------------

def _bare(ctx: RuleContext) -> bool:
    """Nessuna armatura indossata e nessuno scudo impugnato: la condizione di molti privilegi del monaco."""
    return not any(i.is_equipped and i.item_type in ("armor", "shield") for i in ctx.char.items or [])


def _movement_bonus(ctx: RuleContext) -> int:
    """Piedi in più di Movimento Senza Armatura: 10 dal 2°, poi +5 ai livelli 6, 10, 14 e 18."""
    level = ctx.class_level
    return 10 + 5 * sum(level >= lv for lv in (6, 10, 14, 18))


def _turn(ctx: RuleContext) -> dict:
    return ctx.turn if ctx.turn is not None else (ctx.char.turn_state or {})


def _unarmed(ctx: RuleContext) -> bool:
    """Un colpo senz'armi: attacco di mischia senza oggetto e senza incantesimo."""
    return ctx.roll == "attack" and ctx.spell is None and ctx.item is None and ctx.attack_mode == "melee"


def _melee(ctx: RuleContext) -> bool:
    return ctx.roll == "attack" and ctx.spell is None and ctx.attack_mode in ("melee", "offhand")


def _can_act(ctx: RuleContext) -> bool:
    from core.rules.modifiers import is_incapacitated  # import locale: modifiers usa il catalogo
    return not is_incapacitated(ctx.char)


def _mod(ctx: RuleContext, ability: str) -> int:
    from core.game.stats import effective_ability_mod  # import locale: stats usa il catalogo
    return effective_ability_mod(ctx.char, ability)


def _ki_dc(ctx: RuleContext) -> int:
    """CD dei privilegi del ki: 8 + competenza + Saggezza."""
    return 8 + ctx.char.proficiency_bonus + _mod(ctx, "wisdom")


def _say(it: str, en: str):
    return lambda _ctx, _inputs: {"it": it, "en": en}


def _dc_say(it: str, en: str):
    """Esito con la CD del ki (il TS lo tira il bersaglio, lo segna il GM: D1)."""
    return lambda ctx, _inputs: {"it": it.format(dc=_ki_dc(ctx)), "en": en.format(dc=_ki_dc(ctx))}


def _till_my_next_turn() -> dict:
    return {"anchor": "source", "edge": "end", "count": 1}


def _attack_action_done(ctx: RuleContext) -> bool:
    """Subito dopo l'azione Attacco: almeno un attacco dell'azione è già stato fatto in questo turno."""
    return int(_turn(ctx).get("action_attacks") or 0) >= 1


# ---------------------------------------------------------------------------
# Arti Marziali, Raffica di Colpi
# ---------------------------------------------------------------------------

def _bonus_strike_available(ctx: RuleContext) -> bool:
    from core.rules.weapons import martial_arts_level  # import locale: weapons usa stats, che usa il catalogo
    return _unarmed(ctx) and bool(_turn(ctx).get("martial_attack")) and martial_arts_level(ctx.char) > 0


MARTIAL_BONUS = RollOptionSpec(
    key=f"{CK}.martial_arts_bonus", phase="before", rolls=("attack",), slot="bonus", available=_bonus_strike_available,
    label={"it": "Arti Marziali: colpo senz'armi extra come azione bonus (dopo l'azione Attacco)",
           "en": "Martial Arts: extra unarmed strike as a bonus action (after the Attack action)"})

FLURRY_STRIKE = RollOptionSpec(
    key=f"{CK}.flurry_strike", phase="before", rolls=("attack",), outside_action=True, cost=Cost(state_key=FLURRY_STATE),
    defers_damage=True,  # apre la Tecnica della Mano Aperta dopo il colpo
    available=lambda c: _unarmed(c) and state_on(c, FLURRY_STATE),
    label={"it": "Raffica di Colpi: uno dei due colpi senz'armi", "en": "Flurry of Blows: one of the two unarmed strikes"})


# ---------------------------------------------------------------------------
# Passo del Vento, Deviare Proiettili, Caduta Lenta
# ---------------------------------------------------------------------------

_STEP_MODES = {"dash": {"it": "Scatto", "en": "Dash"}, "disengage": {"it": "Disimpegno", "en": "Disengage"}}


def _step_state(_ctx: RuleContext, params: dict) -> StateSpec:
    return StateSpec("step_of_the_wind", rounds=1, ends_on=("new_turn", "manual"),
                     data={"mode": params["mode"], "jump_doubled": True})


def _catch_missile(_session: Any, ctx: RuleContext) -> None:
    """Il danno è sceso a 0: il proiettile si può afferrare (se è piccolo e c'è una mano libera, lo dichiara il giocatore)."""
    begin_state(ctx.char, StateSpec(MISSILE_STATE, rounds=1, ends_on=("new_turn", "manual")), f"{CK}.deflect_missiles",
                "Deviare Proiettili")


DEFLECT_OPTION = RollOptionSpec(
    key=f"{CK}.deflect_missiles", phase="damage_in", rolls=("damage_taken",), slot="reaction", available=_can_act,
    extra_dice=lambda _c, _i: "1d10", bonus=lambda c, _i: _mod(c, "dexterity") + c.class_level,
    offered_on_damage=False, on_zero_damage=_catch_missile,
    label={"it": "Deviare Proiettili: un attacco a distanza con un'arma ti ha colpito? Reazione, riduce il danno di 1d10 + Destrezza + livello",
           "en": "Deflect Missiles: did a ranged weapon attack hit you? Reaction, reduces the damage by 1d10 + Dexterity + level"})


DEFLECT_THROW = RollOptionSpec(
    key=f"{CK}.deflect_missiles_throw", phase="before", rolls=("attack",), outside_action=True,
    cost=Cost(feature_key=KI, state_key=MISSILE_STATE), offered_on_damage=True, ranged_unarmed=True,
    available=lambda c: c.roll == "attack" and c.spell is None and c.item is None and state_on(c, MISSILE_STATE),
    effect=_say("Attacco a distanza con il proiettile afferrato, senza arma in mano: Destrezza, dado di Arti Marziali e competenza; "
                "gittata 6 m, lunga 18 m. Conta come arma da monaco.",
                "Ranged attack with the caught missile, no weapon in hand: Dexterity, Martial Arts die and proficiency; "
                "range 20 ft, long range 60 ft. It counts as a monk weapon."),
    label={"it": "Deviare Proiettili: rilancia il proiettile afferrato (1 ki, nella stessa reazione)",
           "en": "Deflect Missiles: throw back the caught missile (1 ki, as part of the same reaction)"})

SLOW_FALL_OPTION = RollOptionSpec(
    key=f"{CK}.slow_fall", phase="damage_in", rolls=("damage_taken",), slot="reaction", available=_can_act,
    bonus=lambda c, _i: 5 * c.class_level, offered_on_damage=False,
    label={"it": "Caduta Lenta: il danno viene da una caduta? Reazione, riduce il danno di 5 × livello da monaco",
           "en": "Slow Fall: is the damage from a fall? Reaction, reduces the damage by 5 × monk level"})


# ---------------------------------------------------------------------------
# Colpo Stordente, Elusione, Mente Lucida, Anima Adamantina, Perfezione Interiore, Corpo Vuoto
# ---------------------------------------------------------------------------

STUNNING_STRIKE = RollOptionSpec(
    key=f"{CK}.stunning_strike", phase="after_hit", rolls=("attack",), cost=Cost(feature_key=KI), available=_melee,
    label={"it": "Colpo Stordente: spendi 1 ki, TS Costituzione o il bersaglio è stordito",
           "en": "Stunning Strike: spend 1 ki, Constitution save or the target is stunned"},
    effect=_dc_say("Il bersaglio fa un TS Costituzione CD {dc}: se fallisce è stordito fino alla fine del tuo prossimo turno.",
                   "The target makes a DC {dc} Constitution save: on a failure it is stunned until the end of your next turn."),
    target_effect=lambda ctx, _i: TargetEffect(condition="stunned", save_ability="constitution", save_dc=_ki_dc(ctx),
                                               ends_at=_till_my_next_turn()))


def _evasion_started(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    begin_state(ctx.char, StateSpec(EVASION_STATE, rounds=1, ends_on=("new_turn", "manual")), f"{CK}.evasion", "Elusione")


EVASION_SAVE = RollOptionSpec(
    key=f"{CK}.evasion", phase="before", rolls=("save",), available=lambda c: c.ability == "dexterity" and _can_act(c),
    on_confirm=_evasion_started,
    label={"it": "Elusione: l'effetto dimezza i danni con un TS Destrezza?", "en": "Evasion: does the effect halve damage on a Dexterity save?"},
    effect=_say("Elusione: se superi il TS non subisci danni, se lo fallisci subisci la metà. Applica l'esito al danno.",
                "Evasion: if you pass the save you take no damage, on a failure you take half. Apply the outcome to the damage."))
EVASION_SUCCESS = RollOptionSpec(
    key=f"{CK}.evasion_success", phase="damage_in", rolls=("damage_taken",), multiplier=0, group="evasion",
    cost=Cost(state_key=EVASION_STATE), available=lambda c: state_on(c, EVASION_STATE) and _can_act(c),
    label={"it": "Elusione: hai superato il TS, nessun danno", "en": "Evasion: you passed the save, no damage"})
EVASION_FAILED = RollOptionSpec(
    key=f"{CK}.evasion_failed", phase="damage_in", rolls=("damage_taken",), multiplier=0.5, group="evasion",
    cost=Cost(state_key=EVASION_STATE), available=lambda c: state_on(c, EVASION_STATE) and _can_act(c),
    label={"it": "Elusione: hai fallito il TS, metà del danno", "en": "Evasion: you failed the save, half damage"})


def _mind_conditions(ctx: RuleContext) -> list[str]:
    return [c for c in ("charmed", "frightened") if (ctx.char.conditions or {}).get(c)]


_MIND_LABELS = {"charmed": {"it": "Affascinato", "en": "Charmed"}, "frightened": {"it": "Spaventato", "en": "Frightened"}}


def _save_proficiency(ctx: RuleContext) -> int:
    return ctx.char.proficiency_bonus


def _lacks_save_proficiency(ctx: RuleContext) -> bool:
    return (ctx.roll in ("save", "concentration") and bool(ctx.ability)
            and not (ctx.char.saving_throws or {}).get(ctx.ability))


DIAMOND_REROLL = RollOptionSpec(
    key=f"{CK}.diamond_soul", phase="after_roll", after="reroll", rolls=("save",), cost=Cost(feature_key=KI),
    label={"it": "Anima Adamantina: spendi 1 ki e ripeti il tiro salvezza fallito (vale il nuovo risultato)",
           "en": "Diamond Soul: spend 1 ki and reroll the failed saving throw (the new result stands)"})


def _ki_row(ctx: RuleContext) -> Any:
    return next((a for a in ctx.char.abilities if a.feature_key == KI), None)


def _no_ki_left(ctx: RuleContext) -> bool:
    row = _ki_row(ctx)
    return row is not None and row.max_uses is not None and (row.uses or 0) == 0


def _perfect_self_confirmed(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    row = _ki_row(ctx)
    if row is not None and row.max_uses is not None:
        row.uses = min(row.max_uses, 4)


PERFECT_SELF = RollOptionSpec(
    key=f"{CK}.perfect_self", phase="before", rolls=("initiative",), available=_no_ki_left,
    on_confirm=_perfect_self_confirmed,
    label={"it": "Perfezione Interiore: non hai più ki, recuperane 4", "en": "Perfect Self: you have no ki left, regain 4"},
    effect=_say("Perfezione Interiore: recuperi 4 punti ki.", "Perfect Self: you regain 4 ki points."))


def _empty_body_state(_ctx: RuleContext, _params: dict) -> StateSpec:
    """Un minuto (10 round): invisibile, e la resistenza (nei modificatori) dura quanto lui."""
    return StateSpec("empty_body", rounds=10, condition="invisible")


# ---------------------------------------------------------------------------
# Via della Mano Aperta
# ---------------------------------------------------------------------------

def _flurry_hit(ctx: RuleContext) -> bool:
    """Il colpo a segno è uno di quelli della Raffica di Colpi (confermato nel primo tempo dell'attacco)."""
    return ctx.roll == "attack" and f"{CK}.flurry_strike" in ctx.confirmed


def _technique(key: str, label: tuple[str, str], effect: tuple[str, str], target) -> RollOptionSpec:
    return RollOptionSpec(
        key=f"{CK}.open_hand_{key}", phase="after_hit", rolls=("attack",), group="open_hand", available=_flurry_hit,
        label={"it": label[0], "en": label[1]}, effect=_dc_say(*effect), target_effect=target)


OPEN_HAND_OPTIONS = (
    _technique("prone", ("Tecnica della Mano Aperta: TS Destrezza o il bersaglio cade prono",
                         "Open Hand Technique: Dexterity save or the target falls prone"),
               ("Il bersaglio fa un TS Destrezza CD {dc}: se fallisce cade prono.",
                "The target makes a DC {dc} Dexterity save: on a failure it falls prone."),
               lambda ctx, _i: TargetEffect(condition="prone", save_ability="dexterity", save_dc=_ki_dc(ctx))),
    _technique("push", ("Tecnica della Mano Aperta: TS Forza o il bersaglio è spinto di 4,5 m",
                        "Open Hand Technique: Strength save or the target is pushed 15 ft"),
               ("Il bersaglio fa un TS Forza CD {dc}: se fallisce lo spingi fino a 4,5 m lontano da te.",
                "The target makes a DC {dc} Strength save: on a failure you push it up to 15 ft away from you."),
               lambda ctx, _i: TargetEffect(save_ability="strength", save_dc=_ki_dc(ctx))),
    _technique("no_reactions", ("Tecnica della Mano Aperta: il bersaglio non può fare reazioni",
                                "Open Hand Technique: the target cannot take reactions"),
               ("Il bersaglio non può fare reazioni fino alla fine del tuo prossimo turno. Nessun TS (CD ki {dc} per gli altri effetti).",
                "The target cannot take reactions until the end of your next turn. No save (ki DC {dc} for the other effects)."),
               lambda _ctx, _i: TargetEffect(condition="custom:no_reactions", ends_at=_till_my_next_turn())),
)

PALM_START = RollOptionSpec(
    key=f"{CK}.quivering_palm_start", phase="after_hit", rolls=("attack",), cost=Cost(feature_key=KI, amount=3),
    available=lambda c: _unarmed(c) and not state_on(c, "quivering_palm"),
    on_confirm=lambda _s, ctx, _i: begin_state(
        ctx.char, StateSpec("quivering_palm", rounds=ctx.class_level * 14400, ends_on=("manual",)),
        f"{CK}.quivering_palm", "Palmo Tremante"),
    label={"it": "Palmo Tremante: spendi 3 ki e avvia le vibrazioni nel bersaglio", "en": "Quivering Palm: spend 3 ki and start the vibrations in the target"},
    effect=_say("Vibrazioni avviate: durano tanti giorni quanti i tuoi livelli da monaco, su un solo bersaglio.",
                "Vibrations started: they last as many days as your monk levels, on a single target."))


def _tranquility_state(ctx: RuleContext) -> StateSpec:
    return StateSpec("tranquility", ends_on=("attack", "cast", "rest_long"), data={"dc": _ki_dc(ctx), "save": "wisdom", "others": [f"{CK}.tranquility"]})


# ---------------------------------------------------------------------------
# Via dell'Ombra
# ---------------------------------------------------------------------------

_LIGHT_LABEL = {"dim_or_dark": {"it": "Origine e destinazione in luce fioca o oscurità", "en": "Origin and destination in dim light or darkness"}}
_LIGHT_CHOICE = UseChoice("light", {"it": "Luce", "en": "Light"}, lambda _c: ["dim_or_dark"], lambda k: _LIGHT_LABEL[k])

STEP_ADVANTAGE = RollOptionSpec(
    key=f"{CK}.shadow_step_advantage", phase="before", rolls=("attack",), mode="advantage", cost=Cost(state_key="shadow_step"),
    available=lambda c: _melee(c) and state_on(c, "shadow_step"),
    label={"it": "Passo dell'Ombra: primo attacco in mischia dopo il teletrasporto (vantaggio)", "en": "Shadow Step: first melee attack after the teleport (advantage)"})

OPPORTUNIST_OPTION = RollOptionSpec(
    key=f"{CK}.opportunist", phase="before", rolls=("attack",), slot="reaction", available=_melee, offered_on_damage=False,
    label={"it": "Opportunista: una creatura a 1,5 m da te è stata colpita da un altro? Reazione, attacco in mischia contro di lei",
           "en": "Opportunist: was a creature within 5 ft of you hit by someone else? Reaction, melee attack against it"})


# ---------------------------------------------------------------------------
# Via dei Quattro Elementi
# ---------------------------------------------------------------------------

GROUP = "elemental_disciplines"
SUFFIX = "(Monaco 3, Via dei Quattro Elementi, pag. 94)"
# (chiave, it, en, livello minimo, incantesimo, ki)
SPELL_DISCIPLINES = (
    ("ride_the_wind", "Cavalcare il Vento", "Ride the Wind", 11, "fly", 4, ("Volare", "Fly")),
    ("sweeping_cinder_strike", "Colpo della Cenere Turbinante", "Sweeping Cinder Strike", 3, "burning-hands", 2, ("Mani brucianti", "Burning Hands")),
    ("eternal_mountain_defense", "Difesa della Montagna Eterna", "Eternal Mountain Defense", 17, "stoneskin", 5, ("Pelle di pietra", "Stoneskin")),
    ("flames_of_the_phoenix", "Fiamme della Fenice", "Flames of the Phoenix", 11, "fireball", 4, ("Palla di fuoco", "Fireball")),
    ("river_of_hungry_flame", "Fiume della Fiamma Famelica", "River of Hungry Flame", 17, "wall-of-fire", 5, ("Muro di fuoco", "Wall of Fire")),
    ("gong_of_the_summit", "Gong della Sommità", "Gong of the Summit", 6, "shatter", 3, ("Frantumare", "Shatter")),
    ("clench_of_the_north_wind", "Morsa del Vento del Nord", "Clench of the North Wind", 6, "hold-person", 3, ("Bloccare persone", "Hold Person")),
    ("wave_of_rolling_earth", "Onda della Terra Tumultuosa", "Wave of Rolling Earth", 17, "wall-of-stone", 6, ("Muro di pietra", "Wall of Stone")),
    ("mist_stance", "Postura della Nebbia", "Mist Stance", 11, "gaseous-form", 4, ("Forma gassosa", "Gaseous Form")),
    ("fist_of_four_thunders", "Pugno dei Quattro Tuoni", "Fist of Four Thunders", 3, "thunderwave", 2, ("Onda tonante", "Thunderwave")),
    ("breath_of_winter", "Soffio dell'Inverno", "Breath of Winter", 17, "cone-of-cold", 6, ("Cono di freddo", "Cone of Cold")),
    ("rush_of_the_gale_spirits", "Spiriti della Burrasca Impetuosa", "Rush of the Gale Spirits", 3, "gust-of-wind", 2, ("Folata di vento", "Gust of Wind")),
)
# Il manuale ammette i ki in più solo se l'incantesimo «possiede un effetto potenziato» («Ai Livelli Superiori»): non
# l'hanno Pelle di pietra, Muro di pietra, Forma gassosa e Folata di vento; Volare lo ha, ma solo per creature in più
# e Cavalcare il Vento lo lancia su di te soltanto.
NO_UPCAST = frozenset({"ride_the_wind", "eternal_mountain_defense", "wave_of_rolling_earth", "mist_stance", "rush_of_the_gale_spirits"})
ONLY_YOURSELF = {
    "ride_the_wind": ("Volare su te stesso", "Fly on yourself"),
    "eternal_mountain_defense": ("Pelle di pietra su te stesso", "Stoneskin on yourself"),
    "mist_stance": ("Forma gassosa su te stesso", "Gaseous Form on yourself"),
}
OTHER_DISCIPLINE_LEVELS = {"shape_the_flowing_river": 3, "water_whip": 3, "fist_of_unbroken_air": 3, "fangs_of_the_fire_snake": 3}
DISCIPLINE_LEVELS = {**{d[0]: d[3] for d in SPELL_DISCIPLINES}, **OTHER_DISCIPLINE_LEVELS}


def _discipline_options(ctx: RuleContext) -> list[str]:
    return [key for key, level in DISCIPLINE_LEVELS.items() if level <= ctx.class_level]


def _spell_discipline(key: str, it: str, en: str, level: int, spell: str, cost: int, names: tuple[str, str]):
    return feature(
        f"discipline_{key}", CK, ED, level, f"{it} / {en} {SUFFIX}", (it, en),
        (f"Con {cost} ki lanci {ONLY_YOURSELF.get(key, (names[0],))[0]}, senza componenti materiali."
         + ("" if key in NO_UPCAST else " Dal 5° livello ki extra ne alzano il livello, entro il tetto."),
         f"With {cost} ki you cast {ONLY_YOURSELF.get(key, (None, names[1]))[1]}, without material components."
         + ("" if key in NO_UPCAST else " From 5th level extra ki raise its level, up to the cap.")),
        subclass="four_elements", option_group=GROUP, option_key=key, passive=True, granted_spells=(spell,),
        ki_spells=(KiSpell(spell, cost, upcast=key not in NO_UPCAST, self_only=key in ONLY_YOURSELF),))


_WHIP_EFFECTS = {"prone": {"it": "Prono", "en": "Prone"}, "pull": {"it": "Tirato fino a 7,5 m verso di te", "en": "Pulled up to 25 ft toward you"}}


def _whip_effect(ctx: RuleContext, params: dict) -> TargetEffect:
    """Frusta d'Acqua: se il TS fallisce il giocatore sceglie prono o tirato; tirato non è una condizione."""
    return TargetEffect(condition="prone" if params.get("effect") == "prone" else None, save_ability="dexterity", save_dc=_ki_dc(ctx))


def _ki_attack(ability: str) -> OnUse:
    """Frusta d'Acqua e Pugno dell'Aria Inviolabile: azione, 2 ki più extra, 3d10 più 1d10 per ki extra, TS del bersaglio (CD ki).
    L'esito (contundenti, metà danni se supera, traino o spinta) lo dice la nota ``notes`` del privilegio."""
    if ability == "dexterity":
        return OnUse(slot="action", spends=KI, choose_amount=True, min_amount=2, rolls_by_amount=lambda _ctx, n: f"{n + 1}d10",
                     notes=lambda _c, _p: ["water_whip"], target_effect=_whip_effect,
                     choices=(UseChoice("effect", {"it": "Se il TS fallisce", "en": "On a failed save"},
                                        lambda _c: list(_WHIP_EFFECTS), lambda k: _WHIP_EFFECTS[k]),))
    return OnUse(slot="action", spends=KI, choose_amount=True, min_amount=2, rolls_by_amount=lambda _ctx, n: f"{n + 1}d10",
                 notes=lambda _c, _p: ["fist_of_unbroken_air"],
                 target_effect=lambda ctx, _p: TargetEffect(condition="prone", save_ability=ability, save_dc=_ki_dc(ctx)))


FANGS_STATE = "fangs_of_the_fire_snake"
FANGS_EXTRA = RollOptionSpec(
    key=f"{CK}.fangs_extra_damage", phase="after_hit", rolls=("attack",), cost=Cost(feature_key=KI),
    extra_dice=lambda _c, _i: "1d10", available=lambda c: _unarmed(c) and state_on(c, FANGS_STATE),
    label={"it": "Zanne del Serpente di Fuoco: spendi 1 ki, +1d10 danni da fuoco", "en": "Fangs of the Fire Snake: spend 1 ki, +1d10 fire damage"})


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

FEATURES = (
    feature("hit_points", CK, ED, 1, "Punti Ferita / Hit Points (Monaco 1, pag. 90)", ("Punti Ferita", "Hit Points"),
            ("Dado vita d8; al 1° livello 8 + Costituzione, poi d8 (o 5) + Costituzione.",
             "Hit die d8; level 1 gives 8 + Constitution, then d8 (or 5) + Constitution."), no_row=True,
            covered_by="api/routers/classes.py create_class_for_character e total_base_hp; test_hit_points_use_the_d8_and_follow_constitution"),
    feature("proficiencies", CK, ED, 1, "Competenze / Proficiencies (Monaco 1, pag. 90)", ("Competenze", "Proficiencies"),
            ("Armi semplici e spade corte, TS Forza e Destrezza, 2 abilità fra sei, uno strumento. Nessuna armatura.",
             "Simple weapons and shortswords, Strength and Dexterity saves, 2 skills from six, one tool. No armor."),
            no_row=True, covered_by="core/rules/proficiencies.py (class_proficiencies) e la scelta ClassSkillChoice; "
                                    "lo strumento è in lavori-successivi (R40); test_class_proficiencies_first_class_and_multiclass"),
    feature("equipment", CK, ED, 1, "Equipaggiamento / Equipment (Monaco 1, pag. 90)", ("Equipaggiamento", "Equipment"),
            ("Dotazione iniziale: spada corta o un'arma semplice, dotazione da avventuriero o da esploratore, 10 dardi.",
             "Starting gear: a shortsword or a simple weapon, a dungeoneer's or explorer's pack, 10 darts."),
            no_row=True, covered_by="lavori-successivi"),
    feature("unarmored_defense", CK, ED, 1, "Difesa Senza Armatura / Unarmored Defense (Monaco 1, pag. 91)",
            ("Difesa Senza Armatura", "Unarmored Defense"),
            ("Senza armatura né scudo la CA è 10 + Destrezza + Saggezza. Non si somma alla Difesa Senza Armatura di un'altra classe.",
             "With no armor and no shield your AC is 10 + Dexterity + Wisdom. It does not stack with another class's Unarmored Defense."),
            unarmored=UnarmoredAc(("dexterity", "wisdom"), no_shield=True)),
    feature("martial_arts", CK, ED, 1, "Arti Marziali / Martial Arts (Monaco 1, pag. 91)", ("Arti Marziali", "Martial Arts"),
            ("Senza armatura né scudo, colpi senz'armi e armi da monaco usano Destrezza e il dado d4 (d6 al 5°, d8 all'11°, d10 al 17°).",
             "With no armor and no shield, unarmed strikes and monk weapons use Dexterity and the d4 (d6 at 5th, d8 at 11th, d10 at 17th)."),
            roll_options=(MARTIAL_BONUS,)),
    feature("ki", CK, ED, 2, "Ki / Ki (Monaco 2, pag. 91)", ("Ki", "Ki"),
            ("Riserva pari al livello da monaco, torna con un riposo breve o lungo. CD 8 + competenza + Saggezza. Alimenta Raffica di Colpi, Difesa Paziente, Passo del Vento.",
             "Pool equal to your monk level, back after a short or long rest. DC 8 + proficiency + Wisdom. Fuels Flurry of Blows, Patient Defense, Step of the Wind."),
            uses=Uses(table={2: 0}, per_level=1), restoration="short_rest", dc_ability="wisdom"),
    feature("flurry_of_blows", CK, ED, 2, "Raffica di Colpi / Flurry of Blows (Monaco 2, pag. 91)",
            ("Raffica di Colpi", "Flurry of Blows"),
            ("Subito dopo l'azione Attacco, azione bonus e 1 ki: due colpi senz'armi, ognuno con il proprio tiro per colpire.",
             "Right after the Attack action, bonus action and 1 ki: two unarmed strikes, each with its own attack roll."),
            "bonus_action", roll_options=(FLURRY_STRIKE,),
            on_use=OnUse(slot="bonus", spends=KI, available=_attack_action_done,
                         state=StateSpec(FLURRY_STATE, rounds=1, ends_on=("new_turn", "manual"), data={"charges": 2}))),
    feature("patient_defense", CK, ED, 2, "Difesa Paziente / Patient Defense (Monaco 2, pag. 91)",
            ("Difesa Paziente", "Patient Defense"),
            ("Azione bonus e 1 ki: Schivata. Chi ti attacca ha svantaggio al tiro per colpire fino al tuo prossimo turno.",
             "Bonus action and 1 ki: Dodge. Attackers have disadvantage on their attack rolls until your next turn."),
            "bonus_action",
            on_use=OnUse(slot="bonus", spends=KI, state=StateSpec(
                "patient_defense", rounds=1, ends_on=("new_turn", "incapacitated", "manual"), data={"others": [PD]}))),
    feature("step_of_the_wind", CK, ED, 2, "Passo del Vento / Step of the Wind (Monaco 2, pag. 91)",
            ("Passo del Vento", "Step of the Wind"),
            ("Azione bonus e 1 ki: Disimpegno o Scatto, a scelta; la distanza di salto raddoppia per il turno.",
             "Bonus action and 1 ki: Disengage or Dash, your choice; your jump distance doubles for the turn."),
            "bonus_action",
            on_use=OnUse(slot="bonus", spends=KI, state=_step_state, choices=(UseChoice(
                "mode", {"it": "Azione", "en": "Action"}, lambda _c: list(_STEP_MODES), lambda k: _STEP_MODES[k]),))),
    feature("unarmored_movement", CK, ED, 2, "Movimento Senza Armatura / Unarmored Movement (Monaco 2, pag. 91)",
            ("Movimento Senza Armatura", "Unarmored Movement"),
            ("Senza armatura né scudo la velocità cresce: +3 m dal 2°, +4,5 m al 6°, +6 m al 10°, +7,5 m al 14°, +9 m al 18°.",
             "With no armor and no shield your speed grows: +10 ft at 2nd, +15 ft at 6th, +20 ft at 10th, +25 ft at 14th, +30 ft at 18th."),
            modifiers=(Modifier("speed", _movement_bonus, when=_bare, source=f"feature:{CK}.unarmored_movement"),)),
    feature("unarmored_movement_9", CK, ED, 9, "Movimento Senza Armatura / Unarmored Movement (Monaco 2, pag. 91)",
            ("Movimento Senza Armatura Migliorato", "Improved Unarmored Movement"),
            ("Nel tuo turno ti muovi su superfici verticali e liquide senza cadere durante il movimento.",
             "On your turn you move along vertical surfaces and across liquids without falling during the move."),
            passive=True),
    feature("monastic_tradition", CK, ED, 3, "Tradizione Monastica / Monastic Tradition (Monaco 3, pag. 91)",
            ("Tradizione Monastica", "Monastic Tradition"),
            ("Al 3° livello si sceglie Mano Aperta, Ombra o Quattro Elementi; i privilegi arrivano ai livelli 3, 6, 11 e 17.",
             "At 3rd level you choose Open Hand, Shadow or Four Elements; their features arrive at levels 3, 6, 11 and 17."),
            no_row=True, covered_by="core/rules/subclasses.py (match_subclass) e il campo sottoclasse della classe"),
    feature("deflect_missiles", CK, ED, 3, "Deviare Proiettili / Deflect Missiles (Monaco 3, pag. 91)",
            ("Deviare Proiettili", "Deflect Missiles"),
            ("Reazione a un attacco a distanza con arma: il danno cala di 1d10 + Destrezza + livello. A 0, con 1 ki lo rilanci.",
             "Reaction to a ranged weapon attack: damage drops by 1d10 + Dexterity + level. At 0, spend 1 ki to throw it back."),
            "reaction", roll_options=(DEFLECT_OPTION, DEFLECT_THROW)),
    feature("ability_score_improvement", CK, ED, 4,
            "Aumento dei Punteggi di Caratteristica / Ability Score Improvement (Monaco 4, pag. 91)",
            ("Aumento dei Punteggi di Caratteristica", "Ability Score Improvement"),
            ("Ai livelli 4, 8, 12, 16 e 19: +2 a un punteggio o +1 a due, oppure un talento; massimo 20.",
             "At levels 4, 8, 12, 16 and 19: +2 to one score or +1 to two, or a feat; maximum 20."), no_row=True,
            covered_by="core/rules/level_choices.py (scelta asi); test_asi_choice_is_pending_at_each_asi_level"),
    feature("slow_fall", CK, ED, 4, "Caduta Lenta / Slow Fall (Monaco 4, pag. 91)", ("Caduta Lenta", "Slow Fall"),
            ("Reazione quando cadi: il danno da caduta cala di 5 volte il tuo livello da monaco.",
             "Reaction when you fall: fall damage drops by 5 times your monk level."),
            "reaction", roll_options=(SLOW_FALL_OPTION,)),
    feature("extra_attack", CK, ED, 5, "Attacco Extra / Extra Attack (Monaco 5, pag. 92)", ("Attacco Extra", "Extra Attack"),
            ("Con l'azione Attacco attacchi due volte. Non si somma all'Attacco Extra di altre classi.",
             "You attack twice with the Attack action. Does not stack with other classes' Extra Attack."),
            attacks_per_action=2),
    feature("stunning_strike", CK, ED, 5, "Colpo Stordente / Stunning Strike (Monaco 5, pag. 92)",
            ("Colpo Stordente", "Stunning Strike"),
            ("Dopo un colpo a segno con arma da mischia spendi 1 ki: TS Costituzione (CD ki) o il bersaglio è stordito fino alla fine del tuo prossimo turno.",
             "After a melee weapon hit spend 1 ki: Constitution save (ki DC) or the target is stunned until the end of your next turn."),
            roll_options=(STUNNING_STRIKE,)),
    feature("ki_empowered_strikes", CK, ED, 6, "Colpi Ki Potenziati / Ki-Empowered Strikes (Monaco 6, pag. 92)",
            ("Colpi Ki Potenziati", "Ki-Empowered Strikes"),
            ("I colpi senz'armi contano come magici per superare resistenze e immunità a danni non magici.",
             "Your unarmed strikes count as magical for overcoming resistance and immunity to nonmagical damage."),
            magic_unarmed=True),
    feature("evasion", CK, ED, 7, "Elusione / Evasion (Monaco 7, pag. 92)", ("Elusione", "Evasion"),
            ("Con un TS Destrezza per metà danni: TS superato nessun danno, fallito metà. Non vale se sei incapacitato.",
             "On a Dexterity save for half damage: no damage on a success, half on a failure. Not while incapacitated."),
            roll_options=(EVASION_SAVE, EVASION_SUCCESS, EVASION_FAILED)),
    feature("stillness_of_mind", CK, ED, 7, "Mente Lucida / Stillness of Mind (Monaco 7, pag. 92)",
            ("Mente Lucida", "Stillness of Mind"),
            ("Con un'azione termini un effetto che ti rende affascinato o spaventato.",
             "As an action you end one effect on you that makes you charmed or frightened."),
            "action",
            on_use=OnUse(slot="action", available=lambda c: bool(_mind_conditions(c)), removal=ConditionRemoval(("charmed", "frightened"), ally=False,
                                                  allowed=lambda c: tuple(_mind_conditions(c))))),
    feature("purity_of_body", CK, ED, 10, "Purezza del Corpo / Purity of Body (Monaco 10, pag. 92)",
            ("Purezza del Corpo", "Purity of Body"),
            ("Immune a veleno (danni e condizione) e malattie.", "Immune to poison (damage and condition) and disease."),
            condition_immunities=("poisoned",),
            modifiers=(Modifier("immunity:poison", 1, source=f"feature:{CK}.purity_of_body"),)),
    feature("tongue_of_the_sun_and_moon", CK, ED, 13,
            "Lingua del Sole e della Luna / Tongue of the Sun and Moon (Monaco 13, pag. 92)",
            ("Lingua del Sole e della Luna", "Tongue of the Sun and Moon"),
            ("Capisci ogni linguaggio parlato e chiunque capisca un linguaggio capisce te.",
             "You understand every spoken language, and any creature that understands a language understands you."),
            passive=True),
    feature("diamond_soul", CK, ED, 14, "Anima Adamantina / Diamond Soul (Monaco 14, pag. 92)",
            ("Anima Adamantina", "Diamond Soul"),
            ("Competenza in tutti i tiri salvezza. Dopo un TS fallito spendi 1 ki e lo ripeti: vale il nuovo risultato.",
             "Proficiency in all saving throws. After a failed save spend 1 ki to reroll it: the new result stands."),
            roll_options=(DIAMOND_REROLL,),
            modifiers=(Modifier("save", _save_proficiency, when=_lacks_save_proficiency, source=f"feature:{CK}.diamond_soul"),)),
    feature("timeless_body", CK, ED, 15, "Corpo Senza Tempo / Timeless Body (Monaco 15, pag. 92)",
            ("Corpo Senza Tempo", "Timeless Body"),
            ("Non invecchi per via magica e non hai più bisogno di cibo e acqua.",
             "You cannot be aged magically and no longer need food or water."),
            passive=True),
    feature("empty_body", CK, ED, 18, "Corpo Vuoto / Empty Body (Monaco 18, pag. 92)", ("Corpo Vuoto", "Empty Body"),
            ("Azione e 4 ki: invisibile per 1 minuto, con resistenza a ogni danno tranne la forza. Con 8 ki lanci proiezione astrale, senza portare con te altre creature.",
             "Action and 4 ki: invisible for 1 minute, resisting all damage except force. With 8 ki you cast astral projection, without bringing other creatures along."),
            "action", granted_spells=("astral-projection",), ki_spells=(KiSpell("astral-projection", 8, self_only=True),),
            modifiers=tuple(Modifier(f"resistance:{t}", 1, when=lambda c: state_on(c, "empty_body"),
                                     source=f"feature:{CK}.empty_body") for t in DAMAGE_TYPES if t != "force"),
            on_use=OnUse(slot="action", cost=4, spends=KI, state=_empty_body_state)),
    feature("perfect_self", CK, ED, 20, "Perfezione Interiore / Perfect Self (Monaco 20, pag. 92)",
            ("Perfezione Interiore", "Perfect Self"),
            ("Tirando l'iniziativa senza punti ki, ne recuperi 4.", "When you roll initiative with no ki points left, you regain 4."),
            roll_options=(PERFECT_SELF,)),
    # Via della Mano Aperta
    feature("open_hand_technique", CK, ED, 3, "Tecnica della Mano Aperta / Open Hand Technique (Monaco 3, pag. 92)",
            ("Tecnica della Mano Aperta", "Open Hand Technique"),
            ("Un colpo a segno della Raffica di Colpi impone una scelta: TS Destrezza o prono, TS Forza o spinta di 4,5 m, nessuna reazione.",
             "A Flurry of Blows hit imposes one choice: Dexterity save or prone, Strength save or a 15 ft push, no reactions."),
            subclass="open_hand", roll_options=OPEN_HAND_OPTIONS),
    feature("wholeness_of_body", CK, ED, 6, "Integrità del Corpo / Wholeness of Body (Monaco 6, pag. 92)",
            ("Integrità del Corpo", "Wholeness of Body"),
            ("Con un'azione recuperi PF pari a 3 volte il tuo livello da monaco. Un uso, torna con un riposo lungo.",
             "As an action you regain hit points equal to three times your monk level. One use, back after a long rest."),
            "action", subclass="open_hand", uses=Uses(table={6: 1}), restoration="long_rest",
            on_use=OnUse(slot="action", heal=lambda ctx, _rolled: 3 * ctx.class_level)),
    feature("tranquility", CK, ED, 11, "Tranquillità / Tranquility (Monaco 11, pag. 93)", ("Tranquillità", "Tranquility"),
            ("Alla fine di un riposo lungo ottieni Santuario fino al riposo lungo successivo (CD 8 + competenza + Saggezza). Finisce se attacchi o lanci.",
             "At the end of a long rest you gain Sanctuary until your next long rest (DC 8 + proficiency + Wisdom). It ends if you attack or cast."),
            subclass="open_hand", passive=True, long_rest_state=_tranquility_state),
    feature("quivering_palm", CK, ED, 17, "Palmo Tremante / Quivering Palm (Monaco 17, pag. 93)",
            ("Palmo Tremante", "Quivering Palm"),
            ("Dopo un colpo senz'armi a segno, 3 ki avviano vibrazioni per giorni pari al livello. Con un'azione le termini: TS Costituzione, a 0 PF o 10d10 necrotici.",
             "After an unarmed hit, 3 ki start vibrations for days equal to your level. As an action you end them: Constitution save, 0 HP or 10d10 necrotic."),
            "action", subclass="open_hand", roll_options=(PALM_START,),
            on_use=OnUse(slot="action", rolls="10d10", ends_state="quivering_palm", notes=lambda _c, _p: ["quivering_palm"],
                         available=lambda c: state_on(c, "quivering_palm"),
                         target_effect=lambda ctx, _p: TargetEffect(save_ability="constitution", save_dc=_ki_dc(ctx), on_failure_only=False, damage_dice="10d10"))),

    # Via dell'Ombra
    feature("shadow_arts", CK, ED, 3, "Arti dell'Ombra / Shadow Arts (Monaco 3, pag. 93)", ("Arti dell'Ombra", "Shadow Arts"),
            ("Con 2 ki lanci oscurità, passare senza tracce, scurovisione o silenzio senza componenti materiali. Conosci illusione minore.",
             "With 2 ki you cast darkness, pass without trace, darkvision or silence without material components. You know minor illusion."),
            "action", subclass="shadow", passive=True,
            granted_spells=("darkness", "pass-without-trace", "darkvision", "silence", "minor-illusion"),
            ki_spells=tuple(KiSpell(s, 2) for s in ("darkness", "pass-without-trace", "darkvision", "silence"))),
    feature("shadow_step", CK, ED, 6, "Passo dell'Ombra / Shadow Step (Monaco 6, pag. 93)", ("Passo dell'Ombra", "Shadow Step"),
            ("Azione bonus, da luce fioca o oscurità: ti teletrasporti fino a 18 m in uno spazio libero pure in luce fioca; vantaggio al primo attacco in mischia.",
             "Bonus action, from dim light or darkness: teleport up to 60 ft to an unoccupied space also in dim light; advantage on your first melee attack."),
            "bonus_action", subclass="shadow", roll_options=(STEP_ADVANTAGE,),
            on_use=OnUse(slot="bonus", choices=(_LIGHT_CHOICE,),
                         state=StateSpec("shadow_step", rounds=1, ends_on=("new_turn", "manual")))),
    feature("cloak_of_shadows", CK, ED, 11, "Manto di Ombre / Cloak of Shadows (Monaco 11, pag. 93)",
            ("Manto di Ombre", "Cloak of Shadows"),
            ("Con un'azione, in luce fioca o oscurità, diventi invisibile finché non attacchi, non lanci un incantesimo o non entri in luce intensa.",
             "As an action, in dim light or darkness, you become invisible until you attack, cast a spell or enter bright light."),
            "action", subclass="shadow",
            on_use=OnUse(slot="action", choices=(_LIGHT_CHOICE,),
                         state=StateSpec("cloak_of_shadows", ends_on=("attack", "cast", "manual"), condition="invisible"))),
    feature("opportunist", CK, ED, 17, "Opportunista / Opportunist (Monaco 17, pag. 93)", ("Opportunista", "Opportunist"),
            ("Reazione: una creatura entro 1,5 m da te è colpita da un altro (non te): le fai un attacco in mischia.",
             "Reaction: a creature within 5 ft of you is hit by someone other than you: make a melee attack against it."),
            "reaction", subclass="shadow", roll_options=(OPPORTUNIST_OPTION,)),

    # Via dei Quattro Elementi
    feature("disciple_of_the_elements", CK, ED, 3, "Discepolo degli Elementi / Disciple of the Elements (Monaco 3, pag. 93)",
            ("Discepolo degli Elementi", "Disciple of the Elements"),
            ("Conosci Sintonia Elementale e una disciplina; una in più ai livelli 6, 11 e 17, e puoi sostituirne una. Costi in ki, con tetto per livello.",
             "You know Elemental Attunement and one discipline; one more at levels 6, 11 and 17, and you may swap one. Ki costs, capped by level."),
            subclass="four_elements", no_row=True,
            choices=(ChoiceSpec(group=GROUP, levels={3: 1, 6: 2, 11: 3, 17: 4}, options=_discipline_options, replaceable=True),),
            covered_by="ChoiceSpec elemental_disciplines di questa riga, le righe delle discipline e i lanci col ki (KiSpell); "
                       "test_2014_monk_elements.py"),
    feature("elemental_attunement", CK, ED, 3, "Sintonia Elementale / Elemental Attunement (Monaco 3, Via dei Quattro Elementi, pag. 94)",
            ("Sintonia Elementale", "Elemental Attunement"),
            ("Disciplina sempre nota, senza costo in ki: piccoli effetti elementali (luce, fuoco, freddo, un cubo di 30 cm) che narra il DM.",
             "Always known, no ki cost: minor elemental effects (light, fire, cold, a 1 ft cube) that the DM narrates."),
            subclass="four_elements", passive=True),
    *[_spell_discipline(*d) for d in SPELL_DISCIPLINES],
    feature("discipline_shape_the_flowing_river", CK, ED, 3, f"Forma del Fiume Fluente / Shape the Flowing River {SUFFIX}",
            ("Forma del Fiume Fluente", "Shape the Flowing River"),
            ("Azione e 1 ki: modelli ghiaccio o acqua in un'area di 9 m per lato entro 36 m, senza intrappolare né ferire. Il DM decide la forma.",
             "Action and 1 ki: shape ice or water in a 30 ft square within 120 ft, without trapping or harming. The DM rules the shape."),
            "action", subclass="four_elements", option_group=GROUP, option_key="shape_the_flowing_river",
            on_use=OnUse(slot="action", spends=KI)),
    feature("discipline_water_whip", CK, ED, 3, f"Frusta d'Acqua / Water Whip {SUFFIX}", ("Frusta d'Acqua", "Water Whip"),
            ("Azione, 2 ki più extra: una creatura entro 9 m, TS Destrezza (CD ki). Fallisce: 3d10 (+1d10 per ki extra), prono o tirata di 7,5 m. Supera: metà.",
             "Action, 2 ki plus extra: a creature within 30 ft, Dexterity save (ki DC). Fail: 3d10 (+1d10 per extra ki), prone or pulled 25 ft. Pass: half."),
            "action", subclass="four_elements", option_group=GROUP, option_key="water_whip", on_use=_ki_attack("dexterity")),
    feature("discipline_fist_of_unbroken_air", CK, ED, 3, f"Pugno dell'Aria Inviolabile / Fist of Unbroken Air {SUFFIX}",
            ("Pugno dell'Aria Inviolabile", "Fist of Unbroken Air"),
            ("Azione, 2 ki più extra: una creatura entro 9 m, TS Forza (CD ki). Fallisce: 3d10 (+1d10 per ki extra), spinta di 6 m e prono. Supera: metà.",
             "Action, 2 ki plus extra: a creature within 30 ft, Strength save (ki DC). Fail: 3d10 (+1d10 per extra ki), pushed 20 ft and prone. Pass: half."),
            "action", subclass="four_elements", option_group=GROUP, option_key="fist_of_unbroken_air", on_use=_ki_attack("strength")),
    feature("discipline_fangs_of_the_fire_snake", CK, ED, 3, f"Zanne del Serpente di Fuoco / Fangs of the Fire Snake {SUFFIX}",
            ("Zanne del Serpente di Fuoco", "Fangs of the Fire Snake"),
            ("Con l'azione Attacco, 1 ki: portata dei senz'armi +3 m per il turno e danno da fuoco. Su un colpo a segno, un altro ki aggiunge 1d10 fuoco.",
             "With the Attack action, 1 ki: unarmed reach +10 ft for the turn and fire damage. On a hit, another ki adds 1d10 fire."),
            subclass="four_elements", option_group=GROUP, option_key="fangs_of_the_fire_snake", roll_options=(FANGS_EXTRA,),
            on_use=OnUse(spends=KI, state=StateSpec(
                FANGS_STATE, rounds=1, ends_on=("new_turn", "manual"), data={"unarmed_damage_type": "fire", "reach_bonus_ft": 10}))),

    feature("multiclassing", CK, ED, 1, "Multiclasse: Monaco / Multiclassing: Monk (Capitolo 6, pag. 163)",
            ("Multiclasse: Monaco", "Multiclassing: Monk"),
            ("Requisiti Destrezza 13 e Saggezza 13. Da multiclasse: armi semplici e spade corte, nessuna armatura.",
             "Requires Dexterity 13 and Wisdom 13. As a multiclass: simple weapons and shortswords, no armor."),
            no_row=True, covered_by="core/rules/proficiencies.py (as_multiclass) e webapp/src/data/multiclassPrereqs.ts (D2)"),
)
