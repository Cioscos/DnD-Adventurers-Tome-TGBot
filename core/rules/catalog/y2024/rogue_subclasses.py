"""Ladro 2024, parte B (sottoclassi): Mistificatore Arcano, Assassino, Coltello dell'Anima, Furfante.

Valori dalla scheda ``docs/superpowers/rules/2024/classes/rogue.md``; i testi sono nostri, mai quelli del manuale.
Dalla parte A (``rogue.py``) si riusano le opzioni del Colpo Astuto (``_cunning``, ``POISON``, ``TRIP``) e Attacco Furtivo
(``SNEAK``). Le Lame Psichiche sono un colpo senz'armi con dado e tipo propri (``unarmed_dice``, ``finesse_unarmed``). Il kit
da Avvelenatore dell'Assassino e la Velocità della Mira Errante stanno in ``rogue.py`` (``_has_poisoners_kit``,
``steady_aim_keeps_speed``); sintonia a 4 oggetti e tiro 1d6 delle cariche in ``api/services/item_charges.py``.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from core.rules.catalog._common import feature, save_spell
from core.rules.catalog.y2014.rogue import (
    MAGICAL_AMBUSH_CAST, SPELL_THIEF_USE, _cunning_label, _knows_mage_hand, _proficient_skill_check,
)
from core.rules.catalog.y2024.rogue import CK, ED, POISON, SNEAK, TRIP, _both, _cunning, _dc, _subclass_from
from core.rules.weapons import _arm_vex
from core.rules.types import Cost, Modifier, OnUse, RollOptionSpec, RuleContext, StateSpec, TargetEffect, Uses, UseChoice, UseToggle

PSI = f"{CK}.psionic_power"
BLADE, BLADE_BONUS = f"{CK}.psychic_blade", f"{CK}.psychic_blade_bonus"
BLADE_USED = "blade_used"


def _sub(label: tuple[str, str], subclass: str):
    """Fabbrica delle righe di una sottoclasse: il titolo è quello della scheda, con il nome italiano della sottoclasse."""
    def make(key: str, level: int, it: str, en: str, page: int, summary: tuple[str, str], action_type: str | None = None,
             parent: str | None = None, **kw: Any):
        where = f"{parent + ', ' if parent else ''}{label[0]} {level}, pag. {page}"
        return feature(key, CK, ED, level, f"{it} / {en} ({where})", (it, en), summary, action_type, subclass=subclass, **kw)
    return make


# ---------------------------------------------------------------------------
# Mistificatore Arcano
# ---------------------------------------------------------------------------

MAGICAL_AMBUSH = replace(
    MAGICAL_AMBUSH_CAST, available=lambda c: c.spell is not None and save_spell(c.spell) and bool((c.char.conditions or {}).get("invisible")),
    label=_both("Imboscata Magica: sei Invisibile? Il bersaglio ha svantaggio ai TS contro questo incantesimo, fino a fine turno",
                "Magical Ambush: are you Invisible? The target has disadvantage on saves against this spell until the end of the turn"))

VERSATILE_TRIP = RollOptionSpec(
    key=f"{CK}.versatile_trip", phase="after_hit", rolls=("attack",), needs=TRIP.key,
    available=lambda c: _subclass_from(c, "arcane_trickster", 13) and _knows_mage_hand(c),
    label=_both("Ingannatore Versatile: Sgambetto anche su una seconda creatura entro 1,5 m dalla mano spettrale",
                "Versatile Trickster: Trip also a second creature within 5 ft of the spectral hand"),
    target_effect=TRIP.target_effect)

_at = _sub(("Mistificatore Arcano", "Arcane Trickster"), "arcane_trickster")
ARCANE_TRICKSTER = (
    _at("arcane_trickster_spellcasting", 3, "Incantesimi", "Spellcasting", 132,
        ("Terzo di incantatore con Intelligenza, lista del Mago. Trucchetti 3 (Mano Magica più 2; 4 al 10°); preparati da 3 a 13.",
         "Third-caster with Intelligence, Wizard list. Cantrips 3 (Mage Hand plus 2; 4 at 10th); prepared spells 3 to 13."),
        no_row=True, covered_by="core/rules/spellcasting.py (known_limits, prepared_limit, slots_for, caster_stats); "
                                "test_arcane_trickster_slots_cantrips_and_prepared_follow_the_2024_table"),
    _at("mage_hand_legerdemain", 3, "Gioco di Prestigio della Mano Magica", "Mage Hand Legerdemain", 133,
        ("Mano Magica come azione bonus; la mano spettrale è Invisibile, la controlli con un'azione bonus e con essa fai prove di Rapidità di Mano.",
         "Mage Hand as a bonus action; the spectral hand is Invisible, you control it with a bonus action and make Sleight of Hand checks through it."),
        "bonus_action", on_use=OnUse(slot="bonus", available=_knows_mage_hand, notes=lambda _c, _p: ["mage_hand_control"])),
    _at("magical_ambush", 9, "Imboscata Magica", "Magical Ambush", 133,
        ("Lanciando un incantesimo da Invisibile, il bersaglio ha svantaggio ai TS contro di esso fino a fine turno.",
         "Cast a spell at a creature while Invisible: its saves against that spell have disadvantage until turn end."),
        roll_options=(MAGICAL_AMBUSH,), passive=True),
    _at("versatile_trickster", 13, "Ingannatore Versatile", "Versatile Trickster", 133,
        ("Con Sgambetto del Colpo Astuto, con Mano Magica attiva, colpisci anche una seconda creatura entro 1,5 m dalla mano spettrale.",
         "With Trip from Cunning Strike, with Mage Hand active, you also affect a second creature within 5 ft of the spectral hand."),
        roll_options=(VERSATILE_TRIP,), passive=True),
    _at("spell_thief", 17, "Ladro di Incantesimi", "Spell Thief", 133,
        ("Reazione, una volta per riposo lungo: il lanciatore fa un TS Intelligenza; se fallisce annulli l'effetto e ruba l'incantesimo per 8 ore.",
         "Reaction, once per long rest: the caster makes an Intelligence save; on a failure you cancel the effect and steal the spell for 8 hours."),
        "reaction", uses=Uses(table={17: 1}), restoration="long_rest", on_use=SPELL_THIEF_USE, dc_ability="intelligence"),
)


# ---------------------------------------------------------------------------
# Assassino
# ---------------------------------------------------------------------------

ASSASSINATE_ADVANTAGE = RollOptionSpec(
    key=f"{CK}.assassinate_advantage", phase="before", rolls=("attack",), mode="advantage",
    label=_both("Assassinare: è il primo round e il bersaglio non ha ancora agito? Vantaggio al tiro per colpire",
                "Assassinate: is it the first round and has the target not acted yet? Advantage on the attack roll"))
ASSASSINATE_DAMAGE = RollOptionSpec(
    key=f"{CK}.assassinate_damage", phase="after_hit", rolls=("attack",), needs=SNEAK, bonus=lambda c, _i: c.class_level,
    label=_both("Assassinare: primo round, l'Attacco Furtivo ha colpito? Danni extra pari al livello da ladro, dello stesso tipo dell'arma",
                "Assassinate: first round, did Sneak Attack hit? Extra damage equal to your rogue level, of the weapon's type"))
ENVENOM = RollOptionSpec(
    key=f"{CK}.envenom_weapons", phase="after_hit", rolls=("attack",), needs=POISON.key, extra_dice=lambda _c, _i: "2d6",
    crit_doubles=False,  # il danno viene dal TS fallito, non dai dadi dell'attacco: il critico non lo raddoppia
    label=_both("Armi Velenose: il TS contro Veleno è fallito? 2d6 danni da veleno in più (ignorano la Resistenza al veleno)",
                "Envenom Weapons: did the Poison save fail? 2d6 extra poison damage (ignores Poison resistance)"))


def _death_strike_effect(ctx: RuleContext, _inputs: dict) -> dict[str, str]:
    dc = _dc(ctx)
    return _both(f"Colpo Mortale: il bersaglio fa un TS Costituzione, CD {dc}. Se fallisce i danni dell'attacco sono raddoppiati.",
                 f"Death Strike: the target makes a Constitution save, DC {dc}. On a failure the attack's damage is doubled.")


DEATH_STRIKE = RollOptionSpec(
    key=f"{CK}.death_strike", phase="after_hit", rolls=("attack",), needs=SNEAK, multiplier=2, effect=_death_strike_effect,
    label=_both("Colpo Mortale: primo round e il bersaglio ha fallito il TS Costituzione (CD 8 + Destrezza + competenza)? Danni raddoppiati",
                "Death Strike: first round and the target failed its Constitution save (DC 8 + Dexterity + proficiency)? Damage doubled"))

_as = _sub(("Assassino", "Assassin"), "assassin")
ASSASSIN = (
    _as("assassinate", 3, "Assassinare", "Assassinate", 134,
        ("Vantaggio all'Iniziativa; nel primo round vantaggio contro chi non ha agito, e l'Attacco Furtivo a segno aggiunge il livello da ladro.",
         "Advantage on Initiative; in the first round advantage against creatures that haven't acted, and a Sneak Attack hit adds your rogue level."),
        modifiers=(Modifier("advantage", 1, when=lambda c: c.roll == "initiative", source=f"feature:{CK}.assassinate"),),
        roll_options=(ASSASSINATE_ADVANTAGE, ASSASSINATE_DAMAGE), passive=True),
    _as("assassins_tools", 3, "Strumenti dell'Assassino", "Assassin's Tools", 134,
        ("Kit da Travestimento e Kit da Avvelenatore, con la competenza; il secondo serve all'opzione Veleno.",
         "Disguise Kit and Poisoner's Kit, with proficiency; the second is needed for the Poison option."),
        proficiency_grants={"tools": ("disguise_kit", "poisoners_kit")}, passive=True),
    _as("infiltration_expertise", 9, "Maestria nell'Infiltrazione", "Infiltration Expertise", 134,
        ("Mira Errante: la Mira Costante non azzera la Velocità. Imitazione Magistrale: dopo 1 ora di studio imiti voce e scrittura.",
         "Roving Aim: Steady Aim doesn't set your Speed to 0. Masterful Mimicry: after 1 hour of study you imitate voice and writing."),
        passive=True),
    _as("envenom_weapons", 13, "Armi Velenose", "Envenom Weapons", 134,
        ("Con Veleno, se il TS fallisce il bersaglio subisce anche 2d6 danni da veleno, che ignorano la Resistenza.",
         "With Poison, on a failed save the target also takes 2d6 poison damage, ignoring Resistance."),
        roll_options=(ENVENOM,), passive=True),
    _as("death_strike", 17, "Colpo Mortale", "Death Strike", 134,
        ("Nel primo round, se l'Attacco Furtivo colpisce il bersaglio fa un TS Costituzione: se fallisce i danni sono raddoppiati.",
         "In the first round, when Sneak Attack hits the target makes a Constitution save: on a failure the damage is doubled."),
        roll_options=(DEATH_STRIKE,), passive=True, dc_ability="dexterity"),
)


# ---------------------------------------------------------------------------
# Coltello dell'Anima
# ---------------------------------------------------------------------------

def _psi_die(ctx: RuleContext) -> str:
    level = ctx.class_level
    return f"1d{6 if level < 5 else 8 if level < 11 else 10 if level < 17 else 12}"


def _restore_toggle() -> UseToggle:
    return UseToggle("restore", _both("Spendi un Dado Energia Psionica invece dell'uso", "Spend a Psionic Energy Die instead of the use"))


def _bare(ctx: RuleContext) -> bool:
    return ctx.item is None and ctx.spell is None and ctx.attack_mode not in ("companion", "beast", "form")  # la lama è tua, non del compagno


def _blade_used(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    ctx.char.turn_state = {**(ctx.char.turn_state or {}), BLADE_USED: True}


PSYCHIC_BLADE = RollOptionSpec(
    key=BLADE, phase="before", rolls=("attack",), available=_bare, group="psychic_blade", on_confirm=_blade_used,
    defers_damage=True,  # apre Attacco Furtivo e le altre opzioni dopo il colpo
    unarmed_dice=lambda _c, _i: "1d6", unarmed_damage_type="psychic", finesse_unarmed=True,
    label=_both("Lama Psichica: manifesta la lama (1d6 psichico, Accurata, Lanciabile 18/36 m)",
                "Psychic Blade: manifest the blade (1d6 psychic, Finesse, Thrown 60/120 ft)"),
    effect=lambda _c, _i: _both("Lama Psichica: padronanza Vessazione (non conta nel limite); svanisce dopo l'attacco. Con Accurata usi la migliore fra Forza e Destrezza.",
                                "Psychic Blade: Vex mastery (doesn't count toward your limit); it vanishes after the attack. Finesse: use the better of Strength and Dexterity."))
PSYCHIC_BLADE_BONUS = RollOptionSpec(
    key=BLADE_BONUS, phase="before", rolls=("attack",), slot="bonus", group="psychic_blade", on_confirm=_blade_used,
    defers_damage=True,
    available=lambda c: _bare(c) and bool((c.turn or {}).get(BLADE_USED)),
    unarmed_dice=lambda _c, _i: "1d4", unarmed_damage_type="psychic", finesse_unarmed=True,
    label=_both("Lama Psichica, azione bonus: secondo attacco con una nuova lama (1d4 psichico), mano libera",
                "Psychic Blade, bonus action: a second attack with a new blade (1d4 psychic), free hand"))
KNACK = RollOptionSpec(
    key=f"{CK}.psi_bolstered_knack", phase="after_roll", after="add", rolls=("skill",), cost=Cost(feature_key=PSI), pay_if_success=True,
    extra_dice=lambda c, _i: _psi_die(c), available=_proficient_skill_check,
    label=_both("Conoscenza Potenziata da Psi: prova fallita con una competenza? Spendi un Dado Energia e sommalo (il dado torna se fallisce comunque)",
                "Psi-Bolstered Knack: failed a proficient check? Spend an Energy Die and add it (the die comes back if it still fails)"))
HOMING = RollOptionSpec(
    key=f"{CK}.homing_strikes", phase="after_roll", after="add", rolls=("attack",), cost=Cost(feature_key=PSI), pay_if_success=True,
    extra_dice=lambda c, _i: _psi_die(c), available=lambda c: _bare(c) and _blade_sneak(c),  # solo con la lama psichica
    label=_both("Colpi Guidati: la Lama Psichica ha mancato? Spendi un Dado Energia e sommalo al tiro (il dado torna se manca comunque)",
                "Homing Strikes: did the Psychic Blade miss? Spend an Energy Die and add it to the roll (the die comes back if it still misses)"))


def _blade_sneak(ctx: RuleContext) -> bool:
    return any(k in ctx.confirmed for k in (BLADE, BLADE_BONUS))


PSYCHIC_BLADE_VEX = RollOptionSpec(
    key=f"{CK}.psychic_blade_vex", phase="after_hit", rolls=("attack",), once_per_turn=True, available=_blade_sneak, on_confirm=_arm_vex,
    label=_both("Lama Psichica, padronanza Vessazione: hai colpito? Vantaggio al prossimo attacco contro il bersaglio",
                "Psychic Blade, Vex mastery: did you hit? Advantage on your next attack against the target"),
    effect=lambda _c, _i: _both("Vex: vantaggio al prossimo attacco contro il bersaglio, entro la fine del tuo prossimo turno.",
                                "Vex: advantage on your next attack against the target, by the end of your next turn."))


def _rend(key: str, cost: Cost, it: str, en: str) -> RollOptionSpec:
    return RollOptionSpec(
        key=key, phase="after_hit", rolls=("attack",), needs=SNEAK, cost=cost, group="rend_mind", available=_blade_sneak,
        label=_both(it, en),
        effect=lambda c, _i: _both(f"Dilaniare la Mente: TS Saggezza del bersaglio, CD {_dc(c)}. Se fallisce è Stordito per 1 minuto e ripete il TS a fine di ogni suo turno.",
                                   f"Rend Mind: the target's Wisdom save, DC {_dc(c)}. On a failure it is Stunned for 1 minute and repeats the save at the end of each of its turns."),
        target_effect=lambda c, _i: TargetEffect(condition="stunned", save_ability="wisdom", save_dc=_dc(c), rounds=10, repeat_save="end"))


REND = _rend(f"{CK}.rend_mind", Cost(feature_key=f"{CK}.rend_mind"),
             "Dilaniare la Mente: Attacco Furtivo con la lama, il bersaglio fa un TS Saggezza o è Stordito (un uso)",
             "Rend Mind: Sneak Attack with the blade, the target makes a Wisdom save or is Stunned (one use)")
REND_DICE = _rend(f"{CK}.rend_mind_dice", Cost(feature_key=PSI, amount=3),
                  "Dilaniare la Mente senza l'uso: spendi tre Dadi Energia Psionica",
                  "Rend Mind without the use: spend three Psionic Energy Dice")

_sk = _sub(("Coltello dell'Anima", "Soulknife"), "soulknife")
SOULKNIFE = (
    _sk("psionic_power", 3, "Potere Psionico", "Psionic Power", 135,
        ("Dadi Energia Psionica: 4d6 (3), 6d8 (5), 8d8 (9), 8d10 (11), 10d10 (13), 12d12 (17). Riposo breve: un dado, lungo: tutti.",
         "Psionic Energy Dice: 4d6 (3), 6d8 (5), 8d8 (9), 8d10 (11), 10d10 (13), 12d12 (17). Short rest: one die, long rest: all."),
        uses=Uses(table={3: 4, 5: 6, 9: 8, 11: 8, 13: 10, 17: 12}), restoration="long_rest", short_rest_recovers=1),
    _sk("psi_bolstered_knack", 3, "Conoscenza Potenziata da Psi", "Psi-Bolstered Knack", 135,
        ("Dopo una prova fallita con un'abilità in cui sei competente, spendi un Dado Energia e lo sommi; il dado si spende solo se riesce.",
         "After a failed check with a skill you are proficient in, spend an Energy Die and add it; it is spent only if the check succeeds."),
        roll_options=(KNACK,), passive=True),
    _sk("psychic_whispers", 3, "Sussurri Psichici", "Psychic Whispers", 135,
        ("Azione Magia: creature fino alla competenza parlano con te in telepatia per tante ore quante il dado. La prima volta per riposo lungo è gratis.",
         "Magic action: creatures up to your proficiency bonus talk to you telepathically for as many hours as the die. The first use per long rest is free."),
        "action", uses=Uses(table={3: 1}), restoration="long_rest",
        on_use=OnUse(slot="action", alt_spends=PSI, toggles=(_restore_toggle(),), rolls=_psi_die,
                     message=lambda c, _p: _both(
                         f"Fino a {c.char.proficiency_bonus} creature entro 1,6 km: telepatia per tante ore quante il risultato del dado.",
                         f"Up to {c.char.proficiency_bonus} creatures within 1 mile: telepathy for as many hours as the die result."))),
    _sk("psychic_blades", 3, "Lame Psichiche", "Psychic Blades", 136,
        ("Con l'azione Attacco manifesti una lama (1d6 psichico, Accurata, Lanciabile); poi con l'azione bonus una seconda lama da 1d4.",
         "With the Attack action you manifest a blade (1d6 psychic, Finesse, Thrown); then a second 1d4 blade as a bonus action."),
        roll_options=(PSYCHIC_BLADE, PSYCHIC_BLADE_BONUS, PSYCHIC_BLADE_VEX), passive=True),
    _sk("soul_blades", 9, "Lame dell'Anima", "Soul Blades", 136,
        ("Sblocca Colpi Guidati e Teletrasporto Psichico per le Lame Psichiche.", "Unlocks Homing Strikes and Psychic Teleportation for the Psychic Blades."),
        passive=True),
    _sk("homing_strikes", 9, "Colpi Guidati", "Homing Strikes", 136,
        ("Dopo un attacco mancato con la lama puoi spendere un Dado Energia e sommarlo al tiro; il dado si spende solo se colpisci.",
         "After a missed attack with the blade you can spend an Energy Die and add it to the roll; it is spent only if you hit."),
        parent="Lame dell'Anima", roll_options=(HOMING,), passive=True),
    _sk("psychic_teleportation", 9, "Teletrasporto Psichico", "Psychic Teleportation", 136,
        ("Azione bonus: spendi e tira un Dado Energia; ti teletrasporti di 3 m per punto del risultato in uno spazio libero che vedi.",
         "Bonus action: spend and roll an Energy Die; you teleport 10 ft per point of the result to an unoccupied space you can see."),
        "bonus_action", parent="Lame dell'Anima",
        on_use=OnUse(slot="bonus", spends=PSI, rolls=_psi_die,
                     message=lambda _c, p: _both(f"Distanza: {3 * p['dice_total']} m (3 m per ogni punto del dado), in uno spazio libero e visibile.",
                                                 f"Distance: {10 * p['dice_total']} ft (10 ft for each point of the die), to an unoccupied space you can see."))),
    _sk("psychic_veil", 13, "Velo Psichico", "Psychic Veil", 136,
        ("Azione Magia: Invisibile per 1 ora; finisce se infliggi danno o imponi un TS. Un uso per riposo lungo, o un Dado Energia.",
         "Magic action: Invisible for 1 hour; it ends if you deal damage or force a save. One use per long rest, or an Energy Die."),
        "action", uses=Uses(table={13: 1}), restoration="long_rest",
        on_use=OnUse(slot="action", alt_spends=PSI, toggles=(_restore_toggle(),),
                     state=StateSpec("psychic_veil", rounds=600, ends_on=("attack", "cast", "manual"), condition="invisible",
                                    data={"refund_on_miss": True, "needs_effect": True}),
                     message=lambda _c, _p: _both("Invisibile per 1 ora: termina se infliggi danno o imponi un TS (l'attacco lo chiude e, se dichiari il mancato, torna; un incantesimo solo se ha danni o un TS).",
                                                  "Invisible for 1 hour: it ends when you deal damage or force a save (an attack ends it and, if you declare a miss, it comes back; a spell only if it has damage or a save)."))),
    _sk("rend_mind", 17, "Dilaniare la Mente", "Rend Mind", 136,
        ("Con l'Attacco Furtivo di una lama: TS Saggezza o Stordito 1 minuto. Un uso per riposo lungo, o tre Dadi Energia.",
         "With a blade's Sneak Attack: Wisdom save or Stunned for 1 minute. One use per long rest, or three Energy Dice."),
        uses=Uses(table={17: 1}), restoration="long_rest", roll_options=(REND, REND_DICE), dc_ability="dexterity"),
)


# ---------------------------------------------------------------------------
# Furfante
# ---------------------------------------------------------------------------

FAST_HANDS_USE = OnUse(
    slot="bonus", notes=lambda _c, params: [f"cunning_{params['action']}"],
    choices=(UseChoice("action", _both("Azione bonus", "Bonus action"), lambda _c: ["sleight_of_hand", "use_object"], _cunning_label),))


def _keep_hiding(_session: Any, ctx: RuleContext, _inputs: dict) -> None:
    """Furtività Suprema: il tiro per colpire ha già chiuso il nascondiglio (``end_hide``); la conferma lo ripristina."""
    turn = dict(ctx.char.turn_state or {})
    hiding = turn.pop("hide_broken", None)
    if hiding:
        ctx.char.settings = {**(ctx.char.settings or {}), "hiding": hiding}
        ctx.char.conditions = {**(ctx.char.conditions or {}), "invisible": True}
        ctx.char.turn_state = turn


def _score(ctx: RuleContext, ability: str) -> int:
    from core.game.stats import effective_ability_score  # import locale: stats usa il catalogo
    row = next((a for a in ctx.char.ability_scores if a.name == ability), None)
    return effective_ability_score(ability, row.value, [i for i in ctx.char.items if i.is_equipped])[0] if row else 10


def _jump_bonus(ctx: RuleContext) -> int:
    """Il salto in lungo vale il punteggio in piedi: con Destrezza al posto di Forza guadagna la differenza, se positiva."""
    return max(0, _score(ctx, "dexterity") - _score(ctx, "strength"))


SUPREME_SNEAK = replace(_cunning(
    "supreme_sneak", 1, "Attacco Furtivo di Nascosto (1d6): resti Invisibile da Nascondersi se finisci il turno dietro Copertura",
    "Sneak Attack from Hiding (1d6): you stay Invisible from Hide if you end the turn behind Cover",
    effect=lambda _c, _i: _both("Furtività Suprema: se hai la condizione Invisibile da Nascondersi, l'attacco non la fa terminare se finisci il turno dietro Copertura Tre Quarti o Totale.",
                                "Supreme Sneak: if you are Invisible from the Hide action, the attack doesn't end it if you end the turn behind Three-Quarters or Total Cover.")),
    on_confirm=_keep_hiding)

_th = _sub(("Furfante", "Thief"), "thief")
THIEF = (
    _th("fast_hands", 3, "Mani Veloci", "Fast Hands", 137,
        ("Azione bonus: Rapidità di Mano (prova di Destrezza per scassinare, disarmare una trappola, borseggiare) oppure Usare un Oggetto.",
         "Bonus action: Sleight of Hand (Dexterity check to pick a lock, disarm a trap, pick a pocket) or Use an Object."),
        "bonus_action", on_use=FAST_HANDS_USE),
    _th("second_story_work", 3, "Lavoro al Secondo Piano", "Second-Story Work", 137,
        ("Velocità di scalata pari alla Velocità; per il salto in lungo usi Destrezza al posto di Forza (la scheda mostra il bonus).",
         "Climb speed equal to your Speed; for the long jump you use Dexterity instead of Strength (the sheet shows the bonus)."),
        modifiers=(Modifier("climb_speed", 1, source=f"feature:{CK}.second_story_work"),
                   Modifier("jump_bonus", _jump_bonus, when=lambda c: c.roll is None, source=f"feature:{CK}.second_story_work")), passive=True),
    _th("supreme_sneak", 9, "Furtività Suprema", "Supreme Sneak", 137,
        ("Nuova opzione di Colpo Astuto, Attacco Furtivo di Nascosto (1d6): da Invisibile per Nascondersi non perdi la condizione dietro Copertura.",
         "New Cunning Strike option, Sneak Attack from Hiding (1d6): from Hide's Invisible you keep the condition behind Cover."),
        roll_options=(SUPREME_SNEAK,), passive=True),
    _th("use_magic_device", 13, "Usare Dispositivi Magici", "Use Magic Device", 137,
        ("Sintonia con 4 oggetti; con 1d6 a 6 non spendi cariche. Pergamene: dal 2° livello prova di Intelligenza (Arcano) CD 10 + livello, o si disintegra.",
         "Attune to 4 items; a 6 on 1d6 spends no charge. Scrolls: from level 2 an Intelligence (Arcana) check, DC 10 + level, or it disintegrates."),
        passive=True),
    _th("thiefs_reflexes", 17, "Riflessi del Furfante", "Thief's Reflexes", 137,
        ("Nel primo round di ogni combattimento hai due turni: all'Iniziativa e all'Iniziativa meno 10. L'incontro aggiunge il secondo turno.",
         "In the first round of each combat you take two turns: at your Initiative and at your Initiative minus 10. The encounter adds the second turn."),
        passive=True),
)

SUBCLASS_ROWS = (*ARCANE_TRICKSTER, *ASSASSIN, *SOULKNIFE, *THIEF)
